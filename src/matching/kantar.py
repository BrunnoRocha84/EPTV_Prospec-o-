"""
Módulo de Cruzamento com Kantar (OOH/TV)
EPTV Prospecção

Cruza a base de prospecção (Econodata) com os dados de
anunciantes OOH/TV da Kantar para identificar:
- Empresas que já investem em mídia OOH/TV
- Volume de investimento
- Categorias dos anunciantes

Uso:
    python cruzar_kantar.py <arquivo_prospeccao> <arquivo_kantar>
    
Exemplo:
    python cruzar_kantar.py "data/input/Saude.xlsx" "data/input/36-25_01.12.25_OOH.xlsx"
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
logger = setup_logger("kantar", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'threshold_similaridade': 0.70,  # 70% de similaridade mínima
    'threshold_alta_confianca': 0.85,  # 85% = match de alta confiança
    'linha_cabecalho_kantar': 11,  # Linha onde começa o cabeçalho no arquivo Kantar
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

def carregar_kantar(caminho: str) -> pd.DataFrame:
    """
    Carrega arquivo da Kantar e extrai lista de anunciantes.
    O arquivo Kantar tem cabeçalho especial nas primeiras linhas.
    """
    logger.info(f"Carregando dados Kantar: {caminho}")
    
    # Lê pulando as linhas de cabeçalho especial
    df = pd.read_excel(caminho, skiprows=CONFIG['linha_cabecalho_kantar'], dtype=str)
    
    logger.info(f"Colunas encontradas: {df.columns.tolist()}")
    
    # Procura coluna de anunciante
    col_anunciante = None
    for col in df.columns:
        if 'ANUNCIANTE' in str(col).upper():
            col_anunciante = col
            break
    
    if not col_anunciante:
        # Tenta primeira coluna
        col_anunciante = df.columns[0]
        logger.warning(f"Coluna 'Anunciante' não encontrada, usando: {col_anunciante}")
    
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
        # Procura qualquer coluna com ($)
        for col in df.columns:
            if '($)' in str(col):
                col_investimento = col
    
    # Procura coluna de praça
    col_praca = None
    for col in df.columns:
        if 'PRAÇA' in str(col).upper() or 'PRACA' in str(col).upper():
            col_praca = col
            break
    
    # Monta DataFrame de anunciantes
    colunas_usar = [col_anunciante]
    if col_categoria:
        colunas_usar.append(col_categoria)
    if col_investimento:
        colunas_usar.append(col_investimento)
    if col_praca:
        colunas_usar.append(col_praca)
    
    df_anunciantes = df[colunas_usar].copy()
    
    # Renomeia colunas
    novos_nomes = {'anunciante': col_anunciante}
    df_anunciantes = df_anunciantes.rename(columns={col_anunciante: 'anunciante'})
    
    if col_categoria:
        df_anunciantes = df_anunciantes.rename(columns={col_categoria: 'categoria'})
    if col_investimento:
        df_anunciantes = df_anunciantes.rename(columns={col_investimento: 'investimento'})
        df_anunciantes['investimento'] = pd.to_numeric(df_anunciantes['investimento'], errors='coerce').fillna(0)
    if col_praca:
        df_anunciantes = df_anunciantes.rename(columns={col_praca: 'praca'})
    
    # Remove vazios e duplicados
    df_anunciantes = df_anunciantes[
        (df_anunciantes['anunciante'].notna()) & 
        (df_anunciantes['anunciante'] != '')
    ]
    
    # Agrupa por anunciante (soma investimento se houver)
    if 'investimento' in df_anunciantes.columns:
        agg_dict = {'investimento': 'sum'}
        if 'categoria' in df_anunciantes.columns:
            agg_dict['categoria'] = 'first'
        if 'praca' in df_anunciantes.columns:
            agg_dict['praca'] = lambda x: ', '.join(x.unique())
        
        df_anunciantes = df_anunciantes.groupby('anunciante', as_index=False).agg(agg_dict)
    else:
        df_anunciantes = df_anunciantes.drop_duplicates(subset=['anunciante'])
    
    logger.info(f"Anunciantes Kantar carregados: {len(df_anunciantes)}")
    
    # Mostra categorias disponíveis
    if 'categoria' in df_anunciantes.columns:
        categorias = df_anunciantes['categoria'].value_counts()
        logger.info(f"Categorias encontradas:\n{categorias.head(10)}")
    
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

def cruzar_bases(df_prospeccao: pd.DataFrame, df_kantar: pd.DataFrame, filtro_categoria: str = None) -> pd.DataFrame:
    """
    Cruza base de prospecção com anunciantes Kantar.
    
    Args:
        df_prospeccao: Base de CNPJs
        df_kantar: Base de anunciantes Kantar
        filtro_categoria: Se informado, filtra apenas anunciantes desta categoria
    
    Retorna DataFrame com matches encontrados.
    """
    logger.info("Iniciando cruzamento de bases...")
    
    # Aplica filtro de categoria se informado
    if filtro_categoria and 'categoria' in df_kantar.columns:
        df_kantar_filtrado = df_kantar[
            df_kantar['categoria'].str.upper().str.contains(filtro_categoria.upper(), na=False)
        ]
        logger.info(f"Filtrado por categoria '{filtro_categoria}': {len(df_kantar_filtrado)} anunciantes")
    else:
        df_kantar_filtrado = df_kantar
    
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
    
    # Lista de anunciantes Kantar
    anunciantes_kantar = df_kantar_filtrado['anunciante'].tolist()
    
    # Resultados
    matches = []
    
    total = len(df_prospeccao)
    logger.info(f"Comparando {total} empresas com {len(anunciantes_kantar)} anunciantes...")
    
    for idx, row in df_prospeccao.iterrows():
        razao = row.get(col_razao, '') if col_razao else ''
        fantasia = row.get(col_fantasia, '') if col_fantasia else ''
        
        melhor_match = None
        melhor_score = 0
        nome_usado = None
        
        # Compara com cada anunciante
        for anunciante in anunciantes_kantar:
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
            dados_anunciante = df_kantar_filtrado[
                df_kantar_filtrado['anunciante'] == melhor_match
            ].iloc[0]
            
            match_info = {
                'razao_social': razao,
                'nome_fantasia': fantasia,
                'anunciante_kantar': melhor_match,
                'similaridade': round(melhor_score * 100, 1),
                'nome_usado_match': nome_usado,
                'confianca': 'ALTA' if melhor_score >= CONFIG['threshold_alta_confianca'] else 'MEDIA',
            }
            
            # Adiciona campos extras se existirem
            if 'categoria' in dados_anunciante:
                match_info['categoria'] = dados_anunciante['categoria']
            if 'investimento' in dados_anunciante:
                match_info['investimento_ooh'] = dados_anunciante['investimento']
            if 'praca' in dados_anunciante:
                match_info['pracas'] = dados_anunciante['praca']
            
            matches.append(match_info)
        
        # Log de progresso
        if (idx + 1) % 50 == 0:
            logger.info(f"Progresso: {idx + 1}/{total}")
    
    logger.info(f"Cruzamento concluído: {len(matches)} matches encontrados")
    
    return pd.DataFrame(matches)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def executar_cruzamento(caminho_prospeccao: str, caminho_kantar: str, filtro_categoria: str = None, caminho_saida: str = None):
    """
    Executa cruzamento completo e gera relatório.
    """
    print("\n" + "="*70)
    print("CRUZAMENTO: BASE PROSPECÇÃO x ANUNCIANTES KANTAR (OOH/TV)")
    print("="*70)
    
    # Carrega bases
    df_prospeccao = carregar_prospeccao(caminho_prospeccao)
    df_kantar = carregar_kantar(caminho_kantar)
    
    print(f"\nBase prospecção: {len(df_prospeccao)} empresas")
    print(f"Anunciantes Kantar: {len(df_kantar)} anunciantes únicos")
    
    # Mostra categorias disponíveis
    if 'categoria' in df_kantar.columns:
        print("\n📋 CATEGORIAS DISPONÍVEIS:")
        categorias = df_kantar['categoria'].value_counts()
        for cat, count in categorias.head(15).items():
            print(f"   • {cat}: {count}")
        
        if filtro_categoria:
            print(f"\n🔍 Filtro aplicado: {filtro_categoria}")
    
    # Executa cruzamento
    df_matches = cruzar_bases(df_prospeccao, df_kantar, filtro_categoria)
    
    # Resumo
    print("\n" + "="*70)
    print("RESULTADO DO CRUZAMENTO")
    print("="*70)
    
    total_empresas = len(df_prospeccao)
    total_matches = len(df_matches)
    matches_alta = len(df_matches[df_matches['confianca'] == 'ALTA']) if len(df_matches) > 0 else 0
    matches_media = len(df_matches[df_matches['confianca'] == 'MEDIA']) if len(df_matches) > 0 else 0
    
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
            anunciante = str(row['anunciante_kantar']) if pd.notna(row['anunciante_kantar']) else ""
            investimento = f" | R${row['investimento_ooh']:,.0f}k" if 'investimento_ooh' in row and pd.notna(row['investimento_ooh']) else ""
            print(f"  {nome[:30]:<30} ↔ {anunciante[:20]:<20} ({row['similaridade']}%){investimento}")
    
    # Salva resultados
    if caminho_saida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = f"cruzamento_kantar_{timestamp}.xlsx"
    
    with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
        # Aba de matches
        if len(df_matches) > 0:
            df_matches.to_excel(writer, sheet_name='Matches', index=False)
        
        # Aba de anunciantes Kantar (referência)
        df_kantar.to_excel(writer, sheet_name='Anunciantes_Kantar', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total_empresas,
            'total_anunciantes_kantar': len(df_kantar),
            'filtro_categoria': filtro_categoria or 'Nenhum',
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
        print(f"  • {matches_alta} empresas JÁ INVESTEM em mídia OOH (alta confiança)")
        print(f"    → Oportunidade: oferecer TV/Rádio como complemento")
        print(f"  • {total_empresas - total_matches} empresas NÃO aparecem na base Kantar")
        print(f"    → Podem ser prospects novos ou não investem em OOH")
    else:
        print("  • Nenhuma empresa da base aparece na Kantar OOH")
        print("    → Base pode ser de setor diferente dos anunciantes OOH")
        print("    → Tente filtrar por categoria específica")
    
    return df_matches


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python cruzar_kantar.py <arquivo_prospeccao> <arquivo_kantar> [filtro_categoria]")
        print("")
        print("Exemplos:")
        print('  python cruzar_kantar.py "data/input/Saude.xlsx" "data/input/36-25_01.12.25_OOH.xlsx"')
        print('  python cruzar_kantar.py "data/input/Saude.xlsx" "data/input/36-25_01.12.25_OOH.xlsx" "SAUDE"')
        print("")
        print("O script cruza a base de prospecção com os anunciantes da Kantar (OOH/TV)")
        print("para identificar quem já investe em mídia externa.")
        print("")
        print("O filtro_categoria é opcional e filtra apenas anunciantes de uma categoria específica.")
        sys.exit(1)
    
    arquivo_prospeccao = sys.argv[1]
    arquivo_kantar = sys.argv[2]
    filtro_categoria = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(arquivo_prospeccao):
        print(f"Erro: Arquivo não encontrado: {arquivo_prospeccao}")
        sys.exit(1)
    
    if not os.path.exists(arquivo_kantar):
        print(f"Erro: Arquivo não encontrado: {arquivo_kantar}")
        sys.exit(1)
    
    executar_cruzamento(arquivo_prospeccao, arquivo_kantar, filtro_categoria)