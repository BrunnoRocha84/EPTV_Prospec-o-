"""
Módulo de Cruzamento com ADI (Kantar TV)
EPTV Prospecção

Cruza a base de prospecção (Econodata) com os dados de
anunciantes de TV da ADI/Kantar para identificar:
- Empresas que já investem em mídia TV
- Praças onde anunciam
- Volume de inserções

Uso:
    python cruzar_adi.py <arquivo_prospeccao> <arquivo_adi>
    
Exemplo:
    python cruzar_adi.py "data/input/Saude - CAM.xlsx" "data/input/adi_2026_01.xlsx"
    
Para processar múltiplos arquivos ADI:
    python cruzar_adi.py "data/input/Saude - CAM.xlsx" "data/input/adi_*.xlsx"
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
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.helpers import setup_logger

# Configura logger
logger = setup_logger("adi", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'threshold_similaridade': 0.70,  # 70% de similaridade mínima
    'threshold_alta_confianca': 0.85,  # 85% = match de alta confiança
    'linha_cabecalho_adi': 10,  # Linha onde começam os dados no arquivo ADI
    'pracas_eptv': ['CAMPINAS', 'RIBEIRAO PRETO', 'RIBEIRÃO PRETO', 'SAO CARLOS', 'SÃO CARLOS', 
                   'FRANCA', 'ARARAQUARA', 'PIRACICABA', 'LIMEIRA', 'JUNDIAI', 'JUNDIAÍ'],
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

def carregar_adi(caminho: str, filtrar_pracas_eptv: bool = True) -> pd.DataFrame:
    """
    Carrega arquivo ADI (Kantar TV) e extrai lista de anunciantes.
    
    Args:
        caminho: Caminho para o arquivo ou padrão glob (ex: "data/input/adi_*.xlsx")
        filtrar_pracas_eptv: Se True, filtra apenas praças da região EPTV
    """
    logger.info(f"Carregando dados ADI: {caminho}")
    
    # Verifica se é um padrão glob
    if '*' in caminho:
        arquivos = glob.glob(caminho)
        logger.info(f"Encontrados {len(arquivos)} arquivos ADI")
    else:
        arquivos = [caminho]
    
    todos_anunciantes = []
    
    for arquivo in arquivos:
        logger.info(f"Processando: {os.path.basename(arquivo)}")
        
        try:
            # Lê pulando as linhas de cabeçalho especial
            df = pd.read_excel(arquivo, skiprows=CONFIG['linha_cabecalho_adi'], dtype=str)
            
            # Identifica colunas pelo conteúdo (o ADI não tem cabeçalho claro)
            # Baseado na análise: coluna 4 = Praça, coluna 6 = Anunciante
            if len(df.columns) >= 19:
                # Renomeia colunas principais
                colunas = df.columns.tolist()
                df = df.rename(columns={
                    colunas[0]: 'mes_ano',
                    colunas[1]: 'data',
                    colunas[2]: 'hora',
                    colunas[3]: 'uf',
                    colunas[4]: 'praca',
                    colunas[5]: 'agencia',
                    colunas[6]: 'anunciante',
                    colunas[7]: 'emissora',
                    colunas[8]: 'praca_emissora',
                    colunas[9]: 'emissora2',
                    colunas[10]: 'programa',
                    colunas[11]: 'categoria',
                    colunas[12]: 'tipo',
                    colunas[13]: 'setor',
                    colunas[14]: 'meio',
                    colunas[15]: 'valor',
                    colunas[16]: 'qtd',
                    colunas[17]: 'duracao',
                })
            
            # Filtra praças EPTV se solicitado
            if filtrar_pracas_eptv and 'praca' in df.columns:
                df_filtrado = df[df['praca'].str.upper().isin([p.upper() for p in CONFIG['pracas_eptv']])]
                logger.info(f"  Filtrado praças EPTV: {len(df_filtrado)} de {len(df)} registros")
                df = df_filtrado
            
            if 'anunciante' in df.columns:
                todos_anunciantes.append(df)
                
        except Exception as e:
            logger.warning(f"Erro ao processar {arquivo}: {e}")
            continue
    
    if not todos_anunciantes:
        raise ValueError("Nenhum arquivo ADI foi carregado com sucesso")
    
    # Concatena todos os arquivos
    df_completo = pd.concat(todos_anunciantes, ignore_index=True)
    
    # Agrupa por anunciante
    df_anunciantes = df_completo.groupby('anunciante', as_index=False).agg({
        'valor': lambda x: pd.to_numeric(x, errors='coerce').sum(),
        'qtd': lambda x: pd.to_numeric(x, errors='coerce').sum(),
        'praca': lambda x: ', '.join(x.dropna().unique()),
        'setor': 'first',
        'emissora': lambda x: ', '.join(x.dropna().unique()[:5]),  # Limita a 5 emissoras
    })
    
    # Remove anunciantes vazios ou inválidos
    df_anunciantes = df_anunciantes[
        (df_anunciantes['anunciante'].notna()) & 
        (df_anunciantes['anunciante'] != '') &
        (~df_anunciantes['anunciante'].str.contains('{DIRETO}', na=False))  # Remove {DIRETO}
    ]
    
    logger.info(f"Anunciantes ADI carregados: {len(df_anunciantes)}")
    
    # Mostra top anunciantes
    top_anunciantes = df_anunciantes.nlargest(10, 'valor')
    logger.info(f"Top 10 anunciantes por valor:\n{top_anunciantes[['anunciante', 'valor']].to_string()}")
    
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

def cruzar_bases(df_prospeccao: pd.DataFrame, df_adi: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza base de prospecção com anunciantes ADI (TV).
    
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
    
    # Lista de anunciantes ADI
    anunciantes_adi = df_adi['anunciante'].tolist()
    
    # Resultados
    matches = []
    
    total = len(df_prospeccao)
    logger.info(f"Comparando {total} empresas com {len(anunciantes_adi)} anunciantes...")
    
    for idx, row in df_prospeccao.iterrows():
        razao = row.get(col_razao, '') if col_razao else ''
        fantasia = row.get(col_fantasia, '') if col_fantasia else ''
        
        melhor_match = None
        melhor_score = 0
        nome_usado = None
        
        # Compara com cada anunciante
        for anunciante in anunciantes_adi:
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
            dados_anunciante = df_adi[
                df_adi['anunciante'] == melhor_match
            ].iloc[0]
            
            match_info = {
                'cnpj': row.get('CNPJ', ''),
                'razao_social': razao,
                'nome_fantasia': fantasia,
                'anunciante_tv': melhor_match,
                'similaridade': round(melhor_score * 100, 1),
                'nome_usado_match': nome_usado,
                'confianca': 'ALTA' if melhor_score >= CONFIG['threshold_alta_confianca'] else 'MEDIA',
                'investimento_tv': dados_anunciante.get('valor', 0),
                'qtd_insercoes': dados_anunciante.get('qtd', 0),
                'pracas_tv': dados_anunciante.get('praca', ''),
                'setor_tv': dados_anunciante.get('setor', ''),
                'emissoras': dados_anunciante.get('emissora', ''),
            }
            
            matches.append(match_info)
        
        # Log de progresso
        if (idx + 1) % 50 == 0:
            logger.info(f"Progresso: {idx + 1}/{total}")
    
    logger.info(f"Cruzamento concluído: {len(matches)} matches encontrados")
    
    return pd.DataFrame(matches)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def executar_cruzamento(caminho_prospeccao: str, caminho_adi: str, filtrar_pracas: bool = True, caminho_saida: str = None):
    """
    Executa cruzamento completo e gera relatório.
    """
    print("\n" + "="*70)
    print("CRUZAMENTO: BASE PROSPECÇÃO x ANUNCIANTES ADI (TV)")
    print("="*70)
    
    # Carrega bases
    df_prospeccao = carregar_prospeccao(caminho_prospeccao)
    df_adi = carregar_adi(caminho_adi, filtrar_pracas_eptv=filtrar_pracas)
    
    print(f"\nBase prospecção: {len(df_prospeccao)} empresas")
    print(f"Anunciantes TV (ADI): {len(df_adi)} anunciantes únicos")
    
    if filtrar_pracas:
        print(f"Filtro: Apenas praças EPTV ({', '.join(CONFIG['pracas_eptv'][:5])}...)")
    
    # Executa cruzamento
    df_matches = cruzar_bases(df_prospeccao, df_adi)
    
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
            nome = str(nome)[:30] if pd.notna(nome) else "SEM NOME"
            anunciante = str(row['anunciante_tv'])[:20] if pd.notna(row['anunciante_tv']) else ""
            investimento = f" | R${float(row['investimento_tv']):,.0f}" if pd.notna(row['investimento_tv']) and row['investimento_tv'] else ""
            print(f"  {nome:<30} ↔ {anunciante:<20} ({row['similaridade']}%){investimento}")
    
    # Salva resultados
    if caminho_saida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = f"cruzamento_adi_tv_{timestamp}.xlsx"
    
    with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
        # Aba de matches
        if len(df_matches) > 0:
            df_matches.to_excel(writer, sheet_name='Matches', index=False)
        
        # Aba de anunciantes ADI (referência)
        df_adi.to_excel(writer, sheet_name='Anunciantes_TV', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total_empresas,
            'total_anunciantes_tv': len(df_adi),
            'filtro_pracas_eptv': 'Sim' if filtrar_pracas else 'Não',
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
        print(f"  • {matches_alta} empresas JÁ INVESTEM em TV (alta confiança)")
        print(f"    → Oportunidade: aumentar investimento ou diversificar horários")
        print(f"  • {total_empresas - total_matches} empresas NÃO aparecem na base ADI")
        print(f"    → Prospects novos para TV")
    else:
        print("  • Nenhuma empresa da base aparece na ADI TV")
        print("    → Base pode ser de setor diferente dos anunciantes TV")
        print("    → Tente sem filtro de praças: adicione --todas-pracas")
    
    return df_matches


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python cruzar_adi.py <arquivo_prospeccao> <arquivo_adi> [--todas-pracas]")
        print("")
        print("Exemplos:")
        print('  python cruzar_adi.py "data/input/Saude - CAM.xlsx" "data/input/adi_2026_01.xlsx"')
        print('  python cruzar_adi.py "data/input/Saude - CAM.xlsx" "data/input/adi_*.xlsx"')
        print('  python cruzar_adi.py "data/input/Saude.xlsx" "data/input/adi_2026_01.xlsx" --todas-pracas')
        print("")
        print("O script cruza a base de prospecção com os anunciantes da ADI (TV)")
        print("para identificar quem já investe em mídia televisiva.")
        print("")
        print("Por padrão, filtra apenas praças da região EPTV.")
        print("Use --todas-pracas para incluir anunciantes de todas as praças.")
        sys.exit(1)
    
    arquivo_prospeccao = sys.argv[1]
    arquivo_adi = sys.argv[2]
    filtrar_pracas = '--todas-pracas' not in sys.argv
    
    if not os.path.exists(arquivo_prospeccao):
        print(f"Erro: Arquivo não encontrado: {arquivo_prospeccao}")
        sys.exit(1)
    
    # Verifica se é glob ou arquivo único
    if '*' not in arquivo_adi and not os.path.exists(arquivo_adi):
        print(f"Erro: Arquivo não encontrado: {arquivo_adi}")
        sys.exit(1)
    
    executar_cruzamento(arquivo_prospeccao, arquivo_adi, filtrar_pracas)