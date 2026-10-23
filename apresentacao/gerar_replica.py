"""Gera replica.html: as telas principais do console com os dados reais embutidos (dados.json),
roteadas por hash igual à UI (#projetos, #inicio, #modelos, #analisar, #analises). Reserva do
deck quando a API não está de pé."""
import json
from pathlib import Path

AQUI = Path(__file__).parent
dados = json.loads((AQUI / "dados.json").read_text())
LOGO = (AQUI.parent / "ui" / "public" / "logo.svg").read_text()

html = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Stars · réplica</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Material+Symbols+Rounded&display=swap" rel="stylesheet">
<style>
:root{--bg:#0b0d14;--s1:#131726;--s2:#1a1f31;--t:#eef0f6;--sub:#9aa0b4;--p:#4285f4;--roxo:#9b72cb;--bom:#5fd39a;--ruim:#f08080;--c:rgba(255,255,255,.1)}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--t);font:14px/1.45 Inter,system-ui,sans-serif;height:100vh;display:flex;overflow:hidden}
.ms{font-family:'Material Symbols Rounded';font-size:20px;vertical-align:middle}
aside{width:200px;padding:16px 10px;border-right:1px solid var(--c);display:flex;flex-direction:column;gap:4px;background:var(--s1)}
aside .marca{display:flex;align-items:center;gap:8px;font-weight:600;font-size:16px;padding:6px 8px 14px}aside .marca svg{width:24px;height:24px}
aside a{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:999px;color:var(--t);text-decoration:none;font-size:13.5px}aside a.on{background:#243055;color:#cfe0ff}
main{flex:1;overflow:auto;padding:22px 28px}h1{font-size:22px;font-weight:400;margin-bottom:14px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--c);border-radius:8px;padding:4px 10px;font-size:12px;color:var(--sub)}.chip.ok{background:#17322a;color:var(--bom);border-color:transparent}
.grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:14px}
.cartao{background:var(--s2);border:1px solid var(--c);border-radius:16px;padding:16px}.cartao h3{font-size:14px;font-weight:500;margin-bottom:6px}
.met .v{font-size:30px;font-weight:500;margin:6px 0 2px}.met .r{font-size:12px;color:var(--sub);text-transform:uppercase;letter-spacing:.06em}.met .d{font-size:12px;color:var(--sub)}
.sub{color:var(--sub)}.bom{color:var(--bom)}.ruim{color:var(--ruim)}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
table{width:100%;border-collapse:collapse;font-size:13px}th{color:var(--sub);font-weight:500;text-align:left;padding:8px 10px;font-size:12px}td{padding:10px;border-top:1px solid var(--c)}td.n{text-align:right;font-variant-numeric:tabular-nums}
.barra{height:8px;border-radius:999px;background:linear-gradient(90deg,#4285f4,#9b72cb);display:inline-block;vertical-align:middle;margin-right:8px}
.feed{display:flex;gap:16px;overflow:auto;padding:6px 2px 12px}.cp{flex:0 0 220px;height:280px;border-radius:20px;background:var(--s2);border:1px solid var(--c);padding:18px;display:flex;flex-direction:column;position:relative;overflow:hidden}
.cp .mos{position:absolute;inset:0;display:grid;grid-template-columns:repeat(3,1fr);gap:3px;padding:3px;filter:blur(2px) grayscale(.45) brightness(.8)}.cp .mos img{width:100%;height:100%;object-fit:cover;border-radius:6px}
.cp .mos::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(26,31,49,.15),rgba(26,31,49,.9) 78%,#1a1f31)}.cp>*:not(.mos){position:relative}
.cp .nome{font-size:16px;font-weight:500;margin-top:40px}.cp .g{margin-top:auto;font-size:28px;font-weight:500}.cp.on{outline:2px solid var(--p);box-shadow:0 0 26px rgba(66,133,244,.35)}
.lin{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-top:1px solid var(--c);font-size:13px}.rot{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--sub);margin:12px 0 4px}
.aval{border:1px solid rgba(66,133,244,.5);box-shadow:0 0 22px rgba(66,133,244,.18)}
.short{width:220px;height:390px;border-radius:22px;background:#0f1322;border:1px dashed var(--c);display:flex;align-items:center;justify-content:center;color:var(--sub);flex-direction:column;gap:8px}
.duas{display:grid;grid-template-columns:240px 1fr;gap:18px}
.ap{opacity:0;transform:translateY(10px);animation:ap .5s forwards}@keyframes ap{to{opacity:1;transform:none}}
</style></head><body>
<aside><div class="marca">__LOGO__ Stars</div>
<a href="#projetos" data-t="projetos"><span class="ms">grid_view</span>Projetos</a>
<a href="#inicio" data-t="inicio"><span class="ms">home</span>Início</a>
<a href="#analisar" data-t="analisar"><span class="ms">auto_awesome</span>Analisar vídeo</a>
<a href="#analises" data-t="analises"><span class="ms">history</span>Vídeos analisados</a>
<a href="#modelos" data-t="modelos"><span class="ms">model_training</span>Modelos</a>
<a href="#revisao"><span class="ms">fact_check</span>Revisão de atributos</a>
<a href="#erros"><span class="ms">troubleshoot</span>Erros</a>
<a href="#trace"><span class="ms">account_tree</span>Trace</a></aside>
<main id="main"></main>
<script id="dados" type="application/json">__DADOS__</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent)
let projeto = 'moda-beleza'
const k = (v) => v >= 1000 ? (v/1000).toFixed(v >= 10000 ? 0 : 1).replace('.', ',') + ' mil' : String(Math.round(v))
const pct = (v, s = true) => (s && v > 0 ? '+' : '') + (v * 100).toFixed(1).replace('.', ',') + '%'
const receita = (r) => r.camadas.join(' + ') + (r.ancora === 'movel' ? ' · âncora móvel' : '')
const ativo = (p, alvo) => (D[p].experimentos.find((e) => e.status === 'ativo' && e.alvo === alvo) || D[p].experimentos.find((e) => e.status === 'ativo'))
const telas = {
  projetos() {
    return `<h1>Projetos</h1><p class="sub" style="margin-bottom:10px">Role para escolher o projeto. Arraste um card para o lado para criar outro.</p><div class="feed">` +
      D.projetos.map((p) => { const a = ativo(p, D[p].config.alvo); return `<div class="cp ${p === projeto ? 'on' : ''}" onclick="projeto='${p}';location.hash='#inicio'"><div class="mos">${(D[p].miniaturas || []).slice(0, 9).map((id) => `<img src="https://i.ytimg.com/vi/${id}/mqdefault.jpg" alt="">`).join('')}</div><span class="ms" style="font-size:34px;color:#8ab4ff">smart_display</span><div class="nome">${p}</div><div class="sub">${D[p].experimentos.length} experimentos</div><div class="g">${a ? '−' + pct(a.resultado.ganho, false) : '—'}</div><div class="sub">mais preciso que a média do canal</div></div>` }).join('') +
      `</div><div class="cartao"><div class="rot">O que funciona em ${projeto}</div>` + (D[projeto].insights.fatores || []).slice(0, 5).map((f) => `<div class="lin"><span class="mono">${f.fator}</span><b class="${f.efeito >= 0 ? 'bom' : 'ruim'}">${pct(f.efeito)}</b></div>`).join('') + `</div>`
  },
  inicio() {
    const r = D[projeto].resumo, a = ativo(projeto, D[projeto].config.alvo), pp = D[projeto]['proximo-passo'], cv = D[projeto].crescimento, ac = D[projeto].acompanhamentos
    const est = (cv.faixas || []).find((f) => f.inclinacao === 0)
    return `<h1>Visão geral <span class="chip">${D[projeto].config.modo === 'cientista' ? 'Data Scientist' : 'Automático'} · ${D[projeto].config.alvo}</span></h1><div class="grade">
      <div class="cartao met"><div class="r">Shorts na base</div><div class="v">${k(r.videos)}</div><div class="d">${r.canais} canais · ${D[projeto].config.setores.join(', ')}</div></div>
      <div class="cartao met"><div class="r">Modelo ativo</div><div class="v">${a ? '−' + pct(a.resultado.ganho, false) : '—'}</div><div class="d">${a ? 'mais preciso que a média do canal · ' + receita(a.receita) : 'nenhum'}</div></div>
      <div class="cartao met"><div class="r">Experimentos</div><div class="v">${r.experimentos}</div><div class="d">${r.runs} execuções</div></div>
      <div class="cartao met"><div class="r">Em produção</div><div class="v">${ac.n ? Math.round(ac.cobertura * 100) + '%' : '—'}</div><div class="d">${ac.n ? ac.n + ' vídeo(s) · dentro da faixa quase certa' : 'nenhum vídeo acompanhado'}</div></div>
      <div class="cartao met"><div class="r">Curva de crescimento</div><div class="v">${cv.videos ? k(cv.videos) : '—'}</div><div class="d">${cv.videos ? 'vídeos reobservados · ' + cv.alvo + (est ? ' estabilizam a partir de ~' + est.de_dias + ' dias' : '') : 'sem reobservação'}</div></div></div>
      <div class="cartao ${pp.certeza === 'ambiguo' ? '' : 'aval'}"><h3><span class="ms">${pp.certeza === 'ambiguo' ? 'help' : 'route'}</span> Próximo passo: <span class="mono">${pp.acao}</span></h3><p class="sub">${pp.motivo}</p>${pp.alternativas.length ? `<p class="sub" style="margin-top:4px">ou: ${pp.alternativas.join(', ')}</p>` : ''}<p class="sub" style="margin-top:8px">${pp.certeza === 'ambiguo' ? 'Decisão de custo ou escopo: o agente pergunta antes de agir.' : 'Deduzido do estado do projeto por regra; o agente segue sem perguntar.'}</p></div>
      <div class="cartao" style="margin-top:12px"><h3>Diagnóstico</h3>${D[projeto].diagnostico.pistas.slice(0, 5).map((p) => `<div class="lin"><span><b class="mono">${p.tipo}</b> · ${p.mensagem.slice(0, 120)}…</span><span class="mono sub">→ ${p.acao}</span></div>`).join('')}</div>`
  },
  modelos() {
    const ex = [...D[projeto].experimentos].reverse(), maior = Math.max(...ex.map((e) => Math.max(e.resultado.ganho, 0)), .01), b = (D[projeto].buscas || [])[0]
    const medidas = b ? b.tentativas.filter((t) => t.objetivo !== null) : [], reais = medidas.filter((t) => (t.confianca || 0) >= .9).length
    return `<h1>Modelos e experimentos</h1>` + (b ? `<div class="cartao" style="margin-bottom:12px"><h3><span class="ms">travel_explore</span> Busca do agente · ${b.alvo}</h3><p class="sub">Testou <b style="color:var(--t)">${b.tentativas.length} receitas</b> na validação: ${reais} com ganho real sobre só-metadados, ${medidas.length - reais} indistinguíveis de acaso${b.tentativas.length - medidas.length ? ', ' + (b.tentativas.length - medidas.length) + ' sem poder estatístico' : ''}. Só a melhor foi ao teste e virou o modelo.</p>
      <table style="margin-top:10px"><thead><tr><th>origem</th><th>camadas</th><th class="n">vs controle</th><th>ganho real?</th><th class="n">n</th></tr></thead><tbody>${b.tentativas.map((t) => `<tr><td class="mono">${t.origem}</td><td>${receita(t.receita)}</td><td class="n">${t.objetivo === null ? '—' : pct(t.objetivo)}</td><td>${t.objetivo === null ? `<span class="sub">${(t.erro || '').slice(0, 70)}</span>` : (t.confianca >= .9 ? `<span class="bom">sim (${Math.round(t.confianca * 100)}%)</span>` : `<span class="sub">indistinguível (${Math.round((t.confianca || 0) * 100)}%)</span>`)}</td><td class="n">${t.n_validacao}</td></tr>`).join('')}</tbody></table></div>` : '') +
      `<div class="cartao"><table><thead><tr><th>modelo</th><th>mais preciso que a média do canal</th><th class="n">acerto A vs B</th><th>status</th></tr></thead><tbody>${ex.map((e) => `<tr><td><b>${receita(e.receita)}</b><br><span class="sub">${e.alvo} · ${e.resultado.n_teste} vídeos de teste</span></td><td><span class="barra" style="width:${Math.max(e.resultado.ganho, 0) / maior * 180}px"></span><b class="bom">${pct(e.resultado.ganho)}</b><br><span class="sub">erro típico ${Math.exp(e.resultado.modelo.mae).toFixed(1)}× · média do canal ${Math.exp(e.resultado.baseline.mae).toFixed(1)}×</span></td><td class="n">${e.resultado.modelo.acerto_pares == null ? '—' : pct(e.resultado.modelo.acerto_pares, false)}</td><td><span class="chip ${e.status === 'ativo' ? 'ok' : ''}">${e.status}</span></td></tr>`).join('')}</tbody></table></div>`
  },
  analisar() {
    const a = (D[projeto].analises || []).find((x) => x.explicacao) || null
    return `<h1>Analisar vídeo</h1><div class="duas"><div class="short"><span class="ms" style="font-size:40px">upload</span><span>arraste o Short ou cole o link</span></div><div>` +
      (a ? `<div class="cartao aval ap"><h3><span class="ms">${a.previsao_7d && a.previsao_7d.q50 >= 1.3 * (a.acompanhamento?.timeline ? 0 : 0) ? 'trending_up' : 'trending_flat'}</span> ${a.titulo} <span class="sub">· ${a.canal || ''}</span></h3><p>${a.explicacao}</p>${a.gancho ? `<div class="rot">o que se vê no gancho</div><p class="sub">${a.gancho}</p>` : ''}${a.fala ? `<div class="rot">o que se fala</div><p class="sub">${a.fala}</p>` : ''}<p class="sub" style="margin-top:8px">${a.chances.map((c) => c.evento + ' ' + Math.round(c.prob * 100) + '%').join(' · ')}</p></div>` : `<div class="cartao"><p class="sub">Sem análise gravada neste projeto.</p></div>`) + `</div></div>`
  },
  analises() {
    const L = D[projeto].analises || []
    return `<h1>Vídeos analisados</h1><div class="cartao"><table><thead><tr><th>quando</th><th>vídeo</th><th>canal</th><th class="n">previsto em 7 dias</th><th class="n">viralizar</th><th>real</th><th>status</th></tr></thead><tbody>` +
      L.map((a) => { const p = a.previsao_7d, u = a.acompanhamento && a.acompanhamento.ultima; return `<tr><td class="sub">${new Date(a.inicio).toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td><td><b>${a.titulo || '(sem título)'}</b></td><td>${a.canal || '—'}</td><td class="n">${p ? k(p.q50) + ' <span class="sub">(' + k(p.q25 || p.q10) + '–' + k(p.q75 || p.q90) + ')</span>' : '—'}</td><td class="n">${a.chances.length ? Math.round(a.chances[a.chances.length - 1].prob * 100) + '%' : '—'}</td><td>${u ? `<span class="${u.dentro_da_faixa ? 'bom' : 'ruim'}">${k(u.real)} aos ${Math.round(u.idade_dias)} d · ${u.dentro_da_faixa_50 ? 'na provável' : u.dentro_da_faixa ? 'na quase certa' : 'fora'}</span>` : '<span class="sub">não acompanhado</span>'}</td><td><span class="chip ${a.status === 'ok' ? 'ok' : ''}">${a.status}</span></td></tr>` }).join('') + `</tbody></table></div>`
  },
}
function render() {
  const t = (location.hash || '#projetos').slice(1).split('/')[0]
  document.querySelectorAll('aside a').forEach((x) => x.classList.toggle('on', x.dataset.t === t))
  document.getElementById('main').innerHTML = (telas[t] || telas.projetos)()
}
addEventListener('hashchange', render); render()
</script></body></html>"""
html = html.replace("__LOGO__", LOGO).replace("__DADOS__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
(AQUI / "replica.html").write_text(html)
print("replica.html", len(html) // 1024, "KB")
