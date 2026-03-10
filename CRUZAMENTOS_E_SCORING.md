# Documentação Técnica: Cruzamentos e Scoring

## Visão Geral

Este documento detalha como o sistema cruza informações de diferentes fontes e calcula o score de priorização para cada empresa.

---

## 1. Fontes de Dados

### 1.1 Base Principal (Econodata)
| Campo | Descrição | Uso |
|-------|-----------|-----|
| CNPJ | Identificador único da empresa | Chave primária |
| RAZÃO SOCIAL | Nome jurídico | Matching fuzzy |
| NOME FANTASIA | Nome comercial | Matching fuzzy (prioridade) |
| SITUAÇÃO CADASTRAL | Ativa/Inativa | Validação |
| TELEFONE | Contato telefônico | Score de contato |
| EMAIL | Contato eletrônico | Score de contato |
| CNAE | Código de atividade | Validação |
| CIDADE / UF | Localização | Filtro regional |
| Instagram, Facebook, LinkedIn, Site | Redes sociais | Score digital |

### 1.2 Base ADI (TV)
| Campo | Descrição | Uso |
|-------|-----------|-----|
| ANUNCIANTE | Nome do anunciante | Matching fuzzy |
| VALOR | Investimento em R$ | Priorização |
| QTD | Quantidade de inserções | Métrica de volume |
| PRAÇA | Região de veiculação | Filtro EPTV |
| SETOR | Segmento do anunciante | Contexto |
| EMISSORA | Canal de TV | Identificação |

**Filtro aplicado:** Apenas praças EPTV (CAMPINAS, RIBEIRÃO PRETO, SÃO CARLOS, etc.)

### 1.3 Base Crowley (Rádio)
| Campo | Descrição | Uso |
|-------|-----------|-----|
| ANUNCIANTE | Nome do anunciante | Matching fuzzy |
| MERCADO | Região de atuação | Filtro regional |
| INSERÇÕES | Quantidade de veiculações | Métrica de volume |

### 1.4 Base Kantar (OOH - Out of Home)
| Campo | Descrição | Uso |
|-------|-----------|-----|
| ANUNCIANTE | Nome do anunciante | Matching fuzzy |
| VALOR | Investimento estimado | Priorização |
| TIPO_MIDIA | Outdoor, Busdoor, etc. | Contexto |

---

## 2. Algoritmo de Cruzamento (Fuzzy Matching)

### 2.1 Localização
**Arquivo:** `src/utils/helpers.py` → função `calcular_similaridade()`

### 2.2 Como Funciona

```
ENTRADA: Nome da empresa (base) + Nome do anunciante (mídia)

ETAPA 1: Normalização
├── Converter para minúsculas
├── Remover acentos
├── Remover caracteres especiais
├── Remover termos jurídicos (LTDA, S/A, ME, EPP, EIRELI)
└── Remover espaços extras

ETAPA 2: Cálculo de Similaridade
├── SequenceMatcher (60% do peso)
│   └── Compara sequência de caracteres
└── Jaccard de Tokens (40% do peso)
    └── Compara palavras em comum

ETAPA 3: Bônus
├── +15% se primeira palavra igual
│   └── Ex: "UNIMED BEBEDOURO" vs "UNIMED BRASIL" → +15%
└── +10% se um nome contém o outro
    └── Ex: "HOSPITAL VIVER" vs "HOSPITAL VIVER LTDA" → +10%

SAÍDA: Score de 0.0 a 1.0 (0% a 100%)
```

### 2.3 Fórmula

```python
# Cálculo base
score_sequencia = SequenceMatcher(None, texto1, texto2).ratio()
score_jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
score_base = (score_sequencia * 0.6) + (score_jaccard * 0.4)

# Bônus
if primeira_palavra_igual:
    score_base += 0.15

if texto1 in texto2 or texto2 in texto1:
    score_base += 0.10

# Limita a 1.0 (100%)
score_final = min(1.0, score_base)
```

### 2.4 Thresholds de Confiança

| Faixa | Classificação | Ação |
|-------|---------------|------|
| ≥ 85% | ALTA | Match confirmado |
| 70% - 84% | MÉDIA | Match provável |
| < 70% | DESCARTADO | Não considera |

### 2.5 Exemplo Prático

```
Base Econodata: "UNIMED DE BEBEDOURO COOPERATIVA"
Base ADI:       "UNIMED BEBEDOURO"

Normalização:
├── Econodata: "unimed bebedouro cooperativa"
└── ADI:       "unimed bebedouro"

Cálculo:
├── SequenceMatcher: 0.75 (75%)
├── Jaccard: 0.66 (2 palavras comuns / 3 únicas)
├── Score base: (0.75 * 0.6) + (0.66 * 0.4) = 0.714
├── Bônus primeira palavra ("unimed" = "unimed"): +0.15
└── Score final: 0.864 (86.4%) → ALTA CONFIANÇA ✓
```

---

## 3. Sistema de Scoring

### 3.1 Localização
**Arquivo:** `src/scoring/scoring.py`

### 3.2 Componentes do Score

O score final (0-100) é composto por 5 dimensões:

| Dimensão | Peso | Máximo Pontos | O que mede |
|----------|------|---------------|------------|
| Cadastro | 15% | 15 pts | Qualidade dos dados cadastrais |
| Viabilidade | 25% | 25 pts | Potencial comercial |
| Digital | 20% | 20 pts | Presença online |
| Mídia | 25% | 25 pts | Já anuncia em TV/Rádio/OOH |
| Contato | 15% | 15 pts | Acessibilidade para abordagem |

### 3.3 Cálculo por Dimensão

#### 3.3.1 Score de Cadastro (15 pts)
```python
score_cadastro = 0

# Situação ativa (+5 pts)
if situacao_cadastral == "ATIVA":
    score_cadastro += 5

# CNAE preenchido (+5 pts)
if cnae_preenchido:
    score_cadastro += 5

# Dados completos (+5 pts)
if razao_social and nome_fantasia and endereco_completo:
    score_cadastro += 5
```

#### 3.3.2 Score de Viabilidade (25 pts)
```python
score_viabilidade = 0

# Porte da empresa
if porte == "GRANDE":
    score_viabilidade += 15
elif porte == "MEDIO":
    score_viabilidade += 10
elif porte == "PEQUENO":
    score_viabilidade += 5

# Capital social
if capital_social > 1_000_000:
    score_viabilidade += 10
elif capital_social > 100_000:
    score_viabilidade += 5
```

#### 3.3.3 Score Digital (20 pts)
```python
# Conta redes sociais presentes
redes = [instagram, facebook, linkedin, site, whatsapp]
qtd_redes = sum(1 for r in redes if r)

# Classificação
if qtd_redes >= 3:
    presenca = "FORTE"
    score_digital = 20
elif qtd_redes == 2:
    presenca = "MEDIA"
    score_digital = 15
elif qtd_redes == 1:
    presenca = "FRACA"
    score_digital = 8
else:
    presenca = "NULA"
    score_digital = 0
```

#### 3.3.4 Score de Mídia (25 pts)
```python
score_midia = 0

# Match com TV (ADI)
if match_tv and similaridade_tv >= 0.70:
    score_midia += 10
    if similaridade_tv >= 0.85:
        score_midia += 5  # Bônus alta confiança

# Match com Rádio (Crowley)
if match_radio and similaridade_radio >= 0.70:
    score_midia += 5
    if similaridade_radio >= 0.85:
        score_midia += 2

# Match com OOH (Kantar)
if match_ooh and similaridade_ooh >= 0.70:
    score_midia += 5
    if similaridade_ooh >= 0.85:
        score_midia += 3
```

#### 3.3.5 Score de Contato (15 pts)
```python
score_contato = 0

# Telefone válido (+7 pts)
if telefone_valido:
    score_contato += 7

# Email válido (+5 pts)
if email_valido:
    score_contato += 5

# WhatsApp (+3 pts)
if whatsapp:
    score_contato += 3
```

### 3.4 Score Final

```python
score_final = (
    score_cadastro +      # máx 15
    score_viabilidade +   # máx 25
    score_digital +       # máx 20
    score_midia +         # máx 25
    score_contato         # máx 15
)
# Total máximo: 100 pontos
```

### 3.5 Classificação de Prioridade

| Score | Prioridade | Recomendação |
|-------|------------|--------------|
| ≥ 70 | MUITO_ALTA | Abordagem imediata |
| 50 - 69 | ALTA | Abordagem prioritária |
| 30 - 49 | MÉDIA | Abordagem secundária |
| < 30 | BAIXA | Manter em base |

---

## 4. Fluxo Completo de Cruzamento

```
┌─────────────────────────────────────────────────────────────────┐
│                    BASE ECONODATA (242 CNPJs)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 1: VALIDAÇÃO                                              │
│ ├── Situação cadastral ativa? ────────────────────► Score +5   │
│ ├── CNAE preenchido? ─────────────────────────────► Score +5   │
│ └── Dados completos? ─────────────────────────────► Score +5   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 2: ENRIQUECIMENTO DIGITAL                                 │
│ ├── Instagram ─┐                                                │
│ ├── Facebook  ─┼── Conta quantas ─► FORTE/MÉDIA/FRACA/NULA     │
│ ├── LinkedIn  ─┤                                                │
│ ├── Site ─────┤                                                 │
│ └── WhatsApp ──┘                    ────────────► Score 0-20    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 3: CRUZAMENTO COM MÍDIA                                   │
│                                                                 │
│ ┌─────────────┐   Fuzzy Match   ┌─────────────┐                │
│ │ NOME        │ ◄─────────────► │ ADI (TV)    │ ► Score +10-15 │
│ │ FANTASIA    │   ≥70%          │ 148 anunc.  │                │
│ └─────────────┘                 └─────────────┘                │
│       │                                                         │
│       │         Fuzzy Match   ┌─────────────┐                  │
│       ├───────────────────────► │ Crowley     │ ► Score +5-7   │
│       │         ≥70%          │ (Rádio)     │                  │
│       │                       └─────────────┘                  │
│       │                                                         │
│       │         Fuzzy Match   ┌─────────────┐                  │
│       └───────────────────────► │ Kantar      │ ► Score +5-8   │
│                 ≥70%          │ (OOH)       │                  │
│                               └─────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 4: VALIDAÇÃO DE CONTATO                                   │
│ ├── Telefone válido (8-9 dígitos)? ───────────────► Score +7   │
│ ├── Email válido (contém @)? ─────────────────────► Score +5   │
│ └── WhatsApp disponível? ─────────────────────────► Score +3   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 5: CÁLCULO FINAL                                          │
│                                                                 │
│ Score Final = Cadastro + Viabilidade + Digital + Mídia + Contato│
│             = (0-15)  + (0-25)      + (0-20)  + (0-25) + (0-15) │
│             = 0 a 100 pontos                                    │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ≥70 pts │ MUITO_ALTA │ 50-69 │ ALTA │ 30-49 │ MÉDIA │ <30 │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT: EXCEL PRIORIZADO                     │
│ ├── Aba 1: Lista completa ordenada por score                   │
│ ├── Aba 2: Resumo estatístico                                  │
│ └── Aba 3: Top 20 prospects                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Métricas de Qualidade

### 5.1 Taxa de Match por Base

| Base | Anunciantes | Matches | Taxa |
|------|-------------|---------|------|
| ADI (TV) | 148 | 6 | 2.5% |
| Crowley (Rádio) | 109 | 2 | 0.8% |
| Kantar (OOH) | 301 | 2 | 0.8% |

### 5.2 Distribuição de Scores (Base Ribeirão Preto)

| Prioridade | Quantidade | Percentual |
|------------|------------|------------|
| MUITO_ALTA | 3 | 1.2% |
| ALTA | 77 | 31.8% |
| MÉDIA | 160 | 66.1% |
| BAIXA | 2 | 0.8% |

### 5.3 Estatísticas de Score

| Métrica | Valor |
|---------|-------|
| Score médio | 45.5 |
| Score mínimo | 27.5 |
| Score máximo | 75.0 |
| Desvio padrão | ~12 |

---

## 6. Considerações Técnicas

### 6.1 Performance
- Fuzzy matching O(n*m) onde n=empresas, m=anunciantes
- 242 empresas x 148 anunciantes = ~36.000 comparações
- Tempo médio: 3-5 segundos por base de mídia

### 6.2 Limitações
- Nomes muito diferentes não fazem match (ex: "Drogão" vs "Drogaria Drogão Ltda")
- Empresas do mesmo grupo com nomes diferentes não são identificadas
- Score de viabilidade depende de dados nem sempre disponíveis

### 6.3 Melhorias Futuras
- Implementar match por CNPJ além de nome
- Adicionar sinônimos/apelidos de empresas conhecidas
- Machine Learning para ajustar pesos automaticamente
- Integração com bases de crédito para score de viabilidade

---

## 7. Glossário

| Termo | Definição |
|-------|-----------|
| **Fuzzy Matching** | Algoritmo que encontra textos similares mesmo com diferenças |
| **SequenceMatcher** | Biblioteca Python que compara sequências de caracteres |
| **Jaccard** | Índice que mede similaridade entre conjuntos |
| **Threshold** | Valor mínimo para considerar um match válido |
| **ADI** | Agência de Dados de Investimento (base de TV) |
| **OOH** | Out of Home - mídia externa (outdoor, busdoor) |
| **CNAE** | Classificação Nacional de Atividades Econômicas |