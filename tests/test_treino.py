from galaxies import Framework
from galaxies.portas import Dependencias
from tests.fakes import YouTubeFalso, base_com_sinal


def projeto_treinavel(tmp_path, base=None, alvo="likes"):
    base = base or base_com_sinal()
    framework = Framework(raiz=tmp_path, dependencias=Dependencias(youtube=YouTubeFalso(base)))
    framework.criar_projeto(
        {
            "nome": "moda-beleza",
            "setores": ["moda"],
            "canais_semente": [{"ref": f"@{c}", "setor": "moda"} for c in base],
            "alvo": alvo,
        }
    )
    framework.coletar("moda-beleza")
    return framework


def test_treino_usa_split_temporal_e_supera_o_baseline_do_canal(tmp_path):
    framework = projeto_treinavel(tmp_path)

    framework.treinar("moda-beleza")
    avaliacao = framework.avaliar("moda-beleza")

    assert avaliacao.split.fim_treino <= avaliacao.split.inicio_teste
    assert avaliacao.split.n_teste > 0
    metadados = avaliacao.camadas["metadados"]
    assert metadados.mae < avaliacao.baseline.mae
    assert metadados.spearman_no_canal > avaliacao.baseline.spearman_no_canal
