# analysis/reconciliation.py
"""
Reconciliation module
Entrada: data/processed/facio_tratado.csv, data/processed/fundo_tratado.csv
Saídas: outputs/conciliation_results.csv, outputs/conciliation_results_with_rates.csv,
        outputs/kpis_summary.json, outputs/top10_divergences.csv, outputs/figures/*.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import json
import subprocess
from pathlib import Path

# Executa o script de tratativa antes da conciliação
script = Path(__file__).parents[1] / "scripts" / "validate_and_clean.py"
subprocess.run(["python", str(script)], check=True)


# Config
ROOT = Path.cwd()
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"
FIG_DIR = OUTPUT / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)




FACIO_CSV = DATA_PROCESSED / "facio_tratado.csv"
FUNDO_CSV = DATA_PROCESSED / "fundo_tratado.csv"

# Parâmetros
EPS_ABS = 0.50
EPS_REL = 0.001
PALETTE = {'primary':'#0B3D91','teal':'#00A6A6','muted':'#6B7280','accent':'#F59E0B'}





# Funções financeiras
def compute_implicit_rate(vc, vn, dc_cessao):
    vc = np.asarray(vc, dtype=float)
    vn = np.asarray(vn, dtype=float)
    dc = np.asarray(dc_cessao, dtype=float)
    i = np.full_like(vc, np.nan, dtype=float)
    valid = (vc > 0) & (vn > 0) & (dc > 0)
    i[valid] = np.power(vn[valid] / vc[valid], 1.0 / dc[valid]) - 1.0
    return i

def compute_vp(vc, i, t):
    vc = np.asarray(vc, dtype=float)
    i = np.asarray(i, dtype=float)
    t = np.asarray(t, dtype=float)
    vp = np.full_like(vc, np.nan, dtype=float)
    valid = (~np.isnan(i)) & (~np.isnan(vc)) & (~np.isnan(t))
    vp[valid] = vc[valid] * np.power(1 + i[valid], t[valid])
    return vp

def classify_row(vp_facio, vp_fundo, eps_abs=EPS_ABS, eps_rel=EPS_REL):
    if pd.isna(vp_facio) and pd.isna(vp_fundo):
        return "Missing Both"
    if pd.isna(vp_facio) and not pd.isna(vp_fundo):
        return "Only Fundo"
    if not pd.isna(vp_facio) and pd.isna(vp_fundo):
        return "Only Facio"
    diff = abs(vp_facio - vp_fundo)
    rel = diff / max(abs(vp_fundo), 1e-9)
    if (diff <= eps_abs) or (rel <= eps_rel):
        return "Match Exact"
    return "Match Divergent"

def run_reconciliation(facio_path=FACIO_CSV, fundo_path=FUNDO_CSV, output_dir=OUTPUT):
    facio = pd.read_csv(facio_path, parse_dates=['data_referencia','data_cessao','data_vencimento'])
    fundo = pd.read_csv(fundo_path, parse_dates=['data_referencia'])
    # dias
    facio['dc_cessao'] = (facio['data_vencimento'] - facio['data_cessao']).dt.days
    facio['t_ref'] = (facio['data_referencia'] - facio['data_cessao']).dt.days
    # taxas e VP
    facio['i_facio'] = compute_implicit_rate(facio['valor_cessao'].values,
                                             facio['valor_nominal'].values,
                                             facio['dc_cessao'].values)
    facio['valor_presente_calculado'] = compute_vp(facio['valor_cessao'].values,
                                                   facio['i_facio'].values,
                                                   facio['t_ref'].values)
    # merge
    key = ['id_contrato','parcela','fundo']
    fundo_sel = fundo[['id_contrato','parcela','fundo','valor_presente_fundo']].copy()
    merged = pd.merge(facio, fundo_sel, on=key, how='outer', indicator=True, suffixes=('_facio','_fundo'))
    # garantir colunas
    for col in ['valor_presente_calculado','valor_presente_fundo','valor_nominal','valor_cessao','data_referencia','data_cessao','data_vencimento']:
        if col not in merged.columns:
            merged[col] = np.nan
    # classificar
    merged['recon_status'] = merged.apply(
        lambda r: classify_row(r.get('valor_presente_calculado', np.nan),
                               r.get('valor_presente_fundo', np.nan)),
        axis=1
    )
    # potential stale
    merged['dias_ate_vencimento'] = (merged['data_vencimento'] - merged['data_referencia']).dt.days
    mask_stale = (merged['dias_ate_vencimento'] < 0) & (~merged['valor_presente_fundo'].isna())
    merged.loc[mask_stale, 'recon_status'] = merged.loc[mask_stale, 'recon_status'].apply(
        lambda s: 'Potential Stale' if s in ['Only Fundo','Match Divergent','Match Exact'] else s
    )
    # divergencias
    merged['abs_diff'] = (merged['valor_presente_calculado'] - merged['valor_presente_fundo']).abs()
    merged['rel_diff'] = merged['abs_diff'] / merged[['valor_presente_fundo','valor_presente_calculado']].max(axis=1).replace(0, np.nan)
    # taxa implicita do fundo para divergentes
    mask_div = (merged['recon_status']=='Match Divergent') & (~merged['valor_presente_fundo'].isna())
    merged.loc[mask_div, 'i_fundo'] = compute_implicit_rate(
        merged.loc[mask_div, 'valor_presente_fundo'].values,
        merged.loc[mask_div, 'valor_nominal'].values,
        merged.loc[mask_div, 'dc_cessao'].values
    )
    merged['i_diff'] = merged['i_fundo'] - merged['i_facio']
    # KPIs
    kpis = {
        'total_rows': int(len(merged)),
        'counts_by_status': merged['recon_status'].value_counts().to_dict(),
        'vp_total_facio': float(merged['valor_presente_calculado'].sum(skipna=True)),
        'vp_total_fundo': float(merged['valor_presente_fundo'].sum(skipna=True)),
        'total_abs_diff': float(merged['abs_diff'].sum(skipna=True))
    }
    # salvar
    merged.to_csv(output_dir / 'conciliation_results.csv', index=False)
    merged.to_csv(output_dir / 'conciliation_results_with_rates.csv', index=False)
    with open(output_dir / 'kpis_summary.json', 'w') as f:
        json.dump(kpis, f, indent=2, default=str)
    merged.sort_values('abs_diff', ascending=False).head(10).to_csv(output_dir / 'top10_divergences.csv', index=False)
    return merged, kpis

# Visualizações simples
def plot_vp_by_status(merged, fig_path):
    sns.set_style('whitegrid')
    plt.figure(figsize=(8,5))
    status_vp = merged.groupby('recon_status')['valor_presente_calculado'].sum().sort_values(ascending=False)
    colors = [PALETTE['primary'] if s=='Match Exact' else PALETTE['teal'] for s in status_vp.index]
    status_vp.plot(kind='bar', color=colors)
    plt.title('VP total por status')
    plt.ylabel('Valor Presente (R$)')
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150)
    plt.close()

def plot_divergence_distribution(merged, fig_path):
    plt.figure(figsize=(8,5))
    sns.histplot(merged['abs_diff'].dropna(), bins=80, color=PALETTE['primary'])
    plt.title('Distribuição das divergências absolutas (R$)')
    plt.xlabel('Diferença absoluta (R$)')
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150)
    plt.close()

if __name__ == "__main__":
    merged, kpis = run_reconciliation()
    plot_vp_by_status(merged, FIG_DIR / 'vp_by_status.png')
    plot_divergence_distribution(merged, FIG_DIR / 'divergence_distribution.png')
    print("Conciliação finalizada. KPIs:", kpis)
