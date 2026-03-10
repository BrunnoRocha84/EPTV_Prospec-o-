"""
Módulo de Cruzamento com Base de Painéis (OOH)
EPTV Prospecção

Cruza a base de prospecção (Econodata) com os dados de
anunciantes de múltiplos arquivos OOH para identificar:
- Empresas que já investem em mídia OOH (Painéis)
- Volume de investimento total
- Categorias dos anunciantes

Uso:
    python -m src.matching.paineis <arquivo_prospeccao> <pasta_arquivos_ooh>
    
Exemplo:
    python -m src.matching.paineis "data/input/Saude - RIB_15-18-42_04-03-2026.xlsx" "data/input"
"""

import pandas as pd
import sys
import os
import re
import glob
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import setup_logger

# Configura logger
logger = setup_logger("paineis", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'threshold_similaridade': 0.70,  # 70% de similaridade mínima
    'threshold_alta_confianca': 0.85,  # 85% = match de alta confiança
    'linha_cabecalho_ooh': 11,  # Linha onde começa o cabeçalho nos arquivos OOH
}


# =============================================================================
# FUNÇÕES DE NORMALIZAÇÃO
# =============================================================================

def normalizar_nome(nome: str) -> str:
    """
    Normaliza nome de empresa para comparação.
    Remove termos comuns, pontuação, espaços extras.
    """
    if not nome or pd.isna(nome):
        return ""
    
    nome = str(nome).upper().strip()
    
    # Remove termos corporativos comuns
    termos_remover = [
        'LTDA', 'ME', 'EPP', 'EIRELI', 'S/A', 'S.A.', 'SA',
        'COMERCIO', 'COMÉRCIO', 'INDUSTRIA', 'INDÚSTRIA',
        'SERVICOS', 'SERVIÇOS', 'DISTRIBUIDORA', 'ATACADISTA',
        'DO BRASIL', 'BRASIL', 'CONCESSIONARIA', 'CONCESSIONÁRIA',
        'LOJA', 'LOJAS', 'SUPERMERCADO', 'SUPERMERCADOS',
        'GRUPO', 'REDE', 'MATRIZ', 'FILIAL', 'ACADEMIA'
    ]
    
    for termo in termos_remover:
        nome = re.sub(r'\b' + termo + r'\b', '', nome)
    
    # Remove pontuação
    nome = re.sub(r'[^\w\s]', '', nome)
    
    # Remove espaços extras
    nome = ' '.join(nome.split())
    
    return nome


def calcular_similaridade(nome1: str, nome2: str) -> float:
    """
    Calcula similaridade entre dois nomes usando SequenceMatcher.
    """
    if not nome1 or not nome2:
        return 0.0
    
    nome1_norm = normalizar_nome(nome1)
    nome2_norm = normalizar_nome(nome2)
    
    if not nome1_norm or not nome2_norm:
        return 0.0
    
    # Similaridade básica
    similaridade = SequenceMatcher(None, nome1_norm, nome2_norm).ratio()
    
    # Bônus se um nome contém o outro
    if nome1_norm in nome2_norm or nome2_norm in nome1_norm:
        similaridade = min(1.0, similaridade + 0.15)
    
    # Bônus se as primeiras palavras são iguais
    palavras1 = nome1_norm.split()
    palavras2 = nome2_norm.split()
    if palavras1 and palavras2 and palavras1[0] == palavras2[0]:
        similaridade = min(1.0, similaridade + 0.10)
    
    return similaridade


# =============================================================================
# FUNÇÕES DE CARREGAMENTO
# =============================================================================

def carregar_multiplos_ooh(pasta_input: str) -> pd.DataFrame:
    """
    Carrega todos os arquivos OOH da pasta e consolida em um único DataFrame.
    """
    logger.info(f"Buscando arquivos OOH na pasta: {pasta_input}")
    
    # Encontra todos os arquivos que terminam com _OOH.xlsx
    padrao_busca = os.path.join(pasta_input, "*_OOH.xlsx")
    arquivos_ooh = glob.glob(padrao_busca)
    
    if not arquivos_ooh:
        logger.error(f"Nenhum arquivo OOH encontrado em {pasta_input}")
        return pd.DataFrame()
        
    logger.info(f"Encontrados {len(arquivos_ooh)} arquivos OOH. Consolidando...")
    
    dfs_consolidados = []
    
    for arquivo in arquivos_ooh:
        try:
            # Lê pulando as linhas de cabeçalho especial
            df = pd.read_excel(arquivo, skiprows=CONFIG['linha_cabecalho_ooh'], dtype=str)
            
            # Procura coluna de anunciante
            col_anunciante = None
            for col in df.columns:
                if 'ANUNCIANTE' in str(col).upper():
                    col_anunciante = col
                    break
            
            if not col_anunciante:
                continue
                
            # Procura coluna de categoria
            col_categoria = None
            for col in df.columns:
                if 'CATEGORIA' in str(col).upper():
                    col_categoria = col
                    break
            
            # Procura coluna de investimento (Total ou última coluna com $)
            col_investimento = None
            for col in df.columns:
                if 'TOTAL' in str(col).upper() and '$' in str(col):
                    col_investimento = col
                    break
            
            if not col_investimento:
                for col in df.columns:
                    if '($)' in str(col):
                        col_investimento = col
            
            # Monta DataFrame de anunciantes deste arquivo
            colunas_usar = [col_anunciante]
            if col_categoria:
                colunas_usar.append(col_categoria)
            if col_investimento:
                colunas_usar.append(col_investimento)
            
            df_temp = df[colunas_usar].copy()
            
            # Renomeia colunas
            df_temp = df_temp.rename(columns={col_anunciante: 'anunciante'})
            
            if col_categoria:
                df_temp = df_temp.rename(columns={col_categoria: 'categoria'})
            if col_investimento:
                df_temp = df_temp.rename(columns={col_investimento: 'investimento'})
                df_temp['investimento'] = pd.to_numeric(df_temp['investimento'], errors='coerce').fillna(0)
            
            # Remove vazios
            df_temp = df_temp[
                (df_temp['anunciante'].notna()) & 
                (df_temp['anunciante'] != '')
            ]
            
            dfs_consolidados.append(df_temp)
            
        except Exception as e:
            logger.warning(f"Erro ao processar arquivo {arquivo}: {e}")
    
    if not dfs_consolidados:
        return pd.DataFrame()
        
    # Concatena todos os DataFrames
    df_final = pd.concat(dfs_consolidados, ignore_index=True)
    
    # Agrupa por anunciante somando os investimentos
    if 'investimento' in df_final.columns:
        agg_dict = {'investimento': 'sum'}
        if 'categoria' in df_final.columns:
            agg_dict['categoria'] = 'first'
        
        df_final = df_final.groupby('anunciante', as_index=False).agg(agg_dict)
    else:
        df_final = df_final.drop_duplicates(subset=['anunciante'])
    
    logger.info(f"Base consolidada: {len(df_final)} anunciantes únicos em painéis")
    
    return df_final


def carregar_prospeccao(caminho: str) -> pd.DataFrame:
    """
    Carrega arquivo de prospecção (Econodata).
    """
    logger.info(f"Carregando base de prospecção: {caminho}")
    
    xlsx = pd.ExcelFile(caminho)
    abas = xlsx.sheet_names
    
    if "Empresas" in abas:
        df = pd.read_excel(caminho, sheet_name="Empresas", dtype=str)
    else:
        df = pd.read_excel(caminho, dtype=str)
    
    logger.info(f"Base de prospecção carregada: {len(df)} empresas")
    
    return df


# =============================================================================
# FUNÇÃO DE CRUZAMENTO
# =============================================================================

def cruzar_bases(df_prospeccao: pd.DataFrame, df_paineis: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza base de prospecção com anunciantes de Painéis.
    """
    logger.info("Iniciando cruzamento de bases...")
    
    # Encontra colunas de nome na prospecção
    col_razao = None
    col_fantasia = None
    
    for col in df_prospeccao.columns:
        col_upper = col.upper()
        if 'RAZÃO SOCIAL' in col_upper or 'RAZAO SOCIAL' in col_upper:
            col_razao = col
        elif 'NOME FANTASIA' in col_upper or 'FANTASIA' in col_upper:
            col_fantasia = col
    
    if not col_razao and not col_fantasia:
        raise ValueError("Colunas de nome não encontradas na base de prospecção")
    
    logger.info(f"Colunas de nome: Razão Social='{col_razao}', Fantasia='{col_fantasia}'")
    
    # Lista de anunciantes
    anunciantes_paineis = df_paineis['anunciante'].tolist()
    
    # Resultados
    matches = []
    
    total = len(df_prospeccao)
    logger.info(f"Comparando {total} empresas com {len(anunciantes_paineis)} anunciantes de painéis...")
    
    for idx, row in df_prospeccao.iterrows():
        razao = row.get(col_razao, '') if col_razao else ''
        fantasia = row.get(col_fantasia, '') if col_fantasia else ''
        
        melhor_match = None
        melhor_score = 0
        nome_usado = None
        
        # Compara com cada anunciante
        for anunciante in anunciantes_paineis:
            # Tenta match com razão social
            if razao:
                score_razao = calcular_similaridade(razao, anunciante)
                if score_razao > melhor_score:
                    melhor_score = score_razao
                    melhor_match = anunciante
                    nome_usado = 'razao_social'
            
            # Tenta match com nome fantasia
            if fantasia:
                score_fantasia = calcular_similaridade(fantasia, anunciante)
                if score_fantasia > melhor_score:
                    melhor_score = score_fantasia
                    melhor_match = anunciante
                    nome_usado = 'nome_fantasia'
        
        # Registra se passou do threshold
        if melhor_score >= CONFIG['threshold_similaridade']:
            # Busca dados do anunciante
            dados_anunciante = df_paineis[
                df_paineis['anunciante'] == melhor_match
            ].iloc[0]
            
            match_info = {
                'razao_social': razao,
                'nome_fantasia': fantasia,
                'anunciante_paineis': melhor_match,
                'similaridade_paineis': round(melhor_score * 100, 1),
                'nome_usado_match_paineis': nome_usado,
                'confianca_paineis': 'ALTA' if melhor_score >= CONFIG['threshold_alta_confianca'] else 'MEDIA',
            }
            
            # Adiciona campos extras se existirem
            if 'categoria' in dados_anunciante:
                match_info['categoria_paineis'] = dados_anunciante['categoria']
            if 'investimento' in dados_anunciante:
                match_info['investimento_paineis'] = dados_anunciante['investimento']
            
            matches.append(match_info)
        
        # Log de progresso
        if (idx + 1) % 50 == 0:
            logger.info(f"Progresso: {idx + 1}/{total}")
    
    logger.info(f"Cruzamento concluído: {len(matches)} matches encontrados")
    
    return pd.DataFrame(matches)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def executar_cruzamento(caminho_prospeccao: str, pasta_ooh: str, caminho_saida: str = None):
    """
    Executa cruzamento completo e gera relatório.
    """
    print("\n" + "="*70)
    print("CRUZAMENTO: BASE PROSPECÇÃO x ANUNCIANTES PAINÉIS (OOH)")
    print("="*70)
    
    # Carrega bases
    df_prospeccao = carregar_prospeccao(caminho_prospeccao)
    df_paineis = carregar_multiplos_ooh(pasta_ooh)
    
    if len(df_paineis) == 0:
        print("Erro: Não foi possível carregar os dados de painéis.")
        return None
        
    print(f"\nBase prospecção: {len(df_prospeccao)} empresas")
    print(f"Anunciantes Painéis: {len(df_paineis)} anunciantes únicos")
    
    # Executa cruzamento
    df_matches = cruzar_bases(df_prospeccao, df_paineis)
    
    # Resumo
    print("\n" + "="*70)
    print("RESULTADO DO CRUZAMENTO")
    print("="*70)
    
    total_empresas = len(df_prospeccao)
    total_matches = len(df_matches)
    matches_alta = len(df_matches[df_matches['confianca_paineis'] == 'ALTA']) if len(df_matches) > 0 else 0
    matches_media = len(df_matches[df_matches['confianca_paineis'] == 'MEDIA']) if len(df_matches) > 0 else 0
    
    print(f"\nTotal de empresas analisadas: {total_empresas}")
    print(f"Matches encontrados: {total_matches} ({total_matches/total_empresas*100:.1f}%)")
    print(f"  - Alta confiança (≥85%): {matches_alta}")
    print(f"  - Média confiança (70-84%): {matches_media}")
    print(f"Empresas sem match: {total_empresas - total_matches}")
    
    if total_matches > 0:
        print("\n📊 TOP 10 MATCHES:")
        print("-" * 70)
        top_matches = df_matches.nlargest(10, 'similaridade_paineis')
        for _, row in top_matches.iterrows():
            nome = row['nome_fantasia'] if pd.notna(row['nome_fantasia']) and row['nome_fantasia'] else row['razao_social']
            nome = str(nome) if pd.notna(nome) else "SEM NOME"
            anunciante = str(row['anunciante_paineis']) if pd.notna(row['anunciante_paineis']) else ""
            investimento = f" | R${row['investimento_paineis']:,.0f}k" if 'investimento_paineis' in row and pd.notna(row['investimento_paineis']) else ""
            print(f"  {nome[:30]:<30} ↔ {anunciante[:20]:<20} ({row['similaridade_paineis']}%){investimento}")
    
    # Salva resultados
    if caminho_saida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = f"data/output/cruzamento_paineis_{timestamp}.xlsx"
        
        # Garante que a pasta existe
        os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    
    with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
        # Aba de matches
        if len(df_matches) > 0:
            df_matches.to_excel(writer, sheet_name='Matches', index=False)
        
        # Aba de anunciantes (referência)
        df_paineis.to_excel(writer, sheet_name='Anunciantes_Paineis', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total_empresas,
            'total_anunciantes_paineis': len(df_paineis),
            'matches_encontrados': total_matches,
            'matches_alta_confianca': matches_alta,
            'matches_media_confianca': matches_media,
            'empresas_sem_match': total_empresas - total_matches,
            'data_cruzamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
    
    print(f"\n✓ Resultados salvos em: {caminho_saida}")
    
    return df_matches


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python -m src.matching.paineis <arquivo_prospeccao> <pasta_arquivos_ooh>")
        print("")
        print("Exemplo:")
        print('  python -m src.matching.paineis "data/input/Saude - RIB_15-18-42_04-03-2026.xlsx" "data/input"')
        sys.exit(1)
    
    arquivo_prospeccao = sys.argv[1]
    pasta_ooh = sys.argv[2]
    
    if not os.path.exists(arquivo_prospeccao):
        print(f"Erro: Arquivo não encontrado: {arquivo_prospeccao}")
        sys.exit(1)
    
    if not os.path.exists(pasta_ooh):
        print(f"Erro: Pasta não encontrada: {pasta_ooh}")
        sys.exit(1)
    
    executar_cruzamento(arquivo_prospeccao, pasta_ooh)
