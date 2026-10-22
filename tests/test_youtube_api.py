import pytest

from galaxies.adaptadores.youtube_api import duracao_em_segundos


@pytest.mark.parametrize(
    ("iso", "segundos"),
    [("PT45S", 45), ("PT1M", 60), ("PT2M59S", 179), ("PT1H2M3S", 3723), ("P0D", 0)],
)
def test_duracao_iso8601(iso, segundos):
    assert duracao_em_segundos(iso) == segundos


def test_video_sem_duracao_e_descartado():
    """Estreia agendada ou live vem sem contentDetails.duration: pula o item, não o canal."""
    from galaxies.adaptadores.youtube_api import YouTubeAPI

    comum = {"snippet": {"channelId": "UC1", "title": "t", "publishedAt": "2025-01-01T00:00:00Z"}}
    itens = [
        {"id": "ok", **comum, "contentDetails": {"duration": "PT30S"}},
        {"id": "live", **comum, "contentDetails": {}},
    ]
    videos = YouTubeAPI._videos_de(itens)
    assert [v["id"] for v in videos] == ["ok"]
