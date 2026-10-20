"""CLI mínima até o MCP (#9) existir: `uv run python -m galaxies <comando> ...`."""

import argparse
import json
from datetime import date
from pathlib import Path

from galaxies.ambiente import framework


def main():
    cli = argparse.ArgumentParser(prog="galaxies")
    comandos = cli.add_subparsers(dest="comando", required=True)
    criar = comandos.add_parser("criar-projeto", help="cria projeto a partir de um JSON")
    criar.add_argument("config", type=Path)
    coletar = comandos.add_parser("coletar", help="coleta os Shorts dos canais-semente")
    coletar.add_argument("projeto")
    coletar.add_argument("--so-faltantes", action="store_true", help="retoma coleta interrompida")
    cota = comandos.add_parser("cota", help="unidades da YouTube API gastas")
    cota.add_argument("projeto")
    ganchos = comandos.add_parser("processar-ganchos", help="camada bruta do gancho")
    ganchos.add_argument("projeto")
    ganchos.add_argument("--limite-por-canal", type=int, default=None)
    ganchos.add_argument("--canais", nargs="*", default=None, help="ids de canal (UC...)")
    ganchos.add_argument("--desde", type=date.fromisoformat, default=None, help="AAAA-MM-DD")
    texto = comandos.add_parser("calcular-texto", help="embedding de título e descrição")
    texto.add_argument("projeto")
    calcular = comandos.add_parser("calcular-atributos", help="pergunta os atributos ao Jev")
    calcular.add_argument("projeto")
    definir = comandos.add_parser("definir-atributos", help="substitui atributos (JSON)")
    definir.add_argument("projeto")
    definir.add_argument("arquivo", type=Path)
    treinar = comandos.add_parser("treinar", help="treina e avalia (split temporal fixo)")
    treinar.add_argument("projeto")
    treinar.add_argument("--alvo", choices=["likes", "views"], default=None)
    falhas = comandos.add_parser("falhas", help="vídeos que falharam no pipeline")
    falhas.add_argument("projeto")
    repro = comandos.add_parser("reprocessar", help="limpa falhas e refaz os vídeos")
    repro.add_argument("projeto")
    repro.add_argument("video_ids", nargs="*", help="vazio = todas as falhas")
    excluir = comandos.add_parser("excluir", help="tira vídeos ou canais da base")
    excluir.add_argument("projeto")
    excluir.add_argument("--videos", nargs="*", default=[])
    excluir.add_argument("--canais", nargs="*", default=[])
    erros = comandos.add_parser("erros", help="falhas do pipeline e onde o modelo erra")
    erros.add_argument("projeto")
    erros.add_argument("--alvo", choices=["likes", "views"], default=None)
    experimentar = comandos.add_parser("experimentar", help="treina uma receita (JSON)")
    experimentar.add_argument("projeto")
    experimentar.add_argument("receita", help='ex.: {"camadas": ["metadados"]}')
    experimentar.add_argument("--hipotese", default="")
    experimentar.add_argument("--alvo", choices=["likes", "views"], default=None)
    lista = comandos.add_parser("experimentos", help="lista experimentos")
    lista.add_argument("projeto")
    promover = comandos.add_parser("promover", help="promove um experimento")
    promover.add_argument("projeto")
    promover.add_argument("exp_id")
    rel = comandos.add_parser("relatorio", help="relatório de avaliação em Markdown")
    rel.add_argument("projeto")
    otimizar = comandos.add_parser("otimizar", help="busca a melhor receita na validação")
    otimizar.add_argument("projeto")
    otimizar.add_argument("--alvo", choices=["likes", "views"], default=None)
    otimizar.add_argument("--orcamento", type=int, default=16)
    otimizar.add_argument("--paciencia", type=int, default=6)
    ciclo = comandos.add_parser("ciclo-automatico", help="otimiza e promove (modo automático)")
    ciclo.add_argument("projeto")
    ciclo.add_argument("--alvo", choices=["likes", "views"], default=None)
    args = cli.parse_args()

    fw = framework(
        multimodal=args.comando in ("processar-ganchos", "reprocessar", "calcular-texto")
    )
    if args.comando == "criar-projeto":
        print(fw.criar_projeto(json.loads(args.config.read_text())).model_dump_json(indent=2))
    elif args.comando == "coletar":
        print(fw.coletar(args.projeto, so_faltantes=args.so_faltantes).model_dump_json(indent=2))
    elif args.comando == "cota":
        print(fw.cota(args.projeto))
    elif args.comando == "processar-ganchos":
        resumo = fw.processar_ganchos(
            args.projeto,
            limite_por_canal=args.limite_por_canal,
            canais=args.canais,
            desde=args.desde,
        )
        print(resumo.model_dump_json(indent=2))
    elif args.comando == "calcular-texto":
        print(fw.calcular_texto(args.projeto))
    elif args.comando == "calcular-atributos":
        print(fw.calcular_atributos(args.projeto).model_dump_json(indent=2))
    elif args.comando == "definir-atributos":
        definidos = fw.definir_atributos(args.projeto, json.loads(args.arquivo.read_text()))
        print(f"{len(definidos)} atributos definidos")
    elif args.comando == "treinar":
        print(fw.treinar(args.projeto, alvo=args.alvo).model_dump_json(indent=2))
    elif args.comando == "falhas":
        for falha in fw.falhas(args.projeto):
            print(falha.model_dump_json())
    elif args.comando == "reprocessar":
        print(fw.reprocessar(args.projeto, args.video_ids or None).model_dump_json(indent=2))
    elif args.comando == "excluir":
        fw.excluir(args.projeto, video_ids=args.videos, canais=args.canais)
    elif args.comando == "experimentar":
        exp = fw.experimentar(args.projeto, json.loads(args.receita), args.hipotese, args.alvo)
        print(exp.model_dump_json(indent=2, exclude={"resultado": {"piores", "segmentos"}}))
    elif args.comando == "experimentos":
        for e in fw.experimentos(args.projeto):
            r = e.resultado
            print(
                f"{e.id} {e.alvo:5} {e.status:20} ganho={r.ganho:+.3f} "
                f"mae={r.modelo.mae:.3f} (base {r.baseline.mae:.3f}, só meta "
                f"{r.controle_metadados.mae:.3f}) sp={r.modelo.spearman_no_canal:.3f} "
                f"n_teste={r.n_teste} {e.receita.camadas}"
            )
    elif args.comando == "promover":
        print(fw.promover(args.projeto, args.exp_id).status)
    elif args.comando == "relatorio":
        print(fw.relatorio(args.projeto))
    elif args.comando == "otimizar":
        ciclo = fw.otimizar(args.projeto, args.alvo, args.orcamento, args.paciencia)
        for t in ciclo.tentativas:
            obj = "   —   " if t["objetivo"] is None else f"{t['objetivo']:+.2%}"
            print(f"{obj}  {t['origem']:40} {t['receita']['camadas']} {t['erro'][:60]}")
        for e in ciclo.experimentos:
            r = e.resultado
            print(
                f"\nescolhida {e.id}: teste ganho {r.ganho:+.1%} vs baseline, "
                f"{r.melhora_sobre_controle:+.1%} vs controle, pares {r.modelo.acerto_pares:.1%}, "
                f"faixa 80% cobre {r.cobertura_80:.0%} · promovido={ciclo.promovido}"
            )
    elif args.comando == "ciclo-automatico":
        resultado = fw.ciclo_automatico(args.projeto, alvo=args.alvo)
        print(json.dumps({"promovido": resultado.promovido, "pulados": resultado.pulados}))
    elif args.comando == "erros":
        print(fw.erros(args.projeto, alvo=args.alvo).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
