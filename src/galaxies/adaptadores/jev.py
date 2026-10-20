"""Respostas tipadas no formato do Jev: o Jev real (pago) ou um LLM grátis do Workers AI."""

import json

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


class JevWorkersAI:
    """Substituto grátis do Jev: um LLM do Workers AI (cota diária gratuita) com saída em JSON
    schema. Devolve as respostas no formato do Jev; as probabilidades viram one-hot."""

    def __init__(
        self,
        conta: str,
        token: str,
        modelo: str = "@cf/meta/llama-3.1-8b-instruct-fast",
        cliente: httpx.Client | None = None,
    ):
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{modelo}"
        self._token = token
        self._http = cliente or httpx.Client(timeout=90)

    def perguntar(self, estado: str, perguntas: dict) -> dict:
        resposta = self._http.post(
            self._url,
            headers={"Authorization": f"Bearer {self._token}"},
            json={
                "messages": [
                    {"role": "system", "content": INSTRUCAO},
                    {"role": "user", "content": f"{estado}\n\nPerguntas:\n{_enunciado(perguntas)}"},
                ],
                "response_format": {"type": "json_schema", "json_schema": _schema(perguntas)},
                "max_tokens": 1024,
                "temperature": 0,
            },
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        if not corpo.get("success", True):
            raise RuntimeError(f"Workers AI: {corpo.get('errors')}")
        conteudo = _conteudo(corpo["result"])
        bruto = json.loads(conteudo) if isinstance(conteudo, str) else conteudo
        return {nome: _no_formato_jev(q, bruto.get(nome)) for nome, q in perguntas.items()}


INSTRUCAO = (
    "Você analisa YouTube Shorts a partir do título, da descrição do gancho visual e da fala "
    "inicial. Responda cada pergunta só com base no texto. Devolva apenas o JSON pedido."
)


def _enunciado(perguntas: dict) -> str:
    linhas = []
    for nome, q in perguntas.items():
        c = q.get("criteria")
        if q["type"] == "choice":
            opcoes = "; ".join(f"{r} = {d}" for r, d in c.items())
            linhas.append(f"- {nome}: {q['instructions']} Escolha uma: {opcoes}")
        elif q["type"] == "score":
            niveis = "; ".join(f"{i} = {n}" for i, n in enumerate(c))
            linhas.append(f"- {nome}: {q['instructions']} Nota inteira: {niveis}")
        else:
            linhas.append(f"- {nome}: {q['instructions']} Responda true ou false.")
    return "\n".join(linhas)


def _schema(perguntas: dict) -> dict:
    propriedades = {}
    for nome, q in perguntas.items():
        if q["type"] == "choice":
            propriedades[nome] = {"type": "string", "enum": list(q["criteria"])}
        elif q["type"] == "score":
            propriedades[nome] = {"type": "integer", "enum": list(range(len(q["criteria"])))}
        else:
            propriedades[nome] = {"type": "boolean"}
    return {"type": "object", "properties": propriedades, "required": list(perguntas)}


def _conteudo(resultado: dict):
    if "choices" in resultado:
        return resultado["choices"][0]["message"]["content"]
    return resultado["response"]


def _no_formato_jev(pergunta: dict, valor) -> dict:
    if valor is None:
        raise RuntimeError("modelo não respondeu todas as perguntas")
    tipo = pergunta["type"]
    if tipo == "choice":
        rotulos = list(pergunta["criteria"])
        if valor not in rotulos:
            raise RuntimeError(f"rótulo fora das opções: {valor!r}")
        probs = {r: float(r == valor) for r in rotulos}
        return {"type": "choice", "choice": valor, "confidence": 1.0, "probabilities": probs}
    if tipo == "score":
        maximo = len(pergunta["criteria"]) - 1
        return {"type": "score", "score": float(min(max(int(valor), 0), maximo))}
    return {"type": "noul", "noul": float(bool(valor))}
