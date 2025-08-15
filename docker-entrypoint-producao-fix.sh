#!/bin/bash

# Script de deploy específico para resolver Internal Server Error em produção
echo "🚀 INICIANDO DEPLOY COM CORREÇÃO DE INTERNAL SERVER ERROR..."

# Aguardar PostgreSQL estar disponível
echo "⏳ Aguardando PostgreSQL..."
for i in {1..30}; do
  if pg_isready -h $PGHOST -p $PGPORT -U $PGUSER; then
    echo "✅ PostgreSQL conectado!"
    break
  fi
  echo "   Tentativa $i/30..."
  sleep 2
done

# Converter URLs postgres:// para postgresql://
if [[ $DATABASE_URL == postgres://* ]]; then
  export DATABASE_URL=${DATABASE_URL/postgres:/postgresql:}
  echo "🔧 URL convertida para postgresql://"
fi

echo "🗄️ Configurando banco de dados..."

# Executar setup do banco via Python inline
python3 << 'EOF'
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(level=logging.INFO)

try:
    # Conectar ao banco
    engine = create_engine(os.environ['DATABASE_URL'])
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("✅ Conexão com banco estabelecida")
    
    # Verificar se existem tabelas
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        print("📦 Banco vazio - criando estrutura...")
        
        # Importar todos os models de uma vez
        sys.path.append('/app')
        from app import app, db
        
        with app.app_context():
            # Criar todas as tabelas
            db.create_all()
            print("✅ Tabelas criadas com sucesso")
            
            # Criar usuários padrão
            from werkzeug.security import generate_password_hash
            from models import Usuario, TipoUsuario
            
            # Verificar se já existem usuários
            user_count = Usuario.query.count()
            if user_count == 0:
                print("👤 Criando usuários padrão...")
                
                # Super Admin
                super_admin = Usuario(
                    nome='Super Admin',
                    email='admin@sige.com',
                    password_hash=generate_password_hash('admin123'),
                    tipo=TipoUsuario.SUPER_ADMIN,
                    ativo=True,
                    admin_id=None
                )
                db.session.add(super_admin)
                
                # Admin Demo
                admin_demo = Usuario(
                    nome='Admin Vale Verde',
                    email='valeverde@sige.com',
                    password_hash=generate_password_hash('admin123'),
                    tipo=TipoUsuario.ADMIN,
                    ativo=True,
                    admin_id=2
                )
                db.session.add(admin_demo)
                
                db.session.commit()
                print("✅ Usuários criados: admin@sige.com e valeverde@sige.com")
    else:
        print(f"✅ Banco já configurado com {len(existing_tables)} tabelas")
    
    # Verificar funcionários
    funcionarios_count = session.execute(text("SELECT COUNT(*) FROM funcionario WHERE ativo = true")).scalar()
    print(f"📊 Funcionários ativos encontrados: {funcionarios_count}")
    
    session.close()
    print("🎯 Setup do banco concluído com sucesso!")
    
except Exception as e:
    print(f"❌ Erro no setup: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "✅ Setup do banco executado com sucesso!"
else
    echo "❌ Falha no setup do banco"
    exit 1
fi

echo "🌐 Iniciando servidor web..."
echo "📍 Rotas seguras disponíveis:"
echo "   - /prod/safe-dashboard"
echo "   - /prod/safe-funcionarios" 
echo "   - /prod/debug-info"

# Iniciar Gunicorn
exec gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 --preload main:app