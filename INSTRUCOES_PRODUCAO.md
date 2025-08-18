# Instruções para Corrigir Erro de Coluna no Banco de Produção

## Problema
O erro está acontecendo porque a coluna `categoria` não existe na tabela `proposta_templates` do banco de dados de produção.

## Solução
Execute o script SQL abaixo no banco de dados de produção:

### Opção 1: Script Completo (Recomendado)
Execute o arquivo `migration_production.sql` que foi criado neste projeto.

### Opção 2: Comando Manual
Se preferir executar manualmente, rode este comando no banco de produção:

```sql
-- Adicionar a coluna categoria que está faltando
ALTER TABLE proposta_templates 
ADD COLUMN categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica';

-- Verificar se foi criada corretamente
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'proposta_templates' 
AND column_name = 'categoria';
```

## Como Executar

1. **Acesse o painel de administração do banco de dados de produção**
2. **Execute o script SQL** (migration_production.sql ou comando manual)
3. **Verifique se a coluna foi criada** com sucesso
4. **Teste o sistema** acessando a seção de templates

## Verificação
Após executar o script, a tabela `proposta_templates` deve ter a coluna `categoria`. Você pode verificar com:

```sql
\d proposta_templates
```

Ou:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'proposta_templates' 
ORDER BY ordinal_position;
```

## Importante
- Este script é seguro e não afeta dados existentes
- A coluna será criada com um valor padrão
- Execute apenas uma vez no banco de produção
- Faça backup do banco antes da execução (recomendado)