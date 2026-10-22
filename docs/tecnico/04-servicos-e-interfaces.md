# 04 · Serviços e interfaces

## `servicos.py` — `Framework`

`Framework(raiz, dependencias)` é o único ponto de entrada do núcleo. Cada método público é
um serviço: abre o banco do projeto (`_abrir_existente`), registra um run (`trace.executar`)
e devolve Pydantic. Agrupados:

**Projeto**: `criar_projeto`, `listar_projetos`, `obter_projeto`, `definir_modo`, `canais`,
`resumo` (contagens para a visão geral), `cota`.

**Dados**: `coletar(so_faltantes)`, `adicionar_canal`, `descobrir_canais(consulta,
teto_unidades)` (busca paga: 100 unidades por página), `processar_ganchos(limite_por_canal,
canais, desde, leve)` (`leve=True`: só frames e embedding, sem Gemini nem Whisper; exige só
`extrator` e `embedder`; uma rodada sem `leve` depois completa os ganchos leves),
`reprocessar`, `excluir`, `falhas`, `calcular_texto`, `calcular_titulos`,
`calcular_atributos` (pula ganchos leves: `incompletos` no resumo), `atributos`,
`definir_atributos` (substitui as perguntas; respostas de atributos inalterados ficam),
`features_de_atributos`, `rotular_vizinhos(k=7, extrator_fonte=None)` (atributos por kNN
para os ganchos que o LLM não leu; run `rotular_vizinhos`, etapa `rotular`),
`avaliar_vizinhos(k=7, extrator_fonte=None)` (leave-one-out: concordância kNN × LLM por
atributo; run `avaliar_vizinhos`, etapa `leave_one_out`). Ver `vizinhos.py` em 02.

**Modelo**: `treinar` (diagnóstico), `experimentar(receita, hipotese, alvo)`,
`experimentos(alvo)`, `promover`, `decidir(aprovar, nota)` (humano), `otimizar(alvo,
orcamento, paciencia)`, `ciclo_automatico`, `erros(alvo)` (falhas do pipeline + onde o
modelo mais erra), `insights` (setores, ganchos e formatos que mais rendem a partir das
respostas do extrator atual, melhores horários, dias, duração).

**Uso**: `analisar(video, canal_id)`, `comparar(video_a, video_b, canal_id)`. Se o modelo
ativo foi treinado com `extrator = "vizinhos"`, a análise responde os atributos com
`vizinhos.responder` sobre o embedding do gancho (etapa `responder_vizinhos`), não exige
`jev` e ignora a checagem de `ATRIBUTOS_MODELO`; sem `descritor` ou `transcritor`
configurados, processa o gancho em modo leve (a análise sai sem descrição e fala, mas com
atributos e previsão).

**Produção**: `acompanhar(run_id, video_id)`, `atualizar_acompanhamentos`,
`acompanhamentos`, `observar_recentes(dias_max)`, `crescimento(alvo)`.

**Diagnóstico** (`diagnostico.py`): `diagnostico(projeto, alvo)` mede na base o que explica um
ganho baixo antes de culpar o modelo (ruído dentro do canal, controle fraco, canais rasos,
setores misturados, camadas incompletas, alvo alternativo, idade, reobservação) e devolve
pistas com evidência e ação; o `otimizar` devolve as mesmas em `Ciclo.pistas`.

**Roadmap**: `proximo_passo` (regras sobre o estado → ação, motivo, certeza `regra` ou
`ambiguo`, alternativas) e `rotina` (reobserva, atualiza acompanhamentos, coleta vídeos
novos e reotimiza se a base cresceu `LIMIAR_NOVOS_ABSOLUTO = 100` ou
`LIMIAR_NOVOS_FRACAO = 2%`).

**Humano** (`humano.py`): `amostra_para_revisao(atributo, n, extrator)` (primeiro os vídeos
em que os extratores discordam, depois ordem fixa espalhada; mostra as outras respostas),
`revisar`, `concordancia` (confiável se ≥ `MIN_CONCORDANCIA = 0,7`), `anotar_erro(video,
tipo, nota)` (`dado_ruim` exclui o vídeo da base; `padrao` vira pista), `notas`.

**Auditoria**: `runs`, `trace(run_id)`, `andamento`, `relatorio`.

Regra de ouro: lógica de domínio fica aqui ou nos módulos do núcleo. MCP, API e CLI nunca
decidem nada.

## `mcp_servidor.py` — a interface principal

`criar_servidor(fw)` registra cada serviço como tool (`mcp` 2.x, stdio). `INSTRUCOES` é o
texto que o cliente MCP recebe: a ordem do pipeline, quando usar `proximo_passo`, como ler
"sem poder estatístico", o que é modo cientista.

**Jobs**: operações longas (`coletar`, `processar_ganchos` (com `leve`), `calcular_*`,
`rotular_vizinhos(k)`, `otimizar`, `experimentar`, `rotina`, …) rodam em uma thread única
(`Jobs`): a tool devolve `job_id` e o agente acompanha com `status(job_id)`. Uma thread só
porque o DuckDB tem um escritor por vez. `avaliar_vizinhos(k)` responde na hora (segundos).

Tools que só existem na UI, de propósito: `decidir`, `revisar`, `anotar` (portões humanos).

`_texto` serializa tudo em JSON (`serializar.para_json`), igual à API. Entrada: `.mcp.json`
na raiz do repo aponta `galaxies-mcp` (script do `pyproject`).

## `api.py` — console humano (FastAPI)

Espelha os serviços e acrescenta o que só o humano faz. Grupos de rotas em
`/projetos/{projeto}/…`: projeto (`resumo`, `insights`, `canais`, `modo`), atributos,
experimentos (`experimentos`, `…/promover`, `…/decisao`), `avaliacao`, `upload` (vídeo
local para análise: multipart), `analisar`, `comparar`, acompanhamento (`acompanhar`,
`acompanhamentos`, `acompanhamentos/atualizar`, `observar-recentes`, `crescimento`),
roadmap (`proximo-passo`, `andamento`), auditoria (`runs`, `runs/{id}/trace`, `falhas`,
`erros`), humano (`revisao/{atributo}`, `revisao`, `concordancia`, `notas`). Erros do
domínio viram 404/400 com `{"erro": ...}`. CORS liberado para `localhost:5173`.

**Jobs pela API** (`POST /projetos/{p}/jobs {operacao, argumentos}`, `GET /jobs[/{id}]`): só
operações de rede (coletar, observar, acompanhamentos, descobrir/adicionar canal). Rodam numa
thread do processo da API, e como o DuckDB aceita várias conexões no mesmo processo, a UI
segue lendo e escrevendo. Jobs de CPU (Laya, SigLIP, Whisper, treino) ficaram ~100× mais
lentos dentro da API (torch em thread secundária) e seguraram o lock do projeto por horas:
esses rodam pelo MCP ou pela CLI, e enquanto rodam a UI daquele projeto fica indisponível.

Em desenvolvimento a API roda sobre um snapshot do banco (`GALAXIES_DADOS` apontando para
uma cópia), para não disputar o arquivo com jobs do MCP/CLI; o `andamento.json` é lido da
pasta do projeto (symlink), por isso o banner de progresso funciona mesmo assim.

## `__main__.py` — CLI

`uv run python -m galaxies <comando>`: criar-projeto, coletar, cota, processar-ganchos
(`--leve`), rotular-vizinhos (`--k`, `--fonte`), avaliar-vizinhos (`--k`, `--fonte`; imprime
uma linha por atributo), calcular-titulos, calcular-texto, calcular-atributos,
definir-atributos, treinar, falhas, reprocessar, excluir, erros, experimentar, experimentos,
promover, relatorio, otimizar, ciclo-automatico, proximo-passo, rotina, crescimento. Mesmo
núcleo; útil para jobs longos fora do MCP e para o `relatorio`. `processar-ganchos --leve`
monta o framework multimodal, mas o Whisper só carrega o modelo na primeira transcrição, que
não acontece.

## `ambiente.py` — montagem a partir do `.env`

`framework(multimodal=False)`: YouTube se houver `YOUTUBE_API_KEY`; com `multimodal=True`,
yt-dlp, Whisper, SigLIP, MiniLM e o descritor (Gemini direto se `GEMINI_API_KEY`, senão
OpenRouter). Extrator do gancho: `ATRIBUTOS_MODELO` ou, com credenciais da Cloudflare,
`MODELO_LLM_PADRAO = @cf/meta/llama-3.1-8b-instruct-fast`; sem elas, `laya`. Extrator
rápido: sempre `JevLaya`. Raiz dos dados: `GALAXIES_DADOS` (padrão `data`).

## `portas.py` — contratos

Protocols: `YouTube` (canal, página de uploads, vídeos, buscar canais), `ExtratorDeGancho`,
`DescritorDeGancho`, `Transcritor`, `Embedder`, `EmbedderDeTexto`, `Jev` (`perguntar(estado,
perguntas) → respostas`). `Dependencias` agrupa as instâncias (`youtube`, `extrator`,
`descritor`, `transcritor`, `embedder`, `jev`, `rapido`, `texto`). `identificar(jev)`
devolve o nome gravado em cada resposta. Os falsos de `tests/fakes.py` implementam os
mesmos Protocols, com uma base sintética com sinal (`base_com_sinal`).
