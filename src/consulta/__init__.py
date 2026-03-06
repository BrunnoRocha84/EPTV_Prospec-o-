"""
Módulo de Consultas Externas
EPTV Prospecção

Submódulos:
- receita_federal: Consulta situação cadastral de CNPJs
- crowley: Coleta dados de investimento em mídia (rádio)
"""

from .receita_federal import (
    consultar_cnpj,
    consultar_lote,
    verificar_situacao_ativa,
    CacheCNPJ,
)