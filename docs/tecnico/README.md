# Documentação técnica do Galaxies

Como o framework funciona por dentro, módulo a módulo. Escrita para quem vai manter o
código depois (inclusive quem o escreveu): cada seção diz o que o módulo faz, o que entra,
o que sai, as regras que ele garante e onde ele é usado.

| arquivo | assunto |
|---|---|
| [01-visao-geral.md](01-visao-geral.md) | propósito, arquitetura em camadas, fluxo ponta a ponta, regras fixas, glossário |
| [02-dados.md](02-dados.md) | banco DuckDB por projeto, coleta, camada bruta do gancho, atributos, curva de crescimento, trace |
| [03-modelagem.md](03-modelagem.md) | base, split, âncora, features, LightGBM quantílico, calibração, experimentos, otimização, análise, acompanhamento |
| [04-servicos-e-interfaces.md](04-servicos-e-interfaces.md) | `Framework` (serviços), MCP, API HTTP, CLI, portões humanos, ambiente |
| [05-ui.md](05-ui.md) | console React: telas, estado, estilos, modo, animações |
| [06-operacao.md](06-operacao.md) | setup, rodar, rotina diária, custos e cotas, limites, como estender, testes, problemas comuns |

Convenções do código:

- Português nos nomes (módulos, funções, campos). Comentários e docstrings dizem o **porquê**,
  não o quê.
- Pydantic para todo dado que cruza uma fronteira (serviço → MCP/API/UI). Dataclasses só
  para coisas internas (`Dependencias`, `Job`).
- Um único *seam*: `servicos.Framework`. MCP, API e CLI só traduzem chamadas para ele. Nada de
  lógica de domínio fora do núcleo.
- Dependências externas (YouTube, Gemini, Whisper, SigLIP, LLM, Laya) entram por `portas.py`
  (Protocols). Os testes usam falsos em `tests/fakes.py`.
- Regras de avaliação são constantes em `modelagem.py` e `experimentos.py`. O agente não as
  altera; ele escolhe a **receita**.
