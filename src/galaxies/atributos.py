"""Atributos: perguntas tipadas do Jev sobre o texto da camada bruta, convertidas em features.

Cada atributo segue o formato de pergunta do Jev (choice, score ou noul). Mudar um atributo
só refaz as perguntas ao Jev; a camada bruta (VLM, Whisper, SigLIP) não é tocada.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

import duckdb
from pydantic import BaseModel, Field, model_validator

MAXIMO_POR_PROJETO = 30


class Atributo(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    tipo: Literal["choice", "score", "noul"]
    instrucoes: str = Field(min_length=10)
    # choice: {rótulo: descrição}, 2–255 opções. score: níveis em ordem crescente, 2–10.
    # noul: opcional, {"true": ..., "false": ...}.
    criterios: dict[str, str] | list[str] | None = None

    @model_validator(mode="after")
    def _criterios_batem_com_o_tipo(self):
        c = self.criterios
        if self.tipo == "choice" and not (isinstance(c, dict) and 2 <= len(c) <= 255):
            raise ValueError("choice precisa de criterios {rótulo: descrição} com 2 a 255 opções")
        if self.tipo == "score" and not (isinstance(c, list) and 2 <= len(c) <= 10):
            raise ValueError("score precisa de criterios [níveis em ordem] com 2 a 10 níveis")
        if (
            self.tipo == "noul"
            and c is not None
            and not (isinstance(c, dict) and set(c) == {"true", "false"})
        ):
            raise ValueError('noul aceita criterios só como {"true": ..., "false": ...}')
        return self

    @property
    def assinatura(self) -> str:
        """Muda quando a pergunta muda: respostas antigas deixam de valer."""
        return hashlib.sha1(self.model_dump_json().encode()).hexdigest()[:12]

    def como_pergunta_jev(self) -> dict:
        pergunta = {"type": self.tipo, "instructions": self.instrucoes}
        if self.criterios is not None:
            pergunta["criteria"] = self.criterios
        return pergunta


def validar_lista(atributos: list[Atributo]):
    if len(atributos) > MAXIMO_POR_PROJETO:
        raise ValueError(f"no máximo {MAXIMO_POR_PROJETO} atributos por projeto")
    ids = [a.id for a in atributos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ValueError(f"ids repetidos: {sorted(repetidos)}")


def salvar_definicoes(banco: duckdb.DuckDBPyConnection, atributos: list[Atributo]):
    banco.execute("DELETE FROM atributos")
    for ordem, atributo in enumerate(atributos):
        banco.execute(
            "INSERT INTO atributos VALUES (?, ?, ?)",
            [ordem, atributo.id, atributo.model_dump_json()],
        )


def ler_definicoes(banco: duckdb.DuckDBPyConnection) -> list[Atributo]:
    linhas = banco.execute("SELECT definicao FROM atributos ORDER BY ordem").fetchall()
    if not linhas:
        return list(PADRAO)
    return [Atributo.model_validate_json(d) for (d,) in linhas]


def estado_do_video(titulo: str, descricao: str, tags: list[str], bruta) -> str:
    """O texto que o Jev lê: metadados planejados + o que a camada bruta viu e ouviu."""
    return (
        f"Título: {titulo}\n"
        f"Descrição: {descricao[:500]}\n"
        f"Tags: {', '.join(tags[:20])}\n"
        f"Gancho visual (primeiros 5s): {bruta.descricao}\n"
        f"Fala nos primeiros 5s: {bruta.transcricao or '(sem fala)'}"
    )


def faltantes(
    banco: duckdb.DuckDBPyConnection, video_id: str, atributos: list[Atributo]
) -> list[Atributo]:
    feitas = {
        (a, s)
        for a, s in banco.execute(
            "SELECT atributo_id, assinatura FROM respostas WHERE video_id = ?", [video_id]
        ).fetchall()
    }
    return [a for a in atributos if (a.id, a.assinatura) not in feitas]


def salvar_respostas(
    banco: duckdb.DuckDBPyConnection, video_id: str, atributos: list[Atributo], respostas: dict
):
    agora = datetime.now(UTC)
    for atributo in atributos:
        banco.execute(
            "INSERT OR REPLACE INTO respostas VALUES (?, ?, ?, ?, ?)",
            [video_id, atributo.id, atributo.assinatura, json.dumps(respostas[atributo.id]), agora],
        )


def features(banco: duckdb.DuckDBPyConnection, atributos: list[Atributo]) -> list[dict]:
    """Uma linha por vídeo com resposta para todos os atributos atuais."""
    por_id = {a.id: a for a in atributos}
    linhas: dict[str, dict] = {}
    for video_id, atributo_id, assinatura, resposta in banco.execute(
        "SELECT video_id, atributo_id, assinatura, resposta FROM respostas"
    ).fetchall():
        atributo = por_id.get(atributo_id)
        if atributo is None or atributo.assinatura != assinatura:
            continue
        linhas.setdefault(video_id, {"video_id": video_id}).update(
            _para_features(atributo, json.loads(resposta))
        )
    completas = len(atributos)
    return [
        linha
        for linha in linhas.values()
        if sum(1 for a in atributos if _tem_feature(linha, a)) == completas
    ]


def _para_features(atributo: Atributo, resposta: dict) -> dict[str, float]:
    if atributo.tipo == "choice":
        probs = resposta["probabilities"]
        return {
            f"{atributo.id}={rotulo}": float(probs.get(rotulo, 0.0))
            for rotulo in atributo.criterios
        }
    if atributo.tipo == "score":
        return {atributo.id: float(resposta["score"]) / (len(atributo.criterios) - 1)}
    return {atributo.id: float(resposta["noul"])}


def _tem_feature(linha: dict, atributo: Atributo) -> bool:
    if atributo.tipo == "choice":
        return f"{atributo.id}={next(iter(atributo.criterios))}" in linha
    return atributo.id in linha


def _a(id, tipo, instrucoes, criterios=None) -> Atributo:
    return Atributo(id=id, tipo=tipo, instrucoes=instrucoes, criterios=criterios)


# Os 15 atributos de partida, combinados no grilling: gancho, conteúdo, texto e produção.
PADRAO: tuple[Atributo, ...] = (
    # Gancho (0–5s)
    _a("rosto_no_gancho", "noul", "Um rosto humano aparece claramente nos primeiros segundos?"),
    _a("fala_para_camera", "noul", "Alguém fala olhando diretamente para a câmera no início?"),
    _a("texto_na_tela", "noul", "Há texto escrito sobreposto ao vídeo nos primeiros segundos?"),
    _a(
        "promessa_falada",
        "noul",
        "A fala inicial faz uma promessa, pergunta ou provocação direta ao espectador?",
    ),
    _a(
        "tipo_de_gancho",
        "choice",
        "Que tipo de gancho o vídeo usa para prender a atenção no início?",
        {
            "pergunta": "Abre com uma pergunta ao espectador",
            "promessa": "Promete um resultado ou revelação",
            "erro_ou_polemica": "Aponta um erro, mito ou opinião polêmica",
            "demonstracao": "Mostra o produto ou a ação imediatamente",
            "humor": "Abre com piada ou situação engraçada",
            "tendencia": "Usa áudio, meme ou formato em alta",
            "sem_gancho": "Não há gancho claro",
        },
    ),
    _a(
        "forca_do_gancho",
        "score",
        "Quão forte é o gancho para fazer alguém parar de rolar o feed?",
        ["fraco", "médio", "forte"],
    ),
    # Conteúdo
    _a(
        "formato",
        "choice",
        "Qual o formato principal do vídeo?",
        {
            "tutorial": "Ensina um passo a passo",
            "review": "Testa ou avalia um produto",
            "antes_e_depois": "Mostra transformação antes e depois",
            "look": "Mostra roupa, look ou provador",
            "haul": "Mostra compras, recebidos ou unboxing",
            "dicas": "Lista dicas, truques ou erros",
            "humor": "Esquete ou situação cômica",
            "rotina": "Rotina, vlog ou dia a dia",
            "outro": "Nenhum dos anteriores",
        },
    ),
    _a("produto_visivel", "noul", "Um produto específico aparece em destaque no início?"),
    _a(
        "enquadramento",
        "choice",
        "Qual o enquadramento predominante no início?",
        {
            "close": "Close no rosto ou no produto",
            "corpo": "Plano médio ou corpo inteiro",
            "espelho": "Selfie ou reflexo no espelho",
            "sem_pessoa": "Sem pessoa (só produto, tela ou cenário)",
        },
    ),
    # Texto
    _a(
        "titulo_curiosidade",
        "noul",
        "O título usa curiosidade, número, lista ou pergunta para atrair o clique?",
    ),
    _a("chamada_para_acao", "noul", "Há chamada para ação (seguir, comentar, link, comprar)?"),
    _a(
        "tom_do_titulo",
        "choice",
        "Qual o tom do título?",
        {
            "informativo": "Descreve o conteúdo de forma direta",
            "exagerado": "Emocional, exagerado ou sensacionalista",
            "humor": "Engraçado ou irônico",
            "neutro": "Genérico ou sem tom marcante",
        },
    ),
    # Produção
    _a(
        "ritmo",
        "score",
        "Qual o ritmo de cortes e movimento no início?",
        ["lento", "moderado", "rápido"],
    ),
    _a(
        "producao",
        "score",
        "Qual o nível de produção do vídeo?",
        ["amadora", "semiprofissional", "profissional"],
    ),
    _a(
        "audio_principal",
        "choice",
        "Qual o áudio principal no início?",
        {
            "fala": "Fala sem música",
            "musica": "Música sem fala",
            "fala_e_musica": "Fala com música de fundo",
            "silencio": "Sem áudio relevante",
        },
    ),
)
