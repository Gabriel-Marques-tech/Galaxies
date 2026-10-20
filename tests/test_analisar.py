import pytest

from galaxies import CanalForaDaBase, ErroGalaxies, Framework
from galaxies.analise import DIAS_DA_TIMELINE, Analise
from galaxies.portas import Dependencias
from tests.fakes import (
    DescritorFalso,
    EmbedderFalso,
    ExtratorFalso,
    JevFalso,
    TranscritorFalso,
    YouTubeFalso,
    base_com_sinal,
)
from tests.test_treino import projeto_treinavel

PERGUNTA = {"titulo": "Você sabia disso?", "duracao_s": 30}
SEM_PERGUNTA = {"titulo": "Meu look do dia", "duracao_s": 30}


@pytest.fixture(scope="module")
def treinado(tmp_path_factory):
    framework = projeto_treinavel(tmp_path_factory.mktemp("analisar"))
    framework.treinar("moda-beleza")
    return framework


def test_timeline_tem_quantis_ordenados_e_cresce_com_o_tempo(treinado):
    analise = treinado.analisar("moda-beleza", PERGUNTA, canal_id="canal2")

    assert [p.dias for p in analise.timeline] == list(DIAS_DA_TIMELINE)
    for ponto in analise.timeline:
        assert ponto.q10 <= ponto.q50 <= ponto.q90
    for q in ("q10", "q50", "q90"):
        valores = [getattr(p, q) for p in analise.timeline]
        assert valores == sorted(valores)


def test_saida_valida_contra_o_schema(treinado):
    analise = treinado.analisar("moda-beleza", PERGUNTA, canal_id="canal2")

    assert Analise.model_validate(analise.model_dump()) == analise
    assert 0.0 <= analise.p_viral <= 1.0
    assert analise.alvo == "likes"


def test_previsao_reage_ao_que_o_modelo_aprendeu(treinado):
    com = treinado.analisar("moda-beleza", PERGUNTA, canal_id="canal2")
    sem = treinado.analisar("moda-beleza", SEM_PERGUNTA, canal_id="canal2")

    assert com.previsao_7d.q50 > sem.previsao_7d.q50
    assert com.p_viral >= sem.p_viral
    # no fake, pergunta, tamanho e palavras do título carregam o mesmo sinal
    assert com.fatores[0].feature.startswith("titulo_")


def test_canal_fora_da_base_e_recusado_sugerindo_adicionar_canal(treinado):
    with pytest.raises(CanalForaDaBase, match="adicionar_canal"):
        treinado.analisar("moda-beleza", PERGUNTA, canal_id="canal_desconhecido")


def test_sem_treino_pede_para_treinar(tmp_path):
    framework = projeto_treinavel(tmp_path)

    with pytest.raises(ErroGalaxies, match="treinar"):
        framework.analisar("moda-beleza", PERGUNTA, canal_id="canal2")


def test_com_arquivo_roda_gancho_e_atributos_sem_sujar_a_base(tmp_path):
    base = base_com_sinal()
    deps = Dependencias(
        youtube=YouTubeFalso(base),
        extrator=ExtratorFalso(),
        descritor=DescritorFalso(),
        transcritor=TranscritorFalso(),
        embedder=EmbedderFalso(),
        jev=JevFalso(),
    )
    framework = Framework(raiz=tmp_path, dependencias=deps)
    framework.criar_projeto(
        {
            "nome": "moda-beleza",
            "setores": ["moda"],
            "canais_semente": [{"ref": f"@{c}", "setor": "moda"} for c in base],
            "alvo": "likes",
        }
    )
    framework.coletar("moda-beleza")
    framework.treinar("moda-beleza")

    analise = framework.analisar(
        "moda-beleza", {**PERGUNTA, "fonte": "/tmp/meu_short.mp4"}, canal_id="canal2"
    )

    assert deps.extrator.extraidos == ["/tmp/meu_short.mp4"]
    assert analise.gancho.descricao.startswith("mulher mostra batom")
    assert set(analise.atributos) == {a.id for a in framework.atributos("moda-beleza")}
    assert framework.camada_bruta("moda-beleza") == []
    etapas = [e.nome for e in framework.trace("moda-beleza", analise.run_id)]
    assert etapas[0] == "extrair_gancho"
    assert {"perguntar_atributos", "prever", "explicar"} <= set(etapas)
