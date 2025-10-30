# 🚨 CORREÇÃO URGENTE: horario_trabalho.admin_id

## Problema

A tabela `horario_trabalho` **NÃO TEM** a coluna `admin_id` na produção, causando erro:

```
column horario_trabalho.admin_id does not exist
```

## Solução: Executar Script via SSH

### Passo 1: Conectar no Container

```bash
# No Easypanel, abrir terminal SSH do container da aplicação
```

### Passo 2: Escolher UMA das opções abaixo

---

## ✅ OPÇÃO 1: Script Python (RECOMENDADO)

**Executar:**
```bash
python3 fix_horario_trabalho_PRODUCAO.py
```

**Output esperado:**
```
================================================================================
🔧 CORREÇÃO PRODUÇÃO: horario_trabalho.admin_id
================================================================================

📊 Database: ep-misty-fire-aee2t322.c-2.us-east-2.aws.neon.tech/neondb

🔌 Conectando ao banco...
   ✅ Conectado

🔍 Verificando se admin_id já existe...
   ⚠️  Coluna admin_id NÃO EXISTE - vamos criar!

📝 PASSO 1: Adicionando coluna admin_id...
   ✅ Coluna adicionada

🔄 PASSO 2: Preenchendo admin_id via funcionario...
   ✅ 2 registros preenchidos via relacionamento

🔧 PASSO 3: Preenchendo registros órfãos com admin_id = 2...
   ✅ 0 registros órfãos corrigidos

🔒 PASSO 4: Aplicando constraint NOT NULL...
   ✅ Constraint aplicada

🔗 PASSO 5: Criando foreign key...
   ✅ Foreign key criada

⚡ PASSO 6: Criando índice...
   ✅ Índice criado

💾 Salvando alterações...
   ✅ COMMIT realizado

🔍 Validando resultado...
   📊 Total de registros: 2
   ✅ Com admin_id: 2
   👥 Admins distintos: 1

📋 Registros:
   ID 1: Seg a Sex  (admin_id=2)
   ID 2: Estagiario (admin_id=2)

================================================================================
✅ CORREÇÃO CONCLUÍDA COM SUCESSO!
================================================================================

🔄 Próximo passo: Reiniciar a aplicação
   supervisorctl restart all
```

---

## ✅ OPÇÃO 2: Script SQL

**Executar:**
```bash
psql $DATABASE_URL -f fix_horario_trabalho_PRODUCAO.sql
```

**Output esperado:**
```
🔧 Iniciando correção de horario_trabalho...

📝 PASSO 1: Adicionando coluna admin_id...
   ✅ Coluna adicionada

🔄 PASSO 2: Preenchendo admin_id via funcionario...
   ✅ Backfill concluído

🔧 PASSO 3: Preenchendo órfãos com admin_id = 2...
   ✅ Órfãos corrigidos

🔒 PASSO 4: Aplicando NOT NULL...
   ✅ Constraint aplicada

🔗 PASSO 5: Criando foreign key...
   ✅ Foreign key criada

⚡ PASSO 6: Criando índice...
   ✅ Índice criado

✅ CORREÇÃO CONCLUÍDA COM SUCESSO!

      tabela       | total | com_admin_id | admins
-------------------+-------+--------------+--------
 horario_trabalho  |     2 |            2 |      1

 id |     nome      | admin_id
----+---------------+----------
  1 | Seg a Sex     |        2
  2 | Estagiario    |        2
```

---

## Passo 3: Reiniciar Aplicação

```bash
supervisorctl restart all
```

Ou simplesmente aguardar o próximo deploy automático.

---

## ✅ Validação

Após executar, testar:

1. **Página de Funcionários** - `/funcionarios`
   - Deve carregar sem erro
   - Horários devem aparecer corretamente

2. **Página de Configurações** - `/configuracoes/horarios`
   - Deve listar os 2 horários
   - Deve permitir criar novos horários

---

## 🔧 Troubleshooting

### Erro: "psycopg2 not found"

Use a opção SQL:
```bash
psql $DATABASE_URL -f fix_horario_trabalho_PRODUCAO.sql
```

### Erro: "permission denied"

Execute como root ou com sudo:
```bash
sudo python3 fix_horario_trabalho_PRODUCAO.py
```

### Script já foi executado

Se o script rodar novamente, ele vai detectar e pular:
```
⏭️  admin_id já existe - nada a fazer
```

---

## 📊 Resumo

| Item | Antes | Depois |
|------|-------|--------|
| Coluna `admin_id` | ❌ Não existe | ✅ Existe |
| Registros com admin_id | 0/2 | 2/2 |
| Constraint NOT NULL | ❌ | ✅ |
| Foreign Key | ❌ | ✅ |
| Índice | ❌ | ✅ |
| Página funcionando | ❌ | ✅ |

---

## ⚡ Execução Rápida (Copy/Paste)

```bash
# Conectar no container via SSH, depois executar:
python3 fix_horario_trabalho_PRODUCAO.py && supervisorctl restart all
```

**Pronto!** 🎉
