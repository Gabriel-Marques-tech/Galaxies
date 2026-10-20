import { useState } from 'react'
import { api, type Experimento, type Projeto } from '../api'
import { Aviso, Icone, num, pct, useCarga } from '../componentes'

// Métricas: o painel grande do wireframe. Como está o modelo ativo e como o agente chegou nele.

export default function Metricas({ projeto, config }: { projeto: string; config: Projeto }) {
  const [alvo, setAlvo] = useState(config.alvo)
  const exps = useCarga(() => api.experimentos(projeto, alvo), [projeto, alvo])
  const erros = useCarga(() => api.erros(projeto), [projeto])
  if (exps.erro) return <Aviso texto={exps.erro} />
  if (!exps.dados) return <div className="carregando" />
  const lista = exps.dados
  const ativo = lista.find((e) => e.status === 'ativo')
  const r = ativo?.resultado

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <h2 className="text-[22px] font-medium tracking-tight mr-auto">Como está o modelo</h2>
        <div className="flex rounded-pilula bg-superficie-2 p-0.5">
          {(['likes', 'views'] as const).map((a) => (
            <button key={a} className={`h-8 px-4 rounded-pilula text-[13px] ${alvo === a ? 'bg-superficie font-medium shadow' : 'text-texto-2'}`} onClick={() => setAlvo(a)}>{a}</button>
          ))}
        </div>
      </div>

      {!ativo && <Aviso texto={`Nenhum modelo ativo para ${alvo}. Peça ao agente: otimizar.`} />}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Cartao icone="trending_down" rotulo="Erro vs baseline" valor={r ? pct(-r.ganho) : '—'}
          detalhe={r ? `MAE ${num(r.modelo.mae)} vs ${num(r.baseline.mae)} · erro típico ${Math.exp(r.modelo.mae).toFixed(2)}× vs ${Math.exp(r.baseline.mae).toFixed(2)}×` : 'sem modelo ativo'} destaque />
        <Cartao icone="swap_vert" rotulo="Acerto A vs B" valor={r ? pct(r.modelo.acerto_pares, false) : '—'} detalhe="pares de vídeos do mesmo canal · acaso = 50%" />
        <Cartao icone="unfold_more" rotulo="Faixa de 80% cobre" valor={r?.cobertura_80 ? pct(r.cobertura_80, false) : '—'} detalhe={r ? `sem calibração: ${pct(r.cobertura_bruta, false)} · alargada ${r.calibracao.toFixed(2)}×` : ''} />
        <Cartao icone="science" rotulo="Experimentos" valor={String(lista.length)} detalhe={ativo ? `ativo: ${ativo.receita.camadas.join(' + ')}` : ''} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
        <section className="rounded-l bg-superficie-2 p-5">
          <h3 className="font-medium">Evolução dos experimentos</h3>
          <p className="text-[12.5px] text-texto-3 mb-3">Erro a menos que o baseline, por experimento, na ordem em que o agente rodou. O ativo está marcado.</p>
          <Evolucao exps={lista} />
        </section>
        <section className="rounded-l bg-superficie-2 p-5 flex flex-col gap-4">
          <div>
            <h3 className="font-medium">Onde o modelo mais erra</h3>
            <p className="text-[12.5px] text-texto-3">MAE por segmento, do pior para o melhor.</p>
          </div>
          {erros.dados ? Object.entries(erros.dados.segmentos).map(([nome, segs]) => (
            <div key={nome}>
              <span className="text-[11px] uppercase tracking-wider text-texto-3">{nome}</span>
              {segs.slice(0, 4).map((s) => (
                <div key={s.chave} className="flex items-center gap-3 py-1 text-[13px]">
                  <span className="truncate flex-1 text-texto-2">{s.chave}</span>
                  <span className="w-24 h-1.5 rounded bg-superficie-4 overflow-hidden"><span className="block h-full bg-acento" style={{ width: `${Math.min(s.mae / 2, 1) * 100}%` }} /></span>
                  <span className="w-12 text-right tabular-nums">{num(s.mae, 2)}</span>
                </div>
              ))}
            </div>
          )) : <div className="carregando" />}
        </section>
      </div>

      {ativo && (
        <section className="rounded-l bg-superficie-2 p-5">
          <h3 className="font-medium">Como o agente chegou nele</h3>
          <p className="text-[13.5px] text-texto-2 mt-1 whitespace-pre-wrap">{ativo.hipotese || 'Sem hipótese registrada.'}</p>
          {ativo.resultado.sugestoes.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1.5">
              {ativo.resultado.sugestoes.map((s) => <li key={s} className="flex gap-2 text-[13px]"><Icone nome="arrow_forward" className="text-acento text-[16px] mt-0.5" />{s}</li>)}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}

function Cartao({ icone, rotulo, valor, detalhe, destaque }: { icone: string; rotulo: string; valor: string; detalhe: string; destaque?: boolean }) {
  return (
    <div className="rounded-l bg-superficie-2 p-5 flex flex-col gap-1 min-h-[120px]">
      <span className="flex items-center gap-1.5 text-[12.5px] text-texto-3"><Icone nome={icone} className="text-[18px]" />{rotulo}</span>
      <span className={`text-[32px] leading-tight tracking-tight tabular-nums ${destaque ? 'texto-gradiente w-fit font-medium' : ''}`}>{valor}</span>
      <span className="text-[12px] text-texto-3">{detalhe}</span>
    </div>
  )
}

// Barras finas por experimento (ordem cronológica); o ativo em acento, os outros neutros.
function Evolucao({ exps }: { exps: Experimento[] }) {
  if (!exps.length) return <p className="text-texto-3 text-[13px]">Nenhum experimento ainda.</p>
  const maior = Math.max(...exps.map((e) => Math.abs(e.resultado.ganho)), 0.01)
  return (
    <div className="flex items-end gap-1.5 h-40 overflow-x-auto sem-rolagem pt-6">
      {exps.map((e) => {
        const g = e.resultado.ganho
        const ativo = e.status === 'ativo'
        return (
          <div key={e.id} className="group relative flex-1 min-w-[18px] h-full flex flex-col justify-end" title={`${e.id} · ${e.receita.camadas.join(' + ')} · ${pct(g)}`}>
            <div className={`rounded-t ${ativo ? 'bg-acento' : g > 0 ? 'bg-superficie-4 group-hover:bg-contorno' : 'bg-ruim/40'}`} style={{ height: `${(Math.max(g, 0) / maior) * 100}%` }} />
            {ativo && <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[11px] text-acento font-medium whitespace-nowrap">{pct(g)}</span>}
          </div>
        )
      })}
    </div>
  )
}
