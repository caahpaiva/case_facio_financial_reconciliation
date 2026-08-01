# Case Facio – Financial Reconciliation

## Visão Geral

Este repositório contém a solução desenvolvida para o **Case de Business Analyst – Conciliação Financeira da Facio**.

O objetivo do projeto foi implementar um processo completo de conciliação entre a posição da Facio e a posição dos Fundos, incluindo cálculo da taxa implícita, cálculo do Valor Presente (VP), classificação das divergências e análises financeiras para suporte à tomada de decisão.

---

# Objetivos

O projeto responde integralmente às cinco questões propostas no case:

- ✔ Implementação da conciliação de carteira
- ✔ Análise de exposição financeira
- ✔ Análise da taxa implícita utilizada pelo Fundo
- ✔ Composição e concentração do portfólio
- ✔ Hipóteses de causa-raiz e recomendações operacionais

---

# Estrutura do Projeto

```
case_facio_financial_reconciliation/

├── data/
│   ├── raw/
│   └── processed/
│
├── analysis/
│   ├── reconciliation.py
│   ├── utils.py
│   └── plots.py
│
├── notebooks/
│   └── 01_reconciliation_analysis.ipynb
│
├── scripts/
│   └── validate_and_clean.py
│
├── outputs/
│   ├── figures/
│   ├── kpis_summary.json
│   ├── conciliation_results_with_rates.csv
│   └── ...
│
└── README.md
```

---

# Tecnologias

- Python 3.13
- Pandas
- NumPy
- Matplotlib
- Seaborn
- Jupyter Notebook

---

# Fluxo da Solução

1. Limpeza e padronização dos datasets
2. Cálculo da taxa implícita de cessão
3. Cálculo do Valor Presente (VP)
4. Conciliação entre Facio e Fundo
5. Classificação dos registros
6. Geração de KPIs
7. Análises exploratórias e visualizações

---

# Principais Resultados

| Indicador | Valor |
|-----------|------:|
| Total de registros conciliados | 49.999 |
| Match Exact | 35.849 |
| Match Divergent | 4.846 |
| Only Fundo | 9.295 |
| Only Facio | 9 |

### Exposição Financeira

- Match Exact: **R$ 6,64 milhões**
- Match Divergent: **R$ 1,15 milhão**
- Only Fundo: **R$ 1,45 milhão**
- Only Facio: **R$ 1,0 mil**

### Produtos

- SimpleCredit: **R$ 5,38 milhões**
- SalaryAdvanceFX: **R$ 2,33 milhões**
- eConsignado: **R$ 72 mil**

---

# Principais Insights

- A maior parte da carteira foi conciliada com sucesso.
- Os maiores riscos financeiros estão concentrados nos registros classificados como **Only Fundo**.
- O **FIDC4** concentra a maior parte das divergências de valor presente.
- Foi identificado indício de utilização de convenções diferentes para cálculo da taxa implícita.
- Grande concentração da carteira em vencimentos de curto prazo.

---

# Visualizações

O notebook gera automaticamente:

- Distribuição dos status de conciliação
- Exposição por produto
- Exposição por fundo
- Top 10 divergências
- Histograma das divergências
- VP por fundo
- VP por produto
- Bucket de prazo
- Boxplot da diferença de taxa por produto
- Boxplot da diferença de taxa por fundo

Todos os gráficos seguem a identidade visual da Facio.

---

# Como Executar

## Criar ambiente

```bash
python -m venv source
```

### Windows

```bash
source\Scripts\activate
```

### Linux / macOS

```bash
source/bin/activate
```

Instalar dependências

```bash
pip install -r requirements.txt
```

Executar limpeza

```bash
python -m scripts.validate_and_clean
```

Executar conciliação

```bash
python -m analysis.reconciliation
```

Abrir notebook

```bash
jupyter notebook notebooks/01_reconciliation_analysis.ipynb
```

---

# Autor

Projeto desenvolvido como solução para o **Case de Business Analyst – Facio**, contemplando modelagem analítica, conciliação financeira, cálculo de valor presente, análise de risco operacional e geração de indicadores executivos.