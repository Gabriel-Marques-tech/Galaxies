import json

import httpx
import pytest

from galaxies.adaptadores.jev import JevWorkersAI
from galaxies.atributos import PADRAO

PERGUNTAS = {a.id: a.como_pergunta_jev() for a in PADRAO}


def _cliente(conteudo: dict) -> tuple[httpx.Client, list]:
    pedidos = []

    def responder(pedido):
        pedidos.append(json.loads(pedido.content))
        mensagem = {"content": json.dumps(conteudo)}
        return httpx.Response(
            200, json={"success": True, "result": {"choices": [{"message": mensagem}]}}
        )

    return httpx.Client(transport=httpx.MockTransport(responder)), pedidos


def _resposta_valida() -> dict:
    resposta = {}
    for a in PADRAO:
        if a.tipo == "choice":
            resposta[a.id] = next(iter(a.criterios))
        elif a.tipo == "score":
            resposta[a.id] = len(a.criterios) - 1
        else:
            resposta[a.id] = True
    return resposta


def test_schema_restringe_cada_tipo():
    cliente, pedidos = _cliente(_resposta_valida())
    JevWorkersAI("conta", "token", cliente=cliente).perguntar("estado", PERGUNTAS)
    schema = pedidos[0]["response_format"]["json_schema"]
    assert set(schema["required"]) == set(PERGUNTAS)
    assert schema["properties"]["formato"]["enum"][0] == "tutorial"
    assert schema["properties"]["forca_do_gancho"]["enum"] == [0, 1, 2]
    assert schema["properties"]["rosto_no_gancho"]["type"] == "boolean"


def test_respostas_viram_formato_do_jev_e_features():
    cliente, _ = _cliente(_resposta_valida())
    respostas = JevWorkersAI("conta", "token", cliente=cliente).perguntar("estado", PERGUNTAS)
    assert respostas["formato"]["probabilities"]["tutorial"] == 1.0
    assert respostas["formato"]["probabilities"]["review"] == 0.0
    assert respostas["forca_do_gancho"]["score"] == 2.0
    assert respostas["rosto_no_gancho"]["noul"] == 1.0


def test_rotulo_fora_das_opcoes_e_recusado():
    resposta = _resposta_valida() | {"formato": "podcast"}
    cliente, _ = _cliente(resposta)
    with pytest.raises(RuntimeError, match="fora das opções"):
        JevWorkersAI("conta", "token", cliente=cliente).perguntar("estado", PERGUNTAS)
