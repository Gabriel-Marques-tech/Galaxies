from galaxies import Framework
from galaxies.portas import Dependencias
from tests.fakes import JevFalso, TextoFalso, YouTubeFalso, base_com_sinal
from tests.test_experimentos import projeto

BASE = base_com_sinal(canais=3, por_canal=80)


def test_proximo_passo_segue_o_roadmap_pelo_estado(tmp_path):
    fw = Framework(
        raiz=tmp_path,
        dependencias=Dependencias(
            youtube=YouTubeFalso(BASE), texto=TextoFalso(), rapido=JevFalso()
        ),
    )
    fw.criar_projeto(
        {
            "nome": "p",
            "setores": ["moda"],
            "canais_semente": [{"ref": "@canal1", "setor": "moda"}],
            "alvo": "likes",
        }
    )
    assert fw.proximo_passo("p").acao == "coletar"

    fw.coletar("p")
    assert fw.proximo_passo("p").acao == "calcular_texto"

    fw.calcular_texto("p")
    assert fw.proximo_passo("p").acao == "calcular_titulos"

    fw.calcular_titulos("p")
    passo = fw.proximo_passo("p")
    assert passo.acao == "otimizar" and "nenhum modelo ativo" in passo.motivo
    assert passo.certeza == "regra"


def test_proximo_passo_com_modelo_em_dia_pede_observacao_e_depois_fica_ambiguo(tmp_path):
    fw = projeto(tmp_path)
    fw.calcular_texto("moda-beleza")
    fw.calcular_titulos("moda-beleza")
    exp = fw.experimentar("moda-beleza", {"camadas": ["metadados"]})
    fw.promover("moda-beleza", exp.id)

    assert fw.proximo_passo("moda-beleza").acao == "observar_recentes"

    fw.observar_recentes("moda-beleza", dias_max=10_000)
    passo = fw.proximo_passo("moda-beleza")
    assert passo.acao == "manter"
    assert passo.certeza == "ambiguo"  # ganchos: custo, decide com o usuário
    assert "processar_ganchos" in passo.alternativas
