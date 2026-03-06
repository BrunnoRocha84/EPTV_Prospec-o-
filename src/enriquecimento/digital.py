"""
Módulo de Enriquecimento Digital

Responsabilidades:
- Verificar presença em redes sociais
- Classificar nível de presença digital
- Extrair usernames de redes sociais
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import (
    encontrar_coluna,
    extrair_usuario_instagram,
    setup_logger
)

# Configura logger
logger = setup_logger("enriquecimento", "INFO")


# =============================================================================
# VERIFICAÇÃO DE REDES SOCIAIS
# =============================================================================

def verificar_redes_sociais(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica presença em cada rede social.
    """
    logger.info("Verificando redes sociais...")
    df = df.copy()
    
    # === INSTAGRAM ===
    col_insta = encontrar_coluna(df, ['INSTAGRAM', 'INSTA'])
    if col_insta:
        df['_tem_instagram'] = df[col_insta].apply(_campo_preenchido)
        df['_instagram_user'] = df[col_insta].apply(extrair_usuario_instagram)
        logger.info(f"Com Instagram: {df['_tem_instagram'].sum()}")
    else:
        df['_tem_instagram'] = False
        df['_instagram_user'] = None
    
    # === FACEBOOK ===
    col_face = encontrar_coluna(df, ['FACEBOOK', 'FB'])
    if col_face:
        df['_tem_facebook'] = df[col_face].apply(_campo_preenchido)
        logger.info(f"Com Facebook: {df['_tem_facebook'].sum()}")
    else:
        df['_tem_facebook'] = False
    
    # === LINKEDIN ===
    col_linkedin = encontrar_coluna(df, ['LINKEDIN'])
    if col_linkedin:
        df['_tem_linkedin'] = df[col_linkedin].apply(_campo_preenchido)
        logger.info(f"Com LinkedIn: {df['_tem_linkedin'].sum()}")
    else:
        df['_tem_linkedin'] = False
    
    # === SITE ===
    col_site = encontrar_coluna(df, ['MELHOR SITE', 'SITE', 'SITES', 'WEBSITE'])
    if col_site:
        df['_tem_site'] = df[col_site].apply(_campo_preenchido)
        logger.info(f"Com Site: {df['_tem_site'].sum()}")
    else:
        df['_tem_site'] = False
    
    # === WHATSAPP ===
    col_whats = encontrar_coluna(df, ['WHATSAPP', 'WHATS'])
    if col_whats:
        df['_tem_whatsapp'] = df[col_whats].apply(_campo_preenchido)
        logger.info(f"Com WhatsApp: {df['_tem_whatsapp'].sum()}")
    else:
        df['_tem_whatsapp'] = False
    
    return df


def _campo_preenchido(valor) -> bool:
    """Verifica se campo está preenchido (não vazio/nulo)."""
    if pd.isna(valor):
        return False
    valor_str = str(valor).strip()
    return len(valor_str) > 3  # Mínimo de 4 caracteres


# =============================================================================
# CLASSIFICAÇÃO DE PRESENÇA DIGITAL
# =============================================================================

def classificar_presenca_digital(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica o nível de presença digital.
    
    Níveis:
    - FORTE: 3+ redes
    - MEDIA: 2 redes
    - FRACA: 1 rede
    - NULA: 0 redes
    """
    logger.info("Classificando presença digital...")
    df = df.copy()
    
    # Conta quantas redes tem
    colunas_redes = ['_tem_instagram', '_tem_facebook', '_tem_linkedin', '_tem_site']
    
    # Garante que colunas existem
    for col in colunas_redes:
        if col not in df.columns:
            df[col] = False
    
    df['_qtd_redes'] = (
        df['_tem_instagram'].astype(int) +
        df['_tem_facebook'].astype(int) +
        df['_tem_linkedin'].astype(int) +
        df['_tem_site'].astype(int)
    )
    
    # Classifica
    def classificar(qtd):
        if qtd >= 3:
            return 'FORTE'
        elif qtd == 2:
            return 'MEDIA'
        elif qtd == 1:
            return 'FRACA'
        else:
            return 'NULA'
    
    df['_presenca_digital'] = df['_qtd_redes'].apply(classificar)
    
    # Estatísticas
    logger.info("Distribuição de presença digital:")
    for nivel in ['FORTE', 'MEDIA', 'FRACA', 'NULA']:
        qtd = (df['_presenca_digital'] == nivel).sum()
        pct = qtd / len(df) * 100
        logger.info(f"  • {nivel}: {qtd} ({pct:.1f}%)")
    
    return df


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def avaliar_presenca_digital(df: pd.DataFrame) -> pd.DataFrame:
    """
    Função principal - avalia presença digital completa.
    Chamada pelo main.py
    """
    logger.info("="*50)
    logger.info("AVALIANDO PRESENÇA DIGITAL")
    logger.info("="*50)
    
    df = verificar_redes_sociais(df)
    df = classificar_presenca_digital(df)
    
    # Resumo
    media_redes = df['_qtd_redes'].mean()
    logger.info("-"*50)
    logger.info(f"Média de redes por empresa: {media_redes:.2f}")
    logger.info("-"*50)
    
    return df


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    from src.ingestao import carregar_base
    from src.validacao import validar_empresas
    
    if len(sys.argv) > 1:
        # Carrega e valida
        df = carregar_base(sys.argv[1])
        df = validar_empresas(df)
        
        # Enriquece
        df = avaliar_presenca_digital(df)
        
        print(f"\nColunas de presença digital:")
        print([c for c in df.columns if 'tem_' in c or 'presenca' in c or 'qtd_' in c])
        
        print(f"\nExemplo de dados:")
        cols = ['NOME FANTASIA', '_tem_instagram', '_tem_facebook', '_tem_linkedin', '_tem_site', '_qtd_redes', '_presenca_digital']
        cols_existentes = [c for c in cols if c in df.columns]
        print(df[cols_existentes].head(10))
    else:
        print("Uso: python digital.py <arquivo>")
