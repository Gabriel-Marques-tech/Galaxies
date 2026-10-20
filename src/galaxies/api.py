"""Adaptador HTTP (FastAPI) para a UI: o console do humano. Sem lógica própria.

Espelha as tools do MCP e acrescenta as ações que só o humano faz: aprovar ou rejeitar
promoções, revisar atributos e anotar erros.
"""

from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from galaxies import ErroGalaxies, Framework, ProjetoNaoEncontrado
from galaxies.serializar import para_json as _json

JSONLivre = dict[str, Any]


def criar_app(fw: Framework) -> FastAPI:
    app = FastAPI(title="Galaxies", description="Console humano do framework Galaxies")
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

    @app.get("/projetos/{projeto}")
    def projeto(projeto: str):
        return _json(fw.obter_projeto(projeto))

    @app.get("/projetos/{projeto}/resumo")
    def resumo(projeto: str):
        return fw.resumo(projeto)

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

    # ------------------------------------------------------------ auditoria

    @app.get("/projetos/{projeto}/runs")
    def runs(projeto: str):
        return _json(fw.runs(projeto))

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
