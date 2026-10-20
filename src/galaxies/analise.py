"""Análise de um Short ainda não publicado: previsão, timeline, P(viral) e fatores (SHAP).

O modelo final usa log_idade_dias como feature; a timeline é a previsão do mesmo vídeo
com a idade fixada em cada dia. Quantis são ordenados e a timeline nunca decresce.
"""

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import norm

from galaxies import modelagem as m

DIAS_DA_TIMELINE = (1, 3, 7, 14, 30)
DIAS_DO_VIRAL = 7
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
    q10: float
    q50: float
    q90: float


class PontoTimeline(Faixa):
    dias: int


class Fator(BaseModel):
    feature: str
    valor: float
    impacto: float  # contribuição SHAP no log relativo ao canal (positivo = ajuda)


class GanchoAnalisado(BaseModel):
    descricao: str
    transcricao: str


class Analise(BaseModel):
    run_id: str
    canal_id: str
    alvo: str
    mediana_canal: float
    previsao_7d: Faixa
    timeline: list[PontoTimeline]
    limite_viral: float
    p_viral: float
    fatores: list[Fator]
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
            "idade_dias": [float(DIAS_DO_VIRAL)],
        }
    )


def prever(modelos, meta: dict, linha: pd.DataFrame, limite_viral: float) -> dict:
    """Timeline em valores absolutos, P(viral) e fatores SHAP aos 7 dias."""
    canais = pd.DataFrame(meta["canais"]).set_index("canal_id")
    mediana = float(canais.loc[linha["canal_id"].iloc[0], "mediana"])
    por_dia = pd.concat([linha.assign(idade_dias=float(d)) for d in DIAS_DA_TIMELINE])
    x = m.features_de_metadados(por_dia.reset_index(drop=True), canais, meta["setores"])
    x = x[meta["colunas"]]
    relativo = np.sort(np.column_stack([modelos[q].predict(x) for q in m.QUANTIS]), axis=1)
    relativo = np.maximum.accumulate(relativo, axis=0)  # mais dias nunca têm menos

    def absoluto(r):
        return max(float(np.expm1(r + np.log1p(mediana))), 0.0)

    timeline = [
        PontoTimeline(dias=d, q10=absoluto(r[0]), q50=absoluto(r[1]), q90=absoluto(r[2]))
        for d, r in zip(DIAS_DA_TIMELINE, relativo, strict=True)
    ]
    i7 = DIAS_DA_TIMELINE.index(DIAS_DO_VIRAL)
    q10, q50, q90 = relativo[i7]
    limite = np.log((limite_viral * mediana + 1) / (mediana + 1))
    sigma = max((q90 - q10) / _Z90, 1e-6)
    p_viral = float(1 - norm.cdf((limite - q50) / sigma))

    x7 = x.iloc[[i7]]
    contrib = modelos[0.5].predict(x7, pred_contrib=True)[0][:-1]  # último = valor base
    ordem = np.argsort(-np.abs(contrib))[:N_FATORES]
    fatores = [
        Fator(feature=x7.columns[i], valor=float(x7.iloc[0, i]), impacto=float(contrib[i]))
        for i in ordem
    ]
    return {
        "mediana_canal": mediana,
        "previsao_7d": Faixa(**timeline[i7].model_dump(exclude={"dias"})),
        "timeline": timeline,
        "limite_viral": limite_viral,
        "p_viral": p_viral,
        "fatores": fatores,
    }
