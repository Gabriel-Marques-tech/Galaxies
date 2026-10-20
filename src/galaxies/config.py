import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# O nome vira nome de pasta: só letras minúsculas, dígitos e hífen.
PADRAO_NOME = r"^[a-z0-9][a-z0-9-]{0,62}$"
NomeProjeto = Annotated[str, StringConstraints(pattern=PADRAO_NOME)]


def nome_valido(nome: str) -> bool:
    return re.fullmatch(PADRAO_NOME, nome) is not None


class CanalSemente(BaseModel):
    ref: str = Field(pattern=r"^(@[\w.-]{3,30}|UC[\w-]{22})$")  # '@handle' ou 'UC...'
    setor: str


class ConfigProjeto(BaseModel):
    """O que o agente do usuário informa ao criar um projeto."""

    nome: NomeProjeto
    setores: list[str] = Field(min_length=1)
    canais_semente: list[CanalSemente] = Field(min_length=1)
    alvo: Literal["likes", "views"]
    detalhes: str = ""
    # Só coleta vídeos publicados a partir desta data; também poupa cota ao parar de paginar.
    coletar_desde: date | None = None
    # Viral = alvo em 7 dias acima deste múltiplo da mediana do canal.
    limite_viral: float = Field(default=3.0, gt=1.0)
    # automatico: o agente promove sozinho o melhor modelo que supera o baseline.
    # cientista: o humano aprova cada promoção e participa da criação.
    modo: Literal["automatico", "cientista"] = "automatico"
