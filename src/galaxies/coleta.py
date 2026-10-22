"""Coleta de Shorts pela YouTube Data API: canal → playlist de uploads → vídeos em lotes de 50."""

import json
from datetime import UTC, date, datetime

import duckdb
from pydantic import BaseModel

from galaxies.config import CanalSemente
from galaxies.erros import CanalNaoEncontrado
from galaxies.portas import YouTube

# Desde out/2024 o YouTube aceita Shorts de até 3 minutos.
DURACAO_MAXIMA_SHORT_S = 180


class ResumoColeta(BaseModel):
    videos_novos: int = 0
    falhas: list[str] = []


class Video(BaseModel):
    id: str
    canal_id: str
    titulo: str
    descricao: str
    tags: list[str]
    publicado_em: datetime
    duracao_s: int
    views: int | None
    likes: int | None
    comentarios: int | None


# Custo de cada método da YouTube Data API v3, em unidades da cota diária (10k).
CUSTO_EM_UNIDADES = {"canal": 1, "pagina_de_uploads": 1, "videos": 1, "buscar_canais": 100}


class YouTubeMedido:
    """Envolve a porta do YouTube e soma as unidades de cota gastas."""

    def __init__(self, youtube: YouTube):
        self._youtube = youtube
        self.unidades = 0

    def __getattr__(self, metodo):
        chamada = getattr(self._youtube, metodo)

        def medida(*args, **kwargs):
            self.unidades += CUSTO_EM_UNIDADES[metodo]
            return chamada(*args, **kwargs)

        return medida


def registrar_cota(banco: duckdb.DuckDBPyConnection, run_id: str, unidades: int):
    banco.execute("INSERT INTO cota VALUES (?, ?)", [run_id, unidades])


def cota_total(banco: duckdb.DuckDBPyConnection) -> int:
    return banco.execute("SELECT COALESCE(SUM(unidades), 0) FROM cota").fetchone()[0]


def e_short(video: dict) -> bool:
    return video["duracao_s"] <= DURACAO_MAXIMA_SHORT_S and video["vertical"]


def coletar_canal(
    banco: duckdb.DuckDBPyConnection,
    youtube: YouTube,
    semente: CanalSemente,
    desde: date | None = None,
):
    agora = datetime.now(UTC)
    canal = youtube.canal(semente.ref)
    if canal is None:
        raise CanalNaoEncontrado(semente.ref)
    token = None
    while True:
        ids, token = youtube.pagina_de_uploads(canal["playlist_uploads"], token)
        passou_do_corte = False
        for video in youtube.videos(ids):
            if desde and datetime.fromisoformat(video["publicado_em"]).date() < desde:
                passou_do_corte = True  # a playlist vem do mais novo para o mais antigo
                continue
            if e_short(video):
                _salvar_video(banco, video, agora)
        if token is None or passou_do_corte:
            break
    # Só marca o canal como coletado no fim: uma falha no meio faz ele ser tentado de novo.
    banco.execute(
        "INSERT OR REPLACE INTO canais VALUES (?, ?, ?, ?, ?, ?)",
        [canal["id"], canal["handle"], canal["titulo"], canal["inscritos"], semente.setor, agora],
    )


def _salvar_video(banco, video: dict, agora: datetime):
    banco.execute(
        "INSERT OR REPLACE INTO videos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            video["id"],
            video["canal_id"],
            video["titulo"],
            video["descricao"],
            json.dumps(video["tags"]),
            video["publicado_em"],
            video["duracao_s"],
            video["views"],
            video["likes"],
            video["comentarios"],
            agora,
        ],
    )


def ids_para_miniaturas(banco: duckdb.DuckDBPyConnection, n: int = 12) -> list[str]:
    """Ids de vídeos para o mosaico do card do projeto: primeiro os com gancho analisado,
    depois os mais recentes. A miniatura vem do próprio YouTube (i.ytimg.com), sem cota."""
    return [
        v
        for (v,) in banco.execute(
            """
            SELECT v.id FROM videos v
            LEFT JOIN camada_bruta b ON b.video_id = v.id
            WHERE v.id NOT IN (SELECT id FROM excluidos WHERE tipo = 'video')
            ORDER BY (b.video_id IS NOT NULL) DESC, v.publicado_em DESC
            LIMIT ?
            """,
            [n],
        ).fetchall()
    ]


def listar_videos(banco: duckdb.DuckDBPyConnection) -> list[Video]:
    colunas = list(Video.model_fields)
    linhas = banco.execute(
        f"SELECT {', '.join(colunas)} FROM videos ORDER BY publicado_em"
    ).fetchall()
    return [
        Video(**{**dict(zip(colunas, linha, strict=True)), "tags": json.loads(linha[4])})
        for linha in linhas
    ]


def contar_videos(banco: duckdb.DuckDBPyConnection) -> int:
    return banco.execute("SELECT COUNT(*) FROM videos").fetchone()[0]


def ja_coletados(banco: duckdb.DuckDBPyConnection) -> set[str]:
    """Refs (id ou handle) de canais com coleta completa."""
    linhas = banco.execute("SELECT id FROM canais UNION SELECT handle FROM canais").fetchall()
    return {r for (r,) in linhas}
