"""Portões humanos (modo cientista): revisão de atributos e triagem de erros.

A revisão mede se o extrator de atributos concorda com quem conhece o setor. A triagem
devolve conhecimento humano ao ciclo: dado ruim sai da base, padrões viram pistas para o
agente criar atributos novos.
"""

import json
from datetime import UTC, datetime
from typing import Literal

import duckdb
from pydantic import BaseModel

from galaxies import atributos as atrib

MIN_CONCORDANCIA = 0.7


class ItemRevisao(BaseModel):
    video_id: str
    atributo_id: str
    extrator: str
    titulo: str
    gancho: str
    fala: str
    resposta_extrator: float | str  # noul/score: valor; choice: rótulo
    outras_respostas: dict[str, float | str] = {}  # o que os outros extratores disseram
    discordancia: bool = False  # extratores discordam: caso difícil, vai primeiro na fila


class Concordancia(BaseModel):
    atributo_id: str
    revisados: int
    concordancia: float
    confiavel: bool


class Nota(BaseModel):
    video_id: str
    tipo: Literal["dado_ruim", "padrao"]
    nota: str
    quando: datetime


# ---------------------------------------------------------------- revisão de atributos


def amostra(
    banco: duckdb.DuckDBPyConnection, atributo: atrib.Atributo, extrator: str | None, n: int
) -> list[ItemRevisao]:
    """Vídeos ainda não revisados neste atributo. Primeiro os em que os extratores discordam
    (o humano desempata os casos difíceis); depois os demais, numa ordem fixa e espalhada."""
    linhas = banco.execute(
        """
        SELECT r.video_id, r.extrator, r.resposta, v.titulo, b.descricao, b.transcricao
        FROM respostas r
        JOIN videos v ON v.id = r.video_id
        JOIN camada_bruta b ON b.video_id = r.video_id
        WHERE r.atributo_id = ? AND r.assinatura = ?
          AND (?::VARCHAR IS NULL OR r.extrator = ?)
          AND r.video_id NOT IN (SELECT video_id FROM revisoes WHERE atributo_id = ?)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY r.video_id ORDER BY r.quando DESC) = 1
        ORDER BY hash(r.video_id)
        """,
        [atributo.id, atributo.assinatura, extrator, extrator, atributo.id],
    ).fetchall()
    outras: dict[str, dict[str, float | str]] = {}
    for video_id, quem, resposta in banco.execute(
        """
        SELECT video_id, extrator, resposta FROM respostas
        WHERE atributo_id = ? AND assinatura = ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY video_id, extrator ORDER BY quando DESC) = 1
        """,
        [atributo.id, atributo.assinatura],
    ).fetchall():
        outras.setdefault(video_id, {})[quem] = _valor_do_extrator(atributo, json.loads(resposta))
    itens = []
    for video_id, quem, resposta, titulo, gancho, fala in linhas:
        valor = _valor_do_extrator(atributo, json.loads(resposta))
        demais = {e: v for e, v in outras.get(video_id, {}).items() if e != quem}
        itens.append(
            ItemRevisao(
                video_id=video_id,
                atributo_id=atributo.id,
                extrator=quem,
                titulo=titulo or "",
                gancho=gancho,
                fala=fala,
                resposta_extrator=valor,
                outras_respostas=demais,
                discordancia=any(_discordam(atributo, valor, v) for v in demais.values()),
            )
        )
    itens.sort(key=lambda i: not i.discordancia)  # estável: mantém a ordem espalhada
    return itens[:n]


def _discordam(atributo: atrib.Atributo, a: float | str, b: float | str) -> bool:
    if atributo.tipo == "noul":
        return (float(a) >= 0.5) != (float(b) >= 0.5)
    if atributo.tipo == "score":
        return round(float(a)) != round(float(b))
    return a != b


def revisar(banco: duckdb.DuckDBPyConnection, atributo: atrib.Atributo, video_id: str, valor):
    banco.execute(
        "INSERT OR REPLACE INTO revisoes VALUES (?, ?, ?, ?)",
        [video_id, atributo.id, json.dumps(_validar(atributo, valor)), datetime.now(UTC)],
    )


def concordancia(
    banco: duckdb.DuckDBPyConnection, definicoes: list[atrib.Atributo], extrator: str | None
) -> list[Concordancia]:
    por_id = {a.id: a for a in definicoes}
    acertos: dict[str, list[bool]] = {}
    for _video_id, atributo_id, humano, resposta in banco.execute(
        """
        SELECT h.video_id, h.atributo_id, h.valor, r.resposta
        FROM revisoes h JOIN respostas r
          ON r.video_id = h.video_id AND r.atributo_id = h.atributo_id
        WHERE ?::VARCHAR IS NULL OR r.extrator = ?
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY h.video_id, h.atributo_id ORDER BY r.quando DESC) = 1
        """,
        [extrator, extrator],
    ).fetchall():
        atributo = por_id.get(atributo_id)
        if atributo is None:
            continue
        maquina = _valor_do_extrator(atributo, json.loads(resposta))
        acertos.setdefault(atributo_id, []).append(_concorda(atributo, maquina, json.loads(humano)))
    return [
        Concordancia(
            atributo_id=a,
            revisados=len(v),
            concordancia=sum(v) / len(v),
            confiavel=sum(v) / len(v) >= MIN_CONCORDANCIA,
        )
        for a, v in acertos.items()
    ]


def _valor_do_extrator(atributo: atrib.Atributo, resposta: dict) -> float | str:
    if atributo.tipo == "noul":
        return float(resposta["noul"])
    if atributo.tipo == "score":
        return float(resposta["score"])
    if resposta.get("choice"):
        return resposta["choice"]
    probs = resposta["probabilities"]
    return max(probs, key=probs.get)


def _validar(atributo: atrib.Atributo, valor):
    if atributo.tipo == "noul":
        if not isinstance(valor, bool):
            raise ValueError(f"{atributo.id}: responda true ou false")
        return valor
    if atributo.tipo == "choice":
        if valor not in atributo.criterios:
            raise ValueError(f"{atributo.id}: escolha uma das opções {list(atributo.criterios)}")
        return valor
    if isinstance(valor, str) and valor in atributo.criterios:
        return atributo.criterios.index(valor)
    if isinstance(valor, int) and 0 <= valor < len(atributo.criterios):
        return valor
    raise ValueError(f"{atributo.id}: use um dos níveis {atributo.criterios} (ou o índice)")


def _concorda(atributo: atrib.Atributo, maquina, humano) -> bool:
    if atributo.tipo == "noul":
        return (maquina >= 0.5) == humano
    if atributo.tipo == "score":
        return round(maquina) == humano
    return maquina == humano


# ---------------------------------------------------------------- triagem de erros


def anotar(banco: duckdb.DuckDBPyConnection, video_id: str, tipo: str, nota: str) -> Nota:
    registro = Nota(video_id=video_id, tipo=tipo, nota=nota, quando=datetime.now(UTC))
    banco.execute(
        "INSERT OR REPLACE INTO notas VALUES (?, ?, ?, ?)",
        [video_id, registro.tipo, nota, registro.quando],
    )
    if tipo == "dado_ruim":
        banco.execute(
            "INSERT OR REPLACE INTO excluidos VALUES (?, 'video', ?)", [video_id, registro.quando]
        )
    return registro


def notas(banco: duckdb.DuckDBPyConnection) -> list[Nota]:
    linhas = banco.execute(
        "SELECT video_id, tipo, nota, quando FROM notas ORDER BY quando"
    ).fetchall()
    return [Nota(video_id=v, tipo=t, nota=n, quando=q) for v, t, n, q in linhas]
