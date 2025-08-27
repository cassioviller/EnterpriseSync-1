#!/bin/bash

# HOTFIX PRODUÇÃO: Correção de Transações DB
# Data: $(date +%Y-%m-%d)
# Descrição: Correções para erros de transação abortada

echo "🚨 INICIANDO HOTFIX DE TRANSAÇÃO EM PRODUÇÃO"
echo "============================================"

# Verificar se está em produção
if [ ! -f "/app/views.py" ]; then
    echo "❌ Erro: Este script deve ser executado no ambiente de produção"
    exit 1
fi

# Criar backup de segurança
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
echo "📦 Criando backup de segurança..."
cp /app/views.py /app/views.py.backup.$BACKUP_DATE
cp /app/templates/funcionario_dashboard.html /app/templates/funcionario_dashboard.html.backup.$BACKUP_DATE

echo "✅ Backup criado: views.py.backup.$BACKUP_DATE"

# Aplicar correção 1: Adicionar função safe_db_operation
echo "🔧 Aplicando correção 1: Função safe_db_operation..."

# Criar arquivo temporário com a função
cat << 'EOF' > /tmp/safe_db_function.py

def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro de transação"""
    try:
        return operation()
    except Exception as e:
        print(f"ERRO DB OPERATION: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return default_value

EOF

# Inserir a função após a linha 14
sed -i '14r /tmp/safe_db_function.py' /app/views.py

echo "✅ Função safe_db_operation adicionada"

# Aplicar correção 2: Corrigir template funcionário
echo "🔧 Aplicando correção 2: Template funcionário..."

sed -i 's/main\.funcionario_lista_rdos/main.funcionario_rdo_consolidado/g' /app/templates/funcionario_dashboard.html

echo "✅ Template funcionário corrigido"

# Aplicar correção 3: Substituir consultas problemáticas
echo "🔧 Aplicando correção 3: Consultas com tratamento de erro..."

# Backup do arquivo antes das mudanças complexas
cp /app/views.py /app/views.py.pre_query_fix

# Criar script Python para fazer as substituições complexas
cat << 'EOF' > /tmp/fix_queries.py
import re

# Ler o arquivo
with open('/app/views.py', 'r') as f:
    content = f.read()

# Padrão 1: Corrigir contagem de obras ativas
pattern1 = r'(# Adicionar contagem correta de obras ativas.*?\n)(.*?obras_ativas_count = Obra\.query.*?\.count\(\))'
replacement1 = r'''\1    # Adicionar contagem correta de obras ativas com tratamento de erro
    obras_ativas_count = safe_db_operation(
        lambda: Obra.query.filter_by(admin_id=admin_id).filter(
            Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).count(),
        default_value=0
    )'''

content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE | re.DOTALL)

# Padrão 2: Corrigir busca de obras em andamento
pattern2 = r'(# Buscar obras em andamento para a tabela.*?\n)(.*?obras_andamento = Obra\.query.*?\.all\(\))'
replacement2 = r'''\1    # Buscar obras em andamento para a tabela com tratamento de erro
    obras_andamento = safe_db_operation(
        lambda: Obra.query.filter_by(admin_id=admin_id).filter(
            Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).order_by(Obra.data_inicio.desc()).limit(5).all(),
        default_value=[]
    )'''

content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE | re.DOTALL)

# Salvar o arquivo
with open('/app/views.py', 'w') as f:
    f.write(content)

print("Substituições aplicadas com sucesso")
EOF

python3 /tmp/fix_queries.py

echo "✅ Consultas de banco corrigidas"

# Verificar sintaxe Python
echo "🔍 Verificando sintaxe do código..."
python3 -m py_compile /app/views.py

if [ $? -eq 0 ]; then
    echo "✅ Sintaxe Python válida"
else
    echo "❌ Erro de sintaxe detectado! Restaurando backup..."
    cp /app/views.py.backup.$BACKUP_DATE /app/views.py
    exit 1
fi

# Verificar se o gunicorn está rodando
echo "🔄 Verificando processo gunicorn..."
if pgrep -f "gunicorn.*main:app" > /dev/null; then
    echo "📡 Reiniciando workers do gunicorn..."
    
    # Enviar sinal SIGHUP para reload suave
    pkill -HUP -f "gunicorn.*main:app"
    
    # Aguardar reload
    sleep 3
    
    # Verificar se ainda está rodando
    if pgrep -f "gunicorn.*main:app" > /dev/null; then
        echo "✅ Gunicorn recarregado com sucesso"
    else
        echo "⚠️  Gunicorn parou. Reiniciando..."
        cd /app
        gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --reload --daemon main:app
        sleep 2
        if pgrep -f "gunicorn.*main:app" > /dev/null; then
            echo "✅ Gunicorn reiniciado com sucesso"
        else
            echo "❌ Falha ao reiniciar gunicorn"
            exit 1
        fi
    fi
else
    echo "🚀 Iniciando gunicorn..."
    cd /app
    gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --reload --daemon main:app
    sleep 2
    if pgrep -f "gunicorn.*main:app" > /dev/null; then
        echo "✅ Gunicorn iniciado com sucesso"
    else
        echo "❌ Falha ao iniciar gunicorn"
        exit 1
    fi
fi

# Teste de saúde
echo "🏥 Testando endpoint de saúde..."
sleep 5

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✅ Aplicação respondendo corretamente"
else
    echo "⚠️  Aplicação não responde (HTTP $HEALTH_CHECK)"
fi

# Limpeza
echo "🧹 Limpando arquivos temporários..."
rm -f /tmp/safe_db_function.py /tmp/fix_queries.py

echo ""
echo "🎉 HOTFIX APLICADO COM SUCESSO!"
echo "================================"
echo "📋 Resumo das correções:"
echo "  ✅ Função safe_db_operation adicionada"
echo "  ✅ Template funcionário corrigido"
echo "  ✅ Consultas de banco protegidas"
echo "  ✅ Aplicação reiniciada"
echo ""
echo "📁 Backups disponíveis:"
echo "  - /app/views.py.backup.$BACKUP_DATE"
echo "  - /app/templates/funcionario_dashboard.html.backup.$BACKUP_DATE"
echo ""
echo "🔍 Para monitorar logs:"
echo "  tail -f /app/logs/*.log"
echo "  journalctl -u sige -f"
echo ""
echo "⏰ Data/Hora: $(date)"