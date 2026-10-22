import pytest

from galaxies import ErroGalaxies
from tests.test_experimentos import VIDEO, projeto


@pytest.fixture
def pronto(tmp_path):
    framework = projeto(tmp_path)
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    framework.promover("moda-beleza", exp.id)
    return framework


def test_acompanhar_liga_a_analise_ao_video_publicado_e_guarda_a_primeira_observacao(pronto):
    analise = pronto.analisar("moda-beleza", VIDEO, canal_id="canal1")
    publicado = next(v for v in pronto.videos("moda-beleza") if v.canal_id == "canal1")

    acomp = pronto.acompanhar("moda-beleza", analise.run_id, publicado.id)

    assert acomp.video_id == publicado.id
    assert acomp.run_id == analise.run_id
    assert acomp.alvo == "likes"
    assert [p.dias for p in acomp.timeline] == [1, 3, 7, 14, 30]
    assert len(acomp.observacoes) == 1
    assert acomp.observacoes[0].likes == publicado.likes
    assert acomp.observacoes[0].idade_dias > 7


def test_atualizar_busca_os_numeros_de_novo_e_compara_com_o_previsto(pronto):
    analise = pronto.analisar("moda-beleza", VIDEO, canal_id="canal1")
    publicado = next(v for v in pronto.videos("moda-beleza") if v.canal_id == "canal1")
    pronto.acompanhar("moda-beleza", analise.run_id, publicado.id)

    resumo = pronto.atualizar_acompanhamentos("moda-beleza")
    lista = pronto.acompanhamentos("moda-beleza")

    assert resumo.atualizados == 1
    (a,) = lista.videos
    assert len(a.observacoes) == 2
    assert a.ultima is not None
    assert a.ultima.previsto_q10 <= a.ultima.previsto_q50 <= a.ultima.previsto_q90
    assert a.ultima.real == publicado.likes
    assert a.ultima.dentro_da_faixa == (
        a.ultima.previsto_q10 <= a.ultima.real <= a.ultima.previsto_q90
    )
    assert lista.n == 1
    assert 0 <= lista.cobertura <= 1


def test_acompanhar_exige_um_run_de_analise(pronto):
    run = next(r for r in pronto.runs("moda-beleza") if r.operacao == "experimentar")
    publicado = pronto.videos("moda-beleza")[0]

    with pytest.raises(ErroGalaxies, match="analisar"):
        pronto.acompanhar("moda-beleza", run.id, publicado.id)


def test_comparacao_tem_a_faixa_provavel_dentro_da_quase_certa(pronto):
    analise = pronto.analisar("moda-beleza", VIDEO, canal_id="canal1")
    publicado = next(v for v in pronto.videos("moda-beleza") if v.canal_id == "canal1")
    pronto.acompanhar("moda-beleza", analise.run_id, publicado.id)

    (a,) = pronto.acompanhamentos("moda-beleza").videos

    u = a.ultima
    assert u.previsto_q10 <= u.previsto_q25 <= u.previsto_q50 <= u.previsto_q75 <= u.previsto_q90
    assert u.dentro_da_faixa_50 == (u.previsto_q25 <= u.real <= u.previsto_q75)
    assert not u.dentro_da_faixa_50 or u.dentro_da_faixa  # a provável está dentro da quase certa


def test_historico_de_analises_traz_previsao_explicacao_e_acompanhamento(pronto):
    analise = pronto.analisar("moda-beleza", VIDEO, canal_id="canal1")
    publicado = next(v for v in pronto.videos("moda-beleza") if v.canal_id == "canal1")
    pronto.acompanhar("moda-beleza", analise.run_id, publicado.id)

    (item,) = pronto.analises("moda-beleza")

    assert item["run_id"] == analise.run_id and item["status"] == "ok"
    assert item["titulo"] == VIDEO["titulo"] and item["canal_id"] == "canal1"
    assert item["previsao_7d"]["dias"] == 7 and item["previsao_7d"]["q50"] > 0
    assert item["explicacao"].startswith("O modelo espera")
    assert item["acompanhamento"]["video_id"] == publicado.id
