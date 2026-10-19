"""Dependências externas falsas, com dados em memória."""

from itertools import count

_seq = count()


def video(canal_id, *, duracao_s=30, vertical=True, likes=100, views=1000, publicado_em=None):
    n = next(_seq)
    return {
        "id": f"v{n}",
        "canal_id": canal_id,
        "titulo": f"video {n}",
        "descricao": "",
        "tags": [],
        "publicado_em": publicado_em or f"2026-09-{n % 28 + 1:02d}T12:00:00Z",
        "duracao_s": duracao_s,
        "vertical": vertical,
        "views": views,
        "likes": likes,
        "comentarios": 1,
    }


class YouTubeFalso:
    def __init__(self, canais: dict[str, list[dict]], busca: dict[str, list[str]] | None = None):
        """canais: canal_id -> vídeos. Handle de cada canal é '@' + canal_id."""
        self._canais = canais
        self._busca = busca or {}
        self.chamadas: list[str] = []

    def canal(self, ref):
        self.chamadas.append("canal")
        canal_id = ref.removeprefix("@")
        if canal_id not in self._canais:
            return None
        return {
            "id": canal_id,
            "handle": "@" + canal_id,
            "titulo": canal_id.title(),
            "inscritos": 10_000,
            "playlist_uploads": "UU" + canal_id,
        }

    def pagina_de_uploads(self, playlist_id, token):
        self.chamadas.append("pagina_de_uploads")
        ids = [v["id"] for v in self._canais[playlist_id.removeprefix("UU")]]
        inicio = int(token or 0)
        fim = inicio + 50
        return ids[inicio:fim], (str(fim) if fim < len(ids) else None)

    def videos(self, ids):
        self.chamadas.append("videos")
        assert len(ids) <= 50
        todos = {v["id"]: v for vs in self._canais.values() for v in vs}
        return [todos[i] for i in ids]

    def buscar_canais(self, consulta, token):
        self.chamadas.append("buscar_canais")
        return self._busca.get(consulta, []), None
