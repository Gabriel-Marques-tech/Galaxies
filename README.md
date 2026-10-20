# Galaxies

Framework para prever a performance de YouTube Shorts de um setor (entregue com um modelo
treinado para moda e beleza). O agente do usuário (Claude Code, Codex) opera tudo via MCP:
cria o projeto, coleta canais, ajusta os atributos ao setor, treina, avalia e analisa um
vídeo antes de publicar.

Tudo roda em serviços gratuitos: YouTube Data API, Gemini pelo AI Studio (descrição do
gancho), Workers AI da Cloudflare (atributos no formato do Jev), Whisper e SigLIP locais.

## Setup

```bash
uv sync --extra multimodal
cp .env.example .env   # preencha as chaves
```

| Variável | Onde pegar |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console → APIs → YouTube Data API v3 |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | dash.cloudflare.com (token com Workers AI) |
| `ATRIBUTOS_MODELO` | `@cf/meta/llama-3.1-8b-instruct-fast` (grátis) ou `typesafe/jev` (pago) |

## Conectar o agente (MCP, stdio)

**Claude Code:** o `.mcp.json` da raiz já registra o servidor. Abra o Claude Code nesta
pasta e aprove o servidor `galaxies`. Em outra pasta:

```bash
claude mcp add galaxies -- uv --directory /caminho/para/Galaxies run --extra multimodal galaxies-mcp
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.galaxies]
command = "uv"
args = ["--directory", "/caminho/para/Galaxies", "run", "--extra", "multimodal", "galaxies-mcp"]
```

Fluxo típico pedido ao agente:

1. `criar_projeto` com setores, canais-semente e alvo (`likes` ou `views`).
2. `coletar` → `processar_ganchos` (amostra) → `calcular_atributos` → `treinar`.
   São jobs: o agente acompanha com `status`.
3. `avaliar`: baseline do canal, camadas (metadados, +multimodal, +atributos) e ganho por
   atributo.
4. `definir_atributos` para adaptar as perguntas ao setor e treinar de novo.
5. `analisar` um vídeo novo: faixa em 7 dias, timeline 1/3/7/14/30 dias, P(viral) e fatores.
6. `runs`, `trace`, `erros`, `falhas`, `reprocessar` para auditar.

## CLI

O mesmo núcleo pela linha de comando: `uv run python -m galaxies --help`.

## Regras fixas de avaliação

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana só do treino.
- Split temporal: 20% mais recentes no teste, só vídeos com 7+ dias.
- Até 300 vídeos por canal (os mais recentes), para canais gigantes não dominarem.
- Métricas: MAE no log e Spearman dentro do canal, contra o baseline "média do canal".

## Testes

```bash
uv run pytest
```
