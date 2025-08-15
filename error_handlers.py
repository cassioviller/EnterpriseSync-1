"""
Error handlers para o SIGE - Sistema robusto de tratamento de erros em produção
"""
from flask import render_template, jsonify, request
import logging
import traceback
from datetime import datetime

def register_error_handlers(app):
    """Registrar handlers de erro para produção"""
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        error_details = str(error)
        error_traceback = traceback.format_exc()
        error_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        logging.error(f"Internal Server Error: {error}")
        logging.error(f"URL: {request.url}")
        logging.error(f"Method: {request.method}")
        logging.error(f"Traceback: {error_traceback}")
        
        # Detalhes completos do erro para diagnóstico
        full_error_details = f"""
ERRO: {error_details}

URL: {request.url}
MÉTODO: {request.method}
TIMESTAMP: {error_timestamp}
USER AGENT: {request.headers.get('User-Agent', 'Não informado')}

TRACEBACK COMPLETO:
{error_traceback}

HEADERS DA REQUISIÇÃO:
{dict(request.headers)}

ARGUMENTOS DA REQUISIÇÃO:
{dict(request.args)}
"""
        
        return render_template('error.html', 
                             error_code=500,
                             error_message="Erro interno do servidor",
                             error_details=full_error_details,
                             error_url=request.url,
                             error_timestamp=error_timestamp), 500
    
    @app.errorhandler(404)
    def handle_not_found(error):
        logging.warning(f"404 Error: {request.url}")
        return render_template('error.html', 
                             error_code=404,
                             error_message="Página não encontrada"), 404
    
    @app.errorhandler(403)
    def handle_forbidden(error):
        logging.warning(f"403 Error: {request.url}")
        return render_template('error.html', 
                             error_code=403,
                             error_message="Acesso negado"), 403
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        error_details = str(error)
        error_traceback = traceback.format_exc()
        error_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        logging.error(f"Unhandled Exception: {error}")
        logging.error(f"URL: {request.url}")
        logging.error(f"Traceback: {error_traceback}")
        
        # Detalhes completos do erro
        full_error_details = f"""
EXCEÇÃO NÃO TRATADA: {error_details}

URL: {request.url}
MÉTODO: {request.method}
TIMESTAMP: {error_timestamp}
TIPO DO ERRO: {type(error).__name__}

TRACEBACK COMPLETO:
{error_traceback}

CONTEXTO DA REQUISIÇÃO:
- Headers: {dict(request.headers)}
- Args: {dict(request.args)}
- Form: {dict(request.form) if request.form else 'Nenhum'}
- JSON: {request.get_json() if request.is_json else 'Não é JSON'}
"""
        
        return render_template('error.html', 
                             error_code=500,
                             error_message="Erro inesperado no sistema",
                             error_details=full_error_details,
                             error_url=request.url,
                             error_timestamp=error_timestamp), 500