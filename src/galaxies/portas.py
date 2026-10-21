"""Interfaces das dependências externas. Implementações reais e falsas entram nas tasks que as usam.

As assinaturas são o rascunho da spec (#1) e devem ser ajustadas em cada task (#3, #4, #5).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class YouTube(Protocol):
    """YouTube Data API v3. Custo em unidades de cota anotado em cada método."""

    def canal(self, ref: str) -> dict | None:
        """1 unidade. ref = '@handle' ou 'UC...'. Devolve id, handle, titulo, inscritos,
        playlist_uploads; None se não existir."""
        ...

    def pagina_de_uploads(
        self, playlist_id: str, token: str | None
    ) -> tuple[list[str], str | None]:
        """1 unidade. Até 50 ids de vídeo e o token da próxima página (None no fim)."""
        ...

    def videos(self, ids: list[str]) -> list[dict]:
        """1 unidade, até 50 ids. Cada vídeo: id, canal_id, titulo, descricao, tags,
        publicado_em (ISO), duracao_s, vertical, views, likes, comentarios."""
        ...

    def buscar_canais(self, consulta: str, token: str | None) -> tuple[list[str], str | None]:
        """100 unidades. Ids de canais que casam com a consulta."""
        ...


@dataclass
class Gancho:
    frames: list[Path]
    audio: Path | None  # None quando o vídeo não tem áudio


class ExtratorDeGancho(Protocol):
    def extrair(self, fonte: str, pasta: Path, segundos: int) -> Gancho:
        """fonte = id de vídeo do YouTube ou caminho de arquivo local. Baixa só o trecho
        inicial, salva frames e áudio em `pasta` e descarta o vídeo."""
        ...


class DescritorDeGancho(Protocol):  # Gemini Flash-Lite
    def descrever(self, frames: list[Path]) -> str: ...


class Transcritor(Protocol):  # Whisper
    def transcrever(self, audio: Path) -> str: ...


class Embedder(Protocol):  # SigLIP
    def embutir(self, frames: list[Path]) -> list[float]: ...


class EmbedderDeTexto(Protocol):  # título + descrição, para todos os vídeos
    def embutir_textos(self, textos: list[str]) -> list[list[float]]: ...


class Jev(Protocol):  # #5
    def perguntar(self, contexto: str, perguntas: list[dict]) -> list[dict]: ...


@dataclass
class Dependencias:
    youtube: YouTube | None = None
    extrator: ExtratorDeGancho | None = None
    descritor: DescritorDeGancho | None = None
    transcritor: Transcritor | None = None
    embedder: Embedder | None = None
    jev: Jev | None = None  # lê o gancho: perguntas que exigem entender o vídeo (LLM)
    rapido: Jev | None = None  # decisões rápidas em volume, local (Laya): título de todo vídeo
    texto: EmbedderDeTexto | None = None


def identificar(jev: Jev) -> str:
    """Nome do extrator de atributos, gravado junto de cada resposta."""
    return getattr(jev, "identificador", type(jev).__name__)
