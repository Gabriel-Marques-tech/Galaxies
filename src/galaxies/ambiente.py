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
        from galaxies.adaptadores.locais import (
            EmbedderDeTextoMiniLM,
            EmbedderSigLIP,
            TranscritorWhisper,
        )

        deps.extrator = ExtratorYtDlp()
        deps.transcritor = TranscritorWhisper()
        deps.embedder = EmbedderSigLIP()
        deps.texto = EmbedderDeTextoMiniLM()
        if chave := os.environ.get("GEMINI_API_KEY"):  # grátis (AI Studio): preferido
            modelo = os.environ.get("GEMINI_MODELO", "gemini-3.1-flash-lite")
            deps.descritor = DescritorGeminiDireto(chave, modelo)
        elif chave := os.environ.get("OPENROUTER_API_KEY"):
            modelo = os.environ.get("OPENROUTER_MODELO", "google/gemini-3.1-flash-lite")
            deps.descritor = DescritorOpenRouter(chave, modelo)
    tem_cloudflare = os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get(
        "CLOUDFLARE_API_TOKEN"
    )
    padrao = MODELO_LLM_PADRAO if tem_cloudflare else "laya"
    deps.jev = extrator_de_atributos(os.environ.get("ATRIBUTOS_MODELO") or padrao)
    deps.rapido = extrator_de_atributos("laya")  # local: título de todos os vídeos
    raiz = os.environ.get("GALAXIES_DADOS", "data")
    return Framework(raiz=raiz, dependencias=deps)


MODELO_LLM_PADRAO = "@cf/meta/llama-3.1-8b-instruct-fast"  # Workers AI, cota diária grátis


def extrator_de_atributos(modelo: str):
    """Para o gancho: um modelo @cf/* do Workers AI (padrão com credenciais da Cloudflare,
    grátis), typesafe/jev (pago) ou laya (local; responde "sim" demais, fica como reserva)."""
    if modelo == "laya":
        from galaxies.adaptadores.jev import JevLaya

        return JevLaya()
    conta, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not (conta and token):
        return None
    from galaxies.adaptadores.jev import JevCloudflare, JevWorkersAI

    if modelo == "typesafe/jev":
        return JevCloudflare(conta, token)
    return JevWorkersAI(conta, token, modelo)
