# analysis/reconciliation.py
"""
Conciliação final e robusta.
Entrada esperada: data/processed/facio_tratado.csv, data/processed/fundo_tratado.csv
Saídas: outputs/conciliation_results.csv,
        outputs/conciliation_results_with_rates.csv,
        outputs/kpis_summary.json,
        outputs/top10_divergences.csv,
        outputs/sample_only_facio.csv,
        outputs/sample_only_fundo.csv
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
import unicodedata

# configuração
ROOT = Path.cwd()
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"
FIG_DIR = OUTPUT / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

FACIO_CSV = DATA_PROCESSED / "facio_tratado.csv"
FUNDO_CSV = DATA_PROCESSED / "fundo_tratado.csv"

# parâmetros de tolerância
EPS_ABS = 0.50
EPS_REL = 0.001

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def compute_implicit_rate(vc, vn, dc_cessao):
    vc = np.asarray(vc, dtype=float)
    vn = np.asarray(vn, dtype=float)
    dc = np.asarray(dc_cessao, dtype=float)
    i = np.full_like(vc, np.nan, dtype=float)
    valid = (vc > 0) & (vn > 0) & (dc > 0)
    if valid.any():
        i[valid] = np.power(vn[valid] / vc[valid], 1.0 / dc[valid]) - 1.0
    return i


def compute_vp(vc, i, t):
    vc = np.asarray(vc, dtype=float)
    i = np.asarray(i, dtype=float)
    t = np.asarray(t, dtype=float)
    vp = np.full_like(vc, np.nan, dtype=float)
    valid = (~np.isnan(i)) & (~np.isnan(vc)) & (~np.isnan(t))
    if valid.any():
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


def norm_str(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ")
    return s


def run_reconciliation(facio_path=FACIO_CSV, fundo_path=FUNDO_CSV, output_dir=OUTPUT):
    logging.info("Iniciando conciliação")

    # carregar arquivos tratados como strings (preserva zeros e formatação)
    facio = pd.read_csv(facio_path, dtype=str, keep_default_na=False, na_values=[""])
    fundo = pd.read_csv(fundo_path, dtype=str, keep_default_na=False, na_values=[""])

    logging.info("Shapes lidos - Facio: %s, Fundo: %s", facio.shape, fundo.shape)

    # normalizar key existente
    facio['key'] = facio['key'].astype(str).apply(norm_str)
    fundo['key'] = fundo['key'].astype(str).apply(norm_str)

    # salvar debug
    facio[['id_contrato','parcela','parcela_z','fundo','fundo_code','key']].head(20).to_csv(output_dir / "facio_debug_key.csv", index=False)
    fundo[['id_contrato','parcela','parcela_z','fundo','fundo_code','key']].head(20).to_csv(output_dir / "fundo_debug_key.csv", index=False)

    # converter datas e numerics
    for dt in ['data_referencia','data_cessao','data_vencimento']:
        if dt in facio.columns:
            facio[dt] = pd.to_datetime(facio[dt], errors='coerce')
        if dt in fundo.columns:
            fundo[dt] = pd.to_datetime(fundo[dt], errors='coerce')

    for col in ['valor_cessao','valor_nominal','valor_presente_fundo','valor_presente_calculado']:
        if col in facio.columns:
            facio[col] = pd.to_numeric(facio[col], errors='coerce')
        if col in fundo.columns:
            fundo[col] = pd.to_numeric(fundo[col], errors='coerce')

    # calcular taxa implícita e VP no facio
    if {'valor_cessao','valor_nominal','data_vencimento','data_cessao'}.issubset(facio.columns):
        facio['dc_cessao'] = (facio['data_vencimento'] - facio['data_cessao']).dt.days
        facio['t_ref'] = (facio['data_referencia'] - facio['data_cessao']).dt.days
        facio['i_facio'] = compute_implicit_rate(facio['valor_cessao'].values,
                                                 facio['valor_nominal'].values,
                                                 facio['dc_cessao'].values)
        facio['valor_presente_calculado'] = compute_vp(facio['valor_cessao'].values,
                                                       facio['i_facio'].values,
                                                       facio['t_ref'].values)

    # merge por key
    merged = pd.merge(facio, fundo, on='key', how='outer', indicator=True, suffixes=('_facio', '_fundo'))

    # classificar status
    merged['recon_status'] = merged.apply(
        lambda r: classify_row(r.get('valor_presente_calculado', np.nan),
                               r.get('valor_presente_fundo', np.nan)),
        axis=1
    )

    # divergências
    merged['abs_diff'] = (merged.get('valor_presente_calculado', np.nan) - merged.get('valor_presente_fundo', np.nan)).abs()
    merged['rel_diff'] = merged['abs_diff'] / merged[['valor_presente_fundo','valor_presente_calculado']].max(axis=1).replace(0, np.nan)

    # KPIs
    kpis = {
        'total_rows': int(len(merged)),
        'counts_by_status': merged['recon_status'].value_counts().to_dict(),
        'vp_total_facio': float(merged.get('valor_presente_calculado', pd.Series(dtype=float)).sum(skipna=True)),
        'vp_total_fundo': float(merged.get('valor_presente_fundo', pd.Series(dtype=float)).sum(skipna=True)),
        'total_abs_diff': float(merged['abs_diff'].sum(skipna=True))
    }

    # salvar outputs
    merged.to_csv(output_dir / 'conciliation_results.csv', index=False)
    merged.to_csv(output_dir / 'conciliation_results_with_rates.csv', index=False)
    merged.sort_values('abs_diff', ascending=False).head(10).to_csv(output_dir / 'top10_divergences.csv', index=False)
    with open(output_dir / 'kpis_summary.json', 'w', encoding='utf-8') as fh:
        json.dump(kpis, fh, indent=2, default=str)

    merged[merged['_merge']=='left_only'].head(200).to_csv(output_dir / 'sample_only_facio.csv', index=False)
    merged[merged['_merge']=='right_only'].head(200).to_csv(output_dir / 'sample_only_fundo.csv', index=False)

    logging.info("Conciliação salva em: %s", output_dir)
    logging.info("KPIs: %s", kpis)

    return merged, kpis


if __name__ == "__main__":
    merged_df, summary_kpis = run_reconciliation()
    print("Conciliação finalizada. KPIs:", summary_kpis)
