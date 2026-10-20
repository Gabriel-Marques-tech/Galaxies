import { useState } from 'react'
import { api, type Analise, type Projeto } from '../api'
import { Aviso, compacto, GraficoTimeline, Icone, pct, TextoRico, useCarga } from '../componentes'

type Conversa = { pergunta: string; canal: string; analise?: Analise; erro?: string }

export default function Analisar({ projeto, config }: { projeto: string; config: Projeto }) {
  const canais = useCarga(() => api.canais(projeto), [projeto])
  const [titulo, setTitulo] = useState('')
  const [canal, setCanal] = useState('')
  const [duracao, setDuracao] = useState(30)
  const [hora, setHora] = useState('18:00')
  const [fonte, setFonte] = useState('')
  const [conversas, setConversas] = useState<Conversa[]>([])
  const [rodando, setRodando] = useState(false)
  const canalEscolhido = canal || canais.dados?.[0]?.id || ''
  const nomeCanal = (id: string) => canais.dados?.find((c) => c.id === id)?.titulo ?? id

  const enviar = () => {
    if (!titulo.trim() || !canalEscolhido) return
    const publicar = new Date(); const [h, m] = hora.split(':').map(Number)
    publicar.setHours(h, m, 0, 0)
    const pergunta = titulo
    setRodando(true); setTitulo('')
    api.analisar(projeto, { titulo: pergunta, duracao_s: duracao, publicar_em: publicar.toISOString(), fonte: fonte || undefined }, canalEscolhido)
      .then((analise) => setConversas((c) => [...c, { pergunta, canal: canalEscolhido, analise }]))
      .catch((e: Error) => setConversas((c) => [...c, { pergunta, canal: canalEscolhido, erro: e.message }]))
      .finally(() => setRodando(false))
  }

  return (
    <div className="pilha" style={{ maxWidth: 860, margin: '0 auto' }}>
      {!conversas.length && (
        <div className="saudacao">
          <h2>Antes de publicar</h2>
          <p>Escreva o título do Short, escolha o canal e veja como ele deve performar.</p>
        </div>
      )}

      {conversas.map((c, i) => (
        <div key={i} className="pilha">
          <div className="pergunta-usuario">{c.pergunta}<div className="sub">{nomeCanal(c.canal)}</div></div>
          <div className="resposta">
            <span className="avatar"><Icone nome="blur_on" /></span>
            {c.erro ? <Aviso texto={c.erro} /> : c.analise && <Resultado a={c.analise} alvo={config.alvo} />}
          </div>
        </div>
      ))}
      {rodando && <div className="resposta"><span className="avatar"><Icone nome="blur_on" /></span><div className="carregando" style={{ marginTop: 14 }} /></div>}

      <div className="compositor" style={{ position: 'sticky', bottom: 0 }}>
        <textarea rows={1} placeholder="Título do Short, ex.: 3 erros que deixam sua base craquelada" value={titulo}
          onChange={(e) => setTitulo(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar() } }} />
        <div className="opcoes">
          <select value={canalEscolhido} onChange={(e) => setCanal(e.target.value)} aria-label="Canal">
            {canais.dados?.map((c) => <option key={c.id} value={c.id}>{c.titulo} · {c.setor}</option>)}
          </select>
          <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} aria-label="Horário de publicação" />
          <select value={duracao} onChange={(e) => setDuracao(Number(e.target.value))} aria-label="Duração">
            {[15, 30, 45, 60, 90].map((d) => <option key={d} value={d}>{d}s</option>)}
          </select>
          <input placeholder="arquivo ou link (opcional)" value={fonte} onChange={(e) => setFonte(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <button className="enviar" onClick={enviar} disabled={rodando || !titulo.trim()} aria-label="Analisar"><Icone nome="arrow_upward" /></button>
        </div>
      </div>
      <p className="sub" style={{ textAlign: 'center', margin: 0 }}>
        Previsões e sugestões vêm de padrões da base (correlação, não causa). Use para priorizar testes.
      </p>
    </div>
  )
}

function Resultado({ a, alvo }: { a: Analise; alvo: string }) {
  const p = a.previsao_7d
  return (
    <div className="pilha" style={{ minWidth: 0 }}>
      <p style={{ margin: 0, fontSize: 16 }}>
        Em 7 dias, o mais provável é <b>{compacto(p.q50)} {alvo}</b>, com 80% de chance de ficar entre {compacto(p.q10)} e {compacto(p.q90)}.
        A chance de viralizar ({a.limite_viral}× a mediana do canal em {a.dias_viral} dias) é de <b>{pct(a.p_viral, false)}</b>.
      </p>
      <div className="grade-2">
        <div className="cartao">
          <h3>Timeline prevista</h3>
          <p className="descricao">Mediana e faixa de 80%</p>
          <GraficoTimeline pontos={a.timeline} alvo={alvo} />
        </div>
        <div className="cartao">
          <h3>Chances em {a.dias_viral} dias</h3>
          <p className="descricao">Hipóteses sobre a mediana do canal ({compacto(a.mediana_canal)} {alvo})</p>
          <div className="chances">
            {a.chances.map((c) => (
              <div key={c.evento} className="chance">
                <span>{c.evento}<span className="sub"> · {c.multiplo}×</span></span>
                <span className="trilho"><div style={{ width: `${c.prob * 100}%` }} /></span>
                <b className="n">{pct(c.prob, false)}</b>
              </div>
            ))}
          </div>
        </div>
      </div>

      {a.sugestoes.length > 0 && (
        <div className="cartao">
          <h3>Para aumentar a chance de viralizar</h3>
          <p className="descricao">Mudanças que o modelo associa a mais alcance neste canal. São hipóteses para testar, não garantia.</p>
          <div className="pilha" style={{ gap: 8 }}>
            {a.sugestoes.map((s) => (
              <div key={s.mudanca} className="sugestao">
                <Icone nome="trending_up" className="destaque-icone" />
                <span className="o-que">{s.mudanca}</span>
                <span className="sub">viral {pct(a.p_viral, false)} → <b className="bom-t">{pct(s.p_viral, false)}</b></span>
                <span className="sub">7 dias {pct(s.ganho)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="cartao">
        <h3>O que mais pesou</h3>
        <p className="descricao">Contribuição de cada fator na previsão (SHAP)</p>
        {a.fatores.map((f) => (
          <div key={f.feature} className="ganho-atrib">
            <span className="mono" style={{ fontSize: 12 }}>{f.feature}</span>
            <span className="trilho">
              <div style={{ left: f.impacto >= 0 ? '50%' : `${50 - Math.min(Math.abs(f.impacto) * 50, 50)}%`, width: `${Math.min(Math.abs(f.impacto) * 50, 50)}%`, background: f.impacto >= 0 ? 'var(--serie-1)' : 'var(--neutro-1)' }} />
            </span>
            <span className="n sub">{f.impacto >= 0 ? '+' : ''}{f.impacto.toFixed(2)}</span>
          </div>
        ))}
      </div>

      {a.gancho && (
        <div className="cartao contorno">
          <h3>O que o modelo viu no gancho</h3>
          <p style={{ margin: '4px 0' }}><TextoRico texto={a.gancho.descricao} /></p>
          <p className="sub" style={{ margin: 0 }}>Fala: {a.gancho.transcricao || '(sem fala)'}</p>
        </div>
      )}
      <span className="sub mono">modelo {a.experimento_id} · run {a.run_id}</span>
    </div>
  )
}
