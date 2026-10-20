import { useState } from 'react'
import { api, type Erro, type Nota } from '../api'
import { Aviso, Dica, Icone, num, useCarga, Vazio } from '../componentes'

export default function Erros({ projeto }: { projeto: string }) {
  const relatorio = useCarga(() => api.erros(projeto), [projeto])
  const notas = useCarga(() => api.notas(projeto), [projeto])
  const canais = useCarga(() => api.canais(projeto), [projeto])
  const nomes = new Map((canais.dados ?? []).map((c) => [c.id, c.titulo]))
  if (relatorio.erro) return <Aviso texto={relatorio.erro} />
  if (!relatorio.dados) return <div className="carregando" />
  const r = relatorio.dados
  const anotar = (video: string, tipo: Nota['tipo'], nota: string) =>
    api.anotar(projeto, video, tipo, nota).then(() => { notas.recarregar(); relatorio.recarregar() })

  return (
    <div className="pilha">
      <Dica>
        Piores previsões do <b>{r.origem || 'último treino'}</b>. Marque <b>dado ruim</b> para tirar o vídeo da base,
        ou <b>padrão</b> para deixar uma pista que o agente lê ao criar novos atributos.
      </Dica>
      <div className="grade-2" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(280px, 1fr)' }}>
        <div className="cartao" style={{ padding: 8 }}>
          {r.piores.length ? (
            <div className="rolagem-x">
              <table className="tabela">
                <thead><tr><th>Vídeo</th><th className="n">Previsto</th><th className="n">Real</th><th className="n">Erro</th><th>Triagem</th></tr></thead>
                <tbody>
                  {r.piores.map((e) => <Linha key={e.video_id} e={e} canal={nomes.get(e.canal_id) ?? e.canal_id} anotar={anotar} nota={notas.dados?.find((n) => n.video_id === e.video_id)} />)}
                </tbody>
              </table>
              <p className="sub" style={{ padding: '0 12px' }}>Previsto e real em log(1 + alvo).</p>
            </div>
          ) : <Vazio icone="query_stats">Sem previsões ainda. Promova um modelo ou rode treinar.</Vazio>}
        </div>
        <div className="pilha">
          <div className="cartao">
            <h3>Falhas do pipeline</h3>
            {Object.keys(r.falhas_por_etapa).length
              ? Object.entries(r.falhas_por_etapa).map(([etapa, n]) => (
                <div key={etapa} className="linha" style={{ justifyContent: 'space-between' }}><span className="mono">{etapa}</span><span>{n}</span></div>
              ))
              : <p className="sub">Nenhuma.</p>}
          </div>
          {Object.entries(r.segmentos).map(([nome, segs]) => (
            <div key={nome} className="cartao">
              <h3>Erro por {nome}</h3>
              {segs.slice(0, 5).map((s) => (
                <div key={s.chave} className="linha" style={{ justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>{nome === 'canal' ? nomes.get(s.chave) ?? s.chave : s.chave}</span>
                  <span className="sub">MAE {num(s.mae, 2)} · {s.n}</span>
                </div>
              ))}
            </div>
          ))}
          <div className="cartao">
            <h3>Pistas para o agente</h3>
            {r.notas_padrao.length ? <ul style={{ margin: 0, paddingLeft: 18 }}>{r.notas_padrao.map((n) => <li key={n}>{n}</li>)}</ul> : <p className="sub">Nenhuma ainda.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

function Linha({ e, canal, nota, anotar }: { e: Erro; canal: string; nota?: Nota; anotar: (v: string, t: Nota['tipo'], n: string) => Promise<unknown> }) {
  const [texto, setTexto] = useState('')
  return (
    <tr>
      <td><a className="mono" href={`https://youtube.com/shorts/${e.video_id}`} target="_blank" rel="noreferrer">{e.video_id}</a><div className="sub">{canal}</div></td>
      <td className="n">{num(e.previsto, 2)}</td>
      <td className="n">{num(e.real, 2)}</td>
      <td className="n">{num(e.erro_log, 2)}</td>
      <td>
        {nota ? (
          <span className={`chip ${nota.tipo === 'dado_ruim' ? 'ruim' : 'primario'}`}>
            <Icone nome={nota.tipo === 'dado_ruim' ? 'block' : 'lightbulb'} />{nota.nota || nota.tipo.replace('_', ' ')}
          </span>
        ) : (
          <div className="linha" style={{ flexWrap: 'nowrap' }}>
            <input className="campo" style={{ padding: '6px 10px', minWidth: 120 }} placeholder="nota" value={texto} onChange={(ev) => setTexto(ev.target.value)} />
            <button className="btn-icone" title="Dado ruim: tirar da base" onClick={() => anotar(e.video_id, 'dado_ruim', texto)}><Icone nome="block" /></button>
            <button className="btn-icone" title="Padrão: pista para o agente" onClick={() => anotar(e.video_id, 'padrao', texto)}><Icone nome="lightbulb" /></button>
          </div>
        )}
      </td>
    </tr>
  )
}
