"""
Módulo de Ingestão e Preparação da Base - EPTV Prospecção

Responsabilidades:
- Carregar arquivos Excel/CSV
- Normalizar CNPJs
- Remover duplicatas
- Mapear colunas automaticamente
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import logging

# Importa utilitários do projeto
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import (
    normalizar_cnpj,
    validar_cnpj,
    encontrar_coluna,
    setup_logger
)

# Configura logger
logger = setup_logger("ingestao", "INFO")


# =============================================================================
# FUNÇÕES DE CARREGAMENTO
# =============================================================================

def carregar_arquivo(caminho: str) -> pd.DataFrame:
    """
    Carrega arquivo Excel ou CSV.
    
    Args:
        caminho: Caminho para o arquivo
        
    Returns:
        DataFrame com dados carregados
        
    Raises:
        FileNotFoundError: Se arquivo não existe
        ValueError: Se extensão não é suportada
    """
    caminho = Path(caminho)
    
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    
    extensao = caminho.suffix.lower()
    
    logger.info(f"Carregando arquivo: {caminho.name}")
    
    if extensao in ['.xlsx', '.xls']:
        # Tenta detectar se tem cabeçalho especial (como Crowley)
        df = _carregar_excel(caminho)
    elif extensao == '.csv':
        df = _carregar_csv(caminho)
    else:
        raise ValueError(f"Extensão não suportada: {extensao}. Use .xlsx, .xls ou .csv")
    
    logger.info(f"Arquivo carregado: {len(df)} linhas, {len(df.columns)} colunas")
    
    return df


def _carregar_excel(caminho: Path) -> pd.DataFrame:
    """Carrega arquivo Excel com detecção automática de cabeçalho e aba."""
    
    # Primeiro, verifica as abas disponíveis
    xlsx = pd.ExcelFile(caminho)
    abas = xlsx.sheet_names
    logger.info(f"Abas encontradas: {abas}")
    
    # Define qual aba carregar
    # Prioridade: "Empresas" > primeira aba que não seja "Documentação"
    aba_dados = None
    
    if "Empresas" in abas:
        aba_dados = "Empresas"
        logger.info("Usando aba 'Empresas' (dados principais)")
    else:
        # Procura primeira aba que não seja documentação/metadados
        abas_excluir = ['documentação', 'documentacao', 'metadata', 'info', 'sobre']
        for aba in abas:
            if aba.lower() not in abas_excluir:
                aba_dados = aba
                break
        
        if aba_dados is None:
            aba_dados = abas[0]  # Fallback para primeira aba
        
        logger.info(f"Usando aba '{aba_dados}'")
    
    # Carrega a aba selecionada
    df = pd.read_excel(caminho, sheet_name=aba_dados, dtype=str)
    
    # Verifica se primeira linha parece ser cabeçalho real
    # (se não tiver muitos NaN e não for texto longo)
    primeira_linha = df.iloc[0] if len(df) > 0 else None
    
    if primeira_linha is not None:
        # Se primeira coluna tiver texto muito longo, pode ser cabeçalho especial
        primeiro_valor = str(primeira_linha.iloc[0]) if pd.notna(primeira_linha.iloc[0]) else ""
        
        if len(primeiro_valor) > 50 or "CROWLEY" in primeiro_valor.upper():
            # Arquivo tipo Crowley - procura linha do cabeçalho real
            logger.info("Detectado formato especial (tipo Crowley), buscando cabeçalho...")
            df = _encontrar_cabecalho_real(caminho, aba_dados)
    
    return df


def _encontrar_cabecalho_real(caminho: Path, aba: str = None) -> pd.DataFrame:
    """Encontra linha do cabeçalho real em arquivos com formato especial."""
    
    # Lê sem cabeçalho
    if aba:
        df_raw = pd.read_excel(caminho, sheet_name=aba, header=None, dtype=str)
    else:
        df_raw = pd.read_excel(caminho, header=None, dtype=str)
    
    # Procura linha que parece ser cabeçalho (tem "RANK", "CNPJ", "ANUNCIANTE", etc)
    palavras_cabecalho = ['RANK', 'CNPJ', 'ANUNCIANTE', 'EMPRESA', 'NOME', 'RAZAO']
    
    linha_cabecalho = None
    for idx, row in df_raw.iterrows():
        row_str = ' '.join([str(x).upper() for x in row.values if pd.notna(x)])
        if any(palavra in row_str for palavra in palavras_cabecalho):
            linha_cabecalho = idx
            break
    
    if linha_cabecalho is not None:
        logger.info(f"Cabeçalho encontrado na linha {linha_cabecalho}")
        if aba:
            df = pd.read_excel(caminho, sheet_name=aba, skiprows=linha_cabecalho, dtype=str)
        else:
            df = pd.read_excel(caminho, skiprows=linha_cabecalho, dtype=str)
    else:
        logger.warning("Cabeçalho não detectado, usando primeira linha")
        if aba:
            df = pd.read_excel(caminho, sheet_name=aba, dtype=str)
        else:
            df = pd.read_excel(caminho, dtype=str)
    
    return df


def _carregar_csv(caminho: Path) -> pd.DataFrame:
    """Carrega arquivo CSV com detecção de separador."""
    
    # Tenta diferentes separadores
    separadores = [',', ';', '\t']
    
    for sep in separadores:
        try:
            df = pd.read_csv(caminho, sep=sep, dtype=str, encoding='utf-8')
            if len(df.columns) > 1:
                logger.info(f"CSV carregado com separador '{sep}'")
                return df
        except:
            continue
    
    # Tenta com encoding latin-1
    for sep in separadores:
        try:
            df = pd.read_csv(caminho, sep=sep, dtype=str, encoding='latin-1')
            if len(df.columns) > 1:
                logger.info(f"CSV carregado com separador '{sep}' e encoding latin-1")
                return df
        except:
            continue
    
    # Fallback
    return pd.read_csv(caminho, dtype=str)


# =============================================================================
# FUNÇÕES DE PREPARAÇÃO
# =============================================================================

def preparar_base(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara a base para processamento.
    
    Etapas:
    1. Mapeia colunas importantes
    2. Normaliza CNPJs
    3. Remove duplicatas
    4. Adiciona colunas de controle
    
    Args:
        df: DataFrame carregado
        
    Returns:
        DataFrame preparado
    """
    logger.info("Iniciando preparação da base...")
    
    df = df.copy()
    registros_inicial = len(df)
    
    # 1. Mapeia coluna de CNPJ
    col_cnpj = _mapear_coluna_cnpj(df)
    
    if col_cnpj:
        # 2. Normaliza CNPJs
        df = _normalizar_cnpjs(df, col_cnpj)
        
        # 3. Remove duplicatas
        df = _remover_duplicatas(df)
    else:
        logger.warning("Coluna CNPJ não encontrada - base pode ser de mídia (Kantar/Crowley)")
        df['_cnpj_normalizado'] = None
        df['_cnpj_valido'] = False
    
    # 4. Adiciona colunas de controle
    df['_registro_id'] = range(1, len(df) + 1)
    
    registros_final = len(df)
    removidos = registros_inicial - registros_final
    
    logger.info(f"Preparação concluída: {registros_final} registros ({removidos} removidos)")
    
    return df


def _mapear_coluna_cnpj(df: pd.DataFrame) -> Optional[str]:
    """Encontra a coluna de CNPJ no DataFrame."""
    
    opcoes = ['CNPJ', 'cnpj', 'Cnpj', 'CNPJ_EMPRESA', 'NR_CNPJ', 'NUM_CNPJ']
    col = encontrar_coluna(df, opcoes)
    
    if col:
        logger.info(f"Coluna CNPJ mapeada: '{col}'")
    else:
        logger.warning("Coluna CNPJ não encontrada")
    
    return col


def _normalizar_cnpjs(df: pd.DataFrame, col_cnpj: str) -> pd.DataFrame:
    """Normaliza e valida CNPJs."""
    
    logger.info("Normalizando CNPJs...")
    
    # Normaliza (remove pontuação)
    df['_cnpj_normalizado'] = df[col_cnpj].apply(normalizar_cnpj)
    
    # Valida
    df['_cnpj_valido'] = df['_cnpj_normalizado'].apply(validar_cnpj)
    
    total = len(df)
    validos = df['_cnpj_valido'].sum()
    invalidos = total - validos
    
    logger.info(f"CNPJs válidos: {validos}/{total} ({validos/total*100:.1f}%)")
    
    if invalidos > 0:
        logger.warning(f"CNPJs inválidos: {invalidos}")
    
    return df


def _remover_duplicatas(df: pd.DataFrame) -> pd.DataFrame:
    """Remove registros duplicados por CNPJ."""
    
    antes = len(df)
    
    # Mantém primeiro registro de cada CNPJ (assumindo que é o mais relevante)
    df = df.drop_duplicates(subset=['_cnpj_normalizado'], keep='first')
    
    depois = len(df)
    removidos = antes - depois
    
    if removidos > 0:
        logger.info(f"Duplicatas removidas: {removidos}")
    
    return df


# =============================================================================
# FUNÇÕES DE MAPEAMENTO DE COLUNAS
# =============================================================================

def mapear_colunas(df: pd.DataFrame) -> Dict[str, str]:
    """
    Mapeia automaticamente as colunas importantes do DataFrame.
    
    Returns:
        Dicionário com {nome_padrao: nome_real_coluna}
    """
    mapeamentos = {
        'cnpj': ['CNPJ', 'cnpj', 'Cnpj'],
        'razao_social': ['RAZÃO SOCIAL', 'RAZAO SOCIAL', 'RAZAO_SOCIAL', 'NOME DA EMPRESA'],
        'nome_fantasia': ['NOME FANTASIA', 'NOME_FANTASIA', 'FANTASIA'],
        'cidade': ['CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'CITY'],
        'uf': ['UF', 'ESTADO', 'STATE'],
        'cnae': ['CNAE', 'COD ATIVIDADE', 'ATIVIDADE ECONÔMICA', 'COD ATIVIDADE ECONÔMICA'],
        'telefone': ['TELEFONE', 'MELHOR TELEFONE', 'FONE', 'TEL'],
        'email': ['EMAIL', 'MELHOR EMAIL', 'E-MAIL'],
        'site': ['SITE', 'MELHOR SITE', 'WEBSITE', 'SITES'],
        'instagram': ['INSTAGRAM', 'INSTA'],
        'facebook': ['FACEBOOK', 'FB'],
        'linkedin': ['LINKEDIN'],
        'faturamento': ['FATURAMENTO', 'FATURAMENTO PRESUMIDO', 'FATURAMENTO PRESUMIDO PARA ESTE CNPJ'],
        'porte': ['PORTE', 'PORTE ESTIMADO'],
        'funcionarios': ['FUNCIONÁRIOS', 'FUNCIONARIOS', 'FUNCIONÁRIOS PRESUMIDOS'],
        'situacao': ['SITUAÇÃO CADASTRAL', 'SITUACAO', 'STATUS'],
    }
    
    resultado = {}
    
    for nome_padrao, opcoes in mapeamentos.items():
        col = encontrar_coluna(df, opcoes)
        if col:
            resultado[nome_padrao] = col
    
    logger.info(f"Colunas mapeadas: {len(resultado)}/{len(mapeamentos)}")
    
    return resultado


# =============================================================================
# FUNÇÃO PRINCIPAL (INTERFACE PARA O PIPELINE)
# =============================================================================

def carregar_base(caminho: str) -> pd.DataFrame:
    """
    Função principal de carregamento.
    Chamada pelo main.py
    
    Args:
        caminho: Caminho para arquivo de entrada
        
    Returns:
        DataFrame carregado e preparado
    """
    df = carregar_arquivo(caminho)
    df = preparar_base(df)
    return df


# =============================================================================
# EXECUÇÃO DIRETA (PARA TESTES)
# =============================================================================

if __name__ == "__main__":
    # Teste básico
    import sys
    
    if len(sys.argv) > 1:
        arquivo = sys.argv[1]
        df = carregar_base(arquivo)
        print(f"\nColunas: {df.columns.tolist()}")
        print(f"\nPrimeiras 5 linhas:")
        print(df.head())
    else:
        print("Uso: python ingestao.py <caminho_arquivo>")
        print("Exemplo: python ingestao.py ../../data/input/Saude.xlsx")