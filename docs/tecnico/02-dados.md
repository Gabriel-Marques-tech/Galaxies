# 02 · Dados

## `armazenamento.py` — um DuckDB por projeto

`abrir(raiz, nome)` conecta em `<raiz>/projetos/<nome>/galaxies.duckdb`, cria o esquema se
faltar (o seu, o do `trace` e o do `acompanhamento`) e aplica migrações pequenas
(`_migrar_respostas`: respostas antigas sem coluna `extrator`).

**Um escritor por vez.** DuckDB permite um processo com escrita por arquivo. Jobs longos
(MCP, CLI) seguram o arquivo; por isso a API em desenvolvimento roda sobre um *snapshot*
(cópia) em outra pasta (`GALAXIES_DADOS`), e o progresso do job chega à UI por arquivo
(`andamento.json`, ver trace), não pelo banco.

Tabelas e papel:

| tabela | conteúdo | escrita por |
|---|---|---|
| `projeto` | config do projeto (JSON) | criar_projeto, definir_modo |
| `canais` | id, handle, título, inscritos, setor | coletar, adicionar_canal |
| `videos` | metadados + contagens na coleta (`coletado_em`) | coletar |
| `camada_bruta` | frames (JSON de caminhos), descrição (Gemini), transcrição (Whisper), embedding (SigLIP); descrição vazia = gancho leve | processar_ganchos |
| `atributos` | definições do projeto (vazia = padrão do código) | definir_atributos |
| `respostas` | (video, atributo, extrator, assinatura) → resposta JSON no formato do Jev | calcular_atributos, calcular_titulos, rotular_vizinhos |
| `texto_embedding` | embedding MiniLM de título+descrição | calcular_texto |
| `falhas` | vídeo que falhou numa etapa do pipeline | processar_ganchos, calcular_atributos |
| `excluidos` | vídeos ou canais tirados da base (triagem humana ou `excluir`) | anotar, excluir |
| `experimentos` | id, alvo, status, criado_em, dados (JSON do `Experimento`) | experimentar, promover, decidir |
| `avaliacoes` | diagnóstico por camadas (`treinar`) | treinar |
| `revisoes`, `notas` | portões humanos | revisar, anotar |
| `cota` | unidades da YouTube API por run | todo serviço que chama o YouTube |
| `runs`, `trace` | execuções e etapas | todo serviço |
| `acompanhamentos`, `observacoes` | vídeos acompanhados e observações de contagem ao longo do tempo | acompanhar, observar_recentes, atualizar_acompanhamentos |

Ao lado do banco: `modelos/<experimento_id>/` (boosters `q10.txt`, `q50.txt`, `q90.txt` e
`meta.json`), `analises/<run_id>/` (frames do vídeo analisado) e `andamento.json` (run em
execução).

## `config.py` — o que o agente informa

`ConfigProjeto`: `nome` (minúsculas, hífens), `setores`, `canais_semente` (≥ 1,
`{ref, setor}`), `alvo` (`likes`/`views`), `modo` (`automatico`/`cientista`),
`coletar_desde` (opcional), `limite_viral` (padrão 3× a mediana do canal).

## `coleta.py` — YouTube Data API

`coletar_canal(banco, youtube, ref, setor, desde)`: resolve o canal (`@handle` ou `UC…`),
pagina a playlist de uploads, busca os vídeos em lotes de 50, filtra Shorts (`e_short`:
vertical e ≤ 180 s) e grava. `YouTubeMedido` envolve a porta e soma as unidades de cota por
método (`CUSTO_EM_UNIDADES`: canal 1, página 1, vídeos 1, busca 100); `registrar_cota`
grava por run. `coletar(so_faltantes=True)` retoma uma coleta interrompida.

Custo real: 46k Shorts por ~2,8k unidades (cota diária gratuita: 10k).

## `camada_bruta.py` + `adaptadores/gancho.py`, `gemini.py`, `locais.py` — o gancho

`processar(banco, deps, ex, video_id, fonte, pasta, salvar=True)`:

1. `ExtratorYtDlp.extrair(fonte, pasta, segundos=5)`: yt-dlp baixa só o começo; ffmpeg tira
   `FRAMES_POR_GANCHO` frames espaçados e o áudio.
2. `DescritorGeminiDireto.descrever(frames)` (ou OpenRouter): texto do que se vê. Grátis no
   AI Studio; a cota zera à meia-noite do Pacífico (04:00 BRT).
3. `TranscritorWhisper.transcrever(audio)`: faster-whisper local.
4. `EmbedderSigLIP.embutir(frames)`: vetor médio dos frames.

Resultado em `camada_bruta`. Falhas vão para `falhas` com a etapa e o erro; `reprocessar`
limpa e refaz. `processar_ganchos(limite_por_canal, canais, desde)` escolhe o lote; é a
operação cara (minutos por vídeo na CPU + cota do Gemini), por isso o agente confirma lotes
grandes com o usuário.

**Modo leve** (`processar(..., leve=True)`, `processar_ganchos(leve=True)`, CLI `--leve`):
pula os passos 2 e 3 e grava `descricao = ""` e `transcricao = ""`; ficam frames e
embedding, que é o que o extrator `vizinhos` precisa. Segundos por vídeo, sem cota: é como
a camada de gancho escala para a base inteira. A descrição vazia é a marca de "gancho leve":
`pendentes(leve=False)` inclui esses vídeos (a rodada completa os preenche) e
`pendentes(leve=True)` não (leve não refaz leve); `calcular_atributos` os pula sem marcar
falha (conta em `ResumoGanchos.incompletos`), porque o LLM só teria título e tags para ler.
Completar um gancho leve refaz o vídeo inteiro (download, frames, embedding, descrição,
fala) e substitui a linha: as partes refeitas custam segundos, guardar o áudio de dezenas de
milhares de ganchos custaria gigabytes, e o código fica com um caminho só.

## `atributos.py` + `adaptadores/jev.py` — perguntas tipadas

`Atributo`: `id`, `tipo` (`choice` com `{rótulo: descrição}`, `score` com níveis
ordenados, `noul` sim/não), `instrucoes`. `assinatura` (hash da definição) muda quando a
pergunta muda e invalida respostas antigas. `PADRAO`: 15 atributos de gancho (rosto, fala
para câmera, texto na tela, tipo e força do gancho, formato, produção, ritmo, CTA, tom do
título…). `DE_TITULO`: 4 perguntas só de título (tom, promete resultado, chama ação, cita
tendência).

Dois papéis, dois extratores (`portas.Dependencias.jev` e `.rapido`):

- **`jev` (gancho)**: lê `estado_do_video` = título + descrição + tags + descrição visual +
  fala. Padrão: `JevWorkersAI` com `@cf/meta/llama-3.1-8b-instruct-fast` (Cloudflare Workers
  AI, grátis), saída forçada por JSON schema e convertida para o formato do Jev
  (`_no_formato_jev`: choice vira one-hot em `probabilities`). Alternativas: `JevCloudflare`
  (`typesafe/jev`, pago, nunca usado) e `JevLaya` (reserva offline).
- **`rapido` (título)**: `JevLaya`, encoder aberto local (~0,15–0,2 s por vídeo; o
  `predict_batch` dele não acelera). Roda em todos os vídeos que o modelo usa
  (`videos_sem_titulo`: 300 mais recentes por canal).

Por que o Laya saiu do gancho: medido em 474 ganchos, responde "sim" a quase tudo (rosto
96%, fala 95%, produto 93%), concorda 26–69% com o LLM e piora o modelo em todos os pares.
Sua confiança não prevê acerto (correlação 0,18), então uma cascata "Laya decide quando
confiante" não funciona; a discordância entre extratores virou gatilho da revisão humana.

`features(banco, atributos, extrator)` devolve uma linha por vídeo com resposta atual para
todos os atributos pedidos (`para_features`: choice → uma coluna por rótulo com a
probabilidade; score/noul → valor). `salvar_respostas_de_varios` grava muitos vídeos num
`executemany` só (o extrator `vizinhos` rotula a base inteira de uma vez).

### `vizinhos.py` — atributos por kNN sobre o embedding

Por que existe: o LLM lê o gancho só depois do Gemini (cota de ~250/dia) e do Whisper
(lento), e por isso só 474 vídeos têm atributos; o embedding SigLIP sai em segundos para
qualquer vídeo (modo leve). Medido na base: um kNN sobre esses embeddings (cosseno, k = 7,
voto da maioria) concorda 71% com os rótulos do LLM e, quando ≥ 80% dos vizinhos concordam,
85–95% nos atributos visuais (rosto, enquadramento, texto na tela…).

- **Fonte** (`rotulos_fonte(banco, definicoes, extrator_fonte=None)`): as *sementes* são os
  vídeos com embedding em `camada_bruta` e resposta atual (assinatura) da fonte para todos
  os atributos. `detectar_fonte` escolhe o extrator do Workers AI (`@cf/...`) se houver;
  senão qualquer um que não seja `vizinhos` nem `laya` (nos testes, `falso`). Embeddings
  são normalizados: produto escalar = cosseno.
- **Resposta** (`responder(embedding, fonte, definicoes, k=7)`), no formato do Jev, para
  `para_features` ler igual às respostas do LLM:
  - `choice`: `probabilities` = fração dos k vizinhos por rótulo, `choice` = maioria (empate:
    o primeiro da lista de critérios), `confidence` = fração da maioria;
  - `noul`: `noul` = fração de vizinhos "sim", `confidence` = `max(p, 1 − p)`;
  - `score`: `score` = mediana baixa dos níveis dos vizinhos (cai sempre num nível
    observado), `confidence` = fração dos vizinhos nesse nível.
  A confiança é sempre a fração de vizinhos que concordam com a resposta: é o que, medido,
  separa os casos em que o kNN acerta 85–95% dos demais.
- **Rotular** (`rotular(banco, definicoes, k, extrator_fonte)` → `ResumoVizinhos(rotulados,
  sementes, k, fonte)`): grava respostas com `extrator = "vizinhos"` para todo vídeo com
  embedding que **não** é semente. Refaz os já rotulados a cada chamada: as sementes crescem
  a cada `calcular_atributos` e o voto muda. Em lotes de `LOTE = 512` vídeos para não trazer
  46k embeddings de uma vez. As sementes não recebem resposta `vizinhos` (o LLM já as
  respondeu); uma receita com `extrator = "vizinhos"` treina só nos demais.
- **Avaliar** (`avaliar(banco, definicoes, k)` → `AvaliacaoVizinhos`): leave-one-out sobre
  as sementes. Por atributo: `concordancia` kNN × fonte, `concordancia_confiante` só onde
  `confidence ≥ LIMIAR_CONFIANCA = 0,8`, `fracao_confiante` (quantos casos são esses) e
  `majoritario` (baseline: responder sempre o rótulo mais comum). Um atributo em que a
  concordância não passa do majoritário não ganha nada com o kNN.

**Cascata recomendada**: `vizinhos` decide quando `confidence ≥ 0,8`; nos demais, pergunta
ao LLM (rode `processar_ganchos` completo nesses vídeos e depois `calcular_atributos`). O
`vizinhos` aparece em `otimizacao.disponiveis` como mais um extrator, então a busca compara
receitas com atributos do LLM e dos vizinhos. Na análise de um vídeo novo com modelo
treinado em `vizinhos`, os atributos saem de `responder` sobre o embedding do gancho, sem
LLM (ver 04).

## `crescimento.py` — curva por idade

A coleta é uma foto só: idade e época se confundem, e árvores não extrapolam para idades
que não viram. `semear` transforma a coleta na primeira observação de cada vídeo;
`observar_recentes` (serviço) busca de novo os vídeos com menos de 90 dias (1 unidade por
50) e grava em `observacoes`. `curva(banco, alvo)` calcula, por faixa de idade, a mediana
de `d log(1+y) / d log(idade)` entre a primeira e a última observação (mínimo 20 vídeos por
faixa). `Curva.fator(de, ate)` integra a inclinação. `idade_minima_vista` (5º percentil da
idade na coleta, ~48 dias) marca abaixo de que idade a timeline usa a curva.

Medido em moda e beleza: likes estabilizam a partir de ~10 dias; views crescem devagar até
~40.

## `trace.py` — execuções, etapas e andamento

`executar(banco, operacao)` abre um `run` (`rodando` → `ok`/`falhou`). `Execucao.etapa(nome,
entrada)` registra duração, entrada, saída e erro em `trace` (ordem crescente). A cada
etapa também grava `andamento.json` ao lado do banco (run, operação, nº de etapas, última
etapa, horário) e apaga ao terminar; `ler_andamento` serve a API sem abrir o DuckDB. Se o
processo morrer no meio, o run fica `rodando` e o arquivo fica para trás: a limpeza é
manual (`UPDATE runs SET status='falhou' WHERE status='rodando'`, apagar o arquivo).

## `erros.py`

Hierarquia `ErroGalaxies`: `ProjetoNaoEncontrado`, `ProjetoJaExiste`, `ConfigInvalida`
(envolve `ValidationError` e `ValueError` de receitas), `DependenciaAusente` (`.env`),
`CanalNaoEncontrado`, `CanalForaDaBase`, `CotaEsgotada`. A API traduz para 404/400; o MCP
devolve como erro da tool.
