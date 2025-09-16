#!/usr/bin/env python3
"""
Mobile API - SIGE v8.0
APIs específicas para aplicativo mobile React Native
"""

from flask import Blueprint, request, jsonify, current_app
from models import *
from app import db
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_
import base64
import os
from werkzeug.utils import secure_filename
import uuid

# Blueprint para APIs mobile
mobile_api = Blueprint('mobile_api', __name__, url_prefix='/api/mobile')

def mobile_auth_required(f):
    """Decorator para autenticação mobile"""
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'error': 'Token de autenticação necessário'}), 401
        
        # Aqui implementaria validação JWT
        # Por enquanto, usa autenticação padrão
        if not current_user.is_authenticated:
            return jsonify({'error': 'Usuário não autenticado'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@mobile_api.route('/auth/login', methods=['POST'])
def mobile_login():
    """Login específico para mobile com JWT"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    device_info = data.get('device_info', {})
    
    if not username or not password:
        return jsonify({'error': 'Username e password obrigatórios'}), 400
    
    # Validar credenciais (implementar validação real)
    user = Usuario.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        # Gerar JWT token (implementar JWT real)
        token = f"mobile_token_{user.id}_{datetime.now().timestamp()}"
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'tipo': user.tipo_usuario.name,
                'nome_completo': user.username
            },
            'expires_in': 3600  # 1 hora
        })
    
    return jsonify({'error': 'Credenciais inválidas'}), 401

@mobile_api.route('/dashboard', methods=['GET'])
@mobile_auth_required
def mobile_dashboard():
    """Dashboard resumido para mobile"""
    try:
        hoje = date.today()
        
        # Dados baseados no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            # Dashboard do funcionário
            funcionario = Funcionario.query.filter_by(usuario_id=current_user.id).first()
            
            if funcionario:
                # Ponto de hoje
                ponto_hoje = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=hoje
                ).first()
                
                # Últimos RDOs
                rdos_recentes = RDO.query.filter_by(
                    criado_por_id=current_user.id
                ).order_by(RDO.data_relatorio.desc()).limit(5).all()
                
                return jsonify({
                    'tipo_dashboard': 'funcionario',
                    'funcionario': {
                        'nome': funcionario.nome,
                        'codigo': funcionario.codigo,
                        'departamento': funcionario.departamento.nome if funcionario.departamento else None
                    },
                    'ponto_hoje': {
                        'registrado': ponto_hoje is not None,
                        'entrada': ponto_hoje.hora_entrada.strftime('%H:%M') if ponto_hoje and ponto_hoje.hora_entrada else None,
                        'saida': ponto_hoje.hora_saida.strftime('%H:%M') if ponto_hoje and ponto_hoje.hora_saida else None,
                        'horas_trabalhadas': float(ponto_hoje.horas_trabalhadas or 0) if ponto_hoje else 0
                    },
                    'rdos_recentes': [
                        {
                            'id': rdo.id,
                            'data': rdo.data_relatorio.isoformat(),
                            'obra': rdo.obra.nome if rdo.obra else 'N/A',
                            'atividades': len(rdo.atividades) if hasattr(rdo, 'atividades') else 0
                        } for rdo in rdos_recentes
                    ],
                    'acoes_rapidas': [
                        {'tipo': 'registrar_ponto', 'titulo': 'Registrar Ponto', 'disponivel': ponto_hoje is None},
                        {'tipo': 'criar_rdo', 'titulo': 'Criar RDO', 'disponivel': True},
                        {'tipo': 'uso_veiculo', 'titulo': 'Usar Veículo', 'disponivel': True}
                    ]
                })
        
        else:
            # Dashboard admin/super admin
            funcionarios_ativos = Funcionario.query.filter_by(ativo=True).count()
            obras_ativas = Obra.query.filter_by(status='Em andamento').count()
            rdos_hoje = RDO.query.filter_by(data_relatorio=hoje).count()
            
            # Alertas críticos
            alertas_criticos = 0  # Implementar contagem de alertas
            
            return jsonify({
                'tipo_dashboard': 'admin',
                'kpis': {
                    'funcionarios_ativos': funcionarios_ativos,
                    'obras_ativas': obras_ativas,
                    'rdos_hoje': rdos_hoje,
                    'alertas_criticos': alertas_criticos
                },
                'acoes_rapidas': [
                    {'tipo': 'ver_alertas', 'titulo': 'Ver Alertas', 'badge': alertas_criticos},
                    {'tipo': 'aprovar_gastos', 'titulo': 'Aprovar Gastos', 'badge': 3},
                    {'tipo': 'relatorios', 'titulo': 'Relatórios', 'badge': 0}
                ]
            })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar dashboard: {str(e)}'}), 500

@mobile_api.route('/ponto/registrar', methods=['POST'])
@mobile_auth_required
def mobile_registrar_ponto():
    """Registra ponto via mobile com GPS"""
    try:
        data = request.get_json()
        tipo_registro = data.get('tipo_registro', 'entrada')  # entrada, saida, almoco_saida, almoco_volta
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        observacoes = data.get('observacoes')
        
        # Buscar funcionário
        funcionario = Funcionario.query.filter_by(usuario_id=current_user.id).first()
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        hoje = date.today()
        agora = datetime.now()
        
        # Buscar ou criar registro de ponto do dia
        ponto = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=hoje
        ).first()
        
        if not ponto:
            ponto = RegistroPonto(
                funcionario_id=funcionario.id,
                data=hoje,
                tipo_registro='trabalho_normal'
            )
            db.session.add(ponto)
        
        # Registrar horário baseado no tipo
        if tipo_registro == 'entrada':
            ponto.hora_entrada = agora.time()
        elif tipo_registro == 'saida':
            ponto.hora_saida = agora.time()
        elif tipo_registro == 'almoco_saida':
            ponto.hora_almoco_saida = agora.time()
        elif tipo_registro == 'almoco_volta':
            ponto.hora_almoco_volta = agora.time()
        
        # Salvar coordenadas GPS
        if latitude and longitude:
            ponto.latitude = float(latitude)
            ponto.longitude = float(longitude)
        
        if observacoes:
            ponto.observacoes = observacoes
        
        # Calcular horas trabalhadas se tiver entrada e saída
        if ponto.hora_entrada and ponto.hora_saida:
            entrada_dt = datetime.combine(hoje, ponto.hora_entrada)
            saida_dt = datetime.combine(hoje, ponto.hora_saida)
            
            # Descontar almoço se registrado
            almoco_minutos = 0
            if ponto.hora_almoco_saida and ponto.hora_almoco_volta:
                almoco_saida_dt = datetime.combine(hoje, ponto.hora_almoco_saida)
                almoco_volta_dt = datetime.combine(hoje, ponto.hora_almoco_volta)
                almoco_minutos = (almoco_volta_dt - almoco_saida_dt).total_seconds() / 60
            
            total_minutos = (saida_dt - entrada_dt).total_seconds() / 60 - almoco_minutos
            ponto.horas_trabalhadas = max(0, total_minutos / 60)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensagem': f'Ponto registrado: {tipo_registro}',
            'horario': agora.strftime('%H:%M:%S'),
            'ponto_atual': {
                'entrada': ponto.hora_entrada.strftime('%H:%M') if ponto.hora_entrada else None,
                'saida': ponto.hora_saida.strftime('%H:%M') if ponto.hora_saida else None,
                'almoco_saida': ponto.hora_almoco_saida.strftime('%H:%M') if ponto.hora_almoco_saida else None,
                'almoco_volta': ponto.hora_almoco_volta.strftime('%H:%M') if ponto.hora_almoco_volta else None,
                'horas_trabalhadas': float(ponto.horas_trabalhadas or 0),
                'observacoes': ponto.observacoes
            }
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao registrar ponto: {str(e)}'}), 500

@mobile_api.route('/ponto/historico', methods=['GET'])
@mobile_auth_required
def mobile_historico_ponto():
    """Histórico de ponto mobile"""
    try:
        funcionario = Funcionario.query.filter_by(usuario_id=current_user.id).first()
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Parâmetros de filtro
        dias = int(request.args.get('dias', 30))
        data_inicio = date.today() - timedelta(days=dias)
        
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= data_inicio
        ).order_by(RegistroPonto.data.desc()).all()
        
        historico = []
        for registro in registros:
            historico.append({
                'data': registro.data.isoformat(),
                'data_formatada': registro.data.strftime('%d/%m/%Y'),
                'dia_semana': registro.data.strftime('%A'),
                'entrada': registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else None,
                'saida': registro.hora_saida.strftime('%H:%M') if registro.hora_saida else None,
                'almoco_saida': registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else None,
                'almoco_volta': registro.hora_almoco_volta.strftime('%H:%M') if registro.hora_almoco_volta else None,
                'horas_trabalhadas': float(registro.horas_trabalhadas or 0),
                'horas_extras': float(registro.horas_extras or 0),
                'tipo_registro': registro.tipo_registro,
                'observacoes': registro.observacoes,
                'atraso_minutos': registro.total_atraso_minutos or 0
            })
        
        return jsonify({
            'success': True,
            'periodo': f'Últimos {dias} dias',
            'total_registros': len(historico),
            'historico': historico
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar histórico: {str(e)}'}), 500

@mobile_api.route('/rdo/listar', methods=['GET'])
@mobile_auth_required
def mobile_listar_rdos():
    """Lista RDOs mobile"""
    try:
        # Filtros
        limite = int(request.args.get('limit', 20))
        pagina = int(request.args.get('page', 1))
        offset = (pagina - 1) * limite
        
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            # Funcionário vê apenas seus RDOs
            rdos = RDO.query.filter_by(
                criado_por_id=current_user.id
            ).order_by(RDO.data_relatorio.desc()).offset(offset).limit(limite).all()
        else:
            # Admin vê todos os RDOs
            rdos = RDO.query.order_by(RDO.data_relatorio.desc()).offset(offset).limit(limite).all()
        
        lista_rdos = []
        for rdo in rdos:
            lista_rdos.append({
                'id': rdo.id,
                'data_relatorio': rdo.data_relatorio.isoformat(),
                'data_formatada': rdo.data_relatorio.strftime('%d/%m/%Y'),
                'obra': {
                    'id': rdo.obra.id if rdo.obra else None,
                    'nome': rdo.obra.nome if rdo.obra else 'N/A'
                },
                'clima': rdo.clima,
                'observacoes': rdo.observacoes,
                'criado_por': rdo.criado_por.username if rdo.criado_por else 'N/A',
                'num_atividades': 0,  # Implementar contagem de atividades
                'status': 'Concluído'
            })
        
        return jsonify({
            'success': True,
            'rdos': lista_rdos,
            'pagina': pagina,
            'limite': limite,
            'total': len(lista_rdos)
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao listar RDOs: {str(e)}'}), 500

@mobile_api.route('/rdo/criar', methods=['POST'])
@mobile_auth_required
def mobile_criar_rdo():
    """Cria RDO via mobile"""
    try:
        data = request.get_json()
        
        obra_id = data.get('obra_id')
        clima = data.get('clima', 'Ensolarado')
        observacoes = data.get('observacoes', '')
        atividades = data.get('atividades', [])
        fotos = data.get('fotos', [])
        
        if not obra_id:
            return jsonify({'error': 'ID da obra é obrigatório'}), 400
        
        # Verificar se obra existe
        obra = Obra.query.get(obra_id)
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Criar RDO
        rdo = RDO(
            data_relatorio=date.today(),
            obra_id=obra_id,
            clima=clima,
            observacoes=observacoes,
            criado_por_id=current_user.id,
            data_criacao=datetime.now()
        )
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID
        
        # Processar fotos base64
        fotos_salvas = []
        for i, foto_base64 in enumerate(fotos):
            if foto_base64:
                try:
                    # Decodificar base64
                    foto_data = base64.b64decode(foto_base64.split(',')[1])
                    
                    # Salvar arquivo
                    filename = f"rdo_{rdo.id}_foto_{i}_{uuid.uuid4().hex[:8]}.jpg"
                    filepath = os.path.join('static', 'fotos_rdo', filename)
                    
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(foto_data)
                    
                    fotos_salvas.append({
                        'filename': filename,
                        'path': filepath,
                        'url': f'/static/fotos_rdo/{filename}'
                    })
                    
                except Exception as e:
                    print(f"Erro ao salvar foto {i}: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'RDO criado com sucesso',
            'rdo': {
                'id': rdo.id,
                'data_relatorio': rdo.data_relatorio.isoformat(),
                'obra': obra.nome,
                'clima': rdo.clima,
                'observacoes': rdo.observacoes,
                'fotos_salvas': len(fotos_salvas)
            }
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao criar RDO: {str(e)}'}), 500

@mobile_api.route('/obras/listar', methods=['GET'])
@mobile_auth_required
def mobile_listar_obras():
    """Lista obras para mobile"""
    try:
        obras = Obra.query.filter_by(status='Em andamento').all()
        
        lista_obras = []
        for obra in obras:
            lista_obras.append({
                'id': obra.id,
                'nome': obra.nome,
                'endereco': obra.endereco,
                'status': obra.status,
                'orcamento': float(obra.orcamento_total or 0),
                'data_inicio': obra.data_inicio.isoformat() if obra.data_inicio else None,
                'data_fim_prevista': obra.data_fim_prevista.isoformat() if obra.data_fim_prevista else None
            })
        
        return jsonify({
            'success': True,
            'obras': lista_obras,
            'total': len(lista_obras)
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao listar obras: {str(e)}'}), 500

@mobile_api.route('/veiculos/usar', methods=['POST'])
@mobile_auth_required
def mobile_usar_veiculo():
    """Registra uso de veículo via mobile"""
    try:
        data = request.get_json()
        
        veiculo_id = data.get('veiculo_id')
        km_inicial = data.get('km_inicial')
        km_final = data.get('km_final')
        destino = data.get('destino')
        observacoes = data.get('observacoes', '')
        
        if not all([veiculo_id, km_inicial, destino]):
            return jsonify({'error': 'Dados obrigatórios: veiculo_id, km_inicial, destino'}), 400
        
        # 🔒 SEGURANÇA MULTITENANT: Verificar se veículo pertence à empresa do usuário
        from utils.tenant import get_tenant_admin_id
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado. Usuário não autenticado.'}), 403
        
        # Verificar se veículo existe E pertence à empresa
        veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            return jsonify({'error': 'Veículo não encontrado ou acesso negado'}), 404
        
        # Criar registro de uso
        uso = UsoVeiculo(
            veiculo_id=veiculo_id,
            usuario_id=current_user.id,
            data=date.today(),
            km_inicial=float(km_inicial),
            km_final=float(km_final) if km_final else None,
            destino=destino,
            observacoes=observacoes
        )
        
        db.session.add(uso)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensagem': 'Uso de veículo registrado',
            'uso': {
                'id': uso.id,
                'veiculo': f"{veiculo.modelo} - {veiculo.placa}",
                'km_inicial': uso.km_inicial,
                'km_final': uso.km_final,
                'destino': uso.destino,
                'data': uso.data.isoformat()
            }
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao registrar uso: {str(e)}'}), 500

@mobile_api.route('/notificacoes', methods=['GET'])
@mobile_auth_required
def mobile_notificacoes():
    """Lista notificações para mobile"""
    try:
        # Simulação de notificações (implementar sistema real)
        notificacoes = [
            {
                'id': 1,
                'titulo': 'Lembrete de Ponto',
                'mensagem': 'Não esqueça de registrar sua saída',
                'tipo': 'lembrete',
                'lida': False,
                'data': datetime.now().isoformat(),
                'icone': 'clock'
            },
            {
                'id': 2,
                'titulo': 'RDO Aprovado',
                'mensagem': 'Seu RDO de ontem foi aprovado',
                'tipo': 'sucesso',
                'lida': True,
                'data': (datetime.now() - timedelta(hours=2)).isoformat(),
                'icone': 'check'
            }
        ]
        
        return jsonify({
            'success': True,
            'notificacoes': notificacoes,
            'nao_lidas': len([n for n in notificacoes if not n['lida']])
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao carregar notificações: {str(e)}'}), 500

@mobile_api.route('/config/sincronizacao', methods=['GET'])
@mobile_auth_required
def mobile_config_sincronizacao():
    """Configurações de sincronização para mobile"""
    return jsonify({
        'sync_interval': 300,  # 5 minutos
        'offline_mode': True,
        'auto_backup': True,
        'compress_photos': True,
        'max_photo_size': 1024,  # KB
        'endpoints': {
            'ponto': '/api/mobile/ponto/registrar',
            'rdo': '/api/mobile/rdo/criar',
            'veiculo': '/api/mobile/veiculos/usar'
        }
    })

# Registrar blueprint na aplicação
def registrar_mobile_api(app):
    """Registra APIs mobile na aplicação"""
    app.register_blueprint(mobile_api)
    print("📱 APIs Mobile registradas com sucesso")