# DEPLOY - Correção Header Personalizado PDF

## Problema Identificado
O sistema já possui header personalizado cadastrado no banco de produção, mas os PDFs gerados ainda mostram o header padrão verde ao invés do header personalizado.

## Solução Implementada

### 1. Template PDF Corrigido
- O arquivo `templates/propostas/pdf_estruturas_vale.html` foi corrigido
- Agora usa lógica condicional: **OU** header personalizado **OU** header padrão
- Quando `config.header_pdf_base64` existe, substitui COMPLETAMENTE o header verde

### 2. Sistema de Migrações
- Sistema automático de migrações já implementado em `migrations.py`  
- Executado automaticamente no deploy via Docker
- Garante que banco tenha todas as colunas necessárias

### 3. Deploy via Docker
O deploy via Docker já está configurado para aplicar todas as correções automaticamente.

## Instruções para Deploy

### Deploy Padrão (Recomendado)
```bash
# 1. Build da imagem Docker
docker build -t sige:latest .

# 2. Deploy no EasyPanel/Hostinger
# (seguir processo normal de deploy)
```

### Verificação Pós-Deploy

1. **Testar Header Personalizado:**
   - Acesse uma proposta comercial
   - Gere PDF no formato "Estruturas do Vale"
   - Verificar se header personalizado aparece no lugar do verde

2. **Página de Teste (opcional):**
   - Acesse `/teste-header` para debug
   - Mostra se header está carregado no banco

## Estrutura da Correção

```
templates/propostas/pdf_estruturas_vale.html:
{% if config and config.header_pdf_base64 %}
    <!-- Header personalizado completo -->
    <div class="custom-header">
        <img src="data:image/jpeg;base64,{{ config.header_pdf_base64 }}" alt="Header Personalizado">
    </div>
{% else %}
    <!-- Header padrão verde -->
    <div class="header">
        <!-- Conteúdo padrão Estruturas do Vale -->
    </div>
{% endif %}
```

## Resultado Esperado
✅ PDFs gerados mostrarão o header personalizado cadastrado  
✅ Não haverá mais sobreposição de headers  
✅ Sistema funcionará automaticamente após deploy  

## Status
🚀 **PRONTO PARA DEPLOY**  
Todas as correções implementadas e testadas localmente.