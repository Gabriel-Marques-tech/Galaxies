import pytest

from galaxies import ErroGalaxies
from tests.test_experimentos import projeto

pytestmark = pytest.mark.lento  # treina e otimiza de verdade (dezenas de segundos)


@pytest.fixture
def com_ganchos(tmp_path):
    return projeto(tmp_path, ganchos=True)


def test_amostra_de_revisao_traz_o_contexto_e_a_resposta_do_extrator(com_ganchos):
    amostra = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=5)

    assert len(amostra) == 5
    item = amostra[0]
    assert item.extrator == "falso"
    assert item.gancho.startswith("mulher mostra batom")
    assert item.resposta_extrator == pytest.approx(0.8)
    assert item.titulo


def test_concordancia_compara_o_humano_com_o_extrator(com_ganchos):
    amostra = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=4)
    for item, valor in zip(amostra, [True, True, True, False], strict=True):
        com_ganchos.revisar("moda-beleza", item.video_id, "rosto_no_gancho", valor)
    formato = com_ganchos.amostra_para_revisao("moda-beleza", "formato", n=2)
    com_ganchos.revisar("moda-beleza", formato[0].video_id, "formato", "tutorial")  # = extrator
    com_ganchos.revisar("moda-beleza", formato[1].video_id, "formato", "review")

    concordancia = {c.atributo_id: c for c in com_ganchos.concordancia("moda-beleza")}

    assert concordancia["rosto_no_gancho"].revisados == 4
    assert concordancia["rosto_no_gancho"].concordancia == pytest.approx(0.75)
    assert concordancia["formato"].concordancia == pytest.approx(0.5)
    assert concordancia["formato"].confiavel is False  # abaixo de 70%


def test_amostra_nao_repete_videos_ja_revisados(com_ganchos):
    primeira = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=3)
    for item in primeira:
        com_ganchos.revisar("moda-beleza", item.video_id, "rosto_no_gancho", True)

    segunda = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=3)

    assert not {i.video_id for i in primeira} & {i.video_id for i in segunda}


def test_revisao_com_valor_invalido_e_recusada(com_ganchos):
    (item,) = com_ganchos.amostra_para_revisao("moda-beleza", "formato", n=1)

    with pytest.raises(ErroGalaxies, match="opções"):
        com_ganchos.revisar("moda-beleza", item.video_id, "formato", "podcast")


def test_nota_de_dado_ruim_exclui_o_video_e_padrao_vira_pista_para_o_agente(tmp_path):
    framework = projeto(tmp_path)
    ruim, collab = [v.id for v in framework.videos("moda-beleza")[:2]]

    framework.anotar_erro("moda-beleza", ruim, "dado_ruim", "views compradas")
    framework.anotar_erro("moda-beleza", collab, "padrao", "collab com famosa")

    notas = framework.notas("moda-beleza")
    assert [(n.video_id, n.tipo) for n in notas] == [(ruim, "dado_ruim"), (collab, "padrao")]
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    assert ruim not in {e.video_id for e in exp.resultado.piores}
    assert framework.erros("moda-beleza").notas_padrao == ["collab com famosa"]


def test_amostra_poe_primeiro_os_videos_em_que_os_extratores_discordam(com_ganchos):
    import json
    from datetime import UTC, datetime

    atributo = next(a for a in com_ganchos.atributos("moda-beleza") if a.id == "rosto_no_gancho")
    antes = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=5)
    alvo = antes[-1].video_id  # último da fila; o fake respondeu 0.8 (sim)
    with com_ganchos._abrir_existente("moda-beleza") as banco:
        banco.execute(
            "INSERT OR REPLACE INTO respostas VALUES (?, ?, ?, ?, ?, ?)",
            [
                alvo,
                "rosto_no_gancho",
                "outro",
                atributo.assinatura,
                json.dumps({"type": "noul", "noul": 0.1}),
                datetime.now(UTC),
            ],
        )

    depois = com_ganchos.amostra_para_revisao("moda-beleza", "rosto_no_gancho", n=5)

    assert depois[0].video_id == alvo
    assert depois[0].discordancia is True
    assert depois[0].outras_respostas == {"outro": 0.1}
    assert all(not i.discordancia for i in depois[1:])
