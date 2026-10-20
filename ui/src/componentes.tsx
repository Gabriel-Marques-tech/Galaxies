import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Experimento, Faixa } from './api'

export const num = (v: number, casas = 3) => v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
export const pct = (v: number, sinal = true) => `${sinal && v >= 0 ? '+' : ''}${num(v * 100, 1)}%`
export const compacto = (v: number) => new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(v)

// Carrega dados de forma assíncrona e expõe erro e recarga.
export function useCarga<T>(carregar: () => Promise<T>, deps: unknown[]) {
  const [dados, setDados] = useState<T | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const recarregar = useCallback(() => {
    setErro(null)
    carregar().then(setDados).catch((e: Error) => setErro(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(recarregar, [recarregar])
  return { dados, erro, recarregar }
}

export function Icone({ nome, cheio, className = '' }: { nome: string; cheio?: boolean; className?: string }) {
  return <span className={`icone ${cheio ? 'cheio' : ''} ${className}`} aria-hidden>{nome}</span>
}

export function Aviso({ texto }: { texto: string }) {
  return <div className="aviso"><Icone nome="error" /> <span>{texto}</span></div>
}

export function Dica({ children }: { children: ReactNode }) {
  return <div className="dica"><Icone nome="info" /> <div>{children}</div></div>
}

export function Vazio({ icone, children }: { icone: string; children: ReactNode }) {
  return <div className="vazio"><Icone nome={icone} />{children}</div>
}

export function Metrica({ icone, rotulo, valor, detalhe }: { icone: string; rotulo: string; valor: string; detalhe?: ReactNode }) {
  return (
    <div className="metrica">
      <span className="rotulo"><Icone nome={icone} />{rotulo}</span>
      <span className="valor">{valor}</span>
      {detalhe && <span className="detalhe">{detalhe}</span>}
    </div>
  )
}

const STATUS: Record<Experimento['status'], [string, string, string]> = {
  ativo: ['bom', 'check_circle', 'ativo'],
  candidato: ['', 'science', 'candidato'],
  aguardando_aprovacao: ['primario', 'pending', 'aguardando você'],
  aposentado: ['', 'inventory_2', 'aposentado'],
  rejeitado: ['ruim', 'cancel', 'rejeitado'],
}

export function ChipStatus({ status }: { status: Experimento['status'] }) {
  const [cls, icone, rotulo] = STATUS[status]
  return <span className={`chip ${cls}`}><Icone nome={icone} cheio={status === 'ativo'} />{rotulo}</span>
}

// MAE do modelo contra o controle e o baseline, nas mesmas linhas. Menor é melhor.
export function BarrasMae({ r }: { r: Experimento['resultado'] }) {
  const maior = Math.max(r.modelo.mae, r.controle_metadados.mae, r.baseline.mae)
  const linhas: [string, string, number][] = [
    ['modelo', 'modelo', r.modelo.mae],
    ['controle', 'só meta', r.controle_metadados.mae],
    ['baseline', 'baseline', r.baseline.mae],
  ]
  return (
    <div className="mae" role="img" aria-label={`MAE modelo ${num(r.modelo.mae)}, só metadados ${num(r.controle_metadados.mae)}, baseline ${num(r.baseline.mae)}`}>
      {linhas.map(([cls, nome, v]) => (
        <div key={cls} style={{ display: 'contents' }} title={`${nome}: ${num(v)}`}>
          <span className="nome">{nome}</span>
          <span className={`trilho ${cls}`}><div style={{ width: `${(v / maior) * 100}%` }} /></span>
          <span className="v">{num(v, 2)}</span>
        </div>
      ))}
    </div>
  )
}

// Timeline prevista: mediana (linha) e faixa q10–q90 (área), com crosshair e tooltip.
export function GraficoTimeline({ pontos, alvo }: { pontos: (Faixa & { dias: number })[]; alvo: string }) {
  const largura = 640, altura = 240, m = { e: 48, d: 16, t: 16, b: 32 }
  const [foco, setFoco] = useState<number | null>(null)
  const ref = useRef<SVGSVGElement>(null)
  const maxDia = Math.max(...pontos.map((p) => p.dias))
  const maxY = Math.max(...pontos.map((p) => p.q90)) * 1.1 || 1
  const x = (d: number) => m.e + (d / maxDia) * (largura - m.e - m.d)
  const y = (v: number) => altura - m.b - (v / maxY) * (altura - m.t - m.b)
  const linha = (k: keyof Faixa) => pontos.map((p, i) => `${i ? 'L' : 'M'}${x(p.dias)},${y(p[k])}`).join('')
  const banda = `${linha('q90')}${[...pontos].reverse().map((p) => `L${x(p.dias)},${y(p.q10)}`).join('')}Z`
  const ticksY = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxY)

  const mover = (ev: React.PointerEvent) => {
    const caixa = ref.current?.getBoundingClientRect()
    if (!caixa) return
    const dia = ((ev.clientX - caixa.left) / caixa.width * largura - m.e) / (largura - m.e - m.d) * maxDia
    let melhor = 0
    pontos.forEach((p, i) => { if (Math.abs(p.dias - dia) < Math.abs(pontos[melhor].dias - dia)) melhor = i })
    setFoco(melhor)
  }
  const p = foco === null ? null : pontos[foco]
  return (
    <div className="grafico">
      <svg ref={ref} viewBox={`0 0 ${largura} ${altura}`} onPointerMove={mover} onPointerLeave={() => setFoco(null)}
        role="img" aria-label={`Previsão de ${alvo} por dia, com faixa de 80%`}>
        <g className="grade">{ticksY.map((t) => <line key={t} x1={m.e} x2={largura - m.d} y1={y(t)} y2={y(t)} />)}</g>
        <g className="eixo">
          {ticksY.map((t) => <text key={t} x={m.e - 8} y={y(t) + 4} textAnchor="end">{compacto(t)}</text>)}
          {pontos.map((p) => <text key={p.dias} x={x(p.dias)} y={altura - 10} textAnchor="middle">{p.dias}d</text>)}
        </g>
        <path d={banda} fill="var(--serie-banda)" />
        <path d={linha('q50')} fill="none" stroke="var(--serie-1)" strokeWidth={2} strokeLinejoin="round" />
        {pontos.map((pt, i) => (
          <circle key={pt.dias} cx={x(pt.dias)} cy={y(pt.q50)} r={foco === i ? 5 : 4} fill="var(--serie-1)" stroke="var(--superficie-2)" strokeWidth={2} />
        ))}
        {p && <line x1={x(p.dias)} x2={x(p.dias)} y1={m.t} y2={altura - m.b} stroke="var(--contorno)" strokeDasharray="3 3" />}
      </svg>
      {p && (
        <div className="tooltip" style={{ left: `${(x(p.dias) / largura) * 100}%`, top: `${(y(p.q90) / altura) * 100}%` }}>
          <b>{p.dias} {p.dias === 1 ? 'dia' : 'dias'}</b><br />
          mediana {compacto(p.q50)} {alvo}<br />
          <span className="sub">faixa {compacto(p.q10)} – {compacto(p.q90)}</span>
        </div>
      )}
    </div>
  )
}

// P(viral) como medidor semicircular: um número só, com o arco como apoio visual.
export function Medidor({ valor, rotulo }: { valor: number; rotulo: string }) {
  const r = 52, c = Math.PI * r
  return (
    <div className="gauge">
      <svg viewBox="0 0 128 72" width={160} role="img" aria-label={`${rotulo}: ${pct(valor, false)}`}>
        <path d="M12,64 A52,52 0 0 1 116,64" fill="none" stroke="var(--superficie-4)" strokeWidth={10} strokeLinecap="round" />
        <path d="M12,64 A52,52 0 0 1 116,64" fill="none" stroke="var(--serie-1)" strokeWidth={10} strokeLinecap="round"
          strokeDasharray={`${c * Math.min(Math.max(valor, 0), 1)} ${c}`} />
        <text x="64" y="60" textAnchor="middle" fill="var(--texto)" fontSize="22">{pct(valor, false)}</text>
      </svg>
      <span className="sub">{rotulo}</span>
    </div>
  )
}

// O descritor do gancho escreve com **negrito** em markdown: renderiza só isso.
export function TextoRico({ texto }: { texto: string }) {
  return <>{texto.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith('**') ? <b key={i}>{p.slice(2, -2)}</b> : p))}</>
}
