"""Curva de crescimento: como likes e views crescem com a idade do vídeo.

A coleta é uma foto só: cada vídeo tem um único par (idade, contagem), e os vídeos jovens
só existem no fim da base. O modelo usa a idade como feature, mas uma árvore não extrapola
para idades que nunca viu. Reobservar os vídeos recentes dias depois dá dois pontos por
vídeo; a inclinação de log(contagem) por log(idade), por faixa de idade, é a curva. Ela
corrige a timeline abaixo da idade mínima que o modelo viu.
"""

from datetime import UTC, datetime

import duckdb
import numpy as np
from pydantic import BaseModel

FAIXAS_DE_IDADE = (0, 2, 5, 10, 20, 40, 80, 160, 10_000)  # dias; limites das faixas
MIN_POR_FAIXA = 20  # vídeos reobservados para a faixa contar


class FaixaDaCurva(BaseModel):
    de_dias: float
    ate_dias: float
    n: int
    inclinacao: float  # d log(1+y) / d log(idade); 0 = parou de crescer


class Curva(BaseModel):
    alvo: str
    faixas: list[FaixaDaCurva]
    videos: int  # vídeos com duas observações
    intervalo_mediano_dias: float  # entre a primeira e a última observação

    def fator(self, de_dias: float, ate_dias: float) -> float:
        """Quanto a contagem muda, em média, de `de_dias` para `ate_dias` (fator > 1 =
        cresce). Integra a inclinação por faixa em log(idade); faixas sem dados não mudam."""
        de, ate = max(de_dias, 0.05), max(ate_dias, 0.05)
        sinal = 1.0 if ate >= de else -1.0
        lo, hi = min(de, ate), max(de, ate)
        soma = 0.0
        for f in self.faixas:
            a, b = max(lo, f.de_dias), min(hi, f.ate_dias)
            if b > a:
                soma += f.inclinacao * (np.log(max(b, 0.05)) - np.log(max(a, 0.05)))
        return float(np.exp(sinal * soma))


class ResumoObservacao(BaseModel):
    candidatos: int  # vídeos com menos de dias_max de idade
    observados: int
    sem_dados: int  # apagados ou privados
    unidades: int


def semear(banco: duckdb.DuckDBPyConnection) -> int:
    """A própria coleta é a primeira observação de cada vídeo."""
    antes = banco.execute("SELECT count(*) FROM observacoes").fetchone()[0]
    banco.execute(
        """
        INSERT OR IGNORE INTO observacoes
        SELECT id, coletado_em, date_diff('second', publicado_em, coletado_em) / 86400.0,
               likes, views
        FROM videos
        """
    )
    return banco.execute("SELECT count(*) FROM observacoes").fetchone()[0] - antes


def recentes(banco: duckdb.DuckDBPyConnection, dias_max: float, agora: datetime) -> list[str]:
    return [
        v
        for (v,) in banco.execute(
            """
            SELECT id FROM videos
            WHERE date_diff('second', publicado_em, ?::TIMESTAMPTZ) / 86400.0 < ?
              AND id NOT IN (SELECT id FROM excluidos WHERE tipo = 'video')
            ORDER BY publicado_em
            """,
            [agora, dias_max],
        ).fetchall()
    ]


def idade_minima_vista(banco: duckdb.DuckDBPyConnection) -> float:
    """Idade (dias) abaixo da qual o modelo quase não tem exemplos: 5º percentil da idade
    na coleta. A timeline abaixo dela usa a curva."""
    (q,) = banco.execute(
        "SELECT quantile_cont(date_diff('second', publicado_em, coletado_em) / 86400.0, 0.05) "
        "FROM videos"
    ).fetchone()
    return float(q or 0.0)


def curva(banco: duckdb.DuckDBPyConnection, alvo: str) -> Curva:
    """Mediana da inclinação log(1+y) × log(idade) por faixa, entre a primeira e a última
    observação de cada vídeo. Faixa pelo ponto médio geométrico das duas idades."""
    linhas = banco.execute(
        f"""
        WITH ordenadas AS (
            SELECT video_id, idade_dias, {alvo} AS y,
                   row_number() OVER (PARTITION BY video_id ORDER BY quando) AS primeira,
                   row_number() OVER (PARTITION BY video_id ORDER BY quando DESC) AS ultima
            FROM observacoes WHERE {alvo} IS NOT NULL AND idade_dias > 0
        )
        SELECT a.idade_dias, a.y, b.idade_dias, b.y
        FROM ordenadas a JOIN ordenadas b USING (video_id)
        WHERE a.primeira = 1 AND b.ultima = 1 AND b.idade_dias > a.idade_dias
        """
    ).fetchall()
    if not linhas:
        return Curva(alvo=alvo, faixas=[], videos=0, intervalo_mediano_dias=0.0)
    i0, y0, i1, y1 = (np.array(c, dtype=float) for c in zip(*linhas, strict=True))
    inclinacao = (np.log1p(y1) - np.log1p(y0)) / (np.log(i1) - np.log(i0))
    meio = np.sqrt(i0 * i1)
    faixas = []
    for de, ate in zip(FAIXAS_DE_IDADE[:-1], FAIXAS_DE_IDADE[1:], strict=True):
        dentro = (meio >= de) & (meio < ate)
        if dentro.sum() >= MIN_POR_FAIXA:
            faixas.append(
                FaixaDaCurva(
                    de_dias=de,
                    ate_dias=ate,
                    n=int(dentro.sum()),
                    inclinacao=float(max(np.median(inclinacao[dentro]), 0.0)),
                )
            )
    return Curva(
        alvo=alvo,
        faixas=faixas,
        videos=len(linhas),
        intervalo_mediano_dias=float(np.median(i1 - i0)),
    )


def agora_utc() -> datetime:
    return datetime.now(UTC)
