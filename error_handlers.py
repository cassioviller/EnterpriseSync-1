"""
Error handlers para o SIGE - Sistema robusto de tratamento de erros em produção
"""
from flask import render_template, jsonify, request
import logging

def register_error_handlers(app):
    """Registrar handlers de erro para produção"""
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        logging.error(f"Internal Server Error: {error}")
        logging.error(f"URL: {request.url}")
        logging.error(f"Method: {request.method}")
        
        # Em produção, retornar página de erro amigável
        return render_template('error.html', 
                             error_code=500,
                             error_message="Erro interno do servidor"), 500
    
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
        logging.error(f"Unhandled Exception: {error}")
        logging.error(f"URL: {request.url}")
        return render_template('error.html', 
                             error_code=500,
                             error_message="Erro inesperado"), 500