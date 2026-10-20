import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Aviso, Icone, useCarga } from './componentes'
import Analisar from './telas/Analisar'
import Erros from './telas/Erros'
import Inicio from './telas/Inicio'
import Modelos from './telas/Modelos'
import Projetos from './telas/Projetos'
import Revisao from './telas/Revisao'
import Terminal from './telas/Terminal'
import Trace from './telas/Trace'

export type Tela = 'projetos' | 'inicio' | 'modelos' | 'analisar' | 'revisao' | 'erros' | 'trace' | 'terminal'

const NAV: { id: Tela; nome: string; icone: string; titulo: string }[] = [
  { id: 'inicio', nome: 'Início', icone: 'home', titulo: 'Visão geral' },
  { id: 'analisar', nome: 'Analisar vídeo', icone: 'auto_awesome', titulo: 'Analisar vídeo' },
  { id: 'modelos', nome: 'Modelos', icone: 'model_training', titulo: 'Modelos e experimentos' },
  { id: 'revisao', nome: 'Revisão de atributos', icone: 'fact_check', titulo: 'Revisão de atributos' },
  { id: 'erros', nome: 'Erros', icone: 'troubleshoot', titulo: 'Erros e triagem' },
  { id: 'trace', nome: 'Trace', icone: 'account_tree', titulo: 'Trace' },
]

const TELAS: Tela[] = ['projetos', 'inicio', 'modelos', 'analisar', 'revisao', 'erros', 'trace', 'terminal']

function lerTema(): 'dark' | 'light' {
  try { return (localStorage.getItem('tema') as 'dark' | 'light') ?? 'dark' } catch { return 'dark' }
}

export default function App() {
  const projetos = useCarga(api.projetos, [])
  const [projeto, setProjeto] = useState('')
  const [tela, setTela] = useState<Tela>(() => (TELAS.includes(location.hash.slice(1) as Tela) ? location.hash.slice(1) as Tela : 'projetos'))
  const [recolhida, setRecolhida] = useState(window.innerWidth < 860)
  const [tema, setTema] = useState(lerTema)
  const [listaAberta, setListaAberta] = useState(false)
  // Onda que atravessa a tela quando o modo muda (sai do botão do topo)
  const [onda, setOnda] = useState<'automatico' | 'cientista' | null>(null)
  const modoAnterior = useRef<string | undefined>(undefined)
  const config = useCarga(() => (projeto ? api.projeto(projeto) : Promise.resolve(null)), [projeto])
  const experimentos = useCarga(() => (projeto ? api.experimentos(projeto) : Promise.resolve([])), [projeto, tela])

  useEffect(() => {
    if (!projeto && projetos.dados?.length) setProjeto(projetos.dados[0])
  }, [projetos.dados, projeto])
  useEffect(() => {
    const modo = config.dados?.modo ?? 'automatico'
    document.documentElement.dataset.modo = modo
    const mudou = modoAnterior.current !== undefined && modoAnterior.current !== modo
    modoAnterior.current = config.dados?.modo
    if (!mudou) return
    setOnda(modo)
    const t = setTimeout(() => setOnda(null), 1300)
    return () => clearTimeout(t)
  }, [config.dados?.modo])
  useEffect(() => {
    document.documentElement.dataset.theme = tema
    try { localStorage.setItem('tema', tema) } catch { /* sem storage: só não lembra */ }
  }, [tema])

  const ir = (t: Tela) => { setTela(t); history.replaceState(null, '', `#${t}`); if (window.innerWidth < 860) setRecolhida(true) }
  const pendentes = experimentos.dados?.filter((e) => e.status === 'aguardando_aprovacao').length ?? 0
  const titulo = tela === 'terminal' ? 'Harness' : tela === 'projetos' ? 'Projetos' : NAV.find((n) => n.id === tela)?.titulo
  const abrirProjeto = (nome: string) => { setProjeto(nome); ir('inicio') }
  const alternarModo = () => config.dados && api.definirModo(projeto, config.dados.modo === 'cientista' ? 'automatico' : 'cientista').then(config.recarregar)

  return (
    <div className="shell">
      <aside className={`sidebar ${recolhida ? 'recolhida' : ''}`}>
        <div className="topo-sidebar">
          <button className="btn-icone" onClick={() => setRecolhida(!recolhida)} aria-label="Alternar menu"><Icone nome="menu" /></button>
          <span className="marca so-aberta"><img src="/logo.svg" alt="" className="logo-img" />Galaxies</span>
        </div>
        <div className={`item-nav projetos-nav ${tela === 'projetos' ? 'ativo' : ''}`}>
          <button className="abrir" onClick={() => (tela === 'projetos' ? setListaAberta(!listaAberta) : ir('projetos'))} title="Projetos">
            <Icone nome="grid_view" cheio={tela === 'projetos'} />
            <span className="rotulo-nav">Projetos{projeto && <small> · {projeto}</small>}</span>
          </button>
          <button className={`seta ${listaAberta ? 'aberta' : ''}`} onClick={() => setListaAberta(!listaAberta)} aria-label="Escolher projeto" aria-expanded={listaAberta}>
            <Icone nome="expand_more" />
          </button>
        </div>
        <div className={`lista-projetos so-aberta ${listaAberta ? 'aberta' : ''}`}>
          <div>
          {projetos.dados?.map((p) => (
            <button key={p} className={`item-nav sub-item ${p === projeto ? 'atual' : ''}`} onClick={() => { setProjeto(p); setListaAberta(false); if (tela === 'projetos') ir('inicio') }}>
              <Icone nome={p === projeto ? 'radio_button_checked' : 'radio_button_unchecked'} className="pequeno" />
              <span className="rotulo-nav">{p}</span>
            </button>
          ))}
          </div>
        </div>
        {NAV.map((n) => (
          <button key={n.id} className={`item-nav ${tela === n.id ? 'ativo' : ''}`} onClick={() => ir(n.id)} title={n.nome}>
            <Icone nome={n.icone} cheio={tela === n.id} />
            <span className="rotulo-nav">{n.nome}</span>
            {n.id === 'modelos' && pendentes > 0 && <span className="contador rotulo-nav">{pendentes}</span>}
          </button>
        ))}
        <div className="separador" />
        <button className={`item-nav ${tela === 'terminal' ? 'ativo' : ''}`} onClick={() => ir('terminal')} title="Harness (terminal)">
          <Icone nome="terminal" />
          <span className="rotulo-nav">Harness</span>
        </button>
        <div className="rodape-sidebar">
          <button className="item-nav" onClick={() => setTema(tema === 'dark' ? 'light' : 'dark')} title="Tema">
            <Icone nome={tema === 'dark' ? 'light_mode' : 'dark_mode'} />
            <span className="rotulo-nav">Tema {tema === 'dark' ? 'claro' : 'escuro'}</span>
          </button>
        </div>
      </aside>

      <div className={`principal ${onda ? 'ressoando' : ''}`}>
        {onda && <div className={`onda ${onda}`} aria-hidden />}
        <div className="barra-topo">
          {recolhida && <button className="btn-icone" onClick={() => setRecolhida(false)} aria-label="Abrir menu"><Icone nome="menu" /></button>}
          <h1>{titulo}</h1>
          {config.dados && tela !== 'projetos' && (
            <button className="chip alternar" onClick={alternarModo}
              title={`Clique para mudar para ${config.dados.modo === 'cientista' ? 'Automático' : 'Data Scientist'}`}>
              <Icone nome={config.dados.modo === 'cientista' ? 'person_search' : 'bolt'} />
              {config.dados.modo === 'cientista' ? 'Data Scientist' : 'Automático'} · {config.dados.alvo}
              <Icone nome="swap_horiz" className="seta" />
            </button>
          )}
        </div>
        <div className="conteudo">
          <div className="largura tela-anim" key={`${tela}-${projeto}`}>
            {projetos.erro && <Aviso texto={`API indisponível (${projetos.erro}). Rode: uv run --extra multimodal galaxies-api`} />}
            {tela === 'projetos' && projetos.dados && (
              <Projetos projetos={projetos.dados} abrir={abrirProjeto} aoCriar={projetos.recarregar} />
            )}
            {tela !== 'projetos' && projeto && config.dados && (
              <>
                {tela === 'inicio' && <Inicio projeto={projeto} config={config.dados} ir={ir} aoMudarModo={config.recarregar} />}
                {tela === 'analisar' && <Analisar projeto={projeto} config={config.dados} />}
                {tela === 'modelos' && <Modelos projeto={projeto} config={config.dados} aoMudar={experimentos.recarregar} />}
                {tela === 'revisao' && <Revisao projeto={projeto} />}
                {tela === 'erros' && <Erros projeto={projeto} />}
                {tela === 'trace' && <Trace projeto={projeto} />}
                {tela === 'terminal' && <Terminal projeto={projeto} />}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
