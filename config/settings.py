"""
Configurações do Pipeline de Prospecção - EPTV
==============================================

Arquivo central de configurações do projeto.
Altere os valores conforme necessidade.
"""

from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================

# Diretório raiz do projeto
ROOT_DIR = Path(__file__).parent.parent

# Diretórios de dados
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
PROCESSED_DIR = DATA_DIR / "processed"

# =============================================================================
# CONFIGURAÇÕES DE INGESTÃO (Task 7298)
# =============================================================================

INGESTAO = {
    # Extensões aceitas
    "extensoes_aceitas": [".xlsx", ".xls", ".csv"],
    
    # Encoding padrão para CSV
    "csv_encoding": "utf-8",
    "csv_separadores": [",", ";", "\t"],
    
    # Colunas obrigatórias (pelo menos uma deve existir)
    "colunas_cnpj": ["CNPJ", "cnpj", "Cnpj", "CNPJ_EMPRESA"],
    "colunas_nome": ["NOME FANTASIA", "NOME_FANTASIA", "RAZÃO SOCIAL", "RAZAO_SOCIAL", "NOME DA EMPRESA"],
}

# =============================================================================
# CONFIGURAÇÕES DE VALIDAÇÃO (Task 7299)
# =============================================================================

VALIDACAO = {
    # Status considerados como empresa ativa
    "status_ativos": ["ATIVA", "ATIVO", "REGULAR"],
    
    # Status considerados como empresa inativa
    "status_inativos": ["BAIXADA", "INAPTA", "SUSPENSA", "NULA", "CANCELADA"],
    
    # Validar CNPJ matematicamente
    "validar_digitos_cnpj": True,
    
    # Usar API externa para validação (futuro)
    "usar_api_receita": False,
    "api_receita_url": "https://brasilapi.com.br/api/cnpj/v1/",
}

# =============================================================================
# CONFIGURAÇÕES DE ENRIQUECIMENTO DIGITAL (Task 7300)
# =============================================================================

ENRIQUECIMENTO = {
    # Colunas de redes sociais na Econodata
    "colunas_redes": {
        "instagram": ["INSTAGRAM", "Instagram"],
        "facebook": ["FACEBOOK", "Facebook"],
        "linkedin": ["LINKEDIN", "Linkedin", "LinkedIn"],
        "site": ["SITE", "MELHOR SITE", "SITES", "Website"],
    },
    
    # Classificação de presença digital
    "classificacao": {
        "forte": 3,      # 3+ redes preenchidas
        "media": 2,      # 2 redes
        "fraca": 1,      # 1 rede
        "nula": 0,       # nenhuma
    },
    
    # Verificar se site está ativo (HTTP request) - futuro
    "verificar_site_ativo": False,
}

# =============================================================================
# CONFIGURAÇÕES DE MATCHING (Task 7301)
# =============================================================================

MATCHING = {
    # Threshold mínimo para considerar match
    "threshold_minimo": 0.70,
    
    # Threshold para alta confiança
    "threshold_alta_confianca": 0.85,
    
    # Pesos do algoritmo de similaridade
    "peso_sequencia": 0.6,  # SequenceMatcher
    "peso_tokens": 0.4,      # Jaccard (tokens em comum)
    
    # Bonus/penalidade por cidade
    "bonus_cidade_match": 0.10,
    "penalidade_cidade_diferente": -0.05,
    
    # Termos a remover na normalização
    "termos_remover": [
        "LTDA", "LIMITADA", "S.A.", "S/A", "SA", "ME", "EPP", "EIRELI",
        "CIA", "COMPANHIA", "COMERCIO", "SERVICOS", "INDUSTRIA",
        "GRUPO", "HOLDING", "PARTICIPACOES", "FILIAL", "MATRIZ",
        "DE", "DO", "DA", "DOS", "DAS", "E", "EM", "NO", "NA",
    ],
}

# =============================================================================
# CONFIGURAÇÕES DE SCORING (Task 7302)
# =============================================================================

SCORING = {
    # Pesos dos componentes do score final
    "pesos": {
        "cadastro": 0.15,       # Dados válidos e completos
        "viabilidade": 0.25,   # Faturamento, porte, saúde financeira
        "digital": 0.20,       # Presença em redes sociais
        "midia": 0.25,         # Match com Kantar/Crowley
        "contato": 0.15,       # Telefone e email disponíveis
    },
    
    # Faixas de prioridade
    "faixas_prioridade": {
        "muito_alta": (76, 100),
        "alta": (51, 75),
        "media": (26, 50),
        "baixa": (0, 25),
    },
    
    # Mapeamento de porte para score (0-1)
    "score_porte": {
        "MICRO": 0.2,
        "PEQUENA": 0.4,
        "MÉDIA": 0.6,
        "MEDIA": 0.6,
        "GRANDE": 0.8,
        "ENTERPRISE": 1.0,
    },
    
    # Mapeamento de faturamento para score (0-1)
    "score_faturamento": {
        "Até R$ 81.000": 0.1,
        "R$ 81.001 a R$ 360.000": 0.2,
        "R$ 360.001 a R$ 1.800.000": 0.3,
        "R$ 1.800.001 a R$ 4.800.000": 0.4,
        "R$ 4.800.001 a R$ 10.000.000": 0.5,
        "R$ 10.000.001 a R$ 20.000.000": 0.6,
        "R$ 20.000.001 a R$ 30.000.000": 0.7,
        "R$ 30.000.001 a R$ 50.000.000": 0.8,
        "R$ 50.000.001 a R$ 100.000.000": 0.9,
        "Acima de R$ 100.000.000": 1.0,
    },
}

# =============================================================================
# CONFIGURAÇÕES DE OUTPUT
# =============================================================================

OUTPUT = {
    # Formato do arquivo de saída
    "formato": "xlsx",  # xlsx ou csv
    
    # Nome do arquivo (sem extensão)
    "nome_arquivo": "prospeccao_refinada",
    
    # Incluir timestamp no nome
    "incluir_timestamp": True,
    
    # Gerar abas separadas no Excel
    "abas": {
        "lista_priorizada": True,
        "resumo": True,
        "top_20": True,
        "log": True,
    },
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    "nivel": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "formato": "[%(asctime)s] [%(levelname)s] %(message)s",
    "arquivo": "pipeline.log",
}
