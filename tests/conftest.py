import pytest

from galaxies import otimizacao


@pytest.fixture(autouse=True)
def validacao_pequena_nos_fakes(monkeypatch):
    """As bases falsas têm poucas linhas; o mínimo de produção (300) travaria toda busca."""
    monkeypatch.setattr(otimizacao, "MIN_VALIDACAO", 10)
