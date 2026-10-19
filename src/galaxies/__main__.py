"""CLI mínima até o MCP (#9) existir: `uv run python -m galaxies <comando> ...`."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from galaxies import Framework
from galaxies.adaptadores.youtube_api import YouTubeAPI
from galaxies.portas import Dependencias


def framework() -> Framework:
    load_dotenv()
    chave = os.environ.get("YOUTUBE_API_KEY")
    youtube = YouTubeAPI(chave) if chave else None
    raiz = os.environ.get("GALAXIES_DADOS", "data")
    return Framework(raiz=raiz, dependencias=Dependencias(youtube=youtube))


def main():
    cli = argparse.ArgumentParser(prog="galaxies")
    comandos = cli.add_subparsers(dest="comando", required=True)
    criar = comandos.add_parser("criar-projeto", help="cria projeto a partir de um JSON")
    criar.add_argument("config", type=Path)
    coletar = comandos.add_parser("coletar", help="coleta os Shorts dos canais-semente")
    coletar.add_argument("projeto")
    cota = comandos.add_parser("cota", help="unidades da YouTube API gastas")
    cota.add_argument("projeto")
    args = cli.parse_args()

    fw = framework()
    if args.comando == "criar-projeto":
        print(fw.criar_projeto(json.loads(args.config.read_text())).model_dump_json(indent=2))
    elif args.comando == "coletar":
        print(fw.coletar(args.projeto).model_dump_json(indent=2))
    elif args.comando == "cota":
        print(fw.cota(args.projeto))


if __name__ == "__main__":
    main()
