"""Descrição do gancho por VLM (Gemini Flash-Lite): direto na API do Google ou via OpenRouter."""

import base64
import threading
import time
from pathlib import Path

import httpx

from galaxies.erros import CotaEsgotada

URL = "https://openrouter.ai/api/v1/chat/completions"

INSTRUCAO = """Estes são frames dos primeiros 5 segundos de um YouTube Short, em ordem.
Descreva em português, de forma objetiva e factual, o que aparece:
- pessoas: quantas, se o rosto aparece, se fala olhando para a câmera, expressão;
- texto escrito na tela (transcreva exatamente);
- produto ou objeto em destaque;
- cenário e enquadramento (close, plano médio, selfie, espelho...);
- movimento e cortes entre frames;
- formato aparente (tutorial, review, antes/depois, humor, trend, provador, unboxing...).
Não opine sobre qualidade nem preveja desempenho. Máximo 120 palavras."""


class DescritorOpenRouter:
    def __init__(self, chave: str, modelo: str, cliente: httpx.Client | None = None):
        self._chave = chave
        self._modelo = modelo
        self._http = cliente or httpx.Client(timeout=60)

    def descrever(self, frames: list[Path]) -> str:
        imagens = [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode()
                },
            }
            for f in frames
        ]
        resposta = self._http.post(
            URL,
            headers={"Authorization": f"Bearer {self._chave}"},
            json={
                "model": self._modelo,
                "temperature": 0,
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": INSTRUCAO}, *imagens]}
                ],
            },
        )
        resposta.raise_for_status()
        texto = resposta.json()["choices"][0]["message"]["content"]
        if not texto or not texto.strip():
            raise RuntimeError("VLM devolveu descrição vazia")
        return texto.strip()


class DescritorGeminiDireto:
    """API do Google AI Studio. O plano gratuito limita requisições por minuto e por dia:
    espaçamos as chamadas e repetimos em 429/5xx."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

    def __init__(
        self,
        chave: str,
        modelo: str = "gemini-3.1-flash-lite",
        por_minuto: int = 14,
        cliente: httpx.Client | None = None,
    ):
        self._chave = chave
        self._url = self.URL.format(modelo=modelo)
        self._intervalo = 60 / por_minuto
        self._proxima = 0.0
        self._trava = threading.Lock()
        self._http = cliente or httpx.Client(timeout=60)

    def _aguardar_vez(self):
        with self._trava:
            agora = time.monotonic()
            espera = self._proxima - agora
            self._proxima = max(agora, self._proxima) + self._intervalo
        if espera > 0:
            time.sleep(espera)

    def descrever(self, frames: list[Path]) -> str:
        partes = [{"text": INSTRUCAO}] + [
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(f.read_bytes()).decode(),
                }
            }
            for f in frames
        ]
        corpo = {"contents": [{"parts": partes}], "generationConfig": {"temperature": 0}}
        for tentativa in range(5):
            self._aguardar_vez()
            resposta = self._http.post(
                self._url, headers={"x-goog-api-key": self._chave}, json=corpo
            )
            if resposta.status_code == 429 or resposta.status_code >= 500:
                time.sleep(min(60, 5 * 2**tentativa))
                continue
            resposta.raise_for_status()
            candidatos = resposta.json().get("candidates") or []
            texto = "".join(
                p.get("text", "") for c in candidatos for p in c.get("content", {}).get("parts", [])
            )
            if not texto.strip():
                raise RuntimeError("Gemini devolveu descrição vazia")
            return texto.strip()
        if resposta.status_code == 429:
            raise CotaEsgotada(f"Gemini: limite do plano gratuito ({resposta.text[:200]})")
        resposta.raise_for_status()
        raise RuntimeError(f"Gemini: {resposta.status_code} após 5 tentativas")
