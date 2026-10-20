import { useEffect, useState } from 'react'
import { api, type Etapa, type Run } from '../api'
import { useCarga, Vazio } from '../componentes'

const LIMITE = 300

export default function Trace({ projeto }: { projeto: string }) {
  const runs = useCarga(() => api.runs(projeto), [projeto])
  const [filtro, setFiltro] = useState('')
  const [run, setRun] = useState<Run | null>(null)
  const [etapas, setEtapas] = useState<Etapa[] | null>(null)
  useEffect(() => {
    if (!run) return
    setEtapas(null)
    api.trace(projeto, run.id).then(setEtapas)
  }, [projeto, run])

  const lista = [...(runs.dados ?? [])].reverse().filter((r) => r.operacao.includes(filtro)).slice(0, 300)
  const operacoes = [...new Set(runs.dados?.map((r) => r.operacao))]

  return (
    <div className="duas-colunas">
      <div className="pilha" style={{ gap: 8 }}>
        <select className="campo" value={filtro} onChange={(e) => setFiltro(e.target.value)} aria-label="Filtrar operação">
          <option value="">Todas as operações</option>
          {operacoes.map((o) => <option key={o}>{o}</option>)}
        </select>
        <div className="lista-lateral">
          {lista.map((r) => (
            <button key={r.id} className={run?.id === r.id ? 'ativo' : ''} onClick={() => setRun(r)}>
              <span style={{ fontWeight: 500 }}>{r.operacao}</span>
              <span className={`sub ${r.status === 'falhou' ? 'ruim-t' : ''}`}>{r.status} · {new Date(r.inicio).toLocaleString('pt-BR')}</span>
            </button>
          ))}
        </div>
      </div>
      <div style={{ minWidth: 0 }}>
        {!run && <Vazio icone="account_tree">Escolha uma execução para ver cada passo, com entrada, saída e duração.</Vazio>}
        {run && !etapas && <div className="carregando" />}
        {etapas && etapas.length > LIMITE && <p className="sub">Mostrando {LIMITE} de {etapas.length} etapas.</p>}
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
  )
}
