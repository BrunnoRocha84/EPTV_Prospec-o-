"""
Módulo de Cruzamento com Crowley
EPTV Prospecção

Cruza a base de prospecção (Econodata) com os dados de
anunciantes de rádio da Crowley para identificar:
- Empresas que já anunciam (potencial de expansão para TV)
- Empresas que não anunciam (prospects novos)

Uso:
    python cruzar_crowley.py <arquivo_prospeccao> <arquivo_crowley>
    
Exemplo:
    python cruzar_crowley.py "data/input/Saude.xlsx" "data/input/h300_crowley.xlsx"
"""

import pandas as pd
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.helpers import setup_logger

# Configura logger
logger = setup_logger("crowley", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'threshold_similaridade': 0.70,  # 70% de similaridade mínima
    'threshold_alta_confianca': 0.85,  # 85% = match de alta confiança
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
        'GRUPO', 'REDE', 'MATRIZ', 'FILIAL'
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

def carregar_crowley(caminho: str) -> pd.DataFrame:
    """
    Carrega arquivo da Crowley e extrai lista de anunciantes.
    """
    logger.info(f"Carregando dados Crowley: {caminho}")
    
    df = pd.read_excel(caminho, dtype=str)
    
    # Procura coluna de anunciante
    col_anunciante = None
    for col in df.columns:
        if 'ANUNCIANTE' in col.upper():
            col_anunciante = col
            break
    
    if not col_anunciante:
        # Tenta segunda coluna (padrão do arquivo)
        if len(df.columns) >= 3:
            col_anunciante = df.columns[2]
            logger.warning(f"Coluna 'Anunciante' não encontrada, usando: {col_anunciante}")
        else:
            raise ValueError("Coluna de anunciante não encontrada no arquivo Crowley")
    
    # Procura coluna de total de inserções
    col_total = None
    for col in df.columns:
        if 'TOTAL' in col.upper():
            col_total = col
            break
    
    # Extrai anunciantes únicos com total de inserções
    df_anunciantes = df[[col_anunciante]].copy()
    df_anunciantes.columns = ['anunciante']
    
    if col_total:
        df_anunciantes['total_insercoes'] = pd.to_numeric(df[col_total], errors='coerce').fillna(0)
    else:
        df_anunciantes['total_insercoes'] = 1
    
    # Agrupa por anunciante (soma inserções)
    df_anunciantes = df_anunciantes.groupby('anunciante', as_index=False).agg({
        'total_insercoes': 'sum'
    })
    
    # Remove "NAO IDENTIFICADO" e vazios
    df_anunciantes = df_anunciantes[
        (df_anunciantes['anunciante'].notna()) & 
        (df_anunciantes['anunciante'] != '') &
        (~df_anunciantes['anunciante'].str.upper().str.contains('NAO IDENTIFICADO', na=False))
    ]
    
    logger.info(f"Anunciantes Crowley carregados: {len(df_anunciantes)}")
    
    return df_anunciantes


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

def cruzar_bases(df_prospeccao: pd.DataFrame, df_crowley: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza base de prospecção com anunciantes Crowley.
    
    Retorna DataFrame com matches encontrados.
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
    
    # Lista de anunciantes Crowley
    anunciantes_crowley = df_crowley['anunciante'].tolist()
    
    # Resultados
    matches = []
    
    total = len(df_prospeccao)
    logger.info(f"Comparando {total} empresas com {len(anunciantes_crowley)} anunciantes...")
    
    for idx, row in df_prospeccao.iterrows():
        razao = row.get(col_razao, '') if col_razao else ''
        fantasia = row.get(col_fantasia, '') if col_fantasia else ''
        
        melhor_match = None
        melhor_score = 0
        nome_usado = None
        
        # Compara com cada anunciante
        for anunciante in anunciantes_crowley:
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
            # Busca total de inserções do anunciante
            total_insercoes = df_crowley[
                df_crowley['anunciante'] == melhor_match
            ]['total_insercoes'].values[0]
            
            matches.append({
                'razao_social': razao,
                'nome_fantasia': fantasia,
                'anunciante_crowley': melhor_match,
                'similaridade': round(melhor_score * 100, 1),
                'nome_usado_match': nome_usado,
                'total_insercoes': int(total_insercoes),
                'confianca': 'ALTA' if melhor_score >= CONFIG['threshold_alta_confianca'] else 'MEDIA',
            })
        
        # Log de progresso
        if (idx + 1) % 50 == 0:
            logger.info(f"Progresso: {idx + 1}/{total}")
    
    logger.info(f"Cruzamento concluído: {len(matches)} matches encontrados")
    
    return pd.DataFrame(matches)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def executar_cruzamento(caminho_prospeccao: str, caminho_crowley: str, caminho_saida: str = None):
    """
    Executa cruzamento completo e gera relatório.
    """
    print("\n" + "="*70)
    print("CRUZAMENTO: BASE PROSPECÇÃO x ANUNCIANTES CROWLEY (RÁDIO)")
    print("="*70)
    
    # Carrega bases
    df_prospeccao = carregar_prospeccao(caminho_prospeccao)
    df_crowley = carregar_crowley(caminho_crowley)
    
    print(f"\nBase prospecção: {len(df_prospeccao)} empresas")
    print(f"Anunciantes Crowley: {len(df_crowley)} anunciantes únicos")
    
    # Executa cruzamento
    df_matches = cruzar_bases(df_prospeccao, df_crowley)
    
    # Resumo
    print("\n" + "="*70)
    print("RESULTADO DO CRUZAMENTO")
    print("="*70)
    
    total_empresas = len(df_prospeccao)
    total_matches = len(df_matches)
    matches_alta = len(df_matches[df_matches['confianca'] == 'ALTA'])
    matches_media = len(df_matches[df_matches['confianca'] == 'MEDIA'])
    
    print(f"\nTotal de empresas analisadas: {total_empresas}")
    print(f"Matches encontrados: {total_matches} ({total_matches/total_empresas*100:.1f}%)")
    print(f"  - Alta confiança (≥85%): {matches_alta}")
    print(f"  - Média confiança (70-84%): {matches_media}")
    print(f"Empresas sem match: {total_empresas - total_matches}")
    
    if total_matches > 0:
        print("\n📊 TOP 10 MATCHES:")
        print("-" * 70)
        top_matches = df_matches.nlargest(10, 'similaridade')
        for _, row in top_matches.iterrows():
            nome = row['nome_fantasia'] if pd.notna(row['nome_fantasia']) and row['nome_fantasia'] else row['razao_social']
            nome = str(nome) if pd.notna(nome) else "SEM NOME"
            anunciante = str(row['anunciante_crowley']) if pd.notna(row['anunciante_crowley']) else ""
            print(f"  {nome[:30]:<30} ↔ {anunciante[:25]:<25} ({row['similaridade']}%)")
    
    # Salva resultados
    if caminho_saida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = f"cruzamento_crowley_{timestamp}.xlsx"
    
    with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
        # Aba de matches
        if len(df_matches) > 0:
            df_matches.to_excel(writer, sheet_name='Matches', index=False)
        
        # Aba de anunciantes Crowley (referência)
        df_crowley.to_excel(writer, sheet_name='Anunciantes_Crowley', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total_empresas,
            'total_anunciantes_crowley': len(df_crowley),
            'matches_encontrados': total_matches,
            'matches_alta_confianca': matches_alta,
            'matches_media_confianca': matches_media,
            'empresas_sem_match': total_empresas - total_matches,
            'data_cruzamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
    
    print(f"\n✓ Resultados salvos em: {caminho_saida}")
    
    # Insights
    print("\n💡 INSIGHTS:")
    if total_matches > 0:
        print(f"  • {matches_alta} empresas JÁ ANUNCIAM em rádio (alta confiança)")
        print(f"    → Oportunidade: oferecer expansão para TV")
        print(f"  • {total_empresas - total_matches} empresas NÃO anunciam em rádio")
        print(f"    → Oportunidade: prospects novos para rádio e TV")
    else:
        print("  • Nenhuma empresa da base anuncia nas rádios monitoradas")
        print("    → Base é de setor diferente dos anunciantes de rádio")
    
    return df_matches


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python cruzar_crowley.py <arquivo_prospeccao> <arquivo_crowley>")
        print("")
        print("Exemplo:")
        print('  python cruzar_crowley.py "data/input/Saude.xlsx" "data/input/h300_crowley.xlsx"')
        print("")
        print("O script cruza a base de prospecção com os anunciantes da Crowley")
        print("para identificar quem já anuncia em rádio.")
        sys.exit(1)
    
    arquivo_prospeccao = sys.argv[1]
    arquivo_crowley = sys.argv[2]
    
    if not os.path.exists(arquivo_prospeccao):
        print(f"Erro: Arquivo não encontrado: {arquivo_prospeccao}")
        sys.exit(1)
    
    if not os.path.exists(arquivo_crowley):
        print(f"Erro: Arquivo não encontrado: {arquivo_crowley}")
        sys.exit(1)
    
    executar_cruzamento(arquivo_prospeccao, arquivo_crowley)