"""
Validação em Lote - Receita Federal
EPTV Prospecção

Valida situação cadastral de todos os CNPJs de uma base de prospecção.
Usa BrasilAPI (gratuita) com fallback para ReceitaWS.

Uso:
    python validar_receita.py <arquivo_prospeccao>
    
Exemplo:
    python validar_receita.py "data/input/Saude - RIB_15-18-42_04-03-2026.xlsx"
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
logger = setup_logger("receita_lote", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'brasilapi_url': 'https://brasilapi.com.br/api/cnpj/v1/',
    'receitaws_url': 'https://receitaws.com.br/v1/cnpj/',
    'delay_entre_requisicoes': 1.2,  # Respeita rate limit
    'timeout': 15,
    'max_tentativas': 3,
}


# =============================================================================
# FUNÇÕES DE CONSULTA
# =============================================================================

def limpar_cnpj(cnpj: str) -> str:
    """Remove caracteres não numéricos do CNPJ."""
    if not cnpj or pd.isna(cnpj):
        return ""
    return re.sub(r'\D', '', str(cnpj))


def consultar_brasilapi(cnpj: str) -> dict:
    """Consulta CNPJ na BrasilAPI."""
    try:
        url = f"{CONFIG['brasilapi_url']}{cnpj}"
        response = requests.get(url, timeout=CONFIG['timeout'])
        
        if response.status_code == 200:
            dados = response.json()
            return {
                'sucesso': True,
                'fonte': 'BrasilAPI',
                'situacao': dados.get('descricao_situacao_cadastral', ''),
                'razao_social_rf': dados.get('razao_social', ''),
                'nome_fantasia_rf': dados.get('nome_fantasia', ''),
                'cnae_principal': dados.get('cnae_fiscal_descricao', ''),
                'data_abertura': dados.get('data_inicio_atividade', ''),
                'porte': dados.get('porte', ''),
                'natureza_juridica': dados.get('natureza_juridica', ''),
                'capital_social': dados.get('capital_social', 0),
                'logradouro': dados.get('logradouro', ''),
                'numero': dados.get('numero', ''),
                'bairro': dados.get('bairro', ''),
                'municipio': dados.get('municipio', ''),
                'uf': dados.get('uf', ''),
                'cep': dados.get('cep', ''),
            }
        else:
            return {'sucesso': False, 'erro': f'HTTP {response.status_code}'}
            
    except Exception as e:
        return {'sucesso': False, 'erro': str(e)}


def consultar_receitaws(cnpj: str) -> dict:
    """Consulta CNPJ na ReceitaWS (fallback)."""
    try:
        url = f"{CONFIG['receitaws_url']}{cnpj}"
        response = requests.get(url, timeout=CONFIG['timeout'])
        
        if response.status_code == 200:
            dados = response.json()
            
            if dados.get('status') == 'ERROR':
                return {'sucesso': False, 'erro': dados.get('message', 'Erro desconhecido')}
            
            return {
                'sucesso': True,
                'fonte': 'ReceitaWS',
                'situacao': dados.get('situacao', ''),
                'razao_social_rf': dados.get('nome', ''),
                'nome_fantasia_rf': dados.get('fantasia', ''),
                'cnae_principal': dados.get('atividade_principal', [{}])[0].get('text', ''),
                'data_abertura': dados.get('abertura', ''),
                'porte': dados.get('porte', ''),
                'natureza_juridica': dados.get('natureza_juridica', ''),
                'capital_social': dados.get('capital_social', 0),
                'logradouro': dados.get('logradouro', ''),
                'numero': dados.get('numero', ''),
                'bairro': dados.get('bairro', ''),
                'municipio': dados.get('municipio', ''),
                'uf': dados.get('uf', ''),
                'cep': dados.get('cep', ''),
            }
        else:
            return {'sucesso': False, 'erro': f'HTTP {response.status_code}'}
            
    except Exception as e:
        return {'sucesso': False, 'erro': str(e)}


def consultar_cnpj(cnpj: str) -> dict:
    """Consulta CNPJ com fallback."""
    cnpj_limpo = limpar_cnpj(cnpj)
    
    if len(cnpj_limpo) != 14:
        return {'sucesso': False, 'erro': 'CNPJ inválido', 'cnpj': cnpj}
    
    # Tenta BrasilAPI primeiro
    resultado = consultar_brasilapi(cnpj_limpo)
    
    # Se falhou, tenta ReceitaWS
    if not resultado.get('sucesso'):
        time.sleep(0.5)  # Pequeno delay antes do fallback
        resultado = consultar_receitaws(cnpj_limpo)
    
    resultado['cnpj'] = cnpj_limpo
    return resultado


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def validar_cnpjs_lote(caminho_arquivo: str, limite: int = None):
    """
    Valida todos os CNPJs de um arquivo de prospecção.
    
    Args:
        caminho_arquivo: Caminho para o Excel
        limite: Número máximo de CNPJs a validar (None = todos)
    """
    print("\n" + "="*70)
    print("VALIDAÇÃO EM LOTE - RECEITA FEDERAL")
    print("="*70)
    print("APIs: BrasilAPI (primária) + ReceitaWS (fallback)")
    print("Custo: GRATUITO")
    print("="*70)
    
    # Carrega arquivo
    logger.info(f"Carregando arquivo: {caminho_arquivo}")
    
    xlsx = pd.ExcelFile(caminho_arquivo)
    if "Empresas" in xlsx.sheet_names:
        df = pd.read_excel(caminho_arquivo, sheet_name="Empresas", dtype=str)
    else:
        df = pd.read_excel(caminho_arquivo, dtype=str)
    
    logger.info(f"Empresas carregadas: {len(df)}")
    
    # Encontra coluna de CNPJ
    col_cnpj = None
    for col in df.columns:
        if 'CNPJ' in col.upper():
            col_cnpj = col
            break
    
    if not col_cnpj:
        print("❌ Erro: Coluna CNPJ não encontrada")
        return None
    
    # Limita se necessário
    if limite:
        df = df.head(limite)
        logger.info(f"Limitado a {limite} empresas")
    
    total = len(df)
    print(f"\nValidando {total} CNPJs...")
    tempo_estimado = total * CONFIG['delay_entre_requisicoes'] / 60
    print(f"Tempo estimado: ~{tempo_estimado:.1f} minutos\n")
    
    # Processa cada CNPJ
    resultados = []
    ativos = 0
    inativos = 0
    erros = 0
    
    for idx, row in df.iterrows():
        cnpj = row.get(col_cnpj, '')
        nome = row.get('NOME FANTASIA', '') or row.get('RAZÃO SOCIAL', '') or 'N/A'
        nome = str(nome)[:30] if pd.notna(nome) else 'N/A'
        
        # Consulta
        resultado = consultar_cnpj(cnpj)
        
        # Adiciona dados originais
        resultado['nome_original'] = nome
        resultado['cnpj_original'] = cnpj
        
        resultados.append(resultado)
        
        # Log de progresso
        if resultado.get('sucesso'):
            situacao = resultado.get('situacao', '').upper()
            if 'ATIV' in situacao:
                ativos += 1
                status = "✓ ATIVA"
            else:
                inativos += 1
                status = f"✗ {situacao[:15]}"
            print(f"[{idx+1}/{total}] {nome:<30} → {status}")
        else:
            erros += 1
            print(f"[{idx+1}/{total}] {nome:<30} → ERRO: {resultado.get('erro', 'N/A')[:20]}")
        
        # Delay entre requisições
        if idx < total - 1:
            time.sleep(CONFIG['delay_entre_requisicoes'])
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DA VALIDAÇÃO")
    print("="*70)
    print(f"Total de CNPJs: {total}")
    print(f"Empresas ATIVAS: {ativos} ({ativos/total*100:.1f}%)")
    print(f"Empresas INATIVAS/BAIXADAS: {inativos} ({inativos/total*100:.1f}%)")
    print(f"Erros de consulta: {erros} ({erros/total*100:.1f}%)")
    
    # Cria DataFrame de resultados
    df_resultados = pd.DataFrame(resultados)
    
    # Identifica divergências
    divergencias = df_resultados[
        (df_resultados['sucesso'] == True) & 
        (~df_resultados['situacao'].str.upper().str.contains('ATIV', na=False))
    ]
    
    if len(divergencias) > 0:
        print(f"\n⚠️ DIVERGÊNCIAS ENCONTRADAS ({len(divergencias)}):")
        print("-" * 70)
        for _, row in divergencias.iterrows():
            print(f"  • {row['nome_original'][:35]:<35} | {row['situacao']}")
    
    # Salva resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = f"validacao_receita_{timestamp}.xlsx"
    
    with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
        # Aba principal
        df_resultados.to_excel(writer, sheet_name='Validacao', index=False)
        
        # Aba de divergências
        if len(divergencias) > 0:
            divergencias.to_excel(writer, sheet_name='Divergencias', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_cnpjs': total,
            'empresas_ativas': ativos,
            'empresas_inativas': inativos,
            'erros_consulta': erros,
            'taxa_ativas': f"{ativos/total*100:.1f}%",
            'divergencias': len(divergencias),
            'data_validacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'apis_utilizadas': 'BrasilAPI + ReceitaWS',
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
        print("Uso: python validar_receita.py <arquivo_prospeccao> [limite]")
        print("")
        print("Exemplos:")
        print('  python validar_receita.py "data/input/Saude - RIB.xlsx"')
        print('  python validar_receita.py "data/input/Saude - RIB.xlsx" 10')
        print("")
        print("APIs: BrasilAPI (primária) + ReceitaWS (fallback)")
        print("Custo: GRATUITO")
        sys.exit(1)
    
    arquivo = sys.argv[1]
    limite = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(arquivo):
        print(f"Erro: Arquivo não encontrado: {arquivo}")
        sys.exit(1)
    
    validar_cnpjs_lote(arquivo, limite)