from galaxies import Framework

CONFIG = {
    "nome": "moda-beleza",
    "setores": ["moda", "beleza"],
    "canais_semente": [{"ref": "@canal_a", "setor": "moda"}],
    "alvo": "views",
}


def test_criar_projeto_fica_registrado_como_run_com_etapas(tmp_path):
    framework = Framework(raiz=tmp_path)
    framework.criar_projeto(CONFIG)

    (run,) = framework.runs("moda-beleza")
    etapas = framework.trace("moda-beleza", run.id)

    assert run.operacao == "criar_projeto"
    assert run.status == "ok"
    assert [etapa.nome for etapa in etapas] == ["salvar_config"]
    assert etapas[0].erro is None
    assert etapas[0].duracao_ms >= 0
