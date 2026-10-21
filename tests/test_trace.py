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


def test_run_em_andamento_fica_num_arquivo_ao_lado_do_banco_e_some_no_fim(tmp_path):
    from galaxies.trace import ARQUIVO_ANDAMENTO, executar

    framework = Framework(raiz=tmp_path)
    framework.criar_projeto(CONFIG)
    assert framework.andamento("moda-beleza") is None
    pasta = tmp_path / "projetos" / "moda-beleza"

    with framework._abrir_existente("moda-beleza") as banco, executar(banco, "otimizar") as ex:
        with ex.etapa("tentativa", {"origem": "padrão: historico"}):
            pass
        vivo = framework.andamento("moda-beleza")
        assert vivo["operacao"] == "otimizar"
        assert vivo["etapas"] == 1
        assert vivo["ultima"]["nome"] == "tentativa"
        assert "historico" in vivo["ultima"]["entrada"]
        assert vivo["decorrido_s"] >= 0

    assert not (pasta / ARQUIVO_ANDAMENTO).exists()
    assert framework.andamento("moda-beleza") is None
