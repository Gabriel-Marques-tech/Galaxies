import numpy as np
import pytest

from galaxies import ErroGalaxies, otimizacao, vizinhos
from galaxies.atributos import Atributo
from tests.test_experimentos import VIDEO, projeto

PROJETO = "moda-beleza"

DEFINICOES = [
    Atributo(
        id="formato",
        tipo="choice",
        instrucoes="Qual o formato do vídeo?",
        criterios={"tutorial": "ensina", "review": "avalia", "humor": "ri"},
    ),
    Atributo(id="rosto", tipo="noul", instrucoes="Aparece um rosto no gancho?"),
    Atributo(
        id="ritmo",
        tipo="score",
        instrucoes="Ritmo dos cortes?",
        criterios=["lento", "medio", "rapido"],
    ),
]


def fonte_a_mao():
    """Sete sementes: cinco perto do eixo x e duas perto do eixo y."""
    vetores = np.array(
        [[1, 0.1], [1, 0.2], [1, 0.0], [1, -0.1], [1, -0.2], [0.1, 1], [-0.1, 1]], dtype=np.float32
    )
    vetores /= np.linalg.norm(vetores, axis=1, keepdims=True)
    return vizinhos.Fonte(
        extrator="falso",
        video_ids=[f"v{i}" for i in range(7)],
        embeddings=vetores,
        rotulos={
            "formato": ["tutorial", "tutorial", "tutorial", "review", "humor", "humor", "humor"],
            "rosto": [True, True, True, True, False, False, False],
            "ritmo": [2, 1, 1, 0, 2, 0, 0],
        },
    )


def test_responder_vota_pela_maioria_com_a_fracao_dos_vizinhos_como_confianca():
    fonte = fonte_a_mao()

    resposta = vizinhos.responder([1.0, 0.0], fonte, DEFINICOES, k=5)

    formato = resposta["formato"]
    assert formato["type"] == "choice" and formato["choice"] == "tutorial"
    assert formato["probabilities"] == {"tutorial": 0.6, "review": 0.2, "humor": 0.2}
    assert formato["confidence"] == pytest.approx(0.6)
    rosto = resposta["rosto"]
    assert rosto["type"] == "noul" and rosto["noul"] == pytest.approx(0.8)
    assert rosto["confidence"] == pytest.approx(0.8)
    ritmo = resposta["ritmo"]
    assert ritmo["type"] == "score" and ritmo["score"] == 1  # mediana de [2, 1, 1, 0, 2]
    assert ritmo["confidence"] == pytest.approx(0.4)


def test_responder_perto_do_outro_grupo_muda_o_voto_e_k_maior_que_a_fonte_usa_todas():
    fonte = fonte_a_mao()

    perto_de_y = vizinhos.responder([0.0, 1.0], fonte, DEFINICOES, k=3)
    todas = vizinhos.responder([0.0, 1.0], fonte, DEFINICOES, k=50)

    # Vizinhos de [0, 1]: v5 e v6 (eixo y) e, em terceiro, v1 ([1, 0.2]), que tem rosto.
    assert perto_de_y["formato"]["choice"] == "humor"
    assert perto_de_y["formato"]["confidence"] == pytest.approx(2 / 3)
    assert perto_de_y["rosto"]["noul"] == pytest.approx(1 / 3)
    assert perto_de_y["rosto"]["confidence"] == pytest.approx(2 / 3)
    assert todas["rosto"]["noul"] == pytest.approx(4 / 7)


@pytest.fixture(scope="module")
def com_ganchos_leves(tmp_path_factory):
    """240 ganchos completos com atributos do Jev falso (sementes) + 160 ganchos leves."""
    fw = projeto(tmp_path_factory.mktemp("viz"), ganchos=True)
    fw.processar_ganchos(PROJETO, limite_por_canal=100, leve=True)
    return fw


@pytest.mark.lento
def test_rotular_grava_so_nos_videos_sem_resposta_da_fonte(com_ganchos_leves):
    fw = com_ganchos_leves

    resumo = fw.rotular_vizinhos(PROJETO, k=7)

    assert (resumo.sementes, resumo.rotulados, resumo.fonte) == (240, 160, "falso")
    leves = {b.video_id for b in fw.camada_bruta(PROJETO) if b.descricao == ""}
    assert len(leves) == 160
    com_vizinhos = {f["video_id"] for f in _features(fw, "vizinhos")}
    com_fonte = {f["video_id"] for f in _features(fw, "falso")}
    assert com_vizinhos == leves
    assert not (com_vizinhos & com_fonte)
    assert fw.features_de_atributos(PROJETO).__len__() == 400  # qualquer extrator: a base toda
    run = [r for r in fw.runs(PROJETO) if r.operacao == "rotular_vizinhos"][-1]
    assert [e.nome for e in fw.trace(PROJETO, run.id)] == ["rotular"]


@pytest.mark.lento
def test_avaliar_devolve_concordancia_entre_0_e_1_por_atributo(com_ganchos_leves):
    avaliacao = com_ganchos_leves.avaliar_vizinhos(PROJETO, k=7)

    assert avaliacao.sementes == 240 and avaliacao.k == 7
    assert len(avaliacao.atributos) == 15
    for a in avaliacao.atributos:
        assert 0.0 <= a.concordancia <= 1.0
        assert 0.0 <= a.fracao_confiante <= 1.0
        assert 0.0 <= a.majoritario <= 1.0
        assert a.concordancia_confiante is None or 0.0 <= a.concordancia_confiante <= 1.0
    # O Jev falso responde sempre igual: o kNN reproduz e o majoritário também acerta tudo.
    assert avaliacao.concordancia_media == pytest.approx(1.0)


@pytest.mark.lento
def test_receita_com_extrator_vizinhos_treina_e_a_analise_nao_precisa_de_jev(com_ganchos_leves):
    fw = com_ganchos_leves
    fw.rotular_vizinhos(PROJETO)
    with fw._abrir_existente(PROJETO) as banco:
        _, extratores = otimizacao.disponiveis(banco)
    assert "vizinhos" in extratores

    exp = fw.experimentar(PROJETO, {"camadas": ["metadados", "atributos"], "extrator": "vizinhos"})
    assert exp.receita.extrator == "vizinhos"
    assert exp.resultado.n_treino + exp.resultado.n_teste == 160  # só os ganchos leves
    assert "rosto_no_gancho" in exp.resultado.colunas

    fw.promover(PROJETO, exp.id)
    jev = fw.dependencias.jev
    fw.dependencias.jev = None
    try:
        analise = fw.analisar(PROJETO, {**VIDEO, "fonte": "/tmp/short.mp4"}, canal_id="canal1")
    finally:
        fw.dependencias.jev = jev
    assert analise.experimento_id == exp.id
    assert analise.atributos["rosto_no_gancho"]["type"] == "noul"
    assert 0.0 <= analise.atributos["rosto_no_gancho"]["confidence"] <= 1.0
    etapas = [e.nome for e in fw.trace(PROJETO, analise.run_id)]
    assert "responder_vizinhos" in etapas and "perguntar_atributos" not in etapas
    # Com o Jev configurado ('falso' ≠ 'vizinhos'), o modelo dos vizinhos continua válido.
    assert fw.analisar(PROJETO, {**VIDEO, "fonte": "/tmp/s.mp4"}, canal_id="canal1").atributos


@pytest.mark.lento
def test_analise_com_vizinhos_funciona_sem_descritor_nem_transcritor(com_ganchos_leves):
    fw = com_ganchos_leves
    deps = fw.dependencias
    descritor, transcritor, chamadas = deps.descritor, deps.transcritor, deps.descritor.chamadas
    deps.descritor = deps.transcritor = None
    try:
        analise = fw.analisar(PROJETO, {**VIDEO, "fonte": "/tmp/short.mp4"}, canal_id="canal1")
    finally:
        deps.descritor, deps.transcritor = descritor, transcritor
    assert analise.gancho.descricao == ""
    assert analise.atributos is not None
    assert deps.descritor.chamadas == chamadas


def test_sem_sementes_o_erro_diz_o_que_rodar(tmp_path):
    fw = projeto(tmp_path)
    fw.processar_ganchos(PROJETO, limite_por_canal=2, leve=True)

    with pytest.raises(ErroGalaxies, match="calcular_atributos"):
        fw.rotular_vizinhos(PROJETO)


def _features(fw, extrator):
    from galaxies import atributos as atrib

    with fw._abrir_existente(PROJETO) as banco:
        return atrib.features(banco, atrib.ler_definicoes(banco), extrator)
