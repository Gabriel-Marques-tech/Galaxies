"""Descrição do gancho por VLM (Gemini Flash-Lite) via OpenRouter."""

import base64
from pathlib import Path

import httpx

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
