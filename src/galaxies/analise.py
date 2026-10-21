"""Análise de um Short ainda não publicado: previsão, timeline, P(viral) e fatores (SHAP).

O modelo final usa log_idade_dias como feature; a timeline é a previsão do mesmo vídeo
com a idade fixada em cada dia. Quantis são ordenados e a timeline nunca decresce.
"""

import json
from datetime import UTC, datetime
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import norm

from galaxies import atributos as atrib
from galaxies import modelagem as m

DIAS_DA_TIMELINE = (1, 3, 7, 14, 30)
DIAS_DA_PREVISAO = 7
# A mediana do canal vem de vídeos maduros (semanas ou meses de vida). Comparar com ela a
# previsão de 7 dias subestima a chance de viralizar; o ponto de 30 dias é comparável.
DIAS_DO_VIRAL = 30
FORA_DOS_FATORES = {"log_idade_dias"}  # é o eixo da timeline, não algo que o criador controla
N_FATORES = 8
_Z90 = norm.ppf(0.9) - norm.ppf(0.1)  # largura q10–q90 de uma normal padrão


class VideoNovo(BaseModel):
    """O que o agente informa sobre o vídeo que vai subir."""

    titulo: str
    descricao: str = ""
    tags: list[str] = []
    duracao_s: int = Field(default=30, gt=0, le=180)
    publicar_em: datetime | None = None  # padrão: agora
    fonte: str | None = None  # arquivo local ou link; sem ele, só metadados


class Faixa(BaseModel):
    """q25–q75: faixa provável (metade dos casos); q10–q90: quase certo (80%)."""

    q10: float
    q25: float = 0.0
    q50: float
    q75: float = 0.0
    q90: float


class PontoTimeline(Faixa):
    dias: int


class Fator(BaseModel):
    feature: str
    valor: float
    impacto: float  # contribuição SHAP no log relativo ao canal (positivo = ajuda)


class Sugestao(BaseModel):
    mudanca: str
    previsto_7d: float  # mediana prevista com a mudança
    ganho: float  # variação relativa da mediana em 7 dias
    p_viral: float = 0.0  # chance de viralizar com a mudança
    delta_p_viral: float = 0.0  # pontos de chance de viralizar ganhos


class Chance(BaseModel):
    evento: str
    multiplo: float  # × a mediana do canal, em DIAS_DO_VIRAL dias
    prob: float


class GanchoAnalisado(BaseModel):
    descricao: str
    transcricao: str


class Comparacao(BaseModel):
    a: "Analise"
    b: "Analise"
    vencedor: Literal["a", "b"]
    diferenca: float  # (mediana 7d de b / de a) - 1


class Analise(BaseModel):
    run_id: str
    experimento_id: str
    canal_id: str
    alvo: str
    mediana_canal: float
    previsao_7d: Faixa
    timeline: list[PontoTimeline]
    limite_viral: float
    p_viral: float  # chance de passar limite_viral × a mediana do canal em dias_viral dias
    dias_viral: int = DIAS_DO_VIRAL
    chances: list[Chance] = []
    fatores: list[Fator]
    sugestoes: list[Sugestao] = []
    gancho: GanchoAnalisado | None = None
    atributos: dict | None = None


def linha_do_video(video: VideoNovo, canal: dict, setor: str, inscritos: int) -> pd.DataFrame:
    publicar_em = video.publicar_em or datetime.now(UTC)
    if publicar_em.tzinfo is None:
        publicar_em = publicar_em.replace(tzinfo=UTC)
    return pd.DataFrame(
        {
            "canal_id": [canal["canal_id"]],
            "setor": [setor],
            "inscritos": [inscritos],
            "titulo": [video.titulo],
            "descricao": [video.descricao],
            "tags": [json.dumps(video.tags)],
            "publicado_em": [pd.Timestamp(publicar_em)],
            "duracao_s": [video.duracao_s],
            "idade_dias": [float(DIAS_DA_PREVISAO)],
        }
    )


def features(
    meta: dict,
    linhas: pd.DataFrame,
    embedding=None,
    respostas=None,
    historico: dict | None = None,
    texto=None,
    titulo: dict | None = None,
) -> pd.DataFrame:
    """As mesmas colunas do modelo da receita, para um ou mais cenários do vídeo."""
    canais = pd.DataFrame(meta["canais"]).set_index("canal_id")
    x = m.features_de_metadados(linhas.reset_index(drop=True), canais, meta["setores"])
    if historico is not None:
        for coluna, valor in historico.items():
            x[coluna] = valor
        x["hist_rel_10"] = x["hist_media_10"] - x["log_mediana_canal"]
    for camada, vetor in (("multimodal", embedding), ("texto", texto)):
        pca = meta.get(f"pca_{camada}")
        if pca is None:
            continue
        reduzido = (np.asarray(vetor) - np.asarray(pca["media"])) @ np.asarray(pca["componentes"]).T
        for i, v in enumerate(reduzido):
            x[f"{pca['prefixo']}_{i}"] = v
    if "atributos" in meta:
        for definicao in meta["atributos"]:
            a = atrib.Atributo.model_validate(definicao)
            for coluna, valor in atrib.para_features(a, respostas[a.id]).items():
                x[coluna] = valor
    if meta.get("titulo"):
        for a in atrib.DE_TITULO:
            for coluna, valor in atrib.para_features(a, titulo[a.id]).items():
                x[coluna] = valor
    return x[meta["colunas"]]


MULTIPLOS_DAS_CHANCES = ((1.0, "passar a mediana do canal"), (2.0, "dobrar a mediana do canal"))


def _quantis_relativos(modelos, x: pd.DataFrame) -> np.ndarray:
    return np.sort(np.column_stack([modelos[q].predict(x) for q in m.QUANTIS]), axis=1)


def _prob_acima(q: np.ndarray, calibracao: float, mediana: float, multiplo: float) -> np.ndarray:
    """Chance de passar `multiplo` × a mediana do canal, numa normal no log relativo com
    centro na mediana prevista e largura da faixa calibrada (q10–q90 cobrindo 80%)."""
    q10, q50, q90 = q[:, 0], q[:, 1], q[:, 2]
    sigma = np.maximum(calibracao * (q90 - q10) / _Z90, 1e-6)
    limite = np.log((multiplo * mediana + 1) / (mediana + 1))
    return 1 - norm.cdf((limite - q50) / sigma)


def prever(
    modelos,
    meta: dict,
    linha: pd.DataFrame,
    limite_viral: float,
    embedding=None,
    respostas=None,
    historico: dict | None = None,
    texto=None,
    curva=None,
    idade_minima: float = 0.0,
    titulo: dict | None = None,
) -> dict:
    """Timeline, chances (mediana, dobro, viral), fatores SHAP e sugestões.

    Abaixo de `idade_minima` (dias que o modelo quase não viu) a timeline parte da previsão
    em `idade_minima` e recua pela curva de crescimento observada; sem curva, fica igual."""
    canais = pd.DataFrame(meta["canais"]).set_index("canal_id")
    mediana = float(canais.loc[linha["canal_id"].iloc[0], "mediana"])
    k = float(meta.get("calibracao", 1.0))
    idades = [max(float(d), idade_minima) for d in DIAS_DA_TIMELINE]
    por_dia = pd.concat([linha.assign(idade_dias=i) for i in idades])
    x = features(meta, por_dia, embedding, respostas, historico, texto, titulo)
    # Âncora móvel: o modelo prevê relativo ao momento do canal; converte para relativo à
    # mediana fixa, que é a referência de chances, sugestões e timeline.
    deslocamento = 0.0
    if meta["receita"].get("ancora") == "movel" and historico is not None:
        recente = historico.get("hist_media_10")
        if recente is not None and not np.isnan(recente):
            deslocamento = float(recente - np.log1p(mediana))
    relativo = _quantis_relativos(modelos, x) + deslocamento
    recuo = np.zeros(len(DIAS_DA_TIMELINE))
    if curva is not None:
        pares = zip(idades, DIAS_DA_TIMELINE, strict=True)
        recuo = np.array([np.log(curva.fator(i, float(d))) for i, d in pares])
        relativo = relativo + recuo[:, None]  # mesma faixa, deslocada no log
    relativo = np.maximum.accumulate(relativo, axis=0)  # nunca decresce

    def absoluto(r):
        return max(float(np.expm1(r + np.log1p(mediana))), 0.0)

    timeline = []
    for d, (q10, q50, q90) in zip(DIAS_DA_TIMELINE, relativo, strict=True):
        lo, hi = q50 - k * (q50 - q10), q50 + k * (q90 - q50)  # faixa calibrada
        q25, q75 = m.faixa_50(lo, q50, hi)
        timeline.append(
            PontoTimeline(
                dias=d,
                q10=absoluto(lo),
                q25=absoluto(q25),
                q50=absoluto(q50),
                q75=absoluto(q75),
                q90=absoluto(hi),
            )
        )
    i7 = DIAS_DA_TIMELINE.index(DIAS_DA_PREVISAO)
    i30 = DIAS_DA_TIMELINE.index(DIAS_DO_VIRAL)
    q30 = relativo[[i30]]
    chances = [
        Chance(evento=nome, multiplo=mult, prob=float(_prob_acima(q30, k, mediana, mult)[0]))
        for mult, nome in (*MULTIPLOS_DAS_CHANCES, (limite_viral, "viralizar"))
    ]

    x7 = x.iloc[[i7]]
    contrib = modelos[0.5].predict(x7, pred_contrib=True)[0][:-1]  # último = valor base
    ordem = [i for i in np.argsort(-np.abs(contrib)) if x7.columns[i] not in FORA_DOS_FATORES]
    fatores = [
        Fator(feature=x7.columns[i], valor=float(x7.iloc[0, i]), impacto=float(contrib[i]))
        for i in ordem[:N_FATORES]
    ]
    return {
        "mediana_canal": mediana,
        "previsao_7d": Faixa(**timeline[i7].model_dump(exclude={"dias"})),
        "timeline": timeline,
        "limite_viral": limite_viral,
        "p_viral": chances[-1].prob,
        "chances": chances,
        "fatores": fatores,
        "sugestoes": sugerir(
            modelos,
            x.iloc[[i7]],
            x.iloc[[i30]],
            mediana,
            k,
            limite_viral,
            meta,
            deslocamento + float(recuo[i7]),  # mesma referência da timeline em 7 dias
            deslocamento + float(recuo[i30]),
        ),
    }


# ---------------------------------------------------------------- sugestões (contrafactual)

MIN_GANHO_SUGESTAO = 0.03  # sugere o que move a mediana em 3%+ ou a chance de viral em 1 ponto+
MIN_DELTA_VIRAL = 0.01
N_SUGESTOES = 5


def _alavancas(meta: dict) -> dict[str, list[tuple[str, dict[str, float]]]]:
    """O que o criador controla antes de publicar: nome → [(descrição, colunas novas)]."""
    alavancas = {
        "hora": [(f"publicar às {h}h", {"hora": h}) for h in range(24)],
        "dia_semana": [
            (f"publicar {d}", {"dia_semana": i})
            for i, d in enumerate(["seg", "ter", "qua", "qui", "sex", "sáb", "dom"])
        ],
        "duracao_s": [(f"duração de {d}s", {"duracao_s": d}) for d in (15, 30, 45, 60, 90)],
        "titulo_pergunta": [("título em forma de pergunta", {"titulo_pergunta": 1})],
        "titulo_numero": [("número no título", {"titulo_numero": 1})],
        "hashtags": [(f"{n} hashtags", {"hashtags": n}) for n in (0, 3, 5)],
    }
    for definicao in meta.get("atributos", []):
        a = atrib.Atributo.model_validate(definicao)
        if a.tipo == "noul":
            alavancas[a.id] = [(f"{a.id}: sim", {a.id: 1.0}), (f"{a.id}: não", {a.id: 0.0})]
        elif a.tipo == "score":
            alavancas[a.id] = [
                (f"{a.id}: {nivel}", {a.id: i / (len(a.criterios) - 1)})
                for i, nivel in enumerate(a.criterios)
            ]
        else:
            colunas = [f"{a.id}={r}" for r in a.criterios]
            alavancas[a.id] = [
                (f"{a.id}: {r}", {c: float(c == f"{a.id}={r}") for c in colunas})
                for r in a.criterios
            ]
    return {
        k: v for k, v in alavancas.items() if all(c in meta["colunas"] for _, d in v for c in d)
    }


def sugerir(
    modelos,
    x7,
    x30,
    mediana: float,
    k: float,
    limite_viral: float,
    meta: dict,
    desloc: float = 0.0,
    desloc30: float | None = None,
):
    """Para cada alavanca, a alternativa que mais aumenta a chance de viralizar (e quanto
    move a mediana em 7 dias). Associação aprendida na base, não causa: hipóteses a testar."""
    desloc30 = desloc if desloc30 is None else desloc30
    base_log = desloc + np.log1p(mediana)
    atual_7d = float(np.expm1(modelos[0.5].predict(x7)[0] + base_log))
    atual_viral = float(
        _prob_acima(_quantis_relativos(modelos, x30) + desloc30, k, mediana, limite_viral)[0]
    )
    sugestoes = []
    for opcoes in _alavancas(meta).values():
        c7 = pd.concat([x7.assign(**mudanca) for _, mudanca in opcoes])
        c30 = pd.concat([x30.assign(**mudanca) for _, mudanca in opcoes])
        previstos = np.expm1(modelos[0.5].predict(c7) + base_log).clip(min=0)
        virais = _prob_acima(_quantis_relativos(modelos, c30) + desloc30, k, mediana, limite_viral)
        i = int(np.argmax(virais + 1e-3 * previstos / max(atual_7d, 1.0)))  # desempate: mediana
        if all(float(x7.iloc[0][c]) == v for c, v in opcoes[i][1].items()):
            continue  # o vídeo já está na melhor opção
        ganho = (previstos[i] - atual_7d) / max(atual_7d, 1.0)
        delta = float(virais[i] - atual_viral)
        if delta >= MIN_DELTA_VIRAL or ganho >= MIN_GANHO_SUGESTAO:
            sugestoes.append(
                Sugestao(
                    mudanca=opcoes[i][0],
                    previsto_7d=float(previstos[i]),
                    ganho=float(ganho),
                    p_viral=float(virais[i]),
                    delta_p_viral=delta,
                )
            )
    return sorted(sugestoes, key=lambda s: (-s.delta_p_viral, -s.ganho))[:N_SUGESTOES]


Comparacao.model_rebuild()
