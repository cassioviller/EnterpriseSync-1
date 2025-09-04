#!/bin/bash
# Script de entrada unificado para SIGE v8.2
# Sistema "Serviços da Obra" baseado em RDO + Subatividades

set -e

echo "🚀 Iniciando SIGE v8.2 (Serviços da Obra Corrigido)"

# Detectar ambiente
if [[ "${FLASK_ENV:-production}" == "development" ]]; then
    echo "🔧 Modo: DESENVOLVIMENTO"
    ENABLE_DEBUG=true
else
    echo "🏭 Modo: PRODUÇÃO"
    ENABLE_DEBUG=false
fi

# Verificar e configurar DATABASE_URL
if [[ -z "${DATABASE_URL}" ]]; then
    echo "⚠️  DATABASE_URL não definida, usando padrão EasyPanel"
    export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige"
fi

# Adicionar sslmode=disable se não estiver presente (para EasyPanel)
if [[ "${DATABASE_URL}" != *"sslmode="* ]]; then
    if [[ "${DATABASE_URL}" == *"?"* ]]; then
        export DATABASE_URL="${DATABASE_URL}&sslmode=disable"
    else
        export DATABASE_URL="${DATABASE_URL}?sslmode=disable"
    fi
    echo "🔒 SSL desabilitado para compatibilidade EasyPanel"
fi

# Aguardar conexão com PostgreSQL
echo "⏳ Verificando conexão com PostgreSQL..."

# Extrair componentes da DATABASE_URL de forma mais robusta
if [[ $DATABASE_URL =~ postgres(ql)?://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
    DB_USER="${BASH_REMATCH[2]}"
    DB_PASS="${BASH_REMATCH[3]}" 
    DB_HOST="${BASH_REMATCH[4]}"
    DB_PORT="${BASH_REMATCH[5]}"
    DB_NAME="${BASH_REMATCH[6]}"
else
    # Valores padrão para EasyPanel
    DB_HOST="viajey_sige"
    DB_PORT="5432"
    DB_USER="sige"
    DB_NAME="sige"
fi

echo "🔍 Conectando em: ${DB_HOST}:${DB_PORT} (usuário: ${DB_USER})"

# Aguardar banco com timeout
TIMEOUT=60
COUNTER=0

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout: PostgreSQL não respondeu em ${TIMEOUT}s"
        echo "🔍 Debug: DATABASE_URL=${DATABASE_URL}"
        echo "🔍 Debug: Host=${DB_HOST}, Port=${DB_PORT}, User=${DB_USER}"
        exit 1
    fi
    
    echo "⏳ PostgreSQL não disponível, tentativa $((COUNTER + 1))/${TIMEOUT}..."
    sleep 2
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# Executar migrações automáticas
echo "🔄 Executando migrações automáticas..."
python -c "
import sys
import traceback
from app import app, db

with app.app_context():
    try:
        print('🔄 Testando conexão com banco...')
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        print('✅ Conexão com banco OK')
        
        # Importar e executar migrações
        import migrations
        print('✅ Migrações executadas com sucesso')
        
    except Exception as e:
        print(f'❌ Erro nas migrações: {e}')
        print('📋 Traceback:')
        traceback.print_exc()
        
        # Em produção, falhar se migrações não funcionarem
        if '${FLASK_ENV}' == 'production':
            sys.exit(1)
        else:
            print('⚠️  Continuando em modo desenvolvimento...')
"

# Verificar dados de produção após migrações
echo "🔍 Verificando dados de produção..."
python -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        print('📊 VERIFICAÇÃO COMPLETA DE DADOS DE PRODUÇÃO:')
        print('='*60)
        
        # Verificar admin_ids disponíveis em cada tabela
        print('🔍 Admin_IDs por tabela:')
        
        # Funcionários
        funcionarios = db.session.execute(text('SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'   👥 Funcionários: {dict(funcionarios) if funcionarios else \"Nenhum\"}')
        
        # Serviços  
        servicos = db.session.execute(text('SELECT admin_id, COUNT(*) FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'   🔧 Serviços: {dict(servicos) if servicos else \"Nenhum\"}')
        
        # Subatividades
        subatividades = db.session.execute(text('SELECT admin_id, COUNT(*) FROM subatividade_mestre WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'   📋 Subatividades: {dict(subatividades) if subatividades else \"Nenhum\"}')
        
        # Obras
        obras = db.session.execute(text('SELECT admin_id, COUNT(*) FROM obra GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'   🏗️  Obras: {dict(obras) if obras else \"Nenhum\"}')
        
        # Detectar admin_id recomendado para produção
        print('\\n🎯 DETECÇÃO AUTOMÁTICA DE ADMIN_ID:')
        
        # Buscar admin_id com mais dados combinados (query corrigida)
        combined_query = text('''
            SELECT all_admins.admin_id, 
                   COALESCE(f.funcionarios, 0) + COALESCE(s.servicos, 0) + COALESCE(o.obras, 0) as total_dados
            FROM (
                SELECT DISTINCT admin_id FROM funcionario 
                UNION SELECT DISTINCT admin_id FROM servico 
                UNION SELECT DISTINCT admin_id FROM obra WHERE admin_id IS NOT NULL
            ) all_admins
            LEFT JOIN (SELECT admin_id, COUNT(*) as funcionarios FROM funcionario WHERE ativo = true GROUP BY admin_id) f ON all_admins.admin_id = f.admin_id
            LEFT JOIN (SELECT admin_id, COUNT(*) as servicos FROM servico WHERE ativo = true GROUP BY admin_id) s ON all_admins.admin_id = s.admin_id  
            LEFT JOIN (SELECT admin_id, COUNT(*) as obras FROM obra GROUP BY admin_id) o ON all_admins.admin_id = o.admin_id
            ORDER BY total_dados DESC, all_admins.admin_id ASC
            LIMIT 1
        ''')
        
        recommended = db.session.execute(combined_query).fetchone()
        if recommended and recommended[0]:
            print(f'   ✅ Admin_ID recomendado para produção: {recommended[0]} (total: {recommended[1]} registros)')
        else:
            print('   ⚠️  Nenhum admin_id encontrado com dados')
        
        print('='*60)
        print('✅ Verificação de produção concluída com sucesso!')
        
    except Exception as e:
        print(f'❌ Erro na verificação de produção: {e}')
        import traceback
        traceback.print_exc()
"

# Verificar registros de rotas e APIs
echo "🔍 Verificando registros de rotas e APIs..."
python -c "
from app import app
import importlib.util
import os

with app.app_context():
    try:
        print('📋 VERIFICAÇÃO COMPLETA DE ROTAS E APIs:')
        print('='*70)
        
        # Listar todos os blueprints registrados
        blueprints = []
        for name, blueprint in app.blueprints.items():
            url_prefix = getattr(blueprint, 'url_prefix', '') or ''
            blueprints.append((name, url_prefix))
        
        print(f'📊 BLUEPRINTS REGISTRADOS: {len(blueprints)} encontrados')
        for name, prefix in sorted(blueprints):
            status = '✅' if prefix else '🔸'
            print(f'   {status} {name}: {prefix or \"/\" } ')
        
        # Verificar rotas principais
        print('\\n🎯 ROTAS PRINCIPAIS:')
        critical_routes = [
            '/',
            '/health', 
            '/login',
            '/dashboard',
            '/funcionarios',
            '/obras',
            '/servicos',
            '/api/funcionarios',
            '/api/servicos'
        ]
        
        # Coletar todas as rotas
        all_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                all_routes.append((rule.rule, rule.methods, rule.endpoint))
        
        print(f'   📈 Total de rotas mapeadas: {len(all_routes)}')
        
        # Verificar rotas críticas
        route_rules = [route[0] for route in all_routes]
        for route in critical_routes:
            if any(route in rule for rule in route_rules):
                print(f'   ✅ {route} - ENCONTRADA')
            else:
                print(f'   ⚠️  {route} - NÃO ENCONTRADA')
        
        # Verificar APIs específicas
        print('\\n🔧 APIs ESPECIALIZADAS:')
        api_patterns = [
            ('/api/funcionarios', 'Gestão de funcionários'),
            ('/api/servicos', 'Gestão de serviços'),
            ('/api/mobile', 'API mobile'),
            ('/servicos', 'CRUD serviços'),
            ('/rdo', 'Sistema RDO'),
            ('/propostas', 'Sistema propostas')
        ]
        
        for pattern, desc in api_patterns:
            matching_routes = [route for route in route_rules if pattern in route]
            if matching_routes:
                print(f'   ✅ {pattern} ({len(matching_routes)} rotas) - {desc}')
            else:
                print(f'   ⚠️  {pattern} - {desc} NÃO ENCONTRADO')
        
        # Verificar health check especificamente
        print('\\n❤️ HEALTH CHECK:')
        health_routes = [route for route in all_routes if 'health' in route[0].lower()]
        if health_routes:
            for route, methods, endpoint in health_routes:
                print(f'   ✅ {route} [{\"|\".join(methods)}] -> {endpoint}')
        else:
            print('   ⚠️  Nenhuma rota de health check encontrada')
        
        # Estatísticas finais
        print('\\n📊 ESTATÍSTICAS FINAIS:')
        api_routes = len([r for r in all_routes if '/api/' in r[0]])
        web_routes = len(all_routes) - api_routes
        print(f'   🌐 Rotas web: {web_routes}')
        print(f'   🔌 Rotas API: {api_routes}')
        print(f'   📦 Blueprints: {len(blueprints)}')
        
        print('='*70)
        print('✅ VERIFICAÇÃO DE ROTAS E APIs CONCLUÍDA!')
        
    except Exception as e:
        print(f'❌ Erro na verificação de rotas: {e}')
        import traceback
        traceback.print_exc()
"

# Teste de endpoints críticos funcionando
echo "🧪 Testando endpoints críticos..."
python -c "
from app import app
import json

with app.test_client() as client:
    try:
        print('🧪 TESTE DE ENDPOINTS CRÍTICOS:')
        print('='*50)
        
        # Definir endpoints críticos para teste
        critical_endpoints = [
            ('/health', 'GET', 'Health Check'),
            ('/', 'GET', 'Home Page'),
            ('/login', 'GET', 'Login Page'),
            ('/dashboard', 'GET', 'Dashboard (pode redirecionar)'),
        ]
        
        successful_tests = 0
        total_tests = len(critical_endpoints)
        
        for endpoint, method, description in critical_endpoints:
            try:
                if method == 'GET':
                    response = client.get(endpoint, follow_redirects=True)
                elif method == 'POST':
                    response = client.post(endpoint, follow_redirects=True)
                else:
                    continue
                
                # Considerar sucesso se não for erro 50x
                if response.status_code < 500:
                    print(f'   ✅ {endpoint} [{method}] -> {response.status_code} - {description}')
                    successful_tests += 1
                else:
                    print(f'   ❌ {endpoint} [{method}] -> {response.status_code} - {description}')
                    
            except Exception as endpoint_error:
                print(f'   ⚠️  {endpoint} [{method}] -> ERRO: {str(endpoint_error)[:50]}... - {description}')
        
        # Resultado final
        success_rate = (successful_tests / total_tests) * 100
        print(f'\\n📊 RESULTADO DOS TESTES:')
        print(f'   ✅ Sucessos: {successful_tests}/{total_tests} ({success_rate:.1f}%)')
        
        if success_rate >= 75:
            print('   🎯 ENDPOINTS CRÍTICOS FUNCIONANDO!')
        else:
            print('   ⚠️  Alguns endpoints podem ter problemas')
        
        print('='*50)
        
    except Exception as e:
        print(f'❌ Erro nos testes de endpoint: {e}')
        import traceback
        traceback.print_exc()
"

if [[ $? -ne 0 && "${FLASK_ENV}" == "production" ]]; then
    echo "❌ Falha crítica nas migrações em produção"
    exit 1
fi

# Verificar integridade dos templates críticos
echo "🔍 Verificando templates críticos..."
TEMPLATES_ESSENCIAIS=(
    "templates/rdo/novo.html"
    "templates/funcionarios.html" 
    "templates/dashboard.html"
    "templates/base_completo.html"
)

for template in "${TEMPLATES_ESSENCIAIS[@]}"; do
    if [[ ! -f "/app/${template}" ]]; then
        echo "❌ Template crítico não encontrado: ${template}"
        exit 1
    fi
done

echo "✅ Todos os templates críticos encontrados"

# Verificar rotas com script dedicado
echo "🔍 Verificando rotas..."
python /app/check_routes.py

if [[ $? -ne 0 ]]; then
    echo "⚠️ Problemas na verificação de rotas, mas continuando..."
fi

# Mostrar estatísticas finais
echo "📊 Estatísticas do sistema:"
echo "   - Python: $(python --version)"
echo "   - Diretório: $(pwd)"
echo "   - Usuário: $(whoami)"
echo "   - Templates: $(find /app/templates -name '*.html' | wc -l) arquivos"
echo "   - Arquivos estáticos: $(find /app/static -type f | wc -l) arquivos"

if [[ "${ENABLE_DEBUG}" == "true" ]]; then
    echo "🔧 Informações de debug ativadas"
    echo "   - Blueprints registrados:"
    python -c "
from app import app
for blueprint in app.blueprints:
    print(f'     - {blueprint}')
"
fi

echo "🎯 Sistema pronto! Iniciando aplicação..."
exec "$@"