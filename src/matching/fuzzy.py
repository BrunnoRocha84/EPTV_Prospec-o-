"""
Módulo de Cruzamento com Bases Internas (Fuzzy Matching)
Responsabilidades:
- Fazer fuzzy matching entre Econodata e Kantar/Crowley
- Calcular índice de similaridade
- Identificar empresas que investem em mídia
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import (
    normalizar_nome_empresa,
    calcular_similaridade,
    encontrar_coluna,
    setup_logger
)

# Configura logger
logger = setup_logger("matching", "INFO")

# Configurações de matching
THRESHOLD_MINIMO = 0.70      # Mínimo para considerar match
THRESHOLD_ALTO = 0.85        # Alta confiança


# =============================================================================
# CARREGAMENTO DE BASES DE MÍDIA
# =============================================================================

def carregar_base_midia(caminho: str) -> Optional[pd.DataFrame]:
    """
    Carrega base de mídia (Kantar ou Crowley).
    Detecta formato especial automaticamente.
    """
    if not caminho:
        return None
    
    caminho = Path(caminho)
    if not caminho.exists():
        logger.warning(f"Arquivo não encontrado: {caminho}")
        return None
    
    logger.info(f"Carregando base de mídia: {caminho.name}")
    
    # Tenta carregar detectando cabeçalho
    df = pd.read_excel(caminho, header=None, dtype=str)
    
    # Procura linha do cabeçalho real
    palavras_cabecalho = ['RANK', 'ANUNCIANTE', 'CLIENTE', 'EMPRESA', 'MARCA']
    linha_cabecalho = None
    
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x).upper() for x in row.values if pd.notna(x)])
        if any(palavra in row_str for palavra in palavras_cabecalho):
            linha_cabecalho = idx
            break
    
    if linha_cabecalho is not None:
        df = pd.read_excel(caminho, skiprows=linha_cabecalho, dtype=str)
        logger.info(f"Cabeçalho encontrado na linha {linha_cabecalho}")
    else:
        df = pd.read_excel(caminho, dtype=str)
    
    logger.info(f"Base carregada: {len(df)} registros")
    return df


def extrair_anunciantes(df_midia: pd.DataFrame) -> List[Dict]:
    """
    Extrai lista de anunciantes únicos da base de mídia.
    """
    if df_midia is None:
        return []
    
    # Encontra coluna de anunciante
    col_anunciante = encontrar_coluna(df_midia, [
        'ANUNCIANTE', 'CLIENTE', 'EMPRESA', 'NOME', 'ADVERTISER'
    ])
    
    if not col_anunciante:
        logger.warning("Coluna de anunciante não encontrada")
        return []
    
    # Encontra coluna de cidade/praça (se existir)
    col_cidade = encontrar_coluna(df_midia, [
        'PRAÇA', 'PRACA', 'CIDADE', 'MERCADO', 'CITY'
    ])
    
    # Encontra coluna de valor/inserções (se existir)
    col_valor = encontrar_coluna(df_midia, [
        'TOTAL', 'VALOR', 'INSERÇÕES', 'INSERCOES', 'SPOTS'
    ])
    
    # Agrupa por anunciante
    anunciantes = []
    for nome in df_midia[col_anunciante].dropna().unique():
        if len(str(nome).strip()) < 3:
            continue
            
        subset = df_midia[df_midia[col_anunciante] == nome]
        
        anunciante = {
            'nome': str(nome).strip(),
            'nome_normalizado': normalizar_nome_empresa(str(nome)),
            'cidade': subset[col_cidade].iloc[0] if col_cidade else None,
            'total_registros': len(subset),
        }
        
        # Soma valores se existir coluna
        if col_valor:
            try:
                valores = pd.to_numeric(subset[col_valor], errors='coerce')
                anunciante['total_valor'] = valores.sum()
            except:
                anunciante['total_valor'] = 0
        
        anunciantes.append(anunciante)
    
    logger.info(f"Anunciantes únicos extraídos: {len(anunciantes)}")
    return anunciantes


# =============================================================================
# FUZZY MATCHING
# =============================================================================

def fazer_matching(
    df: pd.DataFrame, 
    anunciantes: List[Dict],
    col_nome: str,
    col_cidade: Optional[str] = None,
    threshold: float = THRESHOLD_MINIMO
) -> pd.DataFrame:
    """
    Faz fuzzy matching entre DataFrame e lista de anunciantes.
    """
    if not anunciantes:
        logger.warning("Lista de anunciantes vazia - sem matching")
        return df
    
    logger.info(f"Iniciando matching com {len(anunciantes)} anunciantes...")
    
    resultados = []
    
    for idx, row in df.iterrows():
        nome_empresa = str(row.get(col_nome, ''))
        nome_normalizado = normalizar_nome_empresa(nome_empresa)
        
        cidade_empresa = None
        if col_cidade and col_cidade in df.columns:
            cidade_empresa = str(row.get(col_cidade, '')).upper()
        
        melhor_match = None
        melhor_score = 0
        
        for anunciante in anunciantes:
            # Calcula similaridade
            score = calcular_similaridade(
                nome_normalizado,
                anunciante['nome_normalizado']
            )
            
            # Bonus se cidade bater
            if cidade_empresa and anunciante.get('cidade'):
                cidade_anunciante = str(anunciante['cidade']).upper()
                if cidade_empresa in cidade_anunciante or cidade_anunciante in cidade_empresa:
                    score = min(1.0, score + 0.1)
            
            if score > melhor_score:
                melhor_score = score
                melhor_match = anunciante
        
        resultados.append({
            'idx': idx,
            'match_encontrado': melhor_score >= threshold,
            'match_score': round(melhor_score, 4),
            'match_nome': melhor_match['nome'] if melhor_match and melhor_score >= threshold else None,
            'match_valor': melhor_match.get('total_valor', 0) if melhor_match and melhor_score >= threshold else 0,
            'match_alta_confianca': melhor_score >= THRESHOLD_ALTO,
        })
    
    return pd.DataFrame(resultados).set_index('idx')


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def cruzar_bases(
    df: pd.DataFrame,
    caminho_kantar: Optional[str] = None,
    caminho_crowley: Optional[str] = None
) -> pd.DataFrame:
    """
    Função principal - cruza Econodata com bases de mídia.
    Chamada pelo main.py
    """
    logger.info("="*50)
    logger.info("CRUZAMENTO COM BASES DE MÍDIA")
    logger.info("="*50)
    
    df = df.copy()
    
    # Encontra coluna de nome na Econodata
    col_nome = encontrar_coluna(df, [
        'NOME FANTASIA', 'NOME_FANTASIA', 'RAZÃO SOCIAL', 'NOME DA EMPRESA'
    ])
    
    col_cidade = encontrar_coluna(df, ['CIDADE', 'MUNICIPIO'])
    
    if not col_nome:
        logger.error("Coluna de nome não encontrada!")
        df['_match_kantar'] = False
        df['_match_crowley'] = False
        df['_tem_match_midia'] = False
        return df
    
    logger.info(f"Coluna de nome: '{col_nome}'")
    
    # === MATCHING COM KANTAR ===
    if caminho_kantar:
        logger.info("-"*50)
        logger.info("Processando KANTAR (TV)...")
        
        df_kantar = carregar_base_midia(caminho_kantar)
        anunciantes_kantar = extrair_anunciantes(df_kantar)
        
        if anunciantes_kantar:
            resultado_kantar = fazer_matching(df, anunciantes_kantar, col_nome, col_cidade)
            
            df['_match_kantar'] = resultado_kantar['match_encontrado']
            df['_kantar_score'] = resultado_kantar['match_score']
            df['_kantar_nome'] = resultado_kantar['match_nome']
            df['_kantar_valor'] = resultado_kantar['match_valor']
            
            matches = df['_match_kantar'].sum()
            logger.info(f"Matches Kantar: {matches}/{len(df)}")
        else:
            df['_match_kantar'] = False
            df['_kantar_score'] = 0
            df['_kantar_nome'] = None
            df['_kantar_valor'] = 0
    else:
        logger.info("Base Kantar não fornecida")
        df['_match_kantar'] = False
        df['_kantar_score'] = 0
        df['_kantar_nome'] = None
        df['_kantar_valor'] = 0
    
    # === MATCHING COM CROWLEY ===
    if caminho_crowley:
        logger.info("-"*50)
        logger.info("Processando CROWLEY (Rádio)...")
        
        df_crowley = carregar_base_midia(caminho_crowley)
        anunciantes_crowley = extrair_anunciantes(df_crowley)
        
        if anunciantes_crowley:
            resultado_crowley = fazer_matching(df, anunciantes_crowley, col_nome, col_cidade)
            
            df['_match_crowley'] = resultado_crowley['match_encontrado']
            df['_crowley_score'] = resultado_crowley['match_score']
            df['_crowley_nome'] = resultado_crowley['match_nome']
            
            matches = df['_match_crowley'].sum()
            logger.info(f"Matches Crowley: {matches}/{len(df)}")
        else:
            df['_match_crowley'] = False
            df['_crowley_score'] = 0
            df['_crowley_nome'] = None
    else:
        logger.info("Base Crowley não fornecida")
        df['_match_crowley'] = False
        df['_crowley_score'] = 0
        df['_crowley_nome'] = None
    
    # === CONSOLIDA ===
    df['_tem_match_midia'] = df['_match_kantar'] | df['_match_crowley']
    
    total_com_midia = df['_tem_match_midia'].sum()
    logger.info("-"*50)
    logger.info(f"TOTAL com match em mídia: {total_com_midia}/{len(df)}")
    logger.info("-"*50)
    
    return df


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    from src.ingestao import carregar_base
    from src.validacao import validar_empresas
    from src.enriquecimento import avaliar_presenca_digital
    
    if len(sys.argv) > 1:
        arquivo_econodata = sys.argv[1]
        arquivo_kantar = sys.argv[2] if len(sys.argv) > 2 else None
        arquivo_crowley = sys.argv[3] if len(sys.argv) > 3 else None
        
        # Pipeline até aqui
        df = carregar_base(arquivo_econodata)
        df = validar_empresas(df)
        df = avaliar_presenca_digital(df)
        
        # Matching
        df = cruzar_bases(df, arquivo_kantar, arquivo_crowley)
        
        print(f"\nColunas de matching:")
        print([c for c in df.columns if 'match' in c.lower() or 'kantar' in c.lower() or 'crowley' in c.lower()])
        
        # Mostra matches encontrados
        if df['_tem_match_midia'].sum() > 0:
            print(f"\nEmpresas com match em mídia:")
            cols = ['NOME FANTASIA', '_match_kantar', '_kantar_nome', '_kantar_score']
            print(df[df['_tem_match_midia']][cols].head(10))
        else:
            print("\nNenhum match encontrado com as bases de mídia.")
    else:
        print("Uso: python fuzzy.py <econodata> [kantar] [crowley]")
        print("Exemplo: python fuzzy.py ../../data/input/Saude.xlsx ../../data/input/kantar.xlsx")
