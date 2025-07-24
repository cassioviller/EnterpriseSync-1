# 📋 INSTRUÇÕES DE DEPLOY - SIGE v8.0

## 🎯 Situação Atual

O sistema foi implantado com sucesso no EasyPanel, mas o banco de dados está vazio. Para resolver isso, execute os seguintes comandos:

## 🚀 Passos para Ativar o Sistema

### 1. Conectar ao Container

Acesse o terminal do container no EasyPanel e execute:

```bash
# Navegar para o diretório da aplicação
cd /app

# Executar script de configuração do banco
python setup_production_database.py
```

### 2. Verificar Funcionamento

Após executar o script, o sistema terá:

- ✅ Todas as tabelas criadas
- ✅ Super Admin: `admin@sige.com` / `admin123`
- ✅ Admin Demo: `valeverde` / `admin123`
- ✅ Dados básicos (departamentos, funções, horários)
- ✅ Funcionários de demonstração
- ✅ Obra e veículos de exemplo

### 3. Acessar o Sistema

1. **Super Admin**: Para gerenciar administradores
   - Login: `admin@sige.com`
   - Senha: `admin123`

2. **Admin Demo**: Para testar todas as funcionalidades
   - Login: `valeverde`
   - Senha: `admin123`

## 🔧 Comandos Alternativos

Se preferir executar passo a passo:

```bash
# Apenas criar tabelas
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Apenas criar super admin
python criar_superadmin.py

# Executar migrações (se necessário)
export FLASK_APP=main.py
flask db upgrade
```

## 📊 Validação do Sistema

Para verificar se tudo está funcionando:

```bash
# Testar conexão e dados
python -c "
from app import app, db
from models import Usuario, Funcionario
with app.app_context():
    print(f'Usuários: {Usuario.query.count()}')
    print(f'Funcionários: {Funcionario.query.count()}')
    print('Sistema operacional!')
"
```

## 🐳 Informações do Deploy

- **Imagem Docker**: `easypanel/viajey/sige1`
- **Banco de dados**: PostgreSQL (configurado via `DATABASE_URL`)
- **Porta**: 5000
- **Ambiente**: Produção

## 🔐 Segurança

Após validar o funcionamento, recomenda-se:

1. Alterar as senhas padrão
2. Configurar backup automático do banco
3. Ativar logs de auditoria
4. Configurar SSL/TLS

## 🆘 Resolução de Problemas

Se houver erros:

1. Verificar se `DATABASE_URL` está configurada
2. Verificar conectividade com PostgreSQL
3. Executar: `python -c "from app import db; print(db.engine.url)"`
4. Consultar logs: `tail -f /app/logs/sige.log`

---

**Sistema pronto para uso após executar `setup_production_database.py`**