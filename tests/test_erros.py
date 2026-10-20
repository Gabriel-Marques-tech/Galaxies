from tests.fakes import ExtratorFalso, video
from tests.test_camada_bruta import montar
from tests.test_treino import projeto_treinavel


def test_reprocessar_limpa_a_falha_e_refaz_o_video(tmp_path):
    quebrado = video("beleza1")
    framework, deps = montar(tmp_path, [quebrado], ExtratorFalso(falhar_em={quebrado["id"]}))
    framework.processar_ganchos("moda-beleza")
    assert framework.falhas("moda-beleza")

    deps.extrator.falhar_em = set()  # a rede voltou
    resumo = framework.reprocessar("moda-beleza", [quebrado["id"]])

    assert resumo.processados == 1
    assert framework.falhas("moda-beleza") == []
    assert [b.video_id for b in framework.camada_bruta("moda-beleza")] == [quebrado["id"]]


def test_reprocessar_sem_ids_refaz_todas_as_falhas(tmp_path):
    a, b, ok = video("beleza1"), video("beleza1"), video("beleza1")
    framework, deps = montar(tmp_path, [a, b, ok], ExtratorFalso(falhar_em={a["id"], b["id"]}))
    framework.processar_ganchos("moda-beleza")

    deps.extrator.falhar_em = set()
    resumo = framework.reprocessar("moda-beleza")

    assert resumo.processados == 2
    assert deps.extrator.extraidos.count(ok["id"]) == 1  # o que deu certo não é refeito


def test_video_excluido_nao_entra_no_processamento(tmp_path):
    fora, dentro = video("beleza1"), video("beleza1")
    framework, deps = montar(tmp_path, [fora, dentro])

    framework.excluir("moda-beleza", video_ids=[fora["id"]])
    framework.processar_ganchos("moda-beleza")

    assert deps.extrator.extraidos == [dentro["id"]]


def test_canal_excluido_nao_entra_no_proximo_treino(tmp_path):
    framework = projeto_treinavel(tmp_path)
    antes = framework.treinar("moda-beleza").split

    framework.excluir("moda-beleza", canais=["canal0"])
    depois = framework.treinar("moda-beleza").split

    assert depois.n_treino + depois.n_teste < antes.n_treino + antes.n_teste
    assert "canal0" not in {e.canal_id for e in framework.erros("moda-beleza").piores}


def test_erros_mostra_piores_previsoes_segmentos_e_falhas_do_pipeline(tmp_path):
    framework = projeto_treinavel(tmp_path)
    framework.treinar("moda-beleza")

    relatorio = framework.erros("moda-beleza")

    assert len(relatorio.piores) == 20
    assert relatorio.piores[0].erro_log >= relatorio.piores[-1].erro_log
    assert {"canal", "setor", "idade"} <= set(relatorio.segmentos)
    assert relatorio.falhas_por_etapa == {}


def test_erros_sem_treino_ainda_lista_falhas(tmp_path):
    quebrado = video("beleza1")
    framework, _ = montar(tmp_path, [quebrado], ExtratorFalso(falhar_em={quebrado["id"]}))
    framework.processar_ganchos("moda-beleza")

    relatorio = framework.erros("moda-beleza")

    assert relatorio.falhas_por_etapa == {"extrair_gancho": 1}
    assert relatorio.piores == []
