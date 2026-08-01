# scripts/validate_and_clean.py
"""
Validação e limpeza dos arquivos de posição (facio e fundo) com mapeamento de fundos.
Leitura: tenta parquet primeiro, cai para CSV.
Saída: data/processed/facio_tratado.csv, data/processed/fundo_tratado.csv
Gera também arquivos de diagnóstico em outputs/.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import logging
import sys
import re

# tentar importar build_key do pacote analysis (garanta analysis/__init__.py existe)
try:
    from analysis.normalization import build_key
except Exception:
    # ajustar sys.path para raiz do projeto e tentar novamente
    p = Path(__file__).resolve().parents[1]
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    from analysis.normalization import build_key

# configuração básica
ROOT = Path.cwd()
DATA_DIR = ROOT / "data"
PROC_DIR = DATA_DIR / "processed"
OUT_DIR = ROOT / "outputs"
PROC_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FMT = "%(asctime)s %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)

# fontes de dados
FACIO_SRC_PARQUET = DATA_DIR / "posicao_facio.parquet"
FUNDO_SRC_PARQUET = DATA_DIR / "posicao_fundo.parquet"
FACIO_SRC_CSV = DATA_DIR / "posicao_facio.csv"
FUNDO_SRC_CSV = DATA_DIR / "posicao_fundo.csv"

FACIO_OUT = PROC_DIR / "facio_tratado.csv"
FUNDO_OUT = PROC_DIR / "fundo_tratado.csv"

# mapeamento conhecido de nomes longos para códigos curtos
FUNDO_NAME_TO_CODE = {
    "FACIO 3 FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS FINANCEIROS DE RESPONSABILIDADE LIMITADA": "FIDC3",
    "FACIO 4 FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS FINANCEIROS DE RESPONSABILIDADE LIMITADA": "FIDC4",
}

# colunas canônicas (variações comuns)
CANONICAL_COLS = {
    'id_contrato': ['id_contrato', 'contract_id', 'contrato'],
    'parcela': ['parcela', 'installment', 'parc'],
    'fundo': ['fundo', 'fund', 'nome_fundo'],
    'data_referencia': ['data_referencia', 'data_ref', 'reference_date'],
    'data_cessao': ['data_cessao', 'cessao_date'],
    'data_vencimento': ['data_vencimento', 'vencimento', 'due_date'],
    'valor_cessao': ['valor_cessao', 'vc', 'valor_cess'],
    'valor_nominal': ['valor_nominal', 'vn', 'valor_nom'],
    'valor_presente_fundo': ['valor_presente_fundo', 'vp_fundo', 'valor_presente'],
    'valor_presente_calculado': ['valor_presente_calculado', 'vp_calc']
}

def find_and_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mapeia colunas alternativas para nomes canônicos definidos em CANONICAL_COLS."""
    cols = {c: c for c in df.columns}
    lower_map = {c.lower().strip(): c for c in df.columns}
    for canon, variants in CANONICAL_COLS.items():
        for v in variants:
            if v.lower() in lower_map:
                cols[lower_map[v.lower()]] = canon
                break
    df = df.rename(columns=cols)
    return df

def read_table(parquet_path: Path, csv_path: Path, parse_dates=None, nrows=None):
    """Tenta ler parquet, senão CSV. Retorna DataFrame com colunas normalizadas."""
    if parquet_path.exists():
        logging.info("Lendo parquet: %s", parquet_path)
        try:
            df = pd.read_parquet(parquet_path)
        except Exception as e:
            logging.warning("Falha ao ler parquet (%s). Tentando CSV. Erro: %s", parquet_path, e)
            df = pd.read_csv(csv_path, nrows=nrows)
    elif csv_path.exists():
        logging.info("Lendo CSV: %s", csv_path)
        df = pd.read_csv(csv_path, nrows=nrows)
    else:
        raise FileNotFoundError(f"Nem parquet nem csv encontrados: {parquet_path} / {csv_path}")
    # normalizar colunas iniciais
    df.columns = [str(c).strip() for c in df.columns]
    df = find_and_rename_columns(df)
    # parse de datas se existirem
    if parse_dates:
        for d in parse_dates:
            if d in df.columns:
                df[d] = pd.to_datetime(df[d], errors='coerce')
    return df

def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def normalize_parcela(df: pd.DataFrame, z=3):
    """Limpa e zfill da parcela."""
    if 'parcela' not in df.columns:
        df['parcela'] = ""
    df['parcela'] = df['parcela'].astype(str).fillna("").str.strip()
    # remover .0 e caracteres não numéricos
    df['parcela'] = df['parcela'].str.replace(r"\.0+$", "", regex=True).str.replace(r"[^\d]", "", regex=True)
    df['parcela_z'] = df['parcela'].apply(lambda x: x.zfill(z) if x != "" else "")
    return df

def map_fundo_names_to_code(fundo: pd.DataFrame):
    """Cria coluna fundo_code com códigos curtos (FIDC3/FIDC4) a partir de nomes longos."""
    if 'fundo' not in fundo.columns:
        fundo['fundo'] = ""
    fundo['fundo'] = fundo['fundo'].astype(str).fillna("").str.strip()
    # mapear nomes exatos
    fundo['fundo_code'] = fundo['fundo'].map(FUNDO_NAME_TO_CODE)
    # tentar extrair código curto dentro do texto (ex.: FIDC3)
    missing_mask = fundo['fundo_code'].isna()
    if missing_mask.any():
        extracted = fundo.loc[missing_mask, 'fundo'].str.extract(r'(FIDC\d+)', expand=False)
        fundo.loc[missing_mask, 'fundo_code'] = extracted.str.upper()
    # fallback: se ainda não mapeado, tentar correspondência por substring com keys do mapping
    still_missing = fundo['fundo_code'].isna()
    if still_missing.any():
        for long_name, code in FUNDO_NAME_TO_CODE.items():
            mask = fundo['fundo'].str.contains(re.escape(long_name), case=False, na=False)
            fundo.loc[mask, 'fundo_code'] = code
    # se nada encontrado, manter o valor original (para não perder informação)
    fundo['fundo_code'] = fundo['fundo_code'].fillna(fundo['fundo'])
    return fundo

def minimal_clean(df: pd.DataFrame, is_facio=True):
    """Aplica limpeza mínima: strip strings, pad parcela, criar key via build_key quando aplicável."""
    # garantir colunas string
    for c in ['id_contrato','parcela','fundo']:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
        else:
            df[c] = ""
    # parcela: limpar e zfill
    df = normalize_parcela(df, z=3)
    # aplicar build_key se existir e for compatível (mantemos, mas vamos recriar key canônica depois)
    try:
        df = build_key(df, parcela_zfill=3)
    except Exception:
        # build_key pode não existir ou ter comportamento diferente; ignorar
        pass
    # datas: tentar converter se existirem
    for d in ['data_referencia','data_cessao','data_vencimento']:
        if d in df.columns:
            df[d] = pd.to_datetime(df[d], errors='coerce')
    # numerics
    df = coerce_numeric(df, ['valor_cessao','valor_nominal','valor_presente_fundo','valor_presente_calculado'])
    return df

def save_diagnostics(df, prefix, out_dir=OUT_DIR):
    """Salva amostra head e valores únicos de 'fundo' para diagnóstico."""
    try:
        df.head(200).to_csv(out_dir / f"{prefix}_sample_head.csv", index=False)
    except Exception:
        pass
    if 'fundo' in df.columns:
        df[['fundo']].drop_duplicates().to_csv(out_dir / f"{prefix}_unique_fundos.csv", index=False)

def create_canonical_key(df: pd.DataFrame, fundo_code_col='fundo_code'):
    """Cria key canônica: id_contrato|parcela_z|fundo_code"""
    # garantir id_contrato
    if 'id_contrato' not in df.columns:
        df['id_contrato'] = ""
    df['id_contrato'] = df['id_contrato'].astype(str).str.strip()
    # garantir parcela_z
    if 'parcela_z' not in df.columns:
        df = normalize_parcela(df, z=3)
    # garantir fundo_code_col
    if fundo_code_col not in df.columns:
        df[fundo_code_col] = df.get('fundo', "").astype(str).str.strip()
    df[fundo_code_col] = df[fundo_code_col].astype(str).fillna("").str.strip()
    df['key'] = df['id_contrato'].astype(str) + "|" + df['parcela_z'].astype(str) + "|" + df[fundo_code_col].astype(str)
    # limpar chaves vazias
    df['key'] = df['key'].str.replace(r'^\|+\|*', '', regex=True)
    return df

def main():
    logging.info("Iniciando validate_and_clean (com mapeamento de fundos)")

    # ler facio
    facio = read_table(FACIO_SRC_PARQUET, FACIO_SRC_CSV, parse_dates=['data_referencia','data_cessao','data_vencimento'])
    logging.info("Facio lido com shape %s", facio.shape)
    save_diagnostics(facio, "facio_raw")
    facio = minimal_clean(facio, is_facio=True)
    logging.info("Facio tratado com shape %s", facio.shape)

    # ler fundo
    fundo = read_table(FUNDO_SRC_PARQUET, FUNDO_SRC_CSV, parse_dates=['data_referencia','data_cessao','data_vencimento'])
    logging.info("Fundo lido com shape %s", fundo.shape)
    save_diagnostics(fundo, "fundo_raw")
    fundo = minimal_clean(fundo, is_facio=False)

    # mapear nomes longos de fundo para códigos curtos (FIDC3/FIDC4)
    fundo = map_fundo_names_to_code(fundo)

    # garantir coluna de código curto no facio (se facio já tem códigos curtos em 'fundo', usar)
    if 'fundo' in facio.columns:
        facio['fundo_code'] = facio['fundo'].astype(str).str.strip()
    else:
        facio['fundo_code'] = facio.get('fundo_facio', "").astype(str).str.strip()

    # normalizar parcela e criar key canônica em ambos
    facio = normalize_parcela(facio, z=3)
    fundo = normalize_parcela(fundo, z=3)

    facio = create_canonical_key(facio, fundo_code_col='fundo_code')
    fundo = create_canonical_key(fundo, fundo_code_col='fundo_code')

    # salvar tratados
    facio.to_csv(FACIO_OUT, index=False)
    logging.info("Facio tratado salvo em %s", FACIO_OUT)
    fundo.to_csv(FUNDO_OUT, index=False)
    logging.info("Fundo tratado salvo em %s", FUNDO_OUT)

    # diagnóstico rápido de chaves
    try:
        keys_f = set(facio['key'].dropna().unique())
        keys_g = set(fundo['key'].dropna().unique())
        inter = len(keys_f & keys_g)
        logging.info("Unique keys - Facio: %d, Fundo: %d, Interseção: %d", len(keys_f), len(keys_g), inter)
        only_facio = facio[~facio['key'].isin(keys_g)].head(200)
        only_fundo = fundo[~fundo['key'].isin(keys_f)].head(200)
        only_facio.to_csv(OUT_DIR / "only_facio_sample.csv", index=False)
        only_fundo.to_csv(OUT_DIR / "only_fundo_sample.csv", index=False)
        logging.info("Amostras only_facio_sample.csv e only_fundo_sample.csv escritas em outputs/")
    except Exception as e:
        logging.warning("Não foi possível calcular interseção de chaves: %s", e)

    # salvar listas únicas de fundos para revisão manual
    try:
        facio[['fundo_code']].drop_duplicates().to_csv(OUT_DIR / "unique_facio_fundos.csv", index=False)
        fundo[['fundo_code']].drop_duplicates().to_csv(OUT_DIR / "unique_fundo_fundos.csv", index=False)
    except Exception:
        pass

    logging.info("validate_and_clean finalizado com sucesso.")

if __name__ == "__main__":
    main()
