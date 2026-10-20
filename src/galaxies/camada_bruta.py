"""Camada bruta: o que é caro de calcular sobre o gancho, feito uma vez por vídeo e guardado."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from pydantic import BaseModel

from galaxies.portas import Dependencias
from galaxies.trace import Execucao

SEGUNDOS_DO_GANCHO = 5


class ResumoGanchos(BaseModel):
    processados: int = 0
    falhas: int = 0
    interrompido_por_cota: bool = False


class Falha(BaseModel):
    video_id: str
    etapa: str
    erro: str
    run_id: str


def registrar_falha(banco: duckdb.DuckDBPyConnection, falha: Falha):
    banco.execute(
        "INSERT OR REPLACE INTO falhas VALUES (?, ?, ?, ?, ?)",
        [falha.video_id, falha.etapa, falha.erro, falha.run_id, datetime.now(UTC)],
    )


def apagar_falhas(banco: duckdb.DuckDBPyConnection, video_ids: list[str]):
    banco.executemany("DELETE FROM falhas WHERE video_id = ?", [[v] for v in video_ids])


def listar_falhas(banco: duckdb.DuckDBPyConnection) -> list[Falha]:
    linhas = banco.execute("SELECT video_id, etapa, erro, run_id FROM falhas").fetchall()
    return [Falha(video_id=v, etapa=e, erro=err, run_id=r) for v, e, err, r in linhas]


def pendentes(
    banco: duckdb.DuckDBPyConnection,
    limite_por_canal: int | None = None,
    canais: list[str] | None = None,
    desde: date | None = None,
) -> list[str]:
    """Vídeos sem camada bruta, sem falha registrada (falhas só voltam via reprocessar) e
    fora da lista de excluídos.

    Com limite_por_canal, a amostra de cada canal é espaçada igualmente no tempo, sobre todos
    os vídeos do canal, para que rodadas repetidas escolham sempre os mesmos. desde limita a
    vídeos publicados a partir da data (ex.: a janela de teste, para a ablação ter tamanho).
    """
    feitos = {
        v
        for (v,) in banco.execute(
            "SELECT video_id FROM camada_bruta UNION SELECT video_id FROM falhas"
            " UNION SELECT id FROM excluidos WHERE tipo = 'video'"
        ).fetchall()
    }
    por_canal: dict[str, list[str]] = {}
    for video_id, canal_id in banco.execute(
        "SELECT id, canal_id FROM videos"
        " WHERE canal_id NOT IN (SELECT id FROM excluidos WHERE tipo = 'canal')"
        "   AND (?::DATE IS NULL OR publicado_em >= ?::DATE)"
        " ORDER BY publicado_em, id",
        [desde, desde],
    ).fetchall():
        por_canal.setdefault(canal_id, []).append(video_id)
    escolhidos = []
    for canal_id, ids in por_canal.items():
        if canais is not None and canal_id not in canais:
            continue
        if limite_por_canal is not None and len(ids) > limite_por_canal:
            ids = _espacados(ids, limite_por_canal)
        escolhidos += [v for v in ids if v not in feitos]
    return escolhidos


def _espacados(itens: list, k: int) -> list:
    if k == 1:
        return [itens[-1]]
    passo = (len(itens) - 1) / (k - 1)
    return [itens[round(i * passo)] for i in range(k)]


class CamadaBruta(BaseModel):
    video_id: str
    frames: list[str]
    descricao: str
    transcricao: str
    embedding: list[float]


def processar(
    banco: duckdb.DuckDBPyConnection,
    deps: Dependencias,
    execucao: Execucao,
    video_id: str,
    fonte: str,
    pasta: Path,
    salvar: bool = True,
) -> CamadaBruta:
    """salvar=False serve à análise de um vídeo novo, que não entra na base."""
    with execucao.etapa("extrair_gancho", {"video_id": video_id}) as registro:
        gancho = deps.extrator.extrair(fonte, pasta, SEGUNDOS_DO_GANCHO)
        registro["saida"] = {"frames": len(gancho.frames), "audio": gancho.audio is not None}
    with execucao.etapa("descrever_gancho", {"video_id": video_id}) as registro:
        descricao = deps.descritor.descrever(gancho.frames)
        registro["saida"] = descricao
    with execucao.etapa("transcrever_gancho", {"video_id": video_id}) as registro:
        transcricao = deps.transcritor.transcrever(gancho.audio) if gancho.audio else ""
        registro["saida"] = transcricao
        if gancho.audio:
            gancho.audio.unlink(missing_ok=True)
    with execucao.etapa("embutir_gancho", {"video_id": video_id}):
        embedding = deps.embedder.embutir(gancho.frames)

    bruta = CamadaBruta(
        video_id=video_id,
        frames=[str(f) for f in gancho.frames],
        descricao=descricao,
        transcricao=transcricao,
        embedding=embedding,
    )
    if salvar:
        banco.execute(
            "INSERT OR REPLACE INTO camada_bruta VALUES (?, ?, ?, ?, ?, ?)",
            [
                video_id,
                json.dumps(bruta.frames),
                descricao,
                transcricao,
                embedding,
                datetime.now(UTC),
            ],
        )
    return bruta


def listar(banco: duckdb.DuckDBPyConnection) -> list[CamadaBruta]:
    linhas = banco.execute(
        "SELECT video_id, frames, descricao, transcricao, embedding FROM camada_bruta"
    ).fetchall()
    return [
        CamadaBruta(video_id=v, frames=json.loads(f), descricao=d, transcricao=t, embedding=e)
        for v, f, d, t, e in linhas
    ]
