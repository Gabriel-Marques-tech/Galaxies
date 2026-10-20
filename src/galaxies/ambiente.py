"""Monta o Framework com os adaptadores reais, a partir do .env."""

import os

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
        from galaxies.adaptadores.gemini import DescritorGeminiDireto, DescritorOpenRouter
        from galaxies.adaptadores.locais import EmbedderSigLIP, TranscritorWhisper

        deps.extrator = ExtratorYtDlp()
        deps.transcritor = TranscritorWhisper()
        deps.embedder = EmbedderSigLIP()
        if chave := os.environ.get("GEMINI_API_KEY"):  # grátis (AI Studio): preferido
            modelo = os.environ.get("GEMINI_MODELO", "gemini-3.1-flash-lite")
            deps.descritor = DescritorGeminiDireto(chave, modelo)
        elif chave := os.environ.get("OPENROUTER_API_KEY"):
            modelo = os.environ.get("OPENROUTER_MODELO", "google/gemini-3.1-flash-lite")
            deps.descritor = DescritorOpenRouter(chave, modelo)
    conta, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if conta and token:
        from galaxies.adaptadores.jev import JevCloudflare, JevWorkersAI

        # Jev de verdade é pago (saldo no gateway); o padrão é um LLM grátis do Workers AI.
        modelo = os.environ.get("ATRIBUTOS_MODELO", "@cf/meta/llama-3.1-8b-instruct-fast")
        if modelo == "typesafe/jev":
            deps.jev = JevCloudflare(conta, token)
        else:
            deps.jev = JevWorkersAI(conta, token, modelo)
    raiz = os.environ.get("GALAXIES_DADOS", "data")
    return Framework(raiz=raiz, dependencias=deps)
