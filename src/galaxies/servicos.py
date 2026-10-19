"""Camada de serviços: o único seam do núcleo. MCP e FastAPI só chamam isto."""

from pathlib import Path

from pydantic import ValidationError

from galaxies import armazenamento, camada_bruta, coleta
from galaxies import atributos as atrib
from galaxies.config import CanalSemente, ConfigProjeto, nome_valido
from galaxies.erros import (
    ConfigInvalida,
    DependenciaAusente,
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

    def atributos(self, projeto: str) -> list[atrib.Atributo]:
        with self._abrir_existente(projeto) as banco:
            return atrib.ler_definicoes(banco)

    def definir_atributos(self, projeto: str, definicoes: list[dict]) -> list[atrib.Atributo]:
        """Substitui os atributos do projeto. Respostas de atributos inalterados são mantidas."""
        try:
            novos = [atrib.Atributo.model_validate(d) for d in definicoes]
            atrib.validar_lista(novos)
        except (ValidationError, ValueError) as erro:
            raise ConfigInvalida(str(erro)) from erro
        with self._abrir_existente(projeto) as banco:
            atrib.salvar_definicoes(banco, novos)
        return novos

    def calcular_atributos(self, projeto: str) -> camada_bruta.ResumoGanchos:
        """Pergunta ao Jev só o que falta: atributos novos ou alterados, por vídeo."""
        jev = self._exigir(self.dependencias.jev, "jev")
        resumo = camada_bruta.ResumoGanchos()
        with self._abrir_existente(projeto) as banco, executar(banco, "calcular_atributos") as ex:
            definicoes = atrib.ler_definicoes(banco)
            videos = {v.id: v for v in coleta.listar_videos(banco)}
            for bruta in camada_bruta.listar(banco):
                faltam = atrib.faltantes(banco, bruta.video_id, definicoes)
                if not faltam:
                    continue
                video = videos[bruta.video_id]
                estado = atrib.estado_do_video(video.titulo, video.descricao, video.tags, bruta)
                perguntas = {a.id: a.como_pergunta_jev() for a in faltam}
                ex.ultima_falha = None
                try:
                    with ex.etapa(
                        "perguntar_jev", {"video_id": video.id, "perguntas": list(perguntas)}
                    ) as registro:
                        respostas = jev.perguntar(estado, perguntas)
                        registro["saida"] = respostas
                    atrib.salvar_respostas(banco, video.id, faltam, respostas)
                    resumo.processados += 1
                except Exception as e:
                    etapa, erro = ex.ultima_falha or ("salvar", f"{type(e).__name__}: {e}")
                    camada_bruta.registrar_falha(
                        banco,
                        camada_bruta.Falha(
                            video_id=video.id, etapa=etapa, erro=erro, run_id=ex.run_id
                        ),
                    )
                    resumo.falhas += 1
        return resumo

    def features_de_atributos(self, projeto: str) -> list[dict]:
        with self._abrir_existente(projeto) as banco:
            return atrib.features(banco, atrib.ler_definicoes(banco))

    def coletar(self, projeto: str, so_faltantes: bool = False) -> coleta.ResumoColeta:
        """Coleta os canais-semente. so_faltantes retoma uma coleta interrompida."""
        config = self.obter_projeto(projeto)
        sementes = config.canais_semente
        if so_faltantes:
            with self._abrir_existente(projeto) as banco:
                feitos = coleta.ja_coletados(banco)
            sementes = [s for s in sementes if s.ref not in feitos]
        return self._coletar(projeto, sementes, "coletar", config.coletar_desde)

    def adicionar_canal(self, projeto: str, ref: str, setor: str) -> coleta.ResumoColeta:
        config = self.obter_projeto(projeto)
        try:
            semente = CanalSemente(ref=ref, setor=setor)
        except ValidationError as erro:
            raise ConfigInvalida(str(erro)) from erro
        resumo = self._coletar(projeto, [semente], "adicionar_canal", config.coletar_desde)
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

    def _coletar(self, projeto: str, sementes, operacao: str, desde=None) -> coleta.ResumoColeta:
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        with self._abrir_existente(projeto) as banco, executar(banco, operacao) as execucao:
            resumo = coleta.ResumoColeta()
            antes = coleta.contar_videos(banco)
            try:
                for semente in sementes:
                    try:
                        with execucao.etapa("coletar_canal", semente.model_dump()):
                            coleta.coletar_canal(banco, youtube, semente, desde)
                    except Exception:  # rede, API ou domínio: falha do canal, não da coleta
                        resumo.falhas.append(semente.ref)
            finally:
                coleta.registrar_cota(banco, execucao.run_id, youtube.unidades)
            resumo.videos_novos = coleta.contar_videos(banco) - antes
        return resumo

    def cota(self, projeto: str) -> int:
        """Unidades da YouTube API já gastas por este projeto."""
        with self._abrir_existente(projeto) as banco:
            return coleta.cota_total(banco)

    def processar_ganchos(
        self, projeto: str, limite_por_canal: int | None = None
    ) -> camada_bruta.ResumoGanchos:
        """Calcula a camada bruta dos vídeos que ainda não a têm. limite_por_canal restringe a
        um subconjunto espaçado no tempo (a camada é cara)."""
        deps = self.dependencias
        for nome in ("extrator", "descritor", "transcritor", "embedder"):
            self._exigir(getattr(deps, nome), nome)
        resumo = camada_bruta.ResumoGanchos()
        with self._abrir_existente(projeto) as banco, executar(banco, "processar_ganchos") as ex:
            for video_id in camada_bruta.pendentes(banco, limite_por_canal):
                pasta = self._pasta_do_projeto(projeto) / "ganchos" / video_id
                ex.ultima_falha = None
                try:
                    camada_bruta.processar(banco, deps, ex, video_id, video_id, pasta)
                    resumo.processados += 1
                except Exception as e:
                    etapa, erro = ex.ultima_falha or ("salvar", f"{type(e).__name__}: {e}")
                    camada_bruta.registrar_falha(
                        banco,
                        camada_bruta.Falha(
                            video_id=video_id, etapa=etapa, erro=erro, run_id=ex.run_id
                        ),
                    )
                    resumo.falhas += 1
        return resumo

    def falhas(self, projeto: str) -> list[camada_bruta.Falha]:
        with self._abrir_existente(projeto) as banco:
            return camada_bruta.listar_falhas(banco)

    def camada_bruta(self, projeto: str) -> list[camada_bruta.CamadaBruta]:
        with self._abrir_existente(projeto) as banco:
            return camada_bruta.listar(banco)

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

    def _pasta_do_projeto(self, nome: str) -> Path:
        return armazenamento.caminho_do_banco(self.raiz, nome).parent
