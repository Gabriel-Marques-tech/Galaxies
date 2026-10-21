from datetime import UTC, datetime, timedelta

import numpy as np

from galaxies import crescimento
from galaxies.crescimento import Curva, FaixaDaCurva
from tests.test_experimentos import BASE, VIDEO, projeto

AGORA = datetime(2026, 10, 21, tzinfo=UTC)


def dobrar_contagens():
    for videos in BASE.values():
        for v in videos:
            v["likes"] *= 2
            v["views"] *= 2


def test_observar_recentes_semeia_a_coleta_e_acrescenta_uma_observacao(tmp_path):
    framework = projeto(tmp_path)

    resumo = framework.observar_recentes("moda-beleza", dias_max=10_000, agora=AGORA)

    assert resumo.candidatos == resumo.observados > 0
    assert resumo.sem_dados == 0
    assert resumo.unidades == -(-resumo.candidatos // 50)
    with framework._abrir_existente("moda-beleza") as banco:
        por_video = banco.execute(
            "SELECT count(*) FROM (SELECT video_id FROM observacoes GROUP BY 1 HAVING count(*) = 2)"
        ).fetchone()[0]
    assert por_video == resumo.observados


def test_curva_mede_a_inclinacao_por_faixa_de_idade(tmp_path):
    framework = projeto(tmp_path)
    framework.observar_recentes("moda-beleza", dias_max=10_000, agora=AGORA)
    dobrar_contagens()  # entre as observações, tudo dobrou
    try:
        framework.observar_recentes(
            "moda-beleza", dias_max=10_000, agora=AGORA + timedelta(days=30)
        )
    finally:
        for videos in BASE.values():
            for v in videos:
                v["likes"] //= 2
                v["views"] //= 2

    curva = framework.crescimento("moda-beleza")

    assert curva.alvo == "likes"
    assert curva.videos > 0
    assert curva.intervalo_mediano_dias == 30
    assert curva.faixas, "faixas com 20+ vídeos"
    for f in curva.faixas:
        assert f.inclinacao > 0
    # com a curva, voltar no tempo encolhe a contagem e avançar aumenta
    f = curva.faixas[0]
    assert curva.fator(f.ate_dias, f.de_dias) < 1 < curva.fator(f.de_dias, f.ate_dias)
    assert np.isclose(curva.fator(f.de_dias, f.ate_dias) * curva.fator(f.ate_dias, f.de_dias), 1)


def test_sem_reobservacao_a_curva_e_vazia_e_nao_muda_nada(tmp_path):
    framework = projeto(tmp_path)
    with framework._abrir_existente("moda-beleza") as banco:
        assert crescimento.curva(banco, "likes").faixas == []
        assert crescimento.idade_minima_vista(banco) > 0
    vazia = Curva(alvo="likes", faixas=[], videos=0, intervalo_mediano_dias=0)
    assert vazia.fator(1, 30) == 1.0


def test_fator_integra_so_as_faixas_cobertas():
    curva = Curva(
        alvo="likes",
        faixas=[FaixaDaCurva(de_dias=5, ate_dias=10, n=30, inclinacao=1.0)],
        videos=30,
        intervalo_mediano_dias=2,
    )
    assert np.isclose(curva.fator(5, 10), 2.0)  # log(10/5) × 1.0 → e^ln2
    assert np.isclose(curva.fator(1, 5), 1.0)  # fora da faixa: não muda
    assert np.isclose(curva.fator(1, 20), 2.0)


def test_timeline_abaixo_da_idade_minima_recua_pela_curva(tmp_path):
    framework = projeto(tmp_path)
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    framework.promover("moda-beleza", exp.id)
    sem_curva = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    # 25 vídeos observados aos 2 e aos 8 dias, dobrando no caminho: faixa 2–5 dias
    with framework._abrir_existente("moda-beleza") as banco:
        ids = [v for (v,) in banco.execute("SELECT id FROM videos LIMIT 25").fetchall()]
        for i, v in enumerate(ids):
            banco.execute(
                "INSERT INTO observacoes VALUES (?, ?, 2.0, 100, 1000), (?, ?, 8.0, 200, 2000)",
                [v, AGORA + timedelta(minutes=i), v, AGORA + timedelta(days=6, minutes=i)],
            )
    curva = framework.crescimento("moda-beleza")
    assert [(f.de_dias, f.ate_dias) for f in curva.faixas] == [(2.0, 5.0)]
    assert np.isclose(curva.faixas[0].inclinacao, np.log(201 / 101) / np.log(4))

    com_curva = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    assert com_curva.timeline[0].q50 < sem_curva.timeline[0].q50  # 1 dia recua
    assert com_curva.timeline[1].q50 < sem_curva.timeline[1].q50  # 3 dias recua
    assert com_curva.timeline[-1].q50 == sem_curva.timeline[-1].q50  # 30 dias: idade vista
    assert com_curva.timeline[-1].q50 >= com_curva.timeline[0].q50


def test_timeline_traz_faixa_provavel_dentro_da_quase_certa(tmp_path):
    framework = projeto(tmp_path)
    exp = framework.experimentar("moda-beleza", {"camadas": ["metadados"]})
    framework.promover("moda-beleza", exp.id)

    a = framework.analisar("moda-beleza", VIDEO, canal_id="canal1")

    for p in a.timeline:
        assert p.q10 <= p.q25 <= p.q50 <= p.q75 <= p.q90
        assert p.q25 > p.q10 or p.q10 == p.q50  # faixa provável é mais estreita de verdade
    assert exp.resultado.cobertura_50 <= exp.resultado.cobertura_80
