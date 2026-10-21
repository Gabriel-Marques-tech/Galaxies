"""Registro de execuções. Cada chamada de serviço vira um run; cada passo dele, uma etapa."""

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import BaseModel

ESQUEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id       VARCHAR PRIMARY KEY,
    operacao VARCHAR NOT NULL,
    inicio   TIMESTAMP NOT NULL,
    status   VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS trace (
    run_id     VARCHAR NOT NULL,
    ordem      INTEGER NOT NULL,
    nome       VARCHAR NOT NULL,
    duracao_ms DOUBLE NOT NULL,
    entrada    JSON,
    saida      JSON,
    erro       VARCHAR
);
"""


class Run(BaseModel):
    id: str
    operacao: str
    inicio: datetime
    status: Literal["rodando", "ok", "falhou"]


class Etapa(BaseModel):
    nome: str
    duracao_ms: float
    entrada: Any = None
    saida: Any = None
    erro: str | None = None


ARQUIVO_ANDAMENTO = "andamento.json"  # ao lado do banco: a UI lê sem abrir o DuckDB


def _pasta_do_banco(banco: duckdb.DuckDBPyConnection) -> Path | None:
    """Pasta do projeto, a partir do arquivo do banco (None se for em memória)."""
    try:
        linha = banco.execute(
            "SELECT path FROM duckdb_databases() WHERE internal = false AND path IS NOT NULL"
        ).fetchone()
    except duckdb.Error:
        return None
    return Path(linha[0]).parent if linha else None


def _escrever_andamento(pasta: Path | None, estado: dict | None):
    """Estado do run em andamento, para outro processo (a API) mostrar progresso."""
    if pasta is None:
        return
    caminho = pasta / ARQUIVO_ANDAMENTO
    if estado is None:
        caminho.unlink(missing_ok=True)
        return
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, default=str))
    os.replace(temporario, caminho)


def ler_andamento(pasta: Path) -> dict | None:
    caminho = pasta / ARQUIVO_ANDAMENTO
    if not caminho.exists():
        return None
    try:
        estado = json.loads(caminho.read_text())
    except (OSError, ValueError):
        return None
    inicio = datetime.fromisoformat(estado["inicio"])
    estado["decorrido_s"] = round((datetime.now(UTC) - inicio).total_seconds())
    return estado


class Execucao:
    def __init__(self, banco: duckdb.DuckDBPyConnection, run_id: str, operacao: str = ""):
        self._banco = banco
        self.run_id = run_id
        self._ordem = 0
        self.ultima_falha: tuple[str, str] | None = None  # (etapa, erro)
        self._pasta = _pasta_do_banco(banco)
        self._estado = {
            "run_id": run_id,
            "operacao": operacao,
            "inicio": datetime.now(UTC).isoformat(),
            "etapas": 0,
            "ultima": None,
        }
        _escrever_andamento(self._pasta, self._estado)

    def _anotar(self, nome: str, entrada: Any):
        resumo = json.dumps(entrada, default=str, ensure_ascii=False) if entrada else ""
        self._estado["etapas"] = self._ordem
        self._estado["ultima"] = {"nome": nome, "entrada": resumo[:160]}
        self._estado["atualizado_em"] = datetime.now(UTC).isoformat()
        _escrever_andamento(self._pasta, self._estado)

    def encerrar(self):
        _escrever_andamento(self._pasta, None)

    @contextmanager
    def etapa(self, nome: str, entrada: Any = None):
        """Uso: `with execucao.etapa("x", entrada) as registro: registro["saida"] = ...`"""
        registro: dict[str, Any] = {"saida": None}
        inicio = time.perf_counter()
        erro = None
        try:
            yield registro
        except Exception as e:
            erro = f"{type(e).__name__}: {e}"
            self.ultima_falha = (nome, erro)
            raise
        finally:
            self._banco.execute(
                "INSERT INTO trace VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    self.run_id,
                    self._ordem,
                    nome,
                    (time.perf_counter() - inicio) * 1000,
                    json.dumps(entrada, default=str),
                    json.dumps(registro["saida"], default=str),
                    erro,
                ],
            )
            self._ordem += 1
            self._anotar(nome, entrada)


@contextmanager
def executar(banco: duckdb.DuckDBPyConnection, operacao: str):
    run_id = uuid.uuid4().hex
    banco.execute(
        "INSERT INTO runs VALUES (?, ?, ?, 'rodando')", [run_id, operacao, datetime.now(UTC)]
    )
    execucao = Execucao(banco, run_id, operacao)
    try:
        yield execucao
    except Exception:
        banco.execute("UPDATE runs SET status = 'falhou' WHERE id = ?", [run_id])
        execucao.encerrar()
        raise
    banco.execute("UPDATE runs SET status = 'ok' WHERE id = ?", [run_id])
    execucao.encerrar()


def listar_runs(banco: duckdb.DuckDBPyConnection) -> list[Run]:
    linhas = banco.execute(
        "SELECT id, operacao, inicio, status FROM runs ORDER BY inicio"
    ).fetchall()
    return [Run(id=i, operacao=o, inicio=d, status=s) for i, o, d, s in linhas]


def ler_trace(banco: duckdb.DuckDBPyConnection, run_id: str) -> list[Etapa]:
    linhas = banco.execute(
        "SELECT nome, duracao_ms, entrada, saida, erro FROM trace WHERE run_id = ? ORDER BY ordem",
        [run_id],
    ).fetchall()
    return [
        Etapa(nome=n, duracao_ms=d, entrada=json.loads(e), saida=json.loads(s), erro=err)
        for n, d, e, s, err in linhas
    ]
