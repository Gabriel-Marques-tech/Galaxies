"""Converte o que os serviços devolvem em JSON puro, igual para o MCP e para a API."""

from pydantic import BaseModel


def para_json(valor):
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json")
    if isinstance(valor, list | tuple):
        return [para_json(v) for v in valor]
    if isinstance(valor, dict):
        return {k: para_json(v) for k, v in valor.items()}
    return valor
