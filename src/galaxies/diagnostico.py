"""Diagnóstico da base: o que um cientista de dados olharia antes de culpar o modelo.

Cada pista é uma evidência medida no banco (ruído do setor, controle fraco, canais rasos,
setores misturados, camadas incompletas, alvo alternativo, idade) com a ação que ela
sugere. Entra no retorno do `otimizar` e nas instruções do agente: a decisão continua
sendo dele (ou do humano), mas com os números na mesa.
"""

import duckdb
from pydantic import BaseModel

MIN_VIDEOS_CANAL = 30  # abaixo disso o canal quase não tem histórico nem teste
CONTROLE_FRACO = 0.08  # só-metadados a menos de 8% do baseline: o texto explica pouco
RUIDO_ALTO = 1.0  # desvio do log(1+y) dentro do canal; 0,96 em moda-beleza
DIFERENCA_SETORES = 0.05  # MAE entre setores difere mais que isso: avalie separar
CAMADA_INCOMPLETA = 0.9  # fração mínima da base coberta por uma camada "para todos"
GANCHOS_PARA_TESTAR = 2900  # ~300 linhas na validação para a camada de gancho


class Pista(BaseModel):
    tipo: str
    mensagem: str
    evidencia: dict = {}
    acao: str  # tool ou decisão sugerida


class Diagnostico(BaseModel):
    alvo: str
    pistas: list[Pista]
    base: dict = {}


def diagnosticar(
    banco: duckdb.DuckDBPyConnection, alvo: str, ativo=None, setores: list[str] | None = None
) -> Diagnostico:
    """`ativo`: experimento ativo (Experimento) para ler controle, baseline e segmentos."""
    um = lambda sql, *p: banco.execute(sql, list(p)).fetchone()[0]  # noqa: E731
    outro = "views" if alvo == "likes" else "likes"
    pistas: list[Pista] = []

    def ruido(coluna: str) -> float | None:
        v = um(
            f"SELECT avg(s) FROM (SELECT stddev(ln({coluna} + 1)) s FROM videos "
            f"WHERE {coluna} IS NOT NULL GROUP BY canal_id HAVING count(*) >= ?)",
            MIN_VIDEOS_CANAL,
        )
        return None if v is None else float(v)

    base = {
        "videos": um("SELECT count(*) FROM videos"),
        "canais": um("SELECT count(*) FROM canais"),
        "mediana_alvo": um(f"SELECT median({alvo}) FROM videos WHERE {alvo} IS NOT NULL"),
        "ruido_alvo": ruido(alvo),
        "ruido_outro": ruido(outro),
        "canais_rasos": um(
            "SELECT count(*) FROM (SELECT count(*) n FROM videos GROUP BY canal_id) WHERE n < ?",
            MIN_VIDEOS_CANAL,
        ),
        "com_texto": um("SELECT count(*) FROM texto_embedding"),
        "com_titulo": um(
            "SELECT count(DISTINCT video_id) FROM respostas WHERE atributo_id LIKE 'titulo_%'"
        ),
        "ganchos": um("SELECT count(*) FROM camada_bruta"),
    }

    # 1. ruído do setor: o teto do que qualquer modelo consegue
    if base["ruido_alvo"] is not None and base["ruido_alvo"] >= RUIDO_ALTO:
        pistas.append(
            Pista(
                tipo="setor_ruidoso",
                mensagem=f"{alvo} varia muito dentro do mesmo canal (desvio do log "
                f"{base['ruido_alvo']:.2f}; referência ~0,96): o teto de qualquer modelo é "
                "mais baixo neste setor. Compare o ganho sobre o controle, não só vs baseline.",
                evidencia={"ruido": round(base["ruido_alvo"], 3)},
                acao="interpretar",
            )
        )
    # 2. alvo alternativo mais estável
    if base["ruido_outro"] is not None and base["ruido_alvo"] is not None:
        if base["ruido_outro"] < base["ruido_alvo"] - 0.1:
            pistas.append(
                Pista(
                    tipo="alvo_alternativo",
                    mensagem=f"{outro} é mais estável dentro do canal que {alvo} "
                    f"({base['ruido_outro']:.2f} vs {base['ruido_alvo']:.2f}): vale um "
                    f"otimizar com alvo={outro}.",
                    evidencia={
                        "ruido_alvo": base["ruido_alvo"],
                        "ruido_outro": base["ruido_outro"],
                    },
                    acao=f"otimizar(alvo='{outro}')",
                )
            )
    # 3. canais rasos
    if base["canais"] and base["canais_rasos"] / base["canais"] >= 0.15:
        rasos = [
            c
            for (c,) in banco.execute(
                "SELECT canal_id FROM videos GROUP BY canal_id HAVING count(*) < ?",
                [MIN_VIDEOS_CANAL],
            ).fetchall()
        ]
        pistas.append(
            Pista(
                tipo="canais_rasos",
                mensagem=f"{base['canais_rasos']} de {base['canais']} canais têm menos de "
                f"{MIN_VIDEOS_CANAL} vídeos: sem histórico para a âncora e com 1–2 vídeos no "
                "teste, dominam os piores erros. Excluir (excluir) ou coletar mais deles.",
                evidencia={
                    "canais_rasos": base["canais_rasos"],
                    "canais": base["canais"],
                    "ids": rasos,
                },
                acao="excluir",
            )
        )
    # 4. camadas incompletas
    for nome, feitos, tool in (
        ("texto", base["com_texto"], "calcular_texto"),
        ("titulo", base["com_titulo"], "calcular_titulos"),
    ):
        if base["videos"] and feitos < CAMADA_INCOMPLETA * min(
            base["videos"], 300 * base["canais"]
        ):
            pistas.append(
                Pista(
                    tipo="camada_incompleta",
                    mensagem=f"camada {nome} cobre {feitos} de {base['videos']} vídeos: ela nem "
                    "entra na busca enquanto não existir para a base.",
                    evidencia={"camada": nome, "feitos": feitos, "videos": base["videos"]},
                    acao=tool,
                )
            )
    if base["ganchos"] < GANCHOS_PARA_TESTAR:
        pistas.append(
            Pista(
                tipo="ganchos_insuficientes",
                mensagem=f"{base['ganchos']} ganchos processados; a camada de gancho só vira "
                f"testável com ~{GANCHOS_PARA_TESTAR}. Modo leve (frames + SigLIP) + vizinhos "
                "chega lá sem cota; decisão de custo com o usuário.",
                evidencia={"ganchos": base["ganchos"], "precisa": GANCHOS_PARA_TESTAR},
                acao="processar_ganchos(leve=True)",
            )
        )
    # 5. o que o modelo ativo conta: controle fraco, setores misturados, idade
    if ativo is not None:
        r = ativo.resultado
        folga_controle = 1 - r.controle_metadados.mae / r.baseline.mae
        if folga_controle < CONTROLE_FRACO:
            pistas.append(
                Pista(
                    tipo="controle_fraco",
                    mensagem=f"só metadados fica {folga_controle:+.1%} do baseline (em moda e "
                    "beleza, ~14%): título, hora e duração explicam pouco aqui. O ganho real do "
                    f"modelo é sobre o controle ({r.melhora_sobre_controle:+.1%}); histórico do "
                    "canal e mais sinais de conteúdo pesam mais que ajuste fino.",
                    evidencia={"controle_vs_baseline": round(folga_controle, 4)},
                    acao="interpretar",
                )
            )
        por_setor = {s.chave: (s.mae, s.n) for s in r.segmentos.get("setor", [])}
        if len(por_setor) >= 2:
            maes = sorted(por_setor.items(), key=lambda kv: -kv[1][0])
            (pior, (mae_p, n_p)), (melhor, (mae_m, n_m)) = maes[0], maes[-1]
            if mae_p - mae_m >= DIFERENCA_SETORES and min(n_p, n_m) >= 100:
                pistas.append(
                    Pista(
                        tipo="setores_misturados",
                        mensagem=f"'{pior}' erra mais que '{melhor}' (MAE {mae_p:.2f} vs "
                        f"{mae_m:.2f}): um projeto por setor, ou canais-semente mais "
                        "homogêneos, pode render mais que misturar.",
                        evidencia={
                            "setores": {k: {"mae": v[0], "n": v[1]} for k, v in por_setor.items()}
                        },
                        acao="criar_projeto",
                    )
                )
        por_idade = {s.chave: (s.mae, s.n) for s in r.segmentos.get("idade", [])}
        jovem, maduro = por_idade.get("7-30d"), por_idade.get("30-90d")
        if jovem and maduro and jovem[0] - maduro[0] >= DIFERENCA_SETORES:
            pistas.append(
                Pista(
                    tipo="idade",
                    mensagem=f"vídeos de 7–30 dias erram mais (MAE {jovem[0]:.2f}) que os de "
                    f"30–90 ({maduro[0]:.2f}): deriva ou crescimento pendente. Reobservar mede "
                    "a curva; a âncora móvel segue a deriva.",
                    evidencia={"7-30d": jovem[0], "30-90d": maduro[0]},
                    acao="observar_recentes",
                )
            )
    sem_obs = um("SELECT count(*) FROM observacoes") == 0
    if sem_obs:
        pistas.append(
            Pista(
                tipo="sem_reobservacao",
                mensagem="nenhuma reobservação ainda: timeline abaixo da idade mínima é "
                "extrapolação. Uma rodada por dia (1 unidade por 50 vídeos).",
                acao="observar_recentes",
            )
        )
    return Diagnostico(
        alvo=alvo,
        pistas=pistas,
        base={k: (round(v, 3) if isinstance(v, float) else v) for k, v in base.items()},
    )
