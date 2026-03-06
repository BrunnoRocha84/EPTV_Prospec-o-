# Guia de Contribuição

Obrigado por considerar contribuir com o projeto! Este documento fornece diretrizes para contribuições.

## 📋 Pré-requisitos

- Python 3.10+
- Git
- Acesso ao Azure DevOps

## 🚀 Configuração do Ambiente

```bash
# 1. Clonar o repositório
git clone https://dev.azure.com/data-and-crm/General/_git/eptv-prospeccao
cd eptv_prospeccao

# 2. Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais
```

## 📝 Padrões de Código

### Estilo

- Seguir PEP 8
- Máximo 100 caracteres por linha
- Usar type hints sempre que possível
- Docstrings em formato Google

### Exemplo de função bem documentada

```python
def calcular_similaridade(texto1: str, texto2: str) -> float:
    """
    Calcula a similaridade entre dois textos usando SequenceMatcher.

    Args:
        texto1: Primeiro texto para comparação.
        texto2: Segundo texto para comparação.

    Returns:
        Score de similaridade entre 0.0 e 1.0.

    Raises:
        ValueError: Se algum dos textos for None.

    Example:
        >>> calcular_similaridade("UNIMED", "UNIMED BRASIL")
        0.75
    """
    if texto1 is None or texto2 is None:
        raise ValueError("Textos não podem ser None")
    
    # implementação...
    return score
```

### Estrutura de módulos

```python
"""
Descrição do módulo.

Este módulo implementa...

Example:
    python -m src.modulo.arquivo "parametro"
"""

# Imports da biblioteca padrão
import os
import sys

# Imports de terceiros
import pandas as pd

# Imports locais
from src.utils.helpers import setup_logger

# Constantes
CONFIG = {...}

# Logger
logger = setup_logger(__name__)


# Classes e funções
def funcao_principal():
    ...


# Entry point
if __name__ == "__main__":
    ...
```

## 🌿 Workflow de Git

### Branches

- `main` - Código de produção
- `develop` - Desenvolvimento ativo
- `feature/*` - Novas funcionalidades
- `bugfix/*` - Correções de bugs
- `hotfix/*` - Correções urgentes em produção

### Commits

Usar [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: adiciona cruzamento com nova base de mídia
fix: corrige bug no fuzzy matching
docs: atualiza README com novos exemplos
refactor: reorganiza estrutura de pastas
test: adiciona testes para módulo de scoring
chore: atualiza dependências
```

### Fluxo de trabalho

```bash
# 1. Criar branch a partir de develop
git checkout develop
git pull origin develop
git checkout -b feature/nova-funcionalidade

# 2. Fazer alterações e commits
git add .
git commit -m "feat: implementa nova funcionalidade"

# 3. Atualizar com develop
git fetch origin
git rebase origin/develop

# 4. Push
git push origin feature/nova-funcionalidade

# 5. Criar Pull Request no Azure DevOps
```

## 🧪 Testes

### Executar testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=src

# Apenas um módulo
pytest tests/test_matching.py
```

### Estrutura de testes

```python
# tests/test_matching.py
import pytest
from src.matching.fuzzy import calcular_similaridade


class TestCalcularSimilaridade:
    """Testes para a função calcular_similaridade."""

    def test_textos_identicos(self):
        """Textos iguais devem retornar 1.0."""
        assert calcular_similaridade("UNIMED", "UNIMED") == 1.0

    def test_textos_diferentes(self):
        """Textos diferentes devem retornar < 1.0."""
        score = calcular_similaridade("UNIMED", "HOSPITAL")
        assert 0 <= score < 1.0

    def test_texto_vazio(self):
        """Texto vazio deve retornar 0.0."""
        assert calcular_similaridade("", "TEXTO") == 0.0
```

## 📁 Estrutura de Pastas

Ao adicionar novos módulos, seguir a estrutura existente:

```
src/
├── novo_modulo/
│   ├── __init__.py      # Exports do módulo
│   └── implementacao.py # Lógica principal
```

## 🔍 Code Review

### Checklist para PRs

- [ ] Código segue os padrões de estilo
- [ ] Docstrings adicionadas/atualizadas
- [ ] Testes adicionados para novas funcionalidades
- [ ] Testes passando localmente
- [ ] CHANGELOG.md atualizado
- [ ] README.md atualizado (se necessário)
- [ ] Sem credenciais ou dados sensíveis

### Processo de review

1. Criar PR no Azure DevOps
2. Aguardar review de pelo menos 1 pessoa
3. Resolver comentários
4. Merge após aprovação

## ❓ Dúvidas

- Abrir issue no Azure DevOps
- Contatar equipe de Inteligência Comercial

---

Obrigado por contribuir! 🎉