# analysis/reconciliation.py
from pathlib import Path
import json
import numpy as np
import pandas as pd

from analysis.normalization import build_key

ROOT = Path.cwd()
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"
FIG_DIR = OUTPUT / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

FACIO_CSV = DATA_PROCESSED / "facio_tratado.csv"
FUNDO_CSV = DATA_PROCESSED / "fundo_tratado.csv"

# parâmetros
EPS_ABS = 0.50
EPS_REL = 0.001

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
    # carregar CSVs tratados
    facio = pd.read_csv(facio_path, parse_dates=['data_referencia','data_cessao','data_vencimento'], dayfirst=False)
    fundo = pd.read_csv(fundo_path, parse_dates=['data_referencia'], dayfirst=False)

    # normalizar e criar key (ajuste parcela_zfill se quiser)
    facio = build_key(facio, parcela_zfill=3)
    fundo = build_key(fundo, parcela_zfill=3)

    # calcular dias e taxas no facio
    facio['dc_cessao'] = (pd.to_datetime(facio['data_vencimento']) - pd.to_datetime(facio['data_cessao'])).dt.days
    facio['t_ref'] = (pd.to_datetime(facio['data_referencia']) - pd.to_datetime(facio['data_cessao'])).dt.days
    facio['i_facio'] = compute_implicit_rate(facio.get('valor_cessao', np.nan).values,
                                             facio.get('valor_nominal', np.nan).values,
                                             facio['dc_cessao'].values)
    facio['valor_presente_calculado'] = compute_vp(facio.get('valor_cessao', np.nan).values,
                                                   facio['i_facio'].values,
                                                   facio['t_ref'].values)

    # merge por key
    fundo_sel = fundo[['key','valor_presente_fundo','valor_nominal','data_referencia','data_cessao','data_vencimento']].copy()
    merged = pd.merge(facio, fundo_sel, on='key', how='outer', indicator=True, suffixes=('_facio','_fundo'))

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
    merged['dias_ate_vencimento'] = (pd.to_datetime(merged['data_vencimento']) - pd.to_datetime(merged['data_referencia'])).dt.days
    mask_stale = (merged['dias_ate_vencimento'] < 0) & (~merged['valor_presente_fundo'].isna())
    merged.loc[mask_stale, 'recon_status'] = merged.loc[mask_stale, 'recon_status'].apply(
        lambda s: 'Potential Stale' if s in ['Only Fundo','Match Divergent','Match Exact'] else s
    )

    # divergencias
    merged['abs_diff'] = (merged['valor_presente_calculado'] - merged['valor_presente_fundo']).abs()
    merged['rel_diff'] = merged['abs_diff'] / merged[['valor_presente_fundo','valor_presente_calculado']].max(axis=1).replace(0, np.nan)

    # taxa implicita do fundo para divergentes
    mask_div = (merged['recon_status']=='Match Divergent') & (~merged['valor_presente_fundo'].isna())
    if mask_div.any():
        merged.loc[mask_div, 'i_fundo'] = compute_implicit_rate(
            merged.loc[mask_div, 'valor_presente_fundo'].values,
            merged.loc[mask_div, 'valor_nominal'].values,
            merged.loc[mask_div, 'dc_cessao'].values
        )
    merged['i_diff'] = merged.get('i_fundo', np.nan) - merged.get('i_facio', np.nan)

    # KPIs
    kpis = {
        'total_rows': int(len(merged)),
        'counts_by_status': merged['recon_status'].value_counts().to_dict(),
        'vp_total_facio': float(merged['valor_presente_calculado'].sum(skipna=True)),
        'vp_total_fundo': float(merged['valor_presente_fundo'].sum(skipna=True)),
        'total_abs_diff': float(merged['abs_diff'].sum(skipna=True))
    }

    # salvar outputs
    merged.to_csv(output_dir / 'conciliation_results.csv', index=False)
    merged.to_csv(output_dir / 'conciliation_results_with_rates.csv', index=False)
    with open(output_dir / 'kpis_summary.json', 'w') as f:
        json.dump(kpis, f, indent=2, default=str)
    merged.sort_values('abs_diff', ascending=False).head(10).to_csv(output_dir / 'top10_divergences.csv', index=False)

    # salvar amostras para investigação
    merged[merged['_merge']=='left_only'].head(50).to_csv(output_dir / 'sample_only_facio.csv', index=False)
    merged[merged['_merge']=='right_only'].head(50).to_csv(output_dir / 'sample_only_fundo.csv', index=False)

    return merged, kpis

if __name__ == "__main__":
    merged, kpis = run_reconciliation()
    print("Conciliação finalizada. KPIs:", kpis)
