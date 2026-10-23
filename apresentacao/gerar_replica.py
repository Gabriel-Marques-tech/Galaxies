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
main{flex:1;overflow:auto;padding:22px 28px}.foco-deck{box-shadow:0 0 0 2px #4285f4,0 0 28px rgba(66,133,244,.45);transition:box-shadow .4s}h1{font-size:22px;font-weight:400;margin-bottom:14px}
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
.short.pronto{border-style:solid;background:#0b0f1c;justify-content:flex-end;padding:12px;position:relative;overflow:hidden}.short.pronto .mini{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.short.pronto .nome-arq{position:relative;font-size:11px;background:rgba(0,0,0,.55);color:#fff;border-radius:6px;padding:3px 6px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pergunta{align-self:flex-end;background:#243055;color:#dfe7ff;border-radius:18px 18px 4px 18px;padding:10px 14px;max-width:80%;margin:0 0 12px auto;font-size:13.5px}.pergunta .sub{font-size:11.5px;color:#aab6d6}
.grade2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.desc{font-size:12px;color:var(--sub);margin-bottom:8px}
.chance{display:grid;grid-template-columns:1fr 140px 48px;gap:10px;align-items:center;padding:6px 0;font-size:13px}.chance .trilho{height:8px;border-radius:999px;background:#2a3150;overflow:hidden}.chance .trilho div{height:100%;background:linear-gradient(90deg,#4285f4,#9b72cb)}.chance b{text-align:right}
.fator{display:grid;grid-template-columns:200px 1fr 56px;gap:10px;align-items:center;padding:5px 0;font-size:12.5px}.fator .trilho{position:relative;height:8px;background:#2a3150;border-radius:999px}.fator .trilho::before{content:'';position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:var(--c)}.fator .trilho div{position:absolute;top:0;height:100%;border-radius:999px}.fator .n{text-align:right;color:var(--sub)}
.sug{display:grid;grid-template-columns:24px 1fr auto auto;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--c);font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.campo{display:grid;grid-template-columns:130px 1fr;gap:10px;font-size:13px;padding:6px 0;border-top:1px solid var(--c)}.campo span:first-child{color:var(--sub)}
.tl{width:100%;height:170px;display:block}
.seg{display:inline-flex;border:1px solid var(--c);border-radius:999px;overflow:hidden;margin-top:8px}.seg span{padding:8px 16px;font-size:13px;color:var(--sub);display:inline-flex;align-items:center;gap:6px}.seg span.on{background:#243055;color:#cfe0ff}
.onda-deck{position:fixed;width:40px;height:40px;border-radius:50%;pointer-events:none;background:radial-gradient(circle,rgba(155,114,203,.55),rgba(66,133,244,.25) 60%,transparent 70%);transform:translate(-50%,-50%) scale(0);animation:ondadeck 1.3s ease-out forwards;z-index:9}@keyframes ondadeck{to{transform:translate(-50%,-50%) scale(60);opacity:0}}
.ap{opacity:0;transform:translateY(10px);animation:ap .5s forwards}@keyframes ap{to{opacity:1;transform:none}}
</style></head><body>
<aside><div class="marca">__LOGO__ Stars</div>
<a href="#projetos" data-t="projetos" data-deck="nav-projetos"><span class="ms">grid_view</span>Projetos</a>
<a href="#inicio" data-t="inicio" data-deck="nav-inicio"><span class="ms">home</span>Início</a>
<a href="#analisar" data-t="analisar" data-deck="nav-analisar"><span class="ms">auto_awesome</span>Analisar vídeo</a>
<a href="#analises" data-t="analises" data-deck="nav-analises"><span class="ms">history</span>Vídeos analisados</a>
<a href="#modelos" data-t="modelos" data-deck="nav-modelos"><span class="ms">model_training</span>Modelos</a>
<a href="#revisao"><span class="ms">fact_check</span>Revisão de atributos</a>
<a href="#erros"><span class="ms">troubleshoot</span>Erros</a>
<a href="#trace"><span class="ms">account_tree</span>Trace</a></aside>
<main id="main"></main>
<script id="dados" type="application/json">__DADOS__</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent)
let projeto = 'moda-beleza', modoVisual = null
const modoDe = (p) => modoVisual || D[p].config.modo
const k = (v) => v >= 1000 ? (v/1000).toFixed(v >= 10000 ? 0 : 1).replace('.', ',') + ' mil' : String(Math.round(v))
const pct = (v, s = true) => (s && v > 0 ? '+' : '') + (v * 100).toFixed(1).replace('.', ',') + '%'
const receita = (r) => r.camadas.join(' + ') + (r.ancora === 'movel' ? ' · âncora móvel' : '')
const ativo = (p, alvo) => (D[p].experimentos.find((e) => e.status === 'ativo' && e.alvo === alvo) || D[p].experimentos.find((e) => e.status === 'ativo'))
const telas = {
  projetos() {
    return `<h1>Projetos</h1><p class="sub" style="margin-bottom:10px">Role para escolher o projeto. Arraste um card para o lado para criar outro.</p><div class="feed">` +
      D.projetos.map((p) => { const a = ativo(p, D[p].config.alvo); return `<div class="cp ${p === projeto ? 'on' : ''}" data-deck="projeto-${p}" onclick="projeto='${p}';location.hash='#inicio'"><div class="mos">${(D[p].miniaturas || []).slice(0, 9).map((id) => `<img src="https://i.ytimg.com/vi/${id}/mqdefault.jpg" alt="">`).join('')}</div><span class="ms" style="font-size:34px;color:#8ab4ff">smart_display</span><div class="nome">${p}</div><div class="sub">${D[p].experimentos.length} experimentos</div><div class="g">${a ? '−' + pct(a.resultado.ganho, false) : '—'}</div><div class="sub">mais preciso que a média do canal</div></div>` }).join('') +
      `</div><div class="cartao"><div class="rot">O que funciona em ${projeto}</div>` + (D[projeto].insights.fatores || []).slice(0, 5).map((f) => `<div class="lin"><span class="mono">${f.fator}</span><b class="${f.efeito >= 0 ? 'bom' : 'ruim'}">${pct(f.efeito)}</b></div>`).join('') + `</div>`
  },
  inicio() {
    const r = D[projeto].resumo, a = ativo(projeto, D[projeto].config.alvo), pp = D[projeto]['proximo-passo'], cv = D[projeto].crescimento, ac = D[projeto].acompanhamentos
    const est = (cv.faixas || []).find((f) => f.inclinacao === 0)
    return `<h1>Visão geral <span class="chip">${modoDe(projeto) === 'cientista' ? 'Data Scientist' : 'Automático'} · ${D[projeto].config.alvo}</span></h1><div class="grade">
      <div class="cartao met"><div class="r">Shorts na base</div><div class="v">${k(r.videos)}</div><div class="d">${r.canais} canais · ${D[projeto].config.setores.join(', ')}</div></div>
      <div class="cartao met" data-deck="modelo-ativo"><div class="r">Modelo ativo</div><div class="v">${a ? '−' + pct(a.resultado.ganho, false) : '—'}</div><div class="d">${a ? 'mais preciso que a média do canal · ' + receita(a.receita) : 'nenhum'}</div></div>
      <div class="cartao met"><div class="r">Experimentos</div><div class="v">${r.experimentos}</div><div class="d">${r.runs} execuções</div></div>
      <div class="cartao met"><div class="r">Em produção</div><div class="v">${ac.n ? Math.round(ac.cobertura * 100) + '%' : '—'}</div><div class="d">${ac.n ? ac.n + ' vídeo(s) · dentro da faixa quase certa' : 'nenhum vídeo acompanhado'}</div></div>
      <div class="cartao met"><div class="r">Curva de crescimento</div><div class="v">${cv.videos ? k(cv.videos) : '—'}</div><div class="d">${cv.videos ? 'vídeos reobservados · ' + cv.alvo + (est ? ' estabilizam a partir de ~' + est.de_dias + ' dias' : '') : 'sem reobservação'}</div></div></div>
      <div class="cartao ${pp.certeza === 'ambiguo' ? '' : 'aval'}" data-deck="proximo-passo"><h3><span class="ms">${pp.certeza === 'ambiguo' ? 'help' : 'route'}</span> Próximo passo: <span class="mono">${pp.acao}</span></h3><p class="sub">${pp.motivo}</p>${pp.alternativas.length ? `<p class="sub" style="margin-top:4px">ou: ${pp.alternativas.join(', ')}</p>` : ''}<p class="sub" style="margin-top:8px">${pp.certeza === 'ambiguo' ? 'Decisão de custo ou escopo: o agente pergunta antes de agir.' : 'Deduzido do estado do projeto por regra; o agente segue sem perguntar.'}</p></div>
      <div class="cartao" style="margin-top:12px" data-deck="modo"><h3>Como você quer trabalhar?</h3><p class="sub">O agente faz o trabalho de cientista de dados. Você decide quanto quer participar.</p><div class="seg"><span class="${modoDe(projeto) === 'automatico' ? 'on' : ''}"><span class="ms">bolt</span> Automático</span><span data-deck="modo-cientista" class="${modoDe(projeto) === 'cientista' ? 'on' : ''}"><span class="ms">person_search</span> Data Scientist</span></div><p class="sub" style="margin-top:10px">${modoDe(projeto) === 'automatico' ? 'O agente testa as receitas e promove sozinho o melhor modelo que supera a média do canal.' : 'Cada promoção espera sua aprovação. Você revisa atributos e faz a triagem dos erros; suas notas viram pistas para o agente.'}</p></div>
      <div class="cartao" style="margin-top:12px" data-deck="diagnostico"><h3>Diagnóstico</h3>${D[projeto].diagnostico.pistas.slice(0, 5).map((p) => `<div class="lin"><span><b class="mono">${p.tipo}</b> · ${p.mensagem.slice(0, 120)}…</span><span class="mono sub">→ ${p.acao}</span></div>`).join('')}</div>`
  },
  modelos() {
    const ex = [...D[projeto].experimentos].reverse(), maior = Math.max(...ex.map((e) => Math.max(e.resultado.ganho, 0)), .01), b = (D[projeto].buscas || [])[0]
    const medidas = b ? b.tentativas.filter((t) => t.objetivo !== null) : [], reais = medidas.filter((t) => (t.confianca || 0) >= .9).length
    return `<h1>Modelos e experimentos</h1>` + (b ? `<div class="cartao" style="margin-bottom:12px" data-deck="busca"><h3><span class="ms">travel_explore</span> Busca do agente · ${b.alvo}</h3><p class="sub">Testou <b style="color:var(--t)">${b.tentativas.length} receitas</b> na validação: ${reais} com ganho real sobre só-metadados, ${medidas.length - reais} indistinguíveis de acaso${b.tentativas.length - medidas.length ? ', ' + (b.tentativas.length - medidas.length) + ' sem poder estatístico' : ''}. Só a melhor foi ao teste e virou o modelo.</p>
      <table style="margin-top:10px"><thead><tr><th>origem</th><th>camadas</th><th class="n">vs controle</th><th>ganho real?</th><th class="n">n</th></tr></thead><tbody>${b.tentativas.map((t) => `<tr><td class="mono">${t.origem}</td><td>${receita(t.receita)}</td><td class="n">${t.objetivo === null ? '—' : pct(t.objetivo)}</td><td>${t.objetivo === null ? `<span class="sub">${(t.erro || '').slice(0, 70)}</span>` : (t.confianca >= .9 ? `<span class="bom">sim (${Math.round(t.confianca * 100)}%)</span>` : `<span class="sub">indistinguível (${Math.round((t.confianca || 0) * 100)}%)</span>`)}</td><td class="n">${t.n_validacao}</td></tr>`).join('')}</tbody></table></div>` : '') +
      `<div class="cartao" data-deck="experimentos"><table><thead><tr><th>modelo</th><th>mais preciso que a média do canal</th><th class="n">acerto A vs B</th><th>status</th></tr></thead><tbody>${ex.map((e) => `<tr><td><b>${receita(e.receita)}</b><br><span class="sub">${e.alvo} · ${e.resultado.n_teste} vídeos de teste</span></td><td><span class="barra" style="width:${Math.max(e.resultado.ganho, 0) / maior * 180}px"></span><b class="bom">${pct(e.resultado.ganho)}</b><br><span class="sub">erro típico ${Math.exp(e.resultado.modelo.mae).toFixed(1)}× · média do canal ${Math.exp(e.resultado.baseline.mae).toFixed(1)}×</span></td><td class="n">${e.resultado.modelo.acerto_pares == null ? '—' : pct(e.resultado.modelo.acerto_pares, false)}</td><td><span class="chip ${e.status === 'ativo' ? 'ok' : ''}">${e.status}</span></td></tr>`).join('')}</tbody></table></div>`
  },
  analisar() {
    const A = D[projeto].analise_completa, resumo = (D[projeto].analises || []).find((x) => A && x.run_id === A.run_id) || (D[projeto].analises || []).find((x) => x.explicacao) || null
    if (!A || !resumo) return `<h1>Analisar vídeo</h1><div class="duas"><div class="short"><span class="ms" style="font-size:40px">upload</span><span>arraste o Short ou cole o link</span></div><div class="cartao"><p class="sub">Sem análise gravada neste projeto.</p></div></div>`
    const p = A.previsao_7d, med = A.mediana_canal, alvo = A.alvo
    const verd = p.q50 >= med * 1.3 ? ['trending_up', 'Acima do normal do canal'] : p.q50 <= med * 0.7 ? ['trending_down', 'Abaixo do normal do canal'] : ['trending_flat', 'No normal do canal']
    const arq = (resumo.fonte || '').split('/').pop() || 'short.mp4'
    const mini = `<video class="mini" src="demo-short.mp4" autoplay muted loop playsinline></video>`
    // timeline: área q10–q90, área q25–q75 e linha q50, eixo em dias (escala log) e valor (escala log)
    const tl = A.timeline, W = 520, H = 150, PL = 44, PB = 22
    const xs = tl.map((t) => Math.log(1 + t.dias)), ys = tl.flatMap((t) => [t.q10, t.q90]).map((v) => Math.log(1 + v))
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) * .98, y1 = Math.max(...ys) * 1.02
    const X = (d) => PL + (Math.log(1 + d) - x0) / (x1 - x0 || 1) * (W - PL - 8), Y = (v) => (H - PB) - (Math.log(1 + v) - y0) / (y1 - y0 || 1) * (H - PB - 8)
    const area = (lo, hi) => 'M' + tl.map((t) => `${X(t.dias)},${Y(t[lo])}`).join(' L') + ' L' + [...tl].reverse().map((t) => `${X(t.dias)},${Y(t[hi])}`).join(' L') + ' Z'
    const linha = 'M' + tl.map((t) => `${X(t.dias)},${Y(t.q50)}`).join(' L')
    const marcas = [7, 30, 90].filter((d) => tl.some((t) => t.dias === d))
    const svg = `<svg class="tl" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path d="${area('q10', 'q90')}" fill="rgba(66,133,244,.16)"/><path d="${area('q25', 'q75')}" fill="rgba(66,133,244,.32)"/><path d="${linha}" fill="none" stroke="#8ab4f8" stroke-width="2"/>${marcas.map((d) => { const t = tl.find((t) => t.dias === d); return `<line x1="${X(d)}" x2="${X(d)}" y1="8" y2="${H - PB}" stroke="rgba(255,255,255,.08)"/><text x="${X(d)}" y="${H - 6}" fill="#9aa0b4" font-size="11" text-anchor="middle">${d} d</text><text x="${X(d) - 4}" y="${Y(t.q50) - 6}" fill="#dfe7ff" font-size="11" text-anchor="end">${k(t.q50)}</text>` }).join('')}<text x="4" y="14" fill="#9aa0b4" font-size="11">${alvo}</text></svg>`
    const chips = A.atributos ? `<div class="chips">${Object.entries(A.atributos).map(([id, v]) => `<span class="chip"><span class="mono">${id.replace(/_/g, ' ')}</span>: ${v.type === 'noul' ? (Number(v.noul) >= .5 ? 'sim' : 'não') : v.type === 'score' ? v.score : (v.choice ?? '')}</span>`).join('')}</div>` : ''
    const fatores = (A.fatores || []).map((f) => { const w = Math.min(Math.abs(f.impacto) * 50, 50); return `<div class="fator"><span class="mono">${f.feature}</span><span class="trilho"><div style="left:${f.impacto >= 0 ? 50 : 50 - w}%;width:${w}%;background:${f.impacto >= 0 ? '#5fd39a' : '#f08080'}"></div></span><span class="n">${f.impacto >= 0 ? '+' : ''}${f.impacto.toFixed(2)}</span></div>` }).join('')
    const sug = (A.sugestoes || []).length ? `<div class="cartao" style="margin-top:12px"><h3>Para aumentar a chance de viralizar</h3><div class="desc">Mudanças que o modelo associa a mais alcance neste canal. Hipóteses para testar, não garantia.</div>${A.sugestoes.map((s) => `<div class="sug"><span class="ms" style="color:var(--p)">trending_up</span><span>${s.mudanca}</span><span class="sub">viral ${pct(A.p_viral, false)} → <b class="bom">${pct(s.p_viral, false)}</b></span><span class="sub">7 dias ${pct(s.ganho)}</span></div>`).join('')}</div>` : ''
    return `<h1>Analisar vídeo</h1><div class="duas"><div class="short pronto">${mini}<span class="nome-arq">${arq}</span></div><div>
      <div class="pergunta">${resumo.titulo}<div class="sub">${resumo.canal || ''}</div></div>
      <div class="cartao aval ap" data-deck="avaliacao"><h3><span class="ms" style="color:var(--p)">${verd[0]}</span> ${verd[1]} <span class="sub">· ${k(p.q50)} ${alvo} em 7 dias (canal costuma fazer ${k(med)})</span></h3>
        <p style="font-size:14.5px">Na metade dos casos fica entre <b>${k(p.q25)} e ${k(p.q75)}</b>; é quase certo (80%) que fique entre ${k(p.q10)} e ${k(p.q90)}. Chance de viralizar (${A.limite_viral}× a mediana em ${A.dias_viral} dias): <b>${pct(A.p_viral, false)}</b>.</p>
        <p class="sub" style="margin-top:8px">${A.explicacao}</p>
        ${A.gancho ? `<div style="margin-top:10px"><div class="campo"><span>O que se vê no gancho</span><span>${A.gancho.descricao}</span></div><div class="campo"><span>O que se fala</span><span>${A.gancho.transcricao || '(sem fala)'}</span></div></div>` : ''}${chips}</div>
      <div class="grade2"><div class="cartao"><h3>Timeline prevista</h3><div class="desc">Mediana, faixa provável (50%) e quase certa (80%)</div>${svg}</div>
        <div class="cartao"><h3>Chances em ${A.dias_viral} dias</h3><div class="desc">Hipóteses sobre a mediana do canal (${k(med)} ${alvo})</div>${A.chances.map((c) => `<div class="chance"><span>${c.evento}<span class="sub"> · ${c.multiplo}×</span></span><span class="trilho"><div style="width:${c.prob * 100}%"></div></span><b>${pct(c.prob, false)}</b></div>`).join('')}</div></div>
      ${sug}
      <div class="cartao" style="margin-top:12px"><h3>O que mais pesou</h3><div class="desc">Contribuição de cada fator na previsão (SHAP)</div>${fatores}</div>
      <div class="cartao" style="margin-top:12px;display:flex;gap:10px;align-items:center"><span class="ms" style="color:var(--p)">publish</span><span style="flex:1"><b>Publicou?</b> <span class="sub">Cole o link do Short para acompanhar previsto × real.</span></span><span class="chip">link ou id do vídeo</span><span class="chip ok">Acompanhar</span></div>
      <p class="sub mono" style="margin-top:8px">modelo ${A.experimento_id} · run ${A.run_id}</p></div></div>`
  },
  analises() {
    const L = D[projeto].analises || []
    return `<h1>Vídeos analisados</h1><div class="cartao" data-deck="analises"><table><thead><tr><th>quando</th><th>vídeo</th><th>canal</th><th class="n">previsto em 7 dias</th><th class="n">viralizar</th><th>real</th><th>status</th></tr></thead><tbody>` +
      L.map((a) => { const p = a.previsao_7d, u = a.acompanhamento && a.acompanhamento.ultima; return `<tr><td class="sub">${new Date(a.inicio).toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td><td><b>${a.titulo || '(sem título)'}</b></td><td>${a.canal || '—'}</td><td class="n">${p ? k(p.q50) + ' <span class="sub">(' + k(p.q25 || p.q10) + '–' + k(p.q75 || p.q90) + ')</span>' : '—'}</td><td class="n">${a.chances.length ? Math.round(a.chances[a.chances.length - 1].prob * 100) + '%' : '—'}</td><td>${u ? `<span class="${u.dentro_da_faixa ? 'bom' : 'ruim'}">${k(u.real)} aos ${Math.round(u.idade_dias)} d · ${u.dentro_da_faixa_50 ? 'na provável' : u.dentro_da_faixa ? 'na quase certa' : 'fora'}</span>` : '<span class="sub">não acompanhado</span>'}</td><td><span class="chip ${a.status === 'ok' ? 'ok' : ''}">${a.status}</span></td></tr>` }).join('') + `</tbody></table></div>`
  },
}
function render() {
  const t = (location.hash || '#projetos').slice(1).split('/')[0]
  document.querySelectorAll('aside a').forEach((x) => x.classList.toggle('on', x.dataset.t === t))
  document.getElementById('main').innerHTML = (telas[t] || telas.projetos)()
}
addEventListener('hashchange', render); render()
addEventListener('message', (e) => { const m = e.data; if (!m || m.origem !== 'deck') return; if (m.tipo === 'ir') location.hash = '#' + m.tela; if (m.tipo === 'projeto') { projeto = m.nome; render() }; if (m.tipo === 'modo') { modoVisual = m.valor; const b = document.querySelector('[data-deck="modo-cientista"]'); const r = b ? b.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 }; const o = document.createElement('div'); o.className = 'onda-deck'; o.style.left = (r.left + r.width / 2) + 'px'; o.style.top = (r.top + r.height / 2) + 'px'; document.body.appendChild(o); setTimeout(() => o.remove(), 1400); render() }; if (m.tipo === 'rolar') document.getElementById('main').scrollBy({ top: Number(m.y) || 0, behavior: 'smooth' }); if (m.tipo === 'foco') { document.querySelectorAll('.foco-deck').forEach((x) => x.classList.remove('foco-deck')); const el = document.querySelector('[data-deck="' + m.alvo + '"]'); if (!el) { e.source.postMessage({ origem: 'ui', tipo: 'rect', alvo: m.alvo, achou: false }, '*'); return } const destacar = m.destacar !== false; if (destacar) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => { if (destacar) el.classList.add('foco-deck'); const r = el.getBoundingClientRect(); e.source.postMessage({ origem: 'ui', tipo: 'rect', alvo: m.alvo, achou: true, x: r.left, y: r.top, w: r.width, h: r.height }, '*') }, destacar ? 650 : 30) } })
</script></body></html>"""
html = html.replace("__LOGO__", LOGO).replace("__DADOS__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
(AQUI / "replica.html").write_text(html)
print("replica.html", len(html) // 1024, "KB")
