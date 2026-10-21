"""Bancada de experimentos: o agente escolhe a receita, as regras de avaliação são fixas.

Cada experimento treina no mesmo split temporal da base inteira, mas só nas linhas que têm
todas as camadas pedidas. Por isso ele sempre é comparado, nas mesmas linhas de teste, com o
baseline do canal e com um controle só de metadados: o ganho de cada receita é relativo ao
seu próprio baseline, o que torna receitas com subconjuntos diferentes comparáveis.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

import duckdb
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from galaxies import atributos as atrib
from galaxies import modelagem as m

# metadados, historico e texto existem para todos os vídeos; multimodal e atributos, só
# para os que têm camada bruta do gancho.
Camada = Literal["metadados", "historico", "texto", "titulo", "multimodal", "atributos"]
COBERTURA_ALVO = 0.8  # a faixa q10–q90 é calibrada para conter 80% dos casos
FRACAO_CALIBRACAO = 0.2  # fim do treino separado para calibrar a faixa
Status = Literal["candidato", "aguardando_aprovacao", "ativo", "aposentado", "rejeitado"]
MIN_TREINO, MIN_TESTE = 50, 10
AMOSTRA_PEQUENA = 100


class Params(BaseModel):
    """Hiperparâmetros que o agente pode mexer, dentro de limites seguros."""

    num_leaves: int = Field(default=31, ge=4, le=127)
    learning_rate: float = Field(default=0.05, ge=0.005, le=0.3)
    rodadas: int = Field(default=300, ge=20, le=2000)
    min_data_in_leaf: int = Field(default=20, ge=5, le=200)
    # Peso por recência: metade a cada meia-vida. None = todos os vídeos pesam igual.
    meia_vida_dias: int | None = Field(default=None, ge=30, le=3000)


class Receita(BaseModel):
    camadas: list[Camada] = Field(min_length=1)
    atributos: list[str] | None = None  # None = todos os atributos do projeto
    # Quem respondeu os atributos (laya, um modelo @cf/*, typesafe/jev). None = o atual.
    extrator: str | None = None
    params: Params = Params()
    # A que o alvo é relativo: mediana do canal no treino (fixa) ou a média dos últimos 10
    # vídeos do canal, defasada 7 dias (móvel: segue o momento do canal e a deriva do setor).
    ancora: Literal["mediana_canal", "movel"] = "mediana_canal"

    @model_validator(mode="after")
    def _metadados_sempre(self):
        if "metadados" not in self.camadas:
            raise ValueError("toda receita inclui a camada 'metadados'")
        if self.ancora == "movel" and "historico" not in self.camadas:
            raise ValueError("ancora 'movel' precisa da camada 'historico'")
        return self


class Resultado(BaseModel):
    n_treino: int
    n_teste: int
    colunas: list[str]
    baseline: m.Metricas  # média do canal, nas mesmas linhas de teste
    controle_metadados: m.Metricas  # só metadados e hiperparâmetros padrão, mesmas linhas
    modelo: m.Metricas
    ganho: float  # 1 - MAE do modelo / MAE do baseline (positivo = melhor)
    # Fração do teste dentro da faixa de 80%: crua e depois da calibração conformal.
    cobertura_bruta: float = 0.0
    cobertura_80: float = 0.0
    cobertura_50: float = 0.0  # faixa "provável" (q25–q75 derivada da calibrada)
    calibracao: float = 1.0  # quanto a faixa foi alargada
    confianca_sobre_controle: float = 0.5  # bootstrap pareado: P(modelo bate o controle)
    melhora_sobre_controle: float = 0.0  # 1 - MAE do modelo / MAE do controle
    ganho_por_atributo: dict[str, float] = {}
    piores: list[m.Erro] = []
    segmentos: dict[str, list[m.Segmento]] = {}
    sugestoes: list[str] = []


class Experimento(BaseModel):
    id: str
    alvo: str
    receita: Receita
    hipotese: str = ""
    resultado: Resultado
    status: Status = "candidato"
    nota_humana: str = ""
    criado_em: datetime


MARGEM_SOBRE_CONTROLE = 0.01  # camadas extras precisam reduzir o MAE do controle em 1%+
CONFIANCA_MINIMA = 0.9  # bootstrap pareado no teste: camadas extras precisam de ganho real


def escolher(feitos: list["Experimento"]) -> "Experimento | None":
    """Ganhos de receitas com linhas diferentes não são comparáveis entre si. Regra:
    1. só concorre quem supera o baseline do canal;
    2. receitas com camadas extras precisam bater o controle só de metadados nas mesmas
       linhas por MARGEM_SOBRE_CONTROLE; entre elas vence a maior melhora sobre o controle;
    3. se nenhuma bater, vence o melhor só de metadados."""
    validos = [e for e in feitos if e.resultado.ganho > 0]
    ricos = [e for e in validos if e.receita.camadas != ["metadados"]]
    ricos = [e for e in ricos if e.resultado.melhora_sobre_controle >= MARGEM_SOBRE_CONTROLE]
    if ricos:
        return max(ricos, key=lambda e: e.resultado.melhora_sobre_controle)
    simples = [e for e in validos if e.receita.camadas == ["metadados"]]
    return max(simples, key=lambda e: e.resultado.ganho) if simples else None


TOLERANCIA_VS_ATIVO = 0.02  # novo pode ficar até 2 pontos abaixo do ativo vs baseline


def motivo_para_nao_promover(exp: "Experimento", ativo: "Experimento | None") -> str | None:
    """Trava da promoção automática: o teste é a palavra final, não a validação."""
    r = exp.resultado
    if r.ganho <= 0:
        return "não supera a média do canal no teste"
    if exp.receita.camadas != ["metadados"] and r.melhora_sobre_controle < MARGEM_SOBRE_CONTROLE:
        return (
            f"as camadas extras melhoram só {r.melhora_sobre_controle:+.1%} sobre o controle no "
            f"teste (mínimo {MARGEM_SOBRE_CONTROLE:.0%}); fica como candidato"
        )
    if exp.receita.camadas != ["metadados"] and r.confianca_sobre_controle < CONFIANCA_MINIMA:
        return (
            f"no teste, o ganho sobre o controle é indistinguível de acaso (confiança "
            f"{r.confianca_sobre_controle:.0%}, mínimo {CONFIANCA_MINIMA:.0%}); fica como candidato"
        )
    if ativo is not None and r.ganho < ativo.resultado.ganho - TOLERANCIA_VS_ATIVO:
        return (
            f"ganho no teste ({r.ganho:+.1%}) fica abaixo do modelo ativo "
            f"({ativo.resultado.ganho:+.1%}); fica como candidato"
        )
    return None


class Ciclo(BaseModel):
    experimentos: list[Experimento]
    promovido: str | None
    motivo: str | None = None  # por que a escolhida não foi promovida
    pulados: dict[str, str] = {}  # receita → motivo
    tentativas: list[dict] = []  # busca na validação (otimizacao.Tentativa)
    objetivo_validacao: float | None = None


RECEITAS_PADRAO = {
    "metadados": Receita(camadas=["metadados"]),
    "historico": Receita(camadas=["metadados", "historico"]),
    "texto": Receita(camadas=["metadados", "texto"]),
    "titulo": Receita(camadas=["metadados", "historico", "titulo"]),
    "movel": Receita(camadas=["metadados", "historico"], ancora="movel"),
    "historico+texto": Receita(camadas=["metadados", "historico", "texto"]),
    "historico+texto+multimodal": Receita(
        camadas=["metadados", "historico", "texto", "multimodal"]
    ),
    "completo": Receita(camadas=["metadados", "historico", "texto", "multimodal", "atributos"]),
}
# Variações de hiperparâmetros testadas sobre a melhor receita do ciclo.
PARAMS_DA_BUSCA = {
    "mais_suave": Params(num_leaves=15, learning_rate=0.03, rodadas=600, min_data_in_leaf=40),
    "mais_detalhe": Params(num_leaves=63, learning_rate=0.05, rodadas=400, min_data_in_leaf=20),
}


# ---------------------------------------------------------------- treino de uma receita


def treinar(
    banco: duckdb.DuckDBPyConnection,
    alvo: str,
    receita: Receita,
    definicoes: list[atrib.Atributo],
    pasta_modelos: Path,
    hipotese: str = "",
    extrator_atual: str | None = None,
) -> Experimento:
    """Avalia a receita no teste (uma vez), registra e salva o modelo final."""
    receita, resultado, ctx = avaliar(banco, alvo, receita, definicoes, extrator_atual)
    experimento = Experimento(
        id=uuid.uuid4().hex[:10],
        alvo=alvo,
        receita=receita,
        hipotese=hipotese,
        resultado=resultado,
        criado_em=m.agora(),
    )
    _modelo_final(*ctx, pasta_modelos / experimento.id)
    return experimento


def avaliar(
    banco: duckdb.DuckDBPyConnection,
    alvo: str,
    receita: Receita,
    definicoes: list[atrib.Atributo],
    extrator_atual: str | None = None,
    em: Literal["teste", "validacao"] = "teste",
    cache: dict | None = None,
) -> tuple[Receita, Resultado, tuple]:
    """Mede a receita. em='validacao' usa o fim do período de treino como teste: é onde a
    otimização compara receitas, para o teste ser usado uma vez só, na escolhida."""
    cache = {} if cache is None else cache
    if "atributos" in receita.camadas and receita.extrator is None:
        receita = receita.model_copy(update={"extrator": extrator_atual})
    escolhidos = _atributos_da_receita(receita, definicoes)
    if ("base", alvo) not in cache:
        cache[("base", alvo)] = m.montar_base(banco, alvo)
    base = cache[("base", alvo)]
    treino, teste, _ = m.dividir(base)
    if em == "validacao":
        treino, teste, _ = m.dividir(treino)
    setores = sorted(base["setor"].unique())
    canais = m.estatisticas_dos_canais(treino)

    extras, tem = _camadas_extras(banco, base, receita, escolhidos, alvo, cache)
    tr, te = treino.index[tem.loc[treino.index]], teste.index[tem.loc[teste.index]]
    if len(tr) < MIN_TREINO or len(te) < MIN_TESTE:
        raise ValueError(
            f"receita com poucos dados ({len(tr)} treino, {len(te)} teste): processe mais "
            "ganchos, calcule os atributos ou o texto"
        )
    x_meta = m.features_de_metadados(base, canais, setores)
    x, _ = _montar_x(x_meta, extras, tr, te)
    y_fixo = m.alvo_relativo(base, canais)
    anc = _ancora_log(base, canais, extras, receita)
    y = base["log_y"] - anc

    modelos = _quantis(x.loc[tr], y.loc[tr], receita.params, base.loc[tr, "publicado_em"])
    controle = _quantis(x_meta.loc[tr], y_fixo.loc[tr], Params())  # referência fixa
    sub_te = base.loc[te]
    ancora = anc.loc[te].to_numpy()
    q = {k: b.predict(x.loc[te]) + ancora for k, b in modelos.items()}
    pred = q[0.5]
    k = _calibrar(base, tr, x, y, receita.params)
    resultado_modelo = m.medir(pred, sub_te)
    baseline = m.medir(m.predicao_baseline(sub_te, canais), sub_te)
    piores, segmentos = m.diagnosticar(pred, sub_te)
    pred_controle = m.prever_log(controle, x_meta.loc[te], sub_te, canais)
    controle_m = m.medir(pred_controle, sub_te)
    real = sub_te["log_y"].to_numpy()
    confianca = m.confianca_pareada(np.abs(pred - real), np.abs(pred_controle - real))
    resultado = Resultado(
        n_treino=len(tr),
        n_teste=len(te),
        colunas=list(x.columns),
        baseline=baseline,
        controle_metadados=controle_m,
        modelo=resultado_modelo,
        ganho=1 - resultado_modelo.mae / baseline.mae,
        melhora_sobre_controle=1 - resultado_modelo.mae / controle_m.mae,
        confianca_sobre_controle=confianca,
        cobertura_bruta=_cobertura(q, real, 1.0),
        cobertura_80=_cobertura(q, real, k),
        cobertura_50=_cobertura(q, real, k, estreita=True),
        calibracao=k,
        ganho_por_atributo=_ganho_por_permutacao(
            modelos, x.loc[te], sub_te, canais, escolhidos, resultado_modelo.mae
        ),
        piores=piores,
        segmentos=segmentos,
    )
    resultado.sugestoes = sugerir(receita, resultado)
    return receita, resultado, (base, tem, extras, receita, escolhidos, k)


def _atributos_da_receita(receita: Receita, definicoes: list[atrib.Atributo]):
    if "atributos" not in receita.camadas:
        return []
    if receita.atributos is None:
        return definicoes
    por_id = {a.id: a for a in definicoes}
    desconhecidos = sorted(set(receita.atributos) - set(por_id))
    if desconhecidos:
        raise ValueError(f"atributos inexistentes no projeto: {desconhecidos}")
    return [por_id[i] for i in receita.atributos]


def _camadas_extras(banco, base, receita, escolhidos, alvo, cache=None) -> tuple[dict, pd.Series]:
    """DataFrames das camadas extras (índice da base) e quais linhas têm todas."""
    cache = {} if cache is None else cache

    def memo(chave, calcular):
        if chave not in cache:
            cache[chave] = calcular()
        return cache[chave]

    extras, tem = {}, pd.Series(True, index=base.index)
    if "historico" in receita.camadas:  # NaN quando o canal ainda não tem passado: o
        hist = memo(("historico", alvo), lambda: m.historico_do_banco(banco, alvo))  # LGBM lida
        hist = hist.reindex(base["video_id"])
        hist.index = base.index
        extras["historico"] = hist
    if "texto" in receita.camadas:
        texto = memo(("texto", alvo), lambda: _embeddings(banco, "texto_embedding", base))
        if texto is None:
            raise ValueError("camada texto sem embeddings: rode calcular_texto antes")
        extras["texto"] = texto
        tem &= texto.notna().all(axis=1)
    if "titulo" in receita.camadas:
        titulo = memo(("titulo",), lambda: _features_de_titulo(banco, base))
        if titulo is None:
            raise ValueError("camada titulo sem respostas: rode calcular_titulos antes")
        extras["titulo"] = titulo
        tem &= titulo.notna().all(axis=1)
    if "multimodal" in receita.camadas:
        emb = memo(("multimodal", alvo), lambda: _embeddings(banco, "camada_bruta", base))
        if emb is None:
            emb = pd.DataFrame(index=base.index, columns=[0], dtype=float)
        extras["multimodal"] = emb
        tem &= emb.notna().all(axis=1)
    if escolhidos:
        feats = pd.DataFrame(atrib.features(banco, escolhidos, receita.extrator))
        colunas = _colunas_de_atributos(escolhidos)
        if feats.empty:
            feats = pd.DataFrame(columns=["video_id", *colunas])
        feats = feats.set_index("video_id").reindex(base["video_id"])[colunas]
        feats.index = base.index
        extras["atributos"] = feats
        tem &= feats.notna().all(axis=1)
    return extras, tem


def _ancora_log(base, canais, extras, receita) -> pd.Series:
    """log(1 + âncora) por linha da base. Fixa: mediana do canal no treino. Móvel: média dos
    últimos 10 vídeos (log, defasada 7 dias); sem passado, cai na fixa."""
    fixa = pd.Series(
        np.log1p(canais.reindex(base["canal_id"])["mediana"].to_numpy()), index=base.index
    )
    if receita.ancora != "movel":
        return fixa
    return extras["historico"]["hist_media_10"].fillna(fixa)


def _features_de_titulo(banco, base: pd.DataFrame) -> pd.DataFrame | None:
    """Respostas do extrator rápido às perguntas de título, uma linha por vídeo da base."""
    definicoes = list(atrib.DE_TITULO)
    feats = pd.DataFrame(atrib.features(banco, definicoes))
    if feats.empty:
        return None
    colunas = _colunas_de_atributos(definicoes)
    feats = feats.set_index("video_id").reindex(base["video_id"])[colunas]
    feats.index = base.index
    return feats


def _embeddings(banco, tabela: str, base: pd.DataFrame) -> pd.DataFrame | None:
    linhas = banco.execute(f"SELECT video_id, embedding FROM {tabela}").fetchall()
    if not linhas:
        return None
    emb = pd.DataFrame({v: e for v, e in linhas}).T.reindex(base["video_id"].to_numpy())
    emb.index = base.index
    return emb


PREFIXO_PCA = {"multimodal": "siglip", "texto": "texto"}


def _montar_x(x_meta, extras, ajuste, aplicar) -> tuple[pd.DataFrame, dict]:
    """Junta as camadas. Embeddings viram PCA ajustado só nas linhas de `ajuste`."""
    x, pcas = x_meta, {}
    if "historico" in extras:
        hist = extras["historico"]
        x = x.join(hist).assign(hist_rel_10=hist["hist_media_10"] - x_meta["log_mediana_canal"])
    for camada, prefixo in PREFIXO_PCA.items():
        if camada in extras:
            emb = extras[camada]
            linhas = ajuste.union(aplicar)
            red_tr, red_te, pca = m.reduzir_embeddings(emb.loc[ajuste], emb.loc[linhas])
            x = x.join(red_te.rename(columns=lambda c, p=prefixo: c.replace("siglip", p)))
            pcas[camada] = pca
    if "titulo" in extras:
        x = x.join(extras["titulo"])
    if "atributos" in extras:
        x = x.join(extras["atributos"])
    return x, pcas


def _calibrar(base, tr, x, y, params) -> float:
    """Conformal: treina sem o fim do período de treino, mede nesse fim quanto a faixa
    q10–q90 precisa alargar para conter COBERTURA_ALVO dos casos."""
    datas = base.loc[tr, "publicado_em"]
    corte = datas.quantile(1 - FRACAO_CALIBRACAO)
    ajuste, cal = tr[datas < corte], tr[datas >= corte]
    if len(ajuste) < MIN_TREINO or len(cal) < MIN_TESTE:
        return 1.0
    modelos = _quantis(x.loc[ajuste], y.loc[ajuste], params, base.loc[ajuste, "publicado_em"])
    q = {k: b.predict(x.loc[cal]) for k, b in modelos.items()}
    lo, mid, hi = np.sort(np.column_stack([q[0.1], q[0.5], q[0.9]]), axis=1).T
    real = y.loc[cal].to_numpy()
    escore = np.maximum(
        (mid - real) / np.maximum(mid - lo, 1e-6), (real - mid) / np.maximum(hi - mid, 1e-6)
    )
    return float(max(np.quantile(escore, COBERTURA_ALVO), 1e-3))


def alargar(q10, q50, q90, k: float):
    return q50 - k * (q50 - q10), q50 + k * (q90 - q50)


def _cobertura(q: dict, real: np.ndarray, k: float, estreita: bool = False) -> float:
    lo, mid, hi = np.sort(np.column_stack([q[0.1], q[0.5], q[0.9]]), axis=1).T
    lo, hi = alargar(lo, mid, hi, k)
    if estreita:
        lo, hi = m.faixa_50(lo, mid, hi)
    return float(np.mean((real >= lo) & (real <= hi)))


def _colunas_de_atributos(definicoes: list[atrib.Atributo]) -> list[str]:
    colunas = []
    for a in definicoes:
        if a.tipo == "choice":
            colunas += [f"{a.id}={rotulo}" for rotulo in a.criterios]
        else:
            colunas.append(a.id)
    return colunas


def _quantis(x, y, params: Params, datas: pd.Series | None = None):
    peso = None if datas is None else m.peso_por_recencia(datas, params.meia_vida_dias)
    return m.treinar_quantis(
        x, y, params.model_dump(exclude={"rodadas", "meia_vida_dias"}), params.rodadas, peso
    )


def _ganho_por_permutacao(modelos, x_te, teste, canais, definicoes, mae_base) -> dict:
    rng = np.random.default_rng(0)
    ganhos = {}
    for atributo in definicoes:
        colunas = [c for c in x_te.columns if c == atributo.id or c.startswith(f"{atributo.id}=")]
        embaralhado = x_te.copy()
        embaralhado[colunas] = x_te[colunas].to_numpy()[rng.permutation(len(x_te))]
        mae = m.medir(m.prever_log(modelos, embaralhado, teste, canais), teste).mae
        ganhos[atributo.id] = round(mae - mae_base, 5)
    return dict(sorted(ganhos.items(), key=lambda kv: -kv[1]))


def _modelo_final(base, tem, extras, receita, escolhidos, calibracao, pasta: Path):
    """Retreina em todas as linhas com as camadas e salva o que a análise precisa."""
    linhas = base.index[tem]
    sub = base.loc[linhas]
    canais = m.estatisticas_dos_canais(base)
    setores = sorted(base["setor"].unique())
    x_meta = m.features_de_metadados(sub, canais, setores)
    extras_sub = {k: v.loc[linhas] for k, v in extras.items()}
    x, pcas = _montar_x(x_meta, extras_sub, linhas, linhas[:0])
    y = sub["log_y"] - _ancora_log(sub, canais, extras_sub, receita)
    meta: dict = {"receita": receita.model_dump(), "setores": setores, "calibracao": calibracao}
    for camada, pca in pcas.items():
        meta[f"pca_{camada}"] = {
            "media": pca.mean_.tolist(),
            "componentes": pca.components_.tolist(),
            "prefixo": PREFIXO_PCA[camada],
        }
    if "atributos" in extras:
        meta["atributos"] = [a.model_dump() for a in escolhidos]
        meta["extrator"] = receita.extrator
    meta["titulo"] = "titulo" in extras
    modelos = _quantis(x, y, receita.params, sub["publicado_em"])
    meta |= {
        "colunas": list(x.columns),
        "canais": canais.reset_index().to_dict(orient="records"),
        "n": len(sub),
    }
    m.salvar_modelos(pasta, modelos, meta)


# ---------------------------------------------------------------- sugestões para o agente


def sugerir(receita: Receita, r: Resultado) -> list[str]:
    """Próximos passos a partir do resultado. Heurísticas simples e explícitas."""
    s = []
    if r.ganho <= 0:
        s.append("O modelo não supera o baseline do canal: não promova esta receita.")
    extra = r.modelo.mae - r.controle_metadados.mae
    camadas_extras = [c for c in receita.camadas if c != "metadados"]
    if camadas_extras and extra >= 0:
        s.append(
            f"As camadas {camadas_extras} não melhoraram o MAE sobre só metadados "
            f"({r.modelo.mae:.3f} vs {r.controle_metadados.mae:.3f}): teste sem elas ou "
            "reformule os atributos."
        )
    elif camadas_extras:
        s.append(f"As camadas {camadas_extras} reduziram o MAE em {-extra:.3f}: mantenha.")
    inuteis = [a for a, g in r.ganho_por_atributo.items() if g <= 0]
    uteis = [a for a, g in r.ganho_por_atributo.items() if g > 0]
    if inuteis:
        s.append(f"Atributos sem ganho (candidatos a remover ou reescrever): {inuteis}.")
    if uteis:
        s.append(f"Atributos que mais ajudam: {uteis[:3]}; crie variações mais específicas.")
    if r.n_teste < AMOSTRA_PEQUENA:
        s.append(
            f"Só {r.n_teste} vídeos no teste: processe ganchos da janela de teste "
            "(processar_ganchos com desde) para a comparação ficar confiável."
        )
    if canais := r.segmentos.get("canal"):
        pior = canais[0]
        if pior.mae > 2 * r.modelo.mae:
            s.append(
                f"O canal {pior.chave} tem MAE {pior.mae:.2f} (2x a média): verifique se os "
                "dados dele são atípicos e considere excluir."
            )
    if r.modelo.spearman_no_canal < 0.1:
        s.append("Spearman no canal baixo: o modelo quase não ordena vídeos do mesmo canal.")
    return s


# ---------------------------------------------------------------- persistência


def salvar(banco: duckdb.DuckDBPyConnection, exp: Experimento):
    banco.execute(
        "INSERT OR REPLACE INTO experimentos VALUES (?, ?, ?, ?, ?)",
        [exp.id, exp.alvo, exp.status, exp.criado_em, exp.model_dump_json()],
    )


def listar(banco: duckdb.DuckDBPyConnection, alvo: str | None = None) -> list[Experimento]:
    linhas = banco.execute(
        "SELECT dados FROM experimentos WHERE ? IS NULL OR alvo = ? ORDER BY criado_em",
        [alvo, alvo],
    ).fetchall()
    return [Experimento.model_validate_json(d) for (d,) in linhas]


def obter(banco: duckdb.DuckDBPyConnection, exp_id: str) -> Experimento:
    linha = banco.execute("SELECT dados FROM experimentos WHERE id = ?", [exp_id]).fetchone()
    if linha is None:
        raise ValueError(f"experimento '{exp_id}' não existe")
    return Experimento.model_validate_json(linha[0])


def ativar(banco: duckdb.DuckDBPyConnection, exp: Experimento) -> Experimento:
    for outro in listar(banco, exp.alvo):
        if outro.status == "ativo" and outro.id != exp.id:
            salvar(banco, outro.model_copy(update={"status": "aposentado"}))
    exp = exp.model_copy(update={"status": "ativo"})
    salvar(banco, exp)
    return exp


def ativo(banco: duckdb.DuckDBPyConnection, alvo: str) -> Experimento | None:
    return next((e for e in listar(banco, alvo) if e.status == "ativo"), None)


def carregar_meta(pasta: Path) -> dict:
    return json.loads((pasta / "meta.json").read_text())
