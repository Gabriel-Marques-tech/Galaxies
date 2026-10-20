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
CREATE TABLE IF NOT EXISTS atributos (
    ordem     INTEGER NOT NULL,
    id        VARCHAR PRIMARY KEY,
    definicao JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS respostas (
    video_id    VARCHAR NOT NULL,
    atributo_id VARCHAR NOT NULL,
    extrator    VARCHAR NOT NULL,  -- quem respondeu: Laya, LLM do Workers AI, Jev...
    assinatura  VARCHAR NOT NULL,
    resposta    JSON NOT NULL,
    quando      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (video_id, atributo_id, extrator)
);
CREATE TABLE IF NOT EXISTS falhas (
    video_id VARCHAR PRIMARY KEY,
    etapa    VARCHAR NOT NULL,
    erro     VARCHAR NOT NULL,
    run_id   VARCHAR NOT NULL,
    quando   TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS avaliacoes (
    run_id    VARCHAR NOT NULL,
    alvo      VARCHAR NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL,
    avaliacao JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS cota (
    run_id   VARCHAR NOT NULL,
    unidades INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS experimentos (
    id        VARCHAR PRIMARY KEY,
    alvo      VARCHAR NOT NULL,
    status    VARCHAR NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL,
    dados     JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS texto_embedding (
    video_id  VARCHAR PRIMARY KEY,
    embedding FLOAT[] NOT NULL
);
CREATE TABLE IF NOT EXISTS revisoes (
    video_id    VARCHAR NOT NULL,
    atributo_id VARCHAR NOT NULL,
    valor       JSON NOT NULL,  -- resposta do humano
    quando      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (video_id, atributo_id)
);
CREATE TABLE IF NOT EXISTS notas (
    video_id VARCHAR PRIMARY KEY,
    tipo     VARCHAR NOT NULL,  -- 'dado_ruim' (sai da base) ou 'padrao' (pista para o agente)
    nota     VARCHAR NOT NULL,
    quando   TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS excluidos (
    id     VARCHAR PRIMARY KEY,  -- id de vídeo ou de canal
    tipo   VARCHAR NOT NULL,     -- 'video' ou 'canal'
    quando TIMESTAMPTZ NOT NULL
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


# Bancos de antes de existir a coluna extrator: todas as respostas vieram deste LLM.
EXTRATOR_ANTIGO = "@cf/meta/llama-3.1-8b-instruct-fast"


def _migrar_respostas(conexao: duckdb.DuckDBPyConnection):
    colunas = {
        c
        for (c,) in conexao.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'respostas'"
        ).fetchall()
    }
    if not colunas or "extrator" in colunas:
        return
    conexao.execute("ALTER TABLE respostas RENAME TO respostas_v1")
    conexao.execute(ESQUEMA)
    conexao.execute(
        "INSERT INTO respostas SELECT video_id, atributo_id, ?, assinatura, resposta, quando "
        "FROM respostas_v1",
        [EXTRATOR_ANTIGO],
    )
    conexao.execute("DROP TABLE respostas_v1")


def caminho_do_banco(raiz: Path, nome: str) -> Path:
    return raiz / "projetos" / nome / "galaxies.duckdb"


def abrir(raiz: Path, nome: str) -> duckdb.DuckDBPyConnection:
    caminho = caminho_do_banco(raiz, nome)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(caminho))
    _migrar_respostas(conexao)
    conexao.execute(ESQUEMA)
    conexao.execute(trace.ESQUEMA)
    return conexao
