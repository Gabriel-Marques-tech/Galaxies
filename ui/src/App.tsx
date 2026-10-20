import { useEffect, useState } from 'react'
import { api, type Projeto } from './api'
import { Aviso, Icone, useCarga } from './componentes'
import Inicio from './telas/Inicio'
import ProjetoTela, { type Aba } from './telas/Projeto'

type Tema = 'dark' | 'light'

function lerTema(): Tema {
  try { return (localStorage.getItem('tema') as Tema) ?? 'dark' } catch { return 'dark' }
}

// Rota por hash: #/ (projetos) ou #/<projeto>/<aba>
function lerRota(): { projeto: string; aba: Aba } {
  const [, projeto = '', aba = 'analise'] = location.hash.replace(/^#\/?/, '/').split('/')
  return { projeto: decodeURIComponent(projeto), aba: aba as Aba }
}

export default function App() {
  const projetos = useCarga(api.projetos, [])
  const [rota, setRota] = useState(lerRota)
  const [tema, setTema] = useState<Tema>(lerTema)
  const [menu, setMenu] = useState(false)
  const config = useCarga(
    () => (rota.projeto ? api.projeto(rota.projeto) : Promise.resolve(null)),
    [rota.projeto],
  )
  const modo = config.dados?.modo ?? 'automatico'

  useEffect(() => {
    const aoMudar = () => setRota(lerRota())
    window.addEventListener('hashchange', aoMudar)
    return () => window.removeEventListener('hashchange', aoMudar)
  }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = tema
    try { localStorage.setItem('tema', tema) } catch { /* sem storage: só não lembra */ }
  }, [tema])
  useEffect(() => { document.documentElement.dataset.modo = modo }, [modo])

  const ir = (projeto: string, aba: Aba = 'analise') => {
    location.hash = projeto ? `#/${encodeURIComponent(projeto)}/${aba}` : '#/'
    setMenu(false)
  }
  const mudarModo = (novo: Projeto['modo']) =>
    api.definirModo(rota.projeto, novo).then(() => config.recarregar())

  return (
    <div className="h-full flex bg-fundo">
      {/* ---------------------------------------------------------------- sidebar */}
      <aside
        className={`shrink-0 w-[260px] h-full flex flex-col gap-1 p-3 bg-superficie max-md:fixed max-md:z-30 max-md:shadow-2xl transition-transform ${menu ? '' : 'max-md:-translate-x-full'}`}
      >
        <button className="flex items-center gap-2.5 h-12 px-2 rounded-s hover:bg-superficie-3 text-left" onClick={() => ir('')}>
          <img src="/logo.svg" alt="" className="h-8 w-auto" />
          <span className="text-[19px] font-semibold tracking-tight">Galaxies</span>
        </button>

        <button
          className="mt-2 mb-3 flex items-center gap-2 h-11 px-4 rounded-pilula bg-superficie-2 hover:bg-superficie-3 font-medium"
          onClick={() => ir('')}
        >
          <Icone nome="add" /> Novo projeto
        </button>

        <span className="px-3 text-[11px] uppercase tracking-wider text-texto-3">Projetos</span>
        <nav className="flex flex-col gap-0.5 overflow-y-auto rolagem-fina">
          {projetos.dados?.map((p) => (
            <button
              key={p}
              className={`flex items-center gap-3 h-10 px-3 rounded-pilula text-left truncate ${p === rota.projeto ? 'bg-acento-container text-texto font-medium' : 'text-texto-2 hover:bg-superficie-3'}`}
              onClick={() => ir(p)}
            >
              <Icone nome="smart_display" cheio={p === rota.projeto} className="text-[18px]" />
              <span className="truncate">{p}</span>
            </button>
          ))}
          {projetos.dados && !projetos.dados.length && <span className="px-3 py-2 text-texto-3 text-[13px]">Nenhum ainda.</span>}
        </nav>

        <div className="mt-auto flex flex-col gap-0.5 pt-3 border-t border-contorno-suave">
          {rota.projeto && config.dados && (
            <div className="px-3 pb-2">
              <span className="text-[11px] uppercase tracking-wider text-texto-3">Modo</span>
              <div className="mt-1.5 flex rounded-pilula bg-superficie-2 p-0.5">
                {(['automatico', 'cientista'] as const).map((m) => (
                  <button
                    key={m}
                    className={`flex-1 h-8 rounded-pilula text-[12.5px] font-medium transition-colors ${modo === m ? 'bg-acento text-sobre-acento' : 'text-texto-2 hover:bg-superficie-3'}`}
                    onClick={() => mudarModo(m)}
                  >
                    {m === 'automatico' ? 'Automático' : 'Data Analyst'}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button className="flex items-center gap-3 h-10 px-3 rounded-pilula text-texto-2 hover:bg-superficie-3" onClick={() => setTema(tema === 'dark' ? 'light' : 'dark')}>
            <Icone nome={tema === 'dark' ? 'light_mode' : 'dark_mode'} />
            Tema {tema === 'dark' ? 'claro' : 'escuro'}
          </button>
        </div>
      </aside>
      {menu && <div className="md:hidden fixed inset-0 z-20 bg-black/40" onClick={() => setMenu(false)} />}

      {/* ---------------------------------------------------------------- página */}
      <div className="flex-1 min-w-0 h-full p-2 md:p-3">
        <main className="moldura h-full rounded-l bg-fundo overflow-hidden flex flex-col">
          <header className="flex items-center gap-3 h-14 px-4 md:px-6 shrink-0">
            <button className="md:hidden w-10 h-10 grid place-items-center rounded-full hover:bg-superficie-3" onClick={() => setMenu(true)} aria-label="Menu">
              <Icone nome="menu" />
            </button>
            <h1 className="text-[17px] font-medium truncate">{rota.projeto || 'Projetos'}</h1>
            <span className="ml-auto" />
            {config.dados && (
              <span className="inline-flex items-center gap-1.5 h-8 px-3 rounded-pilula border border-contorno text-[12.5px] text-texto-2">
                <span className="w-2 h-2 rounded-full bg-acento" />
                {modo === 'cientista' ? 'Data Analyst' : 'Automático'} · {config.dados.alvo}
              </span>
            )}
          </header>
          <div className="flex-1 overflow-y-auto rolagem-fina px-4 md:px-8 pb-10">
            {projetos.erro && <Aviso texto={`API indisponível (${projetos.erro}). Rode: uv run --extra multimodal galaxies-api`} />}
            {projetos.dados && !rota.projeto && (
              <Inicio projetos={projetos.dados} ir={ir} aoCriar={projetos.recarregar} />
            )}
            {rota.projeto && config.dados && (
              <ProjetoTela projeto={rota.projeto} config={config.dados} aba={rota.aba} ir={(aba) => ir(rota.projeto, aba)} aoMudarConfig={config.recarregar} />
            )}
            {rota.projeto && config.erro && <Aviso texto={config.erro} />}
          </div>
        </main>
      </div>
    </div>
  )
}
