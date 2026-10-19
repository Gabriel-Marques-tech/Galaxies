"""Um banco DuckDB por projeto, em <raiz>/projetos/<nome>/galaxies.duckdb."""

from pathlib import Path

import duckdb

from galaxies import trace

ESQUEMA = """
CREATE TABLE IF NOT EXISTS projeto (
    nome   VARCHAR PRIMARY KEY,
    config JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS canais (
    id          VARCHAR PRIMARY KEY,
    handle      VARCHAR,
    titulo      VARCHAR,
    inscritos   BIGINT,
    setor       VARCHAR NOT NULL,
    coletado_em TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS camada_bruta (
    video_id     VARCHAR PRIMARY KEY,
    frames       JSON NOT NULL,
    descricao    VARCHAR NOT NULL,
    transcricao  VARCHAR NOT NULL,
    embedding    FLOAT[] NOT NULL,
    processado_em TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS falhas (
    video_id VARCHAR PRIMARY KEY,
    etapa    VARCHAR NOT NULL,
    erro     VARCHAR NOT NULL,
    run_id   VARCHAR NOT NULL,
    quando   TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cota (
    run_id   VARCHAR NOT NULL,
    unidades INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
    id           VARCHAR PRIMARY KEY,
    canal_id     VARCHAR NOT NULL,
    titulo       VARCHAR,
    descricao    VARCHAR,
    tags         JSON,
    publicado_em TIMESTAMPTZ NOT NULL,
    duracao_s    INTEGER NOT NULL,
    views        BIGINT,
    likes        BIGINT,
    comentarios  BIGINT,
    coletado_em  TIMESTAMPTZ NOT NULL
);
"""


def caminho_do_banco(raiz: Path, nome: str) -> Path:
    return raiz / "projetos" / nome / "galaxies.duckdb"


def abrir(raiz: Path, nome: str) -> duckdb.DuckDBPyConnection:
    caminho = caminho_do_banco(raiz, nome)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(caminho))
    conexao.execute(ESQUEMA)
    conexao.execute(trace.ESQUEMA)
    return conexao
