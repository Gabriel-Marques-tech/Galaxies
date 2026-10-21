"""Acompanhamento pós-publicação: liga uma análise ao vídeo publicado e compara previsto × real.

A análise prevê uma timeline (1/3/7/14/30 dias). Depois que o criador publica, guardamos o
id do vídeo e vamos buscando os números reais; cada observação é comparada com a previsão
interpolada para a idade do vídeo naquele momento. É a prova do modelo em produção.
"""

import json
from datetime import UTC, datetime

import duckdb
import numpy as np
from pydantic import BaseModel

ESQUEMA = """
CREATE TABLE IF NOT EXISTS acompanhamentos (
    video_id     VARCHAR PRIMARY KEY,
    run_id       VARCHAR NOT NULL,
    canal_id     VARCHAR NOT NULL,
    alvo         VARCHAR NOT NULL,
    publicado_em TIMESTAMPTZ NOT NULL,
    timeline     JSON NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS observacoes (
    video_id   VARCHAR NOT NULL,
    quando     TIMESTAMPTZ NOT NULL,
    idade_dias DOUBLE NOT NULL,
    likes      BIGINT,
    views      BIGINT,
    PRIMARY KEY (video_id, quando)
);
"""


class Ponto(BaseModel):
    dias: int
    q10: float
    q50: float
    q90: float


class Observacao(BaseModel):
    quando: datetime
    idade_dias: float
    likes: int | None
    views: int | None


class Comparacao(BaseModel):
    """Última observação contra a previsão interpolada para a mesma idade."""

    idade_dias: float
    real: int
    previsto_q10: float
    previsto_q50: float
    previsto_q90: float
    dentro_da_faixa: bool
    erro_log: float  # |log(1+real) - log(1+previsto)|; e^erro = fator de erro


class Acompanhamento(BaseModel):
    video_id: str
    run_id: str
    canal_id: str
    alvo: str
    publicado_em: datetime
    timeline: list[Ponto]
    observacoes: list[Observacao] = []
    ultima: Comparacao | None = None


class ResumoAtualizacao(BaseModel):
    atualizados: int
    sem_dados: list[str] = []  # vídeos que a API não devolveu (apagados, privados)


class ListaAcompanhamentos(BaseModel):
    videos: list[Acompanhamento]
    n: int  # com pelo menos uma comparação
    cobertura: float  # fração das últimas observações dentro da faixa de 80%
    erro_mediano: float  # fator típico (e^mediana do erro_log)


def registrar(
    banco: duckdb.DuckDBPyConnection,
    video_id: str,
    run_id: str,
    canal_id: str,
    alvo: str,
    publicado_em: datetime,
    timeline: list[dict],
):
    banco.execute(
        "INSERT OR REPLACE INTO acompanhamentos VALUES (?, ?, ?, ?, ?, ?, ?)",
        [video_id, run_id, canal_id, alvo, publicado_em, json.dumps(timeline), datetime.now(UTC)],
    )


def observar(banco: duckdb.DuckDBPyConnection, video: dict, agora: datetime | None = None):
    agora = agora or datetime.now(UTC)
    publicado = video["publicado_em"]
    if isinstance(publicado, str):
        publicado = datetime.fromisoformat(publicado.replace("Z", "+00:00"))
    idade = (agora - publicado).total_seconds() / 86400
    banco.execute(
        "INSERT OR REPLACE INTO observacoes VALUES (?, ?, ?, ?, ?)",
        [video["id"], agora, idade, video.get("likes"), video.get("views")],
    )


def ids(banco: duckdb.DuckDBPyConnection) -> list[str]:
    return [v for (v,) in banco.execute("SELECT video_id FROM acompanhamentos").fetchall()]


def listar(banco: duckdb.DuckDBPyConnection) -> ListaAcompanhamentos:
    linhas = banco.execute(
        "SELECT video_id, run_id, canal_id, alvo, publicado_em, timeline FROM acompanhamentos "
        "ORDER BY criado_em DESC"
    ).fetchall()
    obs = banco.execute(
        "SELECT video_id, quando, idade_dias, likes, views FROM observacoes ORDER BY quando"
    ).fetchall()
    por_video: dict[str, list[Observacao]] = {}
    for v, quando, idade, likes, views in obs:
        por_video.setdefault(v, []).append(
            Observacao(quando=quando, idade_dias=idade, likes=likes, views=views)
        )
    videos = []
    for video_id, run_id, canal_id, alvo, publicado_em, timeline in linhas:
        a = Acompanhamento(
            video_id=video_id,
            run_id=run_id,
            canal_id=canal_id,
            alvo=alvo,
            publicado_em=publicado_em,
            timeline=[Ponto(**p) for p in json.loads(timeline)],
            observacoes=por_video.get(video_id, []),
        )
        if a.observacoes:
            a.ultima = comparar(a, a.observacoes[-1])
        videos.append(a)
    comparados = [v.ultima for v in videos if v.ultima is not None]
    return ListaAcompanhamentos(
        videos=videos,
        n=len(comparados),
        cobertura=float(np.mean([c.dentro_da_faixa for c in comparados])) if comparados else 0.0,
        erro_mediano=float(np.exp(np.median([c.erro_log for c in comparados])))
        if comparados
        else 1.0,
    )


def comparar(a: Acompanhamento, obs: Observacao) -> Comparacao | None:
    real = obs.likes if a.alvo == "likes" else obs.views
    if real is None:
        return None
    q10, q50, q90 = (_interpolar(a.timeline, obs.idade_dias, q) for q in ("q10", "q50", "q90"))
    return Comparacao(
        idade_dias=obs.idade_dias,
        real=real,
        previsto_q10=q10,
        previsto_q50=q50,
        previsto_q90=q90,
        dentro_da_faixa=q10 <= real <= q90,
        erro_log=abs(float(np.log1p(real) - np.log1p(q50))),
    )


def _interpolar(timeline: list[Ponto], idade: float, campo: str) -> float:
    """Interpola em log entre os dias da timeline; fora dela, usa a ponta mais próxima."""
    dias = np.array([p.dias for p in timeline], dtype=float)
    valores = np.log1p(np.array([getattr(p, campo) for p in timeline], dtype=float))
    return float(np.expm1(np.interp(idade, dias, valores)))
