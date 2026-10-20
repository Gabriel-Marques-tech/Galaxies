import { useEffect, useState } from 'react'
import { api } from './api'
import { Aviso, Icone, useCarga } from './componentes'
import Analisar from './telas/Analisar'
import Erros from './telas/Erros'
import Inicio from './telas/Inicio'
import Modelos from './telas/Modelos'
import Revisao from './telas/Revisao'
import Terminal from './telas/Terminal'
import Trace from './telas/Trace'

export type Tela = 'inicio' | 'modelos' | 'analisar' | 'revisao' | 'erros' | 'trace' | 'terminal'

const NAV: { id: Tela; nome: string; icone: string; titulo: string }[] = [
  { id: 'inicio', nome: 'Início', icone: 'home', titulo: 'Visão geral' },
  { id: 'analisar', nome: 'Analisar vídeo', icone: 'auto_awesome', titulo: 'Analisar vídeo' },
  { id: 'modelos', nome: 'Modelos', icone: 'model_training', titulo: 'Modelos e experimentos' },
  { id: 'revisao', nome: 'Revisão de atributos', icone: 'fact_check', titulo: 'Revisão de atributos' },
  { id: 'erros', nome: 'Erros', icone: 'troubleshoot', titulo: 'Erros e triagem' },
  { id: 'trace', nome: 'Trace', icone: 'account_tree', titulo: 'Trace' },
]

const TELAS: Tela[] = ['inicio', 'modelos', 'analisar', 'revisao', 'erros', 'trace', 'terminal']

function lerTema(): 'dark' | 'light' {
  try { return (localStorage.getItem('tema') as 'dark' | 'light') ?? 'dark' } catch { return 'dark' }
}

export default function App() {
  const projetos = useCarga(api.projetos, [])
  const [projeto, setProjeto] = useState('')
  const [tela, setTela] = useState<Tela>(() => (TELAS.includes(location.hash.slice(1) as Tela) ? location.hash.slice(1) as Tela : 'inicio'))
  const [recolhida, setRecolhida] = useState(window.innerWidth < 860)
  const [tema, setTema] = useState(lerTema)
  const config = useCarga(() => (projeto ? api.projeto(projeto) : Promise.resolve(null)), [projeto])
  const experimentos = useCarga(() => (projeto ? api.experimentos(projeto) : Promise.resolve([])), [projeto, tela])

  useEffect(() => {
    if (!projeto && projetos.dados?.length) setProjeto(projetos.dados[0])
  }, [projetos.dados, projeto])
  useEffect(() => {
    document.documentElement.dataset.theme = tema
    try { localStorage.setItem('tema', tema) } catch { /* sem storage: só não lembra */ }
  }, [tema])

  const ir = (t: Tela) => { setTela(t); history.replaceState(null, '', `#${t}`); if (window.innerWidth < 860) setRecolhida(true) }
  const pendentes = experimentos.dados?.filter((e) => e.status === 'aguardando_aprovacao').length ?? 0
  const titulo = tela === 'terminal' ? 'Harness' : NAV.find((n) => n.id === tela)?.titulo

  return (
    <div className="shell">
      <aside className={`sidebar ${recolhida ? 'recolhida' : ''}`}>
        <div className="topo-sidebar">
          <button className="btn-icone" onClick={() => setRecolhida(!recolhida)} aria-label="Alternar menu"><Icone nome="menu" /></button>
          <span className="marca so-aberta"><span className="logo"><Icone nome="blur_on" /></span>Galaxies</span>
        </div>
        <select className="campo projeto-select so-aberta" value={projeto} onChange={(e) => setProjeto(e.target.value)} aria-label="Projeto">
          {projetos.dados?.map((p) => <option key={p}>{p}</option>)}
        </select>
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

      <div className="principal">
        <div className="barra-topo">
          {recolhida && <button className="btn-icone" onClick={() => setRecolhida(false)} aria-label="Abrir menu"><Icone nome="menu" /></button>}
          <h1>{titulo}</h1>
          {config.dados && (
            <span className="chip"><Icone nome={config.dados.modo === 'cientista' ? 'person_search' : 'bolt'} />
              {config.dados.modo === 'cientista' ? 'Data Scientist' : 'Automático'} · {config.dados.alvo}
            </span>
          )}
        </div>
        <div className="conteudo">
          <div className="largura">
            {projetos.erro && <Aviso texto={`API indisponível (${projetos.erro}). Rode: uv run --extra multimodal galaxies-api`} />}
            {projetos.dados && !projetos.dados.length && <Aviso texto="Nenhum projeto ainda. Peça ao agente: criar_projeto." />}
            {projeto && config.dados && (
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
