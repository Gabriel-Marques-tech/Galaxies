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
    args = cli.parse_args()

    fw = framework(multimodal=args.comando in ("processar-ganchos", "reprocessar"))
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
    elif args.comando == "erros":
        print(fw.erros(args.projeto, alvo=args.alvo).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
