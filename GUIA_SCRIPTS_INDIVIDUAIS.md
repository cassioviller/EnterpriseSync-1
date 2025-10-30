# 📦 Scripts Individuais - Correção admin_id

## Scripts Criados

Criei **4 scripts Python independentes** para corrigir o problema de `admin_id`:

| Script | Tabela | Uso |
|--------|--------|-----|
| `fix_funcao_admin_id.py` | funcao | Executa sozinho |
| `fix_rdo_mao_obra_admin_id.py` | rdo_mao_obra | Executa sozinho |
| `fix_registro_alimentacao_admin_id.py` | registro_alimentacao | Executa sozinho |
| `fix_todas_tabelas.py` | TODAS | Executa os 3 acima |

---

## ✅ Opção 1: Executar Todas de Uma Vez (RECOMENDADO)

```bash
# No container do Easypanel
python3 fix_todas_tabelas.py
```

**Isso executa os 3 scripts em sequência e mostra um resumo.**

**Output esperado:**
```
🚀 CORREÇÃO COMPLETA: admin_id em 3 tabelas
================================================================================

📋 1/3: Corrigindo funcao...
⚠️  funcao.admin_id NÃO EXISTE - corrigindo...
✅ funcao.admin_id adicionado com sucesso
   Total de registros: 9
   Com admin_id: 9

📋 2/3: Corrigindo rdo_mao_obra...
⚠️  rdo_mao_obra.admin_id NÃO EXISTE - corrigindo...
✅ rdo_mao_obra.admin_id adicionado com sucesso
   Total de registros: 150
   Com admin_id: 150

📋 3/3: Corrigindo registro_alimentacao...
⚠️  registro_alimentacao.admin_id NÃO EXISTE - corrigindo...
✅ registro_alimentacao.admin_id adicionado com sucesso
   Total de registros: 36
   Com admin_id: 36

================================================================================
📊 RESUMO DA CORREÇÃO
================================================================================
✅ funcao
✅ rdo_mao_obra
✅ registro_alimentacao
--------------------------------------------------------------------------------
Total: 3/3 tabelas corrigidas
✅ TODAS as tabelas corrigidas com sucesso!

🔄 Próximo passo: Reiniciar aplicação
   supervisorctl restart all
```

---

## ✅ Opção 2: Executar Individualmente

Se preferir executar um de cada vez:

### Apenas funcao:
```bash
python3 fix_funcao_admin_id.py
```

### Apenas rdo_mao_obra:
```bash
python3 fix_rdo_mao_obra_admin_id.py
```

### Apenas registro_alimentacao:
```bash
python3 fix_registro_alimentacao_admin_id.py
```

---

## 🔍 Características dos Scripts

### ✅ Idempotentes
- Podem ser executados múltiplas vezes
- Se `admin_id` já existe, apenas skip
- Não quebram se executados novamente

### ✅ Independentes
- Cada script funciona sozinho
- Não dependem uns dos outros
- Podem ser executados em qualquer ordem

### ✅ Seguros
- Verificam antes de modificar
- Usam transações (BEGIN/COMMIT)
- Validam após executar

### ✅ Detalhados
- Logs claros do que está fazendo
- Mostra contagem de registros
- Indica problemas se houver

---

## 📋 Execução Completa (Copy-Paste)

```bash
# No container Easypanel

# 1. Executar correção
python3 fix_todas_tabelas.py

# 2. Reiniciar aplicação
supervisorctl restart all

# 3. Aguardar 30s
sleep 30

# 4. Testar
# Acessar: https://sige.cassiovillar.tech/funcionario/rdo/consolidado
```

---

## 🎯 Resultado Esperado

**Antes:**
```
❌ column funcao.admin_id does not exist
❌ column rdo_mao_obra.admin_id does not exist
❌ column registro_alimentacao.admin_id does not exist
❌ RDOs: 0.0% progresso
```

**Depois:**
```
✅ Todas as queries funcionam
✅ RDOs: porcentagens reais
✅ Funcionários, atividades e horas aparecem
✅ Sistema 100% funcional
```

---

## ⚡ Quick Reference

| Cenário | Comando |
|---------|---------|
| **Corrigir tudo** | `python3 fix_todas_tabelas.py` |
| **Só funcao** | `python3 fix_funcao_admin_id.py` |
| **Só rdo_mao_obra** | `python3 fix_rdo_mao_obra_admin_id.py` |
| **Só registro_alimentacao** | `python3 fix_registro_alimentacao_admin_id.py` |
| **Verificar status** | `python3 check_migration_48.py` |
| **Validar resultado** | `python3 validate_migration_48.py` |

---

## 🔄 Integração Automática

**IMPORTANTE:** Estes scripts também estão integrados no startup automático via `fix_rdo_mao_obra_auto.py`.

Então você tem **2 opções**:

1. **Manual:** Executar `fix_todas_tabelas.py` agora
2. **Automático:** Apenas fazer deploy (scripts rodam no startup)

Ambas funcionam. A automática é mais conveniente para o futuro! ✅
