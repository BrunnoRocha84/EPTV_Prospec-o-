# Pipeline de Prospecção Comercial - EPTV

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-Internal-yellow.svg)]()

Sistema automatizado para refinamento de bases de prospecção comercial, integrando validação cadastral, enriquecimento digital e cruzamento com bases de mídia.

## 🎯 Visão Geral

O pipeline processa bases de prospecção (Econodata) e enriquece com:
- Validação de situação cadastral (Receita Federal)
- Análise de presença digital
- Cruzamento com bases de mídia (TV, Rádio, OOH)
- Scoring de priorização para abordagem comercial

## 📁 Estrutura do Projeto

```
eptv_prospeccao/
├── main.py                      # Entry point - orquestrador principal
├── config/
│   ├── __init__.py
│   └── settings.py              # Configurações centralizadas
├── src/
│   ├── ingestao/
│   │   └── ingestao.py          # Carregamento de bases Excel/CSV
│   ├── validacao/
│   │   └── validacao.py         # Validação cadastral e contatos
│   ├── enriquecimento/
│   │   └── digital.py           # Análise de presença digital
│   ├── matching/
│   │   ├── fuzzy.py             # Algoritmo de similaridade
│   │   ├── adi.py               # Cruzamento TV (ADI)
│   │   ├── crowley.py           # Cruzamento Rádio
│   │   └── kantar.py            # Cruzamento OOH
│   ├── scoring/
│   │   └── scoring.py           # Cálculo de priorização
│   ├── services/
│   │   ├── gemini.py            # API Google Gemini
│   │   ├── nominatim.py         # API OpenStreetMap
│   │   └── receita_federal.py   # APIs BrasilAPI/ReceitaWS
│   └── utils/
│       └── helpers.py           # Funções auxiliares
├── data/
│   ├── input/                   # Arquivos de entrada
│   ├── output/                  # Resultados gerados
│   └── processed/               # Arquivos intermediários
├── tests/                       # Testes unitários
├── docs/                        # Documentação adicional
├── .env.example                 # Template de configuração
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 🚀 Instalação

### 1. Clonar o repositório
```bash
git clone https://dev.azure.com/data-and-crm/General/_git/eptv-prospeccao
cd eptv_prospeccao
```

### 2. Criar ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente
```bash
cp .env.example .env
# Editar .env com suas API Keys
```

## ⚙️ Configuração

### API Keys necessárias

| API | Variável | Como obter |
|-----|----------|------------|
| Google Gemini | `GEMINI_API_KEY` | [AI Studio](https://aistudio.google.com/) |

### Arquivo `.env`
```env
GEMINI_API_KEY=sua_chave_aqui
```

## 📖 Uso

### Pipeline Completo (Recomendado)

```bash
python main.py --econodata "data/input/base.xlsx" --kantar "data/input/ooh.xlsx" --crowley "data/input/radio.xlsx"
```

### Opções disponíveis

| Argumento | Obrigatório | Descrição |
|-----------|-------------|-----------|
| `--econodata`, `-e` | ✅ | Base de prospecção |
| `--kantar`, `-k` | ❌ | Base Kantar (OOH) |
| `--crowley`, `-c` | ❌ | Base Crowley (Rádio) |
| `--output`, `-o` | ❌ | Arquivo de saída customizado |

### Módulos Individuais

```bash
# Cruzamento TV (ADI)
python -m src.matching.adi "data/input/base.xlsx" "data/input/adi_2026_01.xlsx"

# Cruzamento Rádio (Crowley)
python -m src.matching.crowley "data/input/base.xlsx" "data/input/crowley.xlsx"

# Cruzamento OOH (Kantar)
python -m src.matching.kantar "data/input/base.xlsx" "data/input/kantar.xlsx"

# Validação Receita Federal
python -m src.services.receita_federal "data/input/base.xlsx" 10

# Verificação Publicidade (Gemini)
python -m src.services.gemini "data/input/base.xlsx" 10

# Verificação Endereço (Nominatim)
python -m src.services.nominatim "data/input/base.xlsx" 10
```

## 📊 Pipeline - Etapas

### 1. Ingestão e Preparação
- Carrega arquivos Excel/CSV
- Normaliza CNPJs (remove formatação)
- Valida integridade dos dados

### 2. Validação de Atividade
- Verifica situação cadastral
- Valida telefones e emails
- Confirma CNAE preenchido

### 3. Enriquecimento Digital
- Analisa presença em redes sociais
- Classifica: `FORTE`, `MÉDIA`, `FRACA`, `NULA`
- Redes: Instagram, Facebook, LinkedIn, Site, WhatsApp

### 4. Cruzamento com Bases de Mídia
- Fuzzy matching com anunciantes
- Threshold mínimo: 70%
- Alta confiança: ≥85%

### 5. Scoring de Priorização

| Critério | Peso |
|----------|------|
| Cadastro completo | 15% |
| Viabilidade comercial | 25% |
| Presença digital | 20% |
| Match com mídia | 25% |
| Qualidade do contato | 15% |

### 6. Geração do Output
- Excel com 3 abas: Lista Priorizada, Resumo, Top 20
- Prioridades: `MUITO_ALTA`, `ALTA`, `MÉDIA`, `BAIXA`

## 🔌 APIs Utilizadas

| API | Uso | Custo | Rate Limit |
|-----|-----|-------|------------|
| BrasilAPI | Consulta CNPJ | Gratuito | 3/seg |
| ReceitaWS | Fallback CNPJ | Gratuito | 3/min |
| Google Gemini | Análise de publicidade | Gratuito | 1.000/dia |
| Nominatim | Geocodificação | Gratuito | 1/seg |

## 📈 Resultados - Exemplo

Base: Saúde - Ribeirão Preto (242 empresas)

| Métrica | Resultado |
|---------|-----------|
| CNPJs válidos | 242 (100%) |
| Empresas ativas | 242 (100%) |
| Com presença digital | 136 (56%) |
| Presença FORTE | 42 (17.4%) |
| Match TV (ADI) | 6 |
| Match Rádio (Crowley) | 2 |
| Match OOH (Kantar) | 2 |
| Prioridade MUITO_ALTA | 3 |
| Prioridade ALTA | 77 |

## 🐛 Troubleshooting

### "API Key não configurada"
```bash
# Verificar se .env existe
cat .env

# Criar se não existir
cp .env.example .env
```

### "HTTP 429" (Rate Limit)
- Aguardar alguns minutos
- Reduzir velocidade de requisições
- Para grandes volumes, usar APIs pagas

### Matches zerados
- Executar módulos individuais para diagnóstico
- Verificar se bases de mídia contêm dados da região
- Ajustar threshold de similaridade se necessário

## 🤝 Contribuição

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para guia detalhado.

```bash
# Criar branch
git checkout -b feature/nova-funcionalidade

# Commit
git commit -m "feat: adiciona nova funcionalidade"

# Push
git push origin feature/nova-funcionalidade
```

## 📋 Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para histórico de versões.

## 📄 Licença

Uso interno - EPTV

## 👥 Contato

**Inteligência Comercial - EPTV**
- Azure DevOps: [data-and-crm/General](https://dev.azure.com/data-and-crm/General)