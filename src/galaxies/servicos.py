"""Camada de serviços: o único seam do núcleo. MCP e FastAPI só chamam isto."""

from pathlib import Path

from pydantic import ValidationError

from galaxies import armazenamento, coleta
from galaxies.config import CanalSemente, ConfigProjeto, nome_valido
from galaxies.erros import (
    ConfigInvalida,
    DependenciaAusente,
    ErroGalaxies,
    ProjetoJaExiste,
    ProjetoNaoEncontrado,
)
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

    def coletar(self, projeto: str) -> coleta.ResumoColeta:
        config = self.obter_projeto(projeto)
        return self._coletar(projeto, config.canais_semente, "coletar")

    def adicionar_canal(self, projeto: str, ref: str, setor: str) -> coleta.ResumoColeta:
        config = self.obter_projeto(projeto)
        try:
            semente = CanalSemente(ref=ref, setor=setor)
        except ValidationError as erro:
            raise ConfigInvalida(str(erro)) from erro
        resumo = self._coletar(projeto, [semente], "adicionar_canal")
        if not resumo.falhas and ref not in [c.ref for c in config.canais_semente]:
            config.canais_semente.append(semente)
            with self._abrir_existente(projeto) as banco:
                banco.execute(
                    "UPDATE projeto SET config = ? WHERE nome = ?",
                    [config.model_dump_json(), projeto],
                )
        return resumo

    def descobrir_canais(self, projeto: str, consulta: str, teto_unidades: int = 1000) -> list[str]:
        """Busca ids de canais por texto. Cara (100 unidades por página): para no teto."""
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        custo = coleta.CUSTO_EM_UNIDADES["buscar_canais"]
        encontrados: list[str] = []
        with self._abrir_existente(projeto) as banco, executar(banco, "descobrir") as execucao:
            token = None
            try:
                while youtube.unidades + custo <= teto_unidades:
                    with execucao.etapa("buscar_canais", {"consulta": consulta, "token": token}):
                        ids, token = youtube.buscar_canais(consulta, token)
                    encontrados += [i for i in ids if i not in encontrados]
                    if token is None:
                        break
            finally:
                coleta.registrar_cota(banco, execucao.run_id, youtube.unidades)
        return encontrados

    def _coletar(self, projeto: str, sementes, operacao: str) -> coleta.ResumoColeta:
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        with self._abrir_existente(projeto) as banco, executar(banco, operacao) as execucao:
            resumo = coleta.ResumoColeta()
            antes = coleta.contar_videos(banco)
            try:
                for semente in sementes:
                    try:
                        with execucao.etapa("coletar_canal", semente.model_dump()):
                            coleta.coletar_canal(banco, youtube, semente)
                    except ErroGalaxies:
                        resumo.falhas.append(semente.ref)
            finally:
                coleta.registrar_cota(banco, execucao.run_id, youtube.unidades)
            resumo.videos_novos = coleta.contar_videos(banco) - antes
        return resumo

    def cota(self, projeto: str) -> int:
        """Unidades da YouTube API já gastas por este projeto."""
        with self._abrir_existente(projeto) as banco:
            return coleta.cota_total(banco)

    def videos(self, projeto: str) -> list[coleta.Video]:
        with self._abrir_existente(projeto) as banco:
            return coleta.listar_videos(banco)

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

    @staticmethod
    def _exigir(dependencia, nome: str):
        if dependencia is None:
            raise DependenciaAusente(nome)
        return dependencia
