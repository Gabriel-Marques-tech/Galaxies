"""Quão estreita é a faixa de 80% do modelo comparada com uma faixa ingênua que cobre os
mesmos 80%? Mede, no teste, a largura mediana (fator q90/q10) das duas."""
import sys
import numpy as np
import duckdb
from galaxies import experimentos as ex, modelagem as m
from galaxies.experimentos import _camadas_extras, _montar_x, _ancora_log, _quantis, _calibrar, alargar, _atributos_da_receita
from galaxies import atributos as atrib

projeto, alvo = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "likes"
banco = duckdb.connect(f"data/projetos/{projeto}/galaxies.duckdb", read_only=True)
ativo = ex.ativo(banco, alvo)
receita = ativo.receita
cache = {}
base = m.montar_base(banco, alvo)
treino, teste, split = m.dividir(base)
setores = sorted(base["setor"].unique())
canais = m.estatisticas_dos_canais(treino)
definicoes = [atrib.Atributo.model_validate(a) for a in atrib.listar(banco)] if hasattr(atrib, "listar") else []
try:
    escolhidos = _atributos_da_receita(receita, definicoes)
except Exception:
    escolhidos = []
extras, tem = _camadas_extras(banco, base, receita, escolhidos, alvo, cache)
tr, te = treino.index[tem.loc[treino.index]], teste.index[tem.loc[teste.index]]
x_meta = m.features_de_metadados(base, canais, setores)
x, _ = _montar_x(x_meta, extras, tr, te)
anc = _ancora_log(base, canais, extras, receita)
y = base["log_y"] - anc
modelos = _quantis(x.loc[tr], y.loc[tr], receita.params, base.loc[tr, "publicado_em"])
ancora = anc.loc[te].to_numpy()
q = {k: b.predict(x.loc[te]) + ancora for k, b in modelos.items()}
k = _calibrar(base, tr, x, y, receita.params)
lo, mid, hi = np.sort(np.column_stack([q[0.1], q[0.5], q[0.9]]), axis=1).T
lo, hi = alargar(lo, mid, hi, k)
real = base.loc[te, "log_y"].to_numpy()
cob_modelo = np.mean((real >= lo) & (real <= hi))
larg_modelo = np.median(hi - lo)

# faixa ingênua: baseline (média do canal) ± c, com c escolhido no TREINO para cobrir 80%
pred_base_tr = m.predicao_baseline(base.loc[tr], canais)
res_tr = base.loc[tr, "log_y"].to_numpy() - pred_base_tr
c = np.quantile(np.abs(res_tr), 0.8)
pred_base_te = m.predicao_baseline(base.loc[te], canais)
cob_ingenua = np.mean(np.abs(real - pred_base_te) <= c)
larg_ingenua = 2 * c
# faixa ingênua ajustada para cobrir exatamente a mesma cobertura do modelo no teste (comparação justa)
c2 = np.quantile(np.abs(real - pred_base_te), cob_modelo)
print(f"{projeto} · {alvo} · modelo ativo {ativo.id} · n teste {len(te)}")
print(f"  modelo : cobertura {cob_modelo:.1%} · largura mediana q90/q10 = {np.exp(larg_modelo):.1f}×")
print(f"  ingênua (média do canal ± c do treino): cobertura {cob_ingenua:.1%} · largura = {np.exp(larg_ingenua):.1f}×")
print(f"  ingênua com a MESMA cobertura do modelo no teste: largura = {np.exp(2*c2):.1f}×")
print(f"  → a faixa do modelo é {np.exp(2*c2)/np.exp(larg_modelo):.1f}× mais estreita para a mesma cobertura")

# ---- "diz se vai viralizar?": chance de passar 3× a mediana do canal, calibrada?
from scipy.stats import norm
med_log = np.log1p(canais.loc[base.loc[te, "canal_id"], "mediana"].to_numpy()) if "mediana" in canais else None
if med_log is None:
    med_log = pred_base_te
limiar_log = med_log + np.log(3)
sigma = (hi - lo) / (2 * norm.ppf(0.9))
p_viral = 1 - norm.cdf((limiar_log - mid) / sigma)
viralizou = real >= limiar_log
from sklearn.metrics import roc_auc_score
auc = roc_auc_score(viralizou, p_viral)
print(f"  viralizar (>3× mediana do canal): taxa real {viralizou.mean():.1%} · AUC da chance prevista {auc:.2f} (acaso 0.50)")
for lo_b, hi_b in [(0, .05), (.05, .1), (.1, .2), (.2, .4), (.4, 1.01)]:
    sel = (p_viral >= lo_b) & (p_viral < hi_b)
    if sel.sum() >= 20:
        print(f"    chance prevista {lo_b:.0%}–{min(hi_b,1):.0%}: {sel.sum():4d} vídeos · viralizaram de fato {viralizou[sel].mean():.1%}")
# acima/abaixo do normal: quando o modelo diz "acima do normal do canal" (q50 ≥ 1.3× mediana), quantos ficaram acima da mediana?
acima = mid >= med_log + np.log(1.3)
abaixo = mid <= med_log + np.log(0.7)
print(f"  'acima do normal' ({acima.sum()} vídeos): {np.mean(real[acima] > med_log[acima]):.0%} ficaram acima da mediana do canal · 'abaixo do normal' ({abaixo.sum()}): {np.mean(real[abaixo] > med_log[abaixo]):.0%} ficaram acima")
