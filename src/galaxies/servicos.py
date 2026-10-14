"""Camada de serviços: o único seam do núcleo. MCP e FastAPI só chamam isto."""

from pathlib import Path

from pydantic import ValidationError

from galaxies import armazenamento
from galaxies.config import ConfigProjeto, nome_valido
from galaxies.erros import ConfigInvalida, ProjetoJaExiste, ProjetoNaoEncontrado
from galaxies.portas import Dependencias
from galaxies.trace import Etapa, Run, executar, ler_trace, listar_runs


class Framework:
    def __init__(self, raiz: Path | str, dependencias: Dependencias | None = None):
        self.raiz = Path(raiz)
        self.dependencias = dependencias or Dependencias()

    def criar_projeto(self, config: ConfigProjeto | dict) -> ConfigProjeto:
        try:
            config = ConfigProjeto.model_validate(config)
        except ValidationError as erro:
            raise ConfigInvalida(str(erro)) from erro
        if armazenamento.caminho_do_banco(self.raiz, config.nome).exists():
            raise ProjetoJaExiste(config.nome)
        with (
            armazenamento.abrir(self.raiz, config.nome) as banco,
            executar(banco, "criar_projeto") as execucao,
            execucao.etapa("salvar_config", config.model_dump()),
        ):
            banco.execute(
                "INSERT INTO projeto VALUES (?, ?)", [config.nome, config.model_dump_json()]
            )
        return config

    def obter_projeto(self, nome: str) -> ConfigProjeto:
        with self._abrir_existente(nome) as banco:
            (config_json,) = banco.execute(
                "SELECT config FROM projeto WHERE nome = ?", [nome]
            ).fetchone()
        return ConfigProjeto.model_validate_json(config_json)

    def runs(self, projeto: str) -> list[Run]:
        with self._abrir_existente(projeto) as banco:
            return listar_runs(banco)

    def trace(self, projeto: str, run_id: str) -> list[Etapa]:
        with self._abrir_existente(projeto) as banco:
            return ler_trace(banco, run_id)

    # Serviços das próximas tasks. Assinaturas finais saem de cada uma.

    def definir_atributos(self, projeto: str, atributos: list[dict]):  # #5
        raise NotImplementedError("#5")

    def coletar(self, projeto: str):  # #3
        raise NotImplementedError("#3")

    def adicionar_canal(self, projeto: str, canal_id: str):  # #3
        raise NotImplementedError("#3")

    def treinar(self, projeto: str):  # #6
        raise NotImplementedError("#6")

    def status(self, projeto: str, job_id: str):  # #6
        raise NotImplementedError("#6")

    def avaliar(self, projeto: str):  # #6
        raise NotImplementedError("#6")

    def erros(self, projeto: str):  # #8
        raise NotImplementedError("#8")

    def reprocessar(self, projeto: str, video_ids: list[str]):  # #8
        raise NotImplementedError("#8")

    def analisar(self, projeto: str, video, canal_id: str):  # #7
        raise NotImplementedError("#7")

    def comparar(self, projeto: str, video_a, video_b):  # #10
        raise NotImplementedError("#10")

    def melhorar(self, projeto: str, video, variacoes: list[dict]):  # #11
        raise NotImplementedError("#11")

    def _abrir_existente(self, nome: str):
        if not nome_valido(nome) or not armazenamento.caminho_do_banco(self.raiz, nome).exists():
            raise ProjetoNaoEncontrado(nome)
        return armazenamento.abrir(self.raiz, nome)
