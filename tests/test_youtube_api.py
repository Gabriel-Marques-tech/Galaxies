import pytest

from galaxies.adaptadores.youtube_api import duracao_em_segundos


@pytest.mark.parametrize(
    ("iso", "segundos"),
    [("PT45S", 45), ("PT1M", 60), ("PT2M59S", 179), ("PT1H2M3S", 3723), ("P0D", 0)],
)
def test_duracao_iso8601(iso, segundos):
    assert duracao_em_segundos(iso) == segundos
