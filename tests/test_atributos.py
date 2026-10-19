import pytest

from galaxies import ConfigInvalida, Framework
from galaxies.portas import Dependencias
from tests.fakes import (
    DescritorFalso,
    EmbedderFalso,
    ExtratorFalso,
    JevFalso,
    TranscritorFalso,
    YouTubeFalso,
    video,
)

CONFIG = {
    "nome": "moda-beleza",
    "setores": ["moda", "beleza"],
    "canais_semente": [{"ref": "@beleza1", "setor": "beleza"}],
    "alvo": "likes",
}

FORMATO = {
    "id": "formato",
    "tipo": "choice",
    "instrucoes": "Qual o formato do vídeo?",
    "criterios": {"tutorial": "Ensina um passo a passo", "review": "Avalia um produto"},
}
CLAREZA = {
    "id": "clareza",
    "tipo": "score",
    "instrucoes": "Quão clara é a promessa do gancho?",
    "criterios": ["confusa", "razoável", "clara"],
}
ROSTO = {"id": "rosto", "tipo": "noul", "instrucoes": "Aparece um rosto nos primeiros segundos?"}


def montar(tmp_path, n_videos=1):
    deps = Dependencias(
        youtube=YouTubeFalso({"beleza1": [video("beleza1") for _ in range(n_videos)]}),
        extrator=ExtratorFalso(),
        descritor=DescritorFalso(),
        transcritor=TranscritorFalso(),
        embedder=EmbedderFalso(),
        jev=JevFalso(),
    )
    framework = Framework(raiz=tmp_path, dependencias=deps)
    framework.criar_projeto(CONFIG)
    framework.coletar("moda-beleza")
    framework.processar_ganchos("moda-beleza")
    return framework, deps


def test_projeto_novo_comeca_com_os_15_atributos_padrao(tmp_path):
    framework, _ = montar(tmp_path)

    atributos = framework.atributos("moda-beleza")

    assert len(atributos) == 15
    assert len({a.id for a in atributos}) == 15
    assert {a.tipo for a in atributos} == {"choice", "score", "noul"}


def test_respostas_do_jev_viram_features_numericas(tmp_path):
    framework, _ = montar(tmp_path)
    framework.definir_atributos("moda-beleza", [FORMATO, CLAREZA, ROSTO])

    framework.calcular_atributos("moda-beleza")

    (linha,) = framework.features_de_atributos("moda-beleza")
    assert linha["formato=tutorial"] == pytest.approx(0.7)
    assert linha["formato=review"] == pytest.approx(0.3)
    assert linha["clareza"] == pytest.approx(0.5)  # nível 1 de 0..2
    assert linha["rosto"] == pytest.approx(0.8)


@pytest.mark.parametrize(
    "invalido",
    [
        {**FORMATO, "criterios": {"so_uma": "opção única"}},
        {**CLAREZA, "criterios": [str(i) for i in range(11)]},
        {**ROSTO, "criterios": ["sim", "não"]},
        {**ROSTO, "id": "Rosto Visível"},
        {**ROSTO, "tipo": "texto_livre"},
    ],
)
def test_atributo_malformado_e_recusado(tmp_path, invalido):
    framework, _ = montar(tmp_path)

    with pytest.raises(ConfigInvalida):
        framework.definir_atributos("moda-beleza", [invalido])

    assert len(framework.atributos("moda-beleza")) == 15  # nada mudou


def test_ids_repetidos_e_mais_de_30_sao_recusados(tmp_path):
    framework, _ = montar(tmp_path)
    muitos = [{**ROSTO, "id": f"rosto_{i}"} for i in range(31)]

    with pytest.raises(ConfigInvalida, match="repetidos"):
        framework.definir_atributos("moda-beleza", [ROSTO, ROSTO])
    with pytest.raises(ConfigInvalida, match="30"):
        framework.definir_atributos("moda-beleza", muitos)


def test_atributo_novo_so_pergunta_ao_jev_o_que_mudou(tmp_path):
    framework, deps = montar(tmp_path, n_videos=2)
    framework.definir_atributos("moda-beleza", [FORMATO, ROSTO])
    framework.calcular_atributos("moda-beleza")
    deps.jev.perguntas_feitas.clear()
    chamadas_vlm = deps.descritor.chamadas

    framework.definir_atributos("moda-beleza", [FORMATO, ROSTO, CLAREZA])
    framework.calcular_atributos("moda-beleza")

    assert deps.jev.perguntas_feitas == ["clareza", "clareza"]
    assert deps.descritor.chamadas == chamadas_vlm
    assert all("clareza" in linha for linha in framework.features_de_atributos("moda-beleza"))


def test_mudar_o_texto_da_pergunta_invalida_a_resposta_antiga(tmp_path):
    framework, deps = montar(tmp_path)
    framework.definir_atributos("moda-beleza", [ROSTO])
    framework.calcular_atributos("moda-beleza")
    deps.jev.perguntas_feitas.clear()

    framework.definir_atributos(
        "moda-beleza", [{**ROSTO, "instrucoes": "Aparece um rosto sorrindo no início?"}]
    )
    framework.calcular_atributos("moda-beleza")

    assert deps.jev.perguntas_feitas == ["rosto"]
