"""Extração do gancho: baixa só os primeiros segundos (yt-dlp) e tira frames e áudio (ffmpeg)."""

import subprocess
from pathlib import Path

import yt_dlp
from yt_dlp.utils import download_range_func

from galaxies.portas import Gancho

FRAMES_POR_GANCHO = 8


class ExtratorYtDlp:
    def extrair(self, fonte: str, pasta: Path, segundos: int) -> Gancho:
        pasta.mkdir(parents=True, exist_ok=True)
        local = Path(fonte)
        video = local if local.is_file() else self._baixar(fonte, pasta, segundos)
        try:
            frames = self._frames(video, pasta, segundos)
            audio = self._audio(video, pasta, segundos)
        finally:
            if video != local:
                video.unlink(missing_ok=True)
        return Gancho(frames=frames, audio=audio)

    @staticmethod
    def _baixar(video_id: str, pasta: Path, segundos: int) -> Path:
        opcoes = {
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
            "download_ranges": download_range_func(None, [(0, segundos)]),
            "force_keyframes_at_cuts": True,
            "outtmpl": str(pasta / "video.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/shorts/{video_id}", download=True)
            return Path(ydl.prepare_filename(info))

    @staticmethod
    def _frames(video: Path, pasta: Path, segundos: int) -> list[Path]:
        fps = FRAMES_POR_GANCHO / segundos
        _ffmpeg(
            "-t", str(segundos), "-i", str(video),
            "-vf", f"fps={fps},scale=384:-2", "-frames:v", str(FRAMES_POR_GANCHO),
            "-q:v", "4", str(pasta / "frame_%02d.jpg"),
        )  # fmt: skip
        frames = sorted(pasta.glob("frame_*.jpg"))
        if not frames:
            raise RuntimeError("ffmpeg não extraiu nenhum frame")
        return frames

    @staticmethod
    def _audio(video: Path, pasta: Path, segundos: int) -> Path | None:
        destino = pasta / "audio.wav"
        try:
            _ffmpeg(
                "-t", str(segundos), "-i", str(video),
                "-vn", "-ac", "1", "-ar", "16000", str(destino),
            )  # fmt: skip
        except RuntimeError:
            return None  # vídeo sem trilha de áudio
        return destino if destino.exists() and destino.stat().st_size > 0 else None


def _ffmpeg(*args: str):
    resultado = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"ffmpeg: {resultado.stderr.strip()[-300:]}")
