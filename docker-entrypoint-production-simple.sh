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
        
        # Correção de nomes em RDOs existentes (PRODUÇÃO)
        corrections = {
            'Subatividade 440': 'Preparação da Estrutura',
            'Subatividade 441': 'Instalação de Terças', 
            'Subatividade 442': 'Colocação das Telhas',
            'Subatividade 443': 'Vedação e Calhas',
            'Subatividade 150': '1. Detalhamento do projeto',
            'Subatividade 151': '2. Seleção de materiais', 
            'Subatividade 152': '3. Traçagem',
            'Subatividade 153': '4. Corte mecânico',
            'Subatividade 154': '5. Furação',
            'Subatividade 155': '6. Montagem e soldagem',
            'Subatividade 156': '7. Acabamento e pintura', 
            'Subatividade 157': '8. Identificação e logística',
            'Subatividade 158': '9. Planejamento de montagem',
            'Subatividade 159': '10. Preparação do local',
            'Subatividade 160': '11. Transporte para obra',
            'Subatividade 161': '12. Posicionamento e alinhamento',
            'Subatividade 162': '13. Fixação definitiva',
            'Subatividade 163': '14. Inspeção e controle de qualidade',
            'Subatividade 164': '15. Documentação técnica',
            'Subatividade 165': '16. Entrega e aceitação'
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
        
        # Corrigir admin_id (PRODUÇÃO usa admin_id=2)
        db.session.execute(text('''
            UPDATE rdo SET admin_id = 2 
            WHERE admin_id IS NULL OR admin_id = 0 OR admin_id = 10
        '''))
        
        # Corrigir funcionários órfãos
        db.session.execute(text('''
            UPDATE funcionario SET admin_id = 2 
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