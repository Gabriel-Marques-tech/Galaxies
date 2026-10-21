# 01 · Visão geral

## Propósito

Galaxies é um **agente que constrói modelos** de previsão de performance de YouTube Shorts
por setor. Não é um modelo pronto com um agente em volta: o agente do usuário (Claude Code,
Codex ou qualquer cliente MCP) age como cientista de dados, e o framework dá a ele
ferramentas, dados, regras fixas de avaliação e memória do que foi tentado. O humano
acompanha e decide por uma UI.

Entregável de referência: projeto `moda-beleza` (setores moda e beleza, 113 canais, 46k
Shorts), com modelos ativos para likes e views.

Dois modos por projeto:

- **automático**: o agente roda o ciclo e promove sozinho o melhor modelo que supera a média
  do canal e passa pela trava de promoção.
- **cientista** (Data Scientist na UI): cada promoção espera aprovação humana; o humano
  revisa atributos e faz triagem de erros, e as notas voltam para o agente como pistas.

## Arquitetura em camadas

```
┌────────────────────────────────────────────────────────────────────┐
│ Interfaces                                                          │
│  mcp_servidor.py (stdio, ~40 tools, jobs)   api.py (FastAPI → UI)  │
│  __main__.py (CLI)                           ui/ (React + Vite)    │
├────────────────────────────────────────────────────────────────────┤
│ Serviços: servicos.Framework  (único ponto de entrada do núcleo)    │
├────────────────────────────────────────────────────────────────────┤
│ Núcleo                                                              │
│  coleta · camada_bruta · atributos · crescimento · acompanhamento   │
│  modelagem · experimentos · otimizacao · analise · treino           │
│  humano · relatorio · trace · armazenamento · config · erros        │
├────────────────────────────────────────────────────────────────────┤
│ Portas (portas.py: Protocols) → Adaptadores (adaptadores/)          │
│  YouTube Data API · yt-dlp+ffmpeg · Gemini · Whisper · SigLIP ·     │
│  MiniLM · LLM Workers AI · Laya · Jev                               │
├────────────────────────────────────────────────────────────────────┤
│ Dados: um DuckDB por projeto + modelos/ + analises/ (ambiente.py)   │
└────────────────────────────────────────────────────────────────────┘
```

Regras de dependência: interfaces só conhecem `Framework`; núcleo não conhece interfaces;
adaptadores só implementam portas. `ambiente.framework()` monta tudo a partir do `.env`.

## Fluxo ponta a ponta

1. **Projeto** (`criar_projeto`): nome, setores, canais-semente, alvo (`likes` ou `views`),
   modo. Cria `data/projetos/<nome>/galaxies.duckdb`.
2. **Coleta** (`coletar`): YouTube Data API, canal → playlist de uploads → vídeos em lotes de
   50; só Shorts (vertical, ≤ 180 s). Guarda título, descrição, tags, duração, contagens e
   `coletado_em`. Custo medido em unidades de cota.
3. **Camadas para todos os vídeos**: `calcular_texto` (embedding MiniLM de título+descrição)
   e `calcular_titulos` (4 perguntas de título respondidas pelo Laya, local).
4. **Camadas do gancho** (caras, só para um subconjunto): `processar_ganchos` baixa os
   primeiros 5 s, tira frames, Gemini descreve, Whisper transcreve, SigLIP embute;
   `calcular_atributos` faz o LLM responder 15 perguntas tipadas (formato do Jev).
5. **Modelo**: `otimizar` busca a melhor receita na validação e testa só a escolhida; ou
   `experimentar` com uma receita e uma hipótese escritas pelo agente. `promover` ativa.
6. **Uso**: `analisar` um vídeo novo (mediana, faixas de 50% e 80%, timeline 1/3/7/14/30
   dias, chances, fatores, sugestões), `comparar` A vs B.
7. **Produção**: `acompanhar` liga a análise ao vídeo publicado; `atualizar_acompanhamentos`
   e `observar_recentes` vão buscando os números; `crescimento` mede a curva por idade.
8. **Dia a dia**: `proximo_passo` diz o que o estado pede; `rotina` faz o pacote diário.
9. **Auditoria**: todo serviço vira um `run` com `trace` de etapas; `relatorio` gera o
   `docs/avaliacao.md` a partir do banco.

## Regras fixas de avaliação (o agente não altera)

| regra | onde | por quê |
|---|---|---|
| alvo `log((y+1)/(âncora+1))` | `modelagem.alvo_relativo`, `experimentos._ancora_log` | compara vídeos de canais de tamanhos diferentes; log tira a cauda |
| âncora = mediana do canal no treino (ou móvel: média dos últimos 10 vídeos, defasada 7 dias) | idem | a móvel segue o momento do canal; fixa é a referência do baseline |
| split temporal: 20% mais recentes = teste, só vídeos com 7+ dias | `modelagem.dividir` | o que o modelo vai enfrentar é o futuro; 7 dias para as contagens assentarem |
| validação = fim do treino (20% dele) | `experimentos.avaliar(em="validacao")` | a busca compara receitas aqui; o teste é usado uma vez por experimento |
| teto de 300 vídeos por canal (os mais recentes) | `modelagem.MAX_POR_CANAL` | canais gigantes não dominam |
| baseline = média do canal; controle = só metadados com hiperparâmetros padrão, nas mesmas linhas | `experimentos.avaliar` | toda receita é comparada com os dois |
| métricas: MAE no log, acerto A vs B em pares do mesmo canal, Spearman no canal, cobertura real das faixas | `modelagem.medir`, `experimentos._cobertura` | erro, ranking e honestidade da faixa |
| bootstrap pareado modelo × controle (1000 reamostras) | `modelagem.confianca_pareada` | separa ganho real de ruído |
| trava de promoção: ganho > 0; camadas extras exigem ≥ 1% sobre o controle e confiança ≥ 90% no teste; não cair mais de 2 pontos abaixo do ativo | `experimentos.motivo_para_nao_promover` | a validação propõe, o teste decide |

## Glossário

- **Receita**: `{camadas, atributos, extrator, params, ancora}`. O que o agente escolhe.
- **Camada**: grupo de features. `metadados` (sempre), `historico`, `texto`, `titulo`,
  `multimodal`, `atributos`.
- **Baseline**: prever a média (mediana) do canal. **Controle**: modelo só de metadados.
- **Ganho**: `1 − MAE_modelo / MAE_baseline`. **Melhora sobre o controle**: idem vs controle.
- **Faixa quase certa (80%)**: q10–q90 calibrados. **Faixa provável (50%)**: q25–q75
  derivados da calibrada. **Cobertura**: fração dos reais dentro da faixa.
- **Gancho**: primeiros 5 s do vídeo. **Camada bruta**: frames, descrição, fala, embedding.
- **Atributo**: pergunta tipada (`choice`, `score`, `noul`) no formato do Jev.
- **Extrator**: quem responde os atributos (`laya`, `@cf/...`, `typesafe/jev`).
- **Run / etapa / trace**: uma chamada de serviço, seus passos e o registro deles.
- **Job**: run disparado pelo MCP em segundo plano; o agente acompanha com `status`.
- **Deriva**: o período recente rende diferente do histórico (hoje: ~18% abaixo).
