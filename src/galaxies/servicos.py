"""Camada de serviços: o único seam do núcleo. MCP e FastAPI só chamam isto."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError

from galaxies import (
    acompanhamento,
    armazenamento,
    camada_bruta,
    coleta,
    crescimento,
    erros,
    experimentos,
    humano,
    modelagem,
    otimizacao,
    treino,
)
from galaxies import atributos as atrib
from galaxies import relatorio as relatorio_md
from galaxies.analise import (
    Analise,
    Comparacao,
    GanchoAnalisado,
    VideoNovo,
    linha_do_video,
    prever,
)
from galaxies.config import CanalSemente, ConfigProjeto, nome_valido
from galaxies.erros import (
    CanalForaDaBase,
    ConfigInvalida,
    DependenciaAusente,
    ProjetoJaExiste,
    ProjetoNaoEncontrado,
)
from galaxies.experimentos import Ciclo, Experimento, Receita
from galaxies.portas import Dependencias, identificar
from galaxies.trace import Etapa, Run, executar, ler_andamento, ler_trace, listar_runs

LOTE_TITULOS = 200  # vídeos por etapa do trace em calcular_titulos
LIMIAR_NOVOS_ABSOLUTO = 100  # vídeos novos para a rotina reotimizar
LIMIAR_NOVOS_FRACAO = 0.02  # ou 2% da base, o que for maior


class ProximoPasso(BaseModel):
    """Roadmap do projeto deduzido do estado: o que o agente deve chamar agora e por quê."""

    acao: str  # nome da tool (ou "aguardar_humano" / "manter")
    motivo: str
    certeza: Literal["regra", "ambiguo"]  # ambiguo = decisão de custo/escopo: envolva o usuário
    alternativas: list[str] = []
    estado: dict = {}


class Rotina(BaseModel):
    observados: int
    acompanhamentos_atualizados: int
    videos_novos: int
    unidades: int  # cota do YouTube gasta na reobservação
    texto_calculado: int = 0
    reotimizou: bool = False
    experimento: str | None = None
    promovido: str | None = None
    motivo: str | None = None


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

    def listar_projetos(self) -> list[str]:
        pasta = self.raiz / "projetos"
        if not pasta.exists():
            return []
        return sorted(p.name for p in pasta.iterdir() if (p / "galaxies.duckdb").exists())

    def obter_projeto(self, nome: str) -> ConfigProjeto:
        with self._abrir_existente(nome) as banco:
            (config_json,) = banco.execute(
                "SELECT config FROM projeto WHERE nome = ?", [nome]
            ).fetchone()
        return ConfigProjeto.model_validate_json(config_json)

    def definir_modo(self, projeto: str, modo: str) -> ConfigProjeto:
        """automatico ou cientista. Decisão do humano (UI); o agente não troca o modo."""
        config = self.obter_projeto(projeto)
        try:
            config = ConfigProjeto.model_validate({**config.model_dump(), "modo": modo})
        except ValidationError as erro:
            raise ConfigInvalida(str(erro)) from erro
        with self._abrir_existente(projeto) as banco:
            banco.execute(
                "UPDATE projeto SET config = ? WHERE nome = ?", [config.model_dump_json(), projeto]
            )
        return config

    def canais(self, projeto: str) -> list[dict]:
        """Canais da base, com quantos Shorts e quantos ganchos processados cada um tem."""
        with self._abrir_existente(projeto) as banco:
            linhas = banco.execute(
                """
                SELECT c.id, c.titulo, c.handle, c.setor, c.inscritos,
                       count(v.id) AS videos, count(b.video_id) AS ganchos
                FROM canais c
                LEFT JOIN videos v ON v.canal_id = c.id
                LEFT JOIN camada_bruta b ON b.video_id = v.id
                WHERE c.id NOT IN (SELECT id FROM excluidos WHERE tipo = 'canal')
                GROUP BY ALL ORDER BY c.inscritos DESC NULLS LAST
                """
            ).fetchall()
        campos = ("id", "titulo", "handle", "setor", "inscritos", "videos", "ganchos")
        return [dict(zip(campos, linha, strict=True)) for linha in linhas]

    def resumo(self, projeto: str) -> dict:
        """Números do projeto para a visão geral."""
        with self._abrir_existente(projeto) as banco:
            contar = lambda sql: banco.execute(sql).fetchone()[0]  # noqa: E731
            por_extrator = dict(
                banco.execute(
                    "SELECT extrator, count(DISTINCT video_id) FROM respostas GROUP BY 1"
                ).fetchall()
            )
            return {
                "canais": contar("SELECT count(*) FROM canais"),
                "videos": contar("SELECT count(*) FROM videos"),
                "ganchos": contar("SELECT count(*) FROM camada_bruta"),
                "falhas": contar("SELECT count(*) FROM falhas"),
                "excluidos": contar("SELECT count(*) FROM excluidos"),
                "atributos_por_extrator": por_extrator,
                "experimentos": contar("SELECT count(*) FROM experimentos"),
                "runs": contar("SELECT count(*) FROM runs"),
                "revisoes": contar("SELECT count(*) FROM revisoes"),
                "cota_youtube": contar("SELECT coalesce(sum(unidades), 0) FROM cota"),
            }

    def runs(self, projeto: str) -> list[Run]:
        with self._abrir_existente(projeto) as banco:
            return listar_runs(banco)

    def trace(self, projeto: str, run_id: str) -> list[Etapa]:
        with self._abrir_existente(projeto) as banco:
            return ler_trace(banco, run_id)

    def andamento(self, projeto: str) -> dict | None:
        """O run em execução agora (de qualquer processo: MCP, CLI), sem abrir o banco."""
        self.obter_projeto(projeto)
        return ler_andamento(self._pasta_do_projeto(projeto))

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
        extrator = identificar(jev)
        resumo = camada_bruta.ResumoGanchos()
        with self._abrir_existente(projeto) as banco, executar(banco, "calcular_atributos") as ex:
            definicoes = atrib.ler_definicoes(banco)
            videos = {v.id: v for v in coleta.listar_videos(banco)}
            for bruta in camada_bruta.listar(banco):
                faltam = atrib.faltantes(banco, bruta.video_id, definicoes, extrator)
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
                    atrib.salvar_respostas(banco, video.id, faltam, respostas, extrator)
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

    def calcular_titulos(self, projeto: str, limite: int | None = None) -> dict:
        """Extrator rápido (Laya, local) responde as perguntas de título para todos os vídeos
        que ainda não têm: é a camada "titulo", disponível para a base inteira."""
        rapido = self._exigir(self.dependencias.rapido, "rapido")
        extrator = identificar(rapido)
        definicoes = list(atrib.DE_TITULO)
        perguntas = {a.id: a.como_pergunta_jev() for a in definicoes}
        feitos = falhas = 0
        with self._abrir_existente(projeto) as banco, executar(banco, "calcular_titulos") as ex:
            pendentes = atrib.videos_sem_titulo(banco, extrator)
            if limite is not None:
                pendentes = pendentes[:limite]
            for inicio in range(0, len(pendentes), LOTE_TITULOS):
                lote = pendentes[inicio : inicio + LOTE_TITULOS]
                with ex.etapa("perguntar_titulos", {"n": len(lote), "feitos": feitos}) as reg:
                    for video_id, titulo, descricao in lote:
                        try:
                            respostas = rapido.perguntar(
                                atrib.estado_do_titulo(titulo, descricao), perguntas
                            )
                            atrib.salvar_respostas(banco, video_id, definicoes, respostas, extrator)
                            feitos += 1
                        except Exception as e:  # um título ruim não derruba o lote
                            falhas += 1
                            reg["saida"] = {"ultimo_erro": f"{type(e).__name__}: {e}"[:200]}
        return {"calculados": feitos, "falhas": falhas, "extrator": extrator}

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
        """Falhas do pipeline por etapa, onde o modelo mais erra (experimento ativo, ou o
        último diagnóstico) e as notas de padrão deixadas pelo humano."""
        alvo = alvo or self.obter_projeto(projeto).alvo
        with self._abrir_existente(projeto) as banco:
            falhas = camada_bruta.listar_falhas(banco)
            ativo = experimentos.ativo(banco, alvo)
            avaliacao = modelagem.ultima_avaliacao(banco, alvo)
            notas = humano.notas(banco)
        por_etapa: dict[str, int] = {}
        for f in falhas:
            por_etapa[f.etapa] = por_etapa.get(f.etapa, 0) + 1
        fonte, origem = (
            (ativo.resultado, f"experimento {ativo.id}")
            if ativo
            else (
                avaliacao,
                "diagnóstico" if avaliacao else "",
            )
        )
        return modelagem.RelatorioErros(
            falhas_por_etapa=por_etapa,
            piores=fonte.piores if fonte else [],
            segmentos=fonte.segmentos if fonte else {},
            origem=origem,
            notas_padrao=[n.nota for n in notas if n.tipo == "padrao"],
        )

    # ------------------------------------------------------------ portões humanos

    def amostra_para_revisao(
        self, projeto: str, atributo_id: str, n: int = 20, extrator: str | None = None
    ) -> list[humano.ItemRevisao]:
        """Vídeos para o humano conferir um atributo (padrão: o extrator configurado)."""
        with self._abrir_existente(projeto) as banco:
            atributo = self._atributo(banco, atributo_id)
            return humano.amostra(banco, atributo, extrator or self._extrator_atual(), n)

    def revisar(self, projeto: str, video_id: str, atributo_id: str, valor) -> None:
        with self._abrir_existente(projeto) as banco:
            atributo = self._atributo(banco, atributo_id)
            try:
                humano.revisar(banco, atributo, video_id, valor)
            except ValueError as erro:
                raise erros.ErroGalaxies(str(erro)) from erro

    def concordancia(self, projeto: str, extrator: str | None = None) -> list[humano.Concordancia]:
        """Quanto o extrator concorda com as revisões humanas, por atributo."""
        with self._abrir_existente(projeto) as banco:
            return humano.concordancia(
                banco, atrib.ler_definicoes(banco), extrator or self._extrator_atual()
            )

    def anotar_erro(self, projeto: str, video_id: str, tipo: str, nota: str) -> humano.Nota:
        """dado_ruim: o vídeo sai da base. padrao: vira pista para o agente (erros)."""
        if tipo not in ("dado_ruim", "padrao"):
            raise ConfigInvalida("tipo deve ser 'dado_ruim' ou 'padrao'")
        with self._abrir_existente(projeto) as banco:
            return humano.anotar(banco, video_id, tipo, nota)

    def notas(self, projeto: str) -> list[humano.Nota]:
        with self._abrir_existente(projeto) as banco:
            return humano.notas(banco)

    def _atributo(self, banco, atributo_id: str) -> atrib.Atributo:
        por_id = {a.id: a for a in atrib.ler_definicoes(banco)}
        if atributo_id not in por_id:
            raise erros.ErroGalaxies(f"atributo '{atributo_id}' não existe no projeto")
        return por_id[atributo_id]

    def _extrator_atual(self) -> str | None:
        return identificar(self.dependencias.jev) if self.dependencias.jev else None

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
        """Diagnóstico: avalia as camadas no split temporal fixo (sem gerar modelo)."""
        config = self.obter_projeto(projeto)
        alvo = alvo or config.alvo
        if alvo not in ("likes", "views"):
            raise ConfigInvalida(f"alvo '{alvo}' inválido: use likes ou views")
        with self._abrir_existente(projeto) as banco, executar(banco, "treinar") as ex:
            avaliacao = treino.treinar(banco, alvo, atrib.ler_definicoes(banco), ex)
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

    # ------------------------------------------------------------ experimentos

    def experimentar(
        self, projeto: str, receita: Receita | dict, hipotese: str = "", alvo: str | None = None
    ) -> Experimento:
        """Treina uma receita e registra como candidato, comparado com o baseline do canal e
        com o controle só de metadados nas mesmas linhas de teste."""
        alvo = self._alvo(projeto, alvo)
        try:
            receita = Receita.model_validate(receita)
        except ValidationError as erro:
            raise ConfigInvalida(str(erro)) from erro
        with self._abrir_existente(projeto) as banco, executar(banco, "experimentar") as ex:
            with ex.etapa("treinar_receita", receita.model_dump()) as registro:
                try:
                    exp = experimentos.treinar(
                        banco,
                        alvo,
                        receita,
                        atrib.ler_definicoes(banco),
                        self._pasta_do_projeto(projeto) / "modelos",
                        hipotese,
                        identificar(self.dependencias.jev) if self.dependencias.jev else None,
                    )
                except ValueError as erro:
                    raise ConfigInvalida(str(erro)) from erro
                registro["saida"] = exp.resultado.model_dump(include={"ganho", "modelo"})
            experimentos.salvar(banco, exp)
        return exp

    def experimentos(self, projeto: str, alvo: str | None = None) -> list[Experimento]:
        with self._abrir_existente(projeto) as banco:
            return experimentos.listar(banco, alvo)

    def promover(self, projeto: str, exp_id: str) -> Experimento:
        """Automático: ativa se supera o baseline. Cientista: fica aguardando o humano."""
        config = self.obter_projeto(projeto)
        with self._abrir_existente(projeto) as banco:
            exp = self._experimento(banco, exp_id)
            if exp.resultado.ganho <= 0:
                raise erros.ErroGalaxies(
                    f"O experimento {exp_id} não supera o baseline do canal "
                    f"(ganho {exp.resultado.ganho:.3f}): não pode ser promovido."
                )
            if config.modo == "cientista":
                exp = exp.model_copy(update={"status": "aguardando_aprovacao"})
                experimentos.salvar(banco, exp)
                return exp
            return experimentos.ativar(banco, exp)

    def decidir(self, projeto: str, exp_id: str, aprovar: bool, nota: str = "") -> Experimento:
        """Decisão humana sobre uma promoção (UI). Não é exposta ao agente."""
        with self._abrir_existente(projeto) as banco:
            exp = self._experimento(banco, exp_id)
            if exp.status != "aguardando_aprovacao":
                raise erros.ErroGalaxies(f"O experimento {exp_id} não aguarda aprovação.")
            exp = exp.model_copy(update={"nota_humana": nota})
            if aprovar:
                return experimentos.ativar(banco, exp)
            exp = exp.model_copy(update={"status": "rejeitado"})
            experimentos.salvar(banco, exp)
            return exp

    def otimizar(
        self, projeto: str, alvo: str | None = None, orcamento: int = 16, paciencia: int = 6
    ) -> Ciclo:
        """O agente busca a melhor receita na validação e avalia só a escolhida no teste.
        Modo automático: promove se superar o baseline. Modo cientista: fica candidata."""
        alvo = self._alvo(projeto, alvo)
        with self._abrir_existente(projeto) as banco, executar(banco, "otimizar") as ex:
            busca = otimizacao.otimizar(
                banco, alvo, atrib.ler_definicoes(banco), ex, orcamento, paciencia
            )
        if busca.melhor is None:
            return Ciclo(
                experimentos=[],
                promovido=None,
                tentativas=[t.model_dump() for t in busca.tentativas],
            )
        resumo = ", ".join(
            f"{t.origem}: {t.objetivo:+.1%}" for t in busca.tentativas if t.objetivo is not None
        )
        exp = self.experimentar(
            projeto,
            busca.melhor,
            f"otimização: melhor de {len(busca.tentativas)} tentativas na validação "
            f"({busca.objetivo_validacao:+.1%} sobre o controle). Tentativas: {resumo}",
            alvo,
        )
        promovido = None
        with self._abrir_existente(projeto) as banco:
            ativo = experimentos.ativo(banco, alvo)
        motivo = experimentos.motivo_para_nao_promover(exp, ativo)
        if self.obter_projeto(projeto).modo == "automatico" and motivo is None:
            promovido = self.promover(projeto, exp.id).id
        return Ciclo(
            experimentos=[exp],
            promovido=promovido,
            tentativas=[t.model_dump() for t in busca.tentativas],
            objetivo_validacao=busca.objetivo_validacao,
            motivo=motivo,
        )

    def insights(self, projeto: str, alvo: str | None = None) -> dict:
        """Analytics rápidas do projeto: o que funciona no setor, medido na base (não no modelo).
        Efeitos são a mediana do alvo relativo ao canal, em %, por grupo."""
        alvo = self._alvo(projeto, alvo)
        with self._abrir_existente(projeto) as banco:
            base = banco.execute(
                f"""
                WITH v AS (
                  SELECT v.id, c.setor, v.duracao_s, v.{alvo} AS y,
                         hour(v.publicado_em AT TIME ZONE 'America/Sao_Paulo') AS hora,
                         dayofweek(v.publicado_em AT TIME ZONE 'America/Sao_Paulo') AS dia,
                         median(v.{alvo}) OVER (PARTITION BY v.canal_id) AS mediana_canal
                  FROM videos v JOIN canais c ON c.id = v.canal_id
                  WHERE v.{alvo} IS NOT NULL
                    AND v.canal_id NOT IN (SELECT id FROM excluidos WHERE tipo = 'canal')
                )
                SELECT id, setor, duracao_s, hora, dia, y,
                       ln(y + 1) - ln(mediana_canal + 1) AS rel
                FROM v
                """
            ).df()
            respostas = banco.execute(
                "SELECT video_id, atributo_id, resposta FROM respostas QUALIFY ROW_NUMBER() "
                "OVER (PARTITION BY video_id, atributo_id ORDER BY quando DESC) = 1"
            ).fetchall()
            setores = banco.execute(
                f"SELECT c.setor, count(DISTINCT c.id), count(v.id), median(v.{alvo}) "
                "FROM canais c LEFT JOIN videos v ON v.canal_id = c.id GROUP BY 1 ORDER BY 3 DESC"
            ).fetchall()
            definicoes = {a.id: a for a in atrib.ler_definicoes(banco)}
        if base.empty:
            return {"alvo": alvo, "setores": [], "horarios": [], "duracao": [], "fatores": []}

        def efeito(grupo) -> float:
            return float(np.expm1(grupo["rel"].median()))

        def ranking(coluna, rotulo, minimo=30):
            grupos = [(k, g) for k, g in base.groupby(coluna) if len(g) >= minimo]
            grupos.sort(key=lambda kg: -kg[1]["rel"].median())
            return [{"grupo": rotulo(k), "efeito": efeito(g), "n": len(g)} for k, g in grupos]

        base["faixa"] = pd.cut(
            base["duracao_s"], [0, 15, 30, 60, 180], labels=["até 15s", "15–30s", "30–60s", "60s+"]
        )
        fatores = []
        if respostas:
            import json as _json

            df = pd.DataFrame(respostas, columns=["video_id", "atributo_id", "resposta"])
            df = df.merge(base[["id", "rel"]], left_on="video_id", right_on="id")
            for atributo_id, g in df.groupby("atributo_id"):
                a = definicoes.get(atributo_id)
                if a is None or len(g) < 30:
                    continue
                rot = g["resposta"].map(_json.loads).map(lambda r, a=a: _rotulo(a, r))
                todos = g["rel"].median()
                for rotulo, gg in g.assign(rotulo=rot).groupby("rotulo"):
                    if len(gg) >= 20:
                        fatores.append(
                            {
                                "fator": f"{atributo_id}: {rotulo}",
                                "efeito": float(np.expm1(gg["rel"].median() - todos)),
                                "n": len(gg),
                            }
                        )
        fatores.sort(key=lambda f: -f["efeito"])
        return {
            "alvo": alvo,
            "setores": [
                {"setor": s, "canais": c, "shorts": n, "mediana": m} for s, c, n, m in setores
            ],
            "horarios": ranking("hora", lambda h: f"{int(h)}h")[:5],
            "dias": ranking(
                "dia", lambda d: ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][int(d)]
            )[:3],
            "duracao": ranking("faixa", str, 50),
            "fatores": fatores[:6],
            "piores_fatores": fatores[-3:][::-1] if len(fatores) > 6 else [],
        }

    # ------------------------------------------------------------ pós-publicação

    def acompanhar(self, projeto: str, run_id: str, video_id: str) -> acompanhamento.Acompanhamento:
        """Liga uma análise (run de analisar) ao vídeo publicado e guarda os números de agora."""
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        config = self.obter_projeto(projeto)
        with self._abrir_existente(projeto) as banco, executar(banco, "acompanhar") as ex:
            run = next((r for r in listar_runs(banco) if r.id == run_id), None)
            if run is None or run.operacao != "analisar":
                raise erros.ErroGalaxies(f"'{run_id}' não é um run de analisar.")
            prever = next((e for e in ler_trace(banco, run_id) if e.nome == "prever"), None)
            if prever is None or not prever.saida:
                raise erros.ErroGalaxies(f"O run {run_id} não tem previsão registrada.")
            with ex.etapa("buscar_video", {"video_id": video_id}):
                videos = youtube.videos([video_id])
            coleta.registrar_cota(banco, ex.run_id, youtube.unidades)
            if not videos:
                raise erros.ErroGalaxies(f"Vídeo '{video_id}' não encontrado no YouTube.")
            video = videos[0]
            publicado = video["publicado_em"]
            if isinstance(publicado, str):
                publicado = datetime.fromisoformat(publicado.replace("Z", "+00:00"))
            acompanhamento.registrar(
                banco,
                video_id,
                run_id,
                video["canal_id"],
                config.alvo,
                publicado,
                prever.saida["timeline"],
            )
            acompanhamento.observar(banco, video)
            return next(a for a in acompanhamento.listar(banco).videos if a.video_id == video_id)

    def atualizar_acompanhamentos(self, projeto: str) -> acompanhamento.ResumoAtualizacao:
        """Busca os números atuais de todos os vídeos acompanhados (1 unidade por 50)."""
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        with (
            self._abrir_existente(projeto) as banco,
            executar(banco, "atualizar_acompanhamentos") as ex,
        ):
            pendentes = acompanhamento.ids(banco)
            vistos: set[str] = set()
            for inicio in range(0, len(pendentes), 50):
                lote = pendentes[inicio : inicio + 50]
                with ex.etapa("buscar_videos", {"n": len(lote)}):
                    for video in youtube.videos(lote):
                        acompanhamento.observar(banco, video)
                        vistos.add(video["id"])
            coleta.registrar_cota(banco, ex.run_id, youtube.unidades)
        return acompanhamento.ResumoAtualizacao(
            atualizados=len(vistos), sem_dados=[v for v in pendentes if v not in vistos]
        )

    def acompanhamentos(self, projeto: str) -> acompanhamento.ListaAcompanhamentos:
        """Previsto × real dos vídeos acompanhados, com cobertura da faixa e erro típico."""
        with self._abrir_existente(projeto) as banco:
            return acompanhamento.listar(banco)

    # ------------------------------------------------------------ curva de crescimento

    def observar_recentes(
        self, projeto: str, dias_max: float = 90, agora: datetime | None = None
    ) -> crescimento.ResumoObservacao:
        """Busca de novo os números dos vídeos com menos de `dias_max` dias (1 unidade por
        50). A coleta vira a primeira observação; cada rodada acrescenta outra. Rode uma vez
        por dia: é o que ensina a curva de crescimento."""
        youtube = coleta.YouTubeMedido(self._exigir(self.dependencias.youtube, "youtube"))
        agora = agora or crescimento.agora_utc()
        with self._abrir_existente(projeto) as banco, executar(banco, "observar_recentes") as ex:
            with ex.etapa("semear") as registro:
                registro["saida"] = {"novas": crescimento.semear(banco)}
            pendentes = crescimento.recentes(banco, dias_max, agora)
            vistos = 0
            for inicio in range(0, len(pendentes), 50):
                lote = pendentes[inicio : inicio + 50]
                with ex.etapa("buscar_videos", {"n": len(lote)}):
                    for video in youtube.videos(lote):
                        acompanhamento.observar(banco, video, agora)
                        vistos += 1
            coleta.registrar_cota(banco, ex.run_id, youtube.unidades)
        return crescimento.ResumoObservacao(
            candidatos=len(pendentes),
            observados=vistos,
            sem_dados=len(pendentes) - vistos,
            unidades=youtube.unidades,
        )

    def proximo_passo(self, projeto: str) -> ProximoPasso:
        """Decide o próximo passo do roadmap por regras sobre o estado do projeto. Regras dão
        decisão auditável e grátis; o agente (LLM) só entra onde a resposta é 'ambiguo'."""
        config = self.obter_projeto(projeto)
        with self._abrir_existente(projeto) as banco:
            um = lambda sql, *p: banco.execute(sql, list(p)).fetchone()[0]  # noqa: E731
            e = {
                "canais": um("SELECT count(*) FROM canais"),
                "videos": um("SELECT count(*) FROM videos"),
                "com_texto": um("SELECT count(*) FROM texto_embedding"),
                "com_titulo": um(
                    "SELECT count(DISTINCT video_id) FROM respostas "
                    "WHERE atributo_id LIKE 'titulo_%'"
                ),
                "ganchos": um("SELECT count(*) FROM camada_bruta"),
                "aguardando": um(
                    "SELECT count(*) FROM experimentos WHERE status = 'aguardando_aprovacao'"
                ),
                "ultima_observacao": um("SELECT max(quando) FROM observacoes"),
            }
            ativo = experimentos.ativo(banco, config.alvo)
            e["modelo_ativo"] = ativo.id if ativo else None
            e["videos_novos"] = (
                um("SELECT count(*) FROM videos WHERE coletado_em > ?", ativo.criado_em)
                if ativo
                else e["videos"]
            )
            base_modelo = um(
                "SELECT count(*) FROM (SELECT row_number() OVER (PARTITION BY canal_id "
                "ORDER BY publicado_em DESC) AS n FROM videos) WHERE n <= 300"
            )
        passo = lambda acao, motivo, certeza="regra", alt=(): ProximoPasso(  # noqa: E731
            acao=acao, motivo=motivo, certeza=certeza, alternativas=list(alt), estado=e
        )
        if e["canais"] == 0 and not config.canais_semente:
            return passo("descobrir_canais", "o projeto não tem canais", alt=["adicionar_canal"])
        if e["videos"] == 0:
            return passo("coletar", "canais sem vídeos coletados")
        if self.dependencias.texto is not None and e["com_texto"] < 0.9 * e["videos"]:
            return passo(
                "calcular_texto", f"{e['videos'] - e['com_texto']} vídeos sem embedding de texto"
            )
        if self.dependencias.rapido is not None and e["com_titulo"] < 0.9 * base_modelo:
            return passo(
                "calcular_titulos",
                f"{base_modelo - e['com_titulo']} vídeos da base sem perguntas de título (local)",
            )
        if config.modo == "cientista" and e["aguardando"]:
            return passo(
                "aguardar_humano",
                f"{e['aguardando']} experimento(s) aguardando aprovação na UI",
                alt=["experimentar"],
            )
        if ativo is None:
            return passo("otimizar", f"nenhum modelo ativo para {config.alvo}")
        limiar = max(LIMIAR_NOVOS_ABSOLUTO, int(0.02 * e["videos"]))
        if e["videos_novos"] >= limiar:
            return passo(
                "otimizar",
                f"{e['videos_novos']} vídeos novos desde o modelo ativo (limiar {limiar})",
            )
        ultima = e["ultima_observacao"]
        if ultima is None or (datetime.now(UTC) - ultima.astimezone(UTC)).days >= 1:
            return passo("observar_recentes", "reobservação diária pendente (curva de crescimento)")
        precisa = 2900  # ~300 linhas na validação para a camada de gancho ter poder estatístico
        if e["ganchos"] < precisa:
            return passo(
                "manter",
                f"modelo em dia; a camada de gancho só vira testável com ~{precisa} ganchos "
                f"(há {e['ganchos']}): processar mais custa Gemini e horas, decida com o usuário",
                certeza="ambiguo",
                alt=["processar_ganchos", "descobrir_canais", "rotina"],
            )
        return passo("manter", "modelo em dia e base estável", alt=["rotina"])

    def rotina(self, projeto: str, alvo: str | None = None) -> "Rotina":
        """O dia a dia do agente, numa chamada: reobserva os vídeos recentes (curva de
        crescimento), atualiza os acompanhamentos, coleta o que os canais publicaram desde a
        última vez e, se a base cresceu o bastante, calcula o texto e reotimiza (automático:
        promove sozinho; cientista: deixa candidato para aprovação)."""
        config = self.obter_projeto(projeto)
        antes = self.resumo(projeto)["videos"]
        observacao = self.observar_recentes(projeto)
        acompanhamentos = self.atualizar_acompanhamentos(projeto).atualizados
        coletados = self.coletar(projeto, so_faltantes=True).videos_novos
        rotina = Rotina(
            observados=observacao.observados,
            acompanhamentos_atualizados=acompanhamentos,
            videos_novos=coletados,
            unidades=observacao.unidades,
        )
        limiar = max(LIMIAR_NOVOS_ABSOLUTO, int(antes * LIMIAR_NOVOS_FRACAO))
        if coletados < limiar:
            rotina.motivo = (
                f"{coletados} vídeos novos (reotimiza a partir de {limiar}): modelo mantido"
            )
            return rotina
        if self.dependencias.texto is not None:
            rotina.texto_calculado = self.calcular_texto(projeto).get("calculados", 0)
        ciclo = self.otimizar(projeto, alvo)
        rotina.reotimizou = True
        rotina.experimento = ciclo.experimentos[0].id if ciclo.experimentos else None
        rotina.promovido = ciclo.promovido
        rotina.motivo = ciclo.motivo or (
            "promovido"
            if ciclo.promovido
            else "candidato aguardando aprovação"
            if config.modo == "cientista"
            else "nenhuma receita superou a média do canal"
        )
        return rotina

    def crescimento(self, projeto: str, alvo: str | None = None) -> crescimento.Curva:
        """Curva de crescimento observada: inclinação de log(1+y) por log(idade) por faixa de
        idade, a partir dos vídeos reobservados."""
        config = self.obter_projeto(projeto)
        with self._abrir_existente(projeto) as banco:
            return crescimento.curva(banco, alvo or config.alvo)

    def relatorio(self, projeto: str) -> str:
        """Relatório de avaliação em Markdown, reproduzível a partir do banco."""
        config = self.obter_projeto(projeto)
        exps = self.experimentos(projeto)
        otimizacoes = []
        with self._abrir_existente(projeto) as banco:
            for run in reversed(listar_runs(banco)):
                if run.operacao != "otimizar" or run.status != "ok":
                    continue
                tentativas = [
                    {**e.entrada, **(e.saida or {})}
                    for e in ler_trace(banco, run.id)
                    if e.nome == "tentativa"
                ]
                inicio = run.inicio if run.inicio.tzinfo else run.inicio.replace(tzinfo=UTC)
                alvo = next((x.alvo for x in exps if x.criado_em >= inicio), config.alvo)
                if tentativas and alvo not in {a for a, _ in otimizacoes}:
                    otimizacoes.append((alvo, tentativas))
            curvas = {alvo: crescimento.curva(banco, alvo) for alvo in ("likes", "views")}
            idade_minima = crescimento.idade_minima_vista(banco)
        return relatorio_md.gerar(
            projeto, config, self.resumo(projeto), exps, otimizacoes, curvas, idade_minima
        )

    def ciclo_automatico(self, projeto: str, alvo: str | None = None) -> Ciclo:
        """Modo automático: otimiza e promove sozinho."""
        if self.obter_projeto(projeto).modo != "automatico":
            raise erros.ErroGalaxies(
                "Projeto no modo cientista: rode otimizar ou experimentar e promova com "
                "aprovação humana."
            )
        return self.otimizar(projeto, alvo)

    @staticmethod
    def _historico_do_novo(banco, alvo: str, canal_id: str, linha) -> dict:
        """Momento do canal na data planejada do vídeo novo (mesmas regras do treino)."""
        videos = banco.execute(
            f"SELECT id AS video_id, canal_id, publicado_em, {alvo} AS y FROM videos "
            f"WHERE canal_id = ? AND {alvo} IS NOT NULL"
            " AND id NOT IN (SELECT id FROM excluidos WHERE tipo = 'video')",
            [canal_id],
        ).df()
        videos["publicado_em"] = pd.to_datetime(videos["publicado_em"], utc=True)
        novo = pd.DataFrame(
            {
                "video_id": ["__novo__"],
                "canal_id": [canal_id],
                "publicado_em": linha["publicado_em"].to_numpy(),
                "y": [np.nan],
            }
        )
        novo["publicado_em"] = pd.to_datetime(novo["publicado_em"], utc=True)
        hist = modelagem.historico(pd.concat([videos, novo], ignore_index=True))
        return hist.set_index("video_id").loc["__novo__"].to_dict()

    def calcular_texto(self, projeto: str, lote: int = 256) -> dict:
        """Embedding de título + descrição dos vídeos que ainda não têm (camada texto)."""
        embedder = self._exigir(self.dependencias.texto, "texto")
        with self._abrir_existente(projeto) as banco, executar(banco, "calcular_texto") as ex:
            faltam = banco.execute(
                "SELECT id, titulo, descricao FROM videos "
                "WHERE id NOT IN (SELECT video_id FROM texto_embedding) ORDER BY id"
            ).fetchall()
            for inicio in range(0, len(faltam), lote):
                parte = faltam[inicio : inicio + lote]
                with ex.etapa("embutir_lote", {"inicio": inicio, "n": len(parte)}):
                    vetores = embedder.embutir_textos([_texto_do_video(t, d) for _, t, d in parte])
                banco.executemany(
                    "INSERT OR REPLACE INTO texto_embedding VALUES (?, ?)",
                    [[v, e] for (v, _, _), e in zip(parte, vetores, strict=True)],
                )
        return {"calculados": len(faltam)}

    def _experimento(self, banco, exp_id: str) -> Experimento:
        try:
            return experimentos.obter(banco, exp_id)
        except ValueError as erro:
            raise erros.ErroGalaxies(str(erro)) from erro

    def _alvo(self, projeto: str, alvo: str | None) -> str:
        alvo = alvo or self.obter_projeto(projeto).alvo
        if alvo not in ("likes", "views"):
            raise ConfigInvalida(f"alvo '{alvo}' inválido: use likes ou views")
        return alvo

    # ------------------------------------------------------------ análise

    def analisar(self, projeto: str, video: VideoNovo | dict, canal_id: str) -> Analise:
        """Previsão de um Short ainda não publicado com o modelo ativo do alvo do projeto."""
        config = self.obter_projeto(projeto)
        video = VideoNovo.model_validate(video)
        with self._abrir_existente(projeto) as banco:
            exp = experimentos.ativo(banco, config.alvo)
        if exp is None:
            raise erros.ErroGalaxies(
                f"Nenhum modelo ativo para '{config.alvo}'. Rode experimentar e promova um."
            )
        pasta = self._pasta_do_projeto(projeto) / "modelos" / exp.id
        modelos, meta = modelagem.carregar_modelos(pasta)
        if canal_id not in {c["canal_id"] for c in meta["canais"]}:
            raise CanalForaDaBase(canal_id)
        if "atributos" in meta and self.dependencias.jev is not None:
            atual = identificar(self.dependencias.jev)
            if meta.get("extrator") not in (None, atual):
                raise erros.ErroGalaxies(
                    f"O modelo ativo foi treinado com atributos de '{meta['extrator']}', mas o "
                    f"extrator configurado é '{atual}' (ATRIBUTOS_MODELO)."
                )
        precisa_video = "pca_multimodal" in meta or "atributos" in meta
        if "pca_texto" in meta:
            self._exigir(self.dependencias.texto, "texto")
        if precisa_video and not video.fonte:
            raise erros.ErroGalaxies(
                f"O modelo ativo usa {exp.receita.camadas}: informe video.fonte (arquivo ou link)."
            )
        with self._abrir_existente(projeto) as banco, executar(banco, "analisar") as ex:
            setor, inscritos = banco.execute(
                "SELECT setor, inscritos FROM canais WHERE id = ?", [canal_id]
            ).fetchone()
            gancho = respostas = bruta = None
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
                    if "atributos" in meta:
                        definicoes = [atrib.Atributo.model_validate(a) for a in meta["atributos"]]
                    estado = atrib.estado_do_video(video.titulo, video.descricao, video.tags, bruta)
                    with ex.etapa("perguntar_atributos", {"estado": estado}) as registro:
                        respostas = self.dependencias.jev.perguntar(
                            estado, {a.id: a.como_pergunta_jev() for a in definicoes}
                        )
                        registro["saida"] = respostas
            if "atributos" in meta and respostas is None:
                raise DependenciaAusente("jev")
            linha = linha_do_video(video, {"canal_id": canal_id}, setor, inscritos)
            historico = texto = None
            if "historico" in exp.receita.camadas:
                with ex.etapa("historico_do_canal") as registro:
                    historico = self._historico_do_novo(banco, config.alvo, canal_id, linha)
                    registro["saida"] = historico
            if "pca_texto" in meta:
                with ex.etapa("embutir_texto") as registro:
                    (texto,) = self.dependencias.texto.embutir_textos(
                        [_texto_do_video(video.titulo, video.descricao)]
                    )
                    registro["saida"] = {"dimensoes": len(texto)}
            titulo_resp = None
            if meta.get("titulo"):
                rapido = self._exigir(self.dependencias.rapido, "rapido")
                with ex.etapa("perguntar_titulo") as registro:
                    titulo_resp = rapido.perguntar(
                        atrib.estado_do_titulo(video.titulo, video.descricao),
                        {a.id: a.como_pergunta_jev() for a in atrib.DE_TITULO},
                    )
                    registro["saida"] = titulo_resp
            curva = crescimento.curva(banco, config.alvo)
            idade_minima = crescimento.idade_minima_vista(banco)
            with ex.etapa("prever", video.model_dump(mode="json")) as registro:
                resultado = prever(
                    modelos,
                    meta,
                    linha,
                    config.limite_viral,
                    embedding=bruta.embedding if bruta else None,
                    respostas=respostas,
                    historico=historico,
                    texto=texto,
                    curva=curva if curva.faixas else None,
                    idade_minima=idade_minima,
                    titulo=titulo_resp,
                )
                registro["saida"] = {
                    "experimento": exp.id,
                    "idade_minima_vista": round(idade_minima, 1),
                    "curva": {f"{f.de_dias:g}-{f.ate_dias:g}d": f.inclinacao for f in curva.faixas},
                    "timeline": [p.model_dump() for p in resultado["timeline"]],
                    "chances": [c.model_dump() for c in resultado["chances"]],
                }
            with ex.etapa("explicar") as registro:
                resultado["explicacao"] = (
                    resultado["explicacao"].replace(" likes ", f" {config.alvo} ", 1)
                    if config.alvo != "likes"
                    else resultado["explicacao"]
                )
                registro["saida"] = {
                    "explicacao": resultado["explicacao"],
                    "fatores": [f.model_dump() for f in resultado["fatores"]],
                    "sugestoes": [s.model_dump() for s in resultado["sugestoes"]],
                }
            return Analise(
                run_id=ex.run_id,
                experimento_id=exp.id,
                canal_id=canal_id,
                alvo=config.alvo,
                gancho=gancho,
                atributos=respostas,
                **resultado,
            )

    def comparar(
        self, projeto: str, video_a: VideoNovo | dict, video_b: VideoNovo | dict, canal_id: str
    ) -> Comparacao:
        """A vs B no mesmo canal: duas análises e qual deve performar melhor em 7 dias.
        A confiança disso é o acerto_pares do modelo ativo (experimentos)."""
        a = self.analisar(projeto, video_a, canal_id)
        b = self.analisar(projeto, video_b, canal_id)
        diferenca = b.previsao_7d.q50 / max(a.previsao_7d.q50, 1.0) - 1
        return Comparacao(a=a, b=b, vencedor="b" if diferenca > 0 else "a", diferenca=diferenca)

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


def _texto_do_video(titulo: str | None, descricao: str | None) -> str:
    return f"{titulo or ''}\n{(descricao or '')[:300]}"


def _rotulo(a: atrib.Atributo, r: dict) -> str:
    """Rótulo legível de uma resposta de atributo, para agrupar nos insights."""
    if a.tipo == "choice":
        return r.get("choice") or max(r["probabilities"], key=r["probabilities"].get)
    if a.tipo == "noul":
        return "sim" if float(r["noul"]) >= 0.5 else "não"
    niveis = a.criterios
    return niveis[min(int(round(float(r["score"]))), len(niveis) - 1)]
