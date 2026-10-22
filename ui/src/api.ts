// Tipos espelham os modelos Pydantic do núcleo (galaxies/*.py).

export type Metricas = { mae: number; spearman_no_canal: number; n: number; acerto_pares: number | null }
export type Erro = { video_id: string; canal_id: string; previsto: number; real: number; erro_log: number }
export type Segmento = { chave: string; mae: number; n: number }

export type Receita = { camadas: string[]; atributos: string[] | null; extrator: string | null; params: Record<string, number | null>; ancora?: 'mediana_canal' | 'movel' }
export const receitaTexto = (r: Receita) => r.camadas.join(' + ') + (r.ancora === 'movel' ? ' · âncora móvel' : '')
export type Experimento = {
  id: string
  alvo: string
  receita: Receita
  hipotese: string
  status: 'candidato' | 'aguardando_aprovacao' | 'ativo' | 'aposentado' | 'rejeitado'
  nota_humana: string
  criado_em: string
  resultado: {
    n_treino: number
    n_teste: number
    baseline: Metricas
    controle_metadados: Metricas
    modelo: Metricas
    ganho: number
    melhora_sobre_controle: number
    cobertura_bruta: number
    cobertura_80: number
    calibracao: number
    ganho_por_atributo: Record<string, number>
    piores: Erro[]
    segmentos: Record<string, Segmento[]>
    sugestoes: string[]
  }
}

export type Projeto = { nome: string; alvo: string; modo: 'automatico' | 'cientista'; setores: string[]; detalhes: string }
export type Atributo = { id: string; tipo: 'choice' | 'score' | 'noul'; instrucoes: string; criterios: Record<string, string> | string[] | null }
export type ItemRevisao = {
  video_id: string; atributo_id: string; extrator: string; titulo: string; gancho: string; fala: string
  resposta_extrator: number | string
  outras_respostas: Record<string, number | string>; discordancia: boolean
}
export type Concordancia = { atributo_id: string; revisados: number; concordancia: number; confiavel: boolean }
export type Nota = { video_id: string; tipo: 'dado_ruim' | 'padrao'; nota: string; quando: string }
export type RelatorioErros = {
  falhas_por_etapa: Record<string, number>; piores: Erro[]; segmentos: Record<string, Segmento[]>
  origem: string; notas_padrao: string[]
}
export type Resumo = {
  canais: number; videos: number; ganchos: number; falhas: number; excluidos: number
  atributos_por_extrator: Record<string, number>; experimentos: number; runs: number
  revisoes: number; cota_youtube: number
}
export type Insights = {
  alvo: string
  setores: { setor: string; canais: number; shorts: number; mediana: number }[]
  horarios: { grupo: string; efeito: number; n: number }[]
  dias: { grupo: string; efeito: number; n: number }[]
  duracao: { grupo: string; efeito: number; n: number }[]
  fatores: { fator: string; efeito: number; n: number }[]
  piores_fatores: { fator: string; efeito: number; n: number }[]
}
export type Canal = { id: string; titulo: string; handle: string | null; setor: string; inscritos: number; videos: number; ganchos: number }
export type Faixa = { q10: number; q25: number; q50: number; q75: number; q90: number }
export type Analise = {
  run_id: string; experimento_id: string; canal_id: string; alvo: string; mediana_canal: number
  previsao_7d: Faixa; timeline: (Faixa & { dias: number })[]; limite_viral: number; p_viral: number; dias_viral: number
  fatores: { feature: string; valor: number; impacto: number }[]
  sugestoes: { mudanca: string; previsto_7d: number; ganho: number; p_viral: number; delta_p_viral: number }[]
  chances: { evento: string; multiplo: number; prob: number }[]
  gancho: { descricao: string; transcricao: string } | null
  explicacao: string
  atributos: Record<string, Record<string, unknown>> | null
}
export type VideoNovo = { titulo: string; descricao?: string; tags?: string[]; duracao_s?: number; publicar_em?: string; fonte?: string }

export type Acompanhamento = {
  video_id: string; run_id: string; canal_id: string; alvo: string; publicado_em: string
  observacoes: { quando: string; idade_dias: number; likes: number | null; views: number | null }[]
  ultima: { idade_dias: number; real: number; previsto_q10: number; previsto_q25: number; previsto_q50: number; previsto_q75: number; previsto_q90: number; dentro_da_faixa: boolean; dentro_da_faixa_50: boolean; erro_log: number } | null
}
export type ListaAcompanhamentos = { videos: Acompanhamento[]; n: number; cobertura: number; cobertura_50: number; erro_mediano: number }
export type Tentativa = { origem: string; receita: Receita; objetivo: number | null; ganho: number | null; confianca: number | null; n_validacao: number; erro: string }
export type Busca = { alvo: string; run_id: string; inicio: string; escolhido: string | null; tentativas: Tentativa[] }
export type ProximoPasso = { acao: string; motivo: string; certeza: 'regra' | 'ambiguo'; alternativas: string[]; estado: Record<string, unknown> }
export type Curva = {
  alvo: string; videos: number; intervalo_mediano_dias: number
  faixas: { de_dias: number; ate_dias: number; n: number; inclinacao: number }[]
}

export type Run = { id: string; operacao: string; inicio: string; status: 'rodando' | 'ok' | 'falhou' }
export type Andamento = { run_id: string; operacao: string; inicio: string; etapas: number; decorrido_s: number; ultima: { nome: string; entrada: string } | null }
export type Etapa = { nome: string; duracao_ms: number; entrada: unknown; saida: unknown; erro: string | null }

async function pedir<T>(caminho: string, corpo?: unknown): Promise<T> {
  const resposta = await fetch(`/api${caminho}`, corpo === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  })
  const dados = await resposta.json()
  if (!resposta.ok) throw new Error(dados.erro ?? resposta.statusText)
  return dados as T
}

const p = (projeto: string) => `/projetos/${encodeURIComponent(projeto)}`

export const api = {
  projetos: () => pedir<string[]>('/projetos'),
  projeto: (pr: string) => pedir<Projeto>(p(pr)),
  criarProjeto: (config: Record<string, unknown>) => pedir<Projeto>('/projetos', config),
  resumo: (pr: string) => pedir<Resumo>(`${p(pr)}/resumo`),
  insights: (pr: string) => pedir<Insights>(`${p(pr)}/insights`),
  canais: (pr: string) => pedir<Canal[]>(`${p(pr)}/canais`),
  miniaturas: (pr: string, n = 12) => pedir<string[]>(`${p(pr)}/miniaturas?n=${n}`),
  definirModo: (pr: string, modo: Projeto['modo']) => pedir<Projeto>(`${p(pr)}/modo`, { modo }),
  analisar: (pr: string, video: VideoNovo, canal_id: string) => pedir<Analise>(`${p(pr)}/analisar`, { video, canal_id }),
  upload: async (pr: string, arquivo: File) => {
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    const r = await fetch(`/api${p(pr)}/upload`, { method: 'POST', body: corpo })
    const dados = await r.json()
    if (!r.ok) throw new Error(dados.erro ?? r.statusText)
    return dados as { fonte: string; nome: string }
  },
  acompanhar: (pr: string, run_id: string, video_id: string) => pedir<Acompanhamento>(`${p(pr)}/acompanhar`, { run_id, video_id }),
  atualizarAcompanhamentos: (pr: string) => pedir<{ atualizados: number; sem_dados: string[] }>(`${p(pr)}/acompanhamentos/atualizar`, {}),
  acompanhamentos: (pr: string) => pedir<ListaAcompanhamentos>(`${p(pr)}/acompanhamentos`),
  crescimento: (pr: string) => pedir<Curva>(`${p(pr)}/crescimento`),
  buscas: (pr: string) => pedir<Busca[]>(`${p(pr)}/buscas`),
  proximoPasso: (pr: string) => pedir<ProximoPasso>(`${p(pr)}/proximo-passo`),
  avaliacao: (pr: string) => pedir<Record<string, unknown>>(`${p(pr)}/avaliacao`),
  falhas: (pr: string) => pedir<{ video_id: string; etapa: string; erro: string; run_id: string }[]>(`${p(pr)}/falhas`),
  atributos: (pr: string) => pedir<Atributo[]>(`${p(pr)}/atributos`),
  experimentos: (pr: string, alvo?: string) => pedir<Experimento[]>(`${p(pr)}/experimentos${alvo ? `?alvo=${alvo}` : ''}`),
  promover: (pr: string, id: string) => pedir<Experimento>(`${p(pr)}/experimentos/${id}/promover`, {}),
  decidir: (pr: string, id: string, aprovar: boolean, nota: string) =>
    pedir<Experimento>(`${p(pr)}/experimentos/${id}/decisao`, { aprovar, nota }),
  contagemRevisao: (pr: string, atributo: string) => pedir<{ pendentes: number; discordantes: number }>(`${p(pr)}/revisao/${atributo}/contagem`),
  amostra: (pr: string, atributo: string, n = 10) => pedir<ItemRevisao[]>(`${p(pr)}/revisao/${atributo}?n=${n}`),
  revisar: (pr: string, atributo: string, video: string, valor: unknown) =>
    pedir<{ ok: boolean }>(`${p(pr)}/revisao/${atributo}/${video}`, { valor }),
  concordancia: (pr: string) => pedir<Concordancia[]>(`${p(pr)}/concordancia`),
  erros: (pr: string) => pedir<RelatorioErros>(`${p(pr)}/erros`),
  notas: (pr: string) => pedir<Nota[]>(`${p(pr)}/notas`),
  anotar: (pr: string, video_id: string, tipo: Nota['tipo'], nota: string) =>
    pedir<Nota>(`${p(pr)}/notas`, { video_id, tipo, nota }),
  runs: (pr: string) => pedir<Run[]>(`${p(pr)}/runs`),
  andamento: (pr: string) => pedir<Andamento | null>(`${p(pr)}/andamento`),
  trace: (pr: string, run: string) => pedir<Etapa[]>(`${p(pr)}/runs/${run}/trace`),
}
