import { useEffect, useRef, useState } from 'react'
import { api, type Experimento, type Insights } from '../api'
import { compacto, Icone, pct, useCarga } from '../componentes'

// Tela inicial: feed vertical de projetos (um por vez, como Shorts). Arrastar um card para o
// lado abre a criação de projeto. Ao lado, analytics rápidas do projeto em foco.

type Cartao = { nome: string; ativo?: Experimento; total: number }
const ARRASTO_PARA_CRIAR = 90 // px para o lado

export default function Projetos({ projetos, abrir, aoCriar }: {
  projetos: string[]; abrir: (nome: string) => void; aoCriar: () => void
}) {
  const [cartoes, setCartoes] = useState<Cartao[]>([])
  const [criando, setCriando] = useState(false)
  const [foco, setFoco] = useState(0)
  const feed = useRef<HTMLDivElement>(null)
  useEffect(() => {
    Promise.all(
      projetos.map(async (nome) => {
        const exps = await api.experimentos(nome).catch(() => [] as Experimento[])
        return { nome, ativo: exps.find((e) => e.status === 'ativo'), total: exps.length }
      }),
    ).then((lista) => { setCartoes(lista); requestAnimationFrame(() => feed.current?.scrollTo({ top: 0 })) })
  }, [projetos])

  // o card mais perto do topo do feed é o "em foco": os insights ao lado são dele
  const aoRolar = () => {
    const el = feed.current
    if (!el) return
    const filhos = Array.from(el.querySelectorAll<HTMLElement>('.cartao-projeto:not(.novo)'))
    let melhor = 0, dist = Infinity
    filhos.forEach((f, i) => { const d = Math.abs(f.offsetTop - el.scrollTop); if (d < dist) { dist = d; melhor = i } })
    setFoco(melhor)
  }
  const emFoco = cartoes[foco]

  return (
    <div className="pilha">
      <div className="saudacao">
        <h2>Olá</h2>
        <p>Role para escolher o projeto. Arraste um card para o lado para criar outro.</p>
      </div>
      <div className="projetos-grade">
        <div className="feed" ref={feed} onScroll={aoRolar} aria-label="Projetos">
          {cartoes.map((c, i) => (
            <CartaoProjeto key={c.nome} c={c} emFoco={i === foco} abrir={() => abrir(c.nome)} criar={() => setCriando(true)} />
          ))}
          <button className="cartao-projeto novo" onClick={() => setCriando(true)} aria-label="Novo projeto">
            <Icone nome="add" />
            <span style={{ fontSize: 13, fontWeight: 500, marginTop: 8 }}>Novo projeto</span>
          </button>
          <div className="feed-fim" />
        </div>
        {emFoco ? <PainelInsights projeto={emFoco.nome} ativo={emFoco.ativo} /> : <div />}
      </div>
      {criando && <NovoProjeto fechar={() => setCriando(false)} criado={(nome) => { setCriando(false); aoCriar(); abrir(nome) }} />}
    </div>
  )
}

function CartaoProjeto({ c, emFoco, abrir, criar }: { c: Cartao; emFoco: boolean; abrir: () => void; criar: () => void }) {
  const ganho = c.ativo?.resultado.ganho
  const [dx, setDx] = useState(0)
  const inicio = useRef<number | null>(null)
  const arrastou = useRef(false)
  return (
    <button
      className={`cartao-projeto ${emFoco ? 'foco' : ''} ${dx ? 'arrastando' : ''}`}
      style={{ transform: dx ? `translateX(${dx}px) rotate(${dx / 40}deg)` : undefined, opacity: dx ? 1 - Math.min(Math.abs(dx) / 260, 0.5) : undefined }}
      onPointerDown={(e) => { inicio.current = e.clientX; arrastou.current = false }}
      onPointerMove={(e) => { if (inicio.current === null || !(e.buttons & 1)) return; const d = e.clientX - inicio.current; if (Math.abs(d) > 6) { arrastou.current = true; setDx(d) } }}
      onPointerUp={() => { if (Math.abs(dx) > ARRASTO_PARA_CRIAR) criar(); setDx(0); inicio.current = null }}
      onPointerLeave={() => { setDx(0); inicio.current = null }}
      onClick={() => { if (!arrastou.current) abrir() }}
    >
      <span className="icone-proj"><Icone nome="smart_display" cheio /></span>
      <span className="nome-proj">{c.nome}</span>
      <span className="sub">{c.total} experimento{c.total === 1 ? '' : 's'}</span>
      <span className="grande">{ganho === undefined ? '—' : `−${pct(ganho, false)}`}</span>
      <span className="sub">{ganho === undefined ? 'sem modelo ativo' : 'de erro vs baseline'}</span>
      <span className="abrir-proj"><Icone nome="arrow_forward" /> abrir</span>
      {Math.abs(dx) > ARRASTO_PARA_CRIAR / 2 && <span className="dica-criar"><Icone nome="add" /> solte para criar um projeto</span>}
    </button>
  )
}

const sinal = (v: number) => `${v >= 0 ? '+' : '−'}${Math.round(Math.abs(v) * 100)}%`

function PainelInsights({ projeto, ativo }: { projeto: string; ativo?: Experimento }) {
  const ins = useCarga(() => api.insights(projeto), [projeto])
  const d: Insights | null = ins.dados
  return (
    <aside className="insights">
      <div className="cabecalho-ins">
        <span className="rotulo">{projeto}</span>
        <h3>O que funciona neste setor</h3>
        <p className="sub">Medido na base: mediana do {d?.alvo ?? 'alvo'} em relação ao canal, por grupo.</p>
      </div>
      {!d && <div className="carregando" />}
      {d && (
        <>
          <div className="bloco-ins">
            <span className="rotulo">Setores</span>
            {d.setores.map((s) => (
              <div key={s.setor} className="linha-ins"><span>{s.setor}</span><span className="sub">{s.canais} canais · {compacto(s.shorts)} shorts · mediana {compacto(s.mediana)}</span></div>
            ))}
          </div>
          <div className="bloco-ins">
            <span className="rotulo">Ganchos e formatos que mais rendem</span>
            {d.fatores.length ? d.fatores.map((f) => (
              <div key={f.fator} className="linha-ins"><span className="mono">{f.fator}</span><b className={f.efeito >= 0 ? 'bom-t' : 'ruim-t'}>{sinal(f.efeito)}</b></div>
            )) : <span className="sub">calcule os atributos para ver</span>}
          </div>
          <div className="grade-ins">
            <div className="bloco-ins">
              <span className="rotulo">Melhores horários</span>
              {d.horarios.map((h) => <div key={h.grupo} className="linha-ins"><span>{h.grupo}</span><b className="bom-t">{sinal(h.efeito)}</b></div>)}
            </div>
            <div className="bloco-ins">
              <span className="rotulo">Duração</span>
              {d.duracao.map((h) => <div key={h.grupo} className="linha-ins"><span>{h.grupo}</span><b className={h.efeito >= 0 ? 'bom-t' : 'ruim-t'}>{sinal(h.efeito)}</b></div>)}
            </div>
          </div>
          <div className="bloco-ins">
            <span className="rotulo">Modelo</span>
            {ativo ? (
              <>
                <div className="linha-ins"><span>erro vs baseline</span><b className="bom-t">−{pct(ativo.resultado.ganho, false)}</b></div>
                <div className="linha-ins"><span>acerto A vs B</span><b>{pct(ativo.resultado.modelo.acerto_pares, false)}</b></div>
                <div className="linha-ins"><span>receita</span><span className="sub">{ativo.receita.camadas.join(' + ')}</span></div>
              </>
            ) : <span className="sub">sem modelo ativo: peça ao agente otimizar</span>}
          </div>
        </>
      )}
    </aside>
  )
}

function NovoProjeto({ fechar, criado }: { fechar: () => void; criado: (nome: string) => void }) {
  const [nome, setNome] = useState('')
  const [setores, setSetores] = useState('')
  const [canais, setCanais] = useState('')
  const [alvo, setAlvo] = useState<'likes' | 'views'>('likes')
  const [modo, setModo] = useState<'automatico' | 'cientista'>('automatico')
  const [erro, setErro] = useState<string | null>(null)
  const lista = (t: string) => t.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)
  const enviar = () => {
    const setor = lista(setores)[0] ?? ''
    api.criarProjeto({ nome, setores: lista(setores), alvo, modo, canais_semente: lista(canais).map((ref) => ({ ref, setor })) })
      .then(() => criado(nome)).catch((e: Error) => setErro(e.message))
  }
  return (
    <div className="modal-fundo" onClick={fechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Novo projeto">
        <h3>Novo projeto</h3>
        <input className="campo" placeholder="nome (ex.: fitness-br)" value={nome} onChange={(e) => setNome(e.target.value.toLowerCase())} />
        <input className="campo" placeholder="setores (ex.: fitness, nutrição)" value={setores} onChange={(e) => setSetores(e.target.value)} />
        <textarea className="campo" rows={3} placeholder="canais-semente: @handle ou UC…, um por linha" value={canais} onChange={(e) => setCanais(e.target.value)} />
        <div className="linha">
          <div className="segmentado">
            {(['likes', 'views'] as const).map((a) => <button key={a} className={alvo === a ? 'ativo' : ''} onClick={() => setAlvo(a)}>{a}</button>)}
          </div>
          <span style={{ flex: 1 }} />
          <div className="segmentado">
            {(['automatico', 'cientista'] as const).map((m) => (
              <button key={m} className={modo === m ? 'ativo' : ''} onClick={() => setModo(m)}>{m === 'automatico' ? 'Automático' : 'Data Scientist'}</button>
            ))}
          </div>
        </div>
        {erro && <p className="ruim-t sub">{erro}</p>}
        <p className="sub" style={{ margin: 0 }}>Depois de criar, peça ao agente (MCP): coletar → calcular_texto → otimizar.</p>
        <div className="linha" style={{ justifyContent: 'flex-end' }}>
          <button className="btn texto" onClick={fechar}>Cancelar</button>
          <button className="btn preenchido" disabled={!nome || !setores || !canais} onClick={enviar}>Criar</button>
        </div>
      </div>
    </div>
  )
}
