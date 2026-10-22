import { useState } from 'react'
import { api, type AnaliseResumo } from '../api'
import { compacto, Icone, pct, TextoRico, useCarga, Vazio } from '../componentes'

// Histórico dos vídeos analisados: previsão, o que o gancho mostrou e, se acompanhado, o real.
export default function Analises({ projeto, alvo }: { projeto: string; alvo: string }) {
  const lista = useCarga(() => api.analises(projeto), [projeto])
  const [aberto, setAberto] = useState<string | null>(null)
  if (!lista.dados) return <div className="carregando" />
  if (!lista.dados.length) return <Vazio icone="history">Nenhum vídeo analisado ainda.</Vazio>
  return (
    <div className="pilha">
      <div className="cartao" style={{ padding: '8px 8px' }}>
        <div className="rolagem-x">
          <table className="tabela">
            <thead><tr><th>quando</th><th>vídeo</th><th>canal</th><th className="n">previsto em 7 dias</th><th className="n">viralizar</th><th>real</th><th>status</th></tr></thead>
            <tbody>
              {lista.dados.map((a) => {
                const p = a.previsao_7d
                const u = a.acompanhamento?.ultima
                return (
                  <tr key={a.run_id} className={`clicavel ${aberto === a.run_id ? 'selecionada' : ''}`} onClick={() => setAberto(aberto === a.run_id ? null : a.run_id)}>
                    <td className="sub">{new Date(a.inicio).toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                    <td><b>{a.titulo ?? '(sem título)'}</b>{a.fonte && <span className="sub"> · com vídeo</span>}</td>
                    <td>{a.canal ?? a.canal_id ?? '—'}</td>
                    <td className="n">{p ? <>{compacto(p.q50)} <span className="sub">({compacto(p.q25)}–{compacto(p.q75)})</span></> : '—'}</td>
                    <td className="n">{a.chances.length ? pct(a.chances[a.chances.length - 1].prob, false) : '—'}</td>
                    <td>{u ? <span className={u.dentro_da_faixa ? 'bom-t' : 'ruim-t'}>{compacto(u.real)} {alvo} aos {Math.round(u.idade_dias)} d {u.dentro_da_faixa_50 ? '· na provável' : u.dentro_da_faixa ? '· na quase certa' : '· fora'}</span> : <span className="sub">não acompanhado</span>}</td>
                    <td>{a.status === 'rodando' ? <span className="chip"><span className="pulso" /> analisando</span> : a.status === 'falhou' ? <span className="chip ruim">falhou</span> : <span className="chip bom">ok</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
      {lista.dados.filter((a) => a.run_id === aberto).map((a) => (
        <div key={a.run_id} className="cartao avaliacao">
          <div className="linha" style={{ justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0 }}>{a.titulo ?? '(sem título)'} <span className="sub">· {a.canal ?? ''} · modelo {a.experimento ?? '—'}</span></h3>
            <button className="btn-icone" onClick={() => setAberto(null)} aria-label="Fechar"><Icone nome="close" /></button>
          </div>
          {a.erro && <p className="ruim-t">{a.erro}</p>}
          {a.explicacao && <p style={{ margin: '8px 0 0' }}>{a.explicacao}</p>}
          {a.gancho && <div className="campo-texto" style={{ marginTop: 8 }}><span>O que se vê no gancho</span><span><TextoRico texto={a.gancho} /></span></div>}
          {a.fala && <div className="campo-texto"><span>O que se fala</span><span>{a.fala}</span></div>}
          {a.chances.length > 0 && <p className="sub" style={{ margin: '8px 0 0' }}>{a.chances.map((c) => `${c.evento} ${Math.round(c.prob * 100)}%`).join(' · ')}</p>}
          {a.acompanhamento?.ultima && (
            <p className="sub" style={{ margin: '6px 0 0' }}>
              Real aos {Math.round(a.acompanhamento.ultima.idade_dias)} dias: <b>{compacto(a.acompanhamento.ultima.real)} {alvo}</b>; previsto para essa idade {compacto(a.acompanhamento.ultima.previsto_q50)} (provável {compacto(a.acompanhamento.ultima.previsto_q25)}–{compacto(a.acompanhamento.ultima.previsto_q75)}).
            </p>
          )}
          <span className="sub mono">run {a.run_id}</span>
        </div>
      ))}
    </div>
  )
}
