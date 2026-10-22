"""Extrator `vizinhos`: responde os atributos de um gancho pelos vizinhos mais parecidos.

O LLM (fonte) só leu ~500 ganchos porque depende do Gemini (cota) e do Whisper (lento). O
embedding SigLIP, porém, sai para qualquer vídeo em segundos. Medido na base: um kNN sobre
esses embeddings (cosseno, k=7, voto da maioria) concorda 71% com o LLM e, quando ≥ 80% dos
vizinhos concordam, 85–95% nos atributos visuais. Então os ganchos rotulados pelo LLM viram
sementes, e todo vídeo que só tem embedding recebe o rótulo dos vizinhos, com a fração de
acordo entre eles como confiança. A cascata recomendada: vizinhos decide quando a confiança é
≥ LIMIAR_CONFIANCA; nos demais, pergunta ao LLM.
"""

import json
from dataclasses import dataclass
from statistics import median_low

import duckdb
import numpy as np
from pydantic import BaseModel

from galaxies import atributos as atrib
from galaxies.erros import ErroGalaxies

EXTRATOR = "vizinhos"
K_PADRAO = 7
LIMIAR_CONFIANCA = 0.8  # acima disso o kNN acerta 85–95% nos atributos visuais
LOTE = 512  # vídeos por consulta ao rotular: embeddings de 46k vídeos não cabem de uma vez
# Extratores que nunca servem de fonte: o próprio kNN e o Laya (responde "sim" a quase tudo).
NAO_FONTE = frozenset({EXTRATOR, "laya"})


class ResumoVizinhos(BaseModel):
    rotulados: int
    sementes: int
    k: int
    fonte: str


class AvaliacaoAtributo(BaseModel):
    atributo: str
    tipo: str
    concordancia: float  # kNN × fonte, leave-one-out sobre as sementes
    concordancia_confiante: float | None  # idem, só onde confidence ≥ LIMIAR_CONFIANCA
    fracao_confiante: float  # quantas sementes caem nesse caso
    majoritario: float  # baseline: responder sempre o rótulo mais comum
    n: int


class AvaliacaoVizinhos(BaseModel):
    fonte: str
    k: int
    sementes: int
    limiar_confianca: float = LIMIAR_CONFIANCA
    concordancia_media: float
    atributos: list[AvaliacaoAtributo]


@dataclass
class Fonte:
    """Sementes: embeddings normalizados (linhas) e, por atributo, o rótulo de cada uma."""

    extrator: str
    video_ids: list[str]
    embeddings: np.ndarray  # (n, d), norma 1: produto escalar = cosseno
    rotulos: dict[str, list]  # atributo.id → rótulo por semente (str, bool ou int, pelo tipo)


def detectar_fonte(banco: duckdb.DuckDBPyConnection, explicito: str | None = None) -> str:
    """O LLM do Workers AI (@cf/...) quando houver; senão qualquer extrator que não seja o
    próprio kNN nem o Laya (nos testes, o Jev falso)."""
    if explicito:
        return explicito
    extratores = [
        e
        for (e,) in banco.execute(
            "SELECT extrator FROM respostas GROUP BY 1 ORDER BY count(*) DESC, 1"
        ).fetchall()
    ]
    cf = [e for e in extratores if e.startswith("@cf/")]
    outros = [e for e in extratores if e not in NAO_FONTE]
    if cf or outros:
        return (cf or outros)[0]
    raise ErroGalaxies(
        "Nenhum extrator fonte com respostas de gancho: rode calcular_atributos (LLM) em alguns "
        "vídeos antes de rotular pelos vizinhos."
    )


def rotulos_fonte(
    banco: duckdb.DuckDBPyConnection,
    definicoes: list[atrib.Atributo],
    extrator_fonte: str | None = None,
) -> Fonte:
    """Vídeos com embedding e resposta atual (assinatura) da fonte para todos os atributos."""
    extrator = detectar_fonte(banco, extrator_fonte)
    por_id = {a.id: a for a in definicoes}
    assinaturas = {a.id: a.assinatura for a in definicoes}
    respostas: dict[str, dict[str, dict]] = {}
    for video_id, atributo_id, assinatura, resposta in banco.execute(
        "SELECT r.video_id, r.atributo_id, r.assinatura, r.resposta FROM respostas r"
        " JOIN camada_bruta b ON b.video_id = r.video_id WHERE r.extrator = ?",
        [extrator],
    ).fetchall():
        if assinaturas.get(atributo_id) == assinatura:
            respostas.setdefault(video_id, {})[atributo_id] = json.loads(resposta)
    completos = sorted(v for v, r in respostas.items() if len(r) == len(definicoes))
    embeddings = _embeddings(banco, completos)
    rotulos = {a.id: [_rotulo(a, respostas[v][a.id]) for v in completos] for a in por_id.values()}
    return Fonte(extrator=extrator, video_ids=completos, embeddings=embeddings, rotulos=rotulos)


def responder(
    embedding: list[float], fonte: Fonte, definicoes: list[atrib.Atributo], k: int = K_PADRAO
) -> dict:
    """Respostas no formato do Jev para um embedding, pelo voto dos k vizinhos mais próximos."""
    if not fonte.video_ids:
        raise ErroGalaxies(
            f"O extrator '{fonte.extrator}' não rotulou nenhum vídeo com embedding: não há "
            "sementes para o kNN. Rode calcular_atributos antes."
        )
    indices = _vizinhos(fonte, _normalizar(np.asarray(embedding, dtype=np.float32)), k)
    return _responder_indices(indices, fonte, definicoes)


def rotular(
    banco: duckdb.DuckDBPyConnection,
    definicoes: list[atrib.Atributo],
    k: int = K_PADRAO,
    extrator_fonte: str | None = None,
) -> ResumoVizinhos:
    """Grava respostas `vizinhos` para todo vídeo com embedding que a fonte não respondeu.
    Refaz os já rotulados: as sementes crescem a cada calcular_atributos e o voto muda."""
    fonte = rotulos_fonte(banco, definicoes, extrator_fonte)
    sementes = set(fonte.video_ids)
    alvo = [
        v
        for (v,) in banco.execute("SELECT video_id FROM camada_bruta ORDER BY video_id").fetchall()
        if v not in sementes
    ]
    if alvo and not fonte.video_ids:
        raise ErroGalaxies(
            f"O extrator '{fonte.extrator}' não rotulou nenhum vídeo com embedding: não há "
            "sementes para o kNN. Rode calcular_atributos antes."
        )
    rotulados = 0
    for inicio in range(0, len(alvo), LOTE):
        lote = alvo[inicio : inicio + LOTE]
        linhas = banco.execute(
            "SELECT video_id, embedding FROM camada_bruta"
            " WHERE video_id IN (SELECT unnest(?::VARCHAR[]))",
            [lote],
        ).fetchall()
        por_video = {}
        for video_id, embedding in linhas:
            e = _normalizar(np.asarray(embedding, dtype=np.float32))
            por_video[video_id] = _responder_indices(_vizinhos(fonte, e, k), fonte, definicoes)
        atrib.salvar_respostas_de_varios(banco, definicoes, por_video, EXTRATOR)
        rotulados += len(por_video)
    return ResumoVizinhos(
        rotulados=rotulados, sementes=len(fonte.video_ids), k=k, fonte=fonte.extrator
    )


def avaliar(
    banco: duckdb.DuckDBPyConnection,
    definicoes: list[atrib.Atributo],
    k: int = K_PADRAO,
    extrator_fonte: str | None = None,
) -> AvaliacaoVizinhos:
    """Leave-one-out sobre as sementes: cada uma é respondida pelas outras e comparada com o
    que a fonte disse. Diz em quais atributos o kNN substitui o LLM e em que fração dos casos."""
    fonte = rotulos_fonte(banco, definicoes, extrator_fonte)
    n = len(fonte.video_ids)
    if n < 2:
        raise ErroGalaxies(
            f"Só {n} semente(s) do extrator '{fonte.extrator}': o leave-one-out precisa de ao "
            "menos 2 vídeos com embedding e atributos respondidos."
        )
    previstos = [
        _responder_indices(_vizinhos(fonte, fonte.embeddings[i], k, excluir=i), fonte, definicoes)
        for i in range(n)
    ]
    avaliacoes = []
    for a in definicoes:
        reais = fonte.rotulos[a.id]
        acertos = np.array(
            [_rotulo(a, p[a.id]) == r for p, r in zip(previstos, reais, strict=True)]
        )
        confiantes = np.array([p[a.id]["confidence"] >= LIMIAR_CONFIANCA for p in previstos])
        contagem = {}
        for r in reais:
            contagem[r] = contagem.get(r, 0) + 1
        avaliacoes.append(
            AvaliacaoAtributo(
                atributo=a.id,
                tipo=a.tipo,
                concordancia=float(acertos.mean()),
                concordancia_confiante=(
                    float(acertos[confiantes].mean()) if confiantes.any() else None
                ),
                fracao_confiante=float(confiantes.mean()),
                majoritario=max(contagem.values()) / n,
                n=n,
            )
        )
    return AvaliacaoVizinhos(
        fonte=fonte.extrator,
        k=k,
        sementes=n,
        concordancia_media=float(np.mean([x.concordancia for x in avaliacoes])),
        atributos=avaliacoes,
    )


def _embeddings(banco, video_ids: list[str]) -> np.ndarray:
    if not video_ids:
        return np.zeros((0, 1), dtype=np.float32)
    por_video = dict(
        banco.execute(
            "SELECT video_id, embedding FROM camada_bruta"
            " WHERE video_id IN (SELECT unnest(?::VARCHAR[]))",
            [video_ids],
        ).fetchall()
    )
    matriz = np.asarray([por_video[v] for v in video_ids], dtype=np.float32)
    return _normalizar(matriz)


def _normalizar(x: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(norma == 0, 1.0, norma)  # vetor nulo fica nulo em vez de NaN


def _vizinhos(fonte: Fonte, e: np.ndarray, k: int, excluir: int | None = None) -> np.ndarray:
    similaridades = fonte.embeddings @ e
    if excluir is not None:
        similaridades[excluir] = -np.inf
    disponiveis = len(similaridades) - (excluir is not None)
    # Ordenação estável: em empate (embeddings iguais), a escolha é determinística.
    return np.argsort(-similaridades, kind="stable")[: max(1, min(k, disponiveis))]


def _responder_indices(indices: np.ndarray, fonte: Fonte, definicoes) -> dict:
    respostas = {}
    for a in definicoes:
        votos = [fonte.rotulos[a.id][i] for i in indices]
        n = len(votos)
        if a.tipo == "choice":
            # Fração dos vizinhos por rótulo: é o que para_features lê (uma coluna por rótulo).
            probabilidades = {r: votos.count(r) / n for r in a.criterios}
            escolha = max(a.criterios, key=lambda r: probabilidades[r])  # empate: 1º da lista
            respostas[a.id] = {
                "type": "choice",
                "choice": escolha,
                "probabilities": probabilidades,
                "confidence": probabilidades[escolha],
            }
        elif a.tipo == "noul":
            p = sum(votos) / n
            respostas[a.id] = {"type": "noul", "noul": p, "confidence": max(p, 1 - p)}
        else:
            # Mediana baixa: cai sempre num nível observado, então a confiança (fração dos
            # vizinhos nesse nível) nunca é zero por causa de um meio-termo.
            mediana = median_low(votos)
            respostas[a.id] = {
                "type": "score",
                "score": mediana,
                "confidence": votos.count(mediana) / n,
            }
    return respostas


def _rotulo(a: atrib.Atributo, resposta: dict):
    """Rótulo discreto de uma resposta no formato do Jev, para votar e comparar."""
    if a.tipo == "choice":
        return resposta.get("choice") or max(
            resposta["probabilities"], key=resposta["probabilities"].get
        )
    if a.tipo == "noul":
        return float(resposta["noul"]) >= 0.5
    return min(int(round(float(resposta["score"]))), len(a.criterios) - 1)
