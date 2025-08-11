#!/usr/bin/env python3
"""
INTERFACE DE LANÇAMENTO MÚLTIPLO v8.1
Permite lançar registros para múltiplos funcionários simultaneamente
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models import *
from app import db
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
import logging

# Blueprint para lançamento múltiplo
lancamento_multiplo_bp = Blueprint('lancamento_multiplo', __name__)

@lancamento_multiplo_bp.route('/lancamento-multiplo', methods=['GET'])
@login_required
def pagina_lancamento_multiplo():
    """Página principal de lançamento múltiplo"""
    
    # Buscar funcionários do admin
    if current_user.tipo_usuario.value == 'super_admin':
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        obras = Obra.query.filter_by(status='Em Andamento').all()
    else:
        funcionarios = Funcionario.query.filter_by(
            admin_id=current_user.id, 
            ativo=True
        ).all()
        obras = Obra.query.filter_by(
            admin_id=current_user.id,
            status='Em Andamento'
        ).all()
    
    return render_template('lancamento_multiplo.html', 
                         funcionarios=funcionarios, 
                         obras=obras)

@lancamento_multiplo_bp.route('/api/lancamento-multiplo', methods=['POST'])
@login_required
def processar_lancamento_multiplo():
    """Processa lançamento múltiplo de registros"""
    
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        campos_obrigatorios = ['data_inicio', 'data_fim', 'tipo_registro', 'funcionarios_ids']
        for campo in campos_obrigatorios:
            if campo not in data or not data[campo]:
                return jsonify({'erro': f'Campo {campo} é obrigatório'}), 400
        
        # Converter datas
        data_inicio = datetime.strptime(data['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(data['data_fim'], '%Y-%m-%d').date()
        
        # Validar período
        if data_fim < data_inicio:
            return jsonify({'erro': 'Data fim deve ser maior que data início'}), 400
        
        tipo_registro = data['tipo_registro']
        funcionarios_ids = data['funcionarios_ids']
        obra_id = data.get('obra_id')
        horas_padrao = float(data.get('horas_padrao', 8.0))
        observacoes = data.get('observacoes', 'Lançamento múltiplo')
        
        # Processar lançamentos
        registros_criados = 0
        registros_atualizados = 0
        erros = []
        
        for funcionario_id in funcionarios_ids:
            funcionario = Funcionario.query.get(funcionario_id)
            if not funcionario:
                erros.append(f'Funcionário ID {funcionario_id} não encontrado')
                continue
            
            # Verificar permissão
            if (current_user.tipo_usuario.value != 'super_admin' and 
                funcionario.admin_id != current_user.id):
                erros.append(f'Sem permissão para funcionário {funcionario.nome}')
                continue
            
            # Criar registros para o período
            data_atual = data_inicio
            while data_atual <= data_fim:
                # Verificar se deve criar o registro
                if deve_criar_registro(data_atual, tipo_registro):
                    resultado = criar_ou_atualizar_registro(
                        funcionario_id=funcionario_id,
                        data=data_atual,
                        tipo_registro=tipo_registro,
                        obra_id=obra_id,
                        horas_trabalhadas=calcular_horas_por_tipo(funcionario, tipo_registro, horas_padrao),
                        observacoes=observacoes
                    )
                    
                    if resultado['criado']:
                        registros_criados += 1
                    elif resultado['atualizado']:
                        registros_atualizados += 1
                    else:
                        erros.append(resultado.get('erro', 'Erro desconhecido'))
                
                data_atual += timedelta(days=1)
        
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'registros_criados': registros_criados,
            'registros_atualizados': registros_atualizados,
            'erros': erros,
            'resumo': f'{registros_criados} criados, {registros_atualizados} atualizados'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro no lançamento múltiplo: {str(e)}")
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500

def deve_criar_registro(data, tipo_registro):
    """Determina se deve criar registro para o dia/tipo"""
    
    dia_semana = data.weekday()  # 0=Segunda, 6=Domingo
    
    # Lógica por tipo
    if tipo_registro in ['trabalho_normal', 'falta', 'falta_justificada']:
        # Apenas dias úteis (segunda a sexta)
        return dia_semana < 5
    
    elif tipo_registro == 'sabado_trabalhado':
        # Apenas sábados
        return dia_semana == 5
    
    elif tipo_registro == 'domingo_trabalhado':
        # Apenas domingos
        return dia_semana == 6
    
    elif tipo_registro == 'sabado_folga':
        # Apenas sábados
        return dia_semana == 5
    
    elif tipo_registro == 'domingo_folga':
        # Apenas domingos
        return dia_semana == 6
    
    elif tipo_registro in ['ferias', 'feriado_trabalhado', 'feriado_folga']:
        # Qualquer dia (usuário define período)
        return True
    
    return False

def calcular_horas_por_tipo(funcionario, tipo_registro, horas_padrao):
    """Calcula horas baseado no tipo e horário do funcionário"""
    
    # Tipos sem horas trabalhadas
    tipos_sem_horas = ['falta', 'sabado_folga', 'domingo_folga', 'feriado_folga']
    if tipo_registro in tipos_sem_horas:
        return 0.0
    
    # Usar horário específico do funcionário
    if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
        return float(funcionario.horario_trabalho.horas_diarias)
    
    # Usar padrão fornecido
    return horas_padrao

def criar_ou_atualizar_registro(funcionario_id, data, tipo_registro, obra_id, horas_trabalhadas, observacoes):
    """Cria ou atualiza registro de ponto com lógica correta por tipo"""
    
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return {'erro': f'Funcionário {funcionario_id} não encontrado'}
        
        # Verificar se já existe
        registro_existente = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data == data
        ).first()
        
        # Mapear tipos novos para antigos no banco
        tipo_banco = tipo_registro
        if tipo_registro == 'trabalho_normal':
            tipo_banco = 'trabalhado'
        elif tipo_registro == 'sabado_trabalhado':
            tipo_banco = 'sabado_horas_extras'
        elif tipo_registro == 'domingo_trabalhado':
            tipo_banco = 'domingo_horas_extras'
        elif tipo_registro == 'feriado_folga':
            tipo_banco = 'feriado'
            
        # Calcular horas extras baseado no tipo
        horas_extras = 0.0
        percentual_extras = 0.0
        
        # Para sábado/domingo/feriado trabalhado: TODAS as horas são extras
        if tipo_registro in ['sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
            horas_extras = horas_trabalhadas
            if tipo_registro == 'sabado_trabalhado':
                percentual_extras = 50.0  # +50% para sábado
            else:  # domingo_trabalhado, feriado_trabalhado
                percentual_extras = 100.0  # +100% para domingo/feriado
        elif tipo_registro == 'trabalho_normal' and horas_trabalhadas > 0:
            # Para trabalho normal: apenas horas acima da jornada
            horas_jornada = funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0
            horas_extras = max(0, horas_trabalhadas - horas_jornada)
            if horas_extras > 0:
                percentual_extras = 50.0  # Padrão para horas extras normais
        
        if registro_existente:
            # Atualizar existente
            registro_existente.tipo_registro = tipo_banco
            registro_existente.obra_id = obra_id
            registro_existente.horas_trabalhadas = horas_trabalhadas
            registro_existente.horas_extras = horas_extras
            registro_existente.percentual_extras = percentual_extras
            registro_existente.observacoes = f"{observacoes} (atualizado)"
            
            return {'atualizado': True, 'registro_id': registro_existente.id}
        
        else:
            # Criar novo
            novo_registro = RegistroPonto(
                funcionario_id=funcionario_id,
                data=data,
                tipo_registro=tipo_banco,
                obra_id=obra_id,
                horas_trabalhadas=horas_trabalhadas,
                horas_extras=horas_extras,
                percentual_extras=percentual_extras,
                observacoes=observacoes
            )
            
            db.session.add(novo_registro)
            db.session.flush()  # Para obter o ID
            
            return {'criado': True, 'registro_id': novo_registro.id}
            
    except Exception as e:
        return {'erro': str(e)}

# Template HTML para lançamento múltiplo
TEMPLATE_LANCAMENTO_MULTIPLO = """
{% extends "base.html" %}

{% block title %}Lançamento Múltiplo de Ponto{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h4 class="card-title mb-0">
                        <i class="fas fa-users"></i> Lançamento Múltiplo de Ponto
                    </h4>
                </div>
                <div class="card-body">
                    <form id="formLancamentoMultiplo">
                        <!-- Configurações do Período -->
                        <div class="row mb-4">
                            <div class="col-md-3">
                                <label class="form-label">Data Início *</label>
                                <input type="date" class="form-control" id="dataInicio" required>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Data Fim *</label>
                                <input type="date" class="form-control" id="dataFim" required>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Tipo de Lançamento *</label>
                                <select class="form-select" id="tipoLancamento" required>
                                    <option value="">Selecione...</option>
                                    <optgroup label="📋 TRABALHO">
                                        <option value="trabalho_normal">Trabalho Normal</option>
                                        <option value="sabado_trabalhado">Sábado Trabalhado</option>
                                        <option value="domingo_trabalhado">Domingo Trabalhado</option>
                                        <option value="feriado_trabalhado">Feriado Trabalhado</option>
                                    </optgroup>
                                    <optgroup label="⚠️ AUSÊNCIAS">
                                        <option value="falta">Falta</option>
                                        <option value="falta_justificada">Falta Justificada</option>
                                        <option value="ferias">Férias</option>
                                    </optgroup>
                                    <optgroup label="🏠 FOLGAS">
                                        <option value="sabado_folga">Sábado - Folga</option>
                                        <option value="domingo_folga">Domingo - Folga</option>
                                        <option value="feriado_folga">Feriado - Folga</option>
                                    </optgroup>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">Obra</label>
                                <select class="form-select" id="obraLancamento">
                                    <option value="">Todas as obras</option>
                                    {% for obra in obras %}
                                    <option value="{{ obra.id }}">{{ obra.nome }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        
                        <!-- Configurações Adicionais -->
                        <div class="row mb-4">
                            <div class="col-md-3">
                                <label class="form-label">Horas Padrão</label>
                                <input type="number" class="form-control" id="horasPadrao" 
                                       value="8.0" step="0.5" min="0" max="12">
                                <small class="text-muted">Para tipos que requerem horas</small>
                            </div>
                            <div class="col-md-9">
                                <label class="form-label">Observações</label>
                                <input type="text" class="form-control" id="observacoes" 
                                       placeholder="Observações sobre o lançamento...">
                            </div>
                        </div>
                        
                        <!-- Seleção de Funcionários -->
                        <div class="row mb-4">
                            <div class="col-12">
                                <label class="form-label">Funcionários *</label>
                                <div class="border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                    <div class="mb-2">
                                        <button type="button" class="btn btn-sm btn-outline-primary me-2" 
                                                onclick="selecionarTodos()">
                                            <i class="fas fa-check-square"></i> Selecionar Todos
                                        </button>
                                        <button type="button" class="btn btn-sm btn-outline-secondary" 
                                                onclick="limparSelecao()">
                                            <i class="fas fa-square"></i> Limpar Seleção
                                        </button>
                                    </div>
                                    <div class="row">
                                        {% for funcionario in funcionarios %}
                                        <div class="col-md-4 mb-2">
                                            <div class="form-check">
                                                <input class="form-check-input funcionario-checkbox" 
                                                       type="checkbox" value="{{ funcionario.id }}" 
                                                       id="func{{ funcionario.id }}">
                                                <label class="form-check-label" for="func{{ funcionario.id }}">
                                                    {{ funcionario.nome }}
                                                </label>
                                            </div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Botões de Ação -->
                        <div class="row">
                            <div class="col-12">
                                <button type="button" class="btn btn-primary me-2" onclick="processarLancamento()">
                                    <i class="fas fa-save"></i> Processar Lançamento
                                </button>
                                <button type="button" class="btn btn-secondary me-2" onclick="previewLancamento()">
                                    <i class="fas fa-eye"></i> Visualizar Preview
                                </button>
                                <a href="{{ url_for('funcionarios') }}" class="btn btn-outline-secondary">
                                    <i class="fas fa-arrow-left"></i> Voltar
                                </a>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Modal de Preview -->
<div class="modal fade" id="modalPreview" tabindex="-1">
    <div class="modal-dialog modal-xl">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Preview do Lançamento</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="previewContent">
                <!-- Conteúdo será preenchido via JavaScript -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                <button type="button" class="btn btn-primary" onclick="confirmarLancamento()">
                    Confirmar Lançamento
                </button>
            </div>
        </div>
    </div>
</div>

<script>
function selecionarTodos() {
    document.querySelectorAll('.funcionario-checkbox').forEach(cb => cb.checked = true);
}

function limparSelecao() {
    document.querySelectorAll('.funcionario-checkbox').forEach(cb => cb.checked = false);
}

function previewLancamento() {
    const dados = coletarDados();
    if (!validarDados(dados)) return;
    
    // Gerar preview
    let preview = `
        <h6>Configuração:</h6>
        <ul>
            <li><strong>Período:</strong> ${dados.data_inicio} até ${dados.data_fim}</li>
            <li><strong>Tipo:</strong> ${dados.tipo_registro}</li>
            <li><strong>Funcionários:</strong> ${dados.funcionarios_ids.length} selecionados</li>
        </ul>
        <h6>Funcionários selecionados:</h6>
        <div class="row">
    `;
    
    dados.funcionarios_ids.forEach(id => {
        const label = document.querySelector(`label[for="func${id}"]`).textContent;
        preview += `<div class="col-md-4">${label}</div>`;
    });
    
    preview += '</div>';
    
    document.getElementById('previewContent').innerHTML = preview;
    new bootstrap.Modal(document.getElementById('modalPreview')).show();
}

function processarLancamento() {
    const dados = coletarDados();
    if (!validarDados(dados)) return;
    
    // Mostrar loading
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
    btn.disabled = true;
    
    fetch('/api/lancamento-multiplo', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(dados)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            alert(`Sucesso! ${data.resumo}`);
            window.location.href = '/funcionarios';
        } else {
            alert(`Erro: ${data.erro}`);
        }
    })
    .catch(error => {
        alert(`Erro: ${error.message}`);
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

function coletarDados() {
    const funcionariosSelecionados = [];
    document.querySelectorAll('.funcionario-checkbox:checked').forEach(cb => {
        funcionariosSelecionados.push(parseInt(cb.value));
    });
    
    return {
        data_inicio: document.getElementById('dataInicio').value,
        data_fim: document.getElementById('dataFim').value,
        tipo_registro: document.getElementById('tipoLancamento').value,
        obra_id: document.getElementById('obraLancamento').value || null,
        horas_padrao: parseFloat(document.getElementById('horasPadrao').value),
        observacoes: document.getElementById('observacoes').value || 'Lançamento múltiplo',
        funcionarios_ids: funcionariosSelecionados
    };
}

function validarDados(dados) {
    if (!dados.data_inicio || !dados.data_fim || !dados.tipo_registro) {
        alert('Preencha todos os campos obrigatórios');
        return false;
    }
    
    if (dados.funcionarios_ids.length === 0) {
        alert('Selecione pelo menos um funcionário');
        return false;
    }
    
    if (new Date(dados.data_fim) < new Date(dados.data_inicio)) {
        alert('Data fim deve ser maior que data início');
        return false;
    }
    
    return true;
}
</script>
{% endblock %}
"""

def salvar_template():
    """Salva template HTML em arquivo"""
    with open('templates/lancamento_multiplo.html', 'w', encoding='utf-8') as f:
        f.write(TEMPLATE_LANCAMENTO_MULTIPLO)

if __name__ == "__main__":
    print("Interface de Lançamento Múltiplo v8.1")
    print("=" * 50)
    print("✅ Blueprint criado")
    print("✅ Rotas definidas")
    print("✅ Template preparado")
    print("\nPara usar:")
    print("1. Registrar blueprint no app principal")
    print("2. Salvar template em templates/lancamento_multiplo.html")
    print("3. Adicionar link no menu principal")