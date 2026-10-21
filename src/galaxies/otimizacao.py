"""Otimização da receita pelo agente: busca na validação, teste usado uma vez só.

Objetivo: melhora do MAE sobre o controle fixo (só metadados, hiperparâmetros padrão) nas
mesmas linhas da validação. Por ser relativo a uma referência fixa nas mesmas linhas, compara
receitas que usam subconjuntos diferentes de vídeos.

Estratégia: avalia as receitas padrão possíveis com os dados do projeto e, depois, faz busca
local sobre a melhor: liga ou desliga uma camada, sorteia um hiperparâmetro, remove o atributo
que mais atrapalha ou troca o extrator. Para quando o orçamento acaba ou depois de `paciencia`
tentativas seguidas sem melhora.
"""

import random

import duckdb
from pydantic import BaseModel

from galaxies import atributos as atrib
from galaxies import experimentos as exps
from galaxies.trace import Execucao

MELHORA_MINIMA = 0.002  # menos que isso é ruído: não conta como melhora
MIN_VALIDACAO = 300  # linhas na validação; abaixo disso não há poder para medir ±1%
CONFIANCA = 0.9  # bootstrap pareado: abaixo disso a melhora é "indistinguível"
EXTRAS = ("historico", "texto", "multimodal", "atributos")


class Tentativa(BaseModel):
    receita: exps.Receita
    origem: str  # de onde veio: receita padrão ou a mutação aplicada
    objetivo: float | None  # melhora sobre o controle na validação (None = não deu para medir)
    ganho: float | None = None
    confianca: float | None = None  # P(modelo bate o controle) na validação
    n_validacao: int = 0
    erro: str = ""


class Otimizacao(BaseModel):
    tentativas: list[Tentativa]
    melhor: exps.Receita | None
    objetivo_validacao: float | None


def disponiveis(banco: duckdb.DuckDBPyConnection) -> tuple[set[str], list[str]]:
    """Camadas com dados no projeto e extratores de atributos com respostas."""
    contar = lambda tabela: banco.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]  # noqa: E731
    camadas = {"historico"}
    if contar("texto_embedding"):
        camadas.add("texto")
    if contar("camada_bruta"):
        camadas.add("multimodal")
    extratores = [e for (e,) in banco.execute("SELECT DISTINCT extrator FROM respostas").fetchall()]
    if extratores:
        camadas.add("atributos")
    return camadas, sorted(extratores)


def otimizar(
    banco: duckdb.DuckDBPyConnection,
    alvo: str,
    definicoes: list[atrib.Atributo],
    ex: Execucao,
    orcamento: int = 16,
    paciencia: int = 6,
    semente: int = 0,
) -> Otimizacao:
    rng = random.Random(semente)
    camadas, extratores = disponiveis(banco)
    cache: dict = {}
    tentativas: list[Tentativa] = []
    vistas: set[str] = set()
    ganhos_attr: dict[str, dict[str, float]] = {}  # receita → ganho por atributo na validação

    def testar(receita: exps.Receita, origem: str) -> Tentativa | None:
        chave = receita.model_dump_json()
        if chave in vistas or len(tentativas) >= orcamento:
            return None
        vistas.add(chave)
        with ex.etapa("tentativa", {"origem": origem, "receita": receita.model_dump()}) as r:
            try:
                _, res, _ = exps.avaliar(
                    banco, alvo, receita, definicoes, em="validacao", cache=cache
                )
                if res.n_teste < MIN_VALIDACAO:
                    precisa = -(-MIN_VALIDACAO * (res.n_treino + res.n_teste) // res.n_teste)
                    t = Tentativa(
                        receita=receita,
                        origem=origem,
                        objetivo=None,
                        n_validacao=res.n_teste,
                        erro=f"sem poder estatístico: {res.n_teste} linhas na validação "
                        f"(mínimo {MIN_VALIDACAO}); precisa de ~{precisa} vídeos com essas "
                        "camadas para medir a diferença",
                    )
                else:
                    t = Tentativa(
                        receita=receita,
                        origem=origem,
                        objetivo=res.melhora_sobre_controle,
                        ganho=res.ganho,
                        confianca=res.confianca_sobre_controle,
                        n_validacao=res.n_teste,
                    )
                tentativas.append(t)
                ganhos_attr[chave] = res.ganho_por_atributo
            except ValueError as erro:
                t = Tentativa(receita=receita, origem=origem, objetivo=None, erro=str(erro))
                tentativas.append(t)
            r["saida"] = t.model_dump(
                include={"objetivo", "ganho", "confianca", "n_validacao", "erro"}
            )
        return t

    for nome, receita in exps.RECEITAS_PADRAO.items():
        if set(receita.camadas) - {"metadados"} <= camadas:
            if "atributos" in receita.camadas and extratores:
                for extrator in extratores:
                    testar(receita.model_copy(update={"extrator": extrator}), f"padrão: {nome}")
            else:
                testar(receita, f"padrão: {nome}")

    sem_melhora = 0
    while len(tentativas) < orcamento and sem_melhora < paciencia:
        melhor = _melhor(tentativas)
        if melhor is None:
            break
        mutante, origem = _mutar(melhor, camadas, extratores, ganhos_attr, rng, definicoes)
        t = testar(mutante, origem)
        if t is None:  # já vista: conta como tentativa sem melhora
            sem_melhora += 1
            continue
        anterior = melhor.objetivo or 0.0
        sem_melhora = 0 if (t.objetivo or -1) > anterior + MELHORA_MINIMA else sem_melhora + 1

    melhor = _melhor(tentativas)
    return Otimizacao(
        tentativas=tentativas,
        melhor=melhor.receita if melhor else None,
        objetivo_validacao=melhor.objetivo if melhor else None,
    )


def _melhor(tentativas: list[Tentativa]) -> Tentativa | None:
    """Maior melhora sobre o controle entre as que têm ganho real (confiança ≥ CONFIANCA);
    sem nenhuma, entre todas. Em empate (dentro do ruído), a receita mais simples."""
    validas = [t for t in tentativas if t.objetivo is not None and (t.ganho or 0) > 0]
    if not validas:
        return None
    reais = [t for t in validas if (t.confianca or 0) >= CONFIANCA]
    validas = reais or validas
    topo = max(t.objetivo for t in validas)
    empatadas = [t for t in validas if t.objetivo >= topo - MELHORA_MINIMA]
    return min(empatadas, key=lambda t: (len(t.receita.camadas), -t.objetivo))


def _mutar(melhor: Tentativa, camadas, extratores, ganhos_attr, rng, definicoes):
    r = melhor.receita
    opcoes = ["camada", "param", "param"]
    if "atributos" in r.camadas:
        opcoes += ["atributo"] + (["extrator"] if len(extratores) > 1 else [])
    escolha = rng.choice(opcoes)

    if escolha == "camada":
        camada = rng.choice(sorted(camadas))
        if camada in r.camadas:
            novas = [c for c in r.camadas if c != camada]
            return r.model_copy(update={"camadas": novas}), f"sem {camada}"
        update = {"camadas": [*r.camadas, camada]}
        if camada == "atributos" and extratores:
            update["extrator"] = rng.choice(extratores)
        return r.model_copy(update=update), f"com {camada}"

    if escolha == "atributo":
        ganhos = ganhos_attr.get(r.model_dump_json(), {})
        atuais = r.atributos or [a.id for a in definicoes]
        candidatos = [a for a in atuais if a in ganhos]
        if len(candidatos) > 2:
            pior = min(candidatos, key=lambda a: ganhos[a])
            restantes = [a for a in atuais if a != pior]
            return r.model_copy(update={"atributos": restantes}), f"sem o atributo {pior}"
        escolha = "param"

    if escolha == "extrator":
        outro = rng.choice([e for e in extratores if e != r.extrator] or extratores)
        return r.model_copy(update={"extrator": outro}), f"extrator {outro}"

    p = r.params.model_dump()
    nome = rng.choice(list(p))
    novo = {
        "num_leaves": lambda: rng.choice([7, 15, 31, 63, 127]),
        "learning_rate": lambda: round(10 ** rng.uniform(-2.2, -0.7), 4),
        "rodadas": lambda: rng.choice([150, 300, 600, 1000]),
        "min_data_in_leaf": lambda: rng.choice([10, 20, 40, 80, 150]),
        "meia_vida_dias": lambda: rng.choice([90, 180, 365, 730, None]),
    }[nome]()
    params = exps.Params(**{**p, nome: novo})
    return r.model_copy(update={"params": params}), f"{nome}={novo}"
