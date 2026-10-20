import { useEffect, useState } from 'react'
import { api, type Atributo, type ItemRevisao } from '../api'
import { Aviso, Dica, Icone, TextoRico, useCarga, Vazio } from '../componentes'

export default function Revisao({ projeto }: { projeto: string }) {
  const atributos = useCarga(() => api.atributos(projeto), [projeto])
  const concordancia = useCarga(() => api.concordancia(projeto), [projeto])
  const [atributo, setAtributo] = useState('')
  const [itens, setItens] = useState<ItemRevisao[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const definicao = atributos.dados?.find((a) => a.id === atributo)
  const porAtributo = new Map((concordancia.dados ?? []).map((c) => [c.atributo_id, c]))

  useEffect(() => {
    if (!atributo && atributos.dados?.length) setAtributo(atributos.dados[0].id)
  }, [atributos.dados, atributo])
  useEffect(() => {
    if (!atributo) return
    setItens(null)
    api.amostra(projeto, atributo).then(setItens).catch((e: Error) => setErro(e.message))
  }, [projeto, atributo])

  const responder = (item: ItemRevisao, valor: unknown) =>
    api.revisar(projeto, item.atributo_id, item.video_id, valor)
      .then(() => { setItens((xs) => xs?.filter((x) => x.video_id !== item.video_id) ?? null); concordancia.recarregar() })
      .catch((e: Error) => setErro(e.message))

  return (
    <div className="pilha">
      <Dica>
        Confira se o extrator acerta o que vê no gancho. Abaixo de 70% de concordância o atributo fica marcado como
        não confiável, e o agente vê isso antes de usá-lo no modelo.
      </Dica>
      <div className="duas-colunas">
        <div className="lista-lateral">
          {atributos.dados?.map((a) => {
            const c = porAtributo.get(a.id)
            return (
              <button key={a.id} className={a.id === atributo ? 'ativo' : ''} onClick={() => setAtributo(a.id)}>
                <span className="mono" style={{ fontSize: 13 }}>{a.id}</span>
                <span className={`sub ${c ? (c.confiavel ? 'bom-t' : 'ruim-t') : ''}`}>
                  {c ? `${Math.round(c.concordancia * 100)}% de acordo · ${c.revisados} revisados` : 'sem revisões'}
                </span>
              </button>
            )
          })}
        </div>
        <div className="pilha" style={{ gap: 12 }}>
          {erro && <Aviso texto={erro} />}
          {definicao && (
            <div>
              <h3 style={{ margin: 0, fontWeight: 500 }}>{definicao.instrucoes}</h3>
              <span className="sub">{definicao.tipo === 'noul' ? 'sim ou não' : definicao.tipo === 'choice' ? 'escolha uma opção' : 'escala'}</span>
            </div>
          )}
          {!itens && <div className="carregando" />}
          {definicao && itens?.map((item) => <Cartao key={item.video_id} item={item} atributo={definicao} responder={responder} />)}
          {itens && !itens.length && <Vazio icone="task_alt">Nada para revisar neste atributo.</Vazio>}
        </div>
      </div>
    </div>
  )
}

function Cartao({ item, atributo, responder }: { item: ItemRevisao; atributo: Atributo; responder: (i: ItemRevisao, v: unknown) => void }) {
  const opcoes: [string, unknown][] =
    atributo.tipo === 'noul' ? [['Sim', true], ['Não', false]]
      : atributo.tipo === 'choice' ? Object.keys(atributo.criterios ?? {}).map((r) => [r, r])
        : (atributo.criterios as string[]).map((nivel, i) => [nivel, i])
  const maquina = typeof item.resposta_extrator === 'number'
    ? atributo.tipo === 'noul' ? `${Math.round(item.resposta_extrator * 100)}% sim` : item.resposta_extrator.toFixed(2)
    : item.resposta_extrator
  return (
    <div className="cartao-revisao">
      <a href={`https://youtube.com/shorts/${item.video_id}`} target="_blank" rel="noreferrer" style={{ fontWeight: 500 }}>
        {item.titulo || '(sem título)'} <Icone nome="open_in_new" className="sub" />
      </a>
      <div className="campo-texto"><span>Gancho</span><span><TextoRico texto={item.gancho} /></span></div>
      <div className="campo-texto"><span>Fala</span><span>{item.fala || '(sem fala)'}</span></div>
      <div className="linha">
        <span className="chip"><Icone nome="smart_toy" />{item.extrator.replace('@cf/meta/', '')}: {maquina}</span>
        <span style={{ flex: 1 }} />
        {opcoes.map(([rotulo, valor]) => (
          <button key={rotulo} className="btn contorno pequeno" onClick={() => responder(item, valor)}>{rotulo}</button>
        ))}
      </div>
    </div>
  )
}
