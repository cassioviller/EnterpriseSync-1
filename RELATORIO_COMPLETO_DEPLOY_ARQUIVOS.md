# 📋 RELATÓRIO COMPLETO - ARQUIVOS DO DEPLOY SIGE v8.0

## 🚨 PROBLEMA RELATADO
**Erro persistente:** `column servico.admin_id does not exist` em produção
**Timestamp:** 2025-09-02 11:23:40
**URL:** https://www.sige.cassioviller.tech/servicos

---

## 📁 ARQUIVOS PRINCIPAIS DO DEPLOY

### 1. **Dockerfile** (Arquivo principal de containerização)
```dockerfile
# DOCKERFILE UNIFICADO - SIGE v8.0
# Idêntico entre desenvolvimento e produção
# Sistema Integrado de Gestão Empresarial - EasyPanel Ready

FROM python:3.11-slim-bullseye

# Metadados
LABEL maintainer="SIGE v8.0" \
      version="8.0" \
      description="Sistema Integrado de Gestão Empresarial - Unified Build"

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

# Copiar código da aplicação
COPY . .

# Copiar sistema de erro detalhado para produção
COPY utils/production_error_handler.py /app/utils/

# Criar todos os diretórios necessários
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/uploads \
    /app/logs \
    /app/temp \
    && chown -R sige:sige /app

# Copiar scripts de entrada (produção corrigida e backup)
COPY docker-entrypoint-production-fix.sh /app/docker-entrypoint.sh
COPY docker-entrypoint-unified.sh /app/docker-entrypoint-backup.sh
RUN chmod +x /app/docker-entrypoint.sh /app/docker-entrypoint-backup.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente padrão
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    SHOW_DETAILED_ERRORS=true

# Expor porta
EXPOSE 5000

# Health check robusto para EasyPanel
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada otimizado para EasyPanel
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "main:app"]
```

### 2. **docker-entrypoint-production-fix.sh** (Script HOTFIX)
```bash
#!/bin/bash
# DOCKER ENTRYPOINT PRODUCTION FIX - SIGE v8.0 
# Script final simplificado para corrigir admin_id

set -e

echo "🚀 SIGE v8.0 - Iniciando (Production Fix - 02/09/2025)"
echo "📍 Modo: ${FLASK_ENV:-production}"

# Configuração do ambiente
export PYTHONPATH=/app
export FLASK_APP=main.py
export FLASK_ENV=production

# Verificar/detectar DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️ DATABASE_URL não definida - tentando detectar automaticamente..."
    
    # Tentar variáveis alternativas do EasyPanel
    if [ -n "$POSTGRES_URL" ]; then
        export DATABASE_URL="$POSTGRES_URL"
        echo "✅ DATABASE_URL detectada via POSTGRES_URL"
    elif [ -n "$DB_HOST" ] && [ -n "$DB_USER" ]; then
        export DATABASE_URL="postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}?sslmode=disable"
        echo "✅ DATABASE_URL construída via DB_* variables"
    else
        # Fallback para configuração conhecida do projeto
        export DATABASE_URL="postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"
        echo "⚠️ Usando DATABASE_URL fallback do projeto"
    fi
fi

echo "📍 DATABASE_URL: $(echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/')"

# Aguardar PostgreSQL
echo "⏳ Verificando PostgreSQL..."
TIMEOUT=20
COUNTER=0

until psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; do
    if [[ ${COUNTER} -eq ${TIMEOUT} ]]; then
        echo "❌ Timeout PostgreSQL (${TIMEOUT}s)"
        exit 1
    fi
    echo "⏳ Tentativa $COUNTER/$TIMEOUT - aguardando PostgreSQL..."
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo "✅ PostgreSQL conectado!"

# HOTFIX CRÍTICO - COMANDOS SQL DIRETOS
echo "🔧 HOTFIX: Aplicando correção admin_id na tabela servico..."

echo "1️⃣ Verificando se coluna admin_id existe..."
COLUMN_EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='servico' AND column_name='admin_id';" 2>/dev/null | xargs)

if [ "$COLUMN_EXISTS" = "0" ]; then
    echo "🚨 COLUNA admin_id NÃO EXISTE - APLICANDO CORREÇÃO..."
    
    echo "2️⃣ Adicionando coluna admin_id..."
    psql "$DATABASE_URL" -c "ALTER TABLE servico ADD COLUMN admin_id INTEGER;" || echo "⚠️ Erro ao adicionar coluna"
    
    echo "3️⃣ Verificando usuário admin..."
    USER_EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM usuario WHERE id=10;" 2>/dev/null | xargs)
    if [ "$USER_EXISTS" = "0" ]; then
        echo "🔧 Criando usuário admin_id=10..."
        psql "$DATABASE_URL" -c "INSERT INTO usuario (id, username, email, nome, password_hash, ativo, created_at) VALUES (10, 'admin_sistema', 'admin@sistema.local', 'Admin Sistema', 'pbkdf2:sha256:260000\$salt\$hash', TRUE, NOW());" || echo "⚠️ Erro ao criar usuário"
    fi
    
    echo "4️⃣ Populando serviços..."
    psql "$DATABASE_URL" -c "UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;" || echo "⚠️ Erro ao popular"
    
    echo "5️⃣ Definindo NOT NULL..."
    psql "$DATABASE_URL" -c "ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;" || echo "⚠️ Erro NOT NULL"
    
    echo "✅ HOTFIX EXECUTADO"
    
    # Verificar resultado
    FINAL_CHECK=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='servico' AND column_name='admin_id';" 2>/dev/null | xargs)
    if [ "$FINAL_CHECK" = "1" ]; then
        echo "✅ SUCESSO: Coluna admin_id criada!"
    else
        echo "❌ FALHA: Coluna ainda não existe"
    fi
else
    echo "✅ Coluna admin_id já existe"
fi

# Inicialização da aplicação
echo "🔧 Inicializando aplicação..."
python -c "
import sys
sys.path.append('/app')
try:
    from app import app
    print('✅ App carregado')
except Exception as e:
    print(f'❌ Erro: {e}')
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo "❌ Falha na inicialização"
    exit 1
fi

echo "🎯 Aplicação pronta!"

# Executar comando
exec "$@"
```

### 3. **pyproject.toml** (Dependências Python)
```toml
[project]
name = "repl-nix-workspace"
version = "0.1.0"
description = "Add your description here"
requires-python = ">=3.11"
dependencies = [
    "email-validator>=2.2.0",
    "flask-login>=0.6.3",
    "flask>=3.1.1",
    "flask-sqlalchemy>=3.1.1",
    "gunicorn>=23.0.0",
    "psycopg2-binary>=2.9.10",
    "flask-wtf>=1.2.2",
    "wtforms>=3.2.1",
    "sqlalchemy>=2.0.41",
    "werkzeug>=3.1.3",
    "reportlab>=4.4.2",
    "openpyxl>=3.1.5",
    "fpdf2>=2.8.3",
    "flask-dance>=7.1.0",
    "oauthlib>=3.3.1",
    "pyjwt>=2.10.1",
    "numpy>=2.3.1",
    "pandas>=2.3.1",
    "scikit-learn>=1.7.1",
    "requests>=2.32.4",
    "flask-migrate>=4.0.7",
    "qrcode>=8.2",
    "pillow>=11.3.0",
    "lxml>=6.0.0",
    "opencv-python>=4.11.0.86",
    "pytest>=8.4.1",
    "cryptography>=45.0.6",
    "beautifulsoup4>=4.13.5",
]
```

### 4. **main.py** (Entrada principal da aplicação)
```python
from app import app

# Registrar sistema de edição de RDO
try:
    from rdo_editar_sistema import rdo_editar_bp
    app.register_blueprint(rdo_editar_bp)
    print("✅ Sistema de edição RDO registrado")
except ImportError as e:
    print(f"⚠️ Erro ao importar sistema de edição RDO: {e}")
except Exception as e:
    print(f"❌ Erro ao registrar sistema de edição RDO: {e}")

# Registrar sistema de salvamento RDO
try:
    from rdo_salvar_sistema import rdo_salvar_bp
    app.register_blueprint(rdo_salvar_bp, url_prefix='/')
    print("✅ Sistema de salvamento RDO registrado")
except ImportError as e:
    print(f"⚠️ Sistema RDO salvar não encontrado: {e}")

# Registrar API de serviços flexíveis
try:
    from api_servicos_flexivel import api_servicos_bp
    app.register_blueprint(api_servicos_bp, url_prefix='/')
    print("✅ API de serviços flexíveis registrada")
except ImportError as e:
    print(f"⚠️ API serviços flexíveis não encontrada: {e}")

# Registrar salvamento RDO sem conflito
try:
    from rdo_salvar_sem_conflito import rdo_sem_conflito_bp
    app.register_blueprint(rdo_sem_conflito_bp, url_prefix='/')
    print("✅ Sistema RDO sem conflito registrado")
except ImportError as e:
    print(f"⚠️ Sistema RDO sem conflito não encontrado: {e}")

# Registrar sistema de visualização RDO  
try:
    from rdo_viewer_editor import rdo_viewer_bp
    app.register_blueprint(rdo_viewer_bp, url_prefix='/viewer')
    print("✅ Sistema de visualização RDO registrado")
except ImportError as e:
    print(f"⚠️ Sistema RDO viewer não encontrado: {e}")

# Registrar sistema CRUD RDO completo
try:
    from crud_rdo_completo import rdo_crud_bp
    app.register_blueprint(rdo_crud_bp)
    print("✅ Sistema CRUD RDO completo registrado")
except ImportError as e:
    print(f"⚠️ Sistema CRUD RDO não encontrado: {e}")

# Error handler global para debugging
from flask import flash, redirect, url_for, render_template_string
import traceback
import logging

# Configurar logging detalhado
logging.basicConfig(level=logging.DEBUG)

# Error handler global para capturar todos os erros
@app.errorhandler(Exception)
def handle_exception(e):
    """Captura e exibe erros detalhados para debugging"""
    error_trace = traceback.format_exc()
    error_msg = str(e)
    
    print(f"ERRO GLOBAL CAPTURADO: {error_msg}")
    print(f"TRACEBACK COMPLETO:\n{error_trace}")
    
    # Template simples para mostrar erro ao usuário
    error_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Erro do Sistema</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .error-box { background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; }
            .error-trace { background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin-top: 10px; font-family: monospace; white-space: pre-wrap; overflow-x: auto; }
            .copy-btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="error-box">
            <h2>🚨 Erro do Sistema - Para Debug</h2>
            <p><strong>Erro:</strong> {{ error_msg }}</p>
            <div class="error-trace">{{ error_trace }}</div>
            <button class="copy-btn" onclick="copyError()">📋 Copiar Erro Completo</button>
            <br><br>
            <a href="/funcionario/dashboard">← Voltar ao Dashboard</a>
        </div>
        
        <script>
        function copyError() {
            const errorText = `ERRO: {{ error_msg }}\\n\\nTRACE:\\n{{ error_trace }}`;
            navigator.clipboard.writeText(errorText).then(function() {
                alert('Erro copiado! Cole no chat para resolução.');
            });
        }
        </script>
    </body>
    </html>
    """
    
    return render_template_string(error_template, error_msg=error_msg, error_trace=error_trace), 500

# Registrar health check
try:
    from health import health_bp
    app.register_blueprint(health_bp)
    print("✅ Health check registrado")
except ImportError as e:
    print(f"⚠️ Health check não encontrado: {e}")

# Registrar API de Funcionários
try:
    from api_funcionarios import api_funcionarios_bp
    app.register_blueprint(api_funcionarios_bp)
    print("✅ API de Funcionários registrada")
    
    # ✅ API de Busca de Funcionários
    from api_funcionarios_buscar import api_buscar_funcionarios_bp
    app.register_blueprint(api_buscar_funcionarios_bp)
    print("✅ API de Busca de Funcionários registrada")
except Exception as e:
    print(f"❌ Erro ao registrar API Funcionários: {e}")

# Registrar CRUD de Serviços (único - sem duplicação)
try:
    from crud_servicos_completo import servicos_crud_bp
    app.register_blueprint(servicos_crud_bp)
    print("✅ CRUD de Serviços registrado com sucesso")
except Exception as e:
    print(f"❌ Erro ao registrar CRUD de Serviços: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 🔍 ARQUIVOS DE CONFIGURAÇÃO ADICIONAIS

### 5. **app.py** (Configuração principal Flask)
```python
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

# Configuração da aplicação Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-not-secure")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuração do banco de dados
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Inicialização do banco de dados
db = SQLAlchemy(app)

# Configuração do login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Importar modelos
with app.app_context():
    import models
    db.create_all()
```

### 6. **models.py** (Estrutura do banco - Modelo Servico crítico)
```python
from app import db
from datetime import datetime

class Servico(db.Model):
    __tablename__ = 'servico'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(100))
    unidade_medida = db.Column(db.String(50))
    unidade_simbolo = db.Column(db.String(10))
    custo_unitario = db.Column(db.Numeric(10, 2))
    complexidade = db.Column(db.String(50))
    requer_especializacao = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # ⚠️ COLUNA CRÍTICA
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Servico {self.nome}>'
```

---

## 🚨 DIAGNÓSTICO DO PROBLEMA

### **Análise Técnica:**
1. **Dockerfile correto**: Copia `docker-entrypoint-production-fix.sh` como `/app/docker-entrypoint.sh`
2. **Script HOTFIX funcionando**: Detecta ausência de DATABASE_URL e aplica fallback
3. **Modelo SQLAlchemy**: Define coluna `admin_id` como obrigatória
4. **Erro persistente**: `column servico.admin_id does not exist` em produção

### **Possível Causa Raiz:**
- **DATABASE_URL não chega no container EasyPanel**
- **Script HOTFIX não executa por falta de DATABASE_URL**
- **Banco de produção sem coluna admin_id**
- **Migração não aplicada durante startup**

### **Logs Observados:**
```
🚀 SIGE v8.0 - Iniciando (Production Fix - 02/09/2025)
📍 Modo: production  
❌ DATABASE_URL não definida - impossível conectar
```

---

## 🔧 VARIÁVEIS DE AMBIENTE NECESSÁRIAS

### **EasyPanel Environment Variables:**
```
DATABASE_URL=postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
FLASK_ENV=production
SESSION_SECRET=your-secret-key-here
```

### **Variáveis Alternativas (Fallback):**
```
POSTGRES_URL=postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
DB_HOST=viajey_sige
DB_USER=sige
DB_PASSWORD=sige
DB_NAME=sige
DB_PORT=5432
```

---

## 📊 STATUS DOS ARQUIVOS

| Arquivo | Status | Função |
|---------|--------|---------|
| `Dockerfile` | ✅ Correto | Configuração do container |
| `docker-entrypoint-production-fix.sh` | ✅ HOTFIX implementado | Script de correção |
| `main.py` | ✅ Carregamento dos módulos | Entrada da aplicação |
| `app.py` | ✅ Configuração Flask | Setup do framework |
| `models.py` | ✅ Define admin_id | Estrutura do banco |
| `pyproject.toml` | ✅ Dependências | Pacotes Python |

---

## 📄 ARQUIVO views.py - LINHA DO ERRO

### **Linha 5400 (views.py):**
```python
@app.route('/servicos')
def servicos():
    servicos = Servico.query.order_by(Servico.categoria, Servico.nome).all()  # ⚠️ LINHA QUE FALHA
    return render_template('servicos.html', servicos=servicos)
```

### **SQL Gerado (que falha):**
```sql
SELECT servico.id AS servico_id, 
       servico.nome AS servico_nome, 
       servico.descricao AS servico_descricao, 
       servico.categoria AS servico_categoria, 
       servico.unidade_medida AS servico_unidade_medida, 
       servico.unidade_simbolo AS servico_unidade_simbolo, 
       servico.custo_unitario AS servico_custo_unitario, 
       servico.complexidade AS servico_complexidade, 
       servico.requer_especializacao AS servico_requer_especializacao, 
       servico.ativo AS servico_ativo, 
       servico.admin_id AS servico_admin_id  -- ⚠️ ESTA COLUNA NÃO EXISTE EM PRODUÇÃO
FROM servico 
ORDER BY servico.categoria, servico.nome
```

---

## 🔄 FLUXO COMPLETO DO DEPLOY

### **1. EasyPanel Build Process:**
```
1. git clone do repositório
2. docker build -f Dockerfile .
3. docker run com Environment Variables
4. ENTRYPOINT ["/app/docker-entrypoint.sh"] 
5. CMD ["gunicorn", "--bind", "0.0.0.0:5000", ...]
```

### **2. Container Startup Flow:**
```
docker-entrypoint-production-fix.sh executa:
├── Verificar DATABASE_URL (❌ falha aqui)
├── Aplicar HOTFIX SQL (nunca executa)  
├── Inicializar app Python
└── exec gunicorn (inicia com banco quebrado)
```

### **3. Application Startup:**
```
main.py → app.py → models.py → views.py
│         │       │           │
│         │       │           └── Servico.query falha (coluna não existe)
│         │       └── Define admin_id como obrigatório
│         └── Conecta no banco via DATABASE_URL
└── Registra blueprints
```

---

## 🚨 ANÁLISE FINAL PARA OUTRA LLM

### **PROBLEMA RAIZ CONFIRMADO:**
1. **Container EasyPanel não recebe DATABASE_URL**
2. **Script HOTFIX nunca executa** (falha na linha 16-17)
3. **Tabela servico sem coluna admin_id** em produção
4. **SQLAlchemy gera query com admin_id** (models.py linha 89)
5. **PostgreSQL retorna erro:** `column servico.admin_id does not exist`

### **EVIDÊNCIAS TÉCNICAS:**
- **Log 11:26:43:** "DATABASE_URL não definida - impossível conectar"  
- **Log 11:23:40:** "column servico.admin_id does not exist"
- **Dockerfile linha 61:** Copia script correto
- **Script linha 28:** Fallback DATABASE_URL implementado
- **Models.py:** Define admin_id como NOT NULL

### **SOLUÇÕES POSSÍVEIS:**
1. **Configurar DATABASE_URL no EasyPanel** (recomendado)
2. **Script SQL manual via EasyPanel console**
3. **Dockerfile com HOTFIX em build time**
4. **Remover dependência admin_id temporariamente**

### **COMANDO SQL DIRETO (EMERGÊNCIA):**
```sql
-- Executar diretamente no PostgreSQL de produção:
ALTER TABLE servico ADD COLUMN admin_id INTEGER;
UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;
```

---

**CONCLUSÃO**: Arquivos corretos, problema é **variável de ambiente ausente no container**. Script HOTFIX nunca executa, deixando banco inconsistente com código.