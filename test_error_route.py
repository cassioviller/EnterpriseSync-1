"""
Rota de teste para gerar erro e verificar os logs detalhados
"""
from flask import Blueprint

test_bp = Blueprint('test_error', __name__)

@test_bp.route('/test-error')
def test_error():
    """Rota que força um erro para testar o sistema de logs"""
    # Forçar erro de template similar ao que acontece em produção
    raise Exception("unsupported format string passed to Undefined.__format__ - ERRO DE TESTE PARA DIAGNÓSTICO")

@test_bp.route('/test-template-error')
def test_template_error():
    """Teste específico de erro de template"""
    from flask import render_template
    # Simular erro de template Jinja
    return render_template('teste_template_erro.html', valor_undefined=None)