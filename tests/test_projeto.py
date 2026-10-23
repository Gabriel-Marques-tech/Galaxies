import pytest

from galaxies import ConfigInvalida, Framework, ProjetoJaExiste, ProjetoNaoEncontrado

CONFIG_MODA_BELEZA = {
    "nome": "moda-beleza",
    "setores": ["moda", "beleza"],
    "canais_semente": [
        {"ref": "@canal_a", "setor": "moda"},
        {"ref": "@canal_b", "setor": "beleza"},
    ],
    "alvo": "likes",
    "detalhes": "Shorts BR de moda e beleza",
}


def test_projeto_criado_sobrevive_a_reabrir_o_framework(tmp_path):
    Framework(raiz=tmp_path).criar_projeto(CONFIG_MODA_BELEZA)

    projeto = Framework(raiz=tmp_path).obter_projeto("moda-beleza")

    assert projeto.setores == ["moda", "beleza"]
    assert [c.ref for c in projeto.canais_semente] == ["@canal_a", "@canal_b"]
    assert projeto.alvo == "likes"
    assert projeto.detalhes == "Shorts BR de moda e beleza"


def test_projeto_inexistente_gera_erro_claro(tmp_path):
    with pytest.raises(ProjetoNaoEncontrado, match="nao-existe"):
        Framework(raiz=tmp_path).obter_projeto("nao-existe")


def test_nome_repetido_e_recusado_sem_sobrescrever(tmp_path):
    framework = Framework(raiz=tmp_path)
    framework.criar_projeto(CONFIG_MODA_BELEZA)

    with pytest.raises(ProjetoJaExiste, match="moda-beleza"):
        framework.criar_projeto({**CONFIG_MODA_BELEZA, "alvo": "views"})

    assert framework.obter_projeto("moda-beleza").alvo == "likes"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("nome", "../fora-da-raiz"),
        ("nome", ""),
        ("alvo", "comentarios"),
        ("setores", []),
        ("limite_viral", 1.0),
    ],
)
def test_config_invalida_e_recusada_sem_criar_nada(tmp_path, campo, valor):
    with pytest.raises(ConfigInvalida, match=campo):
        Framework(raiz=tmp_path).criar_projeto({**CONFIG_MODA_BELEZA, campo: valor})

    assert not any(tmp_path.rglob("*.duckdb"))


def test_viral_padrao_e_3x_a_mediana_do_canal(tmp_path):
    projeto = Framework(raiz=tmp_path).criar_projeto(CONFIG_MODA_BELEZA)

    assert projeto.limite_viral == 3.0


def test_ler_projeto_com_nome_de_caminho_nao_sai_da_raiz(tmp_path):
    Framework(raiz=tmp_path / "fora").criar_projeto(CONFIG_MODA_BELEZA)
    dentro = Framework(raiz=tmp_path / "raiz")
    dentro.criar_projeto({**CONFIG_MODA_BELEZA, "nome": "outro"})

    with pytest.raises(ProjetoNaoEncontrado):
        dentro.obter_projeto("../../fora/projetos/moda-beleza")


def test_projeto_pode_nascer_sem_canais_e_o_roadmap_manda_descobrir(tmp_path):
    from galaxies.portas import Dependencias
    from tests.fakes import YouTubeFalso

    framework = Framework(raiz=tmp_path, dependencias=Dependencias(youtube=YouTubeFalso({})))
    projeto = framework.criar_projeto({**CONFIG_MODA_BELEZA, "canais_semente": []})

    assert projeto.canais_semente == []
    assert framework.proximo_passo("moda-beleza").acao == "descobrir_canais"
