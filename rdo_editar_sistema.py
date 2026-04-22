"""
Sistema de Edição de RDO - SIGE v8.0
Funcionalidade completa para editar RDOs existentes com todas as subatividades
"""

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprint para edição de RDO
rdo_editar_bp = Blueprint('rdo_editar', __name__, url_prefix='/rdo/editar')

@rdo_editar_bp.route('/<int:rdo_id>', methods=['GET'])
@login_required
def editar_rdo_form(rdo_id):
    """
    Exibir formulário de edição para RDO específico
    """
    try:
        from models import RDO, Obra, RDOServicoSubatividade, SubatividadeMestre, Funcionario, TipoUsuario
        try:
            from utils.auth_utils import get_admin_id_from_user
        except ImportError:
            def get_admin_id_from_user():
                if current_user.tipo_usuario == TipoUsuario.ADMIN:
                    return current_user.id
                elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                    return current_user.admin_id
                return None
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
        
        # Criar dicionário de subatividades com percentuais (legado)
        subatividades_data = {}
        for sub_rdo in subatividades_rdo:
            subatividades_data[sub_rdo.nome_subatividade] = sub_rdo.percentual_conclusao

        # Lista rica para renderização direta (V2 — evita dependência do API ServicoObraReal)
        subatividades_rdo_lista = []
        for sub_rdo in subatividades_rdo:
            mestre_id = getattr(sub_rdo, 'subatividade_mestre_id', None) or sub_rdo.id
            subatividades_rdo_lista.append({
                'id': mestre_id,
                'rdo_sub_id': sub_rdo.id,
                'nome': sub_rdo.nome_subatividade,
                'percentual_conclusao': float(sub_rdo.percentual_conclusao or 0),
                'subatividade_mestre_id': getattr(sub_rdo, 'subatividade_mestre_id', None),
                'quantidade_produzida': getattr(sub_rdo, 'quantidade_produzida', None),
                'meta_produtividade_snapshot': getattr(sub_rdo, 'meta_produtividade_snapshot', None),
                'unidade_medida_snapshot': getattr(sub_rdo, 'unidade_medida_snapshot', '') or '',
            })
        
        # Buscar funcionários já vinculados ao RDO
        from models import RDOMaoObra
        funcionarios_rdo = RDOMaoObra.query.filter_by(rdo_id=rdo_id).all()
        funcionarios_data = {}
        # Dict por subatividade: {sub_mestre_id_str: {func_id_str: horas}}
        funcionarios_vinculados_por_sub = {}
        for func_rdo in funcionarios_rdo:
            funcionarios_data[func_rdo.funcionario_id] = {
                'funcao': func_rdo.funcao_exercida,
                'horas': func_rdo.horas_trabalhadas
            }
            # Obter o sub_mestre_id associado a este registro de mão de obra
            if func_rdo.subatividade_id:
                sub_obj = RDOServicoSubatividade.query.get(func_rdo.subatividade_id)
                m_id = getattr(sub_obj, 'subatividade_mestre_id', None) if sub_obj else None
            else:
                m_id = None
            if m_id:
                key = str(m_id)
                if key not in funcionarios_vinculados_por_sub:
                    funcionarios_vinculados_por_sub[key] = {}
                funcionarios_vinculados_por_sub[key][str(func_rdo.funcionario_id)] = func_rdo.horas_trabalhadas
        
        # Buscar lista de todos os funcionários ativos do admin (para seleção por subatividade)
        from models import Funcionario
        funcionarios_todos_list = [
            {'id': f.id, 'nome': f.nome, 'cargo': f.funcao_ref.nome if f.funcao_ref else 'Operacional'}
            for f in Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        ]

        # Buscar dados completos da obra para carregar serviços
        obra_selecionada = rdo.obra_id
        
        logger.info(f"[OK] RDO carregado: {rdo.numero_rdo}, Obra: {rdo.obra.nome}")
        logger.info(f"[INFO] Subatividades encontradas: {len(subatividades_rdo)}")

        # V2: Buscar apontamentos de cronograma existentes
        apontamentos_cronograma = []
        try:
            from utils.tenant import is_v2_active
            if is_v2_active():
                from models import RDOApontamentoCronograma, TarefaCronograma
                from app import db as _db
                aps = RDOApontamentoCronograma.query.filter_by(
                    rdo_id=rdo_id, admin_id=admin_id
                ).all()
                for ap in aps:
                    t = TarefaCronograma.query.get(ap.tarefa_cronograma_id)
                    apontamentos_cronograma.append({
                        'tarefa_id': ap.tarefa_cronograma_id,
                        'nome_tarefa': t.nome_tarefa if t else '—',
                        'quantidade_executada_dia': float(ap.quantidade_executada_dia or 0),
                        'quantidade_acumulada': float(ap.quantidade_acumulada or 0),
                        'percentual_realizado': float(ap.percentual_realizado or 0),
                        'percentual_planejado': float(ap.percentual_planejado or 0),
                        'unidade_medida': (t.unidade_medida or '') if t else '',
                    })
        except Exception as e_v2:
            logger.warning(f"[WARN] Não foi possível carregar apontamentos V2 RDO {rdo_id}: {e_v2}")

        return render_template('rdo/editar_rdo.html',
                             rdo=rdo,
                             obras=obras,
                             obra_selecionada=obra_selecionada,
                             subatividades_data=subatividades_data,
                             subatividades_rdo_lista=subatividades_rdo_lista,
                             funcionarios_data=funcionarios_data,
                             funcionarios_todos_list=funcionarios_todos_list,
                             funcionarios_vinculados_por_sub=funcionarios_vinculados_por_sub,
                             apontamentos_cronograma=apontamentos_cronograma)

    except Exception as e:
        logger.error(f"[ERROR] Erro ao carregar RDO para edição: {e}")
        flash(f'Erro ao carregar RDO: {str(e)}', 'error')
        return redirect(url_for('main.funcionario_rdo_consolidado'))

@rdo_editar_bp.route('/<int:rdo_id>', methods=['POST'])
@login_required
def salvar_edicao_rdo(rdo_id):
    """
    Salvar alterações no RDO editado
    """
    try:
        from models import RDO, RDOServicoSubatividade, SubatividadeMestre, TipoUsuario
        try:
            from utils.auth_utils import get_admin_id_from_user
        except ImportError:
            def get_admin_id_from_user():
                if current_user.tipo_usuario == TipoUsuario.ADMIN:
                    return current_user.id
                elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                    return current_user.admin_id
                return None
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
        # RDO V2: campo único de observações; mantém compat com observacoes_finais legado
        observacoes_gerais = request.form.get('observacoes_gerais', '').strip()
        observacoes_finais = request.form.get('observacoes_finais', '').strip()
        observacoes_unificadas = observacoes_gerais or observacoes_finais
        
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
        # Persistir o conteúdo unificado na coluna real (`comentario_geral`)
        rdo.comentario_geral = observacoes_unificadas
        # Manter atributos legados em memória para compatibilidade com código a jusante
        rdo.observacoes_gerais = observacoes_unificadas
        rdo.observacoes_finais = observacoes_unificadas
        
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
        
        # Salvar referências das subatividades antigas ANTES de deletar (fallback para registros legados)
        old_subs = {s.id: s for s in RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).all()}

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
                    # Validação: apenas tipo='subatividade' pode ser lançado no RDO (grupos são estrutura)
                    tipo_sm = getattr(subatividade_mestre, 'tipo', 'subatividade')
                    if tipo_sm == 'grupo':
                        logger.warning(f"⚠️ SubatividadeMestre {subatividade_id} é do tipo 'grupo' — ignorada no RDO")
                        continue

                    # Caminho V2: subatividade do catálogo com snapshot de produtividade
                    qtd_raw = request.form.get(f'qtd_{subatividade_id}', '').strip()
                    qtd_produzida = float(qtd_raw) if qtd_raw else None
                    if qtd_produzida is not None and qtd_produzida < 0:
                        qtd_produzida = 0.0

                    rdo_subatividade = RDOServicoSubatividade(
                        rdo_id=rdo_id,
                        servico_id=subatividade_mestre.servico_id,
                        nome_subatividade=subatividade_mestre.nome,
                        descricao_subatividade=subatividade_mestre.descricao,
                        percentual_conclusao=percentual,
                        observacoes_tecnicas=f'Editado em {percentual}% - {data_relatorio}',
                        admin_id=admin_id,
                        ativo=True,
                        subatividade_mestre_id=subatividade_mestre.id,
                        meta_produtividade_snapshot=subatividade_mestre.meta_produtividade,
                        unidade_medida_snapshot=subatividade_mestre.unidade_medida,
                        quantidade_produzida=qtd_produzida,
                    )
                    db.session.add(rdo_subatividade)
                    subatividades_salvas += 1
                    logger.info(f"✅ Subatividade V2 editada: {subatividade_mestre.nome} - {percentual}% | qtd={qtd_produzida}")

                else:
                    # Caminho legado: reconstruir a partir do registro original salvo antes da deleção
                    old_sub = old_subs.get(subatividade_id)
                    if old_sub:
                        qtd_raw = request.form.get(f'qtd_{subatividade_id}', '').strip()
                        qtd_produzida = float(qtd_raw) if qtd_raw else getattr(old_sub, 'quantidade_produzida', None)
                        if qtd_produzida is not None and qtd_produzida < 0:
                            qtd_produzida = 0.0
                        rdo_subatividade = RDOServicoSubatividade(
                            rdo_id=rdo_id,
                            servico_id=old_sub.servico_id,
                            nome_subatividade=old_sub.nome_subatividade,
                            descricao_subatividade=old_sub.descricao_subatividade,
                            percentual_conclusao=percentual,
                            observacoes_tecnicas=f'Editado em {percentual}% - {data_relatorio}',
                            admin_id=admin_id,
                            ativo=True,
                            subatividade_mestre_id=getattr(old_sub, 'subatividade_mestre_id', None),
                            meta_produtividade_snapshot=getattr(old_sub, 'meta_produtividade_snapshot', None),
                            unidade_medida_snapshot=getattr(old_sub, 'unidade_medida_snapshot', None),
                            quantidade_produzida=qtd_produzida,
                        )
                        db.session.add(rdo_subatividade)
                        subatividades_salvas += 1
                        logger.info(f"✅ Subatividade legada preservada: {old_sub.nome_subatividade} - {percentual}%")
                    else:
                        logger.warning(f"⚠️ Subatividade {subatividade_id} não encontrada em mestre nem em registros antigos — ignorada")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao salvar subatividade {subatividade_id}: {e}")
                continue
        
        logger.info(f"💾 Total de {subatividades_salvas} subatividades salvas na edição")

        # Flush para obter IDs das novas subatividades (necessário antes de criar RDOMaoObra)
        db.session.flush()

        # Construir mapeamento: sub_mestre_id → RDOServicoSubatividade.id (recém-criado)
        sub_mestre_to_db_id = {}
        novos_subs = RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).all()
        for ns in novos_subs:
            m_id = getattr(ns, 'subatividade_mestre_id', None)
            if m_id:
                sub_mestre_to_db_id[m_id] = ns.id

        logger.info(f"🔗 Mapeamento sub_mestre→db_id: {sub_mestre_to_db_id}")
        
        # Processar funcionários selecionados
        funcionarios_selecionados = request.form.getlist('funcionarios_selecionados')
        logger.info(f"👥 Funcionários selecionados: {len(funcionarios_selecionados)}")
        
        # Limpar funcionários existentes do RDO
        from models import RDOMaoObra
        # Antes, remover os custos automáticos atrelados às linhas que vão sair.
        try:
            from services.rdo_custos import remover_custos_rdo
            remover_custos_rdo(rdo, admin_id)
        except Exception as _e:
            logger.warning(f"[rdo-custo] remover_custos_rdo falhou: {_e}")
        RDOMaoObra.query.filter_by(rdo_id=rdo_id).delete()
        
        import re as _re
        _sub_func_pattern = _re.compile(r'^sub_func_(\d+)_(\d+)_horas$')

        # Processar vínculos per-subatividade (sub_func_{sub_mestre_id}_{func_id}_horas)
        func_ids_vinculados = set()
        funcionarios_salvos = 0
        for campo, valor in request.form.items():
            m = _sub_func_pattern.match(campo)
            if m and valor:
                sub_mestre_id = int(m.group(1))
                func_id = int(m.group(2))
                horas_trabalhadas = float(valor) if valor else 0.0
                if horas_trabalhadas <= 0:
                    continue
                funcionario = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
                if funcionario:
                    sub_db_id = sub_mestre_to_db_id.get(sub_mestre_id)
                    funcao_exercida = request.form.get(f'funcao_{func_id}', 'Operacional')
                    rdo_funcionario = RDOMaoObra(
                        rdo_id=rdo_id,
                        funcionario_id=func_id,
                        funcao_exercida=funcao_exercida,
                        horas_trabalhadas=horas_trabalhadas,
                        admin_id=admin_id,
                        subatividade_id=sub_db_id,
                    )
                    db.session.add(rdo_funcionario)
                    func_ids_vinculados.add(func_id)
                    funcionarios_salvos += 1
                    logger.info(f"✅ Funcionário por subatividade: {funcionario.nome} → sub_mestre={sub_mestre_id} sub_db={sub_db_id} {horas_trabalhadas}h")

        # Processar funcionários sem vínculo de subatividade (campos horas_{func_id})
        for func_id in funcionarios_selecionados:
            try:
                func_id = int(func_id)
                if func_id in func_ids_vinculados:
                    continue  # já criado com vínculo de subatividade
                funcao_exercida = request.form.get(f'funcao_{func_id}', 'Operacional')
                horas_trabalhadas = max(0.0, float(request.form.get(f'horas_{func_id}', 8.0)))
                funcionario = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
                if funcionario:
                    rdo_funcionario = RDOMaoObra(
                        rdo_id=rdo_id,
                        funcionario_id=func_id,
                        funcao_exercida=funcao_exercida,
                        horas_trabalhadas=horas_trabalhadas,
                        admin_id=admin_id,
                    )
                    db.session.add(rdo_funcionario)
                    funcionarios_salvos += 1
                    logger.info(f"✅ Funcionário geral: {funcionario.nome} - {funcao_exercida} - {horas_trabalhadas}h")
                else:
                    logger.warning(f"⚠️ Funcionário {func_id} não encontrado ou não pertence ao admin")
            except Exception as e:
                logger.error(f"❌ Erro ao salvar funcionário {func_id}: {e}")
                continue
        
        logger.info(f"👥 Total de {funcionarios_salvos} funcionários salvos na edição")

        # Processar entregas / terceiros marcadas como concluidas no RDO
        try:
            from services.entregas_terceiros import aplicar_entregas_no_rdo
            qtd_ent, qtd_rev = aplicar_entregas_no_rdo(rdo, request.form, admin_id=getattr(rdo.obra, 'admin_id', None))
            if qtd_ent > 0 or qtd_rev > 0:
                logger.info(f"✅ entregas terceiros via salvar_edicao_rdo RDO {rdo.id}: marcadas={qtd_ent} revertidas={qtd_rev}")
        except Exception as e_ent:
            logger.error(f"Erro processando entregas terceiros (edicao): {e_ent}")

        # Confirmar salvamento
        db.session.commit()

        # Gera/atualiza custos de mão-de-obra desta edição (idempotente)
        try:
            from services.rdo_custos import gerar_custos_mao_obra_rdo
            gerar_custos_mao_obra_rdo(rdo, admin_id)
        except Exception as _e:
            logger.error(f"[rdo-custo] gerar_custos_mao_obra_rdo falhou: {_e}")

        logger.info(f"✅ RDO editado com sucesso: {rdo.numero_rdo}")
        flash(f'RDO {rdo.numero_rdo} editado com sucesso!', 'success')
        
        return redirect(url_for('main.funcionario_rdo_consolidado'))
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar edição do RDO: {str(e)}")
        db.session.rollback()
        error_message = str(e)
        
        # ✅ MENSAGEM DE ERRO DETALHADA
        if 'admin_id' in error_message and 'null' in error_message.lower():
            flash('Erro: Campo admin_id obrigatório não foi preenchido. Entre em contato com o suporte.', 'error')
        elif 'foreign key' in error_message.lower():
            flash('Erro: Referência inválida a obra ou funcionário. Verifique os dados selecionados.', 'error')
        elif 'unique constraint' in error_message.lower():
            flash('Erro: Este RDO já existe. Use um número diferente.', 'error')
        elif 'not-null constraint' in error_message.lower():
            # Extrair nome da coluna do erro
            import re
            match = re.search(r'column "(\w+)"', error_message)
            campo = match.group(1) if match else 'desconhecido'
            flash(f'Erro: O campo "{campo}" é obrigatório e não foi preenchido. Verifique os dados do formulário.', 'error')
        else:
            flash(f'Erro ao salvar edição: {error_message[:200]}', 'error')
        
        return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=rdo_id))

# API para buscar funcionários ativos
@rdo_editar_bp.route('/api/funcionarios-ativos')
@login_required
def api_funcionarios_ativos():
    """
    API para buscar funcionários ativos do admin atual
    """
    try:
        try:
            from utils.auth_utils import get_admin_id_from_user
        except ImportError:
            # bypass_auth removido - usar current_user diretamente
            from flask_login import current_user
            def get_admin_id_from_user():
                return getattr(current_user, 'admin_id', current_user.id)
        from models import Funcionario
        
        # Obter admin_id do usuário atual
        admin_id = get_admin_id_from_user()
        
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        # Formatar dados para o frontend
        funcionarios_data = []
        for func in funcionarios:
            funcionarios_data.append({
                'id': func.id,
                'nome': func.nome,
                'cargo': func.funcao_ref.nome if func.funcao_ref else 'Operacional',
                'departamento': func.departamento or 'Sem Departamento'
            })
        
        logger.info(f"📋 API Funcionários: {len(funcionarios_data)} funcionários ativos encontrados")
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_data,
            'total': len(funcionarios_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API de funcionários: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'funcionarios': []
        }), 500