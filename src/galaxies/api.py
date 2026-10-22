"""Adaptador HTTP (FastAPI) para a UI: o console do humano. Sem lógica própria.

Espelha as tools do MCP e acrescenta as ações que só o humano faz: aprovar ou rejeitar
promoções, revisar atributos e anotar erros.
"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from galaxies import ErroGalaxies, Framework, ProjetoNaoEncontrado, coleta
from galaxies.mcp_servidor import Jobs
from galaxies.serializar import para_json as _json

# Jobs de REDE rodam numa thread deste processo: o DuckDB aceita várias conexões no mesmo
# processo, então a UI continua lendo e escrevendo enquanto o job roda. Jobs de CPU (Laya,
# SigLIP, Whisper, LightGBM) NÃO: medido em 21/10, títulos pelo Laya dentro da API ficaram
# ~100× mais lentos que na linha de comando (torch numa thread secundária) e seguraram o
# lock do projeto por horas. Esses rodam pelo MCP ou pela CLI.
OPERACOES_EM_JOB = {
    "coletar",
    "observar_recentes",
    "atualizar_acompanhamentos",
    "descobrir_canais",
    "adicionar_canal",
}

JSONLivre = dict[str, Any]


def criar_app(fw: Framework) -> FastAPI:
    app = FastAPI(title="Galaxies", description="Console humano do framework Galaxies")
    jobs = Jobs()
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"])

    @app.exception_handler(ErroGalaxies)
    def _erro_de_dominio(_: Request, erro: ErroGalaxies):
        status = 404 if isinstance(erro, ProjetoNaoEncontrado) else 400
        return JSONResponse(status_code=status, content={"erro": str(erro)})

    @app.exception_handler(ValueError)
    def _valor_invalido(_: Request, erro: ValueError):
        return JSONResponse(status_code=400, content={"erro": str(erro)})

    # ------------------------------------------------------------ projeto

    @app.get("/projetos")
    def projetos() -> list[str]:
        return fw.listar_projetos()

    @app.post("/projetos")
    def criar_projeto(config: JSONLivre = Body()):
        """Cria o projeto. Coleta, ganchos e otimização ficam com o agente (MCP)."""
        return _json(fw.criar_projeto(config))

    @app.get("/projetos/{projeto}")
    def projeto(projeto: str):
        return _json(fw.obter_projeto(projeto))

    @app.get("/projetos/{projeto}/resumo")
    def resumo(projeto: str):
        return fw.resumo(projeto)

    @app.get("/projetos/{projeto}/insights")
    def insights(projeto: str, alvo: str | None = None):
        return fw.insights(projeto, alvo)

    @app.get("/projetos/{projeto}/miniaturas")
    def miniaturas(projeto: str, n: int = 12) -> list[str]:
        with fw._abrir_existente(projeto) as banco:  # leitura simples: não vira serviço
            return coleta.ids_para_miniaturas(banco, n)

    @app.get("/projetos/{projeto}/canais")
    def canais(projeto: str):
        return fw.canais(projeto)

    @app.post("/projetos/{projeto}/modo")
    def definir_modo(projeto: str, modo: str = Body(embed=True)):
        """Só o humano troca o modo do projeto."""
        return _json(fw.definir_modo(projeto, modo))

    @app.get("/projetos/{projeto}/atributos")
    def atributos(projeto: str):
        return _json(fw.atributos(projeto))

    # ------------------------------------------------------------ modelo

    @app.get("/projetos/{projeto}/experimentos")
    def experimentos(projeto: str, alvo: str | None = None):
        return _json(fw.experimentos(projeto, alvo))

    @app.post("/projetos/{projeto}/experimentos")
    def experimentar(
        projeto: str,
        receita: JSONLivre = Body(),
        hipotese: str = Body(""),
        alvo: str | None = Body(None),
    ):
        return _json(fw.experimentar(projeto, receita, hipotese, alvo))

    @app.post("/projetos/{projeto}/experimentos/{exp_id}/promover")
    def promover(projeto: str, exp_id: str):
        return _json(fw.promover(projeto, exp_id))

    @app.post("/projetos/{projeto}/experimentos/{exp_id}/decisao")
    def decidir(projeto: str, exp_id: str, aprovar: bool = Body(), nota: str = Body("")):
        """Só o humano: aprova ou rejeita uma promoção no modo cientista."""
        return _json(fw.decidir(projeto, exp_id, aprovar, nota))

    @app.get("/projetos/{projeto}/avaliacao")
    def avaliar(projeto: str, alvo: str | None = None):
        return _json(fw.avaliar(projeto, alvo))

    @app.post("/projetos/{projeto}/upload")
    async def upload(projeto: str, arquivo: UploadFile):
        """Guarda o Short enviado pela UI e devolve o caminho para usar como video.fonte."""
        fw.obter_projeto(projeto)  # valida o nome e a existência
        pasta = Path(fw.raiz) / "projetos" / projeto / "uploads"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = Path(arquivo.filename or "video.mp4").name
        destino = pasta / f"{uuid.uuid4().hex[:8]}-{nome}"
        destino.write_bytes(await arquivo.read())
        return {"fonte": str(destino), "nome": nome}

    @app.post("/projetos/{projeto}/analisar")
    def analisar(projeto: str, video: JSONLivre = Body(), canal_id: str = Body()):
        return _json(fw.analisar(projeto, video, canal_id))

    @app.post("/projetos/{projeto}/comparar")
    def comparar(
        projeto: str,
        video_a: JSONLivre = Body(),
        video_b: JSONLivre = Body(),
        canal_id: str = Body(),
    ):
        return _json(fw.comparar(projeto, video_a, video_b, canal_id))

    @app.get("/projetos/{projeto}/analises")
    def analises(projeto: str, limite: int = 50):
        return _json(fw.analises(projeto, limite))

    @app.post("/projetos/{projeto}/acompanhar")
    def acompanhar(projeto: str, run_id: str = Body(), video_id: str = Body()):
        return _json(fw.acompanhar(projeto, run_id, video_id))

    @app.post("/projetos/{projeto}/acompanhamentos/atualizar")
    def atualizar_acompanhamentos(projeto: str):
        return _json(fw.atualizar_acompanhamentos(projeto))

    @app.get("/projetos/{projeto}/acompanhamentos")
    def acompanhamentos(projeto: str):
        return _json(fw.acompanhamentos(projeto))

    @app.post("/projetos/{projeto}/observar-recentes")
    def observar_recentes(projeto: str, dias_max: float = 90):
        return _json(fw.observar_recentes(projeto, dias_max))

    @app.get("/projetos/{projeto}/crescimento")
    def crescimento(projeto: str, alvo: str | None = None):
        return _json(fw.crescimento(projeto, alvo))

    # ------------------------------------------------------------ auditoria

    @app.get("/projetos/{projeto}/runs")
    def runs(projeto: str):
        return _json(fw.runs(projeto))

    @app.get("/projetos/{projeto}/buscas")
    def buscas(projeto: str):
        return _json(fw.buscas(projeto))

    @app.get("/projetos/{projeto}/diagnostico")
    def diagnostico(projeto: str, alvo: str | None = None):
        return _json(fw.diagnostico(projeto, alvo))

    @app.get("/projetos/{projeto}/proximo-passo")
    def proximo_passo(projeto: str):
        return _json(fw.proximo_passo(projeto))

    @app.post("/projetos/{projeto}/jobs")
    def iniciar_job(projeto: str, operacao: str = Body(), argumentos: JSONLivre = Body(default={})):
        if operacao not in OPERACOES_EM_JOB:
            raise ErroGalaxies(
                f"operação '{operacao}' não roda como job (aceitas: {sorted(OPERACOES_EM_JOB)})"
            )
        fw.obter_projeto(projeto)
        return jobs.iniciar(operacao, projeto, getattr(fw, operacao), projeto, **argumentos)

    @app.get("/jobs")
    def listar_jobs():
        return _json(jobs.status())

    @app.get("/jobs/{job_id}")
    def status_job(job_id: str):
        return _json(jobs.status(job_id))

    @app.get("/projetos/{projeto}/andamento")
    def andamento(projeto: str):
        return _json(fw.andamento(projeto))

    @app.get("/projetos/{projeto}/runs/{run_id}/trace")
    def trace(projeto: str, run_id: str):
        return _json(fw.trace(projeto, run_id))

    @app.get("/projetos/{projeto}/erros")
    def erros(projeto: str, alvo: str | None = None):
        return _json(fw.erros(projeto, alvo))

    @app.get("/projetos/{projeto}/falhas")
    def falhas(projeto: str):
        return _json(fw.falhas(projeto))

    # ------------------------------------------------------------ portões humanos

    @app.get("/projetos/{projeto}/revisao/{atributo_id}")
    def amostra(projeto: str, atributo_id: str, n: int = 20, extrator: str | None = None):
        return _json(fw.amostra_para_revisao(projeto, atributo_id, n, extrator))

    @app.get("/projetos/{projeto}/revisao/{atributo_id}/contagem")
    def contagem_revisao(projeto: str, atributo_id: str, extrator: str | None = None):
        return _json(fw.contagem_revisao(projeto, atributo_id, extrator))

    @app.post("/projetos/{projeto}/revisao/{atributo_id}/{video_id}")
    def revisar(projeto: str, atributo_id: str, video_id: str, valor: Any = Body(embed=True)):
        fw.revisar(projeto, video_id, atributo_id, valor)
        return {"ok": True}

    @app.get("/projetos/{projeto}/concordancia")
    def concordancia(projeto: str, extrator: str | None = None):
        return _json(fw.concordancia(projeto, extrator))

    @app.get("/projetos/{projeto}/notas")
    def notas(projeto: str):
        return _json(fw.notas(projeto))

    @app.post("/projetos/{projeto}/notas")
    def anotar(projeto: str, video_id: str = Body(), tipo: str = Body(), nota: str = Body("")):
        return _json(fw.anotar_erro(projeto, video_id, tipo, nota))

    return app


def main():
    import uvicorn

    from galaxies.ambiente import framework

    uvicorn.run(criar_app(framework(multimodal=True)), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
