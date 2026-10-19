"""Jev (TypeSafe AI) via Cloudflare Workers AI."""

import httpx


class JevCloudflare:
    def __init__(self, conta: str, token: str, cliente: httpx.Client | None = None):
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run"
        self._token = token
        self._http = cliente or httpx.Client(timeout=30)

    def perguntar(self, estado: str, perguntas: dict) -> dict:
        resposta = self._http.post(
            self._url,
            headers={"Authorization": f"Bearer {self._token}"},
            json={"model": "typesafe/jev", "input": {"state": estado, "questions": perguntas}},
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        if not corpo.get("success", True):
            raise RuntimeError(f"Jev: {corpo.get('errors')}")
        respostas = corpo.get("result", corpo)["answers"]
        faltando = set(perguntas) - set(respostas)
        if faltando:
            raise RuntimeError(f"Jev não respondeu: {sorted(faltando)}")
        return respostas
