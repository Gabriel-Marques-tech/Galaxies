from galaxies import atributos as atrib
from galaxies import otimizacao
from tests.test_experimentos import VIDEO, projeto


def test_calcular_titulos_responde_as_perguntas_de_titulo_para_todos_os_videos(tmp_path):
    framework = projeto(tmp_path)

    resumo = framework.calcular_titulos("moda-beleza")
    de_novo = framework.calcular_titulos("moda-beleza")

    total = len(framework.videos("moda-beleza"))
    assert resumo == {"calculados": total, "falhas": 0, "extrator": "falso"}
    assert de_novo["calculados"] == 0  # só o que falta
    with framework._abrir_existente("moda-beleza") as banco:
        assert "titulo" in otimizacao.disponiveis(banco)[0]
        linhas = atrib.features(banco, list(atrib.DE_TITULO))
    assert len(linhas) == total
    assert "titulo_tom=informativo" in linhas[0]


def test_receita_com_camada_titulo_treina_e_analisa_perguntando_ao_extrator_rapido(tmp_path):
    framework = projeto(tmp_path)
    framework.calcular_titulos("moda-beleza")

    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados", "titulo"]})
    framework.promover("moda-beleza", exp.id)
    analise = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    assert any(c.startswith("titulo_") for c in exp.resultado.colunas)
    assert exp.resultado.n_teste > 0
    assert analise.previsao_7d.q50 > 0
    feitas = framework.dependencias.rapido.perguntas_feitas
    assert "titulo_tendencia" in feitas


def test_camada_titulo_sem_respostas_explica_o_que_rodar(tmp_path):
    import pytest

    from galaxies import ErroGalaxies

    framework = projeto(tmp_path)

    with pytest.raises(ErroGalaxies, match="calcular_titulos"):
        framework.experimentar("moda-beleza", {"camadas": ["metadados", "titulo"]})
