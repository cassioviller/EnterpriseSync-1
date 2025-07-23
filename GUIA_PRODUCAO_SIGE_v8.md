# GUIA DE PRODUÇÃO - SIGE v8.0

## Configuração do Ambiente

### Variáveis de Ambiente Obrigatórias
```bash
export DATABASE_URL="postgresql://user:pass@localhost/sige_prod"
export SECRET_KEY="sua-chave-super-secreta-128-chars"
export SESSION_SECRET="sua-chave-sessao-secreta"
```

### Dependências do Sistema
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql-client python3-pip nginx

# Python packages
pip install -r requirements.txt
```

### Configurações de Segurança
```bash
# Firewall
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP  
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

## Deploy

### Primeira Instalação
```bash
./deploy_producao.sh
```

### Verificação de Saúde
```bash
curl http://localhost/api/monitoring/health
curl http://localhost/api/monitoring/metrics
```

## Monitoramento

### URLs Importantes
- Health Check: `/api/monitoring/health`
- Métricas: `/api/monitoring/metrics`
- Login: `/login`

### Logs
- Aplicação: Logs do Flask/Gunicorn
- Sistema: `/var/log/syslog`
- Nginx: `/var/log/nginx/`

## Backup e Restauração

### Backup Manual
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### Restauração
```bash
psql $DATABASE_URL < backup_YYYYMMDD.sql
```

## Solução de Problemas

### Problemas Comuns
1. **Erro 500**: Verificar logs da aplicação
2. **Banco desconectado**: Verificar DATABASE_URL
3. **Performance lenta**: Verificar índices

### Contatos
- Suporte: suporte@empresa.com
- Documentação: Sistema validado em 23/07/2025
