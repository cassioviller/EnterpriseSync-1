# SISTEMA DE SALVAMENTO RDO SEM CONFLITO DE IDEMPOTÊNCIA
from flask import Blueprint, request, jsonify, redirect, url_for, flash
from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Obra, Funcionario
from bypass_auth import obter_admin_id, obter_usuario_atual
from datetime import datetime, date
import logging
import json
import time

rdo_sem_conflito_bp = Blueprint('rdo_sem_conflito', __name__)
logger = logging.getLogger(__name__)

def gerar_numero_rdo_sequencial(admin_id):
    """Gera número sequencial para RDO sem conflitos"""
    try:
        # Buscar último RDO do admin
        ultimo_rdo = RDO.query.join(Obra).filter(
            Obra.admin_id == admin_id
        ).order_by(RDO.id.desc()).first()
        
        if ultimo_rdo and ultimo_rdo.numero_rdo:
            try:
                # Extrair número do formato RDO-ADMIN-ANO-XXX
                partes = ultimo_rdo.numero_rdo.split('-')
                if len(partes) >= 4:
                    ultimo_numero = int(partes[-1])
                    proximo_numero = ultimo_numero + 1
                else:
                    proximo_numero = 1
            except (ValueError, IndexError):
                proximo_numero = 1
        else:
            proximo_numero = 1
        
        ano_atual = datetime.now().year
        numero_rdo = f"RDO-{admin_id}-{ano_atual}-{proximo_numero:03d}"
        
        logger.info(f"Número RDO gerado: {numero_rdo}")
        return numero_rdo
        
    except Exception as e:
        logger.error(f"Erro ao gerar número RDO: {e}")
        # Fallback com timestamp
        timestamp = int(time.time())
        return f"RDO-{admin_id}-{datetime.now().year}-{timestamp}"

@rdo_sem_conflito_bp.route('/salvar-rdo-flexivel', methods=['POST'])
def salvar_rdo_flexivel():
    """Salva RDO flexível sem verificar idempotência"""
    try:
        logger.info("🔄 Iniciando salvamento RDO flexível")
        
        # Obter dados básicos
        admin_id = obter_admin_id()
        usuario_id = obter_usuario_atual()
        
        # Dados básicos do formulário
        obra_id = request.form.get('obra_id', type=int)
        data_relatorio = request.form.get('data_relatorio')
        
        if not obra_id or not data_relatorio:
            flash('Obra e data são obrigatórios', 'error')
            return redirect(url_for('main.funcionario_rdo_novo'))
        
        # Converter data
        try:
            data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
        except ValueError:
            flash('Data inválida', 'error')
            return redirect(url_for('main.funcionario_rdo_novo'))
        
        # Verificar se obra existe e pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada', 'error')
            return redirect(url_for('main.funcionario_rdo_novo'))
        
        # Buscar funcionário ativo para criação
        funcionario = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).first()
        if not funcionario:
            # Criar funcionário padrão
            funcionario = Funcionario(
                nome="Administrador Sistema",
                email=f"admin{admin_id}@sistema.com",
                admin_id=admin_id,
                ativo=True,
                cargo="Administrador",
                departamento="Administração"
            )
            db.session.add(funcionario)
            db.session.flush()
        
        # Verificar se já existe RDO para esta obra/data
        rdo_existente = RDO.query.filter_by(
            obra_id=obra_id, 
            data_relatorio=data_relatorio
        ).first()
        
        if rdo_existente:
            # Atualizar RDO existente
            rdo = rdo_existente
            logger.info(f"Atualizando RDO existente: {rdo.numero_rdo}")
        else:
            # Criar novo RDO
            rdo = RDO()
            rdo.numero_rdo = gerar_numero_rdo_sequencial(admin_id)
            rdo.obra_id = obra_id
            rdo.data_relatorio = data_relatorio
            rdo.criado_por_id = funcionario.id
            rdo.admin_id = admin_id
            rdo.status = 'Rascunho'
            db.session.add(rdo)
            logger.info(f"Criando novo RDO: {rdo.numero_rdo}")
        
        # Dados climáticos
        rdo.clima_geral = request.form.get('clima_geral', '').strip()
        rdo.temperatura_media = request.form.get('temperatura_media', '').strip()
        rdo.umidade_relativa = request.form.get('umidade_relativa', type=int)
        rdo.vento_velocidade = request.form.get('vento_velocidade', '').strip()
        rdo.precipitacao = request.form.get('precipitacao', '').strip()
        rdo.condicoes_trabalho = request.form.get('condicoes_trabalho', '').strip()
        rdo.observacoes_climaticas = request.form.get('observacoes_climaticas', '').strip()
        rdo.comentario_geral = request.form.get('comentario_geral', '').strip()
        
        # Compatibilidade com campos legados
        rdo.tempo_manha = request.form.get('clima', '').strip()
        rdo.temperatura = request.form.get('temperatura', '').strip()
        rdo.condicoes_climaticas = request.form.get('condicoes_climaticas', '').strip()
        
        db.session.flush()  # Para obter ID do RDO
        
        # Processar funcionários selecionados
        funcionarios_selecionados = request.form.getlist('funcionarios_selecionados')
        if funcionarios_selecionados:
            # Limpar funcionários existentes se for atualização
            if rdo_existente:
                RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
            
            # Adicionar funcionários selecionados
            for func_id in funcionarios_selecionados:
                try:
                    func_id = int(func_id)
                    # Verificar se funcionário pertence ao admin
                    func = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
                    if func:
                        rdo_funcionario = RDOMaoObra(
                            rdo_id=rdo.id,
                            funcionario_id=func_id
                        )
                        db.session.add(rdo_funcionario)
                        logger.debug(f"Funcionário {func.nome} adicionado ao RDO")
                except (ValueError, TypeError):
                    continue
        
        # Processar subatividades recebidas do formulário
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
        
        # DEBUG: Verificar dados recebidos
        logger.info(f"🔍 Subatividades processadas: {len(subatividades_processadas)}")
        for sub_id, percentual in subatividades_processadas.items():
            logger.info(f"  - Subatividade {sub_id}: {percentual}%")
        
        # Salvar subatividades no RDOServicoSubatividade
        if rdo_existente:
            # Limpar subatividades existentes
            RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
        
        # Importar modelo SubatividadeMestre para buscar detalhes
        from models import SubatividadeMestre
        
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
                    # Criar registro na tabela RDOServicoSubatividade com campos corretos
                    rdo_subatividade = RDOServicoSubatividade(
                        rdo_id=rdo.id,
                        servico_id=subatividade_mestre.servico_id,
                        nome_subatividade=subatividade_mestre.nome,
                        descricao_subatividade=subatividade_mestre.descricao,
                        percentual_conclusao=percentual,
                        observacoes_tecnicas=f'Executado em {percentual}% - {data_relatorio}',
                        admin_id=admin_id,
                        ativo=True
                    )
                    db.session.add(rdo_subatividade)
                    subatividades_salvas += 1
                    logger.info(f"✅ Subatividade salva: {subatividade_mestre.nome} - {percentual}%")
                else:
                    logger.warning(f"⚠️ Subatividade mestre {subatividade_id} não encontrada")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao salvar subatividade {subatividade_id}: {e}")
                continue
        
        logger.info(f"💾 Total de {subatividades_salvas} subatividades salvas no RDO")
        
        # Confirmar salvamento
        db.session.commit()
        
        logger.info(f"✅ RDO salvo com sucesso: {rdo.numero_rdo}")
        flash(f'RDO {rdo.numero_rdo} salvo com sucesso!', 'success')
        
        return redirect(url_for('main.funcionario_rdo_consolidado'))
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar RDO: {str(e)}")
        db.session.rollback()
        flash(f'Erro ao salvar RDO: {str(e)}', 'error')
        return redirect(url_for('main.funcionario_rdo_novo'))