"""Adaptador MCP (stdio): a interface principal. Só traduz tools em chamadas ao Framework.

Operações longas (coletar, processar ganchos, atributos, reprocessar, treinar) viram jobs em
segundo plano: a tool devolve um job_id e o agente acompanha com `status`.
"""

import functools
import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from galaxies import ErroGalaxies, Framework
from galaxies.serializar import para_json as _json

INSTRUCOES = """Galaxies: você (o agente) constrói o modelo que prevê a performance de
YouTube Shorts de um setor. As regras de avaliação são fixas; você escolhe as receitas.

Dados: criar_projeto → coletar (job) → calcular_texto (job) → processar_ganchos (job,
caro: confirme com o usuário lotes grandes) → calcular_atributos (job).

Modelo: otimizar (job) busca a melhor receita na validação e testa só a escolhida. Use-o
sempre que houver dados novos. Para testar uma ideia específica: experimentar (job) com
uma receita {camadas, atributos, extrator, params} e uma hipótese escrita por você. Cada
experimento é comparado com o baseline do canal e com o controle só de metadados nas
mesmas linhas, e traz sugestões de próximos passos. Modo automático: ciclo_automatico faz
tudo. Modo cientista: a promoção espera aprovação humana na UI; discuta com o usuário.

Melhorar sempre: leia erros, notas (pistas do humano) e concordancia; crie atributos novos
com definir_atributos, calcule e otimize de novo. Diagnóstico da base: treinar → avaliar.
Usar: analisar um vídeo novo (chances, timeline, fatores e sugestões para viralizar).
Depois de publicar: acompanhar(run_id, video_id) e, com o tempo, atualizar_acompanhamentos;
acompanhamentos mostra previsto × real em produção.
Auditar: runs, trace, erros, falhas, reprocessar. Jobs devolvem job_id: use status."""


@dataclass
class Job:
    id: str
    operacao: str
    projeto: str
    inicio: datetime
    futuro: Future = field(repr=False)

    def resumo(self) -> dict:
        status = "rodando"
        resultado = erro = None
        if self.futuro.done():
            if excecao := self.futuro.exception():
                status, erro = "falhou", str(excecao)
            else:
                status, resultado = "ok", _json(self.futuro.result())
        return {
            "job_id": self.id,
            "operacao": self.operacao,
            "projeto": self.projeto,
            "inicio": self.inicio.isoformat(),
            "status": status,
            "resultado": resultado,
            "erro": erro,
        }


class Jobs:
    """Um job por vez: o DuckDB de cada projeto aceita um escritor só."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._jobs: dict[str, Job] = {}
        self._trava = threading.Lock()

    def iniciar(self, operacao: str, projeto: str, funcao, *args, **kwargs) -> dict:
        job = Job(
            id=uuid.uuid4().hex[:12],
            operacao=operacao,
            projeto=projeto,
            inicio=datetime.now(UTC),
            futuro=self._executor.submit(funcao, *args, **kwargs),
        )
        with self._trava:
            self._jobs[job.id] = job
        return {"job_id": job.id, "status": "rodando"}

    def status(self, job_id: str | None = None) -> dict | list[dict]:
        with self._trava:
            if job_id is None:
                return [j.resumo() for j in self._jobs.values()]
            if job_id not in self._jobs:
                raise ValueError(f"job '{job_id}' não existe")
            return self._jobs[job_id].resumo()

    def esperar(self, job_id: str, timeout: float | None = None):
        self._jobs[job_id].futuro.exception(timeout)


@dataclass
class ServidorGalaxies:
    servidor: MCPServer
    jobs: Jobs


def _texto(valor) -> str:
    return json.dumps(_json(valor), ensure_ascii=False, default=str)


def criar_servidor(fw: Framework) -> ServidorGalaxies:
    mcp = MCPServer(name="galaxies", instructions=INSTRUCOES)
    jobs = Jobs()

    def tool(funcao):
        """Erros de domínio e de validação voltam ao agente com a mensagem; o resto, não."""

        @functools.wraps(funcao)
        def chamada(*args, **kwargs):
            try:
                return funcao(*args, **kwargs)
            except (ErroGalaxies, ValidationError, ValueError) as erro:
                raise ToolError(str(erro)) from erro

        return mcp.tool(structured_output=False)(chamada)

    # ------------------------------------------------------------ projeto e setor

    @tool
    def criar_projeto(config: dict) -> str:
        """Cria um projeto. config: nome (minúsculas, dígitos, hífen), setores, canais_semente
        [{ref: '@handle' ou 'UC...', setor}], alvo ('likes' ou 'views'), detalhes (texto livre
        sobre o setor), coletar_desde (AAAA-MM-DD, opcional), limite_viral (padrão 3.0)."""
        return _texto(fw.criar_projeto(config))

    @tool
    def obter_projeto(projeto: str) -> str:
        """Configuração do projeto."""
        return _texto(fw.obter_projeto(projeto))

    @tool
    def adicionar_canal(projeto: str, ref: str, setor: str) -> str:
        """Adiciona e coleta um canal ('@handle' ou 'UC...'). Rode treinar depois."""
        return _texto(fw.adicionar_canal(projeto, ref, setor))

    @tool
    def descobrir_canais(projeto: str, consulta: str, teto_unidades: int = 1000) -> str:
        """Busca canais do setor no YouTube (cada busca custa 100 unidades de cota)."""
        return _texto(fw.descobrir_canais(projeto, consulta, teto_unidades=teto_unidades))

    @tool
    def atributos(projeto: str) -> str:
        """Atributos atuais: perguntas tipadas sobre título, gancho visual e fala."""
        return _texto(fw.atributos(projeto))

    @tool
    def definir_atributos(projeto: str, atributos: list[dict]) -> str:
        """Substitui os atributos. Cada um: id (snake_case), tipo ('choice', 'score' ou 'noul'),
        instrucoes (a pergunta), criterios (choice: {rótulo: descrição}; score: [níveis em
        ordem]; noul: opcional). Só os atributos novos ou alterados são recalculados."""
        return _texto(fw.definir_atributos(projeto, atributos))

    # ------------------------------------------------------------ jobs longos

    @tool
    def coletar(projeto: str, so_faltantes: bool = False) -> str:
        """Job: coleta os Shorts dos canais-semente pela YouTube Data API."""
        return _texto(jobs.iniciar("coletar", projeto, fw.coletar, projeto, so_faltantes))

    @tool
    def processar_ganchos(
        projeto: str,
        limite_por_canal: int | None = None,
        canais: list[str] | None = None,
        desde: str | None = None,
    ) -> str:
        """Job: camada bruta dos primeiros 5s (frames, descrição, fala, embedding). Cara:
        use limite_por_canal para uma amostra espaçada no tempo e desde (AAAA-MM-DD) para
        cobrir a janela de teste."""
        return _texto(
            jobs.iniciar(
                "processar_ganchos",
                projeto,
                fw.processar_ganchos,
                projeto,
                limite_por_canal,
                canais,
                date.fromisoformat(desde) if desde else None,
            )
        )

    @tool
    def calcular_atributos(projeto: str) -> str:
        """Job: responde os atributos para os vídeos com camada bruta (só o que falta)."""
        return _texto(jobs.iniciar("calcular_atributos", projeto, fw.calcular_atributos, projeto))

    @tool
    def calcular_texto(projeto: str) -> str:
        """Job: embedding de título e descrição de todos os vídeos (camada texto), local."""
        return _texto(jobs.iniciar("calcular_texto", projeto, fw.calcular_texto, projeto))

    @tool
    def reprocessar(projeto: str, video_ids: list[str] | None = None) -> str:
        """Job: limpa falhas (todas, ou as dos vídeos pedidos) e refaz esses vídeos."""
        return _texto(jobs.iniciar("reprocessar", projeto, fw.reprocessar, projeto, video_ids))

    @tool
    def treinar(projeto: str, alvo: str | None = None) -> str:
        """Job: diagnóstico da base, avalia as camadas no split temporal fixo (ablação).
        Não cria modelo: para isso use experimentar."""
        return _texto(jobs.iniciar("treinar", projeto, fw.treinar, projeto, alvo))

    @tool
    def experimentar(
        projeto: str, receita: dict, hipotese: str = "", alvo: str | None = None
    ) -> str:
        """Job: treina uma receita e registra como candidato. receita: camadas (lista com
        'metadados' e opcionalmente 'multimodal', 'atributos'), atributos (ids; omitido =
        todos), extrator (quem respondeu os atributos: 'laya', um modelo '@cf/...' ou
        'typesafe/jev'; omitido = o atual), params (num_leaves 4–127, learning_rate
        0.005–0.3, rodadas 20–2000, min_data_in_leaf 5–200).
        hipotese: o que você espera e por quê."""
        return _texto(
            jobs.iniciar("experimentar", projeto, fw.experimentar, projeto, receita, hipotese, alvo)
        )

    @tool
    def experimentos(projeto: str, alvo: str | None = None) -> str:
        """Experimentos com receita, hipótese, métricas (modelo, baseline, controle), ganho,
        status e sugestões. Use para comparar antes de promover."""
        return _texto(fw.experimentos(projeto, alvo))

    @tool
    def promover(projeto: str, exp_id: str) -> str:
        """Promove um experimento a modelo ativo (usado por analisar). Só se supera o
        baseline. No modo cientista fica aguardando aprovação humana na UI."""
        return _texto(fw.promover(projeto, exp_id))

    @tool
    def otimizar(
        projeto: str, alvo: str | None = None, orcamento: int = 16, paciencia: int = 6
    ) -> str:
        """Job: busca a melhor receita (camadas, atributos, extrator, hiperparâmetros) na
        validação e avalia só a escolhida no teste. Use sempre que houver dados novos (mais
        ganchos, atributos novos, notas humanas). Modo automático: promove se superar o
        baseline. Modo cientista: fica candidata para o humano aprovar."""
        return _texto(
            jobs.iniciar("otimizar", projeto, fw.otimizar, projeto, alvo, orcamento, paciencia)
        )

    @tool
    def ciclo_automatico(projeto: str, alvo: str | None = None) -> str:
        """Job (modo automático): otimizar + promover sozinho."""
        return _texto(jobs.iniciar("ciclo_automatico", projeto, fw.ciclo_automatico, projeto, alvo))

    @tool
    def status(job_id: str | None = None) -> str:
        """Estado de um job (ou de todos): rodando, ok ou falhou, com resultado ou erro."""
        return _texto(jobs.status(job_id))

    # ------------------------------------------------------------ avaliação e auditoria

    @tool
    def avaliar(projeto: str, alvo: str | None = None) -> str:
        """Última avaliação: baseline do canal, camadas (metadados, +multimodal, +atributos),
        ganho por atributo, piores previsões e segmentos."""
        return _texto(fw.avaliar(projeto, alvo))

    @tool
    def erros(projeto: str, alvo: str | None = None) -> str:
        """Falhas do pipeline por etapa e onde o modelo mais erra (vídeos, canais, idade)."""
        return _texto(fw.erros(projeto, alvo))

    @tool
    def falhas(projeto: str) -> str:
        """Vídeos que falharam no pipeline, com etapa e mensagem de erro."""
        return _texto(fw.falhas(projeto))

    @tool
    def excluir(projeto: str, video_ids: list[str] = (), canais: list[str] = ()) -> str:
        """Tira vídeos ou canais do processamento e dos próximos treinos."""
        fw.excluir(projeto, video_ids=list(video_ids), canais=list(canais))
        return _texto({"excluidos": {"videos": list(video_ids), "canais": list(canais)}})

    @tool
    def concordancia(projeto: str, extrator: str | None = None) -> str:
        """Quanto o extrator de atributos concorda com as revisões humanas, por atributo.
        Atributo não confiável (< 70%): reformule a pergunta antes de usar no modelo."""
        return _texto(fw.concordancia(projeto, extrator))

    @tool
    def notas(projeto: str) -> str:
        """Notas do humano sobre erros: dado_ruim (já excluído) e padrao (pista para criar
        atributos novos). Revisar, anotar e aprovar promoções são ações só do humano, na UI."""
        return _texto(fw.notas(projeto))

    @tool
    def runs(projeto: str) -> str:
        """Execuções registradas (cada serviço vira um run com trace)."""
        return _texto(fw.runs(projeto))

    @tool
    def trace(projeto: str, run_id: str) -> str:
        """Etapas de um run na ordem, com entrada, saída, duração e erro."""
        return _texto(fw.trace(projeto, run_id))

    @tool
    def cota(projeto: str) -> str:
        """Unidades da YouTube Data API gastas no projeto."""
        return _texto({"unidades": fw.cota(projeto)})

    # ------------------------------------------------------------ análise

    @tool
    def analisar(projeto: str, video: dict, canal_id: str) -> str:
        """Prevê um Short ainda não publicado de um canal da base. video: titulo, descricao,
        tags, duracao_s, publicar_em (ISO), fonte (arquivo local ou link, opcional: com ela
        roda o gancho e os atributos). Devolve faixa em 7 dias, timeline 1/3/7/14/30 dias,
        P(viral) e os fatores que mais pesaram."""
        return _texto(fw.analisar(projeto, video, canal_id))

    @tool
    def acompanhar(projeto: str, run_id: str, video_id: str) -> str:
        """Depois de publicar: liga a análise (run_id de analisar) ao vídeo publicado (id do
        YouTube) e guarda os números de agora. Use atualizar_acompanhamentos com o tempo."""
        return _texto(fw.acompanhar(projeto, run_id, video_id))

    @tool
    def atualizar_acompanhamentos(projeto: str) -> str:
        """Busca os números atuais dos vídeos acompanhados (1 unidade de cota por 50)."""
        return _texto(fw.atualizar_acompanhamentos(projeto))

    @tool
    def acompanhamentos(projeto: str) -> str:
        """Previsto × real dos vídeos publicados: cobertura da faixa de 80% e erro típico em
        produção. É a prova do modelo fora do teste."""
        return _texto(fw.acompanhamentos(projeto))

    @tool
    def comparar(projeto: str, video_a: dict, video_b: dict, canal_id: str) -> str:
        """A vs B: analisa duas versões do mesmo Short (ex.: dois títulos) no mesmo canal e
        diz qual deve performar melhor em 7 dias. Confiabilidade: acerto_pares do modelo."""
        return _texto(fw.comparar(projeto, video_a, video_b, canal_id))

    return ServidorGalaxies(servidor=mcp, jobs=jobs)


def main():
    from galaxies.ambiente import framework

    criar_servidor(framework(multimodal=True)).servidor.run("stdio")


if __name__ == "__main__":
    main()
