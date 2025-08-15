#!/usr/bin/env python3
"""
🍽️ SISTEMA COMPLETO: CRUD de Alimentação com Edição Inline
Implementa todas as operações necessárias para o controle de alimentação
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from models import RegistroAlimentacao, Funcionario, Obra, Restaurante
from app import db
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta

# Criar blueprint para alimentação
alimentacao_bp = Blueprint('alimentacao', __name__)

@alimentacao_bp.route('/alimentacao')
@login_required  
def listar_alimentacao():
    """Lista registros de alimentação com filtros"""
    
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim') 
    funcionario_id = request.args.get('funcionario_id')
    
    # Query base
    query = RegistroAlimentacao.query
    
    # Aplicar filtros
    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        query = query.filter(RegistroAlimentacao.data >= data_inicio)
        
    if data_fim:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        query = query.filter(RegistroAlimentacao.data <= data_fim)
        
    if funcionario_id:
        query = query.filter(RegistroAlimentacao.funcionario_id == funcionario_id)
    
    # Se não há filtros, mostrar últimos 30 dias
    if not data_inicio and not data_fim:
        data_inicio = date.today() - timedelta(days=30)
        query = query.filter(RegistroAlimentacao.data >= data_inicio)
    
    # Buscar registros ordenados por data
    registros = query.order_by(RegistroAlimentacao.data.desc()).all()
    
    # Dados para o template
    funcionarios = Funcionario.query.order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(status='Em Andamento').order_by(Obra.nome).all()
    restaurantes = Restaurante.query.order_by(Restaurante.nome).all()
    
    # Importar date para o template
    from datetime import date
    
    return render_template('alimentacao.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         obras=obras,
                         restaurantes=restaurantes,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         date=date)

@alimentacao_bp.route('/alimentacao/nova', methods=['POST'])
@login_required
def nova_alimentacao():
    """Cria novo registro de alimentação"""
    
    try:
        # Verificar se é lançamento por período
        lancamento_periodo = request.form.get('lancamento_periodo') == 'on'
        
        if lancamento_periodo:
            data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
            data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date()
            
            # Gerar datas do período
            datas = []
            data_atual = data_inicio
            while data_atual <= data_fim:
                datas.append(data_atual)
                data_atual += timedelta(days=1)
        else:
            datas = [datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()]
        
        # Dados do formulário
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        obra_id = int(request.form.get('obra_id'))
        restaurante_id = int(request.form.get('restaurante_id'))
        observacoes = request.form.get('observacoes', '')
        
        # Funcionários selecionados
        funcionarios_ids = request.form.getlist('funcionarios[]')
        funcionarios_ids = [int(fid) for fid in funcionarios_ids]
        
        total_registros = 0
        
        # Criar registros para cada funcionário e cada data
        for data_registro in datas:
            for funcionario_id in funcionarios_ids:
                registro = RegistroAlimentacao(
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    restaurante_id=restaurante_id,
                    data=data_registro,
                    tipo=tipo,
                    valor=valor,
                    observacoes=observacoes
                )
                
                db.session.add(registro)
                total_registros += 1
        
        db.session.commit()
        
        flash(f'✅ {total_registros} registros de alimentação criados com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erro ao criar registros: {str(e)}', 'error')
    
    return redirect(url_for('alimentacao.listar_alimentacao'))

@alimentacao_bp.route('/alimentacao/editar/<int:id>', methods=['POST'])
@login_required
def editar_alimentacao(id):
    """Edita registro existente via AJAX"""
    
    try:
        registro = RegistroAlimentacao.query.get_or_404(id)
        
        # Dados do JSON
        dados = request.get_json()
        
        # Atualizar campos
        if 'data' in dados:
            registro.data = datetime.strptime(dados['data'], '%Y-%m-%d').date()
            
        if 'tipo' in dados:
            registro.tipo = dados['tipo']
            
        if 'valor' in dados:
            registro.valor = float(dados['valor'])
            
        if 'observacoes' in dados:
            registro.observacoes = dados['observacoes']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Registro atualizado com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@alimentacao_bp.route('/alimentacao/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_alimentacao(id):
    """Exclui registro de alimentação"""
    
    try:
        registro = RegistroAlimentacao.query.get_or_404(id)
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Registro excluído com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@alimentacao_bp.route('/alimentacao/funcionario/<int:funcionario_id>')
@login_required
def alimentacao_funcionario(funcionario_id):
    """Lista registros de alimentação de um funcionário específico"""
    
    funcionario = Funcionario.query.get_or_404(funcionario_id)
    
    # Filtros de data
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    query = RegistroAlimentacao.query.filter_by(funcionario_id=funcionario_id)
    
    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        query = query.filter(RegistroAlimentacao.data >= data_inicio)
        
    if data_fim:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        query = query.filter(RegistroAlimentacao.data <= data_fim)
    else:
        # Padrão: últimos 30 dias
        data_inicio_padrao = date.today() - timedelta(days=30)
        query = query.filter(RegistroAlimentacao.data >= data_inicio_padrao)
    
    registros = query.order_by(RegistroAlimentacao.data.desc()).all()
    
    # Calcular totais
    total_gasto = sum(r.valor for r in registros)
    total_registros = len(registros)
    
    return jsonify({
        'funcionario': funcionario.nome,
        'total_registros': total_registros,
        'total_gasto': total_gasto,
        'registros': [{
            'id': r.id,
            'data': r.data.strftime('%d/%m/%Y'),
            'tipo': r.tipo,
            'valor': r.valor,
            'obra': r.obra_ref.nome if r.obra_ref else '',
            'restaurante': r.restaurante_ref.nome if r.restaurante_ref else '',
            'observacoes': r.observacoes or ''
        } for r in registros]
    })

# Registrar blueprint
def init_alimentacao_routes(app):
    """Inicializa as rotas de alimentação"""
    app.register_blueprint(alimentacao_bp)

if __name__ == "__main__":
    print("🍽️ Módulo CRUD de Alimentação")
    print("Implementa todas as operações:")
    print("- ✅ Listar com filtros")
    print("- ✅ Criar (individual/período)")
    print("- ✅ Editar inline")
    print("- ✅ Excluir")
    print("- ✅ Consulta por funcionário")