# 🚀 INSTRUÇÕES DE DEPLOY SIGE v10.0

## ⚠️ PROBLEMA DE DEPLOY IDENTIFICADO

O deploy travou (amarelo) porque o `docker-entrypoint-v10.sh` estava muito complexo. 

## ✅ SOLUÇÃO APLICADA

### 1. ENTRYPOINT SIMPLIFICADO
Criado `docker-entrypoint-production-simple.sh` que:
- ✅ Configurações básicas apenas
- ✅ Aguarda banco 10 segundos
- ✅ Correções RDO essenciais
- ✅ Sem validações complexas que podem travar

### 2. DOCKERFILE OTIMIZADO  
Criado `Dockerfile.production` que:
- ✅ Base Python 3.11-slim
- ✅ Dependências mínimas
- ✅ 2 workers Gunicorn
- ✅ Timeout 120s

## 🔧 COMO CORRIGIR O DEPLOY

### Opção 1: Usar Entrypoint Simples
1. **Renomear arquivos:**
   ```bash
   mv docker-entrypoint-v10.sh docker-entrypoint-v10-complex.sh.bak
   mv docker-entrypoint-production-simple.sh docker-entrypoint.sh
   ```

2. **Atualizar Dockerfile:**
   ```dockerfile
   COPY docker-entrypoint.sh /usr/local/bin/
   ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
   ```

### Opção 2: Usar Dockerfile Otimizado
1. **Renomear Dockerfile:**
   ```bash
   mv Dockerfile Dockerfile.complex.bak
   mv Dockerfile.production Dockerfile
   ```

### Opção 3: Deploy Manual das Correções
Se o sistema subir mas com problemas no RDO, execute:
```bash
python3 deploy_rdo_completo_v10.py
```

## 🎯 CORREÇÕES QUE SERÃO APLICADAS

- ✅ **Limpeza:** Remove "Etapa Inicial" e "Etapa Intermediária" duplicadas
- ✅ **Nomes:** Corrige "Subatividade 440" → "Preparação da Estrutura"
- ✅ **Admin ID:** Corrige RDOs órfãos com admin_id=10
- ✅ **Integridade:** Remove subatividades inválidas dos RDOs

## 🚨 PRÓXIMOS PASSOS

1. **Imediatamente:** Usar entrypoint simples
2. **Fazer novo deploy** no EasyPanel
3. **Verificar logs** se ficou verde
4. **Testar RDO** para confirmar correções

## 📊 MONITORAMENTO

Após deploy bem-sucedido, verificar:
- ✅ Sistema acessível
- ✅ RDOs salvando com nomes corretos
- ✅ Sem "Etapa Inicial" extra
- ✅ Dashboard funcionando