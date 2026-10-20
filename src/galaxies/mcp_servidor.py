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
from pydantic import BaseModel, ValidationError

from galaxies import ErroGalaxies, Framework

INSTRUCOES = """Galaxies prevê a performance de YouTube Shorts de um setor.
Fluxo: criar_projeto → coletar (job) → processar_ganchos (job, opcional, caro) →
calcular_atributos (job) → treinar (job) → avaliar → analisar um vídeo novo.
Jobs devolvem job_id: acompanhe com status. Para auditar: runs, trace, erros, falhas.
Para adaptar ao setor: atributos / definir_atributos (perguntas choice, score ou noul)."""


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


def _json(valor):
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json")
    if isinstance(valor, list | tuple):
        return [_json(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    return valor


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
    def reprocessar(projeto: str, video_ids: list[str] | None = None) -> str:
        """Job: limpa falhas (todas, ou as dos vídeos pedidos) e refaz esses vídeos."""
        return _texto(jobs.iniciar("reprocessar", projeto, fw.reprocessar, projeto, video_ids))

    @tool
    def treinar(projeto: str, alvo: str | None = None) -> str:
        """Job: treina e avalia no split temporal fixo (likes ou views; padrão do projeto)."""
        return _texto(jobs.iniciar("treinar", projeto, fw.treinar, projeto, alvo))

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

    return ServidorGalaxies(servidor=mcp, jobs=jobs)


def main():
    from galaxies.ambiente import framework

    criar_servidor(framework(multimodal=True)).servidor.run("stdio")


if __name__ == "__main__":
    main()
