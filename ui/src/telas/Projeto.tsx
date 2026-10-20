import { useState } from 'react'
import type { Projeto as Config } from '../api'
import { Icone } from '../componentes'
import Analisar from './Analisar'
import Erros from './Erros'
import Metricas from './Metricas'
import Modelos from './Modelos'
import Revisao from './Revisao'
import Terminal from './Terminal'
import Trace from './Trace'

export type Aba = 'analise' | 'metricas' | 'analyst'
type SubAba = 'modelos' | 'revisao' | 'erros' | 'trace' | 'harness'

const ABAS: { id: Aba; nome: string; icone: string }[] = [
  { id: 'analise', nome: 'Análise', icone: 'auto_awesome' },
  { id: 'metricas', nome: 'Métricas', icone: 'monitoring' },
  { id: 'analyst', nome: 'Data Analyst', icone: 'science' },
]
const SUB: { id: SubAba; nome: string }[] = [
  { id: 'modelos', nome: 'Experimentos' },
  { id: 'revisao', nome: 'Revisão de atributos' },
  { id: 'erros', nome: 'Erros' },
  { id: 'trace', nome: 'Trace' },
  { id: 'harness', nome: 'Harness' },
]

export default function ProjetoTela({ projeto, config, aba, ir, aoMudarConfig }: {
  projeto: string; config: Config; aba: Aba; ir: (aba: Aba) => void; aoMudarConfig: () => void
}) {
  const [sub, setSub] = useState<SubAba>('modelos')
  return (
    <div className="max-w-[1180px] mx-auto flex flex-col gap-5 pt-2">
      {/* abas no topo à direita, como no wireframe */}
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-texto-3 text-[13px] mr-auto">{config.setores.join(' · ')}</p>
        <div className="flex rounded-pilula bg-superficie-2 p-0.5">
          {ABAS.map((a) => (
            <button
              key={a.id}
              className={`inline-flex items-center gap-1.5 h-9 px-4 rounded-pilula text-[13.5px] transition-colors ${aba === a.id ? 'bg-superficie text-texto font-medium shadow' : 'text-texto-2 hover:text-texto'}`}
              onClick={() => ir(a.id)}
            >
              <Icone nome={a.icone} className="text-[18px]" />
              {a.nome}
            </button>
          ))}
        </div>
      </div>

      {aba === 'analise' && <Analisar projeto={projeto} config={config} />}
      {aba === 'metricas' && <Metricas projeto={projeto} config={config} />}
      {aba === 'analyst' && (
        <div className="flex flex-col gap-4">
          <div className="flex gap-1 flex-wrap border-b border-contorno-suave">
            {SUB.map((s) => (
              <button
                key={s.id}
                className={`h-10 px-3 -mb-px border-b-2 text-[13.5px] ${sub === s.id ? 'border-acento text-texto font-medium' : 'border-transparent text-texto-3 hover:text-texto'}`}
                onClick={() => setSub(s.id)}
              >
                {s.nome}
              </button>
            ))}
          </div>
          {sub === 'modelos' && <Modelos projeto={projeto} config={config} aoMudar={aoMudarConfig} />}
          {sub === 'revisao' && <Revisao projeto={projeto} />}
          {sub === 'erros' && <Erros projeto={projeto} />}
          {sub === 'trace' && <Trace projeto={projeto} />}
          {sub === 'harness' && <Terminal projeto={projeto} />}
        </div>
      )}
    </div>
  )
}
