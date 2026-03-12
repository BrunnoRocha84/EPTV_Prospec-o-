"""
Módulo de Regras de Decisão (Scoring)

Responsabilidades:
- Calcular score de cada componente
- Calcular score final ponderado
- Classificar prioridade
- Gerar output final
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import (
    encontrar_coluna,
    gerar_timestamp,
    setup_logger
)

# Configura logger
logger = setup_logger("scoring", "INFO")


# =============================================================================
# CONFIGURAÇÃO DOS PESOS
# =============================================================================

PESOS = {
    'cadastro': 0.15,      # Dados válidos e completos
    'viabilidade': 0.25,   # Faturamento, porte
    'digital': 0.20,       # Presença em redes sociais
    'midia': 0.25,         # Match com Kantar/Crowley/Painéis
    'contato': 0.15,       # Telefone e email
}

# Mapeamento de porte para score
SCORE_PORTE = {
    'MICRO': 0.2,
    'PEQUENO': 0.3,
    'PEQUENA': 0.3,
    'MEDIO': 0.5,
    'MÉDIA': 0.5,
    'MEDIA': 0.5,
    'GRANDE': 0.8,
    'ENTERPRISE': 1.0,
}


# =============================================================================
# CÁLCULO DOS SCORES INDIVIDUAIS
# =============================================================================

def calcular_score_cadastro(df: pd.DataFrame) -> pd.Series:
    """
    Score de qualidade cadastral (0-100).
    Baseado em: CNPJ válido, empresa ativa, CNAE preenchido.
    """
    score = pd.Series(0.0, index=df.index)
    
    # CNPJ válido: +40 pontos
    if '_cnpj_valido' in df.columns:
        score += df['_cnpj_valido'].astype(float) * 40
    
    # Empresa ativa: +40 pontos
    if '_empresa_ativa' in df.columns:
        score += df['_empresa_ativa'].astype(float) * 40
    
    # CNAE preenchido: +20 pontos
    if '_cnae_preenchido' in df.columns:
        score += df['_cnae_preenchido'].astype(float) * 20
    
    return score


def calcular_score_viabilidade(df: pd.DataFrame) -> pd.Series:
    """
    Score de viabilidade financeira (0-100).
    Baseado em: porte, faturamento.
    """
    score = pd.Series(50.0, index=df.index)  # Base 50 se não tiver info
    
    # Porte
    col_porte = encontrar_coluna(df, ['PORTE', 'PORTE ESTIMADO'])
    if col_porte:
        def mapear_porte(valor):
            if pd.isna(valor):
                return 0.5
            return SCORE_PORTE.get(str(valor).upper().strip(), 0.5)
        
        score = df[col_porte].apply(mapear_porte) * 100
    
    return score


def calcular_score_digital(df: pd.DataFrame) -> pd.Series:
    """
    Score de presença digital (0-100).
    Baseado em: quantidade de redes sociais.
    """
    score = pd.Series(0.0, index=df.index)
    
    if '_qtd_redes' in df.columns:
        # 0 redes = 0, 1 = 25, 2 = 50, 3 = 75, 4+ = 100
        score = (df['_qtd_redes'].clip(0, 4) / 4) * 100
    
    return score


def calcular_score_midia(df: pd.DataFrame) -> pd.Series:
    """
    Score de investimento em mídia (0-100).
    Baseado em: match com Kantar/Crowley/Painéis.
    """
    score = pd.Series(0.0, index=df.index)
    
    # Match com Kantar: +35 pontos
    if '_match_kantar' in df.columns:
        score += df['_match_kantar'].astype(float) * 35
    
    # Match com Crowley: +35 pontos
    if '_match_crowley' in df.columns:
        score += df['_match_crowley'].astype(float) * 35
        
    # Match com Painéis: +30 pontos
    if '_match_paineis' in df.columns:
        score += df['_match_paineis'].astype(float) * 30
    
    # Se tiver score de confiança alto em qualquer um, bonus
    bonus = pd.Series(0.0, index=df.index)
    
    if '_kantar_score' in df.columns:
        bonus += (df['_kantar_score'] > 0.85).astype(float) * 5
        
    if '_crowley_score' in df.columns:
        bonus += (df['_crowley_score'] > 0.85).astype(float) * 5
        
    if '_paineis_score' in df.columns:
        bonus += (df['_paineis_score'] > 0.85).astype(float) * 5
        
    score = (score + bonus).clip(0, 100)
    
    return score


def calcular_score_contato(df: pd.DataFrame) -> pd.Series:
    """
    Score de dados de contato (0-100).
    Baseado em: telefone válido, email válido.
    """
    score = pd.Series(0.0, index=df.index)
    
    # Telefone válido: +50 pontos
    if '_telefone_valido' in df.columns:
        score += df['_telefone_valido'].astype(float) * 50
    
    # Email válido: +50 pontos
    if '_email_valido' in df.columns:
        score += df['_email_valido'].astype(float) * 50
    
    return score


# =============================================================================
# SCORE FINAL E PRIORIZAÇÃO
# =============================================================================

def calcular_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Função principal - calcula todos os scores e prioridade.
    Chamada pelo main.py
    """
    logger.info("="*50)
    logger.info("CALCULANDO SCORES DE PRIORIZAÇÃO")
    logger.info("="*50)
    
    df = df.copy()
    
    # Calcula scores individuais
    logger.info("Calculando scores individuais...")
    
    df['_score_cadastro'] = calcular_score_cadastro(df).round(1)
    df['_score_viabilidade'] = calcular_score_viabilidade(df).round(1)
    df['_score_digital'] = calcular_score_digital(df).round(1)
    df['_score_midia'] = calcular_score_midia(df).round(1)
    df['_score_contato'] = calcular_score_contato(df).round(1)
    
    # Score final ponderado
    logger.info("Calculando score final ponderado...")
    logger.info(f"Pesos: {PESOS}")
    
    df['_score_final'] = (
        df['_score_cadastro'] * PESOS['cadastro'] +
        df['_score_viabilidade'] * PESOS['viabilidade'] +
        df['_score_digital'] * PESOS['digital'] +
        df['_score_midia'] * PESOS['midia'] +
        df['_score_contato'] * PESOS['contato']
    ).round(1)
    
    # Classificação de prioridade
    def classificar_prioridade(score):
        if score >= 70:
            return 'MUITO_ALTA'
        elif score >= 50:
            return 'ALTA'
        elif score >= 30:
            return 'MEDIA'
        else:
            return 'BAIXA'
    
    df['_prioridade'] = df['_score_final'].apply(classificar_prioridade)
    
    # Estatísticas
    logger.info("-"*50)
    logger.info("RESUMO DOS SCORES:")
    logger.info(f"  • Score médio: {df['_score_final'].mean():.1f}")
    logger.info(f"  • Score mínimo: {df['_score_final'].min():.1f}")
    logger.info(f"  • Score máximo: {df['_score_final'].max():.1f}")
    logger.info("-"*50)
    logger.info("DISTRIBUIÇÃO DE PRIORIDADES:")
    for prio in ['MUITO_ALTA', 'ALTA', 'MEDIA', 'BAIXA']:
        qtd = (df['_prioridade'] == prio).sum()
        pct = qtd / len(df) * 100
        logger.info(f"  • {prio}: {qtd} ({pct:.1f}%)")
    logger.info("-"*50)
    
    return df


# =============================================================================
# GERAÇÃO DO OUTPUT
# =============================================================================

def gerar_output(df: pd.DataFrame, caminho_output: str) -> str:
    """
    Gera arquivo Excel com resultado final.
    """
    logger.info(f"Gerando output: {caminho_output}")
    
    # Ordena por score (maior primeiro)
    df = df.sort_values('_score_final', ascending=False)
    
    # Seleciona colunas principais para output
    colunas_identificacao = ['CNPJ', 'RAZÃO SOCIAL', 'NOME FANTASIA', 'CIDADE', 'UF']
    colunas_contato = ['MELHOR TELEFONE', 'MELHOR EMAIL', 'MELHOR SITE']
    colunas_empresa = ['SETOR AMIGÁVEL', 'PORTE ESTIMADO', 'FATURAMENTO PRESUMIDO PARA ESTE CNPJ', 'SITUAÇÃO CADASTRAL']
    colunas_redes = ['INSTAGRAM', 'FACEBOOK', 'LINKEDIN', 'WHATSAPP']
    colunas_scores = [
        '_score_final', '_prioridade',
        '_score_cadastro', '_score_viabilidade', '_score_digital', 
        '_score_midia', '_score_contato',
        '_empresa_ativa', '_tem_contato', '_presenca_digital',
        '_match_kantar', '_match_crowley', '_match_paineis'
    ]
    
    # Filtra colunas que existem
    todas_colunas = colunas_identificacao + colunas_contato + colunas_empresa + colunas_redes + colunas_scores
    colunas_existentes = [c for c in todas_colunas if c in df.columns]
    
    df_output = df[colunas_existentes].copy()
    
    # Renomeia colunas de score para nomes amigáveis
    renomear = {
    'RAZÃO SOCIAL': 'RAZAO_SOCIAL',
    'NOME FANTASIA': 'NOME_FANTASIA',
    'SETOR AMIGÁVEL': 'SETOR',
    'MELHOR TELEFONE': 'MELHOR_TELEFONE',
    'MELHOR SITE': 'MELHOR_SITE',
    'PORTE ESTIMADO': 'PORTE_ESTIMADO',
    'FATURAMENTO PRESUMIDO PARA ESTE CNPJ': 'FATURAMENTO_PRESUMIDO',
    'SITUAÇÃO CADASTRAL': 'SITUACAO_CADASTRAL',
    '_score_final': 'SCORE_FINAL',
    '_prioridade': 'PRIORIDADE',
    '_score_cadastro': 'SCORE_CADASTRO',
    '_score_viabilidade': 'SCORE_VIABILIDADE',
    '_score_digital': 'SCORE_DIGITAL',
    '_score_midia': 'SCORE_MIDIA',
    '_score_contato': 'SCORE_CONTATO',
    '_empresa_ativa': 'EMPRESA_ATIVA',
    '_tem_contato': 'TEM_CONTATO',
    '_presenca_digital': 'PRESENCA_DIGITAL',
    '_match_kantar': 'ANUNCIA_TV',
    '_match_crowley': 'ANUNCIA_RADIO',
    '_match_paineis': 'ANUNCIA_PAINEIS',
}
    df_output = df_output.rename(columns=renomear)
    
    # Cria arquivo Excel com múltiplas abas
    caminho = Path(caminho_output)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
        # Aba principal - Lista completa priorizada
        df_output.to_excel(writer, sheet_name='Lista Priorizada', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame({
            'MÉTRICA': [
                'Total de empresas',
                'Empresas ativas',
                'Com telefone válido',
                'Com email válido',
                'Com presença digital (1+ rede)',
                'Com match em mídia',
                'Score médio',
                'Prioridade MUITO_ALTA',
                'Prioridade ALTA',
                'Prioridade MEDIA',
                'Prioridade BAIXA',
            ],
            'VALOR': [
                len(df),
                df['_empresa_ativa'].sum() if '_empresa_ativa' in df.columns else 'N/A',
                df['_telefone_valido'].sum() if '_telefone_valido' in df.columns else 'N/A',
                df['_email_valido'].sum() if '_email_valido' in df.columns else 'N/A',
                (df['_qtd_redes'] > 0).sum() if '_qtd_redes' in df.columns else 'N/A',
                df['_tem_match_midia'].sum() if '_tem_match_midia' in df.columns else 0,
                f"{df['_score_final'].mean():.1f}",
                (df['_prioridade'] == 'MUITO_ALTA').sum(),
                (df['_prioridade'] == 'ALTA').sum(),
                (df['_prioridade'] == 'MEDIA').sum(),
                (df['_prioridade'] == 'BAIXA').sum(),
            ]
        })
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
        
        # Aba Top 20
        df_output.head(20).to_excel(writer, sheet_name='Top 20', index=False)
    
    logger.info(f"✅ Arquivo gerado: {caminho}")
    logger.info(f"   • {len(df_output)} registros")
    logger.info(f"   • 3 abas: Lista Priorizada, Resumo, Top 20")
    
    return str(caminho)


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    from src.ingestao import carregar_base
    from src.validacao import validar_empresas
    from src.enriquecimento import avaliar_presenca_digital
    from src.matching import cruzar_bases
    
    if len(sys.argv) > 1:
        arquivo_econodata = sys.argv[1]
        arquivo_kantar = sys.argv[2] if len(sys.argv) > 2 else None
        arquivo_crowley = sys.argv[3] if len(sys.argv) > 3 else None
        pasta_paineis = sys.argv[4] if len(sys.argv) > 4 else None
        
        # Pipeline completo
        df = carregar_base(arquivo_econodata)
        df = validar_empresas(df)
        df = avaliar_presenca_digital(df)
        df = cruzar_bases(df, arquivo_kantar, arquivo_crowley, pasta_paineis)
        
        # Scoring
        df = calcular_score(df)
        
        # Gera output
        timestamp = gerar_timestamp()
        output_path = f"data/output/prospeccao_{timestamp}.xlsx"
        gerar_output(df, output_path)
        
        print(f"\n🎉 Pipeline completo executado!")
        print(f"📁 Arquivo gerado: {output_path}")
    else:
        print("Uso: python scoring.py <econodata> [kantar] [crowley] [pasta_paineis]")
