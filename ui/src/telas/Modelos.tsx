import { useState } from 'react'
import { api, type Experimento, type Projeto } from '../api'
import { Aviso, BarrasMae, ChipStatus, Dica, Icone, Metrica, num, pct, useCarga, Vazio } from '../componentes'

export default function Modelos({ projeto, config, aoMudar }: { projeto: string; config: Projeto; aoMudar: () => void }) {
  const { dados, erro, recarregar } = useCarga(() => api.experimentos(projeto), [projeto])
  const [aberto, setAberto] = useState<string | null>(null)
  const [vista, setVista] = useState<'simples' | 'avancada'>(config.modo === 'cientista' ? 'avancada' : 'simples')
  const [acaoErro, setAcaoErro] = useState<string | null>(null)
  const agir = (p: Promise<unknown>) =>
    p.then(() => { recarregar(); aoMudar(); setAcaoErro(null) }).catch((e: Error) => setAcaoErro(e.message))

  if (erro) return <Aviso texto={erro} />
  if (!dados) return <div className="carregando" />
  if (!dados.length) return <Vazio icone="science">Nenhum experimento ainda. Peça ao agente: <code>experimentar</code> ou <code>ciclo_automatico</code>.</Vazio>

  const ativo = dados.find((e) => e.status === 'ativo')
  const pendentes = dados.filter((e) => e.status === 'aguardando_aprovacao')
  const selecionado = dados.find((e) => e.id === aberto)
  const ordenados = [...dados].reverse()

  return (
    <div className="pilha">
      <div className="grade-cartoes">
        <Metrica icone="check_circle" rotulo="Mais preciso que a média do canal" valor={ativo ? pct(ativo.resultado.ganho) : '—'}
          detalhe={ativo ? `erro típico ${Math.exp(ativo.resultado.modelo.mae).toFixed(1)}× contra ${Math.exp(ativo.resultado.baseline.mae).toFixed(1)}× se chutasse a média do canal` : 'nenhum promovido'} />
        <Metrica icone="swap_vert" rotulo="Acerto A vs B no canal" valor={ativo ? pct(ativo.resultado.modelo.acerto_pares, false) : '—'}
          detalhe="pares de vídeos do mesmo canal (acaso = 50%)" />
        <Metrica icone="pending" rotulo="Aguardando você" valor={String(pendentes.length)}
          detalhe={config.modo === 'cientista' ? 'promoções esperam aprovação' : 'modo automático: o agente promove'} />
      </div>

      {acaoErro && <Aviso texto={acaoErro} />}
      <div className="linha" style={{ justifyContent: 'space-between' }}>
        <Dica>
          {vista === 'simples'
            ? <><b>Mais preciso que a média do canal</b>: quanto o modelo erra menos do que simplesmente chutar a média do canal. Acerto A vs B: de dois vídeos do mesmo canal, quantas vezes o modelo aponta o melhor (acaso = 50%).</>
            : <>Cada modelo é comparado <b>nas mesmas linhas de teste</b> com a média do canal e com um controle só de metadados. MAE no log: menor é melhor. Receitas com gancho ou atributos só vencem se baterem o próprio controle.</>}
        </Dica>
        <div className="segmentado" role="radiogroup" aria-label="Vista">
          <button className={vista === 'simples' ? 'ativo' : ''} onClick={() => setVista('simples')} role="radio" aria-checked={vista === 'simples'}><Icone nome="visibility" /> Simplificada</button>
          <button className={vista === 'avancada' ? 'ativo' : ''} onClick={() => setVista('avancada')} role="radio" aria-checked={vista === 'avancada'}><Icone nome="query_stats" /> Avançada</button>
        </div>
      </div>

      <div className="cartao" style={{ padding: '8px 8px' }}>
        <div className="rolagem-x">
          {vista === 'simples' ? (
            <table className="tabela">
              <thead>
                <tr><th>Modelo</th><th>Mais preciso que a média do canal</th><th className="n">Acerto A vs B</th><th>Status</th></tr>
              </thead>
              <tbody>
                {ordenados.map((e) => {
                  const g = e.resultado.ganho
                  const maior = Math.max(...ordenados.map((x) => Math.max(x.resultado.ganho, 0)), 0.01)
                  return (
                    <tr key={e.id} className={`clicavel ${aberto === e.id ? 'selecionada' : ''}`} onClick={() => setAberto(e.id)}>
                      <td>
                        <b>{e.receita.camadas.join(' + ')}</b>
                        <div className="sub">{e.alvo} · {e.resultado.n_teste} vídeos de teste</div>
                      </td>
                      <td>
                        <div className="ganho-simples">
                          <span className="trilho"><div className={g > 0 ? 'pos' : 'neg'} style={{ width: `${(Math.max(g, 0) / maior) * 100}%` }} /></span>
                          <b className={g > 0 ? 'bom-t' : 'ruim-t'}>{pct(g)}</b>
                        </div>
                        <div className="sub">erro típico {Math.exp(e.resultado.modelo.mae).toFixed(1)}× · média do canal {Math.exp(e.resultado.baseline.mae).toFixed(1)}×</div>
                      </td>
                      <td className="n">{pct(e.resultado.modelo.acerto_pares, false)}</td>
                      <td><ChipStatus status={e.status} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Receita</th><th>Hipótese do agente</th><th className="n">Teste</th>
                  <th>MAE nas mesmas linhas</th><th className="n">Acerto A vs B</th><th className="n">Faixa 80%</th><th className="n">vs média do canal</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {ordenados.map((e) => (
                  <tr key={e.id} className={`clicavel ${aberto === e.id ? 'selecionada' : ''}`} onClick={() => setAberto(e.id)}>
                    <td>
                      <b>{e.receita.camadas.join(' + ')}</b>
                      <div className="sub mono">{e.alvo} · {e.id}{e.receita.extrator ? ` · ${e.receita.extrator.replace('@cf/meta/', '')}` : ''}</div>
                    </td>
                    <td className="sub hipotese-curta" title={e.hipotese}>{e.hipotese || '—'}</td>
                    <td className="n">{e.resultado.n_teste}</td>
                    <td><BarrasMae r={e.resultado} /></td>
                    <td className="n">{pct(e.resultado.modelo.acerto_pares, false)}</td>
                    <td className="n" title="fração do teste dentro da faixa calibrada">{e.resultado.cobertura_80 ? pct(e.resultado.cobertura_80, false) : '—'}</td>
                    <td className={`n ${e.resultado.ganho > 0 ? 'bom-t' : 'ruim-t'}`}>{pct(e.resultado.ganho)}</td>
                    <td><ChipStatus status={e.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selecionado && (
        <Painel e={selecionado} fechar={() => setAberto(null)}
          promover={() => agir(api.promover(projeto, selecionado.id))}
          decidir={(aprovar, nota) => agir(api.decidir(projeto, selecionado.id, aprovar, nota))} />
      )}
    </div>
  )
}

function Painel({ e, fechar, promover, decidir }: {
  e: Experimento; fechar: () => void; promover: () => void; decidir: (aprovar: boolean, nota: string) => void
}) {
  const [nota, setNota] = useState('')
  const r = e.resultado
  const ganhos = Object.entries(r.ganho_por_atributo)
  const maior = Math.max(...ganhos.map(([, g]) => Math.abs(g)), 1e-9)
  return (
    <div className="painel" role="dialog" aria-label={`Experimento ${e.id}`}>
      <header>
        <h2>{e.receita.camadas.join(' + ')}</h2>
        <ChipStatus status={e.status} />
        <button className="btn-icone" onClick={fechar} aria-label="Fechar"><Icone nome="close" /></button>
      </header>
      <div className="corpo">
        {e.hipotese && <div className="dica"><Icone nome="lightbulb" /><div><b>Hipótese do agente</b><br />{e.hipotese}</div></div>}

        <div className="grade-cartoes">
          <Metrica icone="trending_down" rotulo="vs média do canal" valor={pct(r.ganho)} detalhe={`MAE ${num(r.modelo.mae)} vs ${num(r.baseline.mae)}`} />
          <Metrica icone="compare_arrows" rotulo="vs só metadados" valor={pct(r.melhora_sobre_controle)} detalhe={`${r.n_teste} vídeos de teste`} />
        </div>

        <div>
          <h3>Sugestões de próximos passos</h3>
          {r.sugestoes.length ? <ul>{r.sugestoes.map((s) => <li key={s}>{s}</li>)}</ul> : <p className="sub">Nenhuma.</p>}
        </div>

        {ganhos.length > 0 && (
          <div>
            <h3>Ganho por atributo</h3>
            <p className="sub">Quanto o MAE piora ao embaralhar o atributo. Positivo: o atributo ajuda.</p>
            {ganhos.map(([a, g]) => (
              <div key={a} className="ganho-atrib">
                <span className="mono" style={{ fontSize: 12 }}>{a}</span>
                <span className="trilho">
                  <div style={{ left: g >= 0 ? '50%' : `${50 - (Math.abs(g) / maior) * 50}%`, width: `${(Math.abs(g) / maior) * 50}%`, background: g >= 0 ? 'var(--serie-1)' : 'var(--neutro-1)' }} />
                </span>
                <span className="n sub">{g.toFixed(4)}</span>
              </div>
            ))}
          </div>
        )}

        <div>
          <h3>Receita</h3>
          <pre className="mono" style={{ background: 'var(--superficie-2)', padding: 12, borderRadius: 12, fontSize: 12, overflow: 'auto' }}>
            {JSON.stringify(e.receita, null, 2)}
          </pre>
        </div>

        {e.nota_humana && <div className="dica"><Icone nome="person" /><div><b>Nota humana</b><br />{e.nota_humana}</div></div>}

        {e.status === 'candidato' && <button className="btn preenchido" onClick={promover}><Icone nome="rocket_launch" />Promover</button>}
        {e.status === 'aguardando_aprovacao' && (
          <div className="pilha" style={{ gap: 8 }}>
            <textarea className="campo" rows={2} placeholder="Por que aprova ou rejeita? (o agente lê)" value={nota} onChange={(ev) => setNota(ev.target.value)} />
            <div className="linha">
              <button className="btn preenchido" onClick={() => decidir(true, nota)}><Icone nome="check" />Aprovar</button>
              <button className="btn perigo" onClick={() => decidir(false, nota)}><Icone nome="close" />Rejeitar</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
