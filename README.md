# Galaxies

Um agente que **constrói** o modelo de previsão de performance de YouTube Shorts de um setor
(entregue com o modelo criado para moda e beleza). O agente do usuário (Claude Code, Codex)
trabalha via MCP como cientista de dados: coleta canais, define atributos do setor, roda
experimentos, compara com o baseline e promove o melhor modelo. O humano acompanha e decide
pela UI.

- **Modo automático:** o agente roda o ciclo padrão e promove sozinho o melhor modelo que
  supera o baseline. Para quem quer o modelo pronto e os números.
- **Modo Data Scientist (`cientista`):** o humano participa. Aprova cada promoção, revisa as
  respostas dos atributos e faz a triagem dos erros; as notas viram pistas para o agente.

As regras de avaliação são fixas (o agente não as altera): todo experimento é comparado, nas
mesmas linhas de teste, com o baseline do canal e com um controle só de metadados.

Tudo roda em serviços gratuitos: YouTube Data API, Gemini pelo AI Studio (descrição do
gancho), Laya local (atributos no formato do Jev), Whisper e SigLIP locais.

## Resultados (moda e beleza, 46.393 Shorts de 113 canais)

Modelos encontrados pelo agente com `otimizar`, medidos uma vez no teste (os 20% de vídeos
mais recentes). Baseline = média do canal.

| Alvo | Receita escolhida pelo agente | Erro vs baseline | Acerto A vs B no canal | Faixa de 80% cobre |
|---|---|---|---|---|
| likes | metadados + histórico do canal (ajustado) | **−19,0%** (MAE 0,700 vs 0,863) | 58,5% (acaso: 50%) | 74% |
| views | metadados + histórico + texto (ajustado) | **−18,6%** (MAE 0,697 vs 0,856) | 57% | 72% |

Camadas de gancho e atributos (474 ganchos, 190 no teste) ainda não entram no modelo final:
com 22 linhas na validação não há poder estatístico, e o agente agora diz quantos vídeos
faltam (~2.900 com gancho) antes de insistir. Toda comparação com o controle traz um
bootstrap pareado: "ganho real" (≥ 90%) ou "indistinguível". Peso por recência
(`meia_vida_dias`) entra na busca e, nesta base, não ajudou (a deriva do período de teste
vem depois da validação).

O que isso quer dizer na prática: o erro típico cai de ~2,4× para ~2,0×; de dois vídeos
do mesmo canal, o modelo aponta o melhor em ~58% dos casos; a faixa prometida de 80% contém
~75% dos resultados reais (80% no fim do treino; o período de teste derivou para baixo, e o
ciclo de reotimização é o remédio). Serve para expectativa, triagem e priorizar testes, não
para cravar números.

A base é uma foto só, então o framework **reobserva os vídeos recentes** (`observar_recentes`,
1 unidade de cota por 50 vídeos) e mede a curva de crescimento por idade: em moda e beleza,
likes estabilizam a partir de ~10 dias e views seguem crescendo devagar até ~40 dias. A
timeline usa essa curva nas idades que o modelo não viu no treino. Relatório completo, com todas as tentativas do agente:
[`docs/avaliacao.md`](docs/avaliacao.md), gerado por
`uv run python -m galaxies relatorio moda-beleza`.

## Setup

```bash
uv sync --extra multimodal
cp .env.example .env   # preencha as chaves
```

| Variável | Onde pegar |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console → APIs → YouTube Data API v3 |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `ATRIBUTOS_MODELO` | `laya` (padrão, local), `@cf/meta/llama-3.1-8b-instruct-fast` ou `typesafe/jev` (pago) |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | só para os extratores do Workers AI / Jev |

O [Laya](https://github.com/NandhaKishorM/laya) é um encoder aberto (Apache-2.0) que responde
perguntas choice/score/noul no mesmo formato do Jev da TypeSafe. Não é o Jev; o Jev oficial
continua disponível com `ATRIBUTOS_MODELO=typesafe/jev`. As respostas ficam guardadas por
extrator, e a receita do experimento escolhe qual usar, o que permite compará-los.

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

1. `criar_projeto` com setores, canais-semente, alvo (`likes` ou `views`) e `modo`.
2. Dados: `coletar` → `processar_ganchos` (amostra) → `calcular_atributos`. São jobs: o
   agente acompanha com `status`.
3. Modelo: `otimizar` busca a melhor receita (camadas, atributos, extrator, hiperparâmetros)
   na validação e mede só a escolhida no teste. `experimentar` testa uma ideia específica com
   uma hipótese; `experimentos` compara; `promover` ativa. No modo automático,
   `ciclo_automatico` faz tudo.
4. Adaptar: ler `erros`, `notas` e `concordancia`, ajustar com `definir_atributos` e
   experimentar de novo.
5. `analisar` um vídeo novo: mediana em 7 dias com duas faixas (provável, 50%, e quase
   certa, 80%), timeline 1/3/7/14/30 dias, P(viral), fatores e sugestões de mudança
   ("título em pergunta: +X%"). A faixa de 80% é larga de propósito: o erro típico é 2×,
   e canais voláteis têm histórico de 10× entre um vídeo fraco e um bombado.
6. Depois de publicar: `acompanhar` liga a análise ao vídeo real; `atualizar_acompanhamentos`
   busca os números com o tempo; `acompanhamentos` mostra previsto × real em produção.
   `observar_recentes` (1×/dia) reobserva todos os vídeos recentes da base; `crescimento`
   mostra a curva que daí sai.
7. `runs`, `trace`, `falhas`, `reprocessar` para auditar.

## Console humano (UI)

```bash
uv run --extra multimodal galaxies-api   # API em :8000
cd ui && npm install && npm run dev      # UI em :5173
```

Abas: **Modelos** (experimentos contra baseline e controle, sugestões, aprovar/rejeitar),
**Revisão de atributos** (concordância humano × extrator), **Erros** (triagem: dado ruim ou
padrão) e **Trace** (cada passo de cada execução). Enquanto o agente roda um job (MCP ou
CLI), uma faixa no topo mostra a operação, a etapa atual e o tempo decorrido: o run grava
`andamento.json` ao lado do banco e a UI lê sem abrir o DuckDB.

## CLI

O mesmo núcleo pela linha de comando: `uv run python -m galaxies --help`.

## Regras fixas de avaliação

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana só do treino.
- Split temporal: 20% mais recentes no teste, só vídeos com 7+ dias.
- Até 300 vídeos por canal (os mais recentes), para canais gigantes não dominarem.
- Métricas: MAE no log e Spearman dentro do canal, contra o baseline "média do canal".

## Testes

```bash
uv run pytest                 # tudo (~8 min: treina e otimiza de verdade)
uv run pytest -m "not lento"  # ciclo rápido (~2 min)
```
