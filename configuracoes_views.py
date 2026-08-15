"""
Blueprint para configurações da empresa
"""
from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import login_required, current_user
from app import db
from models import (
    ConfiguracaoEmpresa, Departamento, Funcao, HorarioTrabalho, HorarioDia,
    Funcionario, EngenheiroResponsavel,
)
from decorators import admin_required
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

configuracoes_bp = Blueprint('configuracoes', __name__, url_prefix='/configuracoes')

@configuracoes_bp.route('/')
@login_required
@admin_required
def configuracoes():
    """Página principal de configurações da empresa"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    return render_template('configuracoes/index.html', config=config)

@configuracoes_bp.route('/empresa')
@login_required
@admin_required
def empresa():
    """Configurações da empresa"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    
    logger.debug(f"DEBUG EMPRESA: user.id={current_user.id}, admin_id={admin_id}")
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    logger.debug(f"DEBUG EMPRESA: config encontrada={config is not None}")
    if config:
        logger.debug(f"DEBUG EMPRESA: nome_empresa={config.nome_empresa}")

    # Task #173 — engenheiros disponíveis para escolha como padrão
    from services.engenheiro_service import listar_engenheiros_ativos
    engenheiros = listar_engenheiros_ativos(admin_id)

    return render_template(
        'configuracoes/empresa.html',
        config=config,
        engenheiros=engenheiros,
    )

@configuracoes_bp.route('/empresa/salvar', methods=['POST'])
@login_required
@admin_required
def salvar_empresa():
    """Salva configurações da empresa"""
    try:
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
            
        logger.debug(f"DEBUG SALVAR: user.id={current_user.id}, admin_id={admin_id}, tipo={getattr(current_user, 'tipo_usuario', 'N/A')}")
        
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        logger.debug(f"DEBUG SALVAR: config existente = {config is not None}")
        
        if not config:
            config = ConfiguracaoEmpresa()
            config.admin_id = admin_id
        
        config.nome_empresa = request.form.get('nome_empresa')
        config.cnpj = request.form.get('cnpj')
        config.endereco = request.form.get('endereco')
        config.telefone = request.form.get('telefone')
        config.email = request.form.get('email')
        config.website = request.form.get('website')
        
        logo_base64 = request.form.get('logo_base64')
        if logo_base64 and logo_base64.strip():
            config.logo_base64 = logo_base64
            logger.debug("DEBUG LOGO: Logo base64 salva")
        elif request.form.get('clear_logo') == 'true':
            config.logo_base64 = None
            logger.debug("DEBUG LOGO: Logo base64 removida")
            
        logo_pdf_base64 = request.form.get('logo_pdf_base64')
        if logo_pdf_base64 and logo_pdf_base64.strip():
            config.logo_pdf_base64 = logo_pdf_base64
            logger.debug("DEBUG LOGO PDF: Logo PDF base64 salva")
        elif request.form.get('clear_logo_pdf') == 'true':
            config.logo_pdf_base64 = None
            logger.debug("DEBUG LOGO PDF: Logo PDF base64 removida")
            
        header_pdf_base64 = request.form.get('header_pdf_base64', '').strip()
        clear_header = request.form.get('clear_header_pdf', '').strip()
        
        logger.debug(f"DEBUG HEADER: Campo header_pdf_base64 = {len(header_pdf_base64) if header_pdf_base64 else 0} chars")
        logger.debug(f"DEBUG HEADER: Campo clear_header_pdf = '{clear_header}'")
        logger.debug(f"DEBUG HEADER: Todos os campos do form: {list(request.form.keys())}")
        
        if clear_header == 'true':
            config.header_pdf_base64 = None
            logger.debug("DEBUG HEADER: [OK] Header PDF removido com sucesso")
        elif header_pdf_base64 and len(header_pdf_base64) > 100:
            config.header_pdf_base64 = header_pdf_base64
            logger.debug(f"DEBUG HEADER: [OK] Header PDF salvo com sucesso ({len(header_pdf_base64)} chars)")
        else:
            logger.warning(f"DEBUG HEADER: [WARN] Nenhuma ação realizada (header vazio ou inválido)")
        
        cor_primaria = request.form.get('cor_primaria', '#007bff')
        cor_secundaria = request.form.get('cor_secundaria', '#6c757d') 
        cor_fundo = request.form.get('cor_fundo_proposta', '#f8f9fa')
        logo_tamanho = request.form.get('logo_tamanho_portal', 'medio')

        # Task #191: cor_primaria/cor_secundaria são compartilhadas com o tema
        # do sistema. Se mudaram aqui (form de PDF), invalida o tema_preset
        # para evitar drift entre o que o admin vê marcado em "Tema do Sistema"
        # e as cores efetivamente em uso.
        if (config.cor_primaria != cor_primaria
                or config.cor_secundaria != cor_secundaria):
            config.tema_preset = 'custom'

        config.cor_primaria = cor_primaria
        config.cor_secundaria = cor_secundaria
        config.cor_fundo_proposta = cor_fundo
        config.logo_tamanho_portal = logo_tamanho
        
        logger.debug(f"DEBUG CORES: primaria={cor_primaria}, secundaria={cor_secundaria}, fundo={cor_fundo}, logo_tamanho={logo_tamanho}")
        
        config.itens_inclusos_padrao = request.form.get('itens_inclusos_padrao')
        config.itens_exclusos_padrao = request.form.get('itens_exclusos_padrao')
        config.condicoes_padrao = request.form.get('condicoes_padrao')
        config.condicoes_pagamento_padrao = request.form.get('condicoes_pagamento_padrao')
        config.garantias_padrao = request.form.get('garantias_padrao')
        config.observacoes_gerais_padrao = request.form.get('observacoes_gerais_padrao')
        
        # Bloco de assinatura (Task #158). Os campos legados engenheiro_*
        # foram removidos em Task #178 — agora a única fonte é a FK
        # `engenheiro_padrao_id` resolvida pelo cadastro de engenheiros.
        config.assinatura_nome = (request.form.get('assinatura_nome') or '').strip()
        config.assinatura_cargo = (request.form.get('assinatura_cargo') or '').strip()

        # Task #173 — engenheiro responsável padrão (FK)
        eng_padrao_raw = (request.form.get('engenheiro_padrao_id') or '').strip()
        if eng_padrao_raw:
            try:
                eng_padrao_id = int(eng_padrao_raw)
                # Valida que o engenheiro pertence ao tenant
                eng = EngenheiroResponsavel.query.filter_by(
                    id=eng_padrao_id, admin_id=admin_id
                ).first()
                config.engenheiro_padrao_id = eng.id if eng else None
            except (TypeError, ValueError):
                config.engenheiro_padrao_id = None
        else:
            config.engenheiro_padrao_id = None

        config.prazo_entrega_padrao = int(request.form.get('prazo_entrega_padrao', 90))
        config.validade_padrao = int(request.form.get('validade_padrao', 7))
        config.percentual_nota_fiscal_padrao = float(request.form.get('percentual_nota_fiscal_padrao', 13.5))

        # Bloco 3 — BDI completo (padrão TCU). Validação: percentuais ≥ 0.
        def _pct_nao_neg(campo, default):
            valor = float(request.form.get(campo, default) or default)
            return max(0.0, valor)

        config.bdi_ac_pct = _pct_nao_neg('bdi_ac_pct', 0)
        config.bdi_seguro_pct = _pct_nao_neg('bdi_seguro_pct', 0)
        config.bdi_risco_pct = _pct_nao_neg('bdi_risco_pct', 0)
        config.bdi_garantia_pct = _pct_nao_neg('bdi_garantia_pct', 0)
        config.bdi_desp_financeiras_pct = _pct_nao_neg('bdi_desp_financeiras_pct', 0)
        config.bdi_tl_aviso_pct = _pct_nao_neg('bdi_tl_aviso_pct', 60)
        config.bdi_tl_bloqueio_pct = _pct_nao_neg('bdi_tl_bloqueio_pct', 90)

        config.atualizado_em = datetime.utcnow()
        
        logger.debug(f"DEBUG: Salvando config para admin_id {admin_id}")
        config = db.session.merge(config)
        db.session.commit()
        logger.debug("DEBUG: Commit realizado com sucesso")
        flash('Configurações da empresa salvas com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'error')
    
    return redirect(url_for('configuracoes.empresa'))


# ---------------------------------------------------------------------------
# Task #191 — Tema do Sistema (preset + 4 cores customizadas)
# ---------------------------------------------------------------------------
@configuracoes_bp.route('/empresa/tema', methods=['POST'])
@login_required
@admin_required
def salvar_tema():
    """Salva o tema do sistema (preset + 4 cores) para a empresa logada.

    Contrato:
    - Se `tema_preset` for um preset válido (azul_profundo, verde_construcao,
      grafite_premium): aplica as 4 cores do preset, ignorando os campos de
      cor enviados.
    - Caso contrário (preset ausente, vazio ou == 'custom'): persiste as
      cores hex enviadas. Cores inválidas são silenciosamente ignoradas
      (mantém o valor anterior). Marca `tema_preset = 'custom'`.
    """
    from multitenant_helper import get_admin_id
    from services.tema_service import PRESETS, aplicar_preset, is_hex_color

    admin_id = get_admin_id()
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()

    if not config:
        config = ConfiguracaoEmpresa()
        config.admin_id = admin_id
        config.nome_empresa = getattr(current_user, 'username', None) or 'SIGE'

    try:
        preset_id = (request.form.get('tema_preset') or '').strip()

        if preset_id in PRESETS:
            # Preset válido → aplica as 4 cores do preset SEMPRE, ignorando
            # quaisquer cores customizadas vindas no mesmo POST.
            aplicar_preset(config, preset_id)
        else:
            # Modo customizado: persiste apenas cores hex válidas.
            cor_prim   = (request.form.get('cor_primaria') or '').strip()
            cor_sec    = (request.form.get('cor_secundaria') or '').strip()
            cor_header = (request.form.get('cor_header_nav') or '').strip()
            cor_fundo  = (request.form.get('cor_fundo_app') or '').strip()

            if is_hex_color(cor_prim):
                config.cor_primaria = cor_prim.lower()
            if is_hex_color(cor_sec):
                config.cor_secundaria = cor_sec.lower()
            if is_hex_color(cor_header):
                config.cor_header_nav = cor_header.lower()
            if is_hex_color(cor_fundo):
                config.cor_fundo_app = cor_fundo.lower()
            config.tema_preset = 'custom'

        config.atualizado_em = datetime.utcnow()
        config = db.session.merge(config)
        db.session.commit()
        flash('Tema do sistema atualizado com sucesso!', 'success')
        logger.info(
            f"Tema salvo (admin_id={admin_id}, preset={config.tema_preset}, "
            f"cores=[prim={config.cor_primaria}, header={config.cor_header_nav}])"
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar tema: {str(e)}', 'error')
        logger.exception("Erro ao salvar tema do sistema")

    return redirect(url_for('configuracoes.empresa') + '#tema-sistema')


# ---------------------------------------------------------------------------
# Timbre dos PDFs — importar/exportar o JSON de identidade (migration 286)
# ---------------------------------------------------------------------------

@configuracoes_bp.route('/empresa/timbre/exportar.json')
@login_required
@admin_required
def exportar_timbre():
    """Baixa o timbre EFETIVO do tenant no formato do arquivo de import.

    Serve a dois usos: ponto de partida para editar (vem com todas as chaves
    preenchidas, com os padrões do kit onde o tenant não configurou nada) e
    backup antes de trocar de identidade.

    `?sem_logo=1` produz um arquivo leve — a logo em base64 é o que faz o JSON
    passar de 100 KB, e para versionar ou mandar por e-mail ela costuma
    atrapalhar.
    """
    import io
    import json

    from flask import send_file

    from multitenant_helper import get_admin_id
    from services.timbre_pdf import exportar

    admin_id = get_admin_id()
    sem_logo = str(request.args.get('sem_logo') or '').strip() in ('1', 'true')
    timbre = exportar(admin_id, com_logo=not sem_logo)
    conteudo = json.dumps(timbre, ensure_ascii=False, indent=2)
    buf = io.BytesIO(conteudo.encode('utf-8'))
    return send_file(buf, as_attachment=True,
                     download_name='timbre-pdf.json',
                     mimetype='application/json')


@configuracoes_bp.route('/empresa/timbre/importar', methods=['POST'])
@login_required
@admin_required
def importar_timbre():
    """Importa o JSON de timbre enviado no formulário da tela de Empresa.

    O import é INCREMENTAL por chave: um arquivo só com `cores` não apaga a
    logo importada antes. Quem quiser zerar troca o valor explicitamente.

    Erros de validação voltam para a tela em `flash`, todos de uma vez — quem
    editou o arquivo à mão quer a lista completa, não um problema por
    tentativa.
    """
    from multitenant_helper import get_admin_id
    from services.timbre_pdf import TimbreInvalido, importar

    admin_id = get_admin_id()
    arquivo = request.files.get('timbre_json')
    if arquivo is None or not (arquivo.filename or '').strip():
        flash('Escolha um arquivo .json para importar.', 'warning')
        return redirect(url_for('configuracoes.empresa') + '#timbre-pdf')

    try:
        timbre = importar(admin_id, arquivo.read())
        db.session.commit()
    except TimbreInvalido as e:
        db.session.rollback()
        flash('O arquivo não foi aceito: ' + '; '.join(e.erros), 'error')
        return redirect(url_for('configuracoes.empresa') + '#timbre-pdf')
    except Exception as e:
        db.session.rollback()
        logger.exception('Erro ao importar timbre de PDF')
        flash(f'Erro ao importar o timbre: {e}', 'error')
        return redirect(url_for('configuracoes.empresa') + '#timbre-pdf')

    tem_logo = 'com logo' if timbre.get('logo_base64') else 'sem logo'
    flash(f'Timbre dos PDFs atualizado ({tem_logo}). '
          f'Gere um cronograma em PDF para conferir.', 'success')
    return redirect(url_for('configuracoes.empresa') + '#timbre-pdf')


@configuracoes_bp.route('/api/empresa')
@login_required
def api_empresa():
    """API para obter configurações da empresa"""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=current_user.admin_id).first()
    
    if not config:
        return jsonify({
            'success': False,
            'message': 'Configurações não encontradas'
        })
    
    return jsonify({
        'success': True,
        'config': config.to_dict()
    })


# ==================== DEPARTAMENTOS ====================

@configuracoes_bp.route('/departamentos')
@login_required
@admin_required
def departamentos():
    """Listar departamentos"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    departamentos = Departamento.query.filter_by(admin_id=admin_id).all()
    return render_template('configuracoes/departamentos.html', departamentos=departamentos)

@configuracoes_bp.route('/departamentos/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_departamento():
    """Criar departamento"""
    if request.method == 'POST':
        try:
            from multitenant_helper import get_admin_id
            admin_id = get_admin_id()
            dept = Departamento(
                nome=request.form['nome'],
                descricao=request.form.get('descricao'),
                admin_id=admin_id
            )
            db.session.add(dept)
            db.session.commit()
            flash('Departamento criado com sucesso!', 'success')
            return redirect(url_for('configuracoes.departamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar departamento: {str(e)}', 'danger')
    
    return render_template('configuracoes/departamento_form.html', departamento=None)

@configuracoes_bp.route('/departamentos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_departamento(id):
    """Editar departamento"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    dept = Departamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            dept.nome = request.form['nome']
            dept.descricao = request.form.get('descricao')
            db.session.commit()
            flash('Departamento atualizado com sucesso!', 'success')
            return redirect(url_for('configuracoes.departamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar departamento: {str(e)}', 'danger')
    
    return render_template('configuracoes/departamento_form.html', departamento=dept)

@configuracoes_bp.route('/departamentos/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_departamento(id):
    """Deletar departamento"""
    try:
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
        dept = Departamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        db.session.delete(dept)
        db.session.commit()
        flash('Departamento deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar departamento: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.departamentos'))


# ==================== FUNÇÕES ====================

@configuracoes_bp.route('/funcoes')
@login_required
@admin_required
def funcoes():
    """Listar funções"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    funcoes = Funcao.query.filter_by(admin_id=admin_id).all()
    return render_template('configuracoes/funcoes.html', funcoes=funcoes)

@configuracoes_bp.route('/funcoes/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_funcao():
    """Criar função"""
    from multitenant_helper import get_admin_id
    from models import Insumo
    admin_id = get_admin_id()
    if request.method == 'POST':
        try:
            # Task #62: insumo_id (tipo MAO_OBRA) opcional
            raw_insumo = request.form.get('insumo_id') or ''
            insumo_id = int(raw_insumo) if raw_insumo.strip() else None
            if insumo_id:
                ins = Insumo.query.filter_by(
                    id=insumo_id, admin_id=admin_id, tipo='MAO_OBRA'
                ).first()
                if not ins:
                    flash('Insumo selecionado é inválido ou não é do tipo MAO_OBRA.', 'warning')
                    insumo_id = None
            funcao = Funcao(
                nome=request.form['nome'],
                descricao=request.form.get('descricao'),
                salario_base=float(request.form.get('salario_base', 0)),
                admin_id=admin_id,
                insumo_id=insumo_id,
            )
            db.session.add(funcao)
            db.session.commit()
            flash('Função criada com sucesso!', 'success')
            return redirect(url_for('configuracoes.funcoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar função: {str(e)}', 'danger')

    insumos_mo = (
        Insumo.query
        .filter_by(admin_id=admin_id, tipo='MAO_OBRA', ativo=True)
        .order_by(Insumo.nome).all()
    )
    return render_template(
        'configuracoes/funcao_form.html',
        funcao=None, insumos_mo=insumos_mo,
    )

@configuracoes_bp.route('/funcoes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_funcao(id):
    """Editar função"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    funcao = Funcao.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Capturar salário base antigo para comparação
            salario_base_antigo = funcao.salario_base
            
            # Atualizar dados da função
            funcao.nome = request.form['nome']
            funcao.descricao = request.form.get('descricao')
            novo_salario_base = float(request.form.get('salario_base', 0))
            funcao.salario_base = novo_salario_base
            # Task #62: insumo_id (tipo MAO_OBRA)
            from models import Insumo as _Insumo
            if 'insumo_id' in request.form:
                raw_insumo = request.form.get('insumo_id') or ''
                novo_insumo_id = int(raw_insumo) if raw_insumo.strip() else None
                if novo_insumo_id:
                    ins = _Insumo.query.filter_by(
                        id=novo_insumo_id, admin_id=admin_id, tipo='MAO_OBRA'
                    ).first()
                    if ins:
                        funcao.insumo_id = ins.id
                    else:
                        flash('Insumo selecionado é inválido ou não é do tipo MAO_OBRA.', 'warning')
                        funcao.insumo_id = None
                else:
                    funcao.insumo_id = None
            
            # ATUALIZAÇÃO EM MASSA: Se salário base mudou, atualizar todos funcionários
            funcionarios_atualizados = 0
            if salario_base_antigo != novo_salario_base:
                # Buscar todos os funcionários com essa função (FILTRADO POR TENANT)
                from multitenant_helper import get_admin_id
                admin_id = get_admin_id()
                funcionarios = Funcionario.query.filter_by(
                    funcao_id=id, 
                    admin_id=admin_id
                ).all()
                
                # Atualizar salário de cada funcionário
                for funcionario in funcionarios:
                    funcionario.salario = novo_salario_base
                    funcionarios_atualizados += 1
                
                # Log da operação
                    logger.debug(f"ATUALIZAÇÃO MASSA SALARIAL: Função '{funcao.nome}' (ID {id})")
                    logger.debug(f" Salário base: R$ {salario_base_antigo:.2f} → R$ {novo_salario_base:.2f}")
                    logger.debug(f" Funcionários atualizados: {funcionarios_atualizados}")
            
            # Commit da transação (atômica - tudo ou nada)
            db.session.commit()
            
            # Mensagem de sucesso informativa
            if funcionarios_atualizados > 0:
                flash(f'Função atualizada com sucesso! {funcionarios_atualizados} funcionário(s) tiveram seus salários atualizados automaticamente.', 'success')
            else:
                flash('Função atualizada com sucesso!', 'success')
                
            return redirect(url_for('configuracoes.funcoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar função: {str(e)}', 'danger')
    
    from models import Insumo as _Insumo2
    insumos_mo = (
        _Insumo2.query
        .filter_by(admin_id=admin_id, tipo='MAO_OBRA', ativo=True)
        .order_by(_Insumo2.nome).all()
    )
    return render_template(
        'configuracoes/funcao_form.html', funcao=funcao, insumos_mo=insumos_mo,
    )

@configuracoes_bp.route('/funcoes/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_funcao(id):
    """Deletar função"""
    try:
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
        funcao = Funcao.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        db.session.delete(funcao)
        db.session.commit()
        flash('Função deletada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar função: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.funcoes'))


# ==================== HORÁRIOS ====================

@configuracoes_bp.route('/horarios')
@login_required
@admin_required
def horarios():
    """Listar horários de trabalho"""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    horarios = HorarioTrabalho.query.filter_by(admin_id=admin_id).all()
    return render_template('configuracoes/horarios.html', horarios=horarios)

@configuracoes_bp.route('/horarios/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_horario():
    """Criar horário de trabalho com horários flexíveis por dia"""
    if request.method == 'POST':
        try:
            from multitenant_helper import get_admin_id
            from decimal import Decimal
            admin_id = get_admin_id()
            
            horario = HorarioTrabalho(
                nome=request.form['nome'],
                admin_id=admin_id,
                ativo=True
            )
            db.session.add(horario)
            db.session.flush()
            
            DIAS_SEMANA = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
            
            for i, dia_nome in enumerate(DIAS_SEMANA):
                trabalha = request.form.get(f'{dia_nome}_trabalha') == 'on'
                
                entrada_str = request.form.get(f'{dia_nome}_entrada', '08:00')
                saida_str = request.form.get(f'{dia_nome}_saida', '17:00')
                pausa_str = request.form.get(f'{dia_nome}_pausa', '1.0')
                
                horario_dia = HorarioDia(
                    horario_id=horario.id,
                    dia_semana=i,
                    trabalha=trabalha,
                    entrada=datetime.strptime(entrada_str, '%H:%M').time() if trabalha and entrada_str else None,
                    saida=datetime.strptime(saida_str, '%H:%M').time() if trabalha and saida_str else None,
                    pausa_horas=Decimal(pausa_str) if trabalha else Decimal('1.0'),
                    admin_id=admin_id
                )
                db.session.add(horario_dia)
            
            db.session.commit()
            flash('Horário criado com sucesso!', 'success')
            return redirect(url_for('configuracoes.horarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar horário: {str(e)}', 'danger')
    
    return render_template('configuracoes/horarios.html', horarios=[], horario=None, modo='criar')

@configuracoes_bp.route('/horarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_horario(id):
    """Editar horário de trabalho com horários flexíveis por dia"""
    from multitenant_helper import get_admin_id
    from decimal import Decimal
    admin_id = get_admin_id()
    horario = HorarioTrabalho.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            horario.nome = request.form['nome']
            
            DIAS_SEMANA = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
            
            for i, dia_nome in enumerate(DIAS_SEMANA):
                trabalha = request.form.get(f'{dia_nome}_trabalha') == 'on'
                
                horario_dia = HorarioDia.query.filter_by(horario_id=horario.id, dia_semana=i).first()
                
                if not horario_dia:
                    horario_dia = HorarioDia(
                        horario_id=horario.id,
                        dia_semana=i,
                        admin_id=admin_id
                    )
                    db.session.add(horario_dia)
                
                entrada_str = request.form.get(f'{dia_nome}_entrada', '08:00')
                saida_str = request.form.get(f'{dia_nome}_saida', '17:00')
                pausa_str = request.form.get(f'{dia_nome}_pausa', '1.0')
                
                horario_dia.trabalha = trabalha
                horario_dia.entrada = datetime.strptime(entrada_str, '%H:%M').time() if trabalha and entrada_str else None
                horario_dia.saida = datetime.strptime(saida_str, '%H:%M').time() if trabalha and saida_str else None
                horario_dia.pausa_horas = Decimal(pausa_str) if trabalha else Decimal('1.0')
            
            db.session.commit()
            flash('Horário atualizado com sucesso!', 'success')
            return redirect(url_for('configuracoes.horarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar horário: {str(e)}', 'danger')
    
    horarios = HorarioTrabalho.query.filter_by(admin_id=admin_id).all()
    return render_template('configuracoes/horarios.html', horarios=horarios, horario=horario, modo='editar')

@configuracoes_bp.route('/horarios/deletar/<int:id>', methods=['POST'])
@login_required
@admin_required
def deletar_horario(id):
    """Deletar horário de trabalho"""
    try:
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
        horario = HorarioTrabalho.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        db.session.delete(horario)
        db.session.commit()
        flash('Horário deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar horário: {str(e)}', 'danger')
    
    return redirect(url_for('configuracoes.horarios'))

# ==================== ENGENHEIROS RESPONSÁVEIS (Task #173) ====================

def _form_to_engenheiro(eng, form, admin_id):
    """Aplica os campos do formulário ao objeto EngenheiroResponsavel."""
    eng.admin_id = admin_id
    eng.nome = (form.get('nome') or '').strip()
    eng.crea = (form.get('crea') or '').strip()
    eng.email = (form.get('email') or '').strip()
    eng.telefone = (form.get('telefone') or '').strip()
    eng.endereco = (form.get('endereco') or '').strip()
    eng.website = (form.get('website') or '').strip()
    eng.ativo = bool(form.get('ativo'))

    assinatura = (form.get('assinatura_base64') or '').strip()
    if assinatura:
        eng.assinatura_base64 = assinatura
    elif form.get('clear_assinatura') == 'true':
        eng.assinatura_base64 = ''


@configuracoes_bp.route('/engenheiros')
@login_required
@admin_required
def engenheiros():
    """Lista os engenheiros responsáveis cadastrados pelo tenant."""
    from multitenant_helper import get_admin_id
    from services.engenheiro_service import listar_engenheiros
    admin_id = get_admin_id()
    engs = listar_engenheiros(admin_id, incluir_inativos=True)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    padrao_id = config.engenheiro_padrao_id if config else None
    return render_template(
        'configuracoes/engenheiros.html',
        engenheiros=engs,
        engenheiro_padrao_id=padrao_id,
    )


@configuracoes_bp.route('/engenheiros/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_engenheiro():
    """Cria um novo engenheiro responsável."""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()

    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            if not nome:
                flash('Nome do engenheiro é obrigatório.', 'danger')
                return render_template(
                    'configuracoes/engenheiro_form.html',
                    engenheiro=None, modo='criar', form=request.form,
                )
            eng = EngenheiroResponsavel()
            _form_to_engenheiro(eng, request.form, admin_id)
            db.session.add(eng)
            db.session.commit()
            flash('Engenheiro responsável cadastrado com sucesso!', 'success')
            return redirect(url_for('configuracoes.engenheiros'))
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro ao criar engenheiro responsável")
            flash(f'Erro ao cadastrar engenheiro: {e}', 'danger')

    return render_template(
        'configuracoes/engenheiro_form.html',
        engenheiro=None, modo='criar', form=None,
    )


@configuracoes_bp.route('/engenheiros/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_engenheiro(id):
    """Edita um engenheiro responsável."""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    eng = EngenheiroResponsavel.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        try:
            nome = (request.form.get('nome') or '').strip()
            if not nome:
                flash('Nome do engenheiro é obrigatório.', 'danger')
                return render_template(
                    'configuracoes/engenheiro_form.html',
                    engenheiro=eng, modo='editar', form=request.form,
                )
            _form_to_engenheiro(eng, request.form, admin_id)
            # Se este engenheiro foi inativado e era o padrão da empresa,
            # limpa o vínculo (mesma regra de /engenheiros/inativar/<id>).
            if not eng.ativo:
                config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
                if config and config.engenheiro_padrao_id == eng.id:
                    config.engenheiro_padrao_id = None
            db.session.commit()
            flash('Engenheiro responsável atualizado com sucesso!', 'success')
            return redirect(url_for('configuracoes.engenheiros'))
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro ao editar engenheiro responsável")
            flash(f'Erro ao salvar engenheiro: {e}', 'danger')

    return render_template(
        'configuracoes/engenheiro_form.html',
        engenheiro=eng, modo='editar', form=None,
    )


@configuracoes_bp.route('/engenheiros/inativar/<int:id>', methods=['POST'])
@login_required
@admin_required
def inativar_engenheiro(id):
    """Inativa (soft-delete) um engenheiro responsável."""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    try:
        eng = EngenheiroResponsavel.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        eng.ativo = False
        # Se este era o padrão da empresa, remove o vínculo para evitar
        # que um engenheiro inativo continue aparecendo nas propostas.
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        if config and config.engenheiro_padrao_id == eng.id:
            config.engenheiro_padrao_id = None
        db.session.commit()
        flash('Engenheiro inativado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao inativar engenheiro responsável")
        flash(f'Erro ao inativar engenheiro: {e}', 'danger')

    return redirect(url_for('configuracoes.engenheiros'))


@configuracoes_bp.route('/engenheiros/reativar/<int:id>', methods=['POST'])
@login_required
@admin_required
def reativar_engenheiro(id):
    """Reativa um engenheiro previamente inativado."""
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    try:
        eng = EngenheiroResponsavel.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        eng.ativo = True
        db.session.commit()
        flash('Engenheiro reativado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao reativar engenheiro responsável")
        flash(f'Erro ao reativar engenheiro: {e}', 'danger')

    return redirect(url_for('configuracoes.engenheiros'))


# ==================== ALÇADAS DE COMPRA (A7 — fase 3 do ciclo) ====================
#
# 📖 spec docs/superpowers/specs/2026-08-15-alcadas-design.md, decisões D6 e D7.
#
# `FaixaAlcada` nunca teve CRUD: as faixas só existiam via migration 243 e
# UPDATE manual. O passo 1 do runbook manda conferir tetos, `minimo_cotacoes` e
# condições ativas ANTES de ligar a flag `alcadas_avancadas_ativa`, e é por
# aqui que sai o UPDATE da D6 (faixa de topo para 3 cotações).
#
# As regras NÃO moram nestas rotas nem no template: elas estão em
# `services/faixa_alcada_admin.py`, porque a tela é a primeira consumidora e
# não a única — o script de flag é a segunda e SQL manual continua possível.
# O que mora aqui é o que é da tela: quem entra (ADMIN), qual tenant
# (`get_admin_id`), o 404 do vizinho, o commit e o flash.

@configuracoes_bp.route('/alcadas')
@login_required
@admin_required
def alcadas():
    """A escada de faixas de alçada do tenant, com os campos editáveis."""
    from multitenant_helper import get_admin_id
    from services.alcada_compras import CONDICOES_CONHECIDAS, ROTULOS_CONDICAO
    from services.faixa_alcada_admin import diagnosticar, listar_faixas

    admin_id = get_admin_id()
    faixas = listar_faixas(admin_id)
    return render_template(
        'configuracoes/alcadas.html',
        faixas=faixas,
        # Os invariantes quebrados HOJE. A tela os mostra em vez de travar: o
        # invariante do teto aberto nunca teve constraint, então há tenant que
        # já chega aqui fora dele — e esta é a tela que o conserta.
        diagnostico=diagnosticar(admin_id),
        condicoes=[(c, ROTULOS_CONDICAO.get(c, c)) for c in CONDICOES_CONHECIDAS],
    )


@configuracoes_bp.route('/alcadas/<int:id>', methods=['POST'])
@login_required
@admin_required
def salvar_faixa_alcada(id):
    """Salva uma faixa. Faixa de outro tenant é **404**, não 403.

    404 porque 403 já é vazamento — confirmaria ao vizinho que aquele id
    existe e é de alguém. É a convenção da casa (`first_or_404` sempre
    filtrado por `admin_id`), e o isolamento entre empresas é o defeito mais
    caro deste repositório.
    """
    from multitenant_helper import get_admin_id
    from services.faixa_alcada_admin import (FaixaInvalida, faixa_do_tenant,
                                             ler_formulario, salvar_faixa)

    admin_id = get_admin_id()
    if faixa_do_tenant(admin_id, id) is None:
        abort(404)

    try:
        _, avisos = salvar_faixa(admin_id, id, ler_formulario(request.form))
        db.session.commit()
    except FaixaInvalida as e:
        db.session.rollback()
        flash('A faixa não foi salva: ' + '; '.join(e.erros), 'danger')
        return redirect(url_for('configuracoes.alcadas'))
    except Exception as e:
        db.session.rollback()
        logger.exception('Erro ao salvar faixa de alçada')
        flash(f'Erro ao salvar a faixa: {e}', 'danger')
        return redirect(url_for('configuracoes.alcadas'))

    flash('Faixa de alçada salva.', 'success')
    for aviso in avisos:
        # Violação que já existia antes desta edição. Salvou, mas o tenant
        # continua fora do invariante e quem está na tela precisa saber.
        flash(f'Atenção, a escada continua inconsistente: {aviso}', 'warning')
    return redirect(url_for('configuracoes.alcadas'))


@configuracoes_bp.route('/alcadas/nova', methods=['POST'])
@login_required
@admin_required
def criar_faixa_alcada():
    """Cria uma faixa nova. Mesmas validações da edição, mesmo serviço."""
    from multitenant_helper import get_admin_id
    from services.faixa_alcada_admin import (FaixaInvalida, ler_formulario,
                                             salvar_faixa)

    admin_id = get_admin_id()
    try:
        _, avisos = salvar_faixa(admin_id, None, ler_formulario(request.form))
        db.session.commit()
    except FaixaInvalida as e:
        db.session.rollback()
        flash('A faixa não foi criada: ' + '; '.join(e.erros), 'danger')
        return redirect(url_for('configuracoes.alcadas'))
    except Exception as e:
        db.session.rollback()
        logger.exception('Erro ao criar faixa de alçada')
        flash(f'Erro ao criar a faixa: {e}', 'danger')
        return redirect(url_for('configuracoes.alcadas'))

    flash('Faixa de alçada criada.', 'success')
    for aviso in avisos:
        flash(f'Atenção, a escada continua inconsistente: {aviso}', 'warning')
    return redirect(url_for('configuracoes.alcadas'))


@configuracoes_bp.route('/alcadas/semear', methods=['POST'])
@login_required
@admin_required
def semear_faixas_alcada():
    """Semeia as faixas recomendadas num tenant que não tem nenhuma.

    Tenant sem faixa não é tenant sem alçada: `faixa_para_valor` devolve a
    `_FaixaSeguranca` (2 aprovações, exige ADMIN), que é falha fechada e não
    aparece em tela nenhuma. Semear é o caminho para sair disso — e é um POST
    explícito, não um efeito colateral de abrir a página: escrever no banco
    porque alguém olhou uma tela é como um GET vira UPDATE sem que ninguém
    tenha pedido.
    """
    from multitenant_helper import get_admin_id
    from services.alcada_compras import garantir_faixas_do_tenant

    admin_id = get_admin_id()
    try:
        semeou = garantir_faixas_do_tenant(admin_id)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception('Erro ao semear faixas de alçada')
        flash(f'Erro ao semear as faixas: {e}', 'danger')
        return redirect(url_for('configuracoes.alcadas'))

    if semeou:
        flash('Faixas recomendadas criadas. Confira os tetos antes de usar.',
              'success')
    else:
        flash('Este tenant já tem faixas — nada foi criado.', 'info')
    return redirect(url_for('configuracoes.alcadas'))
