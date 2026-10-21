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
    promover_metadados(framework)
    return framework


def promover_metadados(framework):
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    framework.promover("moda-beleza", exp.id)


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

    with pytest.raises(ErroGalaxies, match="experimentar"):
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
        rapido=JevFalso(),
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
    promover_metadados(framework)

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


def test_sugere_mudancas_que_o_modelo_associa_a_mais_engajamento(treinado):
    sem = treinado.analisar("moda-beleza", SEM_PERGUNTA, canal_id="canal2")
    com = treinado.analisar("moda-beleza", PERGUNTA, canal_id="canal2")

    assert "título em forma de pergunta" in [s.mudanca for s in sem.sugestoes]
    assert all(s.ganho >= 0.03 and s.previsto_7d > 0 for s in sem.sugestoes)
    assert "título em forma de pergunta" not in [s.mudanca for s in com.sugestoes]


def test_comparar_diz_qual_versao_deve_ir_melhor(treinado):
    resultado = treinado.comparar("moda-beleza", SEM_PERGUNTA, PERGUNTA, canal_id="canal2")

    assert resultado.vencedor == "b"
    assert resultado.b.previsao_7d.q50 > resultado.a.previsao_7d.q50
    assert resultado.diferenca > 0


def test_avaliacao_mede_o_acerto_em_pares_do_mesmo_canal(treinado):
    (exp,) = [e for e in treinado.experimentos("moda-beleza") if e.status == "ativo"]

    assert exp.resultado.baseline.acerto_pares == 0.5  # média do canal não ordena nada
    assert exp.resultado.modelo.acerto_pares > 0.6
