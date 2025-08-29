#!/usr/bin/env python3
"""
Script para corrigir templates RDO em produção
Força o uso do template moderno novo.html
"""

import os
import shutil
from datetime import datetime

def backup_template_antigo():
    """Fazer backup do template antigo se existir"""
    templates_antigos = [
        'templates/rdo/criar.html',
        'templates/rdo/formulario.html', 
        'templates/rdo/index.html'
    ]
    
    backup_dir = f"templates/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    for template in templates_antigos:
        if os.path.exists(template):
            backup_path = os.path.join(backup_dir, os.path.basename(template))
            shutil.copy2(template, backup_path)
            print(f"✅ Backup criado: {template} → {backup_path}")
    
    return backup_dir

def verificar_rota_rdo_novo():
    """Verificar se a rota aponta para o template correto"""
    print("🔍 VERIFICANDO ROTAS RDO...")
    
    with open('views.py', 'r') as f:
        conteudo = f.read()
    
    # Procurar por rotas que renderizam templates RDO
    rotas_problematicas = [
        "render_template('rdo/criar.html'",
        "render_template('rdo/formulario.html'", 
        "render_template('rdo/index.html'"
    ]
    
    encontrados = []
    for rota in rotas_problematicas:
        if rota in conteudo:
            encontrados.append(rota)
    
    if encontrados:
        print("❌ ROTAS PROBLEMÁTICAS ENCONTRADAS:")
        for rota in encontrados:
            print(f"   {rota}")
        return False
    else:
        print("✅ Nenhuma rota problemática encontrada")
        return True

def corrigir_rotas_rdo():
    """Corrigir rotas para usar novo.html"""
    print("🔧 CORRIGINDO ROTAS RDO...")
    
    with open('views.py', 'r') as f:
        conteudo = f.read()
    
    # Substituições necessárias
    substituicoes = {
        "render_template('rdo/criar.html'": "render_template('rdo/novo.html'",
        "render_template('rdo/formulario.html'": "render_template('rdo/novo.html'",
        "render_template('rdo/index.html'": "render_template('rdo/novo.html'",
        "'/rdo/criar'": "'/funcionario/rdo/novo'",
        "'/rdo/formulario'": "'/funcionario/rdo/novo'",
        "@app.route('/rdo/novo'": "@app.route('/funcionario/rdo/novo'",
    }
    
    conteudo_corrigido = conteudo
    mudancas = 0
    
    for antigo, novo in substituicoes.items():
        if antigo in conteudo_corrigido:
            conteudo_corrigido = conteudo_corrigido.replace(antigo, novo)
            mudancas += 1
            print(f"✅ Corrigido: {antigo} → {novo}")
    
    if mudancas > 0:
        with open('views.py', 'w') as f:
            f.write(conteudo_corrigido)
        print(f"💾 {mudancas} correções salvas em views.py")
    else:
        print("✅ Nenhuma correção necessária")

def criar_dockerfile_producao_corrigido():
    """Criar Dockerfile específico para corrigir produção"""
    dockerfile = '''FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \\
    postgresql-client \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Garantir que o template correto está sendo usado
RUN python corrigir_template_rdo_producao.py

# Configurações de produção
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV TEMPLATE_AUTO_RELOAD=false

# Script de entrypoint
COPY docker-entrypoint-template-fix.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "--preload", "main:app"]
'''
    
    with open('Dockerfile.template-fix', 'w') as f:
        f.write(dockerfile)
    
    print("✅ Dockerfile.template-fix criado")

def criar_entrypoint_template_fix():
    """Criar entrypoint que força uso do template correto"""
    entrypoint = '''#!/bin/bash
set -e

echo "🚀 SIGE v8.0 - Correção de Template RDO"

# Aguardar PostgreSQL
echo "⏳ Aguardando PostgreSQL..."
until pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres} 2>/dev/null; do
    sleep 2
done
echo "✅ PostgreSQL conectado!"

# Executar correção de templates
echo "🔧 Aplicando correção de templates..."
python corrigir_template_rdo_producao.py

# Verificar se template novo.html existe
if [ ! -f "templates/rdo/novo.html" ]; then
    echo "❌ ERRO: Template templates/rdo/novo.html não encontrado!"
    exit 1
fi

echo "✅ Template novo.html confirmado"

# Executar migrações
echo "🔄 Executando migrações..."
python -c "
from app import app, db
with app.app_context():
    try:
        import migrations
        print('✅ Migrações concluídas')
    except Exception as e:
        print(f'⚠️ Aviso: {e}')
"

# Verificar saúde da aplicação antes de iniciar
echo "🔍 Verificação final..."
python -c "
from app import app
with app.app_context():
    print('✅ Aplicação inicializada corretamente')
"

echo "🎯 Iniciando servidor..."
exec "$@"
'''
    
    with open('docker-entrypoint-template-fix.sh', 'w') as f:
        f.write(entrypoint)
    
    print("✅ docker-entrypoint-template-fix.sh criado")

def main():
    print("🔧 CORREÇÃO DE TEMPLATE RDO PARA PRODUÇÃO")
    print("=" * 50)
    
    # 1. Backup de templates antigos
    backup_dir = backup_template_antigo()
    print(f"📁 Backup criado em: {backup_dir}")
    
    # 2. Verificar rotas
    rotas_ok = verificar_rota_rdo_novo()
    
    # 3. Corrigir rotas se necessário  
    if not rotas_ok:
        corrigir_rotas_rdo()
    
    # 4. Criar arquivos para deploy corrigido
    criar_dockerfile_producao_corrigido()
    criar_entrypoint_template_fix()
    
    print("\n📋 PRÓXIMOS PASSOS PARA PRODUÇÃO:")
    print("1. Use: docker build -f Dockerfile.template-fix -t sige-template-fix .")
    print("2. Deploy com: docker run ... sige-template-fix")
    print("3. A aplicação forçará o uso do template novo.html")
    print("4. Verifique se a interface mostra subatividades, não funcionários")
    
    print("\n✅ Correção preparada para produção!")

if __name__ == "__main__":
    main()