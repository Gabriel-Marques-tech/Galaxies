"""Camada de serviços: o único seam do núcleo. MCP e FastAPI só chamam isto."""

from datetime import date
from pathlib import Path

from pydantic import ValidationError

from galaxies import armazenamento, camada_bruta, coleta, erros, modelagem, treino
from galaxies import atributos as atrib
from galaxies.analise import Analise, GanchoAnalisado, VideoNovo, linha_do_video, prever
from galaxies.config import CanalSemente, ConfigProjeto, nome_valido
from galaxies.erros import (
    CanalForaDaBase,
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
        self,
        projeto: str,
        limite_por_canal: int | None = None,
        canais: list[str] | None = None,
        desde: date | None = None,
    ) -> camada_bruta.ResumoGanchos:
        """Calcula a camada bruta dos vídeos que ainda não a têm. limite_por_canal restringe a
        um subconjunto espaçado no tempo (a camada é cara)."""
        deps = self.dependencias
        for nome in ("extrator", "descritor", "transcritor", "embedder"):
            self._exigir(getattr(deps, nome), nome)
        with self._abrir_existente(projeto) as banco, executar(banco, "processar_ganchos") as ex:
            ids = camada_bruta.pendentes(banco, limite_por_canal, canais, desde)
            return self._processar_lista(projeto, banco, ex, ids)

    def _processar_lista(self, projeto, banco, ex, video_ids) -> camada_bruta.ResumoGanchos:
        resumo = camada_bruta.ResumoGanchos()
        for video_id in video_ids:
            pasta = self._pasta_do_projeto(projeto) / "ganchos" / video_id
            ex.ultima_falha = None
            try:
                camada_bruta.processar(banco, self.dependencias, ex, video_id, video_id, pasta)
                resumo.processados += 1
            except erros.CotaEsgotada:
                resumo.interrompido_por_cota = True  # retoma amanhã de onde parou
                break
            except Exception as e:
                etapa, erro = ex.ultima_falha or ("salvar", f"{type(e).__name__}: {e}")
                camada_bruta.registrar_falha(
                    banco,
                    camada_bruta.Falha(video_id=video_id, etapa=etapa, erro=erro, run_id=ex.run_id),
                )
                resumo.falhas += 1
        return resumo

    def reprocessar(
        self, projeto: str, video_ids: list[str] | None = None
    ) -> camada_bruta.ResumoGanchos:
        """Limpa as falhas (todas, ou só as dos vídeos pedidos) e refaz esses vídeos.
        Vídeos que já têm camada bruta só voltam a perguntar os atributos."""
        with self._abrir_existente(projeto) as banco, executar(banco, "reprocessar") as ex:
            falhos = {f.video_id for f in camada_bruta.listar_falhas(banco)}
            alvo = (
                [v for v in video_ids if v in falhos] if video_ids is not None else sorted(falhos)
            )
            camada_bruta.apagar_falhas(banco, alvo)
            feitos = {b.video_id for b in camada_bruta.listar(banco)}
            sem_bruta = [v for v in alvo if v not in feitos]
            if sem_bruta:
                for nome in ("extrator", "descritor", "transcritor", "embedder"):
                    self._exigir(getattr(self.dependencias, nome), nome)
            resumo = (
                self._processar_lista(projeto, banco, ex, sem_bruta)
                if sem_bruta
                else camada_bruta.ResumoGanchos()
            )
        if self.dependencias.jev is not None and len(sem_bruta) < len(alvo):
            self.calcular_atributos(projeto)
        return resumo

    def excluir(self, projeto: str, video_ids: list[str] = (), canais: list[str] = ()):
        """Tira vídeos ou canais inteiros do processamento e dos próximos treinos."""
        with self._abrir_existente(projeto) as banco:
            agora = modelagem.agora()
            banco.executemany(
                "INSERT OR REPLACE INTO excluidos VALUES (?, ?, ?)",
                [[v, "video", agora] for v in video_ids] + [[c, "canal", agora] for c in canais],
            )

    def erros(self, projeto: str, alvo: str | None = None) -> modelagem.RelatorioErros:
        """Falhas do pipeline por etapa + onde o último treino mais erra."""
        alvo = alvo or self.obter_projeto(projeto).alvo
        with self._abrir_existente(projeto) as banco:
            falhas = camada_bruta.listar_falhas(banco)
            avaliacao = modelagem.ultima_avaliacao(banco, alvo)
        por_etapa: dict[str, int] = {}
        for f in falhas:
            por_etapa[f.etapa] = por_etapa.get(f.etapa, 0) + 1
        return modelagem.RelatorioErros(
            falhas_por_etapa=por_etapa,
            piores=avaliacao.piores if avaliacao else [],
            segmentos=avaliacao.segmentos if avaliacao else {},
        )

    def falhas(self, projeto: str) -> list[camada_bruta.Falha]:
        with self._abrir_existente(projeto) as banco:
            return camada_bruta.listar_falhas(banco)

    def camada_bruta(self, projeto: str) -> list[camada_bruta.CamadaBruta]:
        with self._abrir_existente(projeto) as banco:
            return camada_bruta.listar(banco)

    def videos(self, projeto: str) -> list[coleta.Video]:
        with self._abrir_existente(projeto) as banco:
            return coleta.listar_videos(banco)

    def treinar(self, projeto: str, alvo: str | None = None) -> modelagem.Avaliacao:
        """Avalia por camadas no split temporal fixo e salva o modelo final do alvo."""
        config = self.obter_projeto(projeto)
        alvo = alvo or config.alvo
        if alvo not in ("likes", "views"):
            raise ConfigInvalida(f"alvo '{alvo}' inválido: use likes ou views")
        with self._abrir_existente(projeto) as banco, executar(banco, "treinar") as ex:
            avaliacao = treino.treinar(
                banco,
                alvo,
                atrib.ler_definicoes(banco),
                self._pasta_do_projeto(projeto) / "modelos",
                ex,
            )
            modelagem.salvar_avaliacao(banco, ex.run_id, avaliacao)
        return avaliacao

    def avaliar(self, projeto: str, alvo: str | None = None) -> modelagem.Avaliacao:
        """Última avaliação do alvo. Treine antes."""
        alvo = alvo or self.obter_projeto(projeto).alvo
        with self._abrir_existente(projeto) as banco:
            avaliacao = modelagem.ultima_avaliacao(banco, alvo)
        if avaliacao is None:
            raise erros.ErroGalaxies(f"Nenhum treino para o alvo '{alvo}'. Rode treinar primeiro.")
        return avaliacao

    def analisar(self, projeto: str, video: VideoNovo | dict, canal_id: str) -> Analise:
        """Previsão de um Short ainda não publicado, para um canal que já está na base."""
        config = self.obter_projeto(projeto)
        video = VideoNovo.model_validate(video)
        carregado = modelagem.carregar_modelos(
            self._pasta_do_projeto(projeto) / "modelos" / config.alvo
        )
        if carregado is None:
            raise erros.ErroGalaxies(f"Nenhum modelo para '{config.alvo}'. Rode treinar primeiro.")
        modelos, meta = carregado
        if canal_id not in {c["canal_id"] for c in meta["canais"]}:
            raise CanalForaDaBase(canal_id)
        with self._abrir_existente(projeto) as banco, executar(banco, "analisar") as ex:
            setor, inscritos = banco.execute(
                "SELECT setor, inscritos FROM canais WHERE id = ?", [canal_id]
            ).fetchone()
            gancho = atributos = None
            if video.fonte:
                bruta = camada_bruta.processar(
                    banco,
                    self.dependencias,
                    ex,
                    "novo",
                    video.fonte,
                    self._pasta_do_projeto(projeto) / "analises" / ex.run_id,
                    salvar=False,
                )
                gancho = GanchoAnalisado(descricao=bruta.descricao, transcricao=bruta.transcricao)
                if self.dependencias.jev is not None:
                    definicoes = atrib.ler_definicoes(banco)
                    estado = atrib.estado_do_video(video.titulo, video.descricao, video.tags, bruta)
                    with ex.etapa("perguntar_atributos", {"estado": estado}) as registro:
                        atributos = self.dependencias.jev.perguntar(
                            estado, {a.id: a.como_pergunta_jev() for a in definicoes}
                        )
                        registro["saida"] = atributos
            linha = linha_do_video(video, {"canal_id": canal_id}, setor, inscritos)
            with ex.etapa("prever", video.model_dump(mode="json")) as registro:
                resultado = prever(modelos, meta, linha, config.limite_viral)
                registro["saida"] = {
                    "timeline": [p.model_dump() for p in resultado["timeline"]],
                    "p_viral": resultado["p_viral"],
                }
            with ex.etapa("explicar") as registro:
                registro["saida"] = [f.model_dump() for f in resultado["fatores"]]
            return Analise(
                run_id=ex.run_id,
                canal_id=canal_id,
                alvo=config.alvo,
                gancho=gancho,
                atributos=atributos,
                **resultado,
            )

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
