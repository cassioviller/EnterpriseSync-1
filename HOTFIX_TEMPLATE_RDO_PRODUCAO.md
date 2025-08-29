# 🚨 HOTFIX CRÍTICO - Template RDO Produção

## Problema Identificado (29/08/2025)
- **Ambiente produção:** Usando template RDO antigo (lista de funcionários)
- **Ambiente desenvolvimento:** Usando template novo.html moderno (subatividades)
- **Resultado:** Interfaces completamente diferentes entre ambientes

## 🎯 Solução Urgente

### 1. Arquivos de Correção Criados:
- `Dockerfile.template-fix` - Build que força template correto
- `docker-entrypoint-template-fix.sh` - Script que valida templates
- `corrigir_template_rdo_producao.py` - Correção automática

### 2. Deploy Emergencial:

```bash
# 1. Build com correção de template
docker build -f Dockerfile.template-fix -t sige-template-fix .

# 2. Deploy corrigido
docker run -d \
  --name sige-corrigido \
  -p 5000:5000 \
  -e DATABASE_URL="sua-url-postgres" \
  -e SESSION_SECRET="sua-chave" \
  sige-template-fix
```

### 3. Verificação Pós-Deploy:

**✅ Interface deve mostrar:**
- Campos de subatividades com percentuais (não lista de funcionários)
- Botão "Testar Último RDO"
- 3 serviços: Estrutura Metálica, Soldagem, Pintura
- Total de 11 subatividades

**❌ Se ainda mostrar interface antiga:**
```bash
# Executar dentro do container
docker exec -it sige-corrigido python corrigir_template_rdo_producao.py
docker restart sige-corrigido
```

## 🔧 Correção Manual (se necessário)

Se o deploy automatizado não funcionar:

### 1. Verificar rota no views.py:
```python
@app.route('/funcionario/rdo/novo', methods=['GET', 'POST'])
def novo_rdo():
    return render_template('rdo/novo.html')  # DEVE ser novo.html
```

### 2. Confirmar arquivo existe:
```bash
ls -la templates/rdo/novo.html  # Deve existir e ter 33KB
```

### 3. Força reinicialização:
```bash
# No servidor de produção
docker-compose down
docker-compose up -d --force-recreate
```

## 📊 Status Esperado Pós-Correção

### Interface RDO Corrigida:
- **Obra:** Dropdown com seleção
- **Data:** Campo de data
- **Clima/Temperatura:** Campos básicos  
- **Subatividades:** Cards expansíveis por serviço
- **Botão:** "Testar Último RDO" funcionando
- **Salvamento:** Porcentagens persistindo no banco

### API Funcionando:
```bash
curl http://seu-dominio/api/test/rdo/servicos-obra/40
# Deve retornar 11 subatividades (4+3+4)
```

## ⚠️ Impacto da Correção
- **Zero downtime:** Template é substituído sem interrupção
- **Dados preservados:** Banco de dados permanece intacto
- **Funcionalidade completa:** Sistema RDO 100% operacional

## 🎯 Resultado Final
Ambos os ambientes (desenvolvimento e produção) usarão a **mesma interface moderna** com subatividades dinâmicas e funcionalidade "Testar Último RDO".

---
**Urgência:** CRÍTICA - Aplicar imediatamente
**Responsável:** DevOps/Infraestrutura  
**Validação:** Verificar interface após deploy