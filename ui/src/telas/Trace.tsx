import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type Etapa, type Run } from '../api'
import { Icone, useCarga, Vazio } from '../componentes'

// Trace como linha do tempo horizontal (estilo git graph): cada execução é um nó, em ramos por
// tipo (dados, modelo, análise, humano). Clique num nó para ver os passos dele.

const LANES: { id: string; nome: string; ops: string[] }[] = [
  { id: 'modelo', nome: 'Modelo', ops: ['experimentar', 'otimizar', 'treinar', 'promover', 'ciclo_automatico'] },
  { id: 'dados', nome: 'Dados', ops: ['coletar', 'adicionar_canal', 'descobrir', 'processar_ganchos', 'reprocessar', 'calcular_atributos', 'calcular_texto'] },
  { id: 'analise', nome: 'Análise', ops: ['analisar', 'comparar'] },
  { id: 'projeto', nome: 'Projeto', ops: ['criar_projeto', 'definir_atributos'] },
]
const PASSO = 54, ESQ = 72, TOPO = 44, ALTURA_LANE = 52, LIMITE = 300
const laneDe = (op: string) => Math.max(0, LANES.findIndex((l) => l.ops.includes(op)))

export default function Trace({ projeto }: { projeto: string }) {
  const runs = useCarga(() => api.runs(projeto), [projeto])
  const [sel, setSel] = useState<Run | null>(null)
  const [etapas, setEtapas] = useState<Etapa[] | null>(null)
  const rolagem = useRef<HTMLDivElement>(null)
  const lista = useMemo(() => (runs.dados ?? []).slice(-LIMITE), [runs.dados])

  useEffect(() => { rolagem.current?.scrollTo({ left: rolagem.current.scrollWidth }) }, [lista])
  useEffect(() => {
    if (!sel) return
    setEtapas(null)
    api.trace(projeto, sel.id).then(setEtapas)
  }, [projeto, sel])

  if (!runs.dados) return <div className="carregando" />
  if (!lista.length) return <Vazio icone="account_tree">Nenhuma execução ainda.</Vazio>

  const contagem = lista.reduce<Record<string, number>>((acc, r) => ((acc[r.operacao] = (acc[r.operacao] ?? 0) + 1), acc), {})
  const falhas = lista.filter((r) => r.status === 'falhou').length
  const inicio = new Date(lista[0].inicio), fim = new Date(lista[lista.length - 1].inicio)
  const largura = ESQ + lista.length * PASSO + 60
  const altura = TOPO + LANES.length * ALTURA_LANE
  const x = (i: number) => ESQ + i * PASSO
  const y = (lane: number) => TOPO + lane * ALTURA_LANE + 10

  // ramos: liga cada nó ao anterior do mesmo ramo; e ao nó imediatamente anterior se mudou de ramo
  const ligacoes: string[] = []
  const ultimoNaLane: number[] = []
  lista.forEach((r, i) => {
    const lane = laneDe(r.operacao)
    const ant = ultimoNaLane[lane]
    if (ant !== undefined) ligacoes.push(`M${x(ant)},${y(lane)} L${x(i)},${y(lane)}`)
    if (i > 0 && laneDe(lista[i - 1].operacao) !== lane) {
      const la = laneDe(lista[i - 1].operacao)
      const mx = (x(i - 1) + x(i)) / 2
      ligacoes.push(`M${x(i - 1)},${y(la)} C${mx},${y(la)} ${mx},${y(lane)} ${x(i)},${y(lane)}`)
    }
    ultimoNaLane[lane] = i
  })

  return (
    <div className="pilha">
      <div className="linha" style={{ gap: 8 }}>
        <span className="chip"><Icone nome="schedule" />{inicio.toLocaleDateString('pt-BR')} → {fim.toLocaleDateString('pt-BR')}</span>
        {Object.entries(contagem).sort((a, b) => b[1] - a[1]).map(([op, n]) => (
          <span key={op} className="chip"><span className="ponto-lane" style={{ background: corLane(laneDe(op)) }} />{n} {op}</span>
        ))}
        {falhas > 0 && <span className="chip ruim"><Icone nome="error" />{falhas} com falha</span>}
      </div>

      <div className="cartao" style={{ padding: '12px 0 8px' }}>
        <div className="grafo" ref={rolagem}>
          <svg width={largura} height={altura} role="img" aria-label="Linha do tempo das execuções">
            {LANES.map((l, li) => (
              <g key={l.id}>
                <line x1={ESQ - 20} x2={largura} y1={y(li)} y2={y(li)} stroke="var(--contorno-suave)" strokeDasharray="2 6" />
                <text x={8} y={y(li) + 4} className="rotulo-lane" style={{ fill: corLane(li) }}>{l.nome}</text>
              </g>
            ))}
            {lista.map((r, i) => {
              const d = new Date(r.inicio)
              const novoDia = i === 0 || d.toDateString() !== new Date(lista[i - 1].inicio).toDateString()
              return novoDia ? <text key={`d${i}`} x={x(i)} y={TOPO - 24} textAnchor="middle" className="rotulo-dia">{d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}</text> : null
            })}
            <g fill="none" strokeWidth={2}>
              {ligacoes.map((d, i) => <path key={i} d={d} stroke="var(--contorno)" />)}
            </g>
            {lista.map((r, i) => {
              const lane = laneDe(r.operacao)
              const grande = r.operacao === 'otimizar' || r.operacao === 'ciclo_automatico'
              const ativo = sel?.id === r.id
              return (
                <g key={r.id} className="no" onClick={() => setSel(r)} style={{ cursor: 'pointer' }}>
                  <title>{`${r.operacao} · ${r.status} · ${new Date(r.inicio).toLocaleString('pt-BR')}`}</title>
                  {ativo && <circle cx={x(i)} cy={y(lane)} r={grande ? 15 : 11} fill="none" stroke="var(--primaria)" strokeWidth={2} opacity={.7} />}
                  <circle cx={x(i)} cy={y(lane)} r={grande ? 9 : 6}
                    fill={r.status === 'falhou' ? 'var(--ruim)' : r.status === 'rodando' ? 'var(--aviso)' : corLane(lane)}
                    stroke="var(--superficie-2)" strokeWidth={2} />
                  {grande && <text x={x(i)} y={y(lane) + 24} textAnchor="middle" className="rotulo-no">{r.operacao}</text>}
                </g>
              )
            })}
          </svg>
        </div>
        <p className="sub" style={{ margin: '4px 16px 0' }}>Da esquerda para a direita no tempo. Nós maiores são otimizações do agente. Vermelho = falhou.</p>
      </div>

      {!sel && <p className="sub" style={{ textAlign: 'center' }}>Clique num nó para ver os passos daquela execução.</p>}
      {sel && (
        <div className="cartao">
          <div className="linha" style={{ justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0 }}>{sel.operacao} <span className="sub">· {sel.status} · {new Date(sel.inicio).toLocaleString('pt-BR')}</span></h3>
            <button className="btn-icone" onClick={() => setSel(null)} aria-label="Fechar"><Icone nome="close" /></button>
          </div>
          {!etapas && <div className="carregando" />}
          {etapas && etapas.length > LIMITE && <p className="sub">Mostrando {LIMITE} de {etapas.length} etapas.</p>}
          <div style={{ marginTop: 8 }}>
            {etapas?.slice(0, LIMITE).map((e, i) => (
              <div key={i} className={`etapa ${e.erro ? 'falhou' : ''}`}>
                <details>
                  <summary style={{ cursor: 'pointer' }}>
                    <b>{e.nome}</b> <span className="sub">{e.duracao_ms.toFixed(0)} ms</span>
                    {e.erro && <span className="ruim-t"> · {e.erro}</span>}
                  </summary>
                  <pre>{JSON.stringify({ entrada: e.entrada, saida: e.saida }, null, 2)}</pre>
                </details>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function corLane(i: number) {
  return ['var(--primaria)', 'var(--serie-1)', 'var(--bom)', 'var(--neutro-1)'][i] ?? 'var(--neutro-1)'
}
