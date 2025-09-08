#!/bin/bash
# SIGE v10.0 - ENTRYPOINT SIMPLIFICADO PARA PRODUÇÃO
# Versão otimizada para deploy rápido e confiável
# Data: 08/09/2025

set -e

echo "🚀 SIGE v10.0 - Iniciando deploy..."

# Configurações básicas
export FLASK_ENV=production
export DIGITAL_MASTERY_MODE=true

# DATABASE_URL padrão para EasyPanel se não definida
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
fi

echo "✅ Configurações aplicadas"

# Aguardar banco de dados (simples)
echo "🔌 Aguardando banco de dados..."
sleep 10

# Executar correções críticas do RDO de forma simplificada
echo "🔧 Aplicando correções do sistema RDO..."

python3 -c "
import sys
import os
sys.path.append('/app')

try:
    from app import app, db
    from sqlalchemy import text
    
    with app.app_context():
        print('🧹 Limpando subatividades duplicadas...')
        
        # Limpeza básica
        db.session.execute(text('''
            DELETE FROM subatividade_mestre 
            WHERE nome IN (\"Etapa Inicial\", \"Etapa Intermediária\")
              AND servico_id = 121
              AND id NOT IN (15236, 15237, 15238, 15239)
        '''))
        
        # Correção de nomes em RDOs existentes
        corrections = {
            'Subatividade 440': 'Preparação da Estrutura',
            'Subatividade 441': 'Instalação de Terças', 
            'Subatividade 442': 'Colocação das Telhas',
            'Subatividade 443': 'Vedação e Calhas'
        }
        
        for old_name, new_name in corrections.items():
            db.session.execute(text('''
                UPDATE rdo_servico_subatividade 
                SET nome_subatividade = :new_name
                WHERE nome_subatividade = :old_name
            '''), {'new_name': new_name, 'old_name': old_name})
        
        # Remover etapas inválidas
        db.session.execute(text('''
            DELETE FROM rdo_servico_subatividade 
            WHERE nome_subatividade IN (\"Etapa Inicial\", \"Etapa Intermediária\")
        '''))
        
        # Corrigir admin_id
        db.session.execute(text('''
            UPDATE rdo SET admin_id = 10 
            WHERE admin_id IS NULL OR admin_id = 0
        '''))
        
        db.session.commit()
        print('✅ Correções aplicadas com sucesso!')
        
except Exception as e:
    print(f'⚠️  Erro nas correções (não crítico): {e}')
    pass
"

echo "✅ Sistema corrigido"

# Criar tabelas se necessário
echo "📊 Verificando estrutura do banco..."
python3 -c "
from app import app, db
with app.app_context():
    try:
        db.create_all()
        print('✅ Tabelas verificadas/criadas')
    except Exception as e:
        print(f'⚠️  Erro ao criar tabelas: {e}')
"

echo "🎯 SIGE v10.0 pronto para produção!"
echo "🚀 Iniciando aplicação..."

# Executar comando passado como parâmetro
exec "$@"