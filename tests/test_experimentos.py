import pytest

from galaxies import ConfigInvalida, ErroGalaxies, Framework, experimentos
from galaxies.portas import Dependencias
from tests.fakes import (
    DescritorFalso,
    EmbedderFalso,
    ExtratorFalso,
    JevFalso,
    TextoFalso,
    TranscritorFalso,
    YouTubeFalso,
    base_com_sinal,
)

BASE = base_com_sinal(canais=4, por_canal=100)
VIDEO = {"titulo": "Você sabia disso?", "duracao_s": 30}


def projeto(tmp_path, modo="automatico", ganchos=False):
    deps = Dependencias(
        youtube=YouTubeFalso(BASE),
        extrator=ExtratorFalso(),
        descritor=DescritorFalso(),
        transcritor=TranscritorFalso(),
        embedder=EmbedderFalso(),
        jev=JevFalso(),
        texto=TextoFalso(),
    )
    framework = Framework(raiz=tmp_path, dependencias=deps)
    framework.criar_projeto(
        {
            "nome": "moda-beleza",
            "setores": ["moda"],
            "canais_semente": [{"ref": f"@{c}", "setor": "moda"} for c in BASE],
            "alvo": "likes",
            "modo": modo,
        }
    )
    framework.coletar("moda-beleza")
    if ganchos:
        framework.processar_ganchos("moda-beleza", limite_por_canal=60)
        framework.calcular_atributos("moda-beleza")
    return framework


@pytest.fixture(scope="module")
def com_ganchos(tmp_path_factory):
    return projeto(tmp_path_factory.mktemp("exp"), ganchos=True)


def test_experimento_registra_receita_hipotese_e_metricas_nas_mesmas_linhas(tmp_path):
    framework = projeto(tmp_path)

    exp = framework.experimentar(
        "moda-beleza", {"camadas": ["metadados"]}, hipotese="título com pergunta engaja"
    )

    assert exp.status == "candidato"
    assert exp.hipotese == "título com pergunta engaja"
    assert exp.resultado.modelo.n == exp.resultado.baseline.n > 0
    assert exp.resultado.modelo.mae < exp.resultado.baseline.mae
    assert exp.resultado.ganho > 0
    assert [e.id for e in framework.experimentos("moda-beleza")] == [exp.id]


def test_receita_com_atributos_usa_so_videos_com_respostas_e_mede_o_controle(com_ganchos):
    exp = com_ganchos.experimentar(
        "moda-beleza",
        {"camadas": ["metadados", "atributos"], "atributos": ["rosto_no_gancho", "formato"]},
    )

    assert exp.resultado.n_treino + exp.resultado.n_teste == 240  # 4 canais × 60 ganchos
    assert exp.resultado.controle_metadados.n == exp.resultado.modelo.n
    assert "rosto_no_gancho" in exp.resultado.colunas
    assert "formato=tutorial" in exp.resultado.colunas
    assert not any(c.startswith("texto_na_tela") for c in exp.resultado.colunas)


def test_receita_com_multimodal_guarda_o_pca(com_ganchos):
    exp = com_ganchos.experimentar("moda-beleza", {"camadas": ["metadados", "multimodal"]})

    assert any(c.startswith("siglip_") for c in exp.resultado.colunas)


@pytest.mark.parametrize(
    "receita",
    [
        {"camadas": []},
        {"camadas": ["atributos"]},  # metadados é obrigatório
        {"camadas": ["metadados"], "params": {"num_leaves": 4096}},
        {"camadas": ["metadados", "atributos"], "atributos": ["nao_existe"]},
    ],
)
def test_receita_fora_dos_limites_e_recusada(tmp_path, receita):
    framework = projeto(tmp_path)

    with pytest.raises(ConfigInvalida):
        framework.experimentar("moda-beleza", receita)


def test_modo_automatico_promove_direto_e_analisar_usa_o_modelo_ativo(tmp_path):
    framework = projeto(tmp_path)
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})

    assert framework.promover("moda-beleza", exp.id).status == "ativo"
    analise = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    assert analise.experimento_id == exp.id


def test_promover_um_novo_aposenta_o_anterior(tmp_path):
    framework = projeto(tmp_path)
    a = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    b = framework.experimentar(
        "moda-beleza", {"camadas": ["metadados"], "params": {"rodadas": 100}}
    )

    framework.promover("moda-beleza", a.id)
    framework.promover("moda-beleza", b.id)

    status = {e.id: e.status for e in framework.experimentos("moda-beleza")}
    assert status == {a.id: "aposentado", b.id: "ativo"}


def test_modo_cientista_exige_aprovacao_humana(tmp_path):
    framework = projeto(tmp_path, modo="cientista")
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})

    assert framework.promover("moda-beleza", exp.id).status == "aguardando_aprovacao"
    with pytest.raises(ErroGalaxies, match="promov"):
        framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    aprovado = framework.decidir("moda-beleza", exp.id, aprovar=True, nota="faz sentido")
    assert aprovado.status == "ativo"
    assert aprovado.nota_humana == "faz sentido"
    assert framework.analisar("moda-beleza", VIDEO, canal_id="canal1").experimento_id == exp.id


def test_humano_pode_rejeitar_com_nota(tmp_path):
    framework = projeto(tmp_path, modo="cientista")
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    framework.promover("moda-beleza", exp.id)

    rejeitado = framework.decidir("moda-beleza", exp.id, aprovar=False, nota="idade domina")

    assert rejeitado.status == "rejeitado"
    assert rejeitado.nota_humana == "idade domina"


def test_modelo_com_atributos_exige_o_video_na_analise(com_ganchos):
    exp = com_ganchos.experimentar("moda-beleza", {"camadas": ["metadados", "atributos"]})
    com_ganchos.promover("moda-beleza", exp.id)

    with pytest.raises(ErroGalaxies, match="fonte"):
        com_ganchos.analisar("moda-beleza", VIDEO, canal_id="canal1")
    analise = com_ganchos.analisar(
        "moda-beleza", {**VIDEO, "fonte": "/tmp/short.mp4"}, canal_id="canal1"
    )
    assert analise.experimento_id == exp.id


def test_ciclo_automatico_otimiza_na_validacao_e_testa_so_a_escolhida(com_ganchos):
    antes = len(com_ganchos.experimentos("moda-beleza"))
    ciclo = com_ganchos.ciclo_automatico("moda-beleza")

    assert len(ciclo.tentativas) >= 3  # receitas padrão + mutações, todas na validação
    assert len(com_ganchos.experimentos("moda-beleza")) == antes + 1  # teste usado uma vez
    (escolhido,) = ciclo.experimentos
    assert escolhido.hipotese.startswith("otimização")
    ativos = [e for e in com_ganchos.experimentos("moda-beleza") if e.status == "ativo"]
    assert [a.id for a in ativos] == [ciclo.promovido] == [escolhido.id]


def test_ciclo_automatico_e_recusado_no_modo_cientista(tmp_path):
    framework = projeto(tmp_path, modo="cientista")

    with pytest.raises(ErroGalaxies, match="cientista"):
        framework.ciclo_automatico("moda-beleza")


def _exp(camadas, ganho, melhora):
    from galaxies.experimentos import Experimento, Receita, Resultado
    from galaxies.modelagem import Metricas, agora

    metricas = Metricas(mae=1.0, spearman_no_canal=0.1, n=100)
    return Experimento(
        id="-".join(camadas),
        alvo="likes",
        receita=Receita(camadas=camadas),
        resultado=Resultado(
            n_treino=500,
            n_teste=100,
            colunas=[],
            baseline=metricas,
            controle_metadados=metricas,
            modelo=metricas,
            ganho=ganho,
            melhora_sobre_controle=melhora,
        ),
        criado_em=agora(),
    )


def test_escolha_compara_camadas_extras_com_o_controle_nas_mesmas_linhas():
    so_meta = _exp(["metadados"], ganho=0.14, melhora=0.0)
    completo = _exp(["metadados", "multimodal", "atributos"], ganho=0.09, melhora=0.035)
    fraco = _exp(["metadados", "atributos"], ganho=0.06, melhora=0.002)

    assert experimentos.escolher([so_meta, completo, fraco]) is completo
    assert experimentos.escolher([so_meta, fraco]) is so_meta
    assert experimentos.escolher([_exp(["metadados"], ganho=-0.1, melhora=0)]) is None


def test_respostas_de_extratores_diferentes_convivem_e_a_receita_escolhe(tmp_path):
    framework = projeto(tmp_path, ganchos=True)

    class OutroJev(JevFalso):
        identificador = "outro"

    framework.dependencias.jev = OutroJev()
    framework.calcular_atributos("moda-beleza")

    falso = framework.experimentar(
        "moda-beleza", {"camadas": ["metadados", "atributos"], "extrator": "falso"}
    )
    outro = framework.experimentar("moda-beleza", {"camadas": ["metadados", "atributos"]})
    assert falso.receita.extrator == "falso"
    assert outro.receita.extrator == "outro"  # sem extrator na receita, usa o configurado
    assert falso.resultado.n_teste == outro.resultado.n_teste

    framework.promover("moda-beleza", falso.id)
    with pytest.raises(ErroGalaxies, match="extrator"):
        framework.analisar("moda-beleza", {**VIDEO, "fonte": "/tmp/s.mp4"}, canal_id="canal1")


def test_camadas_historico_e_texto_cobrem_todos_os_videos(tmp_path):
    framework = projeto(tmp_path)
    with pytest.raises(ConfigInvalida, match="calcular_texto"):
        framework.experimentar("moda-beleza", {"camadas": ["metadados", "texto"]})
    framework.calcular_texto("moda-beleza")

    so_meta = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    rico = framework.experimentar("moda-beleza", {"camadas": ["metadados", "historico", "texto"]})

    assert rico.resultado.n_teste == so_meta.resultado.n_teste  # mesmas linhas
    assert {"hist_media_10", "hist_rel_10", "texto_0"} <= set(rico.resultado.colunas)


def test_faixa_e_calibrada_e_a_cobertura_e_medida_no_teste(tmp_path):
    exp = projeto(tmp_path).experimentar("moda-beleza", {"camadas": ["metadados"]})

    r = exp.resultado
    assert r.calibracao > 0
    assert 0 <= r.cobertura_bruta <= 1 and 0 <= r.cobertura_80 <= 1
    if r.calibracao > 1:
        assert r.cobertura_80 >= r.cobertura_bruta  # alargar nunca cobre menos


def test_analise_responde_em_chances_e_sugere_o_que_aumenta_a_chance_de_viral(tmp_path):
    framework = projeto(tmp_path)
    framework.calcular_texto("moda-beleza")
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados", "historico", "texto"]})
    framework.promover("moda-beleza", exp.id)

    analise = framework.analisar("moda-beleza", {"titulo": "Meu look do dia"}, canal_id="canal1")

    probs = [c.prob for c in analise.chances]
    assert [c.evento for c in analise.chances][-1] == "viralizar"
    assert probs == sorted(probs, reverse=True)  # passar a mediana ≥ dobrar ≥ viralizar
    assert analise.p_viral == probs[-1]
    for s in analise.sugestoes:
        assert s.delta_p_viral >= 0.01 or s.ganho >= 0.03
    etapas = [e.nome for e in framework.trace("moda-beleza", analise.run_id)]
    assert {"historico_do_canal", "embutir_texto"} <= set(etapas)


def test_otimizar_respeita_orcamento_e_registra_cada_tentativa_no_trace(tmp_path):
    framework = projeto(tmp_path, modo="cientista")
    framework.calcular_texto("moda-beleza")

    ciclo = framework.otimizar("moda-beleza", orcamento=6, paciencia=2)

    assert 1 <= len(ciclo.tentativas) <= 6
    assert ciclo.promovido is None  # cientista: o humano decide
    (exp,) = ciclo.experimentos
    assert exp.status == "candidato"
    run = [r for r in framework.runs("moda-beleza") if r.operacao == "otimizar"][-1]
    assert len([e for e in framework.trace("moda-beleza", run.id) if e.nome == "tentativa"]) == len(
        ciclo.tentativas
    )
