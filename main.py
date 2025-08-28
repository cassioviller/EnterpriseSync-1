from app import app

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

# Registrar blueprint de serviços - TEMPORARIAMENTE DESABILITADO
# try:
#     from servicos_blueprint import servicos_bp
#     app.register_blueprint(servicos_bp)
#     print("✅ Blueprint serviços registrado com sucesso")
# except ImportError as e:
#     print(f"⚠️ Blueprint serviços não encontrado: {e}")
# except Exception as e:
#     print(f"❌ Erro ao registrar blueprint serviços: {e}")
print("⚠️ Blueprint serviços temporariamente desabilitado para correções")

# Registrar health check
try:
    from health import health_bp
    app.register_blueprint(health_bp)
    print("✅ Health check registrado")
except ImportError as e:
    print(f"⚠️ Health check não encontrado: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
