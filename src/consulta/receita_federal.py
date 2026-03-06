"""
Módulo de Consulta à Receita Federal
EPTV Prospecção

Consulta situação cadastral de CNPJs usando APIs públicas.
Estratégia: BrasilAPI (primária) + ReceitaWS (fallback)

APIs utilizadas:
- BrasilAPI: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
- ReceitaWS: https://receitaws.com.br/v1/cnpj/{cnpj}
"""

import requests
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path
import json

# Importa utilitários do projeto
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.helpers import normalizar_cnpj, setup_logger

# Configura logger
logger = setup_logger("receita_federal", "INFO")


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

CONFIG = {
    'brasil_api': {
        'url': 'https://brasilapi.com.br/api/cnpj/v1/{cnpj}',
        'timeout': 30,
        'delay': 0.5,  # Delay entre requisições (segundos)
    },
    'receita_ws': {
        'url': 'https://receitaws.com.br/v1/cnpj/{cnpj}',
        'timeout': 30,
        'delay': 20,  # ReceitaWS tem limite de 3/minuto na versão gratuita
    },
    'max_retries': 3,
    'retry_delay': 5,
}


# =============================================================================
# FUNÇÕES DE CONSULTA
# =============================================================================

def consultar_cnpj(cnpj: str) -> Optional[Dict]:
    """
    Consulta CNPJ nas APIs públicas.
    
    Tenta BrasilAPI primeiro, se falhar usa ReceitaWS como fallback.
    
    Args:
        cnpj: CNPJ (com ou sem formatação)
        
    Returns:
        Dicionário com dados da empresa ou None se não encontrado
    """
    cnpj_limpo = normalizar_cnpj(cnpj)
    
    if not cnpj_limpo or len(cnpj_limpo) != 14:
        logger.warning(f"CNPJ inválido: {cnpj}")
        return None
    
    # Tenta BrasilAPI primeiro
    resultado = _consultar_brasil_api(cnpj_limpo)
    
    if resultado:
        return resultado
    
    # Fallback para ReceitaWS
    logger.info(f"Tentando fallback ReceitaWS para {cnpj_limpo}")
    resultado = _consultar_receita_ws(cnpj_limpo)
    
    return resultado


def _consultar_brasil_api(cnpj: str) -> Optional[Dict]:
    """Consulta CNPJ na BrasilAPI."""
    
    url = CONFIG['brasil_api']['url'].format(cnpj=cnpj)
    
    for tentativa in range(CONFIG['max_retries']):
        try:
            response = requests.get(
                url,
                timeout=CONFIG['brasil_api']['timeout'],
                headers={'User-Agent': 'EPTV-Prospeccao/1.0'}
            )
            
            if response.status_code == 200:
                dados = response.json()
                return _normalizar_resposta_brasil_api(dados)
            
            elif response.status_code == 404:
                logger.warning(f"CNPJ não encontrado na BrasilAPI: {cnpj}")
                return None
            
            elif response.status_code == 429:
                logger.warning("Rate limit BrasilAPI, aguardando...")
                time.sleep(CONFIG['retry_delay'])
                continue
            
            else:
                logger.warning(f"Erro BrasilAPI: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout BrasilAPI (tentativa {tentativa + 1})")
            time.sleep(CONFIG['retry_delay'])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão BrasilAPI: {e}")
            break
    
    return None


def _consultar_receita_ws(cnpj: str) -> Optional[Dict]:
    """Consulta CNPJ na ReceitaWS (fallback)."""
    
    url = CONFIG['receita_ws']['url'].format(cnpj=cnpj)
    
    for tentativa in range(CONFIG['max_retries']):
        try:
            response = requests.get(
                url,
                timeout=CONFIG['receita_ws']['timeout'],
                headers={'User-Agent': 'EPTV-Prospeccao/1.0'}
            )
            
            if response.status_code == 200:
                dados = response.json()
                
                # ReceitaWS retorna status dentro do JSON
                if dados.get('status') == 'ERROR':
                    logger.warning(f"ReceitaWS erro: {dados.get('message')}")
                    return None
                
                return _normalizar_resposta_receita_ws(dados)
            
            elif response.status_code == 429:
                logger.warning("Rate limit ReceitaWS (3/min), aguardando 20s...")
                time.sleep(CONFIG['receita_ws']['delay'])
                continue
            
            else:
                logger.warning(f"Erro ReceitaWS: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ReceitaWS (tentativa {tentativa + 1})")
            time.sleep(CONFIG['retry_delay'])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ReceitaWS: {e}")
            break
    
    return None


# =============================================================================
# NORMALIZAÇÃO DE RESPOSTAS
# =============================================================================

def _normalizar_resposta_brasil_api(dados: Dict) -> Dict:
    """Normaliza resposta da BrasilAPI para formato padrão."""
    
    return {
        'cnpj': dados.get('cnpj'),
        'razao_social': dados.get('razao_social'),
        'nome_fantasia': dados.get('nome_fantasia'),
        'situacao_cadastral': dados.get('descricao_situacao_cadastral'),
        'data_situacao': dados.get('data_situacao_cadastral'),
        'motivo_situacao': dados.get('motivo_situacao_cadastral'),
        'cnae_principal': dados.get('cnae_fiscal'),
        'cnae_descricao': dados.get('cnae_fiscal_descricao'),
        'cnaes_secundarios': [c.get('codigo') for c in dados.get('cnaes_secundarios', [])],
        'natureza_juridica': dados.get('natureza_juridica'),
        'porte': dados.get('porte'),
        'capital_social': dados.get('capital_social'),
        'logradouro': dados.get('logradouro'),
        'numero': dados.get('numero'),
        'complemento': dados.get('complemento'),
        'bairro': dados.get('bairro'),
        'cidade': dados.get('municipio'),
        'uf': dados.get('uf'),
        'cep': dados.get('cep'),
        'telefone': dados.get('ddd_telefone_1'),
        'email': dados.get('email'),
        'data_inicio_atividade': dados.get('data_inicio_atividade'),
        'fonte': 'BrasilAPI',
        'dados_completos': dados,
    }


def _normalizar_resposta_receita_ws(dados: Dict) -> Dict:
    """Normaliza resposta da ReceitaWS para formato padrão."""
    
    # Extrai CNAEs secundários
    cnaes_sec = []
    for atividade in dados.get('atividades_secundarias', []):
        if atividade.get('code'):
            cnaes_sec.append(atividade.get('code').replace('.', '').replace('-', ''))
    
    return {
        'cnpj': dados.get('cnpj', '').replace('.', '').replace('/', '').replace('-', ''),
        'razao_social': dados.get('nome'),
        'nome_fantasia': dados.get('fantasia'),
        'situacao_cadastral': dados.get('situacao'),
        'data_situacao': dados.get('data_situacao'),
        'motivo_situacao': dados.get('motivo_situacao'),
        'cnae_principal': dados.get('atividade_principal', [{}])[0].get('code', '').replace('.', '').replace('-', ''),
        'cnae_descricao': dados.get('atividade_principal', [{}])[0].get('text'),
        'cnaes_secundarios': cnaes_sec,
        'natureza_juridica': dados.get('natureza_juridica'),
        'porte': dados.get('porte'),
        'capital_social': dados.get('capital_social'),
        'logradouro': dados.get('logradouro'),
        'numero': dados.get('numero'),
        'complemento': dados.get('complemento'),
        'bairro': dados.get('bairro'),
        'cidade': dados.get('municipio'),
        'uf': dados.get('uf'),
        'cep': dados.get('cep'),
        'telefone': dados.get('telefone'),
        'email': dados.get('email'),
        'data_inicio_atividade': dados.get('abertura'),
        'fonte': 'ReceitaWS',
        'dados_completos': dados,
    }


# =============================================================================
# CONSULTA EM LOTE
# =============================================================================

def consultar_lote(cnpjs: List[str], delay: float = 1.0, callback=None) -> Dict[str, Dict]:
    """
    Consulta múltiplos CNPJs com controle de rate limit.
    
    Args:
        cnpjs: Lista de CNPJs
        delay: Delay entre consultas (segundos)
        callback: Função chamada após cada consulta (para progresso)
        
    Returns:
        Dicionário {cnpj: dados}
    """
    resultados = {}
    total = len(cnpjs)
    
    logger.info(f"Iniciando consulta em lote de {total} CNPJs")
    
    for i, cnpj in enumerate(cnpjs, 1):
        cnpj_limpo = normalizar_cnpj(cnpj)
        
        if not cnpj_limpo:
            continue
        
        # Consulta
        dados = consultar_cnpj(cnpj_limpo)
        
        if dados:
            resultados[cnpj_limpo] = dados
        
        # Callback de progresso
        if callback:
            callback(i, total, cnpj_limpo, dados)
        
        # Log de progresso a cada 10
        if i % 10 == 0:
            logger.info(f"Progresso: {i}/{total} ({len(resultados)} encontrados)")
        
        # Delay entre consultas
        if i < total:
            time.sleep(delay)
    
    logger.info(f"Consulta em lote concluída: {len(resultados)}/{total} encontrados")
    
    return resultados


def verificar_situacao_ativa(cnpj: str) -> bool:
    """
    Verifica rapidamente se CNPJ está ativo.
    
    Returns:
        True se ATIVA, False caso contrário
    """
    dados = consultar_cnpj(cnpj)
    
    if not dados:
        return False
    
    situacao = dados.get('situacao_cadastral', '').upper()
    return situacao == 'ATIVA'


# =============================================================================
# CACHE LOCAL (OPCIONAL)
# =============================================================================

class CacheCNPJ:
    """Cache local para evitar consultas repetidas."""
    
    def __init__(self, arquivo: str = None):
        self.arquivo = arquivo or '/tmp/cache_cnpj.json'
        self.cache = self._carregar()
    
    def _carregar(self) -> Dict:
        """Carrega cache do arquivo."""
        try:
            with open(self.arquivo, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _salvar(self):
        """Salva cache no arquivo."""
        try:
            with open(self.arquivo, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")
    
    def get(self, cnpj: str) -> Optional[Dict]:
        """Busca CNPJ no cache."""
        cnpj_limpo = normalizar_cnpj(cnpj)
        return self.cache.get(cnpj_limpo)
    
    def set(self, cnpj: str, dados: Dict):
        """Adiciona CNPJ ao cache."""
        cnpj_limpo = normalizar_cnpj(cnpj)
        self.cache[cnpj_limpo] = dados
        self._salvar()
    
    def consultar_com_cache(self, cnpj: str) -> Optional[Dict]:
        """Consulta com cache."""
        # Tenta cache primeiro
        dados = self.get(cnpj)
        if dados:
            logger.debug(f"Cache hit: {cnpj}")
            return dados
        
        # Consulta API
        dados = consultar_cnpj(cnpj)
        if dados:
            self.set(cnpj, dados)
        
        return dados


# =============================================================================
# EXECUÇÃO DIRETA (PARA TESTES)
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cnpj_teste = sys.argv[1]
        print(f"\nConsultando CNPJ: {cnpj_teste}")
        print("-" * 50)
        
        resultado = consultar_cnpj(cnpj_teste)
        
        if resultado:
            print(f"✓ Razão Social: {resultado.get('razao_social')}")
            print(f"✓ Nome Fantasia: {resultado.get('nome_fantasia')}")
            print(f"✓ Situação: {resultado.get('situacao_cadastral')}")
            print(f"✓ CNAE: {resultado.get('cnae_principal')} - {resultado.get('cnae_descricao')}")
            print(f"✓ Cidade/UF: {resultado.get('cidade')}/{resultado.get('uf')}")
            print(f"✓ Fonte: {resultado.get('fonte')}")
        else:
            print("✗ CNPJ não encontrado")
    else:
        print("Uso: python receita_federal.py <cnpj>")
        print("Exemplo: python receita_federal.py 00.000.000/0001-91")