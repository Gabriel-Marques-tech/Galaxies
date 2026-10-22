import { useRef, useState } from 'react'
import { api, type Analise, type Projeto } from '../api'
import { Aviso, compacto, GraficoTimeline, Icone, pct, TextoRico, useCarga } from '../componentes'

type Conversa = { pergunta: string; canal: string; analise?: Analise; erro?: string }
type Short = { fonte: string; nome: string; url?: string }

export default function Analisar({ projeto, config }: { projeto: string; config: Projeto }) {
  const canais = useCarga(() => api.canais(projeto), [projeto])
  const [titulo, setTitulo] = useState('')
  const [canal, setCanal] = useState('')
  const [duracao, setDuracao] = useState(30)
  const [hora, setHora] = useState('18:00')
  const [short, setShort] = useState<Short | null>(null)
  const [conversas, setConversas] = useState<Conversa[]>([])
  const [rodando, setRodando] = useState(false)
  const canalEscolhido = canal || canais.dados?.[0]?.id || ''
  const nomeCanal = (id: string) => canais.dados?.find((c) => c.id === id)?.titulo ?? id

  const enviar = () => {
    if (!titulo.trim() || !canalEscolhido || rodando) return
    const publicar = new Date(); const [h, m] = hora.split(':').map(Number)
    publicar.setHours(h, m, 0, 0)
    const pergunta = titulo
    setRodando(true); setTitulo('')
    api.analisar(projeto, { titulo: pergunta, duracao_s: duracao, publicar_em: publicar.toISOString(), fonte: short?.fonte }, canalEscolhido)
      .then((analise) => setConversas((c) => [...c, { pergunta, canal: canalEscolhido, analise }]))
      .catch((e: Error) => setConversas((c) => [...c, { pergunta, canal: canalEscolhido, erro: e.message }]))
      .finally(() => setRodando(false))
  }

  return (
    <div className={`analise ${conversas.length || rodando ? 'com-resultados' : ''}`}>
      {!conversas.length && !rodando && (
        <div className="saudacao compacta">
          <h2>Antes de publicar</h2>
          <p>Suba o Short (ou só o título), escolha o canal e veja como ele deve performar.</p>
        </div>
      )}
      <div className="meio-analise rolagem-fina">
      {conversas.map((c, i) => (
        <div key={i} className="pilha">
          <div className="pergunta-usuario">{c.pergunta}<div className="sub">{nomeCanal(c.canal)}</div></div>
          <div className="resposta">
            <span className="avatar"><img src="/logo.svg" alt="" style={{ width: 20, height: 20 }} /></span>
            {c.erro ? <Aviso texto={c.erro} /> : c.analise && <Resultado a={c.analise} alvo={config.alvo} projeto={projeto} />}
          </div>
        </div>
      ))}
      {rodando && (
        <div className="resposta">
          <span className="avatar pensando"><img src="/logo.svg" alt="" style={{ width: 20, height: 20 }} /></span>
          <div className="pontos" aria-label="Analisando"><i /><i /><i /></div>
        </div>
      )}
      </div>

      <div className="rodape-analise">
        <div className="palco">
          <ShortDrop projeto={projeto} short={short} setShort={setShort} />
        </div>
        <div className="compositor">
          <textarea rows={1} placeholder="Título do Short, ex.: 3 erros que deixam sua base craquelada" value={titulo}
            onChange={(e) => setTitulo(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar() } }} />
          <div className="opcoes">
            <select value={canalEscolhido} onChange={(e) => setCanal(e.target.value)} aria-label="Canal">
              {canais.dados?.map((c) => <option key={c.id} value={c.id}>{c.titulo} · {c.setor}</option>)}
            </select>
            <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} aria-label="Horário de publicação" />
            <select value={duracao} onChange={(e) => setDuracao(Number(e.target.value))} aria-label="Duração">
              {[15, 30, 45, 60, 90, 120, 180].map((d) => <option key={d} value={d}>{d}s</option>)}
            </select>
            <button className="enviar" onClick={enviar} disabled={rodando || !titulo.trim()} aria-label="Analisar"><Icone nome="arrow_upward" /></button>
          </div>
        </div>
        <p className="sub" style={{ textAlign: 'center', margin: 0 }}>
          Previsões e sugestões vêm de padrões da base (correlação, não causa). Use para priorizar testes.
        </p>
      </div>
    </div>
  )
}

// O "Short": retângulo 9:16 acima da barra. Arraste o vídeo, clique para escolher, ou cole um link.
function ShortDrop({ projeto, short, setShort }: { projeto: string; short: Short | null; setShort: (s: Short | null) => void }) {
  const entrada = useRef<HTMLInputElement>(null)
  const [sobre, setSobre] = useState(false)
  const [subindo, setSubindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const receber = (arquivo: File) => {
    setSubindo(true); setErro(null)
    api.upload(projeto, arquivo)
      .then((r) => setShort({ ...r, url: URL.createObjectURL(arquivo) }))
      .catch((e: Error) => setErro(e.message))
      .finally(() => setSubindo(false))
  }
  const colar = (e: React.ClipboardEvent) => {
    const texto = e.clipboardData.getData('text').trim()
    if (/^https?:\/\//.test(texto)) { e.preventDefault(); setShort({ fonte: texto, nome: texto.replace(/^https?:\/\//, '') }) }
  }
  const pedirLink = () => {
    const link = window.prompt('Link do Short (YouTube) ou caminho do arquivo:')
    if (link?.trim()) setShort({ fonte: link.trim(), nome: link.trim().replace(/^https?:\/\//, '') })
  }

  if (short) {
    return (
      <div className="short-drop pronto" title={short.fonte}>
        {short.url ? <video src={short.url} controls playsInline loop autoPlay muted /> : <Icone nome="link" />}
        <span className="nome-arquivo">{short.nome}</span>
        <button className="remover" onClick={() => setShort(null)} aria-label="Remover vídeo"><Icone nome="close" /></button>
      </div>
    )
  }
  return (
    <div
      className={`short-drop ${sobre ? 'sobre' : ''}`}
      role="button" tabIndex={0} aria-label="Subir o Short"
      onClick={() => entrada.current?.click()}
      onContextMenu={(e) => { e.preventDefault(); pedirLink() }}
      onKeyDown={(e) => { if (e.key === 'Enter') entrada.current?.click() }}
      onPaste={colar}
      onDragOver={(e) => { e.preventDefault(); setSobre(true) }}
      onDragLeave={() => setSobre(false)}
      onDrop={(e) => { e.preventDefault(); setSobre(false); const f = e.dataTransfer.files[0]; if (f) receber(f) }}
    >
      <input ref={entrada} type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) receber(f) }} />
      {subindo ? <div className="pontos"><i /><i /><i /></div> : (
        <div>
          <Icone nome="add" />
          <div>{erro ? <span className="ruim-t">{erro}</span> : <>Subir o Short<br /><span style={{ opacity: .7 }}>ou botão direito p/ link</span></>}</div>
        </div>
      )}
    </div>
  )
}

function Resultado({ a, alvo, projeto }: { a: Analise; alvo: string; projeto: string }) {
  const p = a.previsao_7d
  return (
    <div className="pilha" style={{ minWidth: 0 }}>
      <p style={{ margin: 0, fontSize: 16 }}>
        Em 7 dias, o mais provável é <b>{compacto(p.q50)} {alvo}</b>: na metade dos casos fica entre {compacto(p.q25)} e {compacto(p.q75)}; é quase certo (80%) que fique entre {compacto(p.q10)} e {compacto(p.q90)}.
        A chance de viralizar ({a.limite_viral}× a mediana do canal em {a.dias_viral} dias) é de <b>{pct(a.p_viral, false)}</b>.
      </p>
      {a.explicacao && <p className="sub" style={{ margin: 0 }}>{a.explicacao.split('. ').slice(2).join('. ')}</p>}
      <div className="grade-2">
        <div className="cartao">
          <h3>Timeline prevista</h3>
          <p className="descricao">Mediana, faixa provável (50%) e quase certa (80%)</p>
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
      <Publiquei projeto={projeto} runId={a.run_id} />
      <span className="sub mono">modelo {a.experimento_id} · run {a.run_id}</span>
    </div>
  )
}

// Depois de publicar: liga esta análise ao vídeo real para acompanhar previsto × real.
function Publiquei({ projeto, runId }: { projeto: string; runId: string }) {
  const [id, setId] = useState('')
  const [estado, setEstado] = useState<string | null>(null)
  const enviar = () => {
    const videoId = id.trim().replace(/^.*(?:shorts\/|v=|youtu\.be\/)/, '').split(/[?&]/)[0]
    api.acompanhar(projeto, runId, videoId)
      .then((a) => setEstado(`acompanhando ${a.video_id}: ${a.observacoes[0]?.likes ?? '—'} likes até agora`))
      .catch((e: Error) => setEstado(e.message))
  }
  return (
    <div className="cartao contorno linha" style={{ gap: 10 }}>
      <Icone nome="publish" className="destaque-icone" />
      <span style={{ flex: 1, minWidth: 160 }}><b>Publicou?</b> <span className="sub">Cole o link ou id do Short para acompanhar previsto × real.</span></span>
      <input className="campo" style={{ maxWidth: 260 }} placeholder="link ou id do vídeo" value={id} onChange={(e) => setId(e.target.value)} />
      <button className="btn tonal pequeno" onClick={enviar} disabled={!id.trim()}>Acompanhar</button>
      {estado && <span className="sub" style={{ width: '100%' }}>{estado}</span>}
    </div>
  )
}
