# Checklist de Deploy - Migração 48 (Easypanel)

**Data:** 30 de Outubro de 2025  
**Severidade:** 🔴 **CRÍTICA** - Sistema em produção está quebrado sem esta migração  
**Tempo Total Estimado:** 15-30 minutos

---

## ⚠️ CONTEXTO

**Problema:** Erro `column funcao.admin_id does not exist` em produção.

**Solução:** A Migração 48 adiciona a coluna `admin_id` em 20 tabelas para completar o isolamento multi-tenant.

**Tabelas Afetadas:** 20 tabelas incluindo `departamento`, `funcao`, `horario_trabalho`, `servico_obra`, `rdo_mao_obra`, `proposta_itens`, e outras.

---

## 1️⃣ PRÉ-DEPLOY (⏱️ 5-10 minutos)

### Validações Obrigatórias

- [ ] **Backup do banco de dados criado**
  ```bash
  # Via Easypanel Console/Shell
  pg_dump $DATABASE_URL > backup_pre_migracao_48_$(date +%Y%m%d_%H%M%S).sql
  ```
  > **⚠️ WARNING:** Não prossiga sem backup. Guarde o nome do arquivo gerado.

- [ ] **Executar script de pré-validação**
  ```bash
  python3 pre_migration_48_check.py
  ```
  **Resultado esperado:**
  - ✅ Conexão com banco OK
  - 📊 Lista de admins cadastrados (mínimo 1)
  - 📋 Status das 20 tabelas
  - ⚠️ Se aparecer "órfãos detectados", anote as tabelas

- [ ] **Revisar output do script de validação**
  - Quantas tabelas JÁ têm `admin_id`? (anote: ___/20)
  - Quantos admins ativos? (anote: ___)
  - Há registros órfãos? (sim/não: ___)

### Opcional (Se houver janela de manutenção)

- [ ] **Agendar janela de manutenção** (sugestão: 30 minutos)
- [ ] **Notificar usuários** (email/sistema interno)
  - Exemplo: "Sistema em manutenção por 30 min às [HORÁRIO]"

---

## 2️⃣ DEPLOY (⏱️ 5-10 minutos)

### Execução da Migração

> **💡 DICA:** A Migração 48 executa AUTOMATICAMENTE no startup da aplicação. Você só precisa fazer o deploy.

- [ ] **Acessar Easypanel Dashboard**
  - URL: `https://[seu-easypanel]/`
  - Navegar até o projeto SIGE

- [ ] **Fazer deploy da aplicação**
  ```bash
  # Opção A: Via Easypanel UI
  # Clicar em "Rebuild" ou "Redeploy" no painel da aplicação
  
  # Opção B: Via Git (se configurado)
  git push origin main
  # Aguardar rebuild automático no Easypanel
  ```

- [ ] **Monitorar logs de inicialização**
  - No Easypanel, acessar "Logs" em tempo real
  - Buscar por: `MIGRAÇÃO 48`
  
  **Logs esperados de sucesso:**
  ```
  INFO:migrations:🔄 MIGRAÇÃO 48: Multi-tenancy completo com backfill
  INFO:migrations:  ✅ departamento: XX registros atualizados
  INFO:migrations:  ✅ funcao: XX registros atualizados
  INFO:migrations:  ✅ horario_trabalho: XX registros atualizados
  ...
  INFO:migrations:✅ MIGRAÇÃO 48 CONCLUÍDA!
  ```

- [ ] **Verificar que NÃO há erros SQL nos logs**
  - ❌ Se aparecer `ERRO:` ou `ERROR:`, **PARE** e vá para seção ROLLBACK
  - ❌ Se aparecer `órfãos detectados`, veja Troubleshooting abaixo

- [ ] **Aguardar aplicação ficar "Running" no Easypanel**
  - Status deve mudar de "Starting" → "Running"
  - Tempo estimado: 30-60 segundos

---

## 3️⃣ PÓS-DEPLOY (⏱️ 5-10 minutos)

### Validações de Sucesso

- [ ] **Executar script de validação novamente**
  ```bash
  python3 pre_migration_48_check.py
  ```
  **Resultado esperado:**
  - ✅ **20/20 tabelas** com coluna `admin_id`
  - ✅ **0 registros órfãos**
  - ✅ Status: "Sistema OK para produção"

- [ ] **Acessar dashboard de diagnóstico** (opcional)
  - URL: `https://[seu-dominio]/admin/database-diagnostics`
  - Verificar: Status das tabelas = 100%

### Testes Funcionais Críticos

- [ ] **Testar Listagem de Funcionários**
  - Acessar: `https://[seu-dominio]/funcionarios`
  - ✅ Página carrega sem erro
  - ✅ NÃO aparece erro `column funcao.admin_id does not exist`
  - ✅ Lista de funcionários exibida corretamente

- [ ] **Testar Detalhes de Obra**
  - Acessar: `https://[seu-dominio]/detalhes_obra/[ID-QUALQUER]`
  - ✅ Página carrega normalmente
  - ✅ Dados da obra aparecem

- [ ] **Testar RDO Consolidado**
  - Acessar: `https://[seu-dominio]/funcionario/rdo/consolidado`
  - ✅ Página carrega
  - ✅ Listagem de RDOs funciona

- [ ] **Verificar visualmente**
  - ✅ Sem mensagens de erro vermelhas nas telas
  - ✅ Dados carregam normalmente
  - ✅ Filtros e buscas funcionam

### Validação de Integridade (Opcional, mas recomendado)

- [ ] **Conectar ao banco e executar**
  ```sql
  -- Verificar que todas as 20 tabelas têm admin_id
  SELECT 
      table_name,
      column_name
  FROM information_schema.columns
  WHERE column_name = 'admin_id'
    AND table_name IN (
      'departamento', 'funcao', 'horario_trabalho',
      'servico_obra', 'historico_produtividade_servico',
      'tipo_ocorrencia', 'ocorrencia', 'calendario_util',
      'centro_custo', 'receita', 'orcamento_obra',
      'fluxo_caixa', 'registro_alimentacao',
      'rdo_mao_obra', 'rdo_equipamento', 'rdo_ocorrencia', 'rdo_foto',
      'notificacao_cliente', 'proposta_itens', 'proposta_arquivos'
    )
  ORDER BY table_name;
  
  -- Deve retornar 20 linhas
  ```

- [ ] **Verificar que NÃO há registros órfãos**
  ```sql
  -- Exemplo para tabela funcao
  SELECT COUNT(*) as orfaos 
  FROM funcao 
  WHERE admin_id IS NULL;
  
  -- Deve retornar: 0
  ```

---

## 4️⃣ ROLLBACK (🚨 Apenas se algo der MUITO errado)

> **⚠️ ATENÇÃO:** Só execute rollback se o sistema estiver completamente quebrado.

### Quando fazer rollback?

- ❌ Migração falhou e aplicação não inicia
- ❌ Erro SQL crítico nos logs
- ❌ Funcionalidades críticas do sistema quebradas
- ❌ Perda de dados detectada

### Procedimento de Rollback

- [ ] **Parar aplicação no Easypanel**
  - Via UI: Clicar em "Stop" ou "Pause"

- [ ] **Restaurar backup do banco**
  ```bash
  # Conectar via Console/Shell do Easypanel
  psql $DATABASE_URL < backup_pre_migracao_48_YYYYMMDD_HHMMSS.sql
  ```
  > Substitua `YYYYMMDD_HHMMSS` pelo nome real do arquivo de backup

- [ ] **OU usar script automático de rollback**
  ```bash
  python3 rollback_migration_48.py --force
  ```
  > **⚠️ WARNING:** Isso remove a coluna `admin_id` de todas as 20 tabelas

- [ ] **Reverter código (se necessário)**
  ```bash
  # Fazer rollback do código para commit anterior
  git revert [COMMIT-HASH-DA-MIGRACAO-48]
  git push origin main
  ```

- [ ] **Reiniciar aplicação no Easypanel**
  - Via UI: Clicar em "Start" ou "Redeploy"

- [ ] **Validar que sistema voltou a funcionar**
  - Acessar páginas críticas
  - Confirmar que erro original voltou (esperado)

---

## 🛠️ TROUBLESHOOTING

### Problema: "Órfãos detectados" nos logs

**Sintoma:**
```
🔴 departamento: 5 registros órfãos encontrados
MIGRAÇÃO ABORTADA
```

**Solução:**
1. Identificar registros órfãos:
   ```sql
   SELECT * FROM departamento d
   WHERE NOT EXISTS (
       SELECT 1 FROM funcionario f WHERE f.departamento_id = d.id
   );
   ```

2. Corrigir manualmente:
   - **Opção A:** Deletar registros não utilizados
   - **Opção B:** Associar a um admin válido

3. Re-executar deploy (migração é idempotente)

### Problema: "column admin_id already exists"

**Sintoma:**
```
ERROR: column "admin_id" already exists
```

**Solução:**
Migração já foi executada antes. Verifique:
```sql
SELECT migration_number, status, executed_at 
FROM migration_history 
WHERE migration_number = 48;
```

Se status = 'success', tudo OK. Se status = 'failed', pode re-executar deploy.

### Problema: Aplicação não inicia após deploy

**Sintoma:**
Logs mostram erros Python/SQL e aplicação fica "Restarting" no Easypanel.

**Solução:**
1. Verificar logs completos no Easypanel
2. Procurar linha com `ERROR:` ou `CRITICAL:`
3. Se erro relacionado a `admin_id`, seguir procedimento de ROLLBACK
4. Caso contrário, reportar erro específico

---

## 📞 CONTATOS DE EMERGÊNCIA

**Suporte Técnico:**
- [Adicionar contato do time de desenvolvimento]
- [Adicionar contato do DBA/Admin de sistemas]

**Localização de Backups:**
- Backup manual: `backup_pre_migracao_48_*.sql` (mesmo diretório de execução)
- Backups automáticos Easypanel: [Configurar conforme ambiente]

**Logs de Erro:**
- Aplicação: Via Easypanel → Logs
- Diagnóstico: `/tmp/db_diagnostics.log` (no container)
- Validação: Output de `pre_migration_48_check.py`

---

## ✅ CHECKLIST FINAL

Antes de considerar deploy concluído:

- [ ] ✅ Migração executada com sucesso (logs confirmam)
- [ ] ✅ 20/20 tabelas com coluna `admin_id`
- [ ] ✅ 0 registros órfãos
- [ ] ✅ Erro `column funcao.admin_id does not exist` desapareceu
- [ ] ✅ Página `/funcionarios` funciona
- [ ] ✅ Testes funcionais críticos passaram
- [ ] ✅ Sistema estável por pelo menos 5 minutos
- [ ] ✅ Backup guardado em local seguro

**Recomendação:** Monitore o sistema por 24h após deploy para garantir estabilidade.

---

## 📊 INFORMAÇÕES TÉCNICAS

**Migração 48 - Características:**
- ✅ **Idempotente:** Pode executar múltiplas vezes sem problemas
- ✅ **Transacional:** Falha completa ou sucesso completo (rollback automático em erro)
- ✅ **Tenant-aware:** Preserva isolamento de dados entre admins
- ✅ **Auto-validada:** Detecta problemas antes de commit
- ⏱️ **Tempo de execução:** 30s - 2min (dependendo do volume de dados)

**Tabelas Afetadas (20):**
```
departamento, funcao, horario_trabalho, servico_obra,
historico_produtividade_servico, tipo_ocorrencia, ocorrencia,
calendario_util, centro_custo, receita, orcamento_obra,
fluxo_caixa, registro_alimentacao, rdo_mao_obra, rdo_equipamento,
rdo_ocorrencia, rdo_foto, notificacao_cliente, proposta_itens,
proposta_arquivos
```

---

**Versão:** 1.0  
**Última Atualização:** 30 de Outubro de 2025  
**Mantenedor:** Equipe SIGE
