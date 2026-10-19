from galaxies import Framework
from galaxies.portas import Dependencias
from tests.fakes import YouTubeFalso, video

CONFIG = {
    "nome": "moda-beleza",
    "setores": ["moda", "beleza"],
    "canais_semente": [
        {"ref": "@moda1", "setor": "moda"},
        {"ref": "@beleza1", "setor": "beleza"},
    ],
    "alvo": "likes",
}


def framework_com(tmp_path, youtube):
    framework = Framework(raiz=tmp_path, dependencias=Dependencias(youtube=youtube))
    framework.criar_projeto(CONFIG)
    return framework


def test_coleta_guarda_so_shorts_dos_canais_semente(tmp_path):
    short = video("moda1", duracao_s=40)
    longo = video("moda1", duracao_s=600)
    horizontal = video("beleza1", duracao_s=30, vertical=False)
    short_beleza = video("beleza1", duracao_s=170)
    youtube = YouTubeFalso({"moda1": [short, longo], "beleza1": [horizontal, short_beleza]})
    framework = framework_com(tmp_path, youtube)

    framework.coletar("moda-beleza")

    ids = {v.id for v in framework.videos("moda-beleza")}
    assert ids == {short["id"], short_beleza["id"]}


def test_coleta_pagina_todos_os_uploads_e_registra_a_cota(tmp_path):
    youtube = YouTubeFalso(
        {
            "moda1": [video("moda1") for _ in range(120)],
            "beleza1": [video("beleza1") for _ in range(10)],
        }
    )
    framework = framework_com(tmp_path, youtube)

    framework.coletar("moda-beleza")

    assert len(framework.videos("moda-beleza")) == 130
    # moda1: 1 canal + 3 páginas + 3 lotes de vídeos; beleza1: 1 + 1 + 1.
    assert framework.cota("moda-beleza") == 10


def test_canal_inexistente_vira_falha_e_os_outros_seguem(tmp_path):
    youtube = YouTubeFalso({"beleza1": [video("beleza1")]})
    framework = framework_com(tmp_path, youtube)

    resumo = framework.coletar("moda-beleza")

    assert resumo.falhas == ["@moda1"]
    assert resumo.videos_novos == 1
    (run,) = [r for r in framework.runs("moda-beleza") if r.operacao == "coletar"]
    etapas = framework.trace("moda-beleza", run.id)
    assert [e.erro is not None for e in etapas] == [True, False]


def test_adicionar_canal_coleta_so_ele_e_o_mantem_no_projeto(tmp_path):
    youtube = YouTubeFalso(
        {"moda1": [video("moda1")], "beleza1": [video("beleza1")], "novo": [video("novo")]}
    )
    framework = framework_com(tmp_path, youtube)

    resumo = framework.adicionar_canal("moda-beleza", "@novo", setor="moda")

    assert resumo.videos_novos == 1
    assert {v.canal_id for v in framework.videos("moda-beleza")} == {"novo"}
    assert "@novo" in [c.ref for c in framework.obter_projeto("moda-beleza").canais_semente]


def test_descoberta_para_no_teto_de_cota(tmp_path):
    class BuscaSemFim(YouTubeFalso):
        def buscar_canais(self, consulta, token):
            self.chamadas.append("buscar_canais")
            n = int(token or 0)
            return [f"UC{'x' * 21}{n}"], str(n + 1)

    youtube = BuscaSemFim({})
    framework = framework_com(tmp_path, youtube)

    encontrados = framework.descobrir_canais("moda-beleza", "maquiagem", teto_unidades=250)

    assert youtube.chamadas.count("buscar_canais") == 2
    assert len(encontrados) == 2
    assert framework.cota("moda-beleza") == 200


def test_coleta_para_de_paginar_ao_chegar_na_data_de_corte(tmp_path):
    novos = [video("moda1", publicado_em="2026-06-01T00:00:00Z") for _ in range(60)]
    antigos = [video("moda1", publicado_em="2023-01-01T00:00:00Z") for _ in range(200)]
    youtube = YouTubeFalso({"moda1": novos + antigos, "beleza1": []})
    framework = Framework(raiz=tmp_path, dependencias=Dependencias(youtube=youtube))
    framework.criar_projeto({**CONFIG, "coletar_desde": "2025-01-01"})

    framework.coletar("moda-beleza")

    assert len(framework.videos("moda-beleza")) == 60
    # 2 páginas bastam para cruzar o corte; as outras 4 não são pedidas.
    assert youtube.chamadas.count("pagina_de_uploads") == 2 + 1  # +1 do beleza1


def test_erro_de_rede_num_canal_nao_derruba_a_coleta(tmp_path):
    class RedeInstavel(YouTubeFalso):
        def pagina_de_uploads(self, playlist_id, token):
            if playlist_id == "UUmoda1":
                raise TimeoutError("read timed out")
            return super().pagina_de_uploads(playlist_id, token)

    youtube = RedeInstavel({"moda1": [video("moda1")], "beleza1": [video("beleza1")]})
    framework = framework_com(tmp_path, youtube)

    resumo = framework.coletar("moda-beleza")

    assert resumo.falhas == ["@moda1"]
    assert {v.canal_id for v in framework.videos("moda-beleza")} == {"beleza1"}


def test_retomar_coleta_pula_canais_ja_coletados(tmp_path):
    youtube = YouTubeFalso({"moda1": [video("moda1")], "beleza1": [video("beleza1")]})
    framework = framework_com(tmp_path, youtube)
    framework.adicionar_canal("moda-beleza", "@moda1", setor="moda")
    youtube.chamadas.clear()

    framework.coletar("moda-beleza", so_faltantes=True)

    assert youtube.chamadas.count("canal") == 1  # só beleza1
    assert len(framework.videos("moda-beleza")) == 2
