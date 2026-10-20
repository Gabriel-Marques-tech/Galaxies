from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from galaxies import modelagem as m


def _videos(dias_e_likes, canal="c1"):
    inicio = datetime(2026, 1, 1, tzinfo=UTC)
    return pd.DataFrame(
        {
            "video_id": [f"{canal}-{i}" for i in range(len(dias_e_likes))],
            "canal_id": canal,
            "publicado_em": [inicio + timedelta(days=d) for d, _ in dias_e_likes],
            "y": [likes for _, likes in dias_e_likes],
        }
    )


def test_historico_so_usa_videos_publicados_7_dias_antes():
    df = _videos([(0, 99), (1, 99), (10, 0), (12, 1_000_000)])

    h = m.historico(df).set_index("video_id")

    assert np.isnan(h.loc["c1-0", "hist_media_10"])  # nada antes
    assert np.isnan(h.loc["c1-1", "hist_media_10"])  # o anterior tem só 1 dia
    assert h.loc["c1-2", "hist_media_10"] == pytest.approx(np.log1p(99))  # dias 0 e 1
    # o vídeo do dia 10 tem só 2 dias antes do dia 12: não entra, nem o próprio
    assert h.loc["c1-3", "hist_media_10"] == pytest.approx(np.log1p(99))


def test_historico_mede_ritmo_de_postagem_e_tendencia():
    df = _videos([(d, 10 if d < 20 else 1000) for d in range(0, 40, 2)])

    h = m.historico(df).set_index("video_id")
    ultimo = h.loc["c1-19"]

    assert ultimo["hist_dias_desde_ultimo"] == pytest.approx(2)
    assert ultimo["hist_posts_7d"] == 3
    assert ultimo["hist_tendencia"] > 0  # os últimos foram melhores que a média longa


def test_canais_nao_se_misturam():
    df = pd.concat([_videos([(0, 5), (10, 5)], "a"), _videos([(0, 5000), (10, 5000)], "b")])

    h = m.historico(df).set_index("video_id")

    assert h.loc["a-1", "hist_media_10"] == pytest.approx(np.log1p(5))
    assert h.loc["b-1", "hist_media_10"] == pytest.approx(np.log1p(5000))
