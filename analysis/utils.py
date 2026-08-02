# utils.py
"""
Funções utilitárias de leitura, cálculo de VP e classificação de conciliação.

"""
import numpy as np
import pandas as pd



EPS_ABS = 0.01
DATE_COLS = ["data_referencia", "data_cessao", "data_vencimento"]

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



def classify_reconciliation(merge_indicator, vp_facio, vp_fundo, eps_abs=EPS_ABS):
    """Classificação vetorizada (np.select) dos status de reconciliação.

    Usa o indicador `_merge` do outer join — não apenas a nulidade de VP —
    para não confundir "parcela não existe no outro arquivo" com "parcela
    existe mas o VP não pôde ser calculado por dado inválido" (ex.:
    valor_cessao <= 0). As duas situações antes caíam ambas em
    "Missing Both", o que mascarava um problema de qualidade de dado como
    se fosse ausência genuína nos dois arquivos.

    Tolerância só absoluta (ver EPS_ABS) — sem braço relativo, para bater
    exatamente com o critério do notebook final do case.
    """
    vp_facio = np.asarray(vp_facio, dtype=float)
    vp_fundo = np.asarray(vp_fundo, dtype=float)

    diff = np.abs(vp_facio - vp_fundo)
    is_match = diff <= eps_abs

    only_facio = merge_indicator == "left_only"
    only_fundo = merge_indicator == "right_only"
    both_present = merge_indicator == "both"

    vp_facio_invalido = both_present & pd.isna(vp_facio)  # existe na Facio, VP não calculável (dado ruim)

    conditions = [
        only_facio,
        only_fundo,
        vp_facio_invalido,
        both_present & is_match,
        both_present & ~is_match,
    ]
    choices = [
        "Only Facio",
        "Only Fundo",
        "Invalid Facio Data",
        "Match Exact",
        "Match Divergent",
    ]
    return np.select(conditions, choices, default="Unclassified")