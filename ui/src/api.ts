// Tipos espelham os modelos Pydantic do núcleo (galaxies/*.py).

export type Metricas = { mae: number; spearman_no_canal: number; n: number; acerto_pares: number }
export type Erro = { video_id: string; canal_id: string; previsto: number; real: number; erro_log: number }
export type Segmento = { chave: string; mae: number; n: number }

export type Experimento = {
  id: string
  alvo: string
  receita: { camadas: string[]; atributos: string[] | null; extrator: string | null; params: Record<string, number> }
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
export type Canal = { id: string; titulo: string; handle: string | null; setor: string; inscritos: number; videos: number; ganchos: number }
export type Faixa = { q10: number; q50: number; q90: number }
export type Analise = {
  run_id: string; experimento_id: string; canal_id: string; alvo: string; mediana_canal: number
  previsao_7d: Faixa; timeline: (Faixa & { dias: number })[]; limite_viral: number; p_viral: number; dias_viral: number
  fatores: { feature: string; valor: number; impacto: number }[]
  sugestoes: { mudanca: string; previsto_7d: number; ganho: number; p_viral: number; delta_p_viral: number }[]
  chances: { evento: string; multiplo: number; prob: number }[]
  gancho: { descricao: string; transcricao: string } | null
  atributos: Record<string, Record<string, unknown>> | null
}
export type VideoNovo = { titulo: string; descricao?: string; tags?: string[]; duracao_s?: number; publicar_em?: string; fonte?: string }

export type Run = { id: string; operacao: string; inicio: string; status: 'rodando' | 'ok' | 'falhou' }
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
  canais: (pr: string) => pedir<Canal[]>(`${p(pr)}/canais`),
  definirModo: (pr: string, modo: Projeto['modo']) => pedir<Projeto>(`${p(pr)}/modo`, { modo }),
  analisar: (pr: string, video: VideoNovo, canal_id: string) => pedir<Analise>(`${p(pr)}/analisar`, { video, canal_id }),
  avaliacao: (pr: string) => pedir<Record<string, unknown>>(`${p(pr)}/avaliacao`),
  falhas: (pr: string) => pedir<{ video_id: string; etapa: string; erro: string; run_id: string }[]>(`${p(pr)}/falhas`),
  atributos: (pr: string) => pedir<Atributo[]>(`${p(pr)}/atributos`),
  experimentos: (pr: string) => pedir<Experimento[]>(`${p(pr)}/experimentos`),
  promover: (pr: string, id: string) => pedir<Experimento>(`${p(pr)}/experimentos/${id}/promover`, {}),
  decidir: (pr: string, id: string, aprovar: boolean, nota: string) =>
    pedir<Experimento>(`${p(pr)}/experimentos/${id}/decisao`, { aprovar, nota }),
  amostra: (pr: string, atributo: string, n = 10) => pedir<ItemRevisao[]>(`${p(pr)}/revisao/${atributo}?n=${n}`),
  revisar: (pr: string, atributo: string, video: string, valor: unknown) =>
    pedir<{ ok: boolean }>(`${p(pr)}/revisao/${atributo}/${video}`, { valor }),
  concordancia: (pr: string) => pedir<Concordancia[]>(`${p(pr)}/concordancia`),
  erros: (pr: string) => pedir<RelatorioErros>(`${p(pr)}/erros`),
  notas: (pr: string) => pedir<Nota[]>(`${p(pr)}/notas`),
  anotar: (pr: string, video_id: string, tipo: Nota['tipo'], nota: string) =>
    pedir<Nota>(`${p(pr)}/notas`, { video_id, tipo, nota }),
  runs: (pr: string) => pedir<Run[]>(`${p(pr)}/runs`),
  trace: (pr: string, run: string) => pedir<Etapa[]>(`${p(pr)}/runs/${run}/trace`),
}
