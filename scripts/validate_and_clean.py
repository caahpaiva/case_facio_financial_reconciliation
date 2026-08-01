"""
===============================================================================
- Configuração
- Leitura dos dados
- Validação
- Tratamento inicial
===============================================================================
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

# =============================================================================
# DIRETÓRIOS
# =============================================================================

ROOT = Path.cwd()


DATA = ROOT / "data" 
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LEITURA
# =============================================================================

print("=" * 80)
print("LENDO ARQUIVOS")
print("=" * 80)


facio = pd.read_parquet(
    DATA / "posicao_facio.parquet"
)

fundo = pd.read_parquet(
    DATA / "posicao_fundo.parquet"
)

print(f"Facio : {facio.shape}")
print(f"Fundo : {fundo.shape}")

# =============================================================================
# PADRONIZAÇÃO DOS NOMES DAS COLUNAS
# =============================================================================

facio.columns = (
    facio.columns
    .str.lower()
    .str.strip()
    .str.replace(" ", "_")
)

fundo.columns = (
    fundo.columns
    .str.lower()
    .str.strip()
    .str.replace(" ", "_")
)

# =============================================================================
# CONVERSÃO DE DATAS
# =============================================================================

date_columns_facio = [
    "data_referencia",
    "data_cessao",
    "data_vencimento"
]

for c in date_columns_facio:

    facio[c] = pd.to_datetime(
        facio[c],
        errors="coerce"
    )

fundo["data_referencia"] = pd.to_datetime(
    fundo["data_referencia"],
    errors="coerce"
)

# =============================================================================
# CONVERSÃO DE CAMPOS NUMÉRICOS
# =============================================================================

numeric_columns_facio = [
    "valor_cessao",
    "valor_nominal"
]

for c in numeric_columns_facio:

    facio[c] = pd.to_numeric(
        facio[c],
        errors="coerce"
    )

fundo["valor_presente_fundo"] = pd.to_numeric(
    fundo["valor_presente_fundo"],
    errors="coerce"
)

# =============================================================================
# RELATÓRIO DE QUALIDADE
# =============================================================================

def data_quality(df, nome):

    print("\n")
    print("=" * 80)
    print(nome.upper())
    print("=" * 80)

    print("\nDimensão")
    print(df.shape)

    print("\nTipos")
    print(df.dtypes)

    print("\nValores nulos")

    nulos = (
        df.isna()
        .sum()
        .sort_values(ascending=False)
    )

    print(nulos)

    print("\nDuplicados")

    print(df.duplicated().sum())

    print("\nMemória")

    print(
        round(
            df.memory_usage(deep=True).sum() /
            1024 /
            1024,
            2
        ),
        "MB"
    )

data_quality(facio, "Facio")
data_quality(fundo, "Fundo")

# =============================================================================
# DUPLICIDADE DE CHAVE
# =============================================================================

print("\n")
print("=" * 80)
print("VALIDANDO CHAVE")
print("=" * 80)

chave = [
    "id_contrato",
    "parcela"
]

dup_facio = facio.duplicated(
    subset=chave,
    keep=False
)

dup_fundo = fundo.duplicated(
    subset=chave,
    keep=False
)

print(
    "Duplicidade Facio:",
    dup_facio.sum()
)

print(
    "Duplicidade Fundo:",
    dup_fundo.sum()
)

# =============================================================================
# VALIDAÇÃO DE DOMÍNIOS
# =============================================================================

print("\nProdutos")

print(
    facio["produto"]
    .value_counts(dropna=False)
)

print("\nFundos")

print(
    facio["fundo"]
    .value_counts(dropna=False)
)

print(
    fundo["fundo"]
    .value_counts(dropna=False)
)

# =============================================================================
# VALORES NEGATIVOS
# =============================================================================

print("\n")
print("=" * 80)
print("VALIDANDO VALORES NEGATIVOS")
print("=" * 80)

for coluna in [
    "valor_cessao",
    "valor_nominal"
]:

    negativos = (facio[coluna] < 0).sum()

    print(coluna, negativos)

negativos = (
    fundo["valor_presente_fundo"] < 0
).sum()

print(
    "valor_presente_fundo",
    negativos
)

# =============================================================================
# VALIDAÇÃO DAS DATAS
# =============================================================================

print("\n")
print("=" * 80)
print("VALIDANDO DATAS")
print("=" * 80)

facio["dias_ate_vencimento"] = (
    facio["data_vencimento"]
    -
    facio["data_referencia"]
).dt.days

facio["dias_cessao"] = (
    facio["data_vencimento"]
    -
    facio["data_cessao"]
).dt.days

print(
    "Parcelas vencidas:",
    (facio["dias_ate_vencimento"] < 0).sum()
)

print(
    "Dias cessão <= 0:",
    (facio["dias_cessao"] <= 0).sum()
)

print(
    "Data cessão maior que vencimento:",
    (
        facio["data_cessao"] >
        facio["data_vencimento"]
    ).sum()
)

# =============================================================================
# VALORES FINANCEIROS
# =============================================================================

print("\n")
print("=" * 80)
print("VALIDANDO VALORES")
print("=" * 80)

print(
    "Valor Nominal menor que Valor de Cessão:"
)

print(
    (
        facio["valor_nominal"] <
        facio["valor_cessao"]
    ).sum()
)

# =============================================================================
# REMOÇÃO DE ESPAÇOS
# =============================================================================

for coluna in [
    "produto",
    "fundo",
    "id_contrato"
]:

    facio[coluna] = (
        facio[coluna]
        .astype(str)
        .str.strip()
    )

for coluna in [
    "fundo",
    "id_contrato"
]:

    fundo[coluna] = (
        fundo[coluna]
        .astype(str)
        .str.strip()
    )

# =============================================================================
# REMOÇÃO DE DUPLICADOS EXATOS
# =============================================================================

antes = len(facio)

facio = facio.drop_duplicates()

print(
    f"Duplicados removidos Facio: {antes-len(facio)}"
)

antes = len(fundo)

fundo = fundo.drop_duplicates()

print(
    f"Duplicados removidos Fundo: {antes-len(fundo)}"
)

# =============================================================================
# REMOÇÃO DE REGISTROS SEM CHAVE
# =============================================================================

facio = facio.dropna(
    subset=[
        "id_contrato",
        "parcela"
    ]
)

fundo = fundo.dropna(
    subset=[
        "id_contrato",
        "parcela"
    ]
)

# =============================================================================
# EXPORTAÇÃO DOS DADOS TRATADOS
# =============================================================================

facio.to_csv(
    DATA_PROCESSED / "facio_tratado.csv",
    index=False
)

fundo.to_csv(
    DATA_PROCESSED / "fundo_tratado.csv",
    index=False
)

print("\n")
print("=" * 80)
print("VALIDAÇÃO FINALIZADA")
print("=" * 80)

print(f"Facio : {facio.shape}")
print(f"Fundo : {fundo.shape}")
