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


class ExtratorFalso:
    def __init__(self, falhar_em: set[str] = frozenset()):
        self.falhar_em = falhar_em
        self.extraidos: list[str] = []

    def extrair(self, fonte, pasta, segundos):
        from galaxies.portas import Gancho

        if fonte in self.falhar_em:
            raise RuntimeError(f"download falhou: {fonte}")
        self.extraidos.append(fonte)
        pasta.mkdir(parents=True, exist_ok=True)
        frames = []
        for i in range(3):
            frame = pasta / f"frame_{i}.jpg"
            frame.write_bytes(b"jpg")
            frames.append(frame)
        audio = pasta / "audio.wav"
        audio.write_bytes(b"wav")
        return Gancho(frames=frames, audio=audio)


class DescritorFalso:
    def __init__(self):
        self.chamadas = 0

    def descrever(self, frames):
        self.chamadas += 1
        return f"mulher mostra batom vermelho em close ({len(frames)} frames)"


class TranscritorFalso:
    def __init__(self):
        self.chamadas = 0

    def transcrever(self, audio):
        self.chamadas += 1
        return "gente, olha esse batom"


class EmbedderFalso:
    def embutir(self, frames):
        return [0.1, 0.2, 0.3]


class JevFalso:
    """Responde de forma determinística: choice na 1ª opção, score no nível do meio, noul 0.8."""

    def __init__(self):
        self.perguntas_feitas: list[str] = []

    def perguntar(self, estado, perguntas):
        respostas = {}
        for nome, q in perguntas.items():
            self.perguntas_feitas.append(nome)
            if q["type"] == "choice":
                rotulos = list(q["criteria"])
                probs = {
                    r: (0.7 if i == 0 else 0.3 / (len(rotulos) - 1)) for i, r in enumerate(rotulos)
                }
                respostas[nome] = {
                    "type": "choice",
                    "choice": rotulos[0],
                    "confidence": 0.7,
                    "probabilities": probs,
                }
            elif q["type"] == "score":
                n = len(q["criteria"])
                respostas[nome] = {
                    "type": "score",
                    "score": (n - 1) / 2,
                    "confidence": 0.6,
                    "probabilities": {str(i): 1 / n for i in range(n)},
                }
            else:
                respostas[nome] = {"type": "noul", "noul": 0.8}
        return respostas
