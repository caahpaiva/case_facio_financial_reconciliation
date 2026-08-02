# scripts/validate_and_clean.py
"""
Validação e limpeza dos arquivos de posição (facio e fundo) com mapeamento de fundos.
Leitura: tenta parquet primeiro, cai para CSV.
Saída: data/processed/facio_tratado.parquet, data/processed/fundo_tratado.parquet
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
    

# --------------------------------------------------------------------------
# configuração básica
# ROOT ancorado no arquivo, não no cwd — funciona independente de onde o
# script é chamado (raiz do projeto ou de dentro de scripts/).
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROC_DIR = DATA_DIR / "processed"
OUT_DIR = ROOT / "outputs"
PROC_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FMT = "%(asctime)s %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger = logging.getLogger(__name__)

# fontes de dados
FACIO_SRC_PARQUET = DATA_DIR / "posicao_facio.parquet"
FUNDO_SRC_PARQUET = DATA_DIR / "posicao_fundo.parquet"
FACIO_SRC_CSV = DATA_DIR / "posicao_facio.csv"
FUNDO_SRC_CSV = DATA_DIR / "posicao_fundo.csv"

# saída em Parquet: preserva dtype (datas e floats não voltam como texto no
# próximo script, e não corre o risco de esquecer de re-normalizar a hora).
FACIO_OUT = PROC_DIR / "facio_tratado.parquet"
FUNDO_OUT = PROC_DIR / "fundo_tratado.parquet"

DATE_COLS = ["data_referencia", "data_cessao", "data_vencimento"]
NUMERIC_COLS = ["valor_cessao", "valor_nominal", "valor_presente_fundo", "valor_presente_calculado"]

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
    'valor_presente_calculado': ['valor_presente_calculado', 'vp_calc'],
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


def read_table(parquet_path: Path, csv_path: Path, parse_dates=None, nrows=None) -> pd.DataFrame:
    """Tenta ler parquet, senão CSV. Retorna DataFrame com colunas normalizadas
    e datas convertidas para granularidade de DIA (sem componente de hora).
    """
    if parquet_path.exists():
        logger.info("Lendo parquet: %s", parquet_path)
        try:
            df = pd.read_parquet(parquet_path)
        except Exception as e:
            logger.warning("Falha ao ler parquet (%s). Tentando CSV. Erro: %s", parquet_path, e)
            df = pd.read_csv(csv_path, nrows=nrows)
    elif csv_path.exists():
        logger.info("Lendo CSV: %s", csv_path)
        df = pd.read_csv(csv_path, nrows=nrows)
    else:
        raise FileNotFoundError(f"Nem parquet nem csv encontrados: {parquet_path} / {csv_path}")

    # normalizar colunas iniciais
    df.columns = [str(c).strip() for c in df.columns]
    df = find_and_rename_columns(df)

    # parse de datas + normalização (remove hora).
    # Importante: `data_cessao` costuma carregar timestamp real de transação
    # (ex. 17:20:36), enquanto `data_referencia`/`data_vencimento` vêm à
    # meia-noite. Sem `.dt.normalize()`, uma cessão no mesmo dia da
    # referência mas com hora > 00:00 gera dias corridos NEGATIVOS na
    # subtração de datas, o que quebra silenciosamente a taxa implícita
    # a jusante (potência de base negativa/expoente não inteiro).
    if parse_dates:
        for d in parse_dates:
            if d in df.columns:
                df[d] = pd.to_datetime(df[d], errors='coerce').dt.normalize()

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


def map_fundo_names_to_code(fundo: pd.DataFrame) -> pd.DataFrame:
    """Cria coluna fundo_code com códigos curtos (FIDC3/FIDC4) a partir de nomes longos.

    Loga explicitamente quando uma linha não consegue ser mapeada para um
    código conhecido — isso é justamente o cenário que antes falhava em
    silêncio e quebrava o matching da chave de conciliação.
    """
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

    # fallback: correspondência por substring com keys do mapping
    still_missing = fundo['fundo_code'].isna()
    if still_missing.any():
        for long_name, code in FUNDO_NAME_TO_CODE.items():
            mask = fundo['fundo'].str.contains(re.escape(long_name), case=False, na=False)
            fundo.loc[mask, 'fundo_code'] = code

    # diagnóstico explícito: linhas que não bateram em NENHUM dos 3 métodos
    unmapped_mask = ~fundo['fundo_code'].isin(FUNDO_NAME_TO_CODE.values())
    n_unmapped = int(unmapped_mask.sum())
    if n_unmapped:
        exemplos = fundo.loc[unmapped_mask, 'fundo'].dropna().unique()[:5]
        logger.warning(
            "%d linhas do fundo NÃO mapeadas para FIDC3/FIDC4 — mantendo nome bruto. Exemplos: %s",
            n_unmapped, list(exemplos),
        )

    # se nada encontrado, manter o valor original (para não perder informação)
    fundo['fundo_code'] = fundo['fundo_code'].fillna(fundo['fundo'])
    return fundo


def minimal_clean(df: pd.DataFrame, is_facio=True) -> pd.DataFrame:
    """Aplica limpeza mínima: strip strings, pad parcela, criar key via build_key quando aplicável."""
    # garantir colunas string
    for c in ['id_contrato', 'parcela', 'fundo']:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
        else:
            df[c] = ""

    # parcela: limpar e zfill
    df = normalize_parcela(df, z=3)

    # build_key é opcional/legado: se existir e funcionar, mantemos o efeito
    # colateral que ele possa ter em outras colunas, mas o resultado de
    # `key` em si é sempre recalculado depois por `create_canonical_key`,
    # que é a fonte da verdade. Por isso um erro aqui é logado (não mais
    # engolido em silêncio) mas não interrompe o pipeline.
    try:
        df = build_key(df, parcela_zfill=3)
    except Exception as e:
        logger.debug("build_key não aplicado (opcional/legado): %s", e)

    # datas: normalizar para granularidade de dia
    for d in DATE_COLS:
        if d in df.columns:
            df[d] = pd.to_datetime(df[d], errors='coerce').dt.normalize()

    # numerics
    df = coerce_numeric(df, NUMERIC_COLS)
    return df


def save_diagnostics(df: pd.DataFrame, prefix: str, out_dir: Path = OUT_DIR):
    """Salva amostra head e valores únicos de 'fundo' para diagnóstico."""
    try:
        df.head(200).to_csv(out_dir / f"{prefix}_sample_head.csv", index=False)
    except Exception as e:
        logger.warning("Falha ao salvar amostra de diagnóstico (%s): %s", prefix, e)
    if 'fundo' in df.columns:
        try:
            df[['fundo']].drop_duplicates().to_csv(out_dir / f"{prefix}_unique_fundos.csv", index=False)
        except Exception as e:
            logger.warning("Falha ao salvar fundos únicos (%s): %s", prefix, e)


def create_canonical_key(df: pd.DataFrame) -> pd.DataFrame:
    """Cria a key canônica de conciliação: id_contrato|parcela_z.

    Deliberadamente NÃO inclui fundo_code na chave. `(id_contrato, parcela)`
    já é único nos dois arquivos e o `fundo` reportado bate em 100% das
    linhas presentes nos dois lados — colocar fundo_code dentro da chave
    não ganha poder de matching, só cria um novo modo de falha: se
    `map_fundo_names_to_code` cair no fallback de nome bruto para alguma
    linha, essa parcela deixa de casar mesmo sendo o mesmo contrato,
    virando um falso "Only Facio"/"Only Fundo" sem nenhum aviso.

    A consistência de `fundo_code` entre os dois lados deve ser checada
    DEPOIS do merge (ver `check_fundo_consistency`), não usada como
    condição de join.
    """
    if 'id_contrato' not in df.columns:
        df['id_contrato'] = ""
    df['id_contrato'] = df['id_contrato'].astype(str).str.strip()

    if 'parcela_z' not in df.columns:
        df = normalize_parcela(df, z=3)

    df['key'] = df['id_contrato'].astype(str) + "|" + df['parcela_z'].astype(str)
    return df


def check_fundo_consistency(facio: pd.DataFrame, fundo: pd.DataFrame):
    """Checagem pós-join (não bloqueante): entre as chaves presentes nos dois
    lados, o fundo_code reportado pela Facio bate com o do gestor do fundo?
    """
    merged = facio[['key', 'fundo_code']].merge(
        fundo[['key', 'fundo_code']], on='key', how='inner', suffixes=('_facio', '_fundo')
    )
    mismatch = merged[merged['fundo_code_facio'] != merged['fundo_code_fundo']]
    if len(mismatch):
        logger.warning(
            "%d parcelas com fundo_code divergente entre Facio e Fundo (mesma chave, fundo diferente). "
            "Amostra de keys: %s",
            len(mismatch), mismatch['key'].head(5).tolist(),
        )
    else:
        logger.info("Consistência de fundo_code OK: 0 divergências entre Facio e Fundo nas chaves em comum.")
    return mismatch


def run_data_quality_checks(facio: pd.DataFrame, fundo: pd.DataFrame):
    """Validações de qualidade que efetivamente importam para a conciliação —
    sem elas, problemas de dado viram silenciosamente 'breaks' de negócio.
    """
    logger.info("---- Data quality checks ----")

    dup_facio = facio.duplicated(subset=['id_contrato', 'parcela']).sum()
    dup_fundo = fundo.duplicated(subset=['id_contrato', 'parcela']).sum()
    logger.info("Linhas duplicadas (id_contrato, parcela) — Facio: %d | Fundo: %d", dup_facio, dup_fundo)
    if dup_facio or dup_fundo:
        logger.warning("Existem chaves duplicadas — a conciliação 1:1 pode ficar ambígua.")

    if {'valor_cessao', 'valor_nominal'}.issubset(facio.columns):
        invalid_values = (facio['valor_cessao'] <= 0) | (facio['valor_nominal'] <= 0)
        cessao_ge_nominal = facio['valor_cessao'] >= facio['valor_nominal']
        logger.info(
            "Facio — valor_cessao/valor_nominal <= 0: %d | valor_cessao >= valor_nominal: %d",
            int(invalid_values.sum()), int(cessao_ge_nominal.sum()),
        )

    if {'data_cessao', 'data_vencimento'}.issubset(facio.columns):
        venc_antes_cessao = (facio['data_vencimento'] < facio['data_cessao']).sum()
        logger.info("Facio — data_vencimento anterior à data_cessao: %d", int(venc_antes_cessao))

    if 'valor_presente_fundo' in fundo.columns:
        vp_invalido = (fundo['valor_presente_fundo'] <= 0).sum()
        logger.info("Fundo — valor_presente_fundo <= 0: %d", int(vp_invalido))

    n_unmapped_fundo = (~fundo['fundo_code'].isin(FUNDO_NAME_TO_CODE.values())).sum()
    logger.info("Fundo — linhas com fundo_code fora de FIDC3/FIDC4 (fallback bruto): %d", int(n_unmapped_fundo))

    logger.info("---- Fim dos data quality checks ----")


def main():
    logger.info("Iniciando validate_and_clean (com mapeamento de fundos)")

    # ler facio
    facio = read_table(FACIO_SRC_PARQUET, FACIO_SRC_CSV, parse_dates=DATE_COLS)
    logger.info("Facio lido com shape %s", facio.shape)
    save_diagnostics(facio, "facio_raw")
    facio = minimal_clean(facio, is_facio=True)
    logger.info("Facio tratado com shape %s", facio.shape)

    # ler fundo
    fundo = read_table(FUNDO_SRC_PARQUET, FUNDO_SRC_CSV, parse_dates=DATE_COLS)
    logger.info("Fundo lido com shape %s", fundo.shape)
    save_diagnostics(fundo, "fundo_raw")
    fundo = minimal_clean(fundo, is_facio=False)

    # mapear nomes longos de fundo para códigos curtos (FIDC3/FIDC4)
    fundo = map_fundo_names_to_code(fundo)

    # garantir coluna de código curto no facio (facio já reporta a sigla diretamente)
    if 'fundo' in facio.columns:
        facio['fundo_code'] = facio['fundo'].astype(str).str.strip()
    else:
        facio['fundo_code'] = facio.get('fundo_facio', "").astype(str).str.strip()

    # normalizar parcela e criar key canônica em ambos (SEM fundo_code na chave — ver docstring)
    facio = normalize_parcela(facio, z=3)
    fundo = normalize_parcela(fundo, z=3)
    facio = create_canonical_key(facio)
    fundo = create_canonical_key(fundo)

    # checagens de qualidade — agora reais, não só estruturais
    run_data_quality_checks(facio, fundo)
    check_fundo_consistency(facio, fundo)

    # salvar tratados em Parquet (preserva dtype — datas e floats não voltam
    # como texto no próximo script)
    facio.to_parquet(FACIO_OUT, index=False)
    logger.info("Facio tratado salvo em %s", FACIO_OUT)
    fundo.to_parquet(FUNDO_OUT, index=False)
    logger.info("Fundo tratado salvo em %s", FUNDO_OUT)

    # diagnóstico rápido de chaves
    try:
        keys_f = set(facio['key'].dropna().unique())
        keys_g = set(fundo['key'].dropna().unique())
        inter = len(keys_f & keys_g)
        logger.info("Unique keys - Facio: %d, Fundo: %d, Interseção: %d", len(keys_f), len(keys_g), inter)
        only_facio = facio[~facio['key'].isin(keys_g)].head(200)
        only_fundo = fundo[~fundo['key'].isin(keys_f)].head(200)
        only_facio.to_csv(OUT_DIR / "only_facio_sample.csv", index=False)
        only_fundo.to_csv(OUT_DIR / "only_fundo_sample.csv", index=False)
        logger.info("Amostras only_facio_sample.csv e only_fundo_sample.csv escritas em outputs/")
    except Exception as e:
        logger.warning("Não foi possível calcular interseção de chaves: %s", e)

    # salvar listas únicas de fundos para revisão manual
    try:
        facio[['fundo_code']].drop_duplicates().to_csv(OUT_DIR / "unique_facio_fundos.csv", index=False)
        fundo[['fundo_code']].drop_duplicates().to_csv(OUT_DIR / "unique_fundo_fundos.csv", index=False)
    except Exception as e:
        logger.warning("Não foi possível salvar listas de fundos únicos: %s", e)

    logger.info("validate_and_clean finalizado com sucesso.")


if __name__ == "__main__":
    main()