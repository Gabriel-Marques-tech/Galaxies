"""Um banco DuckDB por projeto, em <raiz>/projetos/<nome>/galaxies.duckdb."""

from pathlib import Path

import duckdb

from galaxies import trace

ESQUEMA = """
CREATE TABLE IF NOT EXISTS projeto (
    nome   VARCHAR PRIMARY KEY,
    config JSON NOT NULL
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
