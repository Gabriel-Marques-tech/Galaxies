"""Relatório de avaliação em Markdown, gerado do banco do projeto. Reproduzível:

uv run python -m galaxies relatorio moda-beleza > docs/avaliacao.md
"""

import math

from galaxies.experimentos import Experimento


def _pct(v: float, sinal: bool = True) -> str:
    return f"{v:+.1%}" if sinal else f"{v:.1%}"


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


def gerar(projeto: str, config, resumo: dict, exps: list[Experimento], otimizacoes: list) -> str:
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
                f"teste (sem calibração: {_pct(r.cobertura_bruta, False)}).",
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
    md += [
        "## Limitações",
        "",
        "- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo "
        "serve para expectativa, triagem e priorizar testes, não para cravar números.",
        "- Sugestões vêm de associação aprendida na base, não de causa.",
        "- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas "
        "usam menos linhas de teste.",
        "",
    ]
    return "\n".join(md)
