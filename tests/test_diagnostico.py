from tests.test_experimentos import projeto


def test_diagnostico_aponta_camadas_incompletas_reobservacao_e_ganchos(tmp_path):
    framework = projeto(tmp_path)

    d = framework.diagnostico("moda-beleza")

    tipos = {p.tipo for p in d.pistas}
    assert {"camada_incompleta", "sem_reobservacao", "ganchos_insuficientes"} <= tipos
    acoes = {p.acao for p in d.pistas}
    assert {"calcular_texto", "calcular_titulos", "observar_recentes"} <= acoes
    assert d.base["videos"] > 0 and d.base["ruido_alvo"] is not None


def test_otimizar_devolve_as_pistas_e_as_pistas_somem_quando_resolvidas(tmp_path):
    framework = projeto(tmp_path)
    framework.calcular_texto("moda-beleza")
    framework.calcular_titulos("moda-beleza")
    framework.observar_recentes("moda-beleza", dias_max=10_000)

    ciclo = framework.otimizar("moda-beleza", orcamento=3, paciencia=1)

    tipos = {p["tipo"] for p in ciclo.pistas}
    assert "camada_incompleta" not in tipos
    assert "sem_reobservacao" not in tipos
    assert "ganchos_insuficientes" in tipos  # o fake tem poucos ganchos
