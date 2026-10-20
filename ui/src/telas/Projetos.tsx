import { useEffect, useState } from 'react'
import { api, type Experimento } from '../api'
import { Icone, pct } from '../componentes'

// Tela inicial: carrossel de projetos com o "+" no meio e, ao lado, o alcance melhorado
// estimado (quanto o modelo ativo de cada projeto reduz o erro sobre o baseline).

type Cartao = { nome: string; ativo?: Experimento; total: number }

export default function Projetos({ projetos, abrir, aoCriar }: {
  projetos: string[]; abrir: (nome: string) => void; aoCriar: () => void
}) {
  const [cartoes, setCartoes] = useState<Cartao[]>([])
  const [criando, setCriando] = useState(false)
  useEffect(() => {
    Promise.all(
      projetos.map(async (nome) => {
        const exps = await api.experimentos(nome).catch(() => [] as Experimento[])
        return { nome, ativo: exps.find((e) => e.status === 'ativo'), total: exps.length }
      }),
    ).then(setCartoes)
  }, [projetos])

  const meio = Math.ceil(cartoes.length / 2)
  const ganhos = cartoes.filter((c) => c.ativo).map((c) => c.ativo!.resultado.ganho)
  const medio = ganhos.length ? ganhos.reduce((a, b) => a + b, 0) / ganhos.length : null
  const Novo = () => (
    <button className="cartao-projeto novo" onClick={() => setCriando(true)} aria-label="Novo projeto">
      <Icone nome="add" />
      <span style={{ fontSize: 13, fontWeight: 500, marginTop: 8 }}>Novo projeto</span>
    </button>
  )

  return (
    <div className="pilha">
      <div className="saudacao">
        <h2>Olá</h2>
        <p>Qual projeto vamos melhorar hoje?</p>
      </div>
      <div className="projetos-grade">
        <div className="carrossel">
          {cartoes.slice(0, meio).map((c) => <CartaoProjeto key={c.nome} c={c} abrir={() => abrir(c.nome)} />)}
          <Novo />
          {cartoes.slice(meio).map((c) => <CartaoProjeto key={c.nome} c={c} abrir={() => abrir(c.nome)} />)}
        </div>
        <aside className="alcance">
          <span className="rotulo">Alcance melhorado estimado</span>
          <span className="enorme">{medio === null ? '—' : pct(medio, false)}</span>
          <p className="sub" style={{ margin: 0 }}>
            Quanto o modelo ativo reduz o erro de previsão em relação a só usar a média do canal, na
            média dos projetos. Menos erro, decisões de publicação mais acertadas.
          </p>
          <ul>
            {cartoes.map((c) => (
              <li key={c.nome}>
                <span className="sub" style={{ color: 'var(--texto-2)' }}>{c.nome}</span>
                <b className={c.ativo ? 'bom-t' : 'sub'}>{c.ativo ? pct(c.ativo.resultado.ganho, false) : 'sem modelo'}</b>
              </li>
            ))}
          </ul>
        </aside>
      </div>
      {criando && <NovoProjeto fechar={() => setCriando(false)} criado={(nome) => { setCriando(false); aoCriar(); abrir(nome) }} />}
    </div>
  )
}

function CartaoProjeto({ c, abrir }: { c: Cartao; abrir: () => void }) {
  const ganho = c.ativo?.resultado.ganho
  return (
    <button className="cartao-projeto" onClick={abrir}>
      <span className="icone-proj"><Icone nome="smart_display" cheio /></span>
      <span className="nome-proj">{c.nome}</span>
      <span className="sub">{c.total} experimento{c.total === 1 ? '' : 's'}</span>
      <span className="grande">{ganho === undefined ? '—' : `−${pct(ganho, false)}`}</span>
      <span className="sub">{ganho === undefined ? 'sem modelo ativo' : 'de erro vs baseline'}</span>
    </button>
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
