import asyncio
import json

from mcp.server.mcpserver.exceptions import ToolError

from galaxies import Framework
from galaxies.mcp_servidor import criar_servidor
from galaxies.portas import Dependencias
from tests.fakes import YouTubeFalso, base_com_sinal

BASE = base_com_sinal(canais=3, por_canal=80)
CONFIG = {
    "nome": "moda-beleza",
    "setores": ["moda"],
    "canais_semente": [{"ref": f"@{c}", "setor": "moda"} for c in BASE],
    "alvo": "likes",
}


def servidor(tmp_path):
    framework = Framework(raiz=tmp_path, dependencias=Dependencias(youtube=YouTubeFalso(BASE)))
    return criar_servidor(framework)


def chamar(mcp, nome, **argumentos):
    try:
        resultado = asyncio.run(mcp.servidor.call_tool(nome, argumentos))
    except ToolError as erro:  # no protocolo vira um resultado com isError
        return {"erro": str(erro)}
    return json.loads(resultado.content[0].text)


def test_expoe_as_tools_do_framework(tmp_path):
    mcp = servidor(tmp_path)

    nomes = {t.name for t in asyncio.run(mcp.servidor.list_tools())}

    assert {
        "criar_projeto",
        "definir_atributos",
        "coletar",
        "adicionar_canal",
        "treinar",
        "status",
        "avaliar",
        "trace",
        "erros",
        "reprocessar",
        "analisar",
    } <= nomes


def test_loop_criar_coletar_treinar_avaliar_analisar(tmp_path):
    mcp = servidor(tmp_path)

    assert chamar(mcp, "criar_projeto", config=CONFIG)["nome"] == "moda-beleza"
    job = chamar(mcp, "coletar", projeto="moda-beleza")["job_id"]
    mcp.jobs.esperar(job)
    job = chamar(mcp, "treinar", projeto="moda-beleza")["job_id"]
    mcp.jobs.esperar(job)

    status = chamar(mcp, "status", job_id=job)
    assert status["status"] == "ok"
    avaliacao = chamar(mcp, "avaliar", projeto="moda-beleza")
    assert avaliacao["camadas"]["metadados"]["mae"] < avaliacao["baseline"]["mae"]
    analise = chamar(
        mcp,
        "analisar",
        projeto="moda-beleza",
        video={"titulo": "Você sabia disso?"},
        canal_id="canal1",
    )
    assert len(analise["timeline"]) == 5
    etapas = chamar(mcp, "trace", projeto="moda-beleza", run_id=analise["run_id"])
    assert [e["nome"] for e in etapas] == ["prever", "explicar"]


def test_erro_de_dominio_volta_como_mensagem_para_o_agente(tmp_path):
    mcp = servidor(tmp_path)

    resposta = chamar(mcp, "avaliar", projeto="nao-existe")

    assert "criar_projeto" in resposta["erro"]


def test_job_que_falha_guarda_o_erro(tmp_path):
    mcp = servidor(tmp_path)
    chamar(mcp, "criar_projeto", config=CONFIG)

    job = chamar(mcp, "treinar", projeto="moda-beleza", alvo="comentarios")["job_id"]
    mcp.jobs.esperar(job)

    status = chamar(mcp, "status", job_id=job)
    assert status["status"] == "falhou"
    assert "likes ou views" in status["erro"]
