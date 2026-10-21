import type { Tela } from '../App'
import { api, type Projeto, receitaTexto } from '../api'
import { compacto, Icone, Metrica, pct, useCarga } from '../componentes'

const ATALHOS: { tela: Tela; icone: string; titulo: string; texto: string }[] = [
  { tela: 'analisar', icone: 'auto_awesome', titulo: 'Analisar um vídeo', texto: 'Previsão em 7 dias, timeline, chance de viralizar e o que mudar.' },
  { tela: 'modelos', icone: 'model_training', titulo: 'Ver os modelos', texto: 'Experimentos do agente contra a média do canal.' },
  { tela: 'revisao', icone: 'fact_check', titulo: 'Revisar atributos', texto: 'Confira se o extrator acerta o que vê no gancho.' },
  { tela: 'terminal', icone: 'terminal', titulo: 'Abrir o harness', texto: 'Terminal com comandos para quem trabalha com dados.' },
]

export default function Inicio({ projeto, config, ir, aoMudarModo }: {
  projeto: string; config: Projeto; ir: (t: Tela) => void; aoMudarModo: () => void
}) {
  const resumo = useCarga(() => api.resumo(projeto), [projeto])
  const exps = useCarga(() => api.experimentos(projeto), [projeto])
  const acomp = useCarga(() => api.acompanhamentos(projeto), [projeto])
  const curva = useCarga(() => api.crescimento(projeto), [projeto])
  // idade a partir da qual a mediana dos vídeos parou de crescer
  const estabiliza = curva.dados?.faixas.find((f) => f.inclinacao === 0)?.de_dias
  const ativo = exps.dados?.find((e) => e.status === 'ativo')
  const r = resumo.dados
  const mudarModo = (modo: Projeto['modo']) => api.definirModo(projeto, modo).then(aoMudarModo)

  return (
    <div className="pilha">
      <div className="saudacao">
        <h2>Olá</h2>
        <p>O que vamos construir em <b>{projeto}</b> hoje?</p>
      </div>

      <div className="grade-cartoes">
        <Metrica icone="smart_display" rotulo="Shorts na base" valor={r ? compacto(r.videos) : '—'} detalhe={r && `${r.canais} canais · ${config.setores.join(', ')}`} />
        <Metrica icone="frame_inspect" rotulo="Ganchos analisados" valor={r ? compacto(r.ganchos) : '—'}
          detalhe={r && Object.entries(r.atributos_por_extrator).map(([e, n]) => `${n} com ${e.replace('@cf/meta/', '')}`).join(' · ')} />
        <Metrica icone="model_training" rotulo="Modelo ativo" valor={ativo ? pct(ativo.resultado.ganho) : '—'}
          detalhe={ativo ? `mais preciso que a média do canal · ${receitaTexto(ativo.receita)}` : 'nenhum promovido ainda'} />
        <Metrica icone="science" rotulo="Experimentos" valor={r ? String(r.experimentos) : '—'} detalhe={r && `${r.revisoes} revisões humanas · ${r.runs} execuções`} />
        <Metrica icone="publish" rotulo="Em produção" valor={acomp.dados?.n ? `${Math.round(acomp.dados.cobertura * 100)}%` : '—'}
          detalhe={acomp.dados?.n ? `${acomp.dados.n} vídeo${acomp.dados.n === 1 ? '' : 's'} · dentro da faixa quase certa; ${Math.round(acomp.dados.cobertura_50 * 100)}% na provável · erro típico ${acomp.dados.erro_mediano.toFixed(1)}×` : 'nenhum vídeo acompanhado: publique e use "Acompanhar" na análise'} />
        <Metrica icone="trending_up" rotulo="Curva de crescimento" valor={curva.dados?.videos ? compacto(curva.dados.videos) : '—'}
          detalhe={curva.dados?.videos
            ? `vídeos reobservados · ${curva.dados.alvo} ${estabiliza !== undefined ? `estabilizam a partir de ~${estabiliza} dias` : 'ainda crescendo em todas as faixas'}`
            : 'sem reobservação: peça ao agente observar_recentes uma vez por dia'} />
      </div>

      <div className="cartao">
        <h3>Como você quer trabalhar?</h3>
        <p className="descricao">O agente faz o trabalho de cientista de dados. Você decide quanto quer participar.</p>
        <div className="segmentado" role="radiogroup" aria-label="Modo do projeto">
          <button className={config.modo === 'automatico' ? 'ativo' : ''} onClick={() => mudarModo('automatico')} role="radio" aria-checked={config.modo === 'automatico'}>
            <Icone nome="bolt" /> Automático
          </button>
          <button className={config.modo === 'cientista' ? 'ativo' : ''} onClick={() => mudarModo('cientista')} role="radio" aria-checked={config.modo === 'cientista'}>
            <Icone nome="person_search" /> Data Scientist
          </button>
        </div>
        <p className="sub" style={{ marginTop: 12, marginBottom: 0 }}>
          {config.modo === 'automatico'
            ? 'O agente testa as receitas e promove sozinho o melhor modelo que supera a média do canal.'
            : 'Cada promoção espera sua aprovação. Você revisa atributos e faz a triagem dos erros; suas notas viram pistas para o agente.'}
        </p>
      </div>

      <div className="grade-cartoes">
        {ATALHOS.map((a) => (
          <button key={a.tela} className="cartao contorno" style={{ textAlign: 'left', cursor: 'pointer', color: 'inherit' }} onClick={() => ir(a.tela)}>
            <Icone nome={a.icone} className="destaque-icone" />
            <h3 style={{ marginTop: 12 }}>{a.titulo}</h3>
            <p className="descricao" style={{ margin: 0 }}>{a.texto}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
