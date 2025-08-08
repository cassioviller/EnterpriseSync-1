#!/bin/bash
set -e

echo "🚀 Iniciando deploy do SIGE v8.0"

# 1. Executar migrações de banco de dados
echo "🔧 Executando migrações de banco de dados..."
python scripts/deploy_migrations.py

# 2. Verificar dependências
echo "📦 Verificando dependências..."
pip list | grep -E "(flask|sqlalchemy|gunicorn)"

# 3. Inicializar banco de dados (criar tabelas se necessário)
echo "🗄️ Inicializando banco de dados..."
python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('✅ Tabelas do banco de dados verificadas/criadas')
"

# 4. Executar verificações de integridade
echo "🔍 Executando verificações de integridade..."
python -c "
from app import app, db
from models import OutroCusto, Funcionario
from sqlalchemy import text

with app.app_context():
    try:
        # Verificar se OutroCusto funciona com admin_id
        total = OutroCusto.query.count()
        with_admin = OutroCusto.query.filter(OutroCusto.admin_id.isnot(None)).count()
        
        print(f'✅ OutroCusto: {total} registros, {with_admin} com admin_id')
        
        # Verificar estrutura da tabela
        result = db.session.execute(text('''
            SELECT COUNT(*) as total_colunas
            FROM information_schema.columns 
            WHERE table_name = \'outro_custo\'
        '''))
        
        colunas = result.scalar()
        print(f'✅ Tabela outro_custo: {colunas} colunas')
        
        if colunas >= 12:
            print('✅ Estrutura da tabela correta (incluindo admin_id)')
        else:
            print('❌ Estrutura da tabela incompleta')
            exit(1)
            
    except Exception as e:
        print(f'❌ Erro na verificação: {e}')
        exit(1)
"

echo "✅ Deploy concluído com sucesso!"
echo "🎯 Sistema SIGE v8.0 pronto para uso"

# 5. Iniciar aplicação
echo "🌐 Iniciando aplicação..."
exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app