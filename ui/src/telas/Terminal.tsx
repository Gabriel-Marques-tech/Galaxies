import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { compacto, num, pct, pctOu } from '../componentes'

// Harness: terminal no navegador para quem trabalha com dados. Mesma API da UI.

type Parte = { t: string; c?: string }
type Linha = Parte[]
type Saida = (linhas: Linha[]) => void
type Comando = { uso: string; desc: string; rodar: (args: string[], projeto: string, out: Saida) => Promise<void> | void }

const l = (...partes: (string | Parte)[]): Linha => partes.map((p) => (typeof p === 'string' ? { t: p } : p))
const dim = (t: string): Parte => ({ t, c: 't-dim' })
const ok = (t: string): Parte => ({ t, c: 't-ok' })
const ruim = (t: string): Parte => ({ t, c: 't-erro' })
const info = (t: string): Parte => ({ t, c: 't-info' })
const negrito = (t: string): Parte => ({ t, c: 't-negrito' })

// Tabela em caracteres de caixa, como num terminal.
function tabela(cab: string[], linhas: string[][], alinhar: ('e' | 'd')[] = []): Linha[] {
  const larg = cab.map((h, i) => Math.max(h.length, ...linhas.map((r) => r[i].length)))
  const cel = (v: string, i: number) => (alinhar[i] === 'd' ? v.padStart(larg[i]) : v.padEnd(larg[i]))
  const borda = (e: string, m: string, d: string) => dim(e + larg.map((w) => '─'.repeat(w + 2)).join(m) + d)
  return [
    l(borda('┌', '┬', '┐')),
    l(dim('│ '), ...cab.flatMap((h, i) => [negrito(cel(h, i)), dim(i < cab.length - 1 ? ' │ ' : ' │')])),
    l(borda('├', '┼', '┤')),
    ...linhas.map((r) => l(dim('│ '), ...r.flatMap((v, i) => [{ t: cel(v, i) }, dim(i < r.length - 1 ? ' │ ' : ' │')]))),
    l(borda('└', '┴', '┘')),
  ]
}

const COMANDOS: Record<string, Comando> = {
  '/ajuda': {
    uso: '/ajuda', desc: 'lista os comandos',
    rodar: (_a, _p, out) => out([
      l(negrito('Comandos')),
      ...Object.values(COMANDOS).map((c) => l('  ', info(c.uso.padEnd(34)), dim(c.desc))),
      l(dim('  Tab completa · ↑↓ navega o histórico · Ctrl+L limpa')),
    ]),
  },
  '/status': {
    uso: '/status', desc: 'números do projeto',
    rodar: async (_a, p, out) => {
      const [r, cfg] = await Promise.all([api.resumo(p), api.projeto(p)])
      out([
        l(negrito(p), dim(` · modo ${cfg.modo} · alvo ${cfg.alvo} · setores ${cfg.setores.join(', ')}`)),
        l('  shorts      ', info(compacto(r.videos)), dim(` em ${r.canais} canais`)),
        l('  ganchos     ', info(String(r.ganchos)), dim(` · ${r.falhas} falhas · ${r.excluidos} excluídos`)),
        ...Object.entries(r.atributos_por_extrator).map(([e, n]) => l('  atributos   ', info(String(n)), dim(` via ${e}`))),
        l('  modelos     ', info(String(r.experimentos)), dim(` experimentos · ${r.revisoes} revisões humanas`)),
        l('  cota YT     ', info(String(r.cota_youtube)), dim(' unidades')),
      ])
    },
  },
  '/modelos': {
    uso: '/modelos', desc: 'experimentos contra a média do canal e o controle',
    rodar: async (_a, p, out) => {
      const exps = await api.experimentos(p)
      if (!exps.length) return out([l(dim('nenhum experimento. o agente roda: experimentar / ciclo_automatico'))])
      out([
        ...tabela(
          ['id', 'receita', 'teste', 'MAE', 'só meta', 'média', 'pares', 'faixa 80%', 'ganho', 'status'],
          [...exps].reverse().map((e) => {
            const r = e.resultado
            return [e.id, e.receita.camadas.join('+').replace('metadados', 'meta'), String(r.n_teste), num(r.modelo.mae),
              num(r.controle_metadados.mae), num(r.baseline.mae), pctOu(r.modelo.acerto_pares), pct(r.cobertura_80 ?? 0, false), pct(r.ganho), e.status]
          }),
          ['e', 'e', 'd', 'd', 'd', 'd', 'd', 'd', 'd', 'e'],
        ),
        l(dim('MAE no log, nas mesmas linhas de teste: menor é melhor. /exp <id> para detalhes.')),
      ])
    },
  },
  '/exp': {
    uso: '/exp <id>', desc: 'detalhes, sugestões e ganho por atributo',
    rodar: async ([id], p, out) => {
      const e = (await api.experimentos(p)).find((x) => x.id.startsWith(id ?? '~'))
      if (!e) return out([l(ruim(`experimento '${id ?? ''}' não encontrado`))])
      const r = e.resultado
      out([
        l(negrito(`${e.id} · ${e.receita.camadas.join(' + ')}`), dim(` · ${e.status}`)),
        e.hipotese ? l(dim('hipótese  '), e.hipotese) : l(),
        l(dim('vs média  '), r.ganho > 0 ? ok(pct(r.ganho)) : ruim(pct(r.ganho)), dim(`  vs só meta `), r.melhora_sobre_controle > 0 ? ok(pct(r.melhora_sobre_controle)) : ruim(pct(r.melhora_sobre_controle)), dim(`  n=${r.n_teste}`)),
        ...r.sugestoes.map((s) => l(info('  › '), s)),
        ...Object.entries(r.ganho_por_atributo).slice(0, 15).map(([a, g]) =>
          l('  ', a.padEnd(22), g > 0 ? ok(('+' + g.toFixed(4)).padStart(8)) : dim(g.toFixed(4).padStart(8)), dim(' ' + '█'.repeat(Math.min(Math.round(Math.abs(g) * 2000), 30))))),
      ])
    },
  },
  '/promover': {
    uso: '/promover <id>', desc: 'promove (no modo cientista vai para aprovação)',
    rodar: async ([id], p, out) => {
      const e = await api.promover(p, id)
      out([l(ok('✓ '), `${e.id} → `, negrito(e.status))])
    },
  },
  '/aprovar': {
    uso: '/aprovar <id> [nota]', desc: 'aprova uma promoção pendente',
    rodar: async ([id, ...nota], p, out) => {
      const e = await api.decidir(p, id, true, nota.join(' '))
      out([l(ok('✓ aprovado: '), `${e.id} agora é o modelo `, negrito(e.status))])
    },
  },
  '/rejeitar': {
    uso: '/rejeitar <id> [nota]', desc: 'rejeita uma promoção pendente',
    rodar: async ([id, ...nota], p, out) => {
      const e = await api.decidir(p, id, false, nota.join(' '))
      out([l(ruim('✗ rejeitado: '), e.id)])
    },
  },
  '/analisar': {
    uso: '/analisar <canal> <título…>', desc: 'prevê um Short (canal = id UC… ou parte do nome)',
    rodar: async ([canal, ...titulo], p, out) => {
      if (!canal || !titulo.length) return out([l(ruim('uso: /analisar <canal> <título>'))])
      const canais = await api.canais(p)
      const c = canais.find((x) => x.id === canal) ?? canais.find((x) => x.titulo.toLowerCase().includes(canal.toLowerCase()))
      if (!c) return out([l(ruim(`canal '${canal}' não encontrado. /canais lista os canais`))])
      const a = await api.analisar(p, { titulo: titulo.join(' ') }, c.id)
      const q = a.previsao_7d
      out([
        l(dim('canal '), c.titulo, dim(` · mediana ${compacto(a.mediana_canal)} ${a.alvo}`)),
        l(negrito('7 dias  '), info(compacto(q.q50)), dim(`  (80%: ${compacto(q.q10)} – ${compacto(q.q90)})`)),
        ...a.chances.map((c) => l(dim(`  ${(c.evento + ` (${c.multiplo}×)`).padEnd(34)}`), info(pct(c.prob, false).padStart(6)), dim(' ' + '█'.repeat(Math.round(c.prob * 30))))),
        ...a.timeline.map((t) => l(dim(`  ${String(t.dias).padStart(2)}d `), info('▇'.repeat(Math.max(1, Math.round((t.q50 / a.timeline[a.timeline.length - 1].q90) * 40)))), dim(` ${compacto(t.q50)}`))),
        ...(a.sugestoes.length ? [l(negrito('sugestões'))] : []),
        ...a.sugestoes.map((s) => l(info('  › '), s.mudanca.padEnd(34), dim('viral '), dim(pct(a.p_viral, false)), dim(' → '), ok(pct(s.p_viral, false)))),
        l(dim(`modelo ${a.experimento_id} · /trace ${a.run_id}`)),
      ])
    },
  },
  '/canais': {
    uso: '/canais [filtro]', desc: 'canais da base',
    rodar: async ([filtro], p, out) => {
      const cs = (await api.canais(p)).filter((c) => !filtro || c.titulo.toLowerCase().includes(filtro.toLowerCase())).slice(0, 40)
      out(tabela(['id', 'canal', 'setor', 'inscritos', 'shorts', 'ganchos'],
        cs.map((c) => [c.id, c.titulo.slice(0, 28), c.setor, compacto(c.inscritos ?? 0), String(c.videos), String(c.ganchos)]),
        ['e', 'e', 'e', 'd', 'd', 'd']))
    },
  },
  '/erros': {
    uso: '/erros', desc: 'piores previsões, segmentos e falhas',
    rodar: async (_a, p, out) => {
      const r = await api.erros(p)
      out([
        l(dim(`origem: ${r.origem || '—'}`)),
        ...tabela(['vídeo', 'canal', 'previsto', 'real', 'erro'], r.piores.slice(0, 10).map((e) => [e.video_id, e.canal_id.slice(0, 12), num(e.previsto, 2), num(e.real, 2), num(e.erro_log, 2)]), ['e', 'e', 'd', 'd', 'd']),
        l(negrito('falhas '), ...Object.entries(r.falhas_por_etapa).map(([e, n]) => dim(`${e}=${n}  `))),
        ...r.notas_padrao.map((n) => l(info('  pista › '), n)),
      ])
    },
  },
  '/concordancia': {
    uso: '/concordancia', desc: 'extrator × revisões humanas',
    rodar: async (_a, p, out) => {
      const cs = await api.concordancia(p)
      if (!cs.length) return out([l(dim('sem revisões ainda. use a aba Revisão de atributos'))])
      out(tabela(['atributo', 'revisados', 'acordo', ''], cs.map((c) => [c.atributo_id, String(c.revisados), pct(c.concordancia, false), c.confiavel ? 'ok' : 'não confiável']), ['e', 'd', 'd', 'e']))
    },
  },
  '/runs': {
    uso: '/runs [n]', desc: 'últimas execuções',
    rodar: async ([n], p, out) => {
      const rs = (await api.runs(p)).slice(-(Number(n) || 15)).reverse()
      out(tabela(['run', 'operação', 'status', 'início'], rs.map((r) => [r.id, r.operacao, r.status, new Date(r.inicio).toLocaleString('pt-BR')])))
    },
  },
  '/trace': {
    uso: '/trace <run>', desc: 'etapas de uma execução',
    rodar: async ([id], p, out) => {
      const etapas = await api.trace(p, id)
      out(etapas.slice(0, 80).map((e) => l(e.erro ? ruim('✗ ') : ok('● '), e.nome.padEnd(22), dim(`${e.duracao_ms.toFixed(0).padStart(7)} ms`), e.erro ? ruim('  ' + e.erro) : dim('  ' + JSON.stringify(e.saida ?? '').slice(0, 90)))))
    },
  },
  '/modo': {
    uso: '/modo automatico|cientista', desc: 'troca o modo do projeto',
    rodar: async ([modo], p, out) => {
      const cfg = await api.definirModo(p, modo as 'automatico' | 'cientista')
      out([l(ok('✓ modo '), negrito(cfg.modo))])
    },
  },
  '/limpar': { uso: '/limpar', desc: 'limpa a tela', rodar: () => undefined },
}

function separar(entrada: string): string[] {
  return (entrada.match(/"[^"]*"|\S+/g) ?? []).map((s) => s.replace(/^"|"$/g, ''))
}

export default function Terminal({ projeto }: { projeto: string }) {
  const cabecalho: Linha[] = [l()]
  const [linhas, setLinhas] = useState<Linha[]>(cabecalho)
  const [entrada, setEntrada] = useState('')
  const [historico, setHistorico] = useState<string[]>([])
  const [posHist, setPosHist] = useState(-1)
  const [sel, setSel] = useState(0)
  const [ocupado, setOcupado] = useState(false)
  const fim = useRef<HTMLDivElement>(null)
  const campo = useRef<HTMLInputElement>(null)

  useEffect(() => { fim.current?.scrollIntoView({ block: 'end' }) }, [linhas])
  const sugestoes = entrada.startsWith('/') && !entrada.includes(' ')
    ? Object.keys(COMANDOS).filter((c) => c.startsWith(entrada)) : []

  const executar = async (texto: string) => {
    const [nome, ...args] = separar(texto.trim())
    if (!nome) return
    setHistorico((h) => [...h, texto]); setPosHist(-1)
    if (nome === '/limpar') return setLinhas(cabecalho)
    setLinhas((ls) => [...ls, l({ t: '› ', c: 'prompt t-info' }, { t: texto, c: 't-cmd' })])
    const cmd = COMANDOS[nome]
    const out: Saida = (novas) => setLinhas((ls) => [...ls, ...novas, l()])
    if (!cmd) return out([l(ruim(`comando desconhecido: ${nome}`), dim('  (/ajuda)'))])
    setOcupado(true)
    try { await cmd.rodar(args, projeto, out) } catch (e) { out([l(ruim('✗ '), (e as Error).message)]) } finally { setOcupado(false) }
  }

  const tecla = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'l' && e.ctrlKey) { e.preventDefault(); setLinhas(cabecalho); return }
    if (sugestoes.length && (e.key === 'Tab' || (e.key === 'Enter' && sugestoes[sel] !== entrada))) {
      e.preventDefault(); setEntrada(sugestoes[sel] + ' '); setSel(0); return
    }
    if (sugestoes.length && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault(); setSel((s) => (s + (e.key === 'ArrowDown' ? 1 : -1) + sugestoes.length) % sugestoes.length); return
    }
    if (e.key === 'Enter') { const t = entrada; setEntrada(''); void executar(t); return }
    if (e.key === 'ArrowUp' && historico.length) {
      e.preventDefault(); const p = posHist < 0 ? historico.length - 1 : Math.max(0, posHist - 1)
      setPosHist(p); setEntrada(historico[p])
    }
    if (e.key === 'ArrowDown' && posHist >= 0) {
      e.preventDefault(); const p = posHist + 1
      if (p >= historico.length) { setPosHist(-1); setEntrada('') } else { setPosHist(p); setEntrada(historico[p]) }
    }
  }

  return (
    <div className="terminal" onClick={() => campo.current?.focus()}>
      <div className="saida" aria-live="polite">
        <div className="t-cabecalho">
          <span className="t-info">✻</span> <b>Galaxies harness</b>
          <div className="t-dim">/ajuda para os comandos · Tab completa · ↑ histórico</div>
          <div className="t-dim">projeto: <span className="t-roxo">{projeto}</span></div>
        </div>
        {linhas.map((ln, i) => <div key={i}>{ln.length ? ln.map((p, j) => <span key={j} className={p.c}>{p.t}</span>) : ' '}</div>)}
        <div ref={fim} />
      </div>
      <div className="entrada">
        {sugestoes.length > 0 && (
          <div className="sugestoes-cmd">
            {sugestoes.map((s, i) => (
              <div key={s} className={i === sel ? 'ativa' : ''}><span className="t-info">{COMANDOS[s].uso}</span><span className="t-dim">{COMANDOS[s].desc}</span></div>
            ))}
          </div>
        )}
        <span className="prompt">{ocupado ? '◌' : '›'}</span>
        <input ref={campo} autoFocus value={entrada} onChange={(e) => { setEntrada(e.target.value); setSel(0) }} onKeyDown={tecla}
          placeholder="/ajuda" spellCheck={false} aria-label="Comando" />
      </div>
      <div className="rodape"><span>{projeto}</span><span>{ocupado ? 'rodando…' : '? /ajuda · Tab completa · ↑ histórico'}</span></div>
    </div>
  )
}
