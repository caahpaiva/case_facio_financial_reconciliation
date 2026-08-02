# Case Facio – Financial Reconciliation

## Sobre o projeto

Este repositório apresenta a solução desenvolvida para o **Case de Business Analyst – Conciliação Financeira da Facio**.

O projeto implementa um fluxo completo de reconciliação financeira entre a posição interna da Facio e a posição dos Fundos, contemplando:

- padronização e validação dos dados;
- cálculo da taxa implícita de desconto;
- cálculo do Valor Presente (VP);
- reconciliação das carteiras;
- classificação das divergências;
- geração automática de KPIs;
- análises exploratórias e recomendações operacionais.

---

## Objetivos do Case

A solução responde às cinco questões propostas no desafio:

- ✅ Questão 1 — Conciliação das posições
- ✅ Questão 2 — Exposição financeira das divergências
- ✅ Questão 3 — Análise da taxa implícita do Fundo
- ✅ Questão 4 — Composição do portfólio
- ✅ Questão 5 — Hipóteses de causa-raiz e recomendações

---

## Arquitetura do Projeto

```
case_facio_financial_reconciliation
│
├── analysis/
│   ├── normalization.py
│   ├── reconciliation.py
│   ├── plots.py
│   └── utils.py
│
├── scripts/
│   ├── parquet_to_csv.py
│   └── validate_and_clean.py
│
├── notebooks/
│   └── 01_reconciliation_analysis.ipynb
│
├── data/
│   ├── raw/
│   └── processed/
│
├── outputs/
│   ├── figures/
│   ├── conciliation_results_with_rates.csv
│   └── kpis_summary.json
│
├── executive_one_page.pdf
├── resumo_executivo_completo.pdf
├── report.md
├── requirements.txt
└── README.md
```

---

## Fluxo da Solução

```text
Datasets (.parquet)
        │
        ▼
Limpeza e Padronização
        │
        ▼
Normalização das Chaves
        │
        ▼
Cálculo da Taxa Implícita
        │
        ▼
Cálculo do Valor Presente
        │
        ▼
Reconciliação Facio × Fundo
        │
        ▼
Classificação dos Status
        │
        ▼
KPIs + Visualizações + Relatórios
```

---

## Tecnologias

- Python 3.13
- Pandas
- NumPy
- Matplotlib
- Seaborn
- Jupyter Notebook

---

## Metodologia

A conciliação foi realizada utilizando uma chave composta formada por:

- contrato
- parcela

Cada registro foi classificado em uma das seguintes categorias:

| Status | Descrição |
|---------|-----------|
| Match Exact | Registro encontrado nos dois lados sem divergência financeira |
| Match Divergent | Registro encontrado em ambos os lados, porém com divergência de VP |
| Only Facio | Registro existente apenas na posição Facio |
| Only Fundo | Registro existente apenas na posição do Fundo |

A taxa implícita foi estimada utilizando:

- Valor de cessão;
- Valor Presente;
- Data de cessão;
- Data de referência.

---

# Principais Resultados

## Reconciliação

| Status | Quantidade |
|---------|-----------:|
| Match Exact | 35.849 |
| Match Divergent | 4.846 |
| Only Fundo | 9.295 |
| Only Facio | 9 |

---

## Exposição Financeira

| Categoria | Exposição |
|-----------|----------:|
| Match Exact | R$ 6,64 milhões |
| Match Divergent | R$ 1,15 milhão |
| Only Fundo | R$ 1,45 milhão |
| Only Facio | R$ 1 mil |

---

## Principais Insights

- 71,7% dos registros foram conciliados sem divergência financeira.
- As maiores diferenças estão concentradas no FIDC4.
- O produto SimpleCredit apresenta maior divergência média de taxa implícita.
- O FIDC4 concentra aproximadamente 89% da exposição financeira da carteira.
- 77,7% da carteira do FIDC4 vence em até 30 dias.

---

# Visualizações

As figuras abaixo são geradas automaticamente pelo notebook.

## Distribuição dos Status

![](outputs/figures/distribuicao_status.png)

---

## Exposição por Produto

![](outputs/figures/vp_produto.png)

---

## Exposição por Fundo

![](outputs/figures/vp_fundo.png)

---

## Bucket de Prazo

![](outputs/figures/bucket_prazo.png)

---

## Top 10 Divergências

![](outputs/figures/top10_divergencias.png)

---

## Distribuição das Divergências

![](outputs/figures/hist_divergencias.png)

---

## Diferença da Taxa por Produto

![](outputs/figures/boxplot_taxa_produto.png)

---

## Diferença da Taxa por Fundo

![](outputs/figures/boxplot_taxa_fundo.png)

---

# Como executar

## Criar ambiente virtual

```bash
python -m venv source
```

### Windows

```bash
source\Scripts\activate
```

### Linux/macOS

```bash
source/bin/activate
```

Instalar dependências

```bash
pip install -r requirements.txt
```

Converter os arquivos Parquet para CSV (opcional)

```bash
python -m scripts.parquet_to_csv
```

Executar limpeza e validação

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

# Entregáveis

- executive_one_page.pdf
- resumo_executivo_completo.pdf
- report.md
- notebook com toda a análise
- KPIs em JSON
- resultados em CSV
- gráficos em PNG

---

# Autor

Projeto desenvolvido como solução para o **Case de Business Analyst – Facio**, com foco em reconciliação financeira, modelagem analítica, análise exploratória e recomendações operacionais.