from app import app
import logging
import os
logger = logging.getLogger(__name__)

# API RDO Refatorada removida - funcionalidade integrada em salvar_rdo_flexivel

# Registrar sistema de edição de RDO
try:
    from rdo_editar_sistema import rdo_editar_bp
    app.register_blueprint(rdo_editar_bp)
    logger.info("[OK] Sistema de edição RDO registrado")
except ImportError as e:
    logger.error(f"[WARN] Erro ao importar sistema de edição RDO: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar sistema de edição RDO: {e}", exc_info=True)





# Registrar sistema CRUD RDO completo
try:
    from crud_rdo_completo import rdo_crud_bp
    app.register_blueprint(rdo_crud_bp)
    logger.info("[OK] Sistema CRUD RDO completo registrado")
except ImportError as e:
    logger.warning(f"[WARN] Sistema CRUD RDO não encontrado: {e}", exc_info=True)

from flask import redirect, url_for, render_template_string, render_template
import traceback

# Fase 0.5 / 1.3 — o nível de log é decidido em UM lugar só.
# Antes havia aqui um `logging.basicConfig(level=logging.DEBUG)` que era
# NO-OP: `from app import app` (linha 1) já configurou o root logger, e sem
# `force=True` o basicConfig não faz nada. Resultado: todo `logger.debug()`
# do sistema era descartado, e quem escreveu esperava o contrário.
# Agora o nível vem de LOG_LEVEL (default INFO) e é aplicado de fato.
_nivel = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.getLogger().setLevel(getattr(logging, _nivel, logging.INFO))
logger.info(f"[OK] Nivel de log: {_nivel}")


# Fase 0.5 / 1.3 — handler global de exceção.
# Antes esta função renderizava o TRACEBACK PYTHON COMPLETO numa página HTML,
# com botão "Copiar Erro Completo", SEM qualquer verificação de ambiente.
# Qualquer 500 em produção — inclusive provocado de propósito por um visitante
# anônimo — expunha caminhos de arquivo, nomes de tabela e trechos de código.
@app.errorhandler(Exception)
def handle_exception(e):
    """Loga o erro completo; mostra detalhe ao usuário SÓ fora de produção."""
    from werkzeug.exceptions import HTTPException

    # HTTPException (404, 403, 422...) tem tratamento próprio — não são falhas
    # do sistema e não devem virar 500.
    if isinstance(e, HTTPException):
        return e

    error_trace = traceback.format_exc()
    error_msg = str(e)

    logger.error(f"ERRO GLOBAL CAPTURADO: {error_msg}")
    logger.error(f"TRACEBACK COMPLETO:\n{error_trace}")

    from app import IS_PRODUCTION
    if IS_PRODUCTION:
        try:
            return render_template('error.html',
                                   error_code=500,
                                   error_message='Erro interno do sistema.'), 500
        except Exception:
            return ('<h1>Erro interno</h1><p>O erro foi registrado. '
                    'Procure o suporte informando o horário.</p>'), 500

    # Fora de produção: detalhe completo, que é onde ele é útil.
    error_template = """
    <!DOCTYPE html>
    <html>
    <head><title>Erro do Sistema (dev)</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .error-box { background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; }
            .error-trace { background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin-top: 10px; font-family: monospace; white-space: pre-wrap; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="error-box">
            <h2>Erro do Sistema — ambiente de desenvolvimento</h2>
            <p><strong>Erro:</strong> {{ error_msg }}</p>
            <div class="error-trace">{{ error_trace }}</div>
        </div>
    </body>
    </html>
    """
    return render_template_string(error_template, error_msg=error_msg,
                                  error_trace=error_trace), 500

# Blueprint antigo removido - usando apenas CRUD de Serviços moderno

# Registrar health check
try:
    from health import health_bp
    app.register_blueprint(health_bp)
    logger.info("[OK] Health check registrado")
except ImportError as e:
    logger.warning(f"[WARN] Health check não encontrado: {e}", exc_info=True)

# Registrar API de Funcionários
try:
    from api_funcionarios import api_funcionarios_bp
    app.register_blueprint(api_funcionarios_bp)
    logger.info("[OK] API de Funcionários registrada")
    
    # [OK] API de Busca de Funcionários
    from api_funcionarios_buscar import api_buscar_funcionarios_bp
    app.register_blueprint(api_buscar_funcionarios_bp)
    logger.info("[OK] API de Busca de Funcionários registrada")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar API Funcionários: {e}", exc_info=True)

# CRUD antigo de Serviços removido (Task #128) — uso exclusivo do Catálogo de Serviços.
# Mantemos um redirect das rotas /servicos* para o Catálogo para não quebrar
# bookmarks ou links externos antigos.
@app.route('/servicos', defaults={'_path': ''})
@app.route('/servicos/<path:_path>')
def _servicos_legacy_redirect(_path):
    return redirect(url_for('catalogo.servicos_list'))

# Registrar sistema de cadastro de serviços na obra
try:
    from cadastrar_servico_obra import cadastrar_servico_bp
    app.register_blueprint(cadastrar_servico_bp)
    logger.info("[OK] Sistema de cadastro serviço-obra registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar cadastro serviço-obra: {e}", exc_info=True)

# Sistema de veículos-obras removido (código obsoleto limpo)

# Dashboard executivo removido (código obsoleto limpo)

# Registrar Analytics Preditivos
try:
    from analytics_preditivos import analytics_bp
    app.register_blueprint(analytics_bp)
    logger.info("[OK] Analytics Preditivos registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Analytics Preditivos: {e}", exc_info=True)

# Sistema de alertas avançados removido (código obsoleto limpo)

# Relatórios de produtividade removido (código obsoleto limpo)

# Registrar Dashboards Específicos
try:
    from dashboards_especificos import dashboards_bp
    app.register_blueprint(dashboards_bp)
    logger.info("[OK] Dashboards Específicos registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Dashboards Específicos: {e}", exc_info=True)

# Registrar Exportação de Relatórios
try:
    from exportacao_relatorios import exportacao_bp
    app.register_blueprint(exportacao_bp)
    logger.info("[OK] Exportação de Relatórios registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Exportação de Relatórios: {e}", exc_info=True)

# Registrar Relatórios Financeiros Avançados
try:
    from relatorios_financeiros_avancados import financeiros_bp
    app.register_blueprint(financeiros_bp)
    logger.info("[OK] Relatórios Financeiros Avançados registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Relatórios Financeiros: {e}", exc_info=True)

# Relatórios de uso detalhado removido (código obsoleto limpo)

# Alimentação CRUD já registrado em app.py - removendo duplicação

try:
    from portal_obras_views import portal_obras_bp
    app.register_blueprint(portal_obras_bp)
    logger.info("[OK] Portal do Cliente por Obra registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Portal Obras: {e}", exc_info=True)

try:
    from medicao_views import medicao_bp
    app.register_blueprint(medicao_bp)
    logger.info("[OK] Blueprint MEDICAO QUINZENAL registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Medicao: {e}", exc_info=True)

logger.info("[READY] SISTEMA INICIADO - Todos os blueprints críticos foram carregados")

try:
    from importacao_views import importacao_bp
    app.register_blueprint(importacao_bp)
    logger.info("[OK] Blueprint IMPORTACAO FUNCIONARIOS registrado")
except Exception as e:
    import sys
    logger.exception("[ERROR] Erro ao registrar Importação Funcionários")
    # Tornar a falha visível no boot (não fica apenas em log silencioso).
    # O menu "Importar por Planilha" será ocultado automaticamente quando
    # o blueprint 'importacao' não estiver disponível (ver base_completo.html).
    print(
        f"[BOOT ERROR] Blueprint 'importacao' NAO foi registrado: {e}. "
        "A tela /importacao/ ficara indisponivel ate que o erro seja corrigido.",
        file=sys.stderr,
        flush=True,
    )

from app import csrf
main_py_exempt_blueprints = [
    'rdo_editar', 'rdo_crud', 'cadastrar_servico',
    'analytics_preditivos', 'dashboards_especificos',
    'exportacao_relatorios', 'relatorios_financeiros',
    'api_funcionarios', 'api_buscar_funcionarios', 'health',
]
for bp_name in main_py_exempt_blueprints:
    bp = app.blueprints.get(bp_name)
    if bp:
        csrf.exempt(bp)
        logger.info(f"[OK] CSRF exempt: {bp_name}")

try:
    from portal_obras_views import portal_obra, aprovar_compra, recusar_compra, upload_comprovante, aprovar_mapa_concorrencia, portal_rdo_detalhe, selecionar_mapa_v2
    csrf.exempt(portal_obra)
    csrf.exempt(aprovar_compra)
    csrf.exempt(recusar_compra)
    csrf.exempt(upload_comprovante)
    csrf.exempt(aprovar_mapa_concorrencia)
    csrf.exempt(portal_rdo_detalhe)
    csrf.exempt(selecionar_mapa_v2)
    logger.info("[OK] CSRF exempt: portal_obras (public routes only)")
except Exception as e:
    logger.error(f"[WARN] CSRF exempt portal_obras routes: {e}", exc_info=True)

try:
    from medicao_views import portal_pdf_extrato
    csrf.exempt(portal_pdf_extrato)
    logger.info("[OK] CSRF exempt: medicao portal_pdf_extrato (public)")
except Exception as e:
    logger.error(f"[WARN] CSRF exempt medicao portal: {e}", exc_info=True)


try:
    from custos_escritorio_views import custos_escritorio_bp
    app.register_blueprint(custos_escritorio_bp)
    logger.info("[OK] Blueprint custos_escritorio registrado")
except ImportError as e:
    logger.warning(f"[WARN] custos_escritorio não encontrado: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Falha ao registrar custos_escritorio: {e}", exc_info=True)

try:
    from views.catalogos_views import catalogos_bp
    app.register_blueprint(catalogos_bp)
    logger.info("[OK] Blueprint catalogos registrado")
except ImportError as e:
    logger.warning(f"[WARN] catalogos não encontrado: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Falha ao registrar catalogos: {e}", exc_info=True)

try:
    from views.cronograma_importacao import cronograma_importacao_bp
    app.register_blueprint(cronograma_importacao_bp)
    # Endpoint de API JSON/multipart (upload via fetch/XHR), como os demais
    # blueprints de API do app — dispensa CSRF de formulário. Exempt aqui e
    # não na lista acima porque aquele loop já rodou antes deste registro.
    csrf.exempt(cronograma_importacao_bp)
    logger.info("[OK] Blueprint cronograma_importacao registrado (CSRF exempt)")
except ImportError as e:
    logger.warning(f"[WARN] cronograma_importacao não encontrado: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Falha ao registrar cronograma_importacao: {e}", exc_info=True)

try:
    from views.quick_create_views import quick_create_bp
    app.register_blueprint(quick_create_bp)
    logger.info("[OK] Blueprint quick_create registrado")
except ImportError as e:
    logger.warning(f"[WARN] quick_create não encontrado: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Falha ao registrar quick_create: {e}", exc_info=True)

try:
    from cadastros_views import cadastros_hub_bp
    app.register_blueprint(cadastros_hub_bp)
    logger.info("[OK] Blueprint cadastros_hub registrado")
except ImportError as e:
    logger.warning(f"[WARN] cadastros_hub não encontrado: {e}", exc_info=True)
except Exception as e:
    logger.error(f"[ERROR] Falha ao registrar cadastros_hub: {e}", exc_info=True)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
