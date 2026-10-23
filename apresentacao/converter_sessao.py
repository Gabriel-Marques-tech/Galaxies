"""Converte a transcrição real do Gemini CLI (--output-format stream-json) no roteiro que o
deck reproduz: prompt do usuário, tool calls do Stars (com argumentos resumidos), resultados
resumidos e a resposta final. Nada é inventado: só se comprime o que aconteceu.

Uso: uv run python apresentacao/converter_sessao.py apresentacao/sessao-gemini-2.jsonl
Saída: apresentacao/sessao-gemini.json (lido pelo index.html) e o bloco inline no index.html.
"""

import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).parent
IGNORAR = {"update_topic", "google_web_search", "run_shell_command"}  # ferramentas internas do CLI (sleep etc.), não do Stars


def resumir_args(p: dict) -> str:
    partes = []
    for k, v in p.items():
        if k == "config" and isinstance(v, dict):
            partes.append(f"nome={v.get('nome')!r}, setores={v.get('setores')}, alvo={v.get('alvo')!r}")
        elif isinstance(v, (int, float, str)):
            s = str(v)
            partes.append(f"{k}={s[:40]!r}" if isinstance(v, str) else f"{k}={s}")
    return ", ".join(partes)


def resumir_saida(o: str) -> str:
    o = (o or "").strip()
    try:
        d = json.loads(o)
    except Exception:
        return o.replace("\n", " ")[:160]
    if isinstance(d, list):
        return f"{len(d)} itens" + (f": {', '.join(map(str, d[:3]))}…" if d else "")
    if isinstance(d, dict):
        if isinstance(d.get("resultado"), dict) and d.get("status") == "ok":
            r = d["resultado"]
            if r.get("experimentos") or r.get("promovido") or r.get("motivo"):
                return (f"status={d['status']!r}, " + resumir_saida(json.dumps(r)))[:220]
            if r.get("tentativas") and not r.get("experimentos"):
                erros = [t.get("erro") for t in r["tentativas"] if t.get("erro")]
                return f"status='ok', nenhum modelo: {erros[0][:150]}" if erros else "status='ok', nenhum modelo"
        chaves = ("job_id", "status", "videos_novos", "acao", "motivo", "calculados", "promovido", "nome")
        itens = [f"{k}={d[k]!r}" if isinstance(d[k], str) else f"{k}={d[k]}" for k in chaves if k in d]
        if "experimentos" in d and d["experimentos"]:
            e = d["experimentos"][0]
            r = e.get("resultado", {})
            itens.append(f"ganho={r.get('ganho', 0):+.1%} vs média do canal, A vs B {r.get('modelo', {}).get('acerto_pares', 0):.1%}, faixa 80% cobre {r.get('cobertura_80', 0):.0%}")
        if "pistas" in d and d["pistas"]:
            itens.append("pistas: " + "; ".join(p.get("tipo", "") for p in d["pistas"][:4]))
        return ", ".join(itens)[:200] or o[:120]
    return o[:120]


def converter(caminho: Path) -> list[dict]:
    eventos = [json.loads(l) for l in caminho.read_text().splitlines() if l.strip().startswith("{")]
    chamadas: dict[str, dict] = {}
    roteiro: list[dict] = []
    for e in eventos:
        t = e.get("type")
        if t == "message" and e.get("role") == "user" and not roteiro:
            texto = e["content"].strip().split("\n")[0].strip()
            roteiro.append({"cena": "prompt", "tipo": "prompt", "texto": texto[:230] + ("…" if len(texto) > 230 else "")})
        elif t == "tool_use":
            nome = e["tool_name"].replace("mcp_stars_", "")
            if e["tool_name"] in IGNORAR or nome in IGNORAR:
                continue
            chamadas[e["tool_id"]] = nome
            roteiro.append({"cena": "tools", "tipo": "tool", "texto": f"{nome}({resumir_args(e.get('parameters') or {})})", "espera": 650})
        elif t == "tool_result" and e.get("tool_id") in chamadas:
            nome = chamadas[e["tool_id"]]
            if e.get("status") == "error":
                msg = str(e.get("error") or e.get("output") or "")
                m = re.search(r"text\W+([^\"]{10,140})", msg)
                roteiro.append({"cena": "tools", "tipo": "dim", "texto": f"✗ {nome}: {(m.group(1) if m else msg)[:140]}", "espera": 500})
            else:
                roteiro.append({"cena": "tools", "tipo": "ok", "texto": f"{nome} → {resumir_saida(e.get('output', ''))}", "espera": 550})
        elif t == "message" and e.get("role") == "assistant" and e.get("content", ""):
            if roteiro and roteiro[-1]["tipo"] == "resposta":
                roteiro[-1]["texto"] = (roteiro[-1]["texto"] + e["content"])[:900]
            else:
                roteiro.append({"cena": "final", "tipo": "resposta", "texto": e["content"].lstrip()[:900]})
    # cena da UI: a partir do primeiro otimizar/diagnostico concluído
    for p in roteiro:
        if p["tipo"] in ("tool", "ok") and ("otimizar" in p["texto"] or "diagnostico" in p["texto"]):
            p["cena"] = "ui"
    # polling (status / proximo_passo repetidos enquanto um job roda) vira um bloco só com ×N,
    # mantendo o último resultado de cada um; o roteiro fica com o ritmo da sessão, não com os sleeps
    compacto: list[dict] = []
    nome = lambda p: p["texto"].split("(")[0].split(" →")[0].strip()
    POLL = ("status", "proximo_passo")
    i = 0
    while i < len(roteiro):
        p = roteiro[i]
        if p["tipo"] == "tool" and nome(p) in POLL:
            j = i
            bloco: list[dict] = []
            while j < len(roteiro) and roteiro[j]["tipo"] in ("tool", "ok") and nome(roteiro[j]) in POLL:
                bloco.append(roteiro[j]); j += 1
            tools = [b for b in bloco if b["tipo"] == "tool"]
            if len(tools) > 1:
                ultimo = {}
                for b in bloco:
                    ultimo[(b["tipo"], nome(b))] = b
                for n in POLL:
                    t, ok = ultimo.get(("tool", n)), ultimo.get(("ok", n))
                    if t:
                        vezes = sum(1 for b in tools if nome(b) == n)
                        compacto.append({**t, "texto": t["texto"] + (f" ×{vezes}" if vezes > 1 else ""), "espera": 900})
                        if ok:
                            compacto.append(dict(ok))
                i = j
                continue
        compacto.append(dict(p)); i += 1
    return compacto


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / "sessao-gemini.jsonl"
    roteiro = converter(origem)
    destino = AQUI / "sessao-gemini.json"
    destino.write_text(json.dumps(roteiro, ensure_ascii=False, indent=1))
    index = AQUI / "index.html"
    html = index.read_text()
    inline = "const SESSAO_INLINE = " + json.dumps(roteiro, ensure_ascii=False) + ";"
    if "const SESSAO_INLINE" in html:
        html = re.sub(r"const SESSAO_INLINE = .*?;\n", inline + "\n", html, count=1, flags=re.S)
    else:
        html = html.replace("let roteiro = null", inline + "\nlet roteiro = null", 1)
    html = html.replace(
        "try { roteiro = await (await fetch('sessao-gemini.json')).json() } catch { roteiro = ROTEIRO_RESERVA }",
        "roteiro = SESSAO_INLINE.length ? SESSAO_INLINE : ROTEIRO_RESERVA",
    )
    index.write_text(html)
    print(f"{len(roteiro)} passos; primeiro: {roteiro[0]['texto'][:60] if roteiro else '-'}")
    for p in roteiro[:12]:
        print(" ", p["cena"], p["tipo"], p["texto"][:90])
