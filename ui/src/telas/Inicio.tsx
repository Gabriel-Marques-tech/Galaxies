import { useEffect, useState } from 'react'
import { api, type Experimento } from '../api'
import { Icone, pct } from '../componentes'

// Início: carrossel de projetos com o "+" no centro e, à direita, o alcance melhorado
// estimado (quanto o modelo ativo de cada projeto reduz o erro sobre o baseline).

type Cartao = { nome: string; ativo?: Experimento; total: number }

export default function Inicio({ projetos, ir, aoCriar }: {
  projetos: string[]; ir: (projeto: string) => void; aoCriar: () => void
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

  const meio = Math.floor(cartoes.length / 2)
  const esquerda = cartoes.slice(0, meio), direita = cartoes.slice(meio)
  const ganhos = cartoes.filter((c) => c.ativo).map((c) => c.ativo!.resultado.ganho)
  const medio = ganhos.length ? ganhos.reduce((a, b) => a + b, 0) / ganhos.length : null

  return (
    <div className="max-w-[1180px] mx-auto">
      <div className="pt-8 md:pt-14 pb-6">
        <h2 className="text-[34px] md:text-[40px] font-medium tracking-tight texto-gradiente w-fit">Olá</h2>
        <p className="text-[18px] md:text-[20px] text-texto-3 mt-1">Qual projeto vamos melhorar hoje?</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        {/* carrossel */}
        <div className="flex items-center gap-4 overflow-x-auto sem-rolagem py-6 px-1 min-h-[300px]">
          {esquerda.map((c) => <CartaoProjeto key={c.nome} c={c} abrir={() => ir(c.nome)} />)}
          <button
            className="shrink-0 w-[200px] h-[250px] rounded-l border-2 border-dashed border-contorno hover:border-acento hover:bg-acento-container/30 transition-colors grid place-items-center text-texto-3 hover:text-acento"
            onClick={() => setCriando(true)}
            aria-label="Novo projeto"
          >
            <div className="flex flex-col items-center gap-2">
              <Icone nome="add" className="text-[44px]" />
              <span className="text-[13px] font-medium">Novo projeto</span>
            </div>
          </button>
          {direita.map((c) => <CartaoProjeto key={c.nome} c={c} abrir={() => ir(c.nome)} />)}
        </div>

        {/* alcance melhorado estimado */}
        <aside className="rounded-l bg-superficie-2 p-6 flex flex-col gap-3 min-h-[300px]">
          <span className="text-[12px] uppercase tracking-wider text-texto-3">Alcance melhorado estimado</span>
          <span className="text-[44px] leading-none font-medium tracking-tight texto-gradiente w-fit">
            {medio === null ? '—' : pct(medio, false)}
          </span>
          <p className="text-[13px] text-texto-3">
            Quanto o modelo ativo reduz o erro de previsão em relação a só usar a média do canal,
            na média dos projetos. Menos erro = decisões de publicação mais acertadas.
          </p>
          <ul className="mt-auto flex flex-col gap-2 text-[13px]">
            {cartoes.map((c) => (
              <li key={c.nome} className="flex justify-between gap-3">
                <span className="truncate text-texto-2">{c.nome}</span>
                <span className={c.ativo ? 'text-bom font-medium' : 'text-texto-3'}>
                  {c.ativo ? pct(c.ativo.resultado.ganho, false) : 'sem modelo'}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      </div>

      {criando && <NovoProjeto fechar={() => setCriando(false)} criado={(nome) => { setCriando(false); aoCriar(); ir(nome) }} />}
    </div>
  )
}

function CartaoProjeto({ c, abrir }: { c: Cartao; abrir: () => void }) {
  const ganho = c.ativo?.resultado.ganho
  return (
    <button
      className="shrink-0 w-[200px] h-[250px] rounded-l bg-superficie-2 hover:bg-superficie-3 transition-colors p-5 flex flex-col text-left"
      onClick={abrir}
    >
      <span className="w-10 h-10 rounded-s bg-acento-container grid place-items-center text-sobre-acento-container">
        <Icone nome="smart_display" cheio />
      </span>
      <span className="mt-4 text-[16px] font-medium truncate">{c.nome}</span>
      <span className="text-[12.5px] text-texto-3">{c.total} experimento{c.total === 1 ? '' : 's'}</span>
      <span className="mt-auto text-[26px] font-medium tracking-tight">{ganho === undefined ? '—' : pct(ganho, false)}</span>
      <span className="text-[12px] text-texto-3">{ganho === undefined ? 'sem modelo ativo' : 'menos erro que o baseline'}</span>
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
    api.criarProjeto({
      nome, setores: lista(setores), alvo, modo,
      canais_semente: lista(canais).map((ref) => ({ ref, setor })),
    }).then(() => criado(nome)).catch((e: Error) => setErro(e.message))
  }
  const campo = 'w-full h-11 px-4 rounded-s bg-superficie-2 outline-none focus:ring-2 focus:ring-acento'
  return (
    <div className="fixed inset-0 z-40 bg-black/50 grid place-items-center p-4" onClick={fechar}>
      <div className="w-full max-w-[520px] rounded-xl bg-superficie p-6 flex flex-col gap-4" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Novo projeto">
        <h3 className="text-[20px] font-medium">Novo projeto</h3>
        <input className={campo} placeholder="nome (ex.: fitness-br)" value={nome} onChange={(e) => setNome(e.target.value.toLowerCase())} />
        <input className={campo} placeholder="setores (ex.: fitness, nutrição)" value={setores} onChange={(e) => setSetores(e.target.value)} />
        <textarea className={`${campo} h-24 py-3`} placeholder="canais-semente: @handle ou UC…, um por linha" value={canais} onChange={(e) => setCanais(e.target.value)} />
        <div className="flex gap-2 flex-wrap">
          {(['likes', 'views'] as const).map((a) => (
            <button key={a} className={`h-9 px-4 rounded-pilula border ${alvo === a ? 'bg-acento text-sobre-acento border-transparent' : 'border-contorno'}`} onClick={() => setAlvo(a)}>{a}</button>
          ))}
          <span className="flex-1" />
          {(['automatico', 'cientista'] as const).map((m) => (
            <button key={m} className={`h-9 px-4 rounded-pilula border ${modo === m ? 'bg-acento text-sobre-acento border-transparent' : 'border-contorno'}`} onClick={() => setModo(m)}>
              {m === 'automatico' ? 'Automático' : 'Data Analyst'}
            </button>
          ))}
        </div>
        {erro && <p className="text-ruim text-[13px]">{erro}</p>}
        <p className="text-[12.5px] text-texto-3">Depois de criar, peça ao agente (MCP): coletar → calcular_texto → otimizar.</p>
        <div className="flex justify-end gap-2">
          <button className="h-10 px-5 rounded-pilula hover:bg-superficie-3" onClick={fechar}>Cancelar</button>
          <button className="h-10 px-5 rounded-pilula bg-acento text-sobre-acento font-medium disabled:opacity-40" disabled={!nome || !setores || !canais} onClick={enviar}>Criar</button>
        </div>
      </div>
    </div>
  )
}
