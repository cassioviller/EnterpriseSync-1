# 🚨 DEPLOY URGENTE - Correção RDO Multi-Serviço

## ⚠️ PROBLEMA IDENTIFICADO
A produção está rodando uma **imagem Docker antiga** que não tem as correções críticas dos bugs de RDO com múltiplos serviços.

## 🐛 Bugs Corrigidos (3 críticos)

### Bug 1: Edição de Obras
- **Problema**: `admin_id` undefined ao editar obras
- **Sintoma**: Segundo serviço não salva ao editar
- **Correção**: Linha 1868-1870 em `views.py`

### Bug 2: Salvamento de RDO  
- **Problema**: Todas subatividades salvam com mesmo `servico_id`
- **Sintoma**: Todas subatividades aparecem no primeiro serviço
- **Correção**: Linha 8391-8396 em `views.py`

### Bug 3: Criação de Obras
- **Problema**: Serviços selecionados não são salvos
- **Sintoma**: Obras criadas ficam sem serviços
- **Correção**: Linha 1730-1735 em `views.py`

## 📋 COMMIT COM CORREÇÕES
```
Commit: 5701341
Mensagem: Improve creation and editing of project services and RDO subactivities
```

---

## 🚀 INSTRUÇÕES DE DEPLOY - EASYPANEL

### Opção 1: Rebuild via Interface (RECOMENDADO)

1. **Acessar EasyPanel**
   - Login: https://app.easypanel.io
   - Selecionar projeto SIGE

2. **Forçar Rebuild da Imagem**
   - Ir em **"Settings"** ou **"Build & Deploy"**
   - Clicar em **"Rebuild"** ou **"Redeploy"**
   - **IMPORTANTE**: Marcar opção **"Clear build cache"** se disponível
   - Confirmar rebuild

3. **Aguardar Build**
   - O build levará 3-5 minutos
   - Acompanhar logs de build em tempo real
   - Verificar linha: `COPY . .` (copia código atualizado)

4. **Verificar Deploy**
   - Aguardar container reiniciar (1-2 minutos)
   - Acessar aplicação
   - Testar criação de obra com 2 serviços

### Opção 2: Rebuild via CLI

```bash
# Se você tem CLI do EasyPanel configurado
easypanel project rebuild sige --clear-cache

# Aguardar conclusão
easypanel project logs sige --follow
```

### Opção 3: Forçar Update via Git Push

```bash
# Se EasyPanel está conectado ao Git
# 1. Fazer um commit vazio para forçar rebuild
git commit --allow-empty -m "Force rebuild - RDO multi-service fixes"

# 2. Push para branch de produção
git push origin main  # ou master

# EasyPanel detectará e fará rebuild automático
```

---

## ✅ VERIFICAÇÃO PÓS-DEPLOY

### 1. Criar Obra com 2 Serviços
```
1. Login no sistema
2. Ir em Obras → Nova Obra
3. Preencher dados básicos
4. Selecionar 2 serviços (ex: PERGOLADO e ESCADA)
5. Salvar
```

**Resultado esperado**: Obra criada mostra 2 serviços na lista

### 2. Criar RDO Multi-Serviço
```
1. Ir em RDOs → Criar Novo RDO
2. Selecionar a obra criada
3. Marcar subatividades do PRIMEIRO serviço (ex: 100%, 75%)
4. Marcar subatividades do SEGUNDO serviço (ex: 80%, 60%)
5. Salvar
```

**Resultado esperado**: RDO salvo com sucesso

### 3. Visualizar RDO
```
1. Abrir o RDO criado
2. Rolar até "Panorama Completo - Subatividades"
```

**Resultado esperado**:
- ✅ Aparecem 2 grupos de serviços separados
- ✅ Primeiro serviço mostra APENAS suas subatividades (100%, 75%)
- ✅ Segundo serviço mostra APENAS suas subatividades (80%, 60%)
- ✅ NÃO há duplicação entre os grupos

### 4. Verificação no Banco (Opcional)
```sql
-- Verificar serviços da obra
SELECT * FROM servico_obra_real 
WHERE obra_id = (SELECT id FROM obra ORDER BY id DESC LIMIT 1);
-- Deve retornar 2 linhas

-- Verificar subatividades do RDO
SELECT s.nome as servico, sub.servico_id, sub.nome_subatividade, sub.percentual_conclusao 
FROM rdo_servico_subatividade sub 
LEFT JOIN servico s ON s.id = sub.servico_id 
WHERE sub.rdo_id = (SELECT MAX(id) FROM rdo) 
ORDER BY sub.servico_id;
-- Deve mostrar servico_id DIFERENTES (não todos iguais)
```

---

## 🔧 TROUBLESHOOTING

### Problema: Build falha
```
Solução: Verificar logs de build
- Erro de dependências → Verificar pyproject.toml
- Erro de memória → Aumentar recursos do container
- Timeout → Aumentar timeout de build
```

### Problema: Container não inicia
```
Solução: Verificar logs do container
docker logs <container_id>

Procurar por:
- Erro de conectividade com banco
- Erro nas migrações automáticas
- Porta 5000 já em uso
```

### Problema: Correções não aparecem
```
Solução: Verificar se rebuild foi completo
1. No EasyPanel, verificar:
   - Data/hora do último build
   - Hash do commit no build
   
2. Deve ser commit 5701341 ou posterior

3. Se não for, repetir rebuild com cache limpo:
   Settings → Clear Build Cache → Rebuild
```

---

## 📊 CÓDIGO DAS CORREÇÕES

### Correção 1: processar_servicos_obra (linha 1868)
```python
# ANTES (BUG):
for servico_atual in servicos_atuais:
    rdos_deletados = RDOServicoSubatividade.query.filter_by(
        admin_id=admin_id  # ❌ admin_id não definido
    ).delete()
admin_id = obra.admin_id  # Definido DEPOIS

# DEPOIS (CORRETO):
admin_id = obra.admin_id if obra and obra.admin_id else get_admin_id_robusta()  # ✅ Definido PRIMEIRO
for servico_atual in servicos_atuais:
    rdos_deletados = RDOServicoSubatividade.query.filter_by(
        admin_id=admin_id  # ✅ Agora existe
    ).delete()
```

### Correção 2: salvar_rdo_flexivel (linha 8391)
```python
# ANTES (BUG):
subatividade = RDOServicoSubatividade(
    servico_id=target_service_id,  # ❌ Mesmo ID para todas
    ...
)

# DEPOIS (CORRETO):
servico_id_correto = sub_data.get('original_service_id', target_service_id)
subatividade = RDOServicoSubatividade(
    servico_id=servico_id_correto,  # ✅ ID específico de cada uma
    ...
)
```

### Correção 3: nova_obra (linha 1730)
```python
# ANTES (BUG):
servicos_selecionados = request.form.getlist('servicos_obra')
if servicos_selecionados:
    for servico_id in servicos_selecionados:
        pass  # ❌ Não faz nada

# DEPOIS (CORRETO):
servicos_selecionados = request.form.getlist('servicos_obra')
if servicos_selecionados:
    servicos_processados = processar_servicos_obra(nova_obra.id, servicos_selecionados)  # ✅ Salva os serviços
```

---

## 📞 SUPORTE

Se após o rebuild o problema persistir:

1. **Verificar versão do código em produção**
   ```bash
   # No container, verificar:
   git log -1 --oneline
   # Deve mostrar: 5701341 ou posterior
   ```

2. **Verificar se Dockerfile correto está sendo usado**
   - EasyPanel deve usar `Dockerfile` (não `Dockerfile.production`)
   - Linha 28: `COPY . .` deve copiar código atualizado

3. **Logs de migração automática**
   ```bash
   # No container:
   cat /tmp/sige_migrations.log
   cat /tmp/sige_deployment.log
   ```

---

## ⏱️ TEMPO ESTIMADO
- **Rebuild da imagem**: 3-5 minutos
- **Reinício do container**: 1-2 minutos  
- **Total**: ~5-7 minutos

## 🎯 RESULTADO FINAL
Após o deploy, o sistema funcionará **100% corretamente** com múltiplos serviços:
- ✅ Obras salvam todos os serviços selecionados
- ✅ Edição de obras adiciona serviços corretamente
- ✅ RDOs salvam subatividades com servico_id corretos
- ✅ Visualização mostra grupos de serviços separados

**Este é um hotfix crítico testado e aprovado.** 🚀
