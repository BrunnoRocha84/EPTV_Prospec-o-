"""
Módulo de Validação de Atividade / Existência

Responsabilidades:
- Verificar situação cadastral da empresa
- Validar dados de contato (telefone, email)
- Marcar empresas como ativa/inativa
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import (
    encontrar_coluna,
    is_valid_email,
    is_valid_phone,
    setup_logger
)

# Configura logger
logger = setup_logger("validacao", "INFO")


# =============================================================================
# VALIDAÇÃO DE SITUAÇÃO CADASTRAL
# =============================================================================

def validar_situacao_cadastral(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica situação cadastral das empresas.
    Usa dados já presentes na Econodata.
    """
    logger.info("Validando situação cadastral...")
    df = df.copy()
    
    # Procura coluna de situação
    col_situacao = encontrar_coluna(df, [
        'SITUAÇÃO CADASTRAL', 'SITUACAO CADASTRAL', 
        'SITUACAO', 'STATUS'
    ])
    
    if col_situacao:
        logger.info(f"Coluna situação: '{col_situacao}'")
        
        # Valores que indicam empresa ativa
        valores_ativos = ['ATIVA', 'ATIVO', 'REGULAR', 'ATIVA - REGULAR']
        
        # Normaliza e verifica
        df['_situacao_cadastral'] = df[col_situacao].fillna('').str.strip().str.upper()
        df['_empresa_ativa'] = df['_situacao_cadastral'].isin(valores_ativos)
        
        # Estatísticas
        total = len(df)
        ativas = df['_empresa_ativa'].sum()
        inativas = total - ativas
        
        logger.info(f"Empresas ativas: {ativas}/{total} ({ativas/total*100:.1f}%)")
        if inativas > 0:
            logger.warning(f"Empresas inativas: {inativas}")
    else:
        logger.warning("Coluna de situação não encontrada - assumindo todas ativas")
        df['_situacao_cadastral'] = 'NAO_INFORMADO'
        df['_empresa_ativa'] = True
    
    return df


# =============================================================================
# VALIDAÇÃO DE CONTATOS
# =============================================================================

def validar_contatos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida dados de contato (telefone e email).
    """
    logger.info("Validando dados de contato...")
    df = df.copy()
    
    # === TELEFONE ===
    col_telefone = encontrar_coluna(df, [
        'MELHOR TELEFONE', 'TELEFONE', 'FONE', 'TEL'
    ])
    
    if col_telefone:
        df['_telefone_valido'] = df[col_telefone].apply(
            lambda x: is_valid_phone(str(x)) if pd.notna(x) else False
        )
        validos = df['_telefone_valido'].sum()
        logger.info(f"Telefones válidos: {validos}/{len(df)}")
    else:
        df['_telefone_valido'] = False
        logger.warning("Coluna de telefone não encontrada")
    
    # === EMAIL ===
    col_email = encontrar_coluna(df, [
        'MELHOR EMAIL', 'EMAIL', 'E-MAIL', 'EMAIL RECEITA FEDERAL'
    ])
    
    if col_email:
        df['_email_valido'] = df[col_email].apply(
            lambda x: is_valid_email(str(x)) if pd.notna(x) else False
        )
        validos = df['_email_valido'].sum()
        logger.info(f"Emails válidos: {validos}/{len(df)}")
    else:
        df['_email_valido'] = False
        logger.warning("Coluna de email não encontrada")
    
    # === TEM CONTATO (telefone OU email) ===
    df['_tem_contato'] = df['_telefone_valido'] | df['_email_valido']
    
    com_contato = df['_tem_contato'].sum()
    logger.info(f"Com algum contato válido: {com_contato}/{len(df)}")
    
    return df


# =============================================================================
# VALIDAÇÃO DE CNAE
# =============================================================================

def validar_cnae(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se CNAE está preenchido.
    """
    logger.info("Validando CNAE...")
    df = df.copy()
    
    col_cnae = encontrar_coluna(df, [
        'COD ATIVIDADE ECONÔMICA', 'CNAE', 'COD ATIVIDADE',
        'ATIVIDADE ECONÔMICA'
    ])
    
    if col_cnae:
        df['_cnae_preenchido'] = df[col_cnae].notna() & (df[col_cnae] != '')
        preenchidos = df['_cnae_preenchido'].sum()
        logger.info(f"CNAE preenchido: {preenchidos}/{len(df)}")
    else:
        df['_cnae_preenchido'] = False
        logger.warning("Coluna CNAE não encontrada")
    
    return df


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def validar_empresas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Função principal - executa todas as validações.
    Chamada pelo main.py
    """
    logger.info("="*50)
    logger.info("INICIANDO VALIDAÇÕES")
    logger.info("="*50)
    
    df = validar_situacao_cadastral(df)
    df = validar_contatos(df)
    df = validar_cnae(df)
    
    # Resumo
    logger.info("-"*50)
    logger.info("RESUMO DAS VALIDAÇÕES:")
    logger.info(f"  • Empresas ativas: {df['_empresa_ativa'].sum()}")
    logger.info(f"  • Com telefone válido: {df['_telefone_valido'].sum()}")
    logger.info(f"  • Com email válido: {df['_email_valido'].sum()}")
    logger.info(f"  • Com CNAE preenchido: {df['_cnae_preenchido'].sum()}")
    logger.info("-"*50)
    
    return df


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    # Teste: carrega base e valida
    from src.ingestao import carregar_base
    
    if len(sys.argv) > 1:
        df = carregar_base(sys.argv[1])
        df = validar_empresas(df)
        
        print(f"\nColunas adicionadas:")
        print([c for c in df.columns if c.startswith('_')])
    else:
        print("Uso: python validacao.py <arquivo>")
