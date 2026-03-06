# Pipeline de Prospecção Comercial - EPTV

Sistema automatizado para refinamento de bases de prospecção comercial, integrando validação cadastral, enriquecimento digital e cruzamento com bases de mídia.

## Visão Geral

O pipeline processa bases de prospecção (Econodata) e enriquece com:
- Validação de situação cadastral (Receita Federal)
- Análise de presença digital
- Cruzamento com bases de mídia (TV, Rádio, OOH)
- Scoring de priorização para abordagem comercial

## Estrutura do Projeto

```
eptv_prospeccao/
├── main.py                     # Orquestrador principal
├── validar_receita.py          # Validação em lote - Receita Federal
├── verificar_publicidade.py    # Verificação via Google Gemini
├── verificar_endereco.py       # Verificação via Nominatim
├── cruzar_adi.py              # Cruzamento com ADI (TV)
├── cruzar_crowley.py          # Cruzamento com Crowley (Rádio)
├── cruzar_kantar.py           # Cruzamento com Kantar (OOH)
├── .env                        # Configurações (API Keys)
├── requirements.txt            # Dependências
├── data/
│   ├── input/                  # Arquivos de entrada
│   └── output/                 # Resultados gerados
└── src/
    ├── ingestao/              # Módulo de ingestão
    ├── validacao/             # Módulo de validação
    ├── enriquecimento/        # Módulo de presença digital
    ├── matching/              # Módulo de cruzamento (fuzzy)
    ├── scoring/               # Módulo de scoring
    ├── consulta/              # Consultas externas (RF)
    └── utils/                 # Utilitários
```

## Instalação

### 1. Clonar o repositório
```bash
git clone <url-do-repositorio>
cd eptv_prospeccao
```

### 2. Criar ambiente virtual (recomendado)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar API Keys
Criar arquivo `.env` na raiz do projeto:
```
GEMINI_API_KEY=sua_chave_aqui
```

Para obter a chave do Gemini:
1. Acesse https://aistudio.google.com/
2. Clique em "Get API Key" → "Create API Key"
3. Copie a chave gerada

## Uso

### Pipeline Completo (Recomendado)
```bash
python main.py --econodata "data/input/Saude - RIB.xlsx" --kantar "data/input/kantar.xlsx" --crowley "data/input/crowley.xlsx"
```

### Opções do Pipeline
```bash
python main.py --help

Argumentos:
  --econodata, -e    Arquivo de prospecção (obrigatório)
  --kantar, -k       Arquivo Kantar OOH (opcional)
  --crowley, -c      Arquivo Crowley Rádio (opcional)
  --output, -o       Arquivo de saída (opcional)
  --verbose, -v      Modo verboso
```

### Scripts Individuais

#### Validação Receita Federal
```bash
python validar_receita.py "data/input/base.xlsx"
python validar_receita.py "data/input/base.xlsx" 10  # Limita a 10 CNPJs
```

#### Cruzamento com TV (ADI)
```bash
python cruzar_adi.py "data/input/base.xlsx" "data/input/adi_2026_01.xlsx"
python cruzar_adi.py "data/input/base.xlsx" "data/input/adi_*.xlsx"  # Múltiplos arquivos
```

#### Cruzamento com Rádio (Crowley)
```bash
python cruzar_crowley.py "data/input/base.xlsx" "data/input/crowley.xlsx"
```

#### Cruzamento com OOH (Kantar)
```bash
python cruzar_kantar.py "data/input/base.xlsx" "data/input/kantar_ooh.xlsx"
```

#### Verificação de Publicidade (Gemini)
```bash
python verificar_publicidade.py "data/input/base.xlsx" 10  # Testa 10 empresas
```

#### Verificação de Endereço (Nominatim)
```bash
python verificar_endereco.py "data/input/base.xlsx" 10  # Testa 10 empresas
```

## Bases de Dados

### Entrada

| Base | Formato | Descrição |
|------|---------|-----------|
| Econodata | .xlsx | Base de prospecção com CNPJs |
| ADI (Kantar TV) | .xlsx | Inserções de TV por anunciante |
| Crowley | .xlsx | Inserções de rádio por anunciante |
| Kantar OOH | .xlsx | Investimento em mídia externa |

### Saída

| Arquivo | Descrição |
|---------|-----------|
| `prospeccao_refinada_*.xlsx` | Resultado do pipeline completo |
| `validacao_receita_*.xlsx` | Resultado da validação RF |
| `cruzamento_adi_*.xlsx` | Matches com TV |
| `cruzamento_crowley_*.xlsx` | Matches com Rádio |
| `cruzamento_kantar_*.xlsx` | Matches com OOH |

## APIs Utilizadas

| API | Uso | Custo |
|-----|-----|-------|
| BrasilAPI | Consulta CNPJ (primária) | Gratuito |
| ReceitaWS | Consulta CNPJ (fallback) | Gratuito (limite 3/min) |
| Google Gemini | Verificar publicidade | Gratuito (1.000 req/dia) |
| Nominatim | Verificar endereço | Gratuito (1 req/seg) |

## Etapas do Pipeline

### 1. Ingestão e Preparação
- Carrega arquivo Excel/CSV
- Normaliza CNPJs
- Valida formato dos dados

### 2. Validação de Atividade
- Verifica situação cadastral (campo existente)
- Valida dados de contato (telefone, email)
- Verifica CNAE preenchido

### 3. Enriquecimento Digital
- Analisa presença em redes sociais
- Classifica: FORTE, MÉDIA, FRACA, NULA
- Redes: Instagram, Facebook, LinkedIn, Site, WhatsApp

### 4. Cruzamento com Bases de Mídia
- Fuzzy matching com anunciantes
- Threshold mínimo: 70%
- Alta confiança: 85%+

### 5. Scoring de Priorização
- Score final: 0-100 pontos
- Prioridades: MUITO_ALTA, ALTA, MÉDIA, BAIXA

Pesos do scoring:
| Critério | Peso |
|----------|------|
| Cadastro | 15% |
| Viabilidade | 25% |
| Presença Digital | 20% |
| Match Mídia | 25% |
| Contato | 15% |

### 6. Geração do Output
- Lista priorizada de empresas
- Resumo executivo
- Top 20 prospects

## Resultados - Base Ribeirão Preto (242 empresas)

| Métrica | Resultado |
|---------|-----------|
| CNPJs válidos | 242 (100%) |
| Empresas ativas | 242 (100%) |
| Com presença digital | 136 (56%) |
| Presença FORTE | 42 (17.4%) |
| Match TV (ADI) | 6 |
| Match Rádio (Crowley) | 10 |
| Match OOH (Kantar) | 18 |
| Prioridade MUITO_ALTA | 3 |
| Prioridade ALTA | 77 |

## Troubleshooting

### Erro: "API Key não configurada"
- Verifique se o arquivo `.env` existe na raiz
- Confirme que a chave está no formato correto: `GEMINI_API_KEY=sua_chave`

### Erro: "HTTP 429" (Rate Limit)
- As APIs gratuitas têm limite de requisições
- Aguarde alguns minutos e tente novamente
- Para grandes volumes, considere APIs pagas

### Erro: "Coluna não encontrada"
- Verifique se o arquivo Excel tem as colunas esperadas
- O sistema busca automaticamente variações de nomes

### Matches zerados no pipeline
- Execute os scripts individuais (`cruzar_*.py`) para diagnóstico
- Verifique se as bases de mídia contêm dados da região

## Contribuição

1. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
2. Commit suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
3. Push para a branch: `git push origin feature/nova-funcionalidade`
4. Abra um Pull Request

## Licença

Uso interno - EPTV

## Contato

Inteligência Comercial - EPTV