# 06 · Operação

## Setup

```bash
uv sync --extra multimodal        # Python 3.12; multimodal = Whisper, SigLIP, MiniLM, Laya, torch
cp .env.example .env              # preencha YOUTUBE_API_KEY, GEMINI_API_KEY, CLOUDFLARE_*
cd ui && npm install
```

Serviços gratuitos usados: YouTube Data API (10k unidades/dia), Google AI Studio (Gemini
Flash-Lite; cota zera às 04:00 BRT), Cloudflare Workers AI (LLM dos atributos), e modelos
locais (Whisper, SigLIP, MiniLM, Laya). Chaves só no `.env` (gitignored). O PDF do TAPI fica
fora do repo.

## Rodar

```bash
uv run galaxies-mcp                               # servidor MCP (stdio); .mcp.json já aponta
uv run --extra multimodal galaxies-api            # API em :8000
cd ui && npx vite --host 127.0.0.1 --port 5173    # UI
uv run python -m galaxies --help                  # CLI
```

Com o agente (Claude Code no repo): peça em linguagem natural; ele chama `proximo_passo` e
segue o pipeline. Jobs devolvem `job_id`; `status` acompanha.

## Rotina diária

Uma vez por dia (agente ou cron):

```bash
uv run python -m galaxies rotina moda-beleza
```

Reobserva vídeos recentes (curva de crescimento, ~125 unidades por 6k vídeos), atualiza os
acompanhamentos, coleta o que os canais publicaram e reotimiza se a base cresceu 100 vídeos
ou 2%. O `proximo_passo` diz se algo mais é pedido.

## Custos e tempos de referência (moda-beleza)

| operação | tempo | cota |
|---|---|---|
| coletar 113 canais / 46k Shorts | minutos | ~2,8k unidades |
| calcular_texto (MiniLM, 46k) | minutos | 0 |
| calcular_titulos (Laya, 14k da base) | 0,15–0,4 s/vídeo sozinho; 1 s com CPU disputada | 0 |
| processar_ganchos | minutos por vídeo (Whisper + SigLIP) | Gemini: ~200–250 descrições/dia grátis |
| calcular_atributos (LLM) | segundos por vídeo | Workers AI: cota diária grátis |
| otimizar (13–14 receitas) | 3–4 min | 0 |
| observar_recentes (6k vídeos) | 1 min | 125 |

**Uma carga pesada por vez.** Laya + suíte de testes + otimização ao mesmo tempo derrubou a
máquina uma vez. O DuckDB também só aceita um escritor.

## Limites conhecidos

- Teto do dado: com 113 canais, A vs B fica em ~58% e o erro típico em ~1,9×. Mais canais
  é a única alavanca que sobe o teto.
- Camadas de gancho (474 vídeos) não têm poder estatístico: precisam de ~2,9k ganchos para
  uma diferença de 1% ser mensurável. O agente diz isso e não insiste.
- A validação é o fim do treino; uma deriva que começa depois dela só aparece no teste. A
  âncora móvel atenua (segue o momento do canal); o remédio estrutural é reotimizar com a
  base atualizada.
- Timeline abaixo de ~48 dias de idade usa a curva de crescimento observada (ainda com
  poucos dias de observação; melhora a cada `observar_recentes`).
- Sugestões são associação, não causa.

## Como estender

**Nova camada de features**: (1) uma tabela ou cálculo que dê um DataFrame indexado por
`video_id`; (2) entrada em `experimentos._camadas_extras` e `_montar_x`; (3) o literal
`Camada` e `RECEITAS_PADRAO`; (4) `otimizacao.disponiveis` e `EXTRAS`; (5) em `analise.features`
a mesma coluna para o vídeo novo (e no serviço `analisar`, como obtê-la ao vivo); (6) o
`meta.json` precisa carregar o que a análise precisa (como `titulo` e os PCAs).

**Novo extrator de atributos**: classe com `perguntar(estado, perguntas) → dict` no formato
do Jev e atributo `identificador`; registrar em `ambiente.extrator_de_atributos`.

**Novo adaptador externo**: implementar o Protocol em `portas.py`, montar em `ambiente.py`,
criar um falso em `tests/fakes.py`.

**Nova tool**: método no `Framework` (Pydantic na saída) → `@tool` em `mcp_servidor.py`
(com `jobs.iniciar` se for longa) → rota em `api.py` → comando no `__main__.py` → tipo e
chamada em `ui/src/api.ts`.

## Testes

```bash
uv run pytest                 # tudo (~8 min: treina e otimiza de verdade)
uv run pytest -m "not lento"  # ciclo rápido (~2 min)
uv run ruff check src tests && uv run ruff format --check src tests
```

`tests/conftest.py` baixa `MIN_VALIDACAO` para 10 nas bases falsas. Os falsos
(`tests/fakes.py`) cobrem todas as portas; `base_com_sinal` gera canais com padrões
aprendíveis. Testes que treinam de verdade levam o marcador `lento`.

## Problemas comuns

| sintoma | causa | saída |
|---|---|---|
| `IO Error: Could not set lock on file` | outro processo com o banco aberto | espere o job acabar; API em dev usa snapshot |
| runs presos em `rodando` e `andamento.json` sobrando | processo morreu no meio | `UPDATE runs SET status='falhou' WHERE status='rodando'`; apagar o arquivo |
| Gemini 429 | cota diária do AI Studio | espera até 04:00 BRT; `processar_ganchos` retoma |
| `DependenciaAusente` | chave faltando no `.env` ou `framework(multimodal=False)` | preencher / usar `--extra multimodal` |
| `receita com poucos dados` | camada cobre poucos vídeos | processar ganchos, calcular texto/títulos |
| UI "API indisponível" | API fora ou porta errada | `uv run --extra multimodal galaxies-api`; proxy do Vite para :8000 |
| Vite só em `::1` | IPv6 | `--host 127.0.0.1` |
