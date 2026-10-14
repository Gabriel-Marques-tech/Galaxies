"""Interfaces das dependências externas. Implementações reais e falsas entram nas tasks que as usam.

As assinaturas são o rascunho da spec (#1) e devem ser ajustadas em cada task (#3, #4, #5).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class YouTube(Protocol):  # #3
    def canal(self, canal_id: str) -> dict: ...
    def ids_de_uploads(self, canal_id: str) -> list[str]: ...
    def videos(self, video_ids: list[str]) -> list[dict]: ...


class DescritorDeGancho(Protocol):  # #4, Gemini Flash-Lite
    def descrever(self, frames: list[Path]) -> str: ...


class Transcritor(Protocol):  # #4, Whisper
    def transcrever(self, audio: Path) -> str: ...


class Embedder(Protocol):  # #4, SigLIP
    def embutir(self, frames: list[Path]) -> list[float]: ...


class Jev(Protocol):  # #5
    def perguntar(self, contexto: str, perguntas: list[dict]) -> list[dict]: ...


@dataclass
class Dependencias:
    youtube: YouTube | None = None
    descritor: DescritorDeGancho | None = None
    transcritor: Transcritor | None = None
    embedder: Embedder | None = None
    jev: Jev | None = None
