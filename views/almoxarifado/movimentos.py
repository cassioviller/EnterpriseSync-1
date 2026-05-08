<<<<<<< HEAD
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
import logging
from app import db
from models import (
    AlmoxarifadoItem,
    AlmoxarifadoEstoque,
    AlmoxarifadoMovimento,
    Funcionario,
    Obra,
    Fornecedor,
)
from event_manager import EventManager
from . import almoxarifado_bp, get_admin_id
=======
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import (AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
                    Funcionario, Obra, Fornecedor)
from datetime import datetime, timedelta
from sqlalchemy import func
from event_manager import EventManager
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

logger = logging.getLogger(__name__)


<<<<<<< HEAD
=======
# ========================================
# ENTRADA DE MATERIAIS
# ========================================

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/entrada', methods=['GET', 'POST'])
@login_required
def entrada():
    """Formulário de entrada de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by(Fornecedor.razao_social).all()
    
    return render_template('almoxarifado/entrada.html', itens=itens, fornecedores=fornecedores)

=======

    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by(Fornecedor.razao_social).all()

    return render_template('almoxarifado/entrada.html', itens=itens, fornecedores=fornecedores)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-entrada', methods=['POST'])
@login_required
def processar_entrada():
    """Processa entrada de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        item_id = request.form.get('item_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        nota_fiscal = request.form.get('nota_fiscal', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        valor_unitario = request.form.get('valor_unitario', type=float)
        fornecedor_id = request.form.get('fornecedor_id', type=int)
<<<<<<< HEAD
        
        # Validações básicas
        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
        if not valor_unitario or valor_unitario <= 0:
            flash('Valor unitário deve ser maior que zero', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
        
=======

        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.entrada'))

        if not valor_unitario or valor_unitario <= 0:
            flash('Valor unitário deve ser maior que zero', 'danger')
            return redirect(url_for('almoxarifado.entrada'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item:
            flash('Item não encontrado', 'danger')
            return redirect(url_for('almoxarifado.entrada'))
<<<<<<< HEAD
        
        # ✅ VALIDAÇÃO CRÍTICA DE SEGURANÇA: Se fornecedor_id fornecido, validar que pertence ao tenant
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if fornecedor_id:
            fornecedor = Fornecedor.query.filter_by(
                id=fornecedor_id,
                admin_id=admin_id
            ).first()
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if not fornecedor:
                logger.warning(f"⚠️ Tentativa de usar fornecedor {fornecedor_id} que não pertence ao tenant {admin_id}")
                flash('Fornecedor não encontrado ou sem permissão.', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
<<<<<<< HEAD
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Para SERIALIZADO: processar múltiplos números de série
=======

        if tipo_controle == 'SERIALIZADO':
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            numeros_serie = request.form.get('numeros_serie', '').strip()
            if not numeros_serie:
                flash('Números de série são obrigatórios para itens serializados', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
<<<<<<< HEAD
            
            # Split por vírgula ou quebra de linha
            series = [s.strip() for s in numeros_serie.replace('\n', ',').split(',') if s.strip()]
            
            if not series:
                flash('Nenhum número de série válido fornecido', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
            
            # Verificar duplicatas
=======

            series = [s.strip() for s in numeros_serie.replace('\n', ',').split(',') if s.strip()]

            if not series:
                flash('Nenhum número de série válido fornecido', 'danger')
                return redirect(url_for('almoxarifado.entrada'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            for serie in series:
                existe = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item_id,
                    numero_serie=serie,
                    admin_id=admin_id
                ).first()
                if existe:
                    flash(f'Número de série "{serie}" já cadastrado para este item', 'danger')
                    return redirect(url_for('almoxarifado.entrada'))
<<<<<<< HEAD
            
            # Criar 1 registro de estoque por série + 1 movimento por série
            movimentos_criados = 0
            movimentos_ids = []
            for serie in series:
                # Primeiro criar o movimento
=======

            movimentos_criados = 0
            movimentos_ids = []
            for serie in series:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='ENTRADA',
                    quantidade=1,
                    numero_serie=serie,
                    valor_unitario=valor_unitario,
                    nota_fiscal=nota_fiscal,
                    observacao=observacoes,
                    estoque_id=None,
                    fornecedor_id=fornecedor_id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=None
                )
                db.session.add(movimento)
<<<<<<< HEAD
                db.session.flush()  # Flush para obter movimento.id
                
                # Agora criar o estoque com rastreamento de lote
=======
                db.session.flush()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque = AlmoxarifadoEstoque(
                    item_id=item_id,
                    numero_serie=serie,
                    quantidade=1,
                    quantidade_inicial=1,
                    quantidade_disponivel=1,
                    entrada_movimento_id=movimento.id,
                    valor_unitario=valor_unitario,
                    status='DISPONIVEL',
                    admin_id=admin_id
                )
                db.session.add(estoque)
<<<<<<< HEAD
                
                movimentos_ids.append(movimento.id)
                movimentos_criados += 1
            
            db.session.commit()
            
            # EMITIR EVENTO para criar conta a pagar (se fornecedor existe)
=======

                movimentos_ids.append(movimento.id)
                movimentos_criados += 1

            db.session.commit()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if fornecedor_id:
                for mov_id in movimentos_ids:
                    EventManager.emit('material_entrada', {
                        'movimento_id': mov_id,
                        'item_id': item_id,
                        'fornecedor_id': fornecedor_id,
                    }, admin_id=admin_id)
<<<<<<< HEAD
            
            flash(f'Entrada processada com sucesso! {movimentos_criados} itens serializados cadastrados.', 'success')
        
=======

            flash(f'Entrada processada com sucesso! {movimentos_criados} itens serializados cadastrados.', 'success')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        else:  # CONSUMIVEL
            quantidade = request.form.get('quantidade', type=float)
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.entrada'))
<<<<<<< HEAD
            
            logger.debug(f'Processando entrada CONSUMIVEL - valor_unitario recebido: {valor_unitario}')
            
            # Primeiro criar o movimento
=======

            logger.debug(f'Processando entrada CONSUMIVEL - valor_unitario recebido: {valor_unitario}')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='ENTRADA',
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                nota_fiscal=nota_fiscal,
                observacao=observacoes,
<<<<<<< HEAD
                estoque_id=None,  # Será atualizado após criar estoque
=======
                estoque_id=None,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                fornecedor_id=fornecedor_id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=None
            )
            db.session.add(movimento)
<<<<<<< HEAD
            db.session.flush()  # Flush para obter movimento.id
            
            # Agora criar registro de estoque com rastreamento de lote FIFO
=======
            db.session.flush()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                quantidade_inicial=quantidade,
                quantidade_disponivel=quantidade,
                entrada_movimento_id=movimento.id,
                valor_unitario=valor_unitario,
                status='DISPONIVEL',
<<<<<<< HEAD
                lote=nota_fiscal,  # Usar nota fiscal como identificador de lote
=======
                lote=nota_fiscal,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                admin_id=admin_id
            )
            db.session.add(estoque)
            db.session.flush()
<<<<<<< HEAD
            
            # Atualizar movimento com estoque_id
            movimento.estoque_id = estoque.id
            
            db.session.commit()
            
            # EMITIR EVENTO para criar conta a pagar (se fornecedor existe)
=======

            movimento.estoque_id = estoque.id

            db.session.commit()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if fornecedor_id:
                EventManager.emit('material_entrada', {
                    'movimento_id': movimento.id,
                    'item_id': item_id,
                    'fornecedor_id': fornecedor_id,
                }, admin_id=admin_id)
<<<<<<< HEAD
            
            flash(f'Entrada processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" cadastrados.', 'success')
        
        return redirect(url_for('almoxarifado.entrada'))
        
=======

            flash(f'Entrada processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" cadastrados.', 'success')

        return redirect(url_for('almoxarifado.entrada'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar entrada: {str(e)}')
        flash('Erro ao processar entrada de material', 'danger')
        return redirect(url_for('almoxarifado.entrada'))

<<<<<<< HEAD
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-entrada-multipla', methods=['POST'])
@login_required
def processar_entrada_multipla():
    """Processa entrada de múltiplos materiais (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        nota_fiscal = data.get('nota_fiscal', '').strip()
        observacoes = data.get('observacoes', '').strip()
        fornecedor_id = data.get('fornecedor_id')
<<<<<<< HEAD
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ✅ VALIDAÇÃO CRÍTICA DE SEGURANÇA: Se fornecedor_id fornecido, validar que pertence ao tenant
=======

        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if fornecedor_id:
            fornecedor = Fornecedor.query.filter_by(
                id=fornecedor_id,
                admin_id=admin_id
            ).first()
<<<<<<< HEAD
            
            if not fornecedor:
                logger.warning(f"⚠️ Tentativa de usar fornecedor {fornecedor_id} que não pertence ao tenant {admin_id}")
                return jsonify({'success': False, 'message': 'Fornecedor não encontrado ou sem permissão'}), 403
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
=======

            if not fornecedor:
                logger.warning(f"⚠️ Tentativa de usar fornecedor {fornecedor_id} que não pertence ao tenant {admin_id}")
                return jsonify({'success': False, 'message': 'Fornecedor não encontrado ou sem permissão'}), 403

        erros = []
        itens_validados = []

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            valor_unitario = float(item_data.get('valor_unitario', 0))
<<<<<<< HEAD
            
            # Validar: item_id, tipo_controle e valor_unitario obrigatórios
            if not item_id or not tipo_controle:
                erros.append(f"Item {idx+1}: Dados incompletos")
                continue
            
            # Validar: valor unitário > 0
            if valor_unitario <= 0:
                erros.append(f"Item {idx+1}: Valor unitário deve ser maior que zero")
                continue
            
            # Verificar se item existe
=======

            if not item_id or not tipo_controle:
                erros.append(f"Item {idx+1}: Dados incompletos")
                continue

            if valor_unitario <= 0:
                erros.append(f"Item {idx+1}: Valor unitário deve ser maior que zero")
                continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                # Processar números de série
                numeros_serie = item_data.get('numeros_serie', '')
                series = [s.strip() for s in numeros_serie.split(',') if s.strip()]
                
                if not series:
                    erros.append(f"Item {idx+1} ({item.nome}): Números de série obrigatórios para itens serializados")
                    continue
                
                # Validar: verificar duplicatas nos números de série
=======

            if tipo_controle == 'SERIALIZADO':
                numeros_serie = item_data.get('numeros_serie', '')
                series = [s.strip() for s in numeros_serie.split(',') if s.strip()]

                if not series:
                    erros.append(f"Item {idx+1} ({item.nome}): Números de série obrigatórios para itens serializados")
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                for serie in series:
                    existe = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item_id,
                        numero_serie=serie,
                        admin_id=admin_id
                    ).first()
<<<<<<< HEAD
                    
                    if existe:
                        erros.append(f"Item {idx+1} ({item.nome}): Número de série '{serie}' já cadastrado")
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                    if existe:
                        erros.append(f"Item {idx+1} ({item.nome}): Número de série '{serie}' já cadastrado")

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'valor_unitario': valor_unitario,
                    'series': series
                })
<<<<<<< HEAD
                
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
<<<<<<< HEAD
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'valor_unitario': valor_unitario,
                    'quantidade': quantidade
                })
<<<<<<< HEAD
        
        # Se houver QUALQUER erro, abortar TUDO
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
<<<<<<< HEAD
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
=======

        total_processados = 0
        total_itens_esperados = len(itens_validados)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            valor_unitario = item_validado['valor_unitario']
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                series = item_validado['series']
                
                for serie in series:
                    # Primeiro criar o movimento
=======

            if tipo_controle == 'SERIALIZADO':
                series = item_validado['series']

                for serie in series:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    movimento = AlmoxarifadoMovimento(
                        item_id=item.id,
                        tipo_movimento='ENTRADA',
                        quantidade=1,
                        numero_serie=serie,
                        valor_unitario=valor_unitario,
                        nota_fiscal=nota_fiscal,
                        observacao=observacoes,
                        estoque_id=None,
                        fornecedor_id=fornecedor_id,
                        admin_id=admin_id,
                        usuario_id=current_user.id,
                        obra_id=None
                    )
                    db.session.add(movimento)
                    db.session.flush()
<<<<<<< HEAD
                    
                    # Agora criar estoque com rastreamento de lote
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    estoque = AlmoxarifadoEstoque(
                        item_id=item.id,
                        numero_serie=serie,
                        quantidade=1,
                        quantidade_inicial=1,
                        quantidade_disponivel=1,
                        entrada_movimento_id=movimento.id,
                        valor_unitario=valor_unitario,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    )
                    db.session.add(estoque)
<<<<<<< HEAD
                    
                    # Emitir evento se tem fornecedor
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    if fornecedor_id:
                        EventManager.emit('material_entrada', {
                            'movimento_id': movimento.id,
                            'item_id': item.id,
                            'fornecedor_id': fornecedor_id,
                        }, admin_id=admin_id)
<<<<<<< HEAD
                
                total_processados += 1
                
            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']
                
                # Primeiro criar o movimento
=======

                total_processados += 1

            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='ENTRADA',
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    nota_fiscal=nota_fiscal,
                    observacao=observacoes,
                    estoque_id=None,
                    fornecedor_id=fornecedor_id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=None
                )
                db.session.add(movimento)
                db.session.flush()
<<<<<<< HEAD
                
                # Agora criar estoque com rastreamento de lote FIFO
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque = AlmoxarifadoEstoque(
                    item_id=item.id,
                    quantidade=quantidade,
                    quantidade_inicial=quantidade,
                    quantidade_disponivel=quantidade,
                    entrada_movimento_id=movimento.id,
                    valor_unitario=valor_unitario,
                    status='DISPONIVEL',
                    lote=nota_fiscal,
                    admin_id=admin_id
                )
                db.session.add(estoque)
                db.session.flush()
<<<<<<< HEAD
                
                # Atualizar movimento com estoque_id
                movimento.estoque_id = estoque.id
                
                # Emitir evento se tem fornecedor
=======

                movimento.estoque_id = estoque.id

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                if fornecedor_id:
                    EventManager.emit('material_entrada', {
                        'movimento_id': movimento.id,
                        'item_id': item.id,
                        'fornecedor_id': fornecedor_id,
                    }, admin_id=admin_id)
<<<<<<< HEAD
                
                total_processados += 1
        
        # Commit APENAS se TODOS itens foram processados
=======

                total_processados += 1

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
<<<<<<< HEAD
        
        db.session.commit()
        
=======

        db.session.commit()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens processados com sucesso!',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar entrada múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

<<<<<<< HEAD
=======

# ========================================
# SAÍDA DE MATERIAIS
# ========================================

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/saida', methods=['GET'])
@login_required
def saida():
    """Formulário de saída de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    return render_template('almoxarifado/saida.html', 
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras)
=======

    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    return render_template('almoxarifado/saida.html',
                           itens=itens,
                           funcionarios=funcionarios,
                           obras=obras)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/processar-saida', methods=['POST'])
@login_required
def processar_saida():
    """Processa saída de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        item_id = request.form.get('item_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        funcionario_id = request.form.get('funcionario_id', type=int)
        obra_id = request.form.get('obra_id', type=int)
        observacoes = request.form.get('observacoes', '').strip()
<<<<<<< HEAD
        
        # Validações básicas
        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
=======

        if not item_id:
            flash('Item é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.saida'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item:
            flash('Item não encontrado', 'danger')
            return redirect(url_for('almoxarifado.saida'))
<<<<<<< HEAD
        
        # Funcionário é obrigatório
        if not funcionario_id:
            flash('Funcionário é obrigatório para saída', 'danger')
            return redirect(url_for('almoxarifado.saida'))
        
=======

        if not funcionario_id:
            flash('Funcionário é obrigatório para saída', 'danger')
            return redirect(url_for('almoxarifado.saida'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.saida'))
<<<<<<< HEAD
        
        # Obra é opcional
        obra = None
        if obra_id:
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Para SERIALIZADO: selecionar itens específicos
=======

        obra = None
        if obra_id:
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()

        if tipo_controle == 'SERIALIZADO':
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            estoque_ids = request.form.getlist('estoque_ids[]')
            if not estoque_ids:
                flash('Selecione ao menos um item para saída', 'danger')
                return redirect(url_for('almoxarifado.saida'))
<<<<<<< HEAD
            
            # Validar estoque e atualizar status
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            itens_processados = 0
            for estoque_id in estoque_ids:
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=int(estoque_id),
                    item_id=item_id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).first()
<<<<<<< HEAD
                
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                if not estoque:
                    db.session.rollback()
                    flash(f'Item de estoque ID {estoque_id} não está disponível', 'danger')
                    return redirect(url_for('almoxarifado.saida'))
<<<<<<< HEAD
                
                # Atualizar estoque
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque.status = 'EM_USO'
                estoque.funcionario_atual_id = funcionario_id
                estoque.obra_id = obra_id
                estoque.updated_at = datetime.utcnow()
<<<<<<< HEAD
                
                # Criar movimento
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='SAIDA',
                    quantidade=1,
                    numero_serie=estoque.numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                itens_processados += 1
<<<<<<< HEAD
            
            db.session.commit()
            flash(f'Saída processada com sucesso! {itens_processados} itens entregues para {funcionario.nome}.', 'success')
        
=======

            db.session.commit()
            flash(f'Saída processada com sucesso! {itens_processados} itens entregues para {funcionario.nome}.', 'success')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        else:  # CONSUMIVEL
            from decimal import Decimal
            quantidade_raw = request.form.get('quantidade', type=float)
            quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
            if not quantidade or quantidade <= 0:
                flash('Quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('almoxarifado.saida'))
<<<<<<< HEAD
            
            # Verificar quantidade disponível usando quantidade_disponivel (FIFO)
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            quantidade_disponivel_total = db.session.query(
                func.sum(AlmoxarifadoEstoque.quantidade_disponivel)
            ).filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
            ).scalar() or Decimal('0')
<<<<<<< HEAD
            
            logger.debug(f'Saída CONSUMIVEL - Quantidade solicitada: {quantidade}, Disponível: {quantidade_disponivel_total}')
            
            if quantidade > quantidade_disponivel_total:
                flash(f'Quantidade insuficiente! Disponível: {quantidade_disponivel_total} {item.unidade}', 'danger')
                return redirect(url_for('almoxarifado.saida'))
            
            # Implementar consumo FIFO pelos lotes mais antigos
=======

            logger.debug(f'Saída CONSUMIVEL - Quantidade solicitada: {quantidade}, Disponível: {quantidade_disponivel_total}')

            if quantidade > quantidade_disponivel_total:
                flash(f'Quantidade insuficiente! Disponível: {quantidade_disponivel_total} {item.unidade}', 'danger')
                return redirect(url_for('almoxarifado.saida'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            lotes = AlmoxarifadoEstoque.query.filter_by(
                item_id=item_id,
                status='DISPONIVEL',
                admin_id=admin_id
<<<<<<< HEAD
            ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()  # FIFO: mais antigos primeiro
            
            quantidade_restante = quantidade
            
            for lote in lotes:
                if quantidade_restante <= 0:
                    break
                
                # Usar quantidade_disponivel para rastreamento FIFO
                qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                
                if qtd_disponivel_lote <= 0:
                    continue  # Pular lotes já consumidos
                
                # Quantidade a consumir deste lote
=======
            ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()

            quantidade_restante = quantidade
            movimento = None

            for lote in lotes:
                if quantidade_restante <= 0:
                    break

                qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade

                if qtd_disponivel_lote <= 0:
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                if qtd_disponivel_lote >= quantidade_restante:
                    qtd_consumida = quantidade_restante
                    quantidade_restante = Decimal('0')
                else:
                    qtd_consumida = qtd_disponivel_lote
                    quantidade_restante -= qtd_disponivel_lote
<<<<<<< HEAD
                
                # Atualizar lote (FIFO tracking)
                lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                lote.quantidade = lote.quantidade_disponivel  # Manter sincronizado
                
                if lote.quantidade_disponivel == 0:
                    lote.status = 'CONSUMIDO'
                
                lote.updated_at = datetime.utcnow()
                
                # Criar movimento individual para este lote consumido
                # Isso permite rastrear o valor_unitario correto de cada lote
=======

                lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                lote.quantidade = lote.quantidade_disponivel

                if lote.quantidade_disponivel == 0:
                    lote.status = 'CONSUMIDO'

                lote.updated_at = datetime.utcnow()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item_id,
                    tipo_movimento='SAIDA',
                    quantidade=qtd_consumida,
<<<<<<< HEAD
                    valor_unitario=lote.valor_unitario,  # Valor do lote específico
=======
                    valor_unitario=lote.valor_unitario,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=lote.id,
                    lote=lote.lote,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
<<<<<<< HEAD
                
                logger.debug(f'Lote {lote.id} - Consumido: {qtd_consumida}, Restante no lote: {lote.quantidade_disponivel}, Valor unitário: {lote.valor_unitario}')
            
            db.session.commit()
            
            # 🔗 INTEGRAÇÃO AUTOMÁTICA - Emitir evento de material saída
            try:
                from event_manager import EventManager
                from decimal import Decimal
                # AlmoxarifadoItem não tem valor_unitario - enviar quantidade e item para cálculo posterior
                EventManager.emit('material_saida', {
                    'movimento_id': movimento.id,
=======

                logger.debug(f'Lote {lote.id} - Consumido: {qtd_consumida}, Restante no lote: {lote.quantidade_disponivel}, Valor unitário: {lote.valor_unitario}')

            db.session.commit()

            try:
                from decimal import Decimal as _Dec
                EventManager.emit('material_saida', {
                    'movimento_id': movimento.id if movimento else 0,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    'item_id': item_id,
                    'item_nome': item.nome,
                    'quantidade': float(quantidade),
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
<<<<<<< HEAD
                    'valor_total': 0  # Será calculado quando houver módulo de custos com preços
                }, admin_id)
            except Exception as e:
                logger.warning(f'Integração automática falhou (não crítico): {e}')
            
            flash(f'Saída processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" entregues para {funcionario.nome}.', 'success')
        
        return redirect(url_for('almoxarifado.saida'))
        
=======
                    'valor_total': 0
                }, admin_id)
            except Exception as e:
                logger.warning(f'Integração automática falhou (não crítico): {e}')

            flash(f'Saída processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" entregues para {funcionario.nome}.', 'success')

        return redirect(url_for('almoxarifado.saida'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar saída: {str(e)}')
        flash('Erro ao processar saída de material', 'danger')
        return redirect(url_for('almoxarifado.saida'))

<<<<<<< HEAD
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-saida-multipla', methods=['POST'])
@login_required
def processar_saida_multipla():
    """Processa saída de múltiplos itens (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        observacoes = data.get('observacoes', '').strip()
<<<<<<< HEAD
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
        # Validar que todos itens têm mesmo funcionário e obra
        funcionario_id = itens[0].get('funcionario_id')
        obra_id = itens[0].get('obra_id') or None
        
=======

        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400

        funcionario_id = itens[0].get('funcionario_id')
        obra_id = itens[0].get('obra_id') or None

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        for item_data in itens:
            if item_data.get('funcionario_id') != funcionario_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesmo funcionário'}), 400
            item_obra_id = item_data.get('obra_id') or None
            if item_obra_id != obra_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesma obra'}), 400
<<<<<<< HEAD
        
        # Validar que funcionário existe
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400
        
        # Validar cada item
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            
            # Verificar se item existe
=======

        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400

        erros = []
        itens_validados = []

        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')
                
                # VALIDAR: Série existe e está disponível?
=======

            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=estoque_id,
                    item_id=item_id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).first()
<<<<<<< HEAD
                
                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não disponível")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não disponível")
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'estoque_id': estoque_id,
                    'numero_serie': numero_serie,
                    'estoque': estoque
                })
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
                lote_allocations = item_data.get('lote_allocations', [])
<<<<<<< HEAD
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # VALIDAR alocações de lotes (se fornecidas)
                if lote_allocations:
                    # Validar que a soma das alocações = quantidade total
=======

                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue

                if lote_allocations:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    total_alocado = sum(Decimal(str(alloc.get('quantidade', 0))) for alloc in lote_allocations)
                    if abs(total_alocado - quantidade) >= Decimal('0.001'):
                        erros.append(f"Item {idx+1} ({item.nome}): Soma das alocações ({total_alocado}) diferente da quantidade total ({quantidade})")
                        continue
<<<<<<< HEAD
                    
                    # Validar cada alocação
                    for alloc_idx, alloc in enumerate(lote_allocations):
                        estoque_id = alloc.get('estoque_id')
                        qtd_alloc = Decimal(str(alloc.get('quantidade', 0)))
                        
                        if qtd_alloc <= 0:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Quantidade deve ser maior que zero")
                            continue
                        
                        # Verificar se o lote existe e pertence ao admin
                        lote_estoque = AlmoxarifadoEstoque.query.filter_by(
                            id=estoque_id,
=======

                    for alloc_idx, alloc in enumerate(lote_allocations):
                        alloc_estoque_id = alloc.get('estoque_id')
                        qtd_alloc = Decimal(str(alloc.get('quantidade', 0)))

                        if qtd_alloc <= 0:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Quantidade deve ser maior que zero")
                            continue

                        lote_estoque = AlmoxarifadoEstoque.query.filter_by(
                            id=alloc_estoque_id,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                            item_id=item_id,
                            status='DISPONIVEL',
                            admin_id=admin_id
                        ).first()
<<<<<<< HEAD
                        
                        if not lote_estoque:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Lote não encontrado ou não disponível")
                            continue
                        
                        # Verificar quantidade disponível
=======

                        if not lote_estoque:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Lote não encontrado ou não disponível")
                            continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                        qtd_disponivel = lote_estoque.quantidade_disponivel if lote_estoque.quantidade_disponivel else lote_estoque.quantidade
                        if qtd_alloc > qtd_disponivel:
                            erros.append(f"Item {idx+1} ({item.nome}), Lote {alloc_idx+1}: Quantidade solicitada ({qtd_alloc}) maior que disponível ({qtd_disponivel})")
                            continue
                else:
<<<<<<< HEAD
                    # Sem alocações manuais - validar estoque total apenas
=======
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    estoque_total = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade_disponivel)).filter_by(
                        item_id=item_id,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    ).scalar() or 0
<<<<<<< HEAD
                    
                    if estoque_total < quantidade:
                        erros.append(f"Item {idx+1} ({item.nome}): Estoque insuficiente (disponível: {estoque_total}, solicitado: {quantidade})")
                        continue
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                    if estoque_total < quantidade:
                        erros.append(f"Item {idx+1} ({item.nome}): Estoque insuficiente (disponível: {estoque_total}, solicitado: {quantidade})")
                        continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'quantidade': quantidade,
                    'lote_allocations': lote_allocations
                })
<<<<<<< HEAD
        
        # Se houver QUALQUER erro, abortar TUDO
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
<<<<<<< HEAD
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            
            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']
                
                # Atualizar estoque
=======

        total_processados = 0
        total_itens_esperados = len(itens_validados)

        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']

            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque.status = 'EM_USO'
                estoque.funcionario_atual_id = funcionario_id
                estoque.obra_id = obra_id
                estoque.updated_at = datetime.utcnow()
<<<<<<< HEAD
                
                # Criar movimento
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='SAIDA',
                    quantidade=1,
                    numero_serie=numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade = item_validado['quantidade']
                lote_allocations = item_validado.get('lote_allocations', [])
<<<<<<< HEAD
                
                # PROCESSAMENTO: Escolha Manual vs FIFO Automático
                if lote_allocations:
                    # ========================================
                    # MODO: SELEÇÃO MANUAL DE LOTES
                    # ========================================
                    for alloc in lote_allocations:
                        estoque_id = alloc.get('estoque_id')
                        qtd_consumida = Decimal(str(alloc.get('quantidade', 0)))
                        
                        # Buscar o lote específico
                        lote = AlmoxarifadoEstoque.query.filter_by(
                            id=estoque_id,
=======

                if lote_allocations:
                    for alloc in lote_allocations:
                        alloc_estoque_id = alloc.get('estoque_id')
                        qtd_consumida = Decimal(str(alloc.get('quantidade', 0)))

                        lote = AlmoxarifadoEstoque.query.filter_by(
                            id=alloc_estoque_id,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                            item_id=item.id,
                            status='DISPONIVEL',
                            admin_id=admin_id
                        ).first()
<<<<<<< HEAD
                        
                        if not lote:
                            continue  # Já validado anteriormente, não deve acontecer
                        
                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                        
                        # Atualizar lote
                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel
                        
                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'
                        
                        lote.updated_at = datetime.utcnow()
                        
                        # Criar movimento para este lote consumido
=======

                        if not lote:
                            continue

                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade

                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel

                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'

                        lote.updated_at = datetime.utcnow()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                        movimento = AlmoxarifadoMovimento(
                            item_id=item.id,
                            tipo_movimento='SAIDA',
                            quantidade=qtd_consumida,
                            valor_unitario=lote.valor_unitario,
                            funcionario_id=funcionario_id,
                            obra_id=obra_id,
                            observacao=observacoes,
                            estoque_id=lote.id,
                            lote=lote.lote,
                            admin_id=admin_id,
                            usuario_id=current_user.id
                        )
                        db.session.add(movimento)
                else:
<<<<<<< HEAD
                    # ========================================
                    # MODO: FIFO AUTOMÁTICO (LEGADO)
                    # ========================================
=======
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    lotes = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=admin_id
                    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()
<<<<<<< HEAD
                    
                    qtd_restante = quantidade
                    
                    for lote in lotes:
                        if qtd_restante <= 0:
                            break
                        
                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade
                        
                        if qtd_disponivel_lote <= 0:
                            continue
                        
=======

                    qtd_restante = quantidade

                    for lote in lotes:
                        if qtd_restante <= 0:
                            break

                        qtd_disponivel_lote = lote.quantidade_disponivel if lote.quantidade_disponivel else lote.quantidade

                        if qtd_disponivel_lote <= 0:
                            continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                        if qtd_disponivel_lote >= qtd_restante:
                            qtd_consumida = qtd_restante
                            qtd_restante = Decimal('0')
                        else:
                            qtd_consumida = qtd_disponivel_lote
                            qtd_restante -= qtd_disponivel_lote
<<<<<<< HEAD
                        
                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel
                        
                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'
                        
                        lote.updated_at = datetime.utcnow()
                        
=======

                        lote.quantidade_disponivel = qtd_disponivel_lote - qtd_consumida
                        lote.quantidade = lote.quantidade_disponivel

                        if lote.quantidade_disponivel == 0:
                            lote.status = 'CONSUMIDO'

                        lote.updated_at = datetime.utcnow()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                        movimento = AlmoxarifadoMovimento(
                            item_id=item.id,
                            tipo_movimento='SAIDA',
                            quantidade=qtd_consumida,
                            valor_unitario=lote.valor_unitario,
                            funcionario_id=funcionario_id,
                            obra_id=obra_id,
                            observacao=observacoes,
                            estoque_id=lote.id,
                            lote=lote.lote,
                            admin_id=admin_id,
                            usuario_id=current_user.id
                        )
                        db.session.add(movimento)
<<<<<<< HEAD
                
                total_processados += 1
        
        # Commit APENAS se TODOS itens foram processados
=======

                total_processados += 1

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
<<<<<<< HEAD
        
        db.session.commit()
        
        # 🔗 INTEGRAÇÃO AUTOMÁTICA - Emitir eventos para cada item processado
        try:
            from event_manager import EventManager
=======

        db.session.commit()

        try:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            for item_validado in itens_validados:
                item = item_validado['item']
                quantidade = item_validado.get('quantidade', 1)
                EventManager.emit('material_saida', {
<<<<<<< HEAD
                    'movimento_id': 0,  # ID não disponível aqui (múltiplos movimentos)
=======
                    'movimento_id': 0,
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    'item_id': item.id,
                    'item_nome': item.nome,
                    'quantidade': quantidade,
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
<<<<<<< HEAD
                    'valor_total': 0  # Será calculado quando houver módulo de custos com preços
                }, admin_id)
        except Exception as e:
            logger.warning(f'Integração automática falhou (não crítico): {e}')
        
=======
                    'valor_total': 0
                }, admin_id)
        except Exception as e:
            logger.warning(f'Integração automática falhou (não crítico): {e}')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens processados com sucesso! Entregues para {funcionario.nome}.',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar saída múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

<<<<<<< HEAD
=======

# ========================================
# DEVOLUÇÃO DE MATERIAIS
# ========================================

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/devolucao', methods=['GET'])
@login_required
def devolucao():
    """Formulário de devolução de materiais"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('almoxarifado/devolucao.html', funcionarios=funcionarios)

=======

    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()

    return render_template('almoxarifado/devolucao.html', funcionarios=funcionarios)


>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-devolucao', methods=['POST'])
@login_required
def processar_devolucao():
    """Processa devolução de materiais (SERIALIZADO ou CONSUMIVEL)"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        funcionario_id = request.form.get('funcionario_id', type=int)
        tipo_controle = request.form.get('tipo_controle')
        condicao_devolucao = request.form.get('condicao_devolucao', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
<<<<<<< HEAD
        
        # Validações
        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
=======

        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
        
        if not condicao_devolucao:
            flash('Condição do item é obrigatória', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        # LÓGICA SERIALIZADO vs CONSUMIVEL
        if tipo_controle == 'SERIALIZADO':
            # Devolução de itens serializados (múltipla seleção)
=======

        if not condicao_devolucao:
            flash('Condição do item é obrigatória', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))

        if tipo_controle == 'SERIALIZADO':
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            estoque_ids = request.form.getlist('estoque_ids[]')
            if not estoque_ids:
                flash('Selecione ao menos um item para devolução', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            itens_processados = 0
            for estoque_id in estoque_ids:
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=int(estoque_id),
                    funcionario_atual_id=funcionario_id,
                    status='EM_USO',
                    admin_id=admin_id
                ).first()
<<<<<<< HEAD
                
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                if not estoque:
                    db.session.rollback()
                    flash(f'Item de estoque ID {estoque_id} não está em uso por este funcionário', 'danger')
                    return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
                
                # Atualizar estoque
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque.status = 'DISPONIVEL'
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
                estoque.updated_at = datetime.utcnow()
<<<<<<< HEAD
                
                # Criar movimento de devolução
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=estoque.item_id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=1,
                    numero_serie=estoque.numero_serie,
                    funcionario_id=funcionario_id,
                    condicao_item=condicao_devolucao,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id,
                    obra_id=estoque.obra_id or 1
                )
                db.session.add(movimento)
                itens_processados += 1
<<<<<<< HEAD
            
            db.session.commit()
            flash(f'Devolução processada com sucesso! {itens_processados} itens devolvidos por {funcionario.nome}.', 'success')
        
        else:  # CONSUMIVEL
            item_id = request.form.get('item_id', type=int)
            quantidade = request.form.get('quantidade', type=float)
            
            if not item_id or not quantidade or quantidade <= 0:
                flash('Item e quantidade válida são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
            
=======

            db.session.commit()
            flash(f'Devolução processada com sucesso! {itens_processados} itens devolvidos por {funcionario.nome}.', 'success')

        else:  # CONSUMIVEL
            item_id = request.form.get('item_id', type=int)
            quantidade = request.form.get('quantidade', type=float)

            if not item_id or not quantidade or quantidade <= 0:
                flash('Item e quantidade válida são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item or not item.permite_devolucao:
                flash('Item não permite devolução', 'danger')
                return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
            
            # Criar novo registro de estoque com quantidade devolvida
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                status='DISPONIVEL',
                admin_id=admin_id
            )
            db.session.add(estoque)
            db.session.flush()
<<<<<<< HEAD
            
            # Criar movimento de devolução
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            movimento = AlmoxarifadoMovimento(
                item_id=item_id,
                tipo_movimento='DEVOLUCAO',
                quantidade=quantidade,
                funcionario_id=funcionario_id,
                condicao_item=condicao_devolucao,
                observacao=observacoes,
                estoque_id=estoque.id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=None
            )
            db.session.add(movimento)
<<<<<<< HEAD
            
            db.session.commit()
            flash(f'Devolução processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" devolvidos por {funcionario.nome}.', 'success')
        
        return redirect(url_for('almoxarifado.devolucao'))
        
=======

            db.session.commit()
            flash(f'Devolução processada com sucesso! {quantidade} {item.unidade} de "{item.nome}" devolvidos por {funcionario.nome}.', 'success')

        return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar devolução: {str(e)}')
        flash('Erro ao processar devolução de material', 'danger')
        return redirect(url_for('almoxarifado.devolucao'))

<<<<<<< HEAD
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-consumo', methods=['POST'])
@login_required
def processar_consumo():
    """Processa consumo de materiais consumíveis"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    try:
=======

    try:
        from decimal import Decimal
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        funcionario_id = request.form.get('funcionario_id', type=int)
        item_id = request.form.get('item_id', type=int)
        quantidade = request.form.get('quantidade', type=float)
        observacoes = request.form.get('observacoes', '').strip()
<<<<<<< HEAD
        
        # Validações
        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        if not item_id or not quantidade or quantidade <= 0:
            flash('Item e quantidade válida são obrigatórios', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
=======

        if not funcionario_id:
            flash('Funcionário é obrigatório', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))

        if not item_id or not quantidade or quantidade <= 0:
            flash('Item e quantidade válida são obrigatórios', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            flash('Funcionário não encontrado', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
        if not item or item.tipo_controle != 'CONSUMIVEL':
            flash('Item não encontrado ou não é consumível', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
<<<<<<< HEAD
        
        # Calcular quantidade em posse
        from decimal import Decimal
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        quantidade_saida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='SAIDA',
            admin_id=admin_id
        ).scalar() or Decimal('0')
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        quantidade_devolvida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='DEVOLUCAO',
            admin_id=admin_id
        ).scalar() or Decimal('0')
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        quantidade_consumida = db.session.query(func.sum(AlmoxarifadoMovimento.quantidade)).filter_by(
            item_id=item_id,
            funcionario_id=funcionario_id,
            tipo_movimento='CONSUMIDO',
            admin_id=admin_id
        ).scalar() or Decimal('0')
<<<<<<< HEAD
        
        quantidade_em_posse = quantidade_saida - quantidade_devolvida - quantidade_consumida
        
        # Verificar se tem quantidade suficiente
        if Decimal(str(quantidade)) > quantidade_em_posse:
            flash(f'Quantidade insuficiente! Funcionário possui apenas {quantidade_em_posse} {item.unidade} em posse.', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))
        
        # Criar movimento de consumo
=======

        quantidade_em_posse = quantidade_saida - quantidade_devolvida - quantidade_consumida

        if Decimal(str(quantidade)) > quantidade_em_posse:
            flash(f'Quantidade insuficiente! Funcionário possui apenas {quantidade_em_posse} {item.unidade} em posse.', 'danger')
            return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        movimento = AlmoxarifadoMovimento(
            item_id=item_id,
            tipo_movimento='CONSUMIDO',
            quantidade=quantidade,
            funcionario_id=funcionario_id,
            observacao=observacoes,
            admin_id=admin_id,
            usuario_id=current_user.id,
            obra_id=None
        )
        db.session.add(movimento)
        db.session.commit()
<<<<<<< HEAD
        
        flash(f'Consumo registrado com sucesso! {quantidade} {item.unidade} de "{item.nome}" consumidos por {funcionario.nome}.', 'success')
        return redirect(url_for('almoxarifado.devolucao'))
        
=======

        flash(f'Consumo registrado com sucesso! {quantidade} {item.unidade} de "{item.nome}" consumidos por {funcionario.nome}.', 'success')
        return redirect(url_for('almoxarifado.devolucao'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar consumo: {str(e)}')
        flash('Erro ao processar consumo de material', 'danger')
        return redirect(url_for('almoxarifado.devolucao'))

<<<<<<< HEAD
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
@almoxarifado_bp.route('/processar-devolucao-multipla', methods=['POST'])
@login_required
def processar_devolucao_multipla():
    """Processa devolução de múltiplos itens (carrinho) - TRANSAÇÃO ATÔMICA"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    try:
        data = request.get_json()
        itens = data.get('itens', [])
        observacoes = data.get('observacoes', '').strip()
<<<<<<< HEAD
        
        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400
        
        # ========================================
        # FASE 1: VALIDAÇÃO PRÉVIA COMPLETA
        # ========================================
        erros = []
        itens_validados = []
        
        # Validar que todos itens têm mesmo funcionário
        funcionario_id = itens[0].get('funcionario_id')
        
        for item_data in itens:
            if item_data.get('funcionario_id') != funcionario_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesmo funcionário'}), 400
        
        # Validar que funcionário existe
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400
        
        # Condições válidas
        condicoes_validas = ['Perfeito', 'Bom', 'Regular', 'Danificado', 'Inutilizado']
        
        # Validar cada item
=======

        if not itens or len(itens) == 0:
            return jsonify({'success': False, 'message': 'Carrinho vazio'}), 400

        funcionario_id = itens[0].get('funcionario_id')

        for item_data in itens:
            if item_data.get('funcionario_id') != funcionario_id:
                return jsonify({'success': False, 'message': 'Todos itens devem ter mesmo funcionário'}), 400

        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 400

        condicoes_validas = ['Perfeito', 'Bom', 'Regular', 'Danificado', 'Inutilizado']

        erros = []
        itens_validados = []

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        for idx, item_data in enumerate(itens):
            item_id = item_data.get('item_id')
            tipo_controle = item_data.get('tipo_controle')
            condicao_item = item_data.get('condicao_item', '').strip()
<<<<<<< HEAD
            
            # Validar: condição obrigatória
            if not condicao_item:
                erros.append(f"Item {idx+1}: Condição do item é obrigatória")
                continue
            
            # Validar: condição válida
            if condicao_item not in condicoes_validas:
                erros.append(f"Item {idx+1}: Condição '{condicao_item}' inválida")
                continue
            
            # Verificar se item existe
=======

            if not condicao_item:
                erros.append(f"Item {idx+1}: Condição do item é obrigatória")
                continue

            if condicao_item not in condicoes_validas:
                erros.append(f"Item {idx+1}: Condição '{condicao_item}' inválida")
                continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                erros.append(f"Item {idx+1}: Item não encontrado")
                continue
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')
                
                # VALIDAR: Item pertence ao funcionário (status='EM_USO')?
=======

            if tipo_controle == 'SERIALIZADO':
                estoque_id = item_data.get('estoque_id')
                numero_serie = item_data.get('numero_serie')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    id=estoque_id,
                    funcionario_id=funcionario_id,
                    status='EM_USO',
                    admin_id=admin_id
                ).first()
<<<<<<< HEAD
                
                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não está em uso pelo funcionário")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                if not estoque:
                    erros.append(f"Item {idx+1} ({item.nome}): Número de série {numero_serie} não está em uso pelo funcionário")
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'estoque_id': estoque_id,
                    'numero_serie': numero_serie,
                    'condicao_item': condicao_item,
                    'estoque': estoque
                })
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            else:  # CONSUMIVEL
                from decimal import Decimal
                quantidade_raw = item_data.get('quantidade', 0)
                quantidade = Decimal(str(quantidade_raw)) if quantidade_raw else Decimal('0')
<<<<<<< HEAD
                
                # Validar: quantidade > 0
                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue
                
                # VALIDAR: Item permite devolução?
                if not item.permite_devolucao:
                    erros.append(f"Item {idx+1} ({item.nome}): Item não permite devolução")
                    continue
                
                # Se passou nas validações, adicionar à lista de processamento
=======

                if quantidade <= 0:
                    erros.append(f"Item {idx+1} ({item.nome}): Quantidade deve ser maior que zero")
                    continue

                if not item.permite_devolucao:
                    erros.append(f"Item {idx+1} ({item.nome}): Item não permite devolução")
                    continue

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                itens_validados.append({
                    'item': item,
                    'tipo_controle': tipo_controle,
                    'quantidade': quantidade,
                    'condicao_item': condicao_item
                })
<<<<<<< HEAD
        
        # Se houver QUALQUER erro, abortar TUDO
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if erros:
            return jsonify({
                'success': False,
                'message': f'{len(erros)} erro(s) encontrado(s)',
                'erros': erros
            }), 400
<<<<<<< HEAD
        
        # ========================================
        # FASE 2: PROCESSAMENTO TRANSACIONAL
        # ========================================
        total_processados = 0
        total_itens_esperados = len(itens_validados)
        
=======

        total_processados = 0
        total_itens_esperados = len(itens_validados)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        for item_validado in itens_validados:
            item = item_validado['item']
            tipo_controle = item_validado['tipo_controle']
            condicao_item = item_validado['condicao_item']
<<<<<<< HEAD
            
            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']
                
                # Determinar novo status baseado na condição
                if condicao_item in ['Perfeito', 'Bom']:
                    estoque.status = 'DISPONIVEL'
                elif condicao_item == 'Regular':
=======

            if tipo_controle == 'SERIALIZADO':
                estoque = item_validado['estoque']
                numero_serie = item_validado['numero_serie']

                if condicao_item in ['Perfeito', 'Bom', 'Regular']:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                    estoque.status = 'DISPONIVEL'
                elif condicao_item == 'Danificado':
                    estoque.status = 'EM_MANUTENCAO'
                elif condicao_item == 'Inutilizado':
                    estoque.status = 'INUTILIZADO'
<<<<<<< HEAD
                
                # Limpar vinculo com funcionário e obra
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                obra_id_movimento = estoque.obra_id
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
                estoque.updated_at = datetime.utcnow()
<<<<<<< HEAD
                
                # Criar movimento de devolução
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=1,
                    numero_serie=numero_serie,
                    funcionario_id=funcionario_id,
                    obra_id=obra_id_movimento,
                    condicao_item=condicao_item,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
<<<<<<< HEAD
            
            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']
                
                # Criar novo registro de estoque com quantidade devolvida
=======

            else:  # CONSUMIVEL
                quantidade = item_validado['quantidade']

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                estoque = AlmoxarifadoEstoque(
                    item_id=item.id,
                    quantidade=quantidade,
                    status='DISPONIVEL',
                    admin_id=admin_id
                )
                db.session.add(estoque)
                db.session.flush()
<<<<<<< HEAD
                
                # Criar movimento de devolução
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                movimento = AlmoxarifadoMovimento(
                    item_id=item.id,
                    tipo_movimento='DEVOLUCAO',
                    quantidade=quantidade,
                    funcionario_id=funcionario_id,
                    obra_id=None,
                    condicao_item=condicao_item,
                    observacao=observacoes,
                    estoque_id=estoque.id,
                    admin_id=admin_id,
                    usuario_id=current_user.id
                )
                db.session.add(movimento)
                total_processados += 1
<<<<<<< HEAD
        
        # Commit APENAS se TODOS itens foram processados
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if total_processados != total_itens_esperados:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Erro: Esperado {total_itens_esperados} itens, processado {total_processados}'
            }), 500
<<<<<<< HEAD
        
        db.session.commit()
        
=======

        db.session.commit()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        return jsonify({
            'success': True,
            'message': f'{total_processados} itens devolvidos com sucesso por {funcionario.nome}!',
            'total_esperado': total_itens_esperados,
            'total_processado': total_processados
        })
<<<<<<< HEAD
        
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao processar devolução múltipla: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao processar operação'}), 500

<<<<<<< HEAD
@almoxarifado_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """Lista todas as movimentações com filtros avançados e paginação - FASE 5"""
=======

# ========================================
# LISTA DE MOVIMENTAÇÕES (com filtros e paginação)
# ========================================

@almoxarifado_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    """Lista todas as movimentações com filtros avançados e paginação"""
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    # Obter parâmetros de filtro
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    page = request.args.get('page', 1, type=int)
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    tipo_movimento = request.args.get('tipo_movimento', '')
    funcionario_id = request.args.get('funcionario_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    item_id = request.args.get('item_id', type=int)
<<<<<<< HEAD
    
    # Query base com multi-tenant
    query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id)
    
    # JOIN com Item (sempre necessário)
    query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
    
    # OUTER JOIN com Funcionario e Obra
    query = query.outerjoin(Funcionario, AlmoxarifadoMovimento.funcionario_id == Funcionario.id)
    query = query.outerjoin(Obra, AlmoxarifadoMovimento.obra_id == Obra.id)
    
    # Aplicar filtros
=======

    query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id)
    query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
    query = query.outerjoin(Funcionario, AlmoxarifadoMovimento.funcionario_id == Funcionario.id)
    query = query.outerjoin(Obra, AlmoxarifadoMovimento.obra_id == Obra.id)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
        except ValueError:
            flash('Data de início inválida', 'warning')
<<<<<<< HEAD
    
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
            # Adicionar 1 dia para incluir todo o dia final
=======

    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            data_fim_obj = data_fim_obj + timedelta(days=1)
            query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
        except ValueError:
            flash('Data de fim inválida', 'warning')
<<<<<<< HEAD
    
    if tipo_movimento:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_movimento)
    
    if funcionario_id:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == funcionario_id)
    
    if obra_id:
        query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
    
    if item_id:
        query = query.filter(AlmoxarifadoMovimento.item_id == item_id)
    
    # Ordenar por data mais recente primeiro
    query = query.order_by(AlmoxarifadoMovimento.data_movimento.desc())
    
    # Paginação (50 registros por página)
    movimentacoes_paginadas = query.paginate(page=page, per_page=50, error_out=False)
    
    # Buscar dados para os filtros (com multi-tenant)
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Calcular estatísticas de exibição
    total_registros = movimentacoes_paginadas.total
    inicio = (page - 1) * 50 + 1 if total_registros > 0 else 0
    fim = min(page * 50, total_registros)
    
    return render_template('almoxarifado/movimentacoes.html',
                         movimentacoes=movimentacoes_paginadas,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         tipo_movimento=tipo_movimento,
                         funcionario_id=funcionario_id,
                         obra_id=obra_id,
                         item_id=item_id,
                         total_registros=total_registros,
                         inicio=inicio,
                         fim=fim)
=======

    if tipo_movimento:
        query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_movimento)

    if funcionario_id:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == funcionario_id)

    if obra_id:
        query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)

    if item_id:
        query = query.filter(AlmoxarifadoMovimento.item_id == item_id)

    query = query.order_by(AlmoxarifadoMovimento.data_movimento.desc())

    movimentacoes_paginadas = query.paginate(page=page, per_page=50, error_out=False)

    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    total_registros = movimentacoes_paginadas.total
    inicio = (page - 1) * 50 + 1 if total_registros > 0 else 0
    fim = min(page * 50, total_registros)

    return render_template('almoxarifado/movimentacoes.html',
                           movimentacoes=movimentacoes_paginadas,
                           itens=itens,
                           funcionarios=funcionarios,
                           obras=obras,
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           tipo_movimento=tipo_movimento,
                           funcionario_id=funcionario_id,
                           obra_id=obra_id,
                           item_id=item_id,
                           total_registros=total_registros,
                           inicio=inicio,
                           fim=fim)


# ========================================
# CRUD MOVIMENTAÇÕES MANUAIS
# ========================================
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/movimentacoes/criar', methods=['GET', 'POST'])
@login_required
def movimentacoes_criar():
    """Criar nova movimentação manual"""
    from almoxarifado_utils import apply_movimento_manual
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    if request.method == 'POST':
        try:
            tipo_movimento = request.form.get('tipo_movimento')
            item_id = request.form.get('item_id')
            quantidade = request.form.get('quantidade')
            data_movimento = request.form.get('data_movimento')
            funcionario_id = request.form.get('funcionario_id')
            obra_id = request.form.get('obra_id')
            observacao = request.form.get('observacao', '').strip()
            impacta_estoque = request.form.get('impacta_estoque') == 'on'
            valor_unitario = request.form.get('valor_unitario')
            lote = request.form.get('lote', '').strip()
            numero_serie = request.form.get('numero_serie', '').strip()
<<<<<<< HEAD
            
            # Validações
            if not tipo_movimento or not item_id or not quantidade:
                flash('Tipo de movimento, item e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
            
=======

            if not tipo_movimento or not item_id or not quantidade:
                flash('Tipo de movimento, item e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            try:
                quantidade = float(quantidade)
                if quantidade <= 0:
                    flash('Quantidade deve ser maior que zero', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            except ValueError:
                flash('Quantidade inválida', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
<<<<<<< HEAD
            
            # Validar data
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if data_movimento:
                data_mov = datetime.strptime(data_movimento, '%Y-%m-%d')
                if data_mov.date() > datetime.now().date():
                    flash('Data do movimento não pode ser futura', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                data_mov = datetime.now()
<<<<<<< HEAD
            
            # Validar item
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
            if not item:
                flash('Item não encontrado', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_criar'))
<<<<<<< HEAD
            
            # Validar funcionário e obra (se fornecidos)
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if funcionario_id:
                funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
                if not funcionario:
                    flash('Funcionário não encontrado', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                funcionario_id = None
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
            else:
                obra_id = None
<<<<<<< HEAD
            
            # Processar valor unitário
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if valor_unitario:
                try:
                    valor_unitario = float(valor_unitario)
                except ValueError:
                    valor_unitario = None
            else:
                valor_unitario = None
<<<<<<< HEAD
            
            # Criar movimentação
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            movimento = AlmoxarifadoMovimento(
                tipo_movimento=tipo_movimento,
                item_id=item_id,
                quantidade=quantidade,
                data_movimento=data_mov,
                funcionario_id=funcionario_id,
                obra_id=obra_id,
                observacao=observacao or None,
                impacta_estoque=impacta_estoque,
                origem_manual=True,
                usuario_id=current_user.id,
                admin_id=admin_id,
                valor_unitario=valor_unitario,
                lote=lote or None,
                numero_serie=numero_serie or None
            )
<<<<<<< HEAD
            
            db.session.add(movimento)
            db.session.flush()
            
            # Aplicar ao estoque se necessário
=======

            db.session.add(movimento)
            db.session.flush()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if impacta_estoque:
                resultado = apply_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao aplicar movimento ao estoque: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_criar'))
<<<<<<< HEAD
            
            db.session.commit()
            
            flash(f'Movimentação manual criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
            
=======

            db.session.commit()

            flash('Movimentação manual criada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar movimentação manual: {str(e)}')
            flash(f'Erro ao criar movimentação: {str(e)}', 'danger')
            return redirect(url_for('almoxarifado.movimentacoes_criar'))
<<<<<<< HEAD
    
    # GET - Carregar dados para o formulário
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Item pré-selecionado da query string
    item_id_pre = request.args.get('item_id')
    
    # Data de hoje
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('almoxarifado/movimentacoes_form.html',
                         movimento=None,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         item_id_pre=item_id_pre,
                         hoje=hoje)
=======

    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    item_id_pre = request.args.get('item_id')
    hoje = datetime.now().strftime('%Y-%m-%d')

    return render_template('almoxarifado/movimentacoes_form.html',
                           movimento=None,
                           itens=itens,
                           funcionarios=funcionarios,
                           obras=obras,
                           item_id_pre=item_id_pre,
                           hoje=hoje)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/movimentacoes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def movimentacoes_editar(id):
    """Editar movimentação manual existente com proteção contra concorrência"""
    from almoxarifado_utils import apply_movimento_manual, rollback_movimento_manual
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # ===== PROTEÇÃO DE CONCORRÊNCIA: Optimistic Locking =====
            # Validar timestamp para detectar edições concorrentes
=======

    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        try:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            updated_at_original = request.form.get('updated_at_original')
            if updated_at_original:
                try:
                    updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S')
<<<<<<< HEAD
                
                # Recarregar movimento do banco para verificar se foi modificado
                db.session.refresh(movimento)
                
=======

                db.session.refresh(movimento)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
                if movimento.updated_at and movimento.updated_at > updated_at_check:
                    flash(
                        'ERRO: Este registro foi modificado por outro usuário. '
                        'Por favor, recarregue a página e tente novamente.',
                        'danger'
                    )
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
<<<<<<< HEAD
            
            # ===== TRANSAÇÃO ATÔMICA =====
            # Iniciar transação explícita para garantir atomicidade
            
            # Salvar estado anterior para rollback
            impactava_estoque_antes = movimento.impacta_estoque
            
            # Rollback do estoque anterior se estava impactando
=======

            impactava_estoque_antes = movimento.impacta_estoque

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if impactava_estoque_antes:
                resultado = rollback_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao reverter movimento anterior: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
<<<<<<< HEAD
            
            # Atualizar campos
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            tipo_movimento = request.form.get('tipo_movimento')
            quantidade = request.form.get('quantidade')
            data_movimento = request.form.get('data_movimento')
            funcionario_id = request.form.get('funcionario_id')
            obra_id = request.form.get('obra_id')
            observacao = request.form.get('observacao', '').strip()
            impacta_estoque = request.form.get('impacta_estoque') == 'on'
            valor_unitario = request.form.get('valor_unitario')
            lote = request.form.get('lote', '').strip()
            numero_serie = request.form.get('numero_serie', '').strip()
<<<<<<< HEAD
            
            # Validações
            if not tipo_movimento or not quantidade:
                flash('Tipo de movimento e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            
=======

            if not tipo_movimento or not quantidade:
                flash('Tipo de movimento e quantidade são obrigatórios', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            try:
                quantidade = float(quantidade)
                if quantidade <= 0:
                    flash('Quantidade deve ser maior que zero', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            except ValueError:
                flash('Quantidade inválida', 'danger')
                return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
<<<<<<< HEAD
            
            # Validar data
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if data_movimento:
                data_mov = datetime.strptime(data_movimento, '%Y-%m-%d')
                if data_mov.date() > datetime.now().date():
                    flash('Data do movimento não pode ser futura', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                data_mov = movimento.data_movimento
<<<<<<< HEAD
            
            # Validar funcionário e obra (se fornecidos)
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if funcionario_id:
                funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
                if not funcionario:
                    flash('Funcionário não encontrado', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                funcionario_id = None
<<<<<<< HEAD
            
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
            else:
                obra_id = None
<<<<<<< HEAD
            
            # Processar valor unitário
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if valor_unitario:
                try:
                    valor_unitario = float(valor_unitario)
                except ValueError:
                    valor_unitario = None
            else:
                valor_unitario = None
<<<<<<< HEAD
            
            # Atualizar movimento
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            movimento.tipo_movimento = tipo_movimento
            movimento.quantidade = quantidade
            movimento.data_movimento = data_mov
            movimento.funcionario_id = funcionario_id
            movimento.obra_id = obra_id
            movimento.observacao = observacao or None
            movimento.impacta_estoque = impacta_estoque
            movimento.valor_unitario = valor_unitario
            movimento.lote = lote or None
            movimento.numero_serie = numero_serie or None
<<<<<<< HEAD
            
            db.session.flush()
            
            # Aplicar novo movimento ao estoque se necessário
=======

            db.session.flush()

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if impacta_estoque:
                resultado = apply_movimento_manual(movimento)
                if not resultado['sucesso']:
                    db.session.rollback()
                    flash(f'Erro ao aplicar movimento ao estoque: {resultado["mensagem"]}', 'danger')
                    return redirect(url_for('almoxarifado.movimentacoes_editar', id=id))
<<<<<<< HEAD
            
            db.session.commit()
            
            flash('Movimentação atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=movimento.item_id))
            
=======

            db.session.commit()

            flash('Movimentação atualizada com sucesso!', 'success')
            return redirect(url_for('almoxarifado.itens_movimentacoes', id=movimento.item_id))

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao editar movimentação: {str(e)}')
            flash(f'Erro ao editar movimentação: {str(e)}', 'danger')
<<<<<<< HEAD
    
    # GET - Carregar dados para o formulário
    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    # Data de hoje
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('almoxarifado/movimentacoes_form.html',
                         movimento=movimento,
                         itens=itens,
                         funcionarios=funcionarios,
                         obras=obras,
                         hoje=hoje)
=======

    itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    hoje = datetime.now().strftime('%Y-%m-%d')

    return render_template('almoxarifado/movimentacoes_form.html',
                           movimento=movimento,
                           itens=itens,
                           funcionarios=funcionarios,
                           obras=obras,
                           hoje=hoje)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1

@almoxarifado_bp.route('/movimentacoes/deletar/<int:id>', methods=['POST'])
@login_required
def movimentacoes_deletar(id):
    """Deletar movimentação manual com proteção contra concorrência"""
    from almoxarifado_utils import rollback_movimento_manual
<<<<<<< HEAD
    
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
<<<<<<< HEAD
    
    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    item_id = movimento.item_id
    
    try:
        # ===== PROTEÇÃO DE CONCORRÊNCIA: Optimistic Locking =====
        # Validar timestamp para detectar modificações concorrentes
=======

    movimento = AlmoxarifadoMovimento.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    item_id = movimento.item_id

    try:
>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        updated_at_original = request.form.get('updated_at_original')
        if updated_at_original:
            try:
                updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                updated_at_check = datetime.strptime(updated_at_original, '%Y-%m-%d %H:%M:%S')
<<<<<<< HEAD
            
            # Recarregar movimento do banco para verificar se foi modificado
            db.session.refresh(movimento)
            
=======

            db.session.refresh(movimento)

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
            if movimento.updated_at and movimento.updated_at > updated_at_check:
                flash(
                    'ERRO: Este registro foi modificado por outro usuário. '
                    'A exclusão foi cancelada. Por favor, recarregue a página.',
                    'danger'
                )
                return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
<<<<<<< HEAD
        
        # ===== TRANSAÇÃO ATÔMICA =====
        
        # Rollback do estoque se estava impactando
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
        if movimento.impacta_estoque:
            resultado = rollback_movimento_manual(movimento)
            if not resultado['sucesso']:
                db.session.rollback()
                flash(f'Erro ao reverter estoque: {resultado["mensagem"]}', 'danger')
                return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
<<<<<<< HEAD
        
        # Hard delete (pode mudar para soft delete se necessário)
        db.session.delete(movimento)
        db.session.commit()
        
        flash('Movimentação excluída com sucesso!', 'success')
        
=======

        db.session.delete(movimento)
        db.session.commit()

        flash('Movimentação excluída com sucesso!', 'success')

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao deletar movimentação: {str(e)}')
        flash(f'Erro ao excluir movimentação: {str(e)}', 'danger')
<<<<<<< HEAD
    
    # Redirecionar de volta para a página de origem
    # Se veio da lista principal de movimentações, volta para lá
    # Se veio da página do item, volta para a página do item
=======

>>>>>>> 7d4bef6c2972b820519cd3cab2f33d3f0078ddd1
    referrer = request.referrer
    if referrer and '/almoxarifado/movimentacoes' in referrer and f'/itens/{item_id}' not in referrer:
        return redirect(url_for('almoxarifado.movimentacoes'))
    else:
        return redirect(url_for('almoxarifado.itens_movimentacoes', id=item_id))
