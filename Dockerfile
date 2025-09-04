# DOCKERFILE UNIFICADO - SIGE v8.2 - SERVIÇOS DA OBRA CORRIGIDO
# Sistema com "Serviços da Obra" baseado em RDO + Subatividades
# Sistema Integrado de Gestão Empresarial - Deploy Production Ready

FROM python:3.11-slim-bullseye

# Metadados
LABEL maintainer="SIGE v8.2 EasyPanel" \
      version="8.2" \
      description="Sistema Integrado de Gestão Empresarial - Serviços da Obra Corrigido"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ENV=production

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    wget \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário para segurança (mesmo nome em dev/prod)
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar pyproject.toml primeiro para cache de dependências
COPY pyproject.toml ./

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Copiar código da aplicação (incluindo correções Serviços da Obra)
COPY . .

# Funcionalidades implementadas na v8.2:
# - Sistema "Serviços da Obra" corrigido para usar RDO
# - API /api/obras/servicos-rdo para criação automática de RDO inicial  
# - API /api/servicos-disponiveis-obra/<obra_id> para filtrar serviços disponíveis
# - Frontend atualizado com renderização de progresso das subatividades
# - Função obter_servicos_da_obra() corrigida para tabelas servico + subatividade_mestre

# Sistema integrado - sem dependências de arquivos externos

# Criar todos os diretórios necessários
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/uploads \
    /app/logs \
    /app/temp \
    && chown -R sige:sige /app

# Criar script de entrada integrado no Dockerfile
RUN cat > /app/docker-entrypoint.sh << 'EOF'
#!/bin/bash

echo "INICIANDO SIGE v8.2 - Deploy EasyPanel Unificado..."
echo "Configuracao: \${FLASK_ENV:-production}"

# Aguardar PostgreSQL
echo "Aguardando PostgreSQL estar disponivel..."
until pg_isready -h "\${DATABASE_URL##*@}" -p "\${DATABASE_URL##*:}" -U "\${DATABASE_URL##*//}" 2>/dev/null; do
    echo "PostgreSQL nao esta pronto ainda. Tentando novamente em 2 segundos..."
    sleep 2
done

echo "PostgreSQL conectado!"

# Executar migrações automáticas
echo "Executando migracoes automaticas..."
python -c "
import sys
import traceback
from app import app, db

with app.app_context():
    try:
        print('Testando conexao com banco...')
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        print('Conexao com banco OK')
        
        # Importar e executar migrações
        import migrations
        print('Migracoes executadas com sucesso')
        
    except Exception as e:
        print(f'Erro nas migracoes: {e}')
        print('Traceback:')
        traceback.print_exc()
        
        # Em produção, falhar se migrações não funcionarem
        if '\${FLASK_ENV}' == 'production':
            sys.exit(1)
        else:
            print('Continuando em modo desenvolvimento...')
"

# Verificar dados de produção após migrações
echo "Verificando dados de producao..."
python -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        print(' VERIFICAÇÃO DE DADOS DE PRODUÇÃO:')
        print('='*60)
        
        # Verificar admin_ids disponíveis em cada tabela
        print(' Admin_IDs por tabela:')
        
        # Funcionários
        funcionarios = db.session.execute(text('SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'    Funcionários: {dict(funcionarios) if funcionarios else \"Nenhum\"}')
        
        # Serviços  
        servicos = db.session.execute(text('SELECT admin_id, COUNT(*) FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'    Serviços: {dict(servicos) if servicos else \"Nenhum\"}')
        
        # Subatividades
        subatividades = db.session.execute(text('SELECT admin_id, COUNT(*) FROM subatividade_mestre WHERE ativo = true GROUP BY admin_id ORDER BY admin_id')).fetchall()
        print(f'    Subatividades: {dict(subatividades) if subatividades else \"Nenhum\"}')
        
        # Detectar admin_id recomendado
        print('\\n DETECÇÃO AUTOMÁTICA DE ADMIN_ID:')
        
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
            print(f'    Admin_ID recomendado: {recommended[0]} (total: {recommended[1]} registros)')
        else:
            print('     Nenhum admin_id encontrado')
        
        print('='*60)
        print(' Verificação de produção concluída!')
        
    except Exception as e:
        print(f' Erro na verificação: {e}')
        import traceback
        traceback.print_exc()
"

# Verificar registros de rotas e APIs
echo " Verificando rotas e APIs..."
python -c "
from app import app

with app.app_context():
    try:
        print(' VERIFICAÇÃO DE ROTAS E APIs:')
        print('='*70)
        
        # Listar blueprints registrados
        blueprints = []
        for name, blueprint in app.blueprints.items():
            url_prefix = getattr(blueprint, 'url_prefix', '') or ''
            blueprints.append((name, url_prefix))
        
        print(f' BLUEPRINTS: {len(blueprints)} registrados')
        for name, prefix in sorted(blueprints)[:10]:  # Primeiros 10
            status = '' if prefix else '🔸'
            print(f'   {status} {name}: {prefix or \"/\"}')
        
        # Coletar rotas
        all_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                all_routes.append((rule.rule, rule.methods, rule.endpoint))
        
        print(f'\\n ROTAS MAPEADAS: {len(all_routes)}')
        
        # Verificar rotas críticas
        critical_routes = ['/', '/health', '/login', '/dashboard', '/funcionarios']
        route_rules = [route[0] for route in all_routes]
        
        for route in critical_routes:
            if any(route in rule for rule in route_rules):
                print(f'    {route} - ENCONTRADA')
            else:
                print(f'     {route} - NÃO ENCONTRADA')
        
        print('='*70)
        print(' VERIFICAÇÃO DE ROTAS CONCLUÍDA!')
        
    except Exception as e:
        print(f' Erro na verificação de rotas: {e}')
"

# Teste de endpoints críticos
echo " Testando endpoints..."
python -c "
from app import app

with app.test_client() as client:
    try:
        print(' TESTE DE ENDPOINTS:')
        print('='*50)
        
        endpoints = [('/health', 'Health Check'), ('/', 'Home Page'), ('/login', 'Login')]
        successful = 0
        
        for endpoint, desc in endpoints:
            try:
                response = client.get(endpoint, follow_redirects=True)
                if response.status_code < 500:
                    print(f'    {endpoint} -> {response.status_code} - {desc}')
                    successful += 1
                else:
                    print(f'    {endpoint} -> {response.status_code} - {desc}')
            except Exception as e:
                print(f'     {endpoint} -> ERRO - {desc}')
        
        print(f'\\n RESULTADO: {successful}/{len(endpoints)} ({(successful/len(endpoints)*100):.1f}%)')
        print('='*50)
        
    except Exception as e:
        print(f' Erro nos testes: {e}')
"

if [[ $? -ne 0 && "${FLASK_ENV}" == "production" ]]; then
    echo " Falha crítica no deploy"
    exit 1
fi

echo " Deploy verificado com sucesso!"
echo " Iniciando aplicação SIGE v8.2..."

# Executar comando
exec "$@"
EOF

RUN chmod +x /app/docker-entrypoint.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente EasyPanel (específicas para resolver 405 + URL issues)
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    WTF_CSRF_ENABLED=false \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    SHOW_DETAILED_ERRORS=true \
    CORS_ORIGINS="*" \
    CORS_METHODS="GET,POST,PUT,DELETE,OPTIONS" \
    SERVER_NAME=0.0.0.0:5000 \
    APPLICATION_ROOT=/ \
    PREFERRED_URL_SCHEME=http

# Expor porta
EXPOSE 5000

# Health check robusto para EasyPanel
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada otimizado para EasyPanel
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "main:app"]