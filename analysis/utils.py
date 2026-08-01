# utils.py
"""
Funções utilitárias de leitura, cálculo de VP e classificação de conciliação.

"""
import numpy as np
import pandas as pd

DATE_COLS = ["data_referencia", "data_cessao", "data_vencimento"]

EPS_ABS = 0.01


def read_data(facio_path: str, fundo_path: str):
    """Lê os parquets tratados e normaliza as colunas de data para
    granularidade de dia (remove hora).
    """
    df_facio = pd.read_parquet(facio_path)
    df_fundo = pd.read_parquet(fundo_path)

    for df in (df_facio, df_fundo):
        for col in DATE_COLS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.normalize()

    return df_facio, df_fundo


def days_between(start, end):
    """Dias corridos entre duas colunas de data, normalizando antes de
    subtrair.
    """
    return (end.dt.normalize() - start.dt.normalize()).dt.days


def compute_implicit_rate(vc, vn, dc_cessao):
    """Taxa diária implícita: i = (VN/VC)^(1/dc_cessao) - 1.

    Retorna NaN (em vez de erro) quando vc<=0, vn<=0 ou dc_cessao<=0 —
    esses casos indicam dado inválido, não devem derrubar o pipeline.
    """
    vc = np.asarray(vc, dtype=float)
    vn = np.asarray(vn, dtype=float)
    dc_cessao = np.asarray(dc_cessao, dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = vn / vc
        valid = (vc > 0) & (ratio > 0) & (dc_cessao > 0)
        i = np.full_like(vc, np.nan, dtype=float)
        i[valid] = np.power(ratio[valid], 1.0 / dc_cessao[valid]) - 1.0
    return i


def compute_vp(vc, i, t, dc_cessao):
    """VP = VC * (1+i)^t, capitalizado apenas até o vencimento.
    """
    vc = np.asarray(vc, dtype=float)
    i = np.asarray(i, dtype=float)
    t = np.asarray(t, dtype=float)
    dc_cessao = np.asarray(dc_cessao, dtype=float)

    t_capado = np.where(np.isnan(t) | np.isnan(dc_cessao), t, np.minimum(t, dc_cessao))

    with np.errstate(invalid="ignore"):
        vp = vc * np.power(1 + i, t_capado)
    return vp


def safe_round(x, ndigits=2):
    return np.round(x, ndigits)


def classify_reconciliation(row, eps_abs=EPS_ABS):
    """Classifica uma linha (facio x fundo já mergeados) em status de conciliação.
    """
    vp_facio = row.get("valor_presente_calculado", np.nan)
    vp_fundo = row.get("valor_presente_fundo", np.nan)
    merge_flag = row.get("_merge", None)

    exists_facio = merge_flag in ("both", "left_only") if merge_flag is not None else not pd.isna(vp_facio)
    exists_fundo = merge_flag in ("both", "right_only") if merge_flag is not None else not pd.isna(vp_fundo)

    if exists_facio and exists_fundo:
        if pd.isna(vp_facio):
            # parcela existe nos dois arquivos, mas o VP da Facio não pôde
            # ser calculado (dado de entrada inválido) — não é a mesma
            # coisa que "os valores batem" nem que "a parcela não existe".
            return "Invalid Facio Data"
        diff = abs(vp_facio - vp_fundo)
        return "Match Exact" if diff <= eps_abs else "Match Divergent"
    elif exists_facio and not exists_fundo:
        return "Only Facio"
    elif exists_fundo and not exists_facio:
        return "Only Fundo"
    else:
        return "Missing Both"