"""Relatório de avaliação em Markdown, gerado do banco do projeto. Reproduzível:

uv run python -m galaxies relatorio moda-beleza > docs/avaliacao.md
"""

import math

from galaxies.experimentos import Experimento


def _pct(v: float, sinal: bool = True) -> str:
    return f"{v:+.1%}" if sinal else f"{v:.1%}"


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _fator(mae: float) -> str:
    return f"{math.exp(mae):.2f}×"


def _linha(e: Experimento) -> str:
    r = e.resultado
    camadas = " + ".join(e.receita.camadas)
    extrator = f" ({e.receita.extrator.replace('@cf/meta/', '')})" if e.receita.extrator else ""
    marca = " **← ativo**" if e.status == "ativo" else ""
    return (
        f"| `{e.id}` | {camadas}{extrator}{marca} | {r.n_teste} | {r.modelo.mae:.3f} | "
        f"{r.controle_metadados.mae:.3f} | {r.baseline.mae:.3f} | {_pct(r.ganho)} | "
        f"{_pct(r.melhora_sobre_controle)} | {_pct(r.modelo.acerto_pares, False)} | "
        f"{_pct(r.cobertura_80, False) if r.cobertura_80 else '—'} |"
    )


def _curva_md(curvas: dict, idade_minima: float) -> list[str]:
    com_dados = {alvo: c for alvo, c in curvas.items() if c.faixas}
    if not com_dados:
        return [
            "## Crescimento observado",
            "",
            "- Ainda sem reobservação: rode `observar_recentes` uma vez por dia para medir como "
            "likes e views crescem com a idade do vídeo.",
            "",
        ]
    md = [
        "## Crescimento observado",
        "",
        "A coleta é uma foto só; os vídeos recentes foram reobservados dias depois "
        f"({_milhar(max(c.videos for c in com_dados.values()))} vídeos, intervalo mediano "
        f"{max(c.intervalo_mediano_dias for c in com_dados.values()):.1f} dias). A inclinação é "
        "quanto `log(1 + y)` cresce por `log(idade)`; 0 = parou de crescer. Abaixo de "
        f"{idade_minima:.0f} dias (idade que o modelo quase não viu no treino) a timeline recua "
        "pela curva.",
        "",
        "| faixa de idade | " + " | ".join(f"{a} (n)" for a in com_dados) + " |",
        "|---|" + "---|" * len(com_dados),
    ]
    faixas = sorted({(f.de_dias, f.ate_dias) for c in com_dados.values() for f in c.faixas})
    for de, ate in faixas:
        celulas = []
        for c in com_dados.values():
            f = next((f for f in c.faixas if (f.de_dias, f.ate_dias) == (de, ate)), None)
            celulas.append("—" if f is None else f"{f.inclinacao:.2f} ({f.n})")
        rotulo = f"{de:g}–{ate:g} dias" if ate < 1000 else f"{de:g}+ dias"
        md.append(f"| {rotulo} | " + " | ".join(celulas) + " |")
    return [*md, ""]


def gerar(
    projeto: str,
    config,
    resumo: dict,
    exps: list[Experimento],
    otimizacoes: list,
    curvas: dict | None = None,
    idade_minima: float = 0.0,
) -> str:
    md = [
        f"# Relatório de avaliação: {projeto}",
        "",
        f"Setores: {', '.join(config.setores)} · alvo padrão: {config.alvo} · modo: {config.modo}",
        "",
        "## Base",
        "",
        f"- {resumo['videos']:,} Shorts de {resumo['canais']} canais (YouTube Data API, "
        f"{resumo['cota_youtube']:,} unidades de cota gratuita).".replace(",", "."),
        f"- {resumo['ganchos']} ganchos (primeiros 5s) com frames, descrição, fala e embedding.",
        "- Atributos por extrator: "
        + ", ".join(f"{e} ({n})" for e, n in resumo["atributos_por_extrator"].items())
        + ".",
        "",
        "## Regras fixas (o agente não altera)",
        "",
        "- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.",
        "- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização "
        "compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.",
        "- Teto de 300 vídeos por canal (os mais recentes).",
        "- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas "
        "mesmas linhas.",
        "- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do "
        "mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.",
        "",
    ]
    for alvo in ("likes", "views"):
        do_alvo = [e for e in exps if e.alvo == alvo]
        if not do_alvo:
            continue
        ativo = next((e for e in do_alvo if e.status == "ativo"), None)
        md += [f"## {alvo.capitalize()}", ""]
        if ativo:
            r = ativo.resultado
            md += [
                f"**Modelo ativo `{ativo.id}`** ({' + '.join(ativo.receita.camadas)}):",
                "",
                f"- Erro {_pct(r.ganho)} menor que o baseline (MAE {r.modelo.mae:.3f} vs "
                f"{r.baseline.mae:.3f}; erro típico {_fator(r.modelo.mae)} vs "
                f"{_fator(r.baseline.mae)}).",
                f"- Acerta {_pct(r.modelo.acerto_pares, False)} dos pares A vs B no mesmo canal "
                "(acaso: 50%).",
                f"- A faixa de 80% contém {_pct(r.cobertura_80, False)} dos resultados reais no "
                f"teste (sem calibração: {_pct(r.cobertura_bruta, False)})."
                + (
                    f" A faixa provável de 50% contém {_pct(r.cobertura_50, False)}."
                    if r.cobertura_50
                    else ""
                ),
                f"- Hipótese registrada: {ativo.hipotese[:400]}",
                "",
            ]
        md += [
            "| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle "
            "| A vs B | faixa 80% |",
            "|---|---|---|---|---|---|---|---|---|---|",
            *[_linha(e) for e in sorted(do_alvo, key=lambda e: e.criado_em)],
            "",
        ]
    for alvo, tentativas in otimizacoes:
        md += [
            f"## Busca do agente ({alvo}, validação)",
            "",
            "| origem | camadas | melhora sobre o controle | n validação |",
            "|---|---|---|---|",
        ]
        for t in tentativas:
            obj = "—" if t["objetivo"] is None else _pct(t["objetivo"])
            camadas = " + ".join(t["receita"]["camadas"])
            t = {"n_validacao": 0, **t}
            md.append(f"| {t['origem']} | {camadas} | {obj} | {t['n_validacao']} |")
        md.append("")
    md += _curva_md(curvas or {}, idade_minima)
    md += [
        "## Limitações",
        "",
        "- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo "
        "serve para expectativa, triagem e priorizar testes, não para cravar números.",
        "- A faixa de 80% é calibrada no fim do treino e lá contém 80%; no teste (período mais "
        "recente) contém menos porque o período derivou: os vídeos novos rendem menos em "
        "relação à mediana histórica do canal do que o treino sugeria. Não é crescimento "
        "pendente (a curva observada mostra likes estáveis a partir de ~10 dias). O remédio é "
        "o ciclo: reotimizar com a base atualizada move o treino para perto do presente.",
        "- Sugestões vêm de associação aprendida na base, não de causa.",
        "- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas "
        "usam menos linhas de teste.",
        "",
    ]
    return "\n".join(md)
