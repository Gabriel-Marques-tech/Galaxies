"""Registro de execuções. Cada chamada de serviço vira um run; cada passo dele, uma etapa."""

import json
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
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


class Execucao:
    def __init__(self, banco: duckdb.DuckDBPyConnection, run_id: str):
        self._banco = banco
        self.run_id = run_id
        self._ordem = 0

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


@contextmanager
def executar(banco: duckdb.DuckDBPyConnection, operacao: str):
    run_id = uuid.uuid4().hex
    banco.execute(
        "INSERT INTO runs VALUES (?, ?, ?, 'rodando')", [run_id, operacao, datetime.now(UTC)]
    )
    try:
        yield Execucao(banco, run_id)
    except Exception:
        banco.execute("UPDATE runs SET status = 'falhou' WHERE id = ?", [run_id])
        raise
    banco.execute("UPDATE runs SET status = 'ok' WHERE id = ?", [run_id])


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
