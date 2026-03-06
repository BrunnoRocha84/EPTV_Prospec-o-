"""
Módulo de Utilitários
=====================

Funções auxiliares compartilhadas entre os módulos do pipeline.
"""

import unicodedata
import re
import logging
from difflib import SequenceMatcher
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

# Configura logging
logger = logging.getLogger(__name__)


# =============================================================================
# NORMALIZAÇÃO DE TEXTO
# =============================================================================

def remover_acentos(texto: str) -> str:
    """Remove acentos de uma string."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto: str, upper: bool = True) -> str:
    """
    Normaliza texto para comparação.
    
    - Remove acentos
    - Converte para maiúsculas (opcional)
    - Remove caracteres especiais
    - Remove espaços extras
    """
    if not texto or not isinstance(texto, str):
        return ""
    
    texto = remover_acentos(texto.strip())
    
    if upper:
        texto = texto.upper()
    
    # Remove caracteres especiais, mantém apenas letras, números e espaços
    texto = re.sub(r'[^\w\s]', ' ', texto)
    
    # Remove espaços extras
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


def normalizar_nome_empresa(nome: str, termos_remover: List[str] = None) -> str:
    """
    Normaliza nome de empresa para comparação em fuzzy matching.
    
    Remove termos jurídicos comuns (LTDA, S/A, ME, etc.)
    """
    if not nome or not isinstance(nome, str):
        return ""
    
    # Lista padrão de termos a remover
    if termos_remover is None:
        termos_remover = [
            r'\bLTDA\b', r'\bLIMITADA\b', r'\bS\.?A\.?\b', r'\bS/A\b',
            r'\bME\b', r'\bEPP\b', r'\bEIRELI\b', r'\bSS\b',
            r'\bCIA\b', r'\bCOMPANHIA\b', r'\b& CIA\b',
            r'\bCOMERCIO\b', r'\bCOM\b', r'\bSERVICOS\b', r'\bSERV\b',
            r'\bINDUSTRIA\b', r'\bIND\b', r'\bEMPRESA\b',
            r'\bGRUPO\b', r'\bHOLDING\b', r'\bPARTICIPACOES\b',
            r'\bFILIAL\b', r'\bMATRIZ\b', r'\bUNIDADE\b',
            r'\bDE\b', r'\bDO\b', r'\bDA\b', r'\bDOS\b', r'\bDAS\b',
            r'\bE\b', r'\bEM\b', r'\bNO\b', r'\bNA\b',
        ]
    
    # Normaliza primeiro
    nome = remover_acentos(nome.upper().strip())
    
    # Remove termos
    for termo in termos_remover:
        nome = re.sub(termo, ' ', nome, flags=re.IGNORECASE)
    
    # Remove pontuação
    nome = re.sub(r'[^\w\s]', ' ', nome)
    
    # Remove números isolados
    nome = re.sub(r'\b\d+\b', ' ', nome)
    
    # Remove espaços extras
    nome = re.sub(r'\s+', ' ', nome).strip()
    
    return nome


# =============================================================================
# CNPJ
# =============================================================================

def normalizar_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ, mantendo apenas números."""
    if not cnpj:
        return ""
    return re.sub(r'\D', '', str(cnpj))


def formatar_cnpj(cnpj: str) -> str:
    """Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX."""
    cnpj_limpo = normalizar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        return cnpj_limpo
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ usando algoritmo de dígitos verificadores.
    
    Returns:
        True se CNPJ é válido, False caso contrário
    """
    cnpj_limpo = normalizar_cnpj(cnpj)
    
    if len(cnpj_limpo) != 14:
        return False
    
    # Verifica se todos os dígitos são iguais (inválido)
    if len(set(cnpj_limpo)) == 1:
        return False
    
    # Cálculo do primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj_limpo[i]) * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    digito1 = 0 if resto1 < 2 else 11 - resto1
    
    if int(cnpj_limpo[12]) != digito1:
        return False
    
    # Cálculo do segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(int(cnpj_limpo[i]) * pesos2[i] for i in range(13))
    resto2 = soma2 % 11
    digito2 = 0 if resto2 < 2 else 11 - resto2
    
    return int(cnpj_limpo[13]) == digito2


# =============================================================================
# FUZZY MATCHING
# =============================================================================

def similaridade_sequencia(texto1: str, texto2: str) -> float:
    """Calcula similaridade usando SequenceMatcher (0 a 1)."""
    if not texto1 or not texto2:
        return 0.0
    return SequenceMatcher(None, texto1, texto2).ratio()


def similaridade_tokens(texto1: str, texto2: str) -> float:
    """Calcula similaridade baseada em tokens (Jaccard)."""
    if not texto1 or not texto2:
        return 0.0
    
    tokens1 = set(texto1.split())
    tokens2 = set(texto2.split())
    
    if not tokens1 or not tokens2:
        return 0.0
    
    intersecao = tokens1.intersection(tokens2)
    uniao = tokens1.union(tokens2)
    
    return len(intersecao) / len(uniao)


def calcular_similaridade(
    texto1: str, 
    texto2: str,
    peso_sequencia: float = 0.6,
    peso_tokens: float = 0.4
) -> float:
    """
    Calcula similaridade combinada entre dois textos.
    
    Args:
        texto1: Primeiro texto
        texto2: Segundo texto
        peso_sequencia: Peso para SequenceMatcher
        peso_tokens: Peso para Jaccard
        
    Returns:
        Score de similaridade (0 a 1)
    """
    sim_seq = similaridade_sequencia(texto1, texto2)
    sim_tok = similaridade_tokens(texto1, texto2)
    
    score = (sim_seq * peso_sequencia) + (sim_tok * peso_tokens)
    
    # BONUS: Se a primeira palavra for igual, adiciona bonus
    palavras1 = str(texto1).upper().split()
    palavras2 = str(texto2).upper().split()
    if palavras1 and palavras2 and palavras1[0] == palavras2[0]:
        score = min(1.0, score + 0.15)
    
    # BONUS: Se um nome contem o outro
    t1 = str(texto1).upper()
    t2 = str(texto2).upper()
    if len(t1) > 3 and len(t2) > 3 and (t1 in t2 or t2 in t1):
        score = min(1.0, score + 0.10)
    
    return score


# =============================================================================
# HELPERS GERAIS
# =============================================================================

def encontrar_coluna(df, opcoes: List[str]) -> Optional[str]:
    """
    Encontra coluna no DataFrame por lista de possíveis nomes.
    
    Args:
        df: DataFrame pandas
        opcoes: Lista de possíveis nomes da coluna
        
    Returns:
        Nome da coluna encontrada ou None
    """
    colunas_lower = {col.lower(): col for col in df.columns}
    for opcao in opcoes:
        if opcao.lower() in colunas_lower:
            return colunas_lower[opcao.lower()]
    return None


def gerar_timestamp() -> str:
    """Gera timestamp no formato YYYYMMDD_HHMMSS."""
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def safe_get(dicionario: Dict, chave: str, default: Any = None) -> Any:
    """Acessa valor de dicionário de forma segura."""
    try:
        return dicionario.get(chave, default)
    except (AttributeError, TypeError):
        return default


def is_valid_email(email: str) -> bool:
    """Verifica se string parece ser um email válido."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def is_valid_phone(telefone: str) -> bool:
    """Verifica se string parece ser um telefone válido."""
    if not telefone or not isinstance(telefone, str):
        return False
    # Remove tudo exceto números
    numeros = re.sub(r'\D', '', telefone)
    # Telefone válido: 10 ou 11 dígitos (com DDD)
    return len(numeros) in [10, 11]


def extrair_usuario_instagram(url_ou_usuario: str) -> Optional[str]:
    """Extrai username do Instagram de URL ou texto."""
    if not url_ou_usuario:
        return None
    
    texto = str(url_ou_usuario).strip()
    
    # Se for URL
    match = re.search(r'instagram\.com/([^/?]+)', texto)
    if match:
        return match.group(1)
    
    # Se começar com @
    if texto.startswith('@'):
        return texto[1:]
    
    # Se for só o username (alfanumérico + ponto + underscore)
    if re.match(r'^[\w.]+$', texto):
        return texto
    
    return None


# =============================================================================
# LOGGING HELPERS
# =============================================================================

def setup_logger(nome: str, nivel: str = "INFO") -> logging.Logger:
    """Configura e retorna um logger."""
    logger = logging.getLogger(nome)
    logger.setLevel(getattr(logging, nivel.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
