# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-03-06

### Adicionado
- Pipeline principal (`main.py`) com 6 etapas de processamento
- Módulo de ingestão para arquivos Excel/CSV
- Módulo de validação de situação cadastral e contatos
- Módulo de enriquecimento digital (redes sociais)
- Módulo de matching fuzzy para cruzamento com bases de mídia
- Módulo de scoring com priorização (MUITO_ALTA, ALTA, MÉDIA, BAIXA)
- Cruzamento com base ADI (TV)
- Cruzamento com base Crowley (Rádio)
- Cruzamento com base Kantar (OOH)
- Serviço de consulta Receita Federal (BrasilAPI + ReceitaWS)
- Serviço de verificação de publicidade via Google Gemini
- Serviço de geocodificação via Nominatim
- Documentação completa (README.md, CONTRIBUTING.md)
- Configuração de projeto (pyproject.toml, requirements.txt)
- Arquivos de exemplo (.env.example)

### Corrigido
- Bug no fuzzy matching que retornava 0 matches
- Função `calcular_similaridade` com bônus para primeira palavra igual
- Truncamento de resposta do Gemini (max_tokens aumentado)
- Indentação no módulo `receita_federal.py`

### Segurança
- API Keys protegidas via arquivo `.env`
- `.gitignore` configurado para não versionar dados sensíveis

## [0.1.0] - 2026-03-03

### Adicionado
- Estrutura inicial do projeto
- Módulos básicos de ingestão e validação
- Primeira versão do scoring

---

## Tipos de mudanças

- `Adicionado` para novos recursos
- `Modificado` para mudanças em recursos existentes
- `Depreciado` para recursos que serão removidos em breve
- `Removido` para recursos removidos
- `Corrigido` para correção de bugs
- `Segurança` para vulnerabilidades