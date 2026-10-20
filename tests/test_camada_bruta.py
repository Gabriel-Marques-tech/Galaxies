from datetime import date

import pytest

from galaxies import CotaEsgotada, Framework
from galaxies.portas import Dependencias
from tests.fakes import (
    DescritorFalso,
    EmbedderFalso,
    ExtratorFalso,
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


def montar(tmp_path, videos, extrator=None):
    deps = Dependencias(
        youtube=YouTubeFalso({"beleza1": videos}),
        extrator=extrator or ExtratorFalso(),
        descritor=DescritorFalso(),
        transcritor=TranscritorFalso(),
        embedder=EmbedderFalso(),
    )
    framework = Framework(raiz=tmp_path, dependencias=deps)
    framework.criar_projeto(CONFIG)
    framework.coletar("moda-beleza")
    return framework, deps


def test_camada_bruta_guarda_descricao_transcricao_e_embedding(tmp_path):
    v = video("beleza1")
    framework, _ = montar(tmp_path, [v])

    framework.processar_ganchos("moda-beleza")

    (bruta,) = framework.camada_bruta("moda-beleza")
    assert bruta.video_id == v["id"]
    assert bruta.descricao == "mulher mostra batom vermelho em close (3 frames)"
    assert bruta.transcricao == "gente, olha esse batom"
    assert bruta.embedding == pytest.approx([0.1, 0.2, 0.3])
    assert len(bruta.frames) == 3


def test_segunda_rodada_nao_chama_vlm_nem_whisper_de_novo(tmp_path):
    framework, deps = montar(tmp_path, [video("beleza1"), video("beleza1")])

    framework.processar_ganchos("moda-beleza")
    framework.processar_ganchos("moda-beleza")

    assert deps.descritor.chamadas == 2
    assert deps.transcritor.chamadas == 2


def test_falha_em_um_video_e_registrada_e_o_lote_segue(tmp_path):
    quebrado, bom = video("beleza1"), video("beleza1")
    framework, _ = montar(tmp_path, [quebrado, bom], ExtratorFalso(falhar_em={quebrado["id"]}))

    resumo = framework.processar_ganchos("moda-beleza")

    assert [b.video_id for b in framework.camada_bruta("moda-beleza")] == [bom["id"]]
    assert resumo.processados == 1
    (falha,) = framework.falhas("moda-beleza")
    assert falha.video_id == quebrado["id"]
    assert falha.etapa == "extrair_gancho"
    assert "download falhou" in falha.erro


def test_limite_por_canal_espalha_a_amostra_no_tempo(tmp_path):
    datas = [f"2026-0{m}-15T12:00:00Z" for m in range(1, 10)]  # jan..set
    framework, _ = montar(tmp_path, [video("beleza1", publicado_em=d) for d in datas])

    framework.processar_ganchos("moda-beleza", limite_por_canal=3)

    processados = {b.video_id for b in framework.camada_bruta("moda-beleza")}
    meses = sorted(
        v.publicado_em.month for v in framework.videos("moda-beleza") if v.id in processados
    )
    assert meses == [1, 5, 9]


def test_processa_so_os_canais_pedidos(tmp_path):
    deps = Dependencias(
        youtube=YouTubeFalso({"beleza1": [video("beleza1")], "moda1": [video("moda1")]}),
        extrator=ExtratorFalso(),
        descritor=DescritorFalso(),
        transcritor=TranscritorFalso(),
        embedder=EmbedderFalso(),
    )
    framework = Framework(raiz=tmp_path, dependencias=deps)
    framework.criar_projeto(
        {
            **CONFIG,
            "canais_semente": [
                {"ref": "@beleza1", "setor": "beleza"},
                {"ref": "@moda1", "setor": "moda"},
            ],
        }
    )
    framework.coletar("moda-beleza")

    framework.processar_ganchos("moda-beleza", canais=["moda1"])

    assert deps.extrator.extraidos == [
        v.id for v in framework.videos("moda-beleza") if v.canal_id == "moda1"
    ]


def test_cota_diaria_esgotada_para_o_lote_sem_marcar_falha(tmp_path):
    class DescritorSemCota(DescritorFalso):
        def descrever(self, frames):
            self.chamadas += 1
            if self.chamadas > 1:
                raise CotaEsgotada("Gemini: cota diária gratuita esgotada")
            return "descrição"

    framework, deps = montar(tmp_path, [video("beleza1") for _ in range(4)])
    deps.descritor = DescritorSemCota()

    resumo = framework.processar_ganchos("moda-beleza")

    assert resumo.processados == 1
    assert resumo.interrompido_por_cota
    assert framework.falhas("moda-beleza") == []
    assert deps.descritor.chamadas == 2  # parou na primeira recusa


def test_desde_restringe_a_janela_de_teste(tmp_path):
    datas = [f"2026-0{m}-15T12:00:00Z" for m in range(1, 10)]  # jan..set
    framework, _ = montar(tmp_path, [video("beleza1", publicado_em=d) for d in datas])

    framework.processar_ganchos("moda-beleza", limite_por_canal=2, desde=date(2026, 7, 1))

    processados = {b.video_id for b in framework.camada_bruta("moda-beleza")}
    meses = sorted(
        v.publicado_em.month for v in framework.videos("moda-beleza") if v.id in processados
    )
    assert meses == [7, 9]
