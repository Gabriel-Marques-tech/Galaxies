import pytest

from galaxies import ErroGalaxies
from tests.test_experimentos import VIDEO, projeto


def test_ancora_movel_treina_preve_e_compara_com_o_mesmo_baseline(tmp_path):
    framework = projeto(tmp_path)

    fixa = framework.experimentar("moda-beleza", {"camadas": ["metadados", "historico"]})
    movel = framework.experimentar(
        "moda-beleza", {"camadas": ["metadados", "historico"], "ancora": "movel"}
    )

    assert movel.receita.ancora == "movel"
    assert movel.resultado.n_teste == fixa.resultado.n_teste
    # mesma referência (LightGBM multithread varia na 3ª casa)
    assert movel.resultado.baseline.mae == pytest.approx(fixa.resultado.baseline.mae, rel=1e-6)
    assert movel.resultado.controle_metadados.mae == pytest.approx(
        fixa.resultado.controle_metadados.mae, rel=0.02
    )

    framework.promover("moda-beleza", movel.id)
    a = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")
    assert a.previsao_7d.q10 <= a.previsao_7d.q50 <= a.previsao_7d.q90
    assert a.previsao_7d.q50 > 0


def test_ancora_movel_exige_historico(tmp_path):
    framework = projeto(tmp_path)
    with pytest.raises(ErroGalaxies, match="historico"):
        framework.experimentar("moda-beleza", {"camadas": ["metadados"], "ancora": "movel"})
