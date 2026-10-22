# Roteiro da apresentação (23/10/2026)

Tese em uma frase: **ciência de dados reprodutível por setor em 40 minutos, com regras que
impedem autoengano, e o humano decidindo onde importa.** O modelo de moda e beleza é a prova
de que a fábrica funciona; o valor é a fábrica.

## 1. O problema e a virada (2 min)

- Pedido: prever performance de Shorts por setor, consumível como ferramenta.
- Virada: não "um modelo com agente em volta", e sim **um agente que constrói modelos**
  dentro de regras fixas (alvo, split temporal, baseline, controle, teste uma vez).
- Slide: a tabela de regras fixas (docs/tecnico/01) em 6 linhas.

## 2. O número (2 min)

| setor | canais / Shorts | erro vs média do canal | A vs B | faixa 80% |
|---|---|---|---|---|
| moda-beleza | 153 / 54,9k | −24,4% | 58,9% | 73% |
| saúde | 42 / 9,4k | −23,0% | 57,1% | 83% |
| automotivo | 37 / 15,9k | −19,8% | 58,6% | 81% |
| fitness | 30 / 13,2k | −7,3% | 52% | 83% |

- O que significa: erro típico 2,4× → 1,9×; de dois vídeos do mesmo canal, aponta o melhor
  em ~58%; a faixa de 80% cumpre 73–83%.
- Fitness é o slide honesto: o diagnóstico mostrou setor ruidoso (likes dependem pouco do
  canal), e o framework não inventou acerto onde não há.

## 3. Demo ao vivo ou gravada (5 min)

Ordem sugerida (projeto `moda-beleza`, API em :8000, UI em :5173):

1. **Projetos**: feed, mosaico, insights do setor. "Cada card é um setor; o automotivo foi
   criado ontem em 40 minutos."
2. **Início**: cards (base, modelo ativo "+24% mais preciso que a média do canal", em
   produção, curva de crescimento) e **Próximo passo**. "O agente não adivinha o que fazer:
   o estado do projeto diz."
3. **Analisar vídeo**: subir `data/demo/Carina Araújo - Achei meu look do ano novo 🤍.mp4`,
   canal Carina Araújo, data 2026-10-06, 45 s. Mostrar o card de avaliação (veredito,
   faixas, explicação só com números, o que o Gemini viu, o que o Whisper ouviu, atributos).
   Real: 14,0k, dentro da faixa provável. Depois "Publiquei" com `VC4ZbSIniMw`.
4. **Vídeos analisados**: previsto × real. Mostrar a Katherine Pierce (2,5k previsto, 11,5k
   real, dentro da quase certa): "o gancho explica, e a camada de gancho ainda não entra
   por volume; é o próximo passo."
5. **Modelos**: vista simplificada e o card **Busca do agente** (receitas tentadas, ganho
   real × indistinguível, sem poder estatístico). Trocar o modo para Data Scientist (onda).
6. **Revisão de atributos**: discordâncias primeiro; o humano desempata.
7. **Trace**: linha do tempo; abrir uma otimização.

Com o Claude Code (MCP), um prompt só, gravado antes:
> "O que o projeto automotivo precisa agora? Faz o que for seguro e me explica o resultado
> com os números."
Esperado: `proximo_passo` → `diagnostico` → ações → explicação sem inventar número.

## 4. O que o agente faz de diferente (3 min)

- **Guardrails medidos**: tentativa sem poder estatístico diz quantos vídeos faltam;
  bootstrap pareado separa ganho real de ruído; a trava só promove quem vence no teste e
  reavalia o ativo quando a base muda; troca lateral não vale.
- **Diagnóstico**: setor ruidoso, controle fraco, canais rasos, setores misturados, camadas
  incompletas, alvo alternativo, idade. Foi assim que fitness+saúde virou dois projetos.
- **Operação**: reobservação diária (curva de crescimento: likes estabilizam em ~10 dias),
  acompanhamento previsto × real, rotina.
- **Custo**: tudo grátis (YouTube Data API, Gemini AI Studio, Workers AI, Laya, Whisper,
  SigLIP locais). 46k Shorts por 2,8k unidades de cota.

## 5. Limites e próximos passos (2 min)

- Teto é o dado: A vs B ~58% não sobe com busca; sobe com canais.
- Gancho: 474 ganchos não têm poder estatístico; modo leve (frames + SigLIP) + vizinhos (kNN
  com confiança) escala sem cota. Resultado medido de 22/10 entra aqui.
- Laya: zero-shot é quase aleatório (model card); vale como base para fine-tune, não como
  classificador pronto.
- O que ficou: docs/tecnico/08-proximos-passos.md.

## Material

- README (resultados, demo, mapa do TAPI), docs/avaliacao*.md (um por setor),
  docs/tecnico/ (8 partes), este roteiro.
