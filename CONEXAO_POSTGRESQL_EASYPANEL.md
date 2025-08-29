# CONFIGURAÇÃO POSTGRESQL EASYPANEL - SIGE v8.0

## PROBLEMA IDENTIFICADO
O sistema estava tentando conectar em `localhost:5432` mas o banco PostgreSQL do EasyPanel está em `viajey_sige:5432`.

## SOLUÇÃO IMPLEMENTADA

### 1. **String de Conexão Correta**
```
postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
```

### 2. **Configurações Atualizadas**

#### `app.py`:
- Database URL padrão atualizada para EasyPanel
- SSL mode=disable adicionado automaticamente
- Conversão postgres:// → postgresql:// mantida

#### `docker-entrypoint-unified.sh`:
- Parsing melhorado da DATABASE_URL
- Detecção automática de componentes (host, porta, usuário)
- Fallback para configurações EasyPanel
- SSL desabilitado automaticamente

### 3. **Variáveis de Ambiente EasyPanel**

#### Configurar no EasyPanel:
```
DATABASE_URL=postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
SESSION_SECRET=sua-chave-secreta-segura
FLASK_ENV=production
```

### 4. **Verificação de Conexão**

O script agora faz:
1. ✅ Parse correto da URL PostgreSQL
2. ✅ Extração de host, porta, usuário
3. ✅ Teste de conexão com `pg_isready`
4. ✅ SSL desabilitado para compatibilidade
5. ✅ Fallback para configurações EasyPanel

### 5. **Log de Debug**

O sistema agora mostra:
```bash
🔍 Conectando em: viajey_sige:5432 (usuário: sige)
🔒 SSL desabilitado para compatibilidade EasyPanel
✅ PostgreSQL conectado!
```

## TESTE DA CONEXÃO

### Comando de teste:
```bash
pg_isready -h viajey_sige -p 5432 -U sige
```

### Resultado esperado:
```bash
viajey_sige:5432 - accepting connections
```

## CONFIGURAÇÃO FINAL EASYPANEL

### Build Settings:
- **Dockerfile:** `Dockerfile` ✅
- **Port:** `5000` ✅
- **Health Check:** `/health` ✅

### Environment Variables:
```
DATABASE_URL=postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
SESSION_SECRET=your-secure-key-here
FLASK_ENV=production
```

### PostgreSQL Service:
- **Host:** `viajey_sige`
- **Port:** `5432`
- **Database:** `sige`
- **User:** `sige`
- **SSL:** `disabled`

## TROUBLESHOOTING

### Se ainda houver problemas de conexão:

1. **Verificar service name no EasyPanel**
2. **Confirmar credenciais PostgreSQL**
3. **Testar conexão manual:**
   ```bash
   docker exec -it container_name bash
   pg_isready -h viajey_sige -p 5432 -U sige
   ```

### Logs úteis:
```bash
# Ver logs da aplicação
docker logs container_name

# Ver logs PostgreSQL
# (disponível no painel EasyPanel)
```

---

## ✅ STATUS
**CONEXÃO POSTGRESQL CONFIGURADA PARA EASYPANEL**

- String de conexão correta ✅
- SSL desabilitado para compatibilidade ✅
- Parsing robusto da DATABASE_URL ✅
- Fallbacks para EasyPanel ✅
- Logs de debug implementados ✅

**Próximo:** Deploy no EasyPanel com configuração PostgreSQL correta.