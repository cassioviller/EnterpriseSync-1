"""
Sistema de Edição de RDO - SIGE v8.0
Funcionalidade completa para editar RDOs existentes com todas as subatividades
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint para edição de RDO
rdo_editar_bp = Blueprint('rdo_editar', __name__, url_prefix='/rdo/editar')

@rdo_editar_bp.route('/<int:rdo_id>', methods=['GET'])
def editar_rdo_form(rdo_id):
    """
    Exibir formulário de edição para RDO específico
    """
    try:
        from models import RDO, Obra, RDOServicoSubatividade, SubatividadeMestre, Funcionario
        try:
            from utils.auth_utils import get_admin_id_from_user
        except ImportError:
            from bypass_auth import obter_admin_id as get_admin_id_from_user
        from app import db
        
        # Obter admin_id do usuário atual
        admin_id = get_admin_id_from_user()
        logger.info(f"🔧 EDITANDO RDO {rdo_id} - Admin ID: {admin_id}")
        
        # Buscar RDO existente
        rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
        if not rdo:
            flash('RDO não encontrado', 'error')
            return redirect(url_for('main.funcionario_rdo_consolidado'))
        
        # Buscar todas as obras do admin
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        # Buscar subatividades já preenchidas no RDO
        subatividades_rdo = RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).all()
        
        # Criar dicionário de subatividades com percentuais
        subatividades_data = {}
        for sub_rdo in subatividades_rdo:
            subatividades_data[sub_rdo.nome_subatividade] = sub_rdo.percentual_conclusao
        
        # Buscar dados completos da obra para carregar serviços
        obra_selecionada = rdo.obra_id
        
        logger.info(f"✅ RDO carregado: {rdo.numero_rdo}, Obra: {rdo.obra.nome}")
        logger.info(f"📊 Subatividades encontradas: {len(subatividades_rdo)}")
        
        return render_template('rdo/editar_rdo.html',
                             rdo=rdo,
                             obras=obras,
                             obra_selecionada=obra_selecionada,
                             subatividades_data=subatividades_data)
                             
    except Exception as e:
        logger.error(f"❌ Erro ao carregar RDO para edição: {e}")
        flash(f'Erro ao carregar RDO: {str(e)}', 'error')
        return redirect(url_for('main.funcionario_rdo_consolidado'))

@rdo_editar_bp.route('/<int:rdo_id>', methods=['POST'])
def salvar_edicao_rdo(rdo_id):
    """
    Salvar alterações no RDO editado
    """
    try:
        from models import RDO, RDOServicoSubatividade, SubatividadeMestre
        try:
            from utils.auth_utils import get_admin_id_from_user
        except ImportError:
            from bypass_auth import obter_admin_id as get_admin_id_from_user
        from app import db
        
        # Obter admin_id do usuário atual
        admin_id = get_admin_id_from_user()
        logger.info(f"💾 SALVANDO EDIÇÃO RDO {rdo_id} - Admin ID: {admin_id}")
        
        # Buscar RDO existente
        rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
        if not rdo:
            flash('RDO não encontrado', 'error')
            return redirect(url_for('main.funcionario_rdo_consolidado'))
        
        # Capturar dados do formulário
        obra_id = request.form.get('obra_id', type=int)
        data_relatorio = request.form.get('data_relatorio')
        clima = request.form.get('clima', '').strip()
        observacoes_gerais = request.form.get('observacoes_gerais', '').strip()
        observacoes_finais = request.form.get('observacoes_finais', '').strip()
        
        # Validar dados básicos
        if not obra_id or not data_relatorio:
            flash('Obra e data do relatório são obrigatórios', 'error')
            return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=rdo_id))
        
        # Converter data
        try:
            data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
        except ValueError:
            flash('Data inválida', 'error')
            return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=rdo_id))
        
        # Atualizar dados básicos do RDO
        rdo.obra_id = obra_id
        rdo.data_relatorio = data_relatorio
        rdo.clima_geral = clima
        rdo.observacoes_gerais = observacoes_gerais
        rdo.observacoes_finais = observacoes_finais
        
        # DEBUG: Verificar TODOS os dados do formulário
        logger.info(f"📋 TOTAL DE CAMPOS RECEBIDOS: {len(request.form)}")
        for campo, valor in request.form.items():
            logger.info(f"   └─ {campo}: {valor}")
        
        # Processar subatividades (campos do tipo 'subatividade_{id}')
        subatividades_processadas = {}
        for campo, valor in request.form.items():
            if campo.startswith('subatividade_'):
                try:
                    # Parse do campo: subatividade_{subatividade_mestre_id}
                    subatividade_id = int(campo.replace('subatividade_', ''))
                    percentual = float(valor) if valor else 0.0
                    
                    # Salvar TODOS os valores, incluindo 0 para rastreamento completo
                    subatividades_processadas[subatividade_id] = percentual
                        
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Erro ao processar campo {campo}: {e}")
                    continue
        
        logger.info(f"🔍 Subatividades processadas: {len(subatividades_processadas)}")
        for sub_id, percentual in subatividades_processadas.items():
            logger.info(f"  - Subatividade {sub_id}: {percentual}%")
        
        # Limpar subatividades existentes do RDO
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).delete()
        
        # Salvar novas subatividades
        subatividades_salvas = 0
        for subatividade_id, percentual in subatividades_processadas.items():
            try:
                # Buscar dados da subatividade mestre
                subatividade_mestre = SubatividadeMestre.query.filter_by(
                    id=subatividade_id,
                    admin_id=admin_id,
                    ativo=True
                ).first()
                
                if subatividade_mestre:
                    # Criar registro na tabela RDOServicoSubatividade
                    rdo_subatividade = RDOServicoSubatividade(
                        rdo_id=rdo_id,
                        servico_id=subatividade_mestre.servico_id,
                        nome_subatividade=subatividade_mestre.nome,
                        descricao_subatividade=subatividade_mestre.descricao,
                        percentual_conclusao=percentual,
                        observacoes_tecnicas=f'Editado em {percentual}% - {data_relatorio}',
                        admin_id=admin_id,
                        ativo=True
                    )
                    db.session.add(rdo_subatividade)
                    subatividades_salvas += 1
                    logger.info(f"✅ Subatividade editada: {subatividade_mestre.nome} - {percentual}%")
                else:
                    logger.warning(f"⚠️ Subatividade mestre {subatividade_id} não encontrada")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao salvar subatividade {subatividade_id}: {e}")
                continue
        
        logger.info(f"💾 Total de {subatividades_salvas} subatividades salvas na edição")
        
        # Confirmar salvamento
        db.session.commit()
        
        logger.info(f"✅ RDO editado com sucesso: {rdo.numero_rdo}")
        flash(f'RDO {rdo.numero_rdo} editado com sucesso!', 'success')
        
        return redirect(url_for('main.funcionario_rdo_consolidado'))
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar edição do RDO: {str(e)}")
        db.session.rollback()
        flash(f'Erro ao salvar edição: {str(e)}', 'error')
        return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=rdo_id))