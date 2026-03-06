"""
Módulo de Verificação de Endereço - Nominatim (OpenStreetMap)
EPTV Prospecção

Verifica se o endereço da empresa existe usando a API gratuita do Nominatim.
Retorna coordenadas, endereço formatado e score de confiança.

API: https://nominatim.openstreetmap.org
Custo: GRATUITO
Limite: 1 requisição por segundo (respeitado automaticamente)

Uso:
    python verificar_endereco.py <arquivo_prospeccao>
    
Exemplo:
    python verificar_endereco.py "data/input/Saude - CAM_11-59-05_23-02-2026.xlsx"
"""

import pandas as pd
import requests
import sys
import os
import time
import re
from pathlib import Path
from datetime import datetime

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.helpers import setup_logger

# Configura logger
logger = setup_logger("nominatim", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'base_url': 'https://nominatim.openstreetmap.org/search',
    'delay_entre_requisicoes': 1.1,  # Nominatim exige 1 req/seg
    'timeout': 10,
    'user_agent': 'EPTV-Prospeccao/1.0 (contato@eptv.com.br)',  # Obrigatório pelo Nominatim
}


# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO
# =============================================================================

def montar_endereco(row: pd.Series, colunas_endereco: dict) -> str:
    """
    Monta string de endereço a partir das colunas disponíveis.
    """
    partes = []
    
    # Logradouro + Número
    if colunas_endereco.get('logradouro'):
        logradouro = row.get(colunas_endereco['logradouro'], '')
        if pd.notna(logradouro) and logradouro:
            partes.append(str(logradouro).strip())
    
    if colunas_endereco.get('numero'):
        numero = row.get(colunas_endereco['numero'], '')
        if pd.notna(numero) and numero:
            partes.append(str(numero).strip())
    
    # Bairro
    if colunas_endereco.get('bairro'):
        bairro = row.get(colunas_endereco['bairro'], '')
        if pd.notna(bairro) and bairro:
            partes.append(str(bairro).strip())
    
    # Cidade
    if colunas_endereco.get('cidade'):
        cidade = row.get(colunas_endereco['cidade'], '')
        if pd.notna(cidade) and cidade:
            partes.append(str(cidade).strip())
    
    # Estado
    if colunas_endereco.get('estado'):
        estado = row.get(colunas_endereco['estado'], '')
        if pd.notna(estado) and estado:
            partes.append(str(estado).strip())
    
    # CEP
    if colunas_endereco.get('cep'):
        cep = row.get(colunas_endereco['cep'], '')
        if pd.notna(cep) and cep:
            # Limpa CEP (só números)
            cep_limpo = re.sub(r'\D', '', str(cep))
            if len(cep_limpo) == 8:
                partes.append(cep_limpo)
    
    endereco = ', '.join(partes)
    
    # Adiciona Brasil se não tiver
    if endereco and 'brasil' not in endereco.lower():
        endereco += ', Brasil'
    
    return endereco


def verificar_endereco_nominatim(endereco: str) -> dict:
    """
    Verifica endereço usando a API Nominatim (OpenStreetMap).
    
    Retorna:
        dict com latitude, longitude, endereço formatado, tipo e score
    """
    if not endereco or len(endereco) < 10:
        return {
            'encontrado': False,
            'erro': 'Endereço muito curto ou vazio'
        }
    
    try:
        params = {
            'q': endereco,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1,
            'countrycodes': 'br',  # Limita ao Brasil
        }
        
        headers = {
            'User-Agent': CONFIG['user_agent']
        }
        
        response = requests.get(
            CONFIG['base_url'],
            params=params,
            headers=headers,
            timeout=CONFIG['timeout']
        )
        
        if response.status_code != 200:
            return {
                'encontrado': False,
                'erro': f'HTTP {response.status_code}'
            }
        
        dados = response.json()
        
        if not dados:
            return {
                'encontrado': False,
                'erro': 'Endereço não encontrado'
            }
        
        resultado = dados[0]
        
        # Extrai informações
        return {
            'encontrado': True,
            'latitude': float(resultado.get('lat', 0)),
            'longitude': float(resultado.get('lon', 0)),
            'endereco_formatado': resultado.get('display_name', ''),
            'tipo': resultado.get('type', ''),
            'classe': resultado.get('class', ''),
            'importancia': float(resultado.get('importance', 0)),
            'erro': None
        }
        
    except requests.exceptions.Timeout:
        return {
            'encontrado': False,
            'erro': 'Timeout na requisição'
        }
    except Exception as e:
        return {
            'encontrado': False,
            'erro': str(e)
        }


def encontrar_colunas_endereco(df: pd.DataFrame) -> dict:
    """
    Encontra automaticamente as colunas de endereço no DataFrame.
    """
    colunas = {}
    
    for col in df.columns:
        col_upper = col.upper()
        
        if 'LOGRADOURO' in col_upper or 'ENDERECO' in col_upper or 'RUA' in col_upper:
            if 'logradouro' not in colunas:
                colunas['logradouro'] = col
        elif 'NUMERO' in col_upper or 'NÚMERO' in col_upper or col_upper == 'NUM':
            if 'numero' not in colunas:
                colunas['numero'] = col
        elif 'BAIRRO' in col_upper:
            colunas['bairro'] = col
        elif 'CIDADE' in col_upper or 'MUNICIPIO' in col_upper or 'MUNICÍPIO' in col_upper:
            colunas['cidade'] = col
        elif col_upper in ['UF', 'ESTADO'] or 'ESTADO' in col_upper:
            colunas['estado'] = col
        elif 'CEP' in col_upper:
            colunas['cep'] = col
    
    return colunas


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def verificar_enderecos(caminho_arquivo: str, limite: int = None):
    """
    Verifica endereços de todas as empresas no arquivo.
    
    Args:
        caminho_arquivo: Caminho para o Excel de prospecção
        limite: Número máximo de empresas a verificar (None = todas)
    """
    print("\n" + "="*70)
    print("VERIFICAÇÃO DE ENDEREÇOS - NOMINATIM (OpenStreetMap)")
    print("="*70)
    print("API: Gratuita | Limite: 1 req/segundo")
    print("="*70)
    
    # Carrega arquivo
    logger.info(f"Carregando arquivo: {caminho_arquivo}")
    
    xlsx = pd.ExcelFile(caminho_arquivo)
    if "Empresas" in xlsx.sheet_names:
        df = pd.read_excel(caminho_arquivo, sheet_name="Empresas", dtype=str)
    else:
        df = pd.read_excel(caminho_arquivo, dtype=str)
    
    logger.info(f"Empresas carregadas: {len(df)}")
    
    # Encontra colunas de endereço
    colunas_endereco = encontrar_colunas_endereco(df)
    logger.info(f"Colunas de endereço encontradas: {colunas_endereco}")
    
    if not colunas_endereco:
        print("❌ Erro: Não foi possível encontrar colunas de endereço no arquivo")
        return None
    
    # Limita se necessário
    if limite:
        df = df.head(limite)
        logger.info(f"Limitado a {limite} empresas")
    
    # Processa cada empresa
    resultados = []
    total = len(df)
    encontrados = 0
    erros = 0
    
    print(f"\nVerificando {total} endereços (delay: {CONFIG['delay_entre_requisicoes']}s entre requisições)...")
    tempo_estimado = total * CONFIG['delay_entre_requisicoes'] / 60
    print(f"Tempo estimado: ~{tempo_estimado:.1f} minutos\n")
    
    for idx, row in df.iterrows():
        # Monta endereço
        endereco = montar_endereco(row, colunas_endereco)
        
        # Identifica empresa
        nome_fantasia = row.get('NOME FANTASIA', '') or row.get('Nome Fantasia', '')
        razao_social = row.get('RAZÃO SOCIAL', '') or row.get('Razao Social', '')
        nome = nome_fantasia if pd.notna(nome_fantasia) and nome_fantasia else razao_social
        nome = str(nome)[:40] if pd.notna(nome) else 'N/A'
        
        # Verifica endereço
        resultado = verificar_endereco_nominatim(endereco)
        
        # Adiciona dados da empresa
        resultado['empresa'] = nome
        resultado['endereco_original'] = endereco
        resultado['cnpj'] = row.get('CNPJ', '')
        
        resultados.append(resultado)
        
        # Log de progresso
        status = "✓" if resultado['encontrado'] else "✗"
        if resultado['encontrado']:
            encontrados += 1
            print(f"[{idx+1}/{total}] {status} {nome[:30]:<30} → {resultado.get('tipo', 'N/A')}")
        else:
            erros += 1
            print(f"[{idx+1}/{total}] {status} {nome[:30]:<30} → {resultado.get('erro', 'Não encontrado')}")
        
        # Delay obrigatório (Nominatim exige 1 req/seg)
        if idx < total - 1:
            time.sleep(CONFIG['delay_entre_requisicoes'])
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DA VERIFICAÇÃO")
    print("="*70)
    print(f"Total de endereços: {total}")
    print(f"Encontrados: {encontrados} ({encontrados/total*100:.1f}%)")
    print(f"Não encontrados: {erros} ({erros/total*100:.1f}%)")
    
    # Cria DataFrame de resultados
    df_resultados = pd.DataFrame(resultados)
    
    # Salva resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = f"verificacao_endereco_{timestamp}.xlsx"
    
    with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
        df_resultados.to_excel(writer, sheet_name='Resultados', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total,
            'enderecos_encontrados': encontrados,
            'enderecos_nao_encontrados': erros,
            'taxa_sucesso': f"{encontrados/total*100:.1f}%",
            'data_verificacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'api_utilizada': 'Nominatim (OpenStreetMap)',
            'custo': 'GRATUITO'
        }])
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
    
    print(f"\n✓ Resultados salvos em: {arquivo_saida}")
    
    return df_resultados


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python verificar_endereco.py <arquivo_prospeccao> [limite]")
        print("")
        print("Exemplos:")
        print('  python verificar_endereco.py "data/input/Saude.xlsx"')
        print('  python verificar_endereco.py "data/input/Saude.xlsx" 10  # Apenas 10 primeiras')
        print("")
        print("API: Nominatim (OpenStreetMap) - GRATUITA")
        print("Limite: 1 requisição por segundo")
        sys.exit(1)
    
    arquivo = sys.argv[1]
    limite = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(arquivo):
        print(f"Erro: Arquivo não encontrado: {arquivo}")
        sys.exit(1)
    
    verificar_enderecos(arquivo, limite)