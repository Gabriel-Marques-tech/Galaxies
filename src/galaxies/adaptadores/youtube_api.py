"""Implementação real da porta YouTube, sobre a YouTube Data API v3."""

import re
import time

import httpx

BASE = "https://www.googleapis.com/youtube/v3"
_DURACAO = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def duracao_em_segundos(iso: str) -> int:
    dias, horas, minutos, segundos = (int(g or 0) for g in _DURACAO.fullmatch(iso).groups())
    return ((dias * 24 + horas) * 60 + minutos) * 60 + segundos


class YouTubeAPI:
    def __init__(self, chave: str, cliente: httpx.Client | None = None):
        self._chave = chave
        self._http = cliente or httpx.Client(timeout=60)

    def _get(self, recurso: str, tentativas: int = 4, **params) -> dict:
        """Repete com espera crescente em erros transitórios (rede, 429, 5xx)."""
        for tentativa in range(tentativas):
            ultima = tentativa == tentativas - 1
            try:
                resposta = self._http.get(
                    f"{BASE}/{recurso}", params={**params, "key": self._chave}
                )
            except httpx.TransportError:
                if ultima:
                    raise
            else:
                transitorio = resposta.status_code == 429 or resposta.status_code >= 500
                if not transitorio or ultima:
                    resposta.raise_for_status()
                    return resposta.json()
            time.sleep(2**tentativa)
        raise AssertionError("inalcançável")

    def canal(self, ref):
        filtro = {"forHandle": ref} if ref.startswith("@") else {"id": ref}
        itens = self._get("channels", part="snippet,statistics,contentDetails", **filtro).get(
            "items", []
        )
        if not itens:
            return None
        item = itens[0]
        return {
            "id": item["id"],
            "handle": item["snippet"].get("customUrl"),
            "titulo": item["snippet"]["title"],
            "inscritos": int(item["statistics"].get("subscriberCount", 0)),
            "playlist_uploads": item["contentDetails"]["relatedPlaylists"]["uploads"],
        }

    def pagina_de_uploads(self, playlist_id, token):
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token:
            params["pageToken"] = token
        dados = self._get("playlistItems", **params)
        ids = [i["contentDetails"]["videoId"] for i in dados.get("items", [])]
        return ids, dados.get("nextPageToken")

    def videos(self, ids):
        if not ids:
            return []
        # maxHeight faz a API devolver as dimensões do player: é como sabemos se é vertical.
        dados = self._get(
            "videos",
            part="snippet,contentDetails,statistics,player",
            id=",".join(ids),
            maxHeight=1080,
        )
        return [self._video(item) for item in dados.get("items", [])]

    @staticmethod
    def _video(item: dict) -> dict:
        estatisticas = item.get("statistics", {})
        player = item.get("player", {})

        def numero(campo):
            valor = estatisticas.get(campo)
            return int(valor) if valor is not None else None

        return {
            "id": item["id"],
            "canal_id": item["snippet"]["channelId"],
            "titulo": item["snippet"]["title"],
            "descricao": item["snippet"].get("description", ""),
            "tags": item["snippet"].get("tags", []),
            "publicado_em": item["snippet"]["publishedAt"],
            "duracao_s": duracao_em_segundos(item["contentDetails"]["duration"]),
            "vertical": int(player.get("embedHeight", 0)) > int(player.get("embedWidth", 1)),
            "views": numero("viewCount"),
            "likes": numero("likeCount"),
            "comentarios": numero("commentCount"),
        }

    def buscar_canais(self, consulta, token):
        params = {
            "part": "id",
            "type": "channel",
            "q": consulta,
            "regionCode": "BR",
            "relevanceLanguage": "pt",
            "maxResults": 50,
        }
        if token:
            params["pageToken"] = token
        dados = self._get("search", **params)
        return [i["id"]["channelId"] for i in dados.get("items", [])], dados.get("nextPageToken")
