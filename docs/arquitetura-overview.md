# Stars (Galaxies) · arquitetura em uma conversa

Guia para explicar a arquitetura de cabeça, do mais geral ao mais específico. A versão
completa, módulo por módulo, está em `docs/tecnico/01` a `08`.

## A frase

Stars é um **servidor MCP** que qualquer LLM pluga (Gemini CLI, Claude Code, Codex). Por
trás dele existe um **framework de ciência de dados com regras fixas**: coleta, camadas de
features, busca de receitas, teste uma vez, trava de promoção, operação diária. O LLM decide
*o que tentar*; o framework decide *se valeu* e nunca deixa o LLM mexer na régua.

Quem faz o quê:

| quem | faz | não faz |
|---|---|---|
| LLM (Gemini/Claude) | escolhe o próximo passo, escreve hipóteses, cria atributos novos, explica ao humano | não mede, não decide promoção, não altera split/baseline/métrica |
| Framework (Python) | coleta, features, treino, validação, teste, calibração, promoção, trace, rotina | não "pensa" em linguagem natural; só regras e números |
| Humano | aprova promoções no modo Data Scientist, revisa atributos, anota erros | não precisa saber de ML para operar |

## Cinco camadas, de fora para dentro

```
Interfaces   MCP (stdio, ~40 tools)  ·  API FastAPI → UI React  ·  CLI
                    │ todas chamam a mesma coisa:
Serviços     servicos.Framework  (uma classe; cada método vira um "run" com trace)
                    │
Núcleo       coleta · camada_bruta · atributos · vizinhos · modelagem · experimentos
             otimizacao · analise · acompanhamento · crescimento · diagnostico · humano
                    │ só fala com o mundo por contratos (portas.py)
Adaptadores  YouTube Data API · yt-dlp+ffmpeg · Gemini · Whisper · SigLIP · MiniLM
             LLM (Workers AI) · Laya · Jev     ← todos trocáveis, todos gratuitos
                    │
Dados        um DuckDB por projeto (data/projetos/<setor>/galaxies.duckdb)
             + modelos/ (LightGBM q10/q50/q90 + meta.json) + uploads/
```

Regra de dependência: interfaces só conhecem `Framework`; o núcleo não sabe que existe
MCP ou UI; adaptadores só implementam portas. Trocar Gemini por outro descritor de imagem é
escrever um adaptador.

## O fluxo de um setor (os "50 minutos")

1. **criar_projeto** → DuckDB novo. `descobrir_canais` (busca do YouTube) → `adicionar_canal`
   → `coletar`: só Shorts (vertical, ≤ 180 s), metadados e contagens. Custo em unidades de
   cota, registrado.
2. **Camadas baratas para todos os vídeos**: `calcular_texto` (embedding MiniLM de título e
   descrição) e `calcular_titulos` (perguntas de título, Laya local).
3. **Camadas caras só para um subconjunto**: `processar_ganchos` baixa os 5 primeiros
   segundos, tira frames (Gemini descreve, Whisper transcreve, SigLIP embute);
   `calcular_atributos` faz o LLM responder 15 perguntas tipadas sobre o gancho. Modo leve:
   frames + SigLIP, e `rotular_vizinhos` (kNN) copia os rótulos dos ganchos que o LLM já leu.
4. **otimizar**: busca de receitas (`{camadas, atributos, extrator, params, âncora}`) na
   **validação**; só a vencedora vai ao **teste**, uma vez. Cada tentativa é comparada com o
   **baseline** (média do canal) e com um **controle** (só metadados) nas mesmas linhas.
5. **Trava de promoção**: ganho > 0; camadas extras precisam de ≥ 1% sobre o controle com
   confiança ≥ 90% (bootstrap pareado); só substitui o ativo quem o supera no teste.
6. **analisar**: um vídeo novo entra pela mesma régua: mediana, faixa de 50% e de 80%,
   timeline 1/3/7/14/30 dias, chances, fatores (SHAP), sugestões.
7. **Operação**: `acompanhar` liga a análise ao vídeo publicado; `observar_recentes` reobserva
   todo dia (curva de crescimento); `proximo_passo` e `diagnostico` dizem o que o estado do
   projeto pede; `rotina` empacota o dia.

## O modelo em si (se perguntarem)

- LightGBM quantílico, três modelos (q10, q50, q90), alvo `log((y+1)/(âncora+1))`: o vídeo é
  previsto **em relação ao próprio canal**, não em valor absoluto. Âncora móvel = média dos
  últimos 10 vídeos do canal, defasada 7 dias (segue o momento do canal).
- Split temporal: 20% mais recentes = teste, só vídeos com 7+ dias. Validação = fim do treino.
- Calibração conformal da faixa de 80% na validação; a de 50% é derivada.
- Métricas: MAE no log (vira "erro típico ×"), acerto A vs B em pares do mesmo canal,
  cobertura real das faixas. Teto de 300 vídeos por canal.

## Por que MCP e não uma API própria para o agente

O agente não é nosso. A plateia usa Gemini, Claude ou Codex; o Stars entra como conector.
Toda tool devolve JSON com motivo (`proximo_passo` diz *por quê*), jobs longos devolvem
`job_id` e o agente consulta `status`. A UI React existe porque humano precisa ver; ela usa
a API FastAPI que chama o **mesmo** `Framework`. Nada que a UI mostra é diferente do que o
agente vê.

## Guardrails que valem citar

- Validação separada do teste; teste usado uma vez por receita escolhida.
- "Sem poder estatístico": uma camada com menos de 300 linhas na validação não entra na
  busca, e a mensagem diz quantos vídeos faltam.
- Troca lateral não vale: um candidato com ganho igual não substitui o ativo.
- Diagnóstico com evidência: setor ruidoso (desvio dentro do canal), canais rasos, camada
  incompleta, setores misturados. Foi assim que fitness e saúde viraram dois projetos.
- Explicação só com números das tools; o LLM não inventa valor (a explicação textual da
  análise é montada por template a partir das faixas).
- Trace de cada run: entrada, saída e tempo por etapa; a análise gravada reabre do trace.

## Custos e infra

Tudo gratuito: YouTube Data API (10 mil unidades/dia; 93k Shorts custaram ~14 mil
unidades somadas), AI Studio (Gemini), Workers AI (LLM dos atributos), Whisper, SigLIP, MiniLM
e Laya rodando localmente. Um laptop. Um DuckDB por projeto, sem servidor de banco.

## Respostas prontas

- *"Por que não um modelo só para todos os setores?"* Setores têm ruído e teto diferentes
  (fitness: likes variam muito dentro do canal). Um projeto por setor dá um diagnóstico
  honesto por setor e deixa o agente decidir dividir.
- *"O gancho ajuda?"* Ainda não dá para afirmar: os ganchos processados caem no período de
  teste; a validação tem 22 linhas com gancho (mínimo 300). O framework recusou medir.
- *"58% em A vs B é pouco?"* Acaso é 50%; o teto vem do dado (o que acontece depois de
  publicar o vídeo não carrega). O valor principal é o erro 24% menor que a média do canal e
  a faixa que cumpre o que promete.
- *"Quanto tempo para um setor novo?"* Coleta + texto + títulos + otimizar: cerca de 50 min
  com a cota disponível. Títulos locais para dezenas de milhares de vídeos levam horas
  (foi o gargalo da sessão real do automotivo).
- *"E se o LLM errar?"* Ele só escolhe receitas e escreve hipóteses; a régua é fixa e a
  promoção passa pela trava. No modo Data Scientist, passa também por você.
