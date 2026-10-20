"""Orquestra um treino: avaliação por camadas no split temporal + modelo final em toda a base."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from galaxies import atributos as atrib
from galaxies import modelagem as m
from galaxies.trace import Execucao


def treinar(
    banco: duckdb.DuckDBPyConnection,
    alvo: str,
    definicoes: list[atrib.Atributo],
    pasta_modelos: Path,
    ex: Execucao,
) -> m.Avaliacao:
    with ex.etapa("montar_base", {"alvo": alvo}) as r:
        base = m.montar_base(banco, alvo)
        treino, teste, split = m.dividir(base)
        canais = m.estatisticas_dos_canais(treino)
        r["saida"] = split.model_dump()

    setores = sorted(base["setor"].unique())
    x_tr = m.features_de_metadados(treino, canais, setores)
    x_te = m.features_de_metadados(teste, canais, setores)
    y_tr = m.alvo_relativo(treino, canais)

    with ex.etapa("camada_metadados") as r:
        modelos = m.treinar_quantis(x_tr, y_tr)
        baseline = m.medir(m.predicao_baseline(teste, canais), teste)
        pred = m.prever_log(modelos, x_te, teste, canais)
        # Controle: quanto do ganho vem só da idade do vídeo e do tamanho do canal.
        so_idade = ["log_idade_dias", "log_mediana_canal"]
        idade = m.treinar_quantis(x_tr[so_idade], y_tr)
        camadas = {
            "baseline+idade": m.medir(m.prever_log(idade, x_te[so_idade], teste, canais), teste),
            "metadados": m.medir(pred, teste),
        }
        piores, segmentos = m.diagnosticar(pred, teste)
        r["saida"] = {
            "baseline": baseline.model_dump(),
            **{k: v.model_dump() for k, v in camadas.items()},
        }

    avaliacao = m.Avaliacao(
        alvo=alvo,
        split=split,
        baseline=baseline,
        camadas=camadas,
        piores=piores,
        segmentos=segmentos,
        criado_em=m.agora(),
    )
    with ex.etapa("ablacao_multimodal") as r:
        _ablacao(banco, definicoes, treino, teste, x_tr, x_te, y_tr, canais, avaliacao)
        r["saida"] = {k: v.model_dump() for k, v in avaliacao.camadas.items()}

    with ex.etapa("modelo_final") as r:
        r["saida"] = _modelo_final(banco, base, definicoes, alvo, pasta_modelos)
    return avaliacao


def _ablacao(banco, definicoes, treino, teste, x_tr, x_te, y_tr, canais, avaliacao):
    """metadados → +multimodal → +atributos, todos no subconjunto com camada bruta."""
    emb = m.features_multimodais(banco, base_ids := pd.concat([treino, teste])["video_id"])
    if emb is None:
        return
    emb.index = base_ids.index
    tem_emb = emb.notna().all(axis=1)
    tr, te = tem_emb.loc[treino.index], tem_emb.loc[teste.index]
    if tr.sum() < 50 or te.sum() < 10:
        return
    sub_tr, sub_te = treino[tr], teste[te]
    xs_tr, xs_te, ys_tr = x_tr[tr], x_te[te], y_tr[tr]

    avaliacao.baseline_subconjunto = m.medir(m.predicao_baseline(sub_te, canais), sub_te)
    so_meta = m.treinar_quantis(xs_tr, ys_tr)
    avaliacao.camadas["subconjunto:metadados"] = m.medir(
        m.prever_log(so_meta, xs_te, sub_te, canais), sub_te
    )

    pca_tr, pca_te, _ = m.reduzir_embeddings(emb.loc[sub_tr.index], emb.loc[sub_te.index])
    xm_tr, xm_te = xs_tr.join(pca_tr), xs_te.join(pca_te)
    multimodal = m.treinar_quantis(xm_tr, ys_tr)
    avaliacao.camadas["subconjunto:+multimodal"] = m.medir(
        m.prever_log(multimodal, xm_te, sub_te, canais), sub_te
    )

    feats = pd.DataFrame(atrib.features(banco, definicoes))
    if feats.empty:
        return
    feats = feats.set_index("video_id")
    xa_tr = xm_tr.join(feats.reindex(sub_tr["video_id"]).set_axis(sub_tr.index))
    xa_te = xm_te.join(feats.reindex(sub_te["video_id"]).set_axis(sub_te.index))
    completo = m.treinar_quantis(xa_tr, ys_tr)
    pred = m.prever_log(completo, xa_te, sub_te, canais)
    avaliacao.camadas["subconjunto:+atributos"] = m.medir(pred, sub_te)
    avaliacao.ganho_por_atributo = _ganho_por_permutacao(
        completo, xa_te, sub_te, canais, definicoes, m.medir(pred, sub_te).mae
    )


def _ganho_por_permutacao(modelos, x_te, teste, canais, definicoes, mae_base) -> dict[str, float]:
    """Quanto o MAE piora ao embaralhar as colunas de cada atributo (positivo = ajuda)."""
    rng = np.random.default_rng(0)
    ganhos = {}
    for atributo in definicoes:
        colunas = [c for c in x_te.columns if c == atributo.id or c.startswith(f"{atributo.id}=")]
        if not colunas:
            continue
        embaralhado = x_te.copy()
        ordem = rng.permutation(len(x_te))
        embaralhado[colunas] = x_te[colunas].to_numpy()[ordem]
        mae = m.medir(m.prever_log(modelos, embaralhado, teste, canais), teste).mae
        ganhos[atributo.id] = round(mae - mae_base, 5)
    return dict(sorted(ganhos.items(), key=lambda kv: -kv[1]))


def _modelo_final(banco, base, definicoes, alvo, pasta_modelos: Path) -> dict:
    """Treina em toda a base (só metadados por ora) e salva o que a análise (#7) precisa."""
    canais = m.estatisticas_dos_canais(base)
    setores = sorted(base["setor"].unique())
    x = m.features_de_metadados(base, canais, setores)
    modelos = m.treinar_quantis(x, m.alvo_relativo(base, canais))
    meta = {
        "alvo": alvo,
        "colunas": list(x.columns),
        "canais": canais.reset_index().to_dict(orient="records"),
        "setores": setores,
        "n": len(base),
    }
    m.salvar_modelos(pasta_modelos / alvo, modelos, meta)
    return {"n": len(base), "colunas": len(x.columns)}
