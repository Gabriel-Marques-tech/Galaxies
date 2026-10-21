"""Treino e avaliação honesta. As regras abaixo são fixas: o cliente não as altera.

Alvo: log((alvo + 1) / (mediana_do_canal + 1)), com a mediana calculada só no treino.
Split temporal: os 20% mais recentes viram teste, e só entram vídeos com 7+ dias de vida.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from pydantic import BaseModel
from scipy.stats import spearmanr
from sklearn.decomposition import PCA

FRACAO_TESTE = 0.2
IDADE_MINIMA_TESTE_DIAS = 7
MAX_POR_CANAL = 300  # canais gigantes não dominam o treino
MIN_VIDEOS_CANAL_SPEARMAN = 5
QUANTIS = (0.1, 0.5, 0.9)
# Faixa "provável" de 50% derivada da faixa calibrada de 80%: numa normal no log, a meia
# largura q25–q75 é z(0.75)/z(0.9) = 0.6745/1.2816 da meia largura q10–q90.
FRACAO_FAIXA_50 = 0.5263


def faixa_50(lo, mid, hi):
    """q25 e q75 a partir da faixa calibrada (lo, mid, hi), lado a lado."""
    return mid - FRACAO_FAIXA_50 * (mid - lo), mid + FRACAO_FAIXA_50 * (hi - mid)


DIMENSOES_SIGLIP = 16
PARAMS_LGB = {
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbose": -1,
    "seed": 42,
}
RODADAS = 300

_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")


class Split(BaseModel):
    fim_treino: datetime
    inicio_teste: datetime
    n_treino: int
    n_teste: int


class Metricas(BaseModel):
    mae: float
    spearman_no_canal: float
    n: int
    # A vs B: dos pares de vídeos do mesmo canal no teste, a fração que o modelo ordena
    # certo (empates contam meio). 0.5 = não ordena nada, como a média do canal.
    # None = não medido (experimentos antigos ou sem pares no teste).
    acerto_pares: float | None = None


class Erro(BaseModel):
    """Uma previsão do teste, em log(1 + alvo)."""

    video_id: str
    canal_id: str
    previsto: float
    real: float
    erro_log: float


class Segmento(BaseModel):
    chave: str
    mae: float
    n: int


class Avaliacao(BaseModel):
    alvo: str
    split: Split
    baseline: Metricas
    camadas: dict[str, Metricas]
    # Só existe quando há camada bruta: ablação no mesmo subconjunto de vídeos.
    baseline_subconjunto: Metricas | None = None
    ganho_por_atributo: dict[str, float] = {}
    # Diagnóstico da camada de metadados no teste: onde o modelo mais erra.
    piores: list[Erro] = []
    segmentos: dict[str, list[Segmento]] = {}
    criado_em: datetime


class RelatorioErros(BaseModel):
    falhas_por_etapa: dict[str, int]
    piores: list[Erro]
    segmentos: dict[str, list[Segmento]]
    origem: str = ""  # experimento ativo ou diagnóstico de onde vêm piores e segmentos
    notas_padrao: list[str] = []  # padrões apontados pelo humano: pistas para novos atributos


# ---------------------------------------------------------------- base e split


def montar_base(banco: duckdb.DuckDBPyConnection, alvo: str) -> pd.DataFrame:
    df = banco.execute(
        f"""
        SELECT v.id AS video_id, v.canal_id, c.setor, c.inscritos, v.titulo, v.descricao,
               v.tags, v.publicado_em, v.coletado_em, v.duracao_s, v.{alvo} AS y
        FROM videos v JOIN canais c ON c.id = v.canal_id
        WHERE v.{alvo} IS NOT NULL
          AND v.id NOT IN (SELECT id FROM excluidos WHERE tipo = 'video')
          AND v.canal_id NOT IN (SELECT id FROM excluidos WHERE tipo = 'canal')
        QUALIFY ROW_NUMBER() OVER (PARTITION BY v.canal_id ORDER BY v.publicado_em DESC)
                <= {MAX_POR_CANAL}
        ORDER BY v.publicado_em
        """
    ).df()
    df["publicado_em"] = pd.to_datetime(df["publicado_em"], utc=True)
    df["coletado_em"] = pd.to_datetime(df["coletado_em"], utc=True)
    df["idade_dias"] = (df["coletado_em"] - df["publicado_em"]).dt.total_seconds() / 86400
    df["log_y"] = np.log1p(df["y"].astype(float))
    return df


def dividir(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, Split]:
    corte = df["publicado_em"].quantile(1 - FRACAO_TESTE)
    treino = df[df["publicado_em"] < corte]
    teste = df[(df["publicado_em"] >= corte) & (df["idade_dias"] >= IDADE_MINIMA_TESTE_DIAS)]
    teste = teste[teste["canal_id"].isin(treino["canal_id"])]  # canal precisa de histórico
    split = Split(
        fim_treino=treino["publicado_em"].max().to_pydatetime(),
        inicio_teste=teste["publicado_em"].min().to_pydatetime(),
        n_treino=len(treino),
        n_teste=len(teste),
    )
    return treino, teste, split


# ---------------------------------------------------------------- features


def estatisticas_dos_canais(historico: pd.DataFrame) -> pd.DataFrame:
    """Âncoras por canal, calculadas só sobre o histórico (treino)."""
    g = historico.groupby("canal_id")
    dias = (g["publicado_em"].max() - g["publicado_em"].min()).dt.days.clip(lower=1)
    return pd.DataFrame(
        {
            "mediana": g["y"].median(),
            "media_log": g["log_y"].mean(),
            "posts_por_30d": g.size() / dias * 30,
        }
    )


def features_de_metadados(
    df: pd.DataFrame, canais: pd.DataFrame, setores: list[str]
) -> pd.DataFrame:
    """setores fixa o código de cada setor entre treino, teste e análise."""
    titulo = df["titulo"].fillna("")
    descricao = df["descricao"].fillna("")
    local = df["publicado_em"].dt.tz_convert("America/Sao_Paulo")
    ancora = canais.reindex(df["canal_id"])
    return pd.DataFrame(
        {
            "duracao_s": df["duracao_s"],
            "hora": local.dt.hour,
            "dia_semana": local.dt.dayofweek,
            "log_idade_dias": np.log1p(df["idade_dias"].clip(lower=0)),
            "titulo_caracteres": titulo.str.len(),
            "titulo_palavras": titulo.str.split().str.len(),
            "titulo_pergunta": titulo.str.contains(r"\?").astype(int),
            "titulo_numero": titulo.str.contains(r"\d").astype(int),
            "titulo_exclamacao": titulo.str.contains("!").astype(int),
            "titulo_maiusculas": titulo.map(_fracao_maiusculas),
            "titulo_emojis": titulo.map(lambda t: len(_EMOJI.findall(t))),
            "hashtags": (titulo + " " + descricao).str.count(r"#\w"),
            "descricao_caracteres": descricao.str.len(),
            "tags": df["tags"].map(lambda t: len(json.loads(t)) if isinstance(t, str) else 0),
            "log_inscritos": np.log1p(df["inscritos"].astype(float)),
            "log_mediana_canal": np.log1p(ancora["mediana"].to_numpy()),
            "posts_por_30d": ancora["posts_por_30d"].to_numpy(),
            "setor": pd.Categorical(df["setor"], categories=setores).codes,
        },
        index=df.index,
    )


def _fracao_maiusculas(texto: str) -> float:
    letras = [c for c in texto if c.isalpha()]
    return sum(c.isupper() for c in letras) / len(letras) if letras else 0.0


def alvo_relativo(df: pd.DataFrame, canais: pd.DataFrame) -> pd.Series:
    return df["log_y"] - np.log1p(canais.reindex(df["canal_id"])["mediana"].to_numpy())


# ---------------------------------------------------------------- modelo e métricas


def treinar_quantis(
    x: pd.DataFrame,
    y: pd.Series,
    params: dict | None = None,
    rodadas: int = RODADAS,
    peso: np.ndarray | None = None,
) -> dict[float, lgb.Booster]:
    base = {**PARAMS_LGB, **(params or {})}
    dados = lgb.Dataset(x, y, weight=peso)
    return {
        q: lgb.train({**base, "objective": "quantile", "alpha": q}, dados, rodadas) for q in QUANTIS
    }


def peso_por_recencia(datas: pd.Series, meia_vida_dias: float | None) -> np.ndarray | None:
    """Peso 1 para o vídeo mais recente, metade a cada meia-vida para trás: o modelo
    acompanha a deriva do setor sem jogar fora o histórico."""
    if meia_vida_dias is None:
        return None
    idade = (datas.max() - datas).dt.total_seconds() / 86400
    return (0.5 ** (idade / meia_vida_dias)).to_numpy()


def confianca_pareada(erros_modelo: np.ndarray, erros_controle: np.ndarray, n: int = 1000) -> float:
    """Bootstrap pareado nas mesmas linhas: fração das reamostras em que o MAE do modelo fica
    abaixo do MAE do controle. ~0,5 = indistinguível; ≥ 0,9 = ganho real."""
    dif = np.asarray(erros_modelo) - np.asarray(erros_controle)
    if len(dif) == 0 or np.all(dif == 0):
        return 0.5
    rng = np.random.default_rng(0)
    amostras = rng.choice(dif, size=(n, len(dif)), replace=True).mean(axis=1)
    return float(np.mean(amostras < 0))


def medir(pred_log: np.ndarray, teste: pd.DataFrame) -> Metricas:
    mae = float(np.mean(np.abs(pred_log - teste["log_y"].to_numpy())))
    correlacoes, acertos, pares = [], 0.0, 0
    for _, grupo in pd.DataFrame(
        {"canal": teste["canal_id"].to_numpy(), "p": pred_log, "y": teste["log_y"].to_numpy()}
    ).groupby("canal"):
        if len(grupo) < MIN_VIDEOS_CANAL_SPEARMAN:
            continue
        rho = spearmanr(grupo["p"], grupo["y"]).statistic if grupo["p"].nunique() > 1 else 0.0
        correlacoes.append(0.0 if np.isnan(rho) else float(rho))
        p, y = grupo["p"].to_numpy(), grupo["y"].to_numpy()
        dp, dy = np.sign(p[:, None] - p[None, :]), np.sign(y[:, None] - y[None, :])
        validos = np.triu(dy != 0, k=1)  # pares em que um vídeo foi de fato melhor
        acertos += float(np.sum((dp == dy) & validos) + 0.5 * np.sum((dp == 0) & validos))
        pares += int(validos.sum())
    return Metricas(
        mae=mae,
        spearman_no_canal=float(np.mean(correlacoes)) if correlacoes else 0.0,
        n=len(teste),
        acerto_pares=acertos / pares if pares else None,
    )


def prever_log(
    modelos: dict[float, lgb.Booster], x: pd.DataFrame, teste: pd.DataFrame, canais
) -> np.ndarray:
    """Mediana prevista, de volta para log(1 + alvo)."""
    relativo = modelos[0.5].predict(x)
    return relativo + np.log1p(canais.reindex(teste["canal_id"])["mediana"].to_numpy())


def predicao_baseline(teste: pd.DataFrame, canais: pd.DataFrame) -> np.ndarray:
    return canais.reindex(teste["canal_id"])["media_log"].to_numpy()


N_PIORES = 20
FAIXAS_DE_IDADE = [(7, 30, "7-30d"), (30, 90, "30-90d"), (90, float("inf"), "90d+")]


def diagnosticar(
    pred_log: np.ndarray, teste: pd.DataFrame
) -> tuple[list[Erro], dict[str, list[Segmento]]]:
    """Piores previsões e MAE por segmento (canal, setor, idade), do pior para o melhor."""
    df = teste.assign(previsto=pred_log, erro=np.abs(pred_log - teste["log_y"].to_numpy()))
    piores = [
        Erro(
            video_id=r.video_id,
            canal_id=r.canal_id,
            previsto=float(r.previsto),
            real=float(r.log_y),
            erro_log=float(r.erro),
        )
        for r in df.nlargest(N_PIORES, "erro").itertuples()
    ]
    idade = pd.Series("", index=df.index)
    for inicio, fim, rotulo in FAIXAS_DE_IDADE:
        idade[(df["idade_dias"] >= inicio) & (df["idade_dias"] < fim)] = rotulo
    segmentos = {
        nome: [
            Segmento(chave=str(chave), mae=float(g["erro"].mean()), n=len(g))
            for chave, g in sorted(df.groupby(chaves), key=lambda kv: -kv[1]["erro"].mean())
        ]
        for nome, chaves in (("canal", df["canal_id"]), ("setor", df["setor"]), ("idade", idade))
    }
    return piores, segmentos


# ---------------------------------------------------------------- histórico do canal

DEFASAGEM_HISTORICO_DIAS = 7  # só vídeos com 7+ dias: os números deles já estavam visíveis


def historico(videos: pd.DataFrame) -> pd.DataFrame:
    """Momento do canal antes de cada vídeo, sem olhar o futuro.

    videos: video_id, canal_id, publicado_em, y (todos os vídeos do canal, sem teto).
    Médias usam só vídeos publicados DEFASAGEM_HISTORICO_DIAS antes; ritmo de postagem usa
    todos os anteriores (a data de publicação é conhecida na hora)."""
    partes = []
    for _, g in videos.sort_values("publicado_em").groupby("canal_id", sort=False):
        t = g["publicado_em"].to_numpy(dtype="datetime64[s]").astype("int64") / 86400.0
        logy = np.log1p(g["y"].astype(float).to_numpy())
        soma = np.concatenate([[0.0], np.cumsum(logy)])
        quad = np.concatenate([[0.0], np.cumsum(logy**2)])
        elegiveis = np.searchsorted(t, t - DEFASAGEM_HISTORICO_DIAS, side="right")
        m10, q10, n10 = _janela(soma, quad, elegiveis, 10)
        m30, _, _ = _janela(soma, quad, elegiveis, 30)
        anteriores = np.arange(len(t))
        partes.append(
            pd.DataFrame(
                {
                    "video_id": g["video_id"].to_numpy(),
                    "hist_media_10": m10,
                    "hist_media_30": m30,
                    "hist_desvio_10": np.sqrt(np.clip(q10 - m10**2, 0, None)),
                    "hist_tendencia": m10 - m30,
                    "hist_n": n10,
                    "hist_dias_desde_ultimo": np.concatenate([[np.nan], np.diff(t)]),
                    "hist_posts_7d": anteriores - np.searchsorted(t, t - 7, side="left"),
                }
            )
        )
    return pd.concat(partes, ignore_index=True)


def _janela(soma, quad, elegiveis, tamanho):
    """Média e média dos quadrados dos últimos `tamanho` vídeos elegíveis (somas acumuladas)."""
    ini = np.maximum(elegiveis - tamanho, 0)
    n = elegiveis - ini
    with np.errstate(invalid="ignore", divide="ignore"):
        return (soma[elegiveis] - soma[ini]) / n, (quad[elegiveis] - quad[ini]) / n, n


def historico_do_banco(banco: duckdb.DuckDBPyConnection, alvo: str) -> pd.DataFrame:
    df = banco.execute(
        f"SELECT id AS video_id, canal_id, publicado_em, {alvo} AS y FROM videos "
        f"WHERE {alvo} IS NOT NULL"
        " AND id NOT IN (SELECT id FROM excluidos WHERE tipo = 'video')"
        " AND canal_id NOT IN (SELECT id FROM excluidos WHERE tipo = 'canal')"
    ).df()
    df["publicado_em"] = pd.to_datetime(df["publicado_em"], utc=True)
    return historico(df).set_index("video_id")


# ---------------------------------------------------------------- camadas extras


def features_multimodais(
    banco: duckdb.DuckDBPyConnection, video_ids: pd.Series
) -> pd.DataFrame | None:
    linhas = banco.execute("SELECT video_id, embedding FROM camada_bruta").fetchall()
    if not linhas:
        return None
    emb = pd.DataFrame({v: e for v, e in linhas}).T
    return emb.reindex(video_ids.to_numpy())


def reduzir_embeddings(
    treino: pd.DataFrame, teste: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, PCA]:
    pca = PCA(n_components=min(DIMENSOES_SIGLIP, treino.shape[0], treino.shape[1]), random_state=0)
    nomes = [f"siglip_{i}" for i in range(pca.n_components)]
    tr = pd.DataFrame(pca.fit_transform(treino.to_numpy()), index=treino.index, columns=nomes)
    te = pd.DataFrame(pca.transform(teste.to_numpy()), index=teste.index, columns=nomes)
    return tr, te, pca


# ---------------------------------------------------------------- persistência


def salvar_modelos(pasta: Path, modelos: dict[float, lgb.Booster], meta: dict):
    pasta.mkdir(parents=True, exist_ok=True)
    for q, booster in modelos.items():
        booster.save_model(str(pasta / f"q{int(q * 100):02d}.txt"))
    (pasta / "meta.json").write_text(json.dumps(meta, default=str, indent=2))


def carregar_modelos(pasta: Path) -> tuple[dict[float, lgb.Booster], dict] | None:
    if not (pasta / "meta.json").exists():
        return None
    modelos = {q: lgb.Booster(model_file=str(pasta / f"q{int(q * 100):02d}.txt")) for q in QUANTIS}
    return modelos, json.loads((pasta / "meta.json").read_text())


def salvar_avaliacao(banco: duckdb.DuckDBPyConnection, run_id: str, avaliacao: Avaliacao):
    banco.execute(
        "INSERT INTO avaliacoes VALUES (?, ?, ?, ?)",
        [run_id, avaliacao.alvo, avaliacao.criado_em, avaliacao.model_dump_json()],
    )


def ultima_avaliacao(banco: duckdb.DuckDBPyConnection, alvo: str) -> Avaliacao | None:
    linha = banco.execute(
        "SELECT avaliacao FROM avaliacoes WHERE alvo = ? ORDER BY criado_em DESC LIMIT 1", [alvo]
    ).fetchone()
    return Avaliacao.model_validate_json(linha[0]) if linha else None


def agora() -> datetime:
    return datetime.now(UTC)
