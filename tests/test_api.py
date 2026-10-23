import json

from fastapi.testclient import TestClient

from galaxies.api import criar_app
from galaxies.mcp_servidor import criar_servidor
from tests.test_experimentos import VIDEO, projeto
from tests.test_mcp import chamar


def test_rotas_chegam_nos_servicos_e_igualam_o_mcp(tmp_path):
    framework = projeto(tmp_path)
    api = TestClient(criar_app(framework))
    mcp = criar_servidor(framework)

    assert api.get("/projetos").json() == ["moda-beleza"]
    exp = api.post(
        "/projetos/moda-beleza/experimentos", json={"receita": {"camadas": ["metadados"]}}
    ).json()
    # o MCP embrulha listas em {"itens", "n"} (o Gemini CLI valida listas cruas como registro)
    assert api.get("/projetos/moda-beleza/experimentos").json() == chamar(
        mcp, "experimentos", projeto="moda-beleza"
    )["itens"]
    assert (
        api.post(f"/projetos/moda-beleza/experimentos/{exp['id']}/promover").json()["status"]
        == "ativo"
    )
    analise = api.post(
        "/projetos/moda-beleza/analisar", json={"video": VIDEO, "canal_id": "canal1"}
    ).json()
    trace = api.get(f"/projetos/moda-beleza/runs/{analise['run_id']}/trace").json()
    assert trace == chamar(mcp, "trace", projeto="moda-beleza", run_id=analise["run_id"])["itens"]
    # uma análise gravada reabre inteira a partir do trace, igual à resposta original
    reaberta = api.get(f"/projetos/moda-beleza/analises/{analise['run_id']}").json()
    assert reaberta["timeline"] == analise["timeline"]
    assert reaberta["fatores"] == analise["fatores"]
    assert reaberta["mediana_canal"] == analise["mediana_canal"]
    assert reaberta["explicacao"] == analise["explicacao"]


def test_humano_aprova_promocao_e_anota_erro(tmp_path):
    framework = projeto(tmp_path, modo="cientista")
    api = TestClient(criar_app(framework))
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    api.post(f"/projetos/moda-beleza/experimentos/{exp.id}/promover")

    decisao = api.post(
        f"/projetos/moda-beleza/experimentos/{exp.id}/decisao",
        json={"aprovar": True, "nota": "ok"},
    ).json()
    video_id = framework.videos("moda-beleza")[0].id
    nota = api.post(
        "/projetos/moda-beleza/notas",
        json={"video_id": video_id, "tipo": "dado_ruim", "nota": "live"},
    ).json()

    assert decisao["status"] == "ativo"
    assert nota["tipo"] == "dado_ruim"
    assert json.dumps(api.get("/projetos/moda-beleza/notas").json())


def test_erro_de_dominio_vira_status_http_legivel(tmp_path):
    api = TestClient(criar_app(projeto(tmp_path)))

    nao_existe = api.get("/projetos/outro")
    sem_modelo = api.post(
        "/projetos/moda-beleza/analisar", json={"video": VIDEO, "canal_id": "canal1"}
    )

    assert nao_existe.status_code == 404
    assert "criar_projeto" in nao_existe.json()["erro"]
    assert sem_modelo.status_code == 400
    assert "experimentar" in sem_modelo.json()["erro"]


def test_visao_geral_canais_e_troca_de_modo(tmp_path):
    api = TestClient(criar_app(projeto(tmp_path)))

    resumo = api.get("/projetos/moda-beleza/resumo").json()
    canais = api.get("/projetos/moda-beleza/canais").json()
    modo = api.post("/projetos/moda-beleza/modo", json={"modo": "cientista"}).json()
    invalido = api.post("/projetos/moda-beleza/modo", json={"modo": "turbo"})

    assert resumo["canais"] == 4 and resumo["videos"] == 400
    assert {c["id"] for c in canais} == {"canal0", "canal1", "canal2", "canal3"}
    assert canais[0]["videos"] == 100
    assert modo["modo"] == "cientista"
    assert api.get("/projetos/moda-beleza").json()["modo"] == "cientista"
    assert invalido.status_code == 400
