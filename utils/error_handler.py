"""
SISTEMA DE TRATAMENTO DE ERROS DETALHADO - SIGE v8.0
Captura e exibe erros detalhados para debugging em desenvolvimento
"""

import traceback
import logging
import os
from flask import current_app, render_template_string, request, redirect, url_for, flash
from datetime import datetime

logger = logging.getLogger(__name__)

def handle_detailed_error(exception, context="Sistema", fallback_url="main.dashboard"):
    """
    Manipula erros com detalhes completos para debugging
    
    Args:
        exception: A exceção capturada
        context: Contexto onde ocorreu o erro
        fallback_url: URL para redirecionamento em produção
    
    Returns:
        Response com erro detalhado (dev) ou redirect (prod)
    """
    
    error_trace = traceback.format_exc()
    error_msg = f"Erro no {context}: {str(exception)}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Log detalhado
    logger.error(f"❌ {error_msg}")
    logger.error(f"📋 Traceback completo:\n{error_trace}")
    
    # Informações de contexto
    context_info = {
        'timestamp': timestamp,
        'url': getattr(request, 'url', 'N/A'),
        'method': getattr(request, 'method', 'N/A'),
        'user_agent': getattr(request, 'user_agent', 'N/A'),
        'form_data': dict(getattr(request, 'form', {})),
        'args': dict(getattr(request, 'args', {}))
    }
    
    # Em desenvolvimento ou debug, mostrar erro detalhado
    if (current_app.config.get('DEBUG', False) or 
        os.environ.get('FLASK_ENV') == 'development' or
        os.environ.get('SHOW_DETAILED_ERRORS') == 'true'):
        
        error_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erro Detalhado - {context}</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: #f5f5f5; 
                }}
                .error-container {{ 
                    max-width: 1200px; 
                    margin: 0 auto; 
                    background: white; 
                    border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .error-header {{ 
                    background: #dc3545; 
                    color: white; 
                    padding: 20px; 
                    border-radius: 8px 8px 0 0;
                }}
                .error-content {{ 
                    padding: 20px; 
                }}
                .error-section {{ 
                    margin: 20px 0; 
                    padding: 15px; 
                    border: 1px solid #dee2e6; 
                    border-radius: 5px; 
                    background: #f8f9fa;
                }}
                .error-trace {{ 
                    background: #2d3748; 
                    color: #e2e8f0; 
                    padding: 20px; 
                    border-radius: 5px; 
                    font-family: 'Consolas', 'Monaco', monospace; 
                    font-size: 12px; 
                    overflow-x: auto; 
                    white-space: pre-wrap; 
                    line-height: 1.4;
                }}
                .btn {{ 
                    display: inline-block; 
                    background: #007bff; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 10px 5px 0 0;
                }}
                .btn-copy {{ 
                    background: #28a745; 
                }}
                .info-grid {{ 
                    display: grid; 
                    grid-template-columns: 150px 1fr; 
                    gap: 10px; 
                    align-items: start;
                }}
                .info-label {{ 
                    font-weight: bold; 
                    color: #495057;
                }}
                details {{ 
                    margin: 15px 0; 
                }}
                summary {{ 
                    cursor: pointer; 
                    padding: 10px; 
                    background: #e9ecef; 
                    border-radius: 5px; 
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-header">
                    <h1>🚨 Erro Detalhado - {context}</h1>
                    <p>Erro capturado em: {timestamp}</p>
                </div>
                
                <div class="error-content">
                    <div class="error-section">
                        <h3>📋 Informações do Erro</h3>
                        <div class="info-grid">
                            <span class="info-label">Tipo:</span>
                            <span>{type(exception).__name__}</span>
                            <span class="info-label">Mensagem:</span>
                            <span>{str(exception)}</span>
                        </div>
                    </div>
                    
                    <div class="error-section">
                        <h3>🌐 Contexto da Requisição</h3>
                        <div class="info-grid">
                            <span class="info-label">URL:</span>
                            <span>{context_info['url']}</span>
                            <span class="info-label">Método:</span>
                            <span>{context_info['method']}</span>
                            <span class="info-label">User Agent:</span>
                            <span style="word-break: break-all;">{context_info['user_agent']}</span>
                        </div>
                    </div>
                    
                    {f'''
                    <div class="error-section">
                        <h3>📝 Dados do Formulário</h3>
                        <pre style="background: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto;">{context_info['form_data']}</pre>
                    </div>
                    ''' if context_info['form_data'] else ''}
                    
                    <details open>
                        <summary>🔍 Stack Trace Completo</summary>
                        <div class="error-trace">{error_trace}</div>
                    </details>
                    
                    <div style="margin-top: 20px;">
                        <a href="/{fallback_url.replace('main.', '')}" class="btn">← Voltar</a>
                        <button onclick="copyError()" class="btn btn-copy">📋 Copiar Erro</button>
                        <button onclick="location.reload()" class="btn">🔄 Tentar Novamente</button>
                    </div>
                </div>
            </div>
            
            <script>
                function copyError() {{
                    const errorText = `ERRO {context} - {timestamp}
                    
TIPO: {type(exception).__name__}
MENSAGEM: {str(exception)}
URL: {context_info['url']}
MÉTODO: {context_info['method']}

STACK TRACE:
{error_trace}`;
                    
                    navigator.clipboard.writeText(errorText).then(function() {{
                        alert('✅ Erro copiado! Cole no chat para análise.');
                    }});
                }}
            </script>
        </body>
        </html>
        """
        
        return render_template_string(error_template), 500
    
    else:
        # Em produção, mensagem amigável + log
        flash(f'Erro no {context.lower()}. Nossa equipe foi notificada.', 'error')
        return redirect(url_for(fallback_url))

def log_sql_error(exception, query_context=""):
    """Log específico para erros SQL com informações de transação"""
    
    logger.error(f"🚨 ERRO SQL: {str(exception)}")
    if query_context:
        logger.error(f"📋 Contexto: {query_context}")
    
    # Detectar tipos comuns de erro SQL
    error_str = str(exception).lower()
    
    if "transaction" in error_str and "aborted" in error_str:
        logger.error("💥 ERRO DE TRANSAÇÃO: Transação abortada - possível conflito de dados")
        
    elif "duplicate key" in error_str:
        logger.error("🔑 ERRO DE CHAVE: Tentativa de inserir dados duplicados")
        
    elif "foreign key" in error_str:
        logger.error("🔗 ERRO DE INTEGRIDADE: Violação de chave estrangeira")
        
    elif "connection" in error_str:
        logger.error("📡 ERRO DE CONEXÃO: Problema na conexão com banco de dados")
        
    elif "timeout" in error_str:
        logger.error("⏰ ERRO DE TIMEOUT: Operação demorou muito para executar")