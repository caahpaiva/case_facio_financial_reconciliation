# analysis/normalization.py
import pandas as pd
import re

def normalize_string_series(s: pd.Series) -> pd.Series:
    """Trim, uppercase, collapse spaces and replace multiple whitespace."""
    s = s.fillna("").astype(str)
    s = s.str.strip()
    s = s.str.replace(r"\s+", " ", regex=True)
    s = s.str.upper()
    return s

def normalize_parcela_series(s: pd.Series, zfill: int = 0) -> pd.Series:
    """Pad parcela as string; if numeric-like convert to int then to string."""
    s = s.fillna("").astype(str).str.strip()
    # remove decimal .0 if present
    s = s.str.replace(r"\.0+$", "", regex=True)
    # keep only digits
    s = s.str.replace(r"[^\d]", "", regex=True)
    if zfill > 0:
        s = s.str.zfill(zfill)
    return s

def build_key(df: pd.DataFrame,
              id_col: str = "id_contrato",
              parcela_col: str = "parcela",
              fundo_col: str = "fundo",
              parcela_zfill: int = 0) -> pd.DataFrame:
    """
    Normaliza colunas e cria coluna 'key' no formato:
    ID_CONTRATO|PARCELA|FUNDO
    Retorna o DataFrame com a coluna 'key' adicionada.
    """
    df = df.copy()
    # garantir colunas existam
    for c in (id_col, parcela_col, fundo_col):
        if c not in df.columns:
            df[c] = ""
    # normalizações
    df[id_col] = normalize_string_series(df[id_col])
    df[parcela_col] = normalize_parcela_series(df[parcela_col], zfill=parcela_zfill)
    df[fundo_col] = normalize_string_series(df[fundo_col])
    # opcional: mapear nomes longos de fundo para códigos (adicione mapping se necessário)
    # exemplo: mapping = {"FACIO 3 FUNDO...": "FIDC3"}
    # df[fundo_col] = df[fundo_col].replace(mapping)
    # construir key
    df["key"] = df[id_col].astype(str) + "|" + df[parcela_col].astype(str) + "|" + df[fundo_col].astype(str)
    # tratar chaves vazias
    df["key"] = df["key"].str.replace(r"^\|+\|+$", "", regex=True)
    return df
