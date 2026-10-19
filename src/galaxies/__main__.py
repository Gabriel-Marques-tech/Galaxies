"""CLI mínima até o MCP (#9) existir: `uv run python -m galaxies <comando> ...`."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from galaxies import Framework
from galaxies.adaptadores.youtube_api import YouTubeAPI
from galaxies.portas import Dependencias


def framework(multimodal: bool = False) -> Framework:
    load_dotenv()
    deps = Dependencias()
    if chave := os.environ.get("YOUTUBE_API_KEY"):
        deps.youtube = YouTubeAPI(chave)
    if multimodal:
        from galaxies.adaptadores.gancho import ExtratorYtDlp
        from galaxies.adaptadores.gemini import DescritorOpenRouter
        from galaxies.adaptadores.locais import EmbedderSigLIP, TranscritorWhisper

        deps.extrator = ExtratorYtDlp()
        deps.transcritor = TranscritorWhisper()
        deps.embedder = EmbedderSigLIP()
        if chave := os.environ.get("OPENROUTER_API_KEY"):
            modelo = os.environ.get("OPENROUTER_MODELO", "google/gemini-2.5-flash-lite")
            deps.descritor = DescritorOpenRouter(chave, modelo)
    raiz = os.environ.get("GALAXIES_DADOS", "data")
    return Framework(raiz=raiz, dependencias=deps)


def main():
    cli = argparse.ArgumentParser(prog="galaxies")
    comandos = cli.add_subparsers(dest="comando", required=True)
    criar = comandos.add_parser("criar-projeto", help="cria projeto a partir de um JSON")
    criar.add_argument("config", type=Path)
    coletar = comandos.add_parser("coletar", help="coleta os Shorts dos canais-semente")
    coletar.add_argument("projeto")
    cota = comandos.add_parser("cota", help="unidades da YouTube API gastas")
    cota.add_argument("projeto")
    ganchos = comandos.add_parser("processar-ganchos", help="camada bruta do gancho")
    ganchos.add_argument("projeto")
    ganchos.add_argument("--limite-por-canal", type=int, default=None)
    falhas = comandos.add_parser("falhas", help="vídeos que falharam no pipeline")
    falhas.add_argument("projeto")
    args = cli.parse_args()

    fw = framework(multimodal=args.comando == "processar-ganchos")
    if args.comando == "criar-projeto":
        print(fw.criar_projeto(json.loads(args.config.read_text())).model_dump_json(indent=2))
    elif args.comando == "coletar":
        print(fw.coletar(args.projeto).model_dump_json(indent=2))
    elif args.comando == "cota":
        print(fw.cota(args.projeto))
    elif args.comando == "processar-ganchos":
        resumo = fw.processar_ganchos(args.projeto, limite_por_canal=args.limite_por_canal)
        print(resumo.model_dump_json(indent=2))
    elif args.comando == "falhas":
        for falha in fw.falhas(args.projeto):
            print(falha.model_dump_json())


if __name__ == "__main__":
    main()
