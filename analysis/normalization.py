# analysis/normalization.py


import pandas as pd


def normalize_string_series(series: pd.Series) -> pd.Series:
    """
    Normaliza uma coluna de texto.

    - substitui NaN por string vazia
    - remove espaços nas extremidades
    - reduz múltiplos espaços para um único
    - converte para caixa alta
    """

    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )


def normalize_parcela_series(series: pd.Series, zfill: int = 3) -> pd.Series:
    """
    Normaliza o número da parcela.

    Exemplos:
        1      -> 001
        01     -> 001
        1.0    -> 001
        '001'  -> 001
    """

    parcela = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0+$", "", regex=True)
        .str.replace(r"[^\d]", "", regex=True)
    )

    return parcela.str.zfill(zfill)

def normalize_key(series):
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKC")
        .str.replace("\u00A0", " ", regex=False)
        .str.strip()
    )