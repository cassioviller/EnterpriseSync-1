from app import app

# API RDO Refatorada removida - funcionalidade integrada em salvar_rdo_flexivel

# Registrar sistema de edição de RDO
try:
    from rdo_editar_sistema import rdo_editar_bp
    app.register_blueprint(rdo_editar_bp)
    print("✅ Sistema de edição RDO registrado")
except ImportError as e:
    print(f"⚠️ Erro ao importar sistema de edição RDO: {e}")
except Exception as e:
    print(f"❌ Erro ao registrar sistema de edição RDO: {e}")





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

# Blueprint antigo removido - usando apenas CRUD de Serviços moderno

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

# Registrar sistema de cadastro de serviços na obra
try:
    from cadastrar_servico_obra import cadastrar_servico_bp
    app.register_blueprint(cadastrar_servico_bp)
    print("✅ Sistema de cadastro serviço-obra registrado")
except Exception as e:
    print(f"❌ Erro ao registrar cadastro serviço-obra: {e}")

# Sistema de veículos-obras removido (código obsoleto limpo)

# Dashboard executivo removido (código obsoleto limpo)

# Registrar Analytics Preditivos
try:
    from analytics_preditivos import analytics_bp
    app.register_blueprint(analytics_bp)
    print("✅ Analytics Preditivos registrado")
except Exception as e:
    print(f"❌ Erro ao registrar Analytics Preditivos: {e}")

# Sistema de alertas avançados removido (código obsoleto limpo)

# Relatórios de produtividade removido (código obsoleto limpo)

# Registrar Dashboards Específicos
try:
    from dashboards_especificos import dashboards_bp
    app.register_blueprint(dashboards_bp)
    print("✅ Dashboards Específicos registrado")
except Exception as e:
    print(f"❌ Erro ao registrar Dashboards Específicos: {e}")

# Registrar Exportação de Relatórios
try:
    from exportacao_relatorios import exportacao_bp
    app.register_blueprint(exportacao_bp)
    print("✅ Exportação de Relatórios registrado")
except Exception as e:
    print(f"❌ Erro ao registrar Exportação de Relatórios: {e}")

# Registrar Relatórios Financeiros Avançados
try:
    from relatorios_financeiros_avancados import financeiros_bp
    app.register_blueprint(financeiros_bp)
    print("✅ Relatórios Financeiros Avançados registrado")
except Exception as e:
    print(f"❌ Erro ao registrar Relatórios Financeiros: {e}")

# Relatórios de uso detalhado removido (código obsoleto limpo)

# Alimentação CRUD já registrado em app.py - removendo duplicação

print("🔥 SISTEMA INICIADO - Todos os blueprints críticos foram carregados")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
