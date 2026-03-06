#!/usr/bin/env python3
"""
Pipeline de Prospecção Comercial - EPTV
=======================================

Script principal que orquestra a execução do pipeline completo.

Uso:
    python main.py --econodata <arquivo> [--kantar <arquivo>] [--crowley <arquivo>]
    python main.py --help

Exemplo:
    python main.py --econodata data/input/Saude.xlsx --kantar data/input/kantar.xlsx
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils import setup_logger, gerar_timestamp

# Configura logger
logger = setup_logger("pipeline", "INFO")


def parse_args():
    """Parse argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Pipeline de Refinamento de Prospecção Comercial - EPTV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py --econodata data/input/Saude.xlsx
  python main.py --econodata data/input/Saude.xlsx --kantar data/input/kantar.xlsx
  python main.py --econodata data/input/Saude.xlsx --output data/output/resultado.xlsx
        """
    )
    
    parser.add_argument(
        "--econodata", "-e",
        required=True,
        help="Caminho para arquivo Econodata (Excel ou CSV)"
    )
    
    parser.add_argument(
        "--kantar", "-k",
        required=False,
        help="Caminho para arquivo Kantar (opcional)"
    )
    
    parser.add_argument(
        "--crowley", "-c",
        required=False,
        help="Caminho para arquivo Crowley (opcional)"
    )
    
    parser.add_argument(
        "--output", "-o",
        required=False,
        help="Caminho para arquivo de saída (opcional, gera automático)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Modo verboso (mais detalhes no log)"
    )
    
    return parser.parse_args()


def main():
    """Função principal do pipeline."""
    args = parse_args()
    
    # Banner
    print("=" * 70)
    print("   PIPELINE DE REFINAMENTO DE PROSPECÇÃO COMERCIAL")
    print("   EPTV - Inteligência Comercial")
    print("=" * 70)
    print()
    
    inicio = datetime.now()
    logger.info(f"Início da execução: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verifica arquivos de entrada
    econodata_path = Path(args.econodata)
    if not econodata_path.exists():
        logger.error(f"Arquivo não encontrado: {econodata_path}")
        sys.exit(1)
    
    logger.info(f"Econodata: {econodata_path}")
    
    kantar_path = Path(args.kantar) if args.kantar else None
    if kantar_path and not kantar_path.exists():
        logger.warning(f"Arquivo Kantar não encontrado: {kantar_path}")
        kantar_path = None
    
    crowley_path = Path(args.crowley) if args.crowley else None
    if crowley_path and not crowley_path.exists():
        logger.warning(f"Arquivo Crowley não encontrado: {crowley_path}")
        crowley_path = None
    
    # Define output
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = gerar_timestamp()
        output_path = Path("data/output") / f"prospeccao_refinada_{timestamp}.xlsx"
    
    # Garante que diretório de output existe
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # =====================================================================
        # TASK 7298: Ingestão e Preparação da Base
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 1: Ingestão e Preparação da Base")
        logger.info("-" * 50)
        
        from ingestao import carregar_base, preparar_base
        
        df = carregar_base(econodata_path)
        df = preparar_base(df)
        
        logger.info(f"✓ Base carregada: {len(df)} registros")
        
        # =====================================================================
        # TASK 7299: Validação de Atividade / Existência
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 2: Validação de Atividade")
        logger.info("-" * 50)
        
        from validacao import validar_empresas
        
        df = validar_empresas(df)
        
        ativos = df['_empresa_ativa'].sum() if '_empresa_ativa' in df.columns else 'N/A'
        logger.info(f"✓ Validação concluída: {ativos} empresas ativas")
        
        # =====================================================================
        # TASK 7300: Enriquecimento Digital
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 3: Enriquecimento Digital")
        logger.info("-" * 50)
        
        from enriquecimento import avaliar_presenca_digital
        
        df = avaliar_presenca_digital(df)
        
        com_presenca = (df['_qtd_redes'] > 0).sum() if '_qtd_redes' in df.columns else 'N/A'
        logger.info(f"✓ Enriquecimento concluído: {com_presenca} com presença digital")
        
        # =====================================================================
        # TASK 7301: Cruzamento com Bases Internas
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 4: Cruzamento com Bases Internas")
        logger.info("-" * 50)
        
        from matching import cruzar_bases
        
        df = cruzar_bases(df, kantar_path, crowley_path)
        
        matches = df['_tem_match_midia'].sum() if '_tem_match_midia' in df.columns else 0
        logger.info(f"✓ Cruzamento concluído: {matches} matches encontrados")
        
        # =====================================================================
        # TASK 7302: Regras de Decisão (Scoring)
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 5: Regras de Decisão e Scoring")
        logger.info("-" * 50)
        
        from scoring import calcular_score, gerar_output
        
        df = calcular_score(df)
        
        score_medio = df['_score_final'].mean() if '_score_final' in df.columns else 'N/A'
        logger.info(f"✓ Scoring concluído. Score médio: {score_medio:.1f}")
        
        # =====================================================================
        # Geração do Output
        # =====================================================================
        logger.info("-" * 50)
        logger.info("ETAPA 6: Geração do Output")
        logger.info("-" * 50)
        
        gerar_output(df, output_path)
        
        logger.info(f"✓ Arquivo gerado: {output_path}")
        
    except ImportError as e:
        logger.error(f"Módulo não encontrado: {e}")
        logger.error("Execute o pipeline a partir do diretório raiz do projeto.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro durante execução: {e}")
        raise
    
    # Finalização
    fim = datetime.now()
    duracao = (fim - inicio).total_seconds()
    
    print()
    print("=" * 70)
    print("   ✅ PIPELINE CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print(f"   Tempo de execução: {duracao:.1f} segundos")
    print(f"   Arquivo gerado: {output_path}")
    print()


if __name__ == "__main__":
    main()
