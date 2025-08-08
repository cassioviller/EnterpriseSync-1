#!/bin/bash
# Docker entrypoint com migração automática da coluna foto_base64
# Seguindo o padrão estabelecido para admin_id e kpi_associado

echo "===========================================" 
echo "DOCKER ENTRYPOINT: SIGE v8.0 - FOTOS BASE64"
echo "==========================================="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# Verificar se estamos em produção
if [[ -n "$DATABASE_URL" && "$DATABASE_URL" == postgres* ]]; then
    echo "🌍 Ambiente: PRODUÇÃO"
    echo "📊 Database: PostgreSQL"
else
    echo "🌍 Ambiente: DESENVOLVIMENTO" 
    echo "📊 Database: Local"
fi

# Aguardar banco de dados estar disponível
echo ""
echo "⏳ Aguardando banco de dados..."
while ! pg_isready -h ${PGHOST:-localhost} -p ${PGPORT:-5432} -U ${PGUSER:-postgres} -d ${PGDATABASE:-sige} 2>/dev/null; do
    echo "   Aguardando PostgreSQL..."
    sleep 2
done
echo "✅ Banco de dados disponível!"

# Executar migração da coluna foto_base64
echo ""
echo "🔧 Executando migração da coluna foto_base64..."
python3 migrations/add_foto_base64_to_funcionario.py

if [ $? -eq 0 ]; then
    echo "✅ Migração foto_base64 concluída com sucesso!"
else
    echo "⚠️ Aviso na migração foto_base64 (pode já existir)"
fi

# Validar integridade do banco
echo ""
echo "🔍 Validando integridade do banco..."
python3 -c "
from app import app, db
from models import Funcionario
from sqlalchemy import text

with app.app_context():
    try:
        # Verificar coluna foto_base64
        result = db.session.execute(text('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = \'funcionario\' AND column_name = \'foto_base64\'
        ''')).fetchone()
        
        if result:
            print('✅ Coluna foto_base64 validada')
        else:
            print('❌ Coluna foto_base64 não encontrada')
            
        # Contar funcionários com fotos base64
        count = Funcionario.query.filter(Funcionario.foto_base64.isnot(None)).count()
        print(f'📊 Funcionários com foto_base64: {count}')
        
    except Exception as e:
        print(f'⚠️ Erro na validação: {e}')
"

# Iniciar aplicação
echo ""
echo "🚀 Iniciando aplicação SIGE..."
echo "==========================================="

exec "$@"