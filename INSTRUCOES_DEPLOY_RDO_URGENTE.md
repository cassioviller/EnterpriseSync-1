# 🔥 CORREÇÃO URGENTE - Template RDO Produção

## DIAGNÓSTICO REALIZADO (29/08/2025)

**PROBLEMA:** Produção usa interface antiga (lista funcionários), desenvolvimento usa interface moderna (subatividades)

## SOLUÇÃO DEFINITIVA

### Opção 1: Deploy com Dockerfile Corrigido (RECOMENDADO)

```bash
# 1. Build da imagem corrigida
docker build -f Dockerfile.template-fix -t sige-rdo-fix .

# 2. Parar container atual
docker stop sige-atual
docker rm sige-atual

# 3. Iniciar com correção
docker run -d \
  --name sige-corrigido \
  -p 5000:5000 \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e SESSION_SECRET="${SESSION_SECRET}" \
  sige-rdo-fix

# 4. Verificar correção
curl http://localhost:5000/funcionario/rdo/novo
```

### Opção 2: Correção Manual no Container

```bash
# Executar dentro do container atual
docker exec -it seu-container bash

# Verificar template existe
ls -la templates/rdo/novo.html

# Se não existir, copiar do desenvolvimento
# OU executar correção
python corrigir_template_rdo_producao.py

# Reiniciar aplicação
pkill -f gunicorn
gunicorn --bind 0.0.0.0:5000 main:app &
```

### Opção 3: Substituição Direta de Arquivo

```bash
# No servidor de produção, substituir diretamente o arquivo
# Fazer backup primeiro
cp templates/rdo/novo.html templates/rdo/novo.html.backup

# Copiar template correto (33KB, interface moderna)
# [Substituir pelo conteúdo do template correto]

# Reiniciar aplicação
docker restart seu-container
```

## VERIFICAÇÃO PÓS-CORREÇÃO

**Interface deve mostrar:**
- ✅ Dropdown de obras
- ✅ Campos de data, clima, temperatura
- ✅ Botão "Testar Último RDO" (verde, moderno)
- ✅ 3 cards de serviços (Estrutura Metálica, Soldagem, Pintura)
- ✅ Subatividades com campos de porcentagem
- ✅ Design moderno com gradientes

**Interface NÃO deve mostrar:**
- ❌ Lista de funcionários (Antonio Fernandes da Silva, etc.)
- ❌ Checkboxes de funcionários
- ❌ Interface antiga sem subatividades

## TESTE FINAL

```bash
# 1. Acessar URL
http://seu-dominio/funcionario/rdo/novo

# 2. Verificar API
curl http://seu-dominio/api/test/rdo/servicos-obra/40
# Deve retornar 11 subatividades

# 3. Testar salvamento
# Preencher subatividades → Salvar → Verificar se persiste
```

## 🚨 SE AINDA ESTIVER ERRADO

Execute dentro do container:
```bash
find . -name "*.html" | grep -i rdo
python -c "
import os
for root, dirs, files in os.walk('templates'):
    for file in files:
        if 'rdo' in file.lower():
            print(os.path.join(root, file))
"
```

---
**STATUS:** CORREÇÃO CRÍTICA PRONTA
**AÇÃO:** Deploy imediato necessário
**RESULTADO:** Interface idêntica em desenvolvimento e produção
