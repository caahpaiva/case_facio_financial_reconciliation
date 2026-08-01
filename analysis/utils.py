# utils.py
import pandas as pd
import numpy as np
from datetime import datetime

def read_data(facio_path: str, fundo_path: str):
    df_facio = pd.read_parquet(facio_path, parse_dates=['data_referencia','data_cessao','data_vencimento'])
    df_fundo = pd.read_parquet(fundo_path, parse_dates=['data_referencia'])
    return df_facio, df_fundo

def days_between(start, end):
    return (end - start).dt.days

def compute_implicit_rate(vc, vn, dc_cessao):
    # Avoid division by zero or negative days
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = vn / vc
        # If vc <= 0 or ratio <=0, return NaN
        valid = (vc > 0) & (ratio > 0) & (dc_cessao > 0)
        i = np.full_like(vc, np.nan, dtype=float)
        i[valid] = np.power(ratio[valid], 1.0/dc_cessao[valid]) - 1.0
    return i

def compute_vp(vc, i, t):
    # VP = VC * (1 + i)^t
    with np.errstate(invalid='ignore'):
        vp = vc * np.power(1 + i, t)
    return vp

def safe_round(x, ndigits=2):
    return np.round(x, ndigits)

def classify_reconciliation(row, eps_abs=0.5, eps_rel=0.001):
    # eps_abs in R$, eps_rel relative fraction
    vp_facio = row.get('valor_presente_calculado', np.nan)
    vp_fundo = row.get('valor_presente_fundo', np.nan)
    exists_facio = not pd.isna(vp_facio)
    exists_fundo = not pd.isna(vp_fundo)
    if exists_facio and exists_fundo:
        diff = abs(vp_facio - vp_fundo)
        rel = diff / max(abs(vp_fundo), 1e-9)
        if diff <= eps_abs or rel <= eps_rel:
            return 'Match Exact'
        else:
            return 'Match Divergent'
    elif exists_facio and not exists_fundo:
        return 'Only Facio'
    elif exists_fundo and not exists_facio:
        return 'Only Fundo'
    else:
        return 'Missing Both'
