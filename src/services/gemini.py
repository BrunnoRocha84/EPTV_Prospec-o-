"""
Módulo de Verificação de Publicidade - Google Gemini
EPTV Prospecção

Usa o Google Gemini para verificar se a empresa faz publicidade
em TV, rádio, OOH, redes sociais ou links patrocinados.

API: Google Gemini (AI Studio)
Custo: GRATUITO (tier gratuito: 1.000 req/dia)
Modelo: gemini-1.5-flash (mais rápido e econômico)

Configuração:
    1. Acesse https://aistudio.google.com/
    2. Clique em "Get API Key" → "Create API Key"
    3. Crie um arquivo .env na raiz do projeto com:
       GEMINI_API_KEY=sua_chave_aqui

Uso:
    python verificar_publicidade.py <arquivo_prospeccao> [limite]
    
Exemplo:
    python verificar_publicidade.py "data/input/Saude.xlsx"
    python verificar_publicidade.py "data/input/Saude.xlsx" 10
"""

import pandas as pd
import requests
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.helpers import setup_logger

# Configura logger
logger = setup_logger("gemini", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'api_key': os.getenv('GEMINI_API_KEY', ''),
    'modelo': 'gemini-2.5-flash',
    'base_url': 'https://generativelanguage.googleapis.com/v1beta/models',
    'delay_entre_requisicoes': 1.0,  # 1 segundo entre requisições
    'timeout': 30,
    'max_tokens': 1000,
}

PROMPT_TEMPLATE = """Empresa: {nome_empresa} | Setor: {setor} | Cidade: {cidade}-{estado}

Essa empresa faz publicidade em TV, Rádio ou OOH? Responda APENAS em JSON:
{{"faz_publicidade": true, "canais": ["TV","Radio","OOH"], "confianca": "ALTA"}}

Regras:
- canais: lista apenas os canais que a empresa provavelmente usa
- confianca: ALTA se conhece a empresa, BAIXA se não conhece
- Se não conhecer, responda baseado no porte típico do setor
"""


# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO
# =============================================================================

def verificar_publicidade_gemini(nome_empresa: str, setor: str = "", cidade: str = "", estado: str = "") -> dict:
    """
    Verifica se a empresa faz publicidade usando Google Gemini.
    
    Retorna:
        dict com análise de publicidade
    """
    if not CONFIG['api_key']:
        return {
            'sucesso': False,
            'erro': 'API Key não configurada. Crie um arquivo .env com GEMINI_API_KEY=sua_chave'
        }
    
    if not nome_empresa or len(nome_empresa) < 3:
        return {
            'sucesso': False,
            'erro': 'Nome da empresa muito curto ou vazio'
        }
    
    try:
        # Monta o prompt
        prompt = PROMPT_TEMPLATE.format(
            nome_empresa=nome_empresa,
            setor=setor or "Não informado",
            cidade=cidade or "Não informada",
            estado=estado or "Não informado"
        )
        
        # URL da API
        url = f"{CONFIG['base_url']}/{CONFIG['modelo']}:generateContent?key={CONFIG['api_key']}"
        
        # Payload
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": CONFIG['max_tokens'],
            }
        }
        
        # Faz a requisição
        response = requests.post(
            url,
            json=payload,
            timeout=CONFIG['timeout']
        )
        
        if response.status_code != 200:
            return {
                'sucesso': False,
                'erro': f'HTTP {response.status_code}: {response.text[:200]}'
            }
        
        dados = response.json()
        
        # Extrai o texto da resposta
        if 'candidates' not in dados or not dados['candidates']:
            return {
                'sucesso': False,
                'erro': 'Resposta vazia do Gemini'
            }
        
        texto_resposta = dados['candidates'][0]['content']['parts'][0]['text']
        
        # Tenta extrair JSON da resposta
        try:
            # Remove possíveis marcadores de código
            texto_limpo = texto_resposta.strip()
            if texto_limpo.startswith('```json'):
                texto_limpo = texto_limpo[7:]
            if texto_limpo.startswith('```'):
                texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith('```'):
                texto_limpo = texto_limpo[:-3]
            texto_limpo = texto_limpo.strip()
            
            resultado_json = json.loads(texto_limpo)
            # Normaliza campos para o formato esperado
            return {
                'sucesso': True,
                'faz_publicidade': resultado_json.get('faz_publicidade', False),
                'canais_provaveis': resultado_json.get('canais', resultado_json.get('canais_provaveis', [])),
                'confianca': resultado_json.get('confianca', 'BAIXA'),
                'justificativa': resultado_json.get('justificativa', ''),
                'erro': None,
                'resposta_raw': texto_resposta
            }
            
        except json.JSONDecodeError:
            # Se não conseguir fazer parse, retorna o texto bruto
            return {
                'sucesso': True,
                'faz_publicidade': None,
                'canais_provaveis': [],
                'confianca': 'BAIXA',
                'justificativa': texto_resposta[:200],
                'erro': 'Não foi possível extrair JSON',
                'resposta_raw': texto_resposta
            }
        
    except requests.exceptions.Timeout:
        return {
            'sucesso': False,
            'erro': 'Timeout na requisição'
        }
    except Exception as e:
        return {
            'sucesso': False,
            'erro': str(e)
        }


def encontrar_colunas(df: pd.DataFrame) -> dict:
    """
    Encontra automaticamente as colunas relevantes no DataFrame.
    """
    colunas = {}
    
    for col in df.columns:
        col_upper = col.upper()
        
        if 'NOME FANTASIA' in col_upper or 'FANTASIA' in col_upper:
            colunas['nome_fantasia'] = col
        elif 'RAZÃO SOCIAL' in col_upper or 'RAZAO SOCIAL' in col_upper:
            colunas['razao_social'] = col
        elif 'CNAE' in col_upper and 'DESCRICAO' in col_upper:
            colunas['setor'] = col
        elif col_upper in ['SETOR', 'ATIVIDADE', 'RAMO']:
            colunas['setor'] = col
        elif 'CIDADE' in col_upper or 'MUNICIPIO' in col_upper or 'MUNICÍPIO' in col_upper:
            colunas['cidade'] = col
        elif col_upper in ['UF', 'ESTADO'] or 'ESTADO' in col_upper:
            colunas['estado'] = col
    
    return colunas


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def verificar_publicidade_empresas(caminho_arquivo: str, limite: int = None):
    """
    Verifica publicidade de todas as empresas no arquivo.
    
    Args:
        caminho_arquivo: Caminho para o Excel de prospecção
        limite: Número máximo de empresas a verificar (None = todas)
    """
    print("\n" + "="*70)
    print("VERIFICAÇÃO DE PUBLICIDADE - GOOGLE GEMINI")
    print("="*70)
    print(f"API: Gratuita (tier free) | Modelo: {CONFIG['modelo']}")
    print("="*70)
    
    # Verifica API Key
    if not CONFIG['api_key']:
        print("\n❌ ERRO: API Key não configurada!")
        print("\nPara configurar:")
        print("1. Acesse https://aistudio.google.com/")
        print("2. Clique em 'Get API Key' → 'Create API Key'")
        print("3. Crie um arquivo .env na raiz do projeto com:")
        print("   GEMINI_API_KEY=sua_chave_aqui")
        return None
    
    print(f"\n✓ API Key configurada: {CONFIG['api_key'][:10]}...")
    
    # Carrega arquivo
    logger.info(f"Carregando arquivo: {caminho_arquivo}")
    
    xlsx = pd.ExcelFile(caminho_arquivo)
    if "Empresas" in xlsx.sheet_names:
        df = pd.read_excel(caminho_arquivo, sheet_name="Empresas", dtype=str)
    else:
        df = pd.read_excel(caminho_arquivo, dtype=str)
    
    logger.info(f"Empresas carregadas: {len(df)}")
    
    # Encontra colunas
    colunas = encontrar_colunas(df)
    logger.info(f"Colunas encontradas: {colunas}")
    
    # Limita se necessário
    if limite:
        df = df.head(limite)
        logger.info(f"Limitado a {limite} empresas")
    
    # Processa cada empresa
    resultados = []
    total = len(df)
    sucessos = 0
    fazem_publicidade = 0
    
    print(f"\nVerificando {total} empresas...")
    tempo_estimado = total * CONFIG['delay_entre_requisicoes'] / 60
    print(f"Tempo estimado: ~{tempo_estimado:.1f} minutos\n")
    
    for idx, row in df.iterrows():
        # Identifica empresa
        nome_fantasia = row.get(colunas.get('nome_fantasia', ''), '')
        razao_social = row.get(colunas.get('razao_social', ''), '')
        nome = nome_fantasia if pd.notna(nome_fantasia) and nome_fantasia else razao_social
        nome = str(nome) if pd.notna(nome) else 'N/A'
        
        setor = row.get(colunas.get('setor', ''), '') or ''
        cidade = row.get(colunas.get('cidade', ''), '') or ''
        estado = row.get(colunas.get('estado', ''), '') or ''
        
        # Verifica publicidade
        resultado = verificar_publicidade_gemini(nome, setor, cidade, estado)
        
        # Adiciona dados da empresa
        resultado['empresa'] = nome[:50]
        resultado['cnpj'] = row.get('CNPJ', '')
        resultado['setor'] = setor[:50] if setor else ''
        resultado['cidade'] = cidade
        resultado['estado'] = estado
        
        resultados.append(resultado)
        
        # Log de progresso
        if resultado.get('sucesso'):
            sucessos += 1
            faz_pub = resultado.get('faz_publicidade', False)
            if faz_pub:
                fazem_publicidade += 1
                canais = ', '.join(resultado.get('canais_provaveis', [])[:3])
                print(f"[{idx+1}/{total}] ✓ {nome[:30]:<30} → SIM ({canais})")
            else:
                print(f"[{idx+1}/{total}] ✓ {nome[:30]:<30} → NÃO/DESCONHECIDO")
        else:
            print(f"[{idx+1}/{total}] ✗ {nome[:30]:<30} → ERRO: {resultado.get('erro', 'N/A')[:30]}")
        
        # Delay entre requisições
        if idx < total - 1:
            time.sleep(CONFIG['delay_entre_requisicoes'])
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DA VERIFICAÇÃO")
    print("="*70)
    print(f"Total de empresas: {total}")
    print(f"Consultas com sucesso: {sucessos} ({sucessos/total*100:.1f}%)")
    print(f"Provavelmente fazem publicidade: {fazem_publicidade} ({fazem_publicidade/total*100:.1f}%)")
    
    # Cria DataFrame de resultados
    df_resultados = pd.DataFrame(resultados)
    
    # Conta canais
    if 'canais_provaveis' in df_resultados.columns:
        todos_canais = []
        for canais in df_resultados['canais_provaveis'].dropna():
            if isinstance(canais, list):
                todos_canais.extend(canais)
        if todos_canais:
            from collections import Counter
            contagem_canais = Counter(todos_canais)
            print("\n📊 CANAIS MAIS PROVÁVEIS:")
            for canal, count in contagem_canais.most_common(10):
                print(f"   • {canal}: {count}")
    
    # Salva resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = f"verificacao_publicidade_{timestamp}.xlsx"
    
    # Prepara DataFrame para salvar (converte listas para string)
    df_salvar = df_resultados.copy()
    if 'canais_provaveis' in df_salvar.columns:
        df_salvar['canais_provaveis'] = df_salvar['canais_provaveis'].apply(
            lambda x: ', '.join(x) if isinstance(x, list) else str(x)
        )
    if 'resposta_raw' in df_salvar.columns:
        df_salvar = df_salvar.drop(columns=['resposta_raw'])
    
    with pd.ExcelWriter(arquivo_saida, engine='openpyxl') as writer:
        df_salvar.to_excel(writer, sheet_name='Resultados', index=False)
        
        # Aba de resumo
        resumo = pd.DataFrame([{
            'total_empresas': total,
            'consultas_sucesso': sucessos,
            'fazem_publicidade': fazem_publicidade,
            'nao_fazem_ou_desconhecido': total - fazem_publicidade,
            'data_verificacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'api_utilizada': 'Google Gemini',
            'modelo': CONFIG['modelo'],
            'custo': 'GRATUITO (tier free)'
        }])
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
    
    print(f"\n✓ Resultados salvos em: {arquivo_saida}")
    
    return df_resultados


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python verificar_publicidade.py <arquivo_prospeccao> [limite]")
        print("")
        print("Exemplos:")
        print('  python verificar_publicidade.py "data/input/Saude.xlsx"')
        print('  python verificar_publicidade.py "data/input/Saude.xlsx" 10')
        print("")
        print("Configuração:")
        print("  1. Acesse https://aistudio.google.com/")
        print("  2. Crie uma API Key")
        print("  3. Crie arquivo .env com: GEMINI_API_KEY=sua_chave")
        print("")
        print("API: Google Gemini - GRATUITA (1.000 req/dia)")
        sys.exit(1)
    
    arquivo = sys.argv[1]
    limite = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(arquivo):
        print(f"Erro: Arquivo não encontrado: {arquivo}")
        sys.exit(1)
    
    verificar_publicidade_empresas(arquivo, limite)