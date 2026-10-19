"""Modelos que rodam na CPU local: Whisper (faster-whisper) e SigLIP.

Dependem do extra `multimodal` (uv sync --extra multimodal). Carregam o modelo na primeira uso.
"""

from functools import cached_property
from pathlib import Path


class TranscritorWhisper:
    def __init__(self, tamanho: str = "small"):
        self._tamanho = tamanho

    @cached_property
    def _modelo(self):
        from faster_whisper import WhisperModel

        return WhisperModel(self._tamanho, device="cpu", compute_type="int8")

    def transcrever(self, audio: Path) -> str:
        # O extrator já entrega WAV PCM 16 kHz mono; lemos direto para não depender do
        # decodificador do faster-whisper (incompatível com versões novas do pacote av).
        import wave

        import numpy as np

        with wave.open(str(audio)) as wav:
            amostras = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        sinal = amostras.astype(np.float32) / 32768.0
        segmentos, _ = self._modelo.transcribe(sinal, language="pt", vad_filter=True)
        return " ".join(s.text.strip() for s in segmentos).strip()


class EmbedderSigLIP:
    def __init__(self, modelo: str = "google/siglip-base-patch16-224"):
        self._nome = modelo

    @cached_property
    def _carregado(self):
        from transformers import AutoModel, AutoProcessor

        return AutoModel.from_pretrained(self._nome).eval(), AutoProcessor.from_pretrained(
            self._nome
        )

    def embutir(self, frames: list[Path]) -> list[float]:
        """Média dos embeddings dos frames, normalizada."""
        import torch
        from PIL import Image

        modelo, processador = self._carregado
        imagens = [Image.open(f).convert("RGB") for f in frames]
        with torch.no_grad():
            entradas = processador(images=imagens, return_tensors="pt")
            vetores = modelo.get_image_features(**entradas)
            if not isinstance(vetores, torch.Tensor):  # transformers 5 pode devolver um objeto
                vetores = vetores.pooler_output
            media = torch.nn.functional.normalize(vetores.mean(dim=0), dim=0)
        return media.tolist()
