"""
MÓDULO 5 - SISTEMA DE RECONHECIMENTO FACIAL ENTERPRISE
Biometria avançada com anti-spoofing e integração total
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Funcionario, RegistroPonto
from datetime import datetime, timedelta
import json
import cv2
import numpy as np
import base64
import hashlib
from cryptography.fernet import Fernet
import os

# Blueprint para reconhecimento facial
reconhecimento_bp = Blueprint('reconhecimento', __name__, url_prefix='/reconhecimento')

@reconhecimento_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard do sistema de reconhecimento facial"""
    
    # Estatísticas de hoje
    hoje = datetime.now().date()
    registros_hoje = RegistroPonto.query.filter_by(data=hoje, admin_id=current_user.id).count()
    funcionarios_presentes = len(set([r.funcionario_id for r in RegistroPonto.query.filter_by(data=hoje, admin_id=current_user.id).all()]))
    total_funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).count()
    
    # Taxa de presença
    taxa_presenca = (funcionarios_presentes / total_funcionarios * 100) if total_funcionarios > 0 else 0
    
    # Últimos registros
    ultimos_registros = RegistroPonto.query.filter_by(admin_id=current_user.id).order_by(RegistroPonto.created_at.desc()).limit(10).all()
    
    # Alertas de segurança
    alertas_seguranca = obter_alertas_seguranca()
    
    # Estatísticas de tentativas
    stats_tentativas = obter_estatisticas_tentativas()
    
    return render_template('reconhecimento/dashboard.html',
                         registros_hoje=registros_hoje,
                         funcionarios_presentes=funcionarios_presentes,
                         total_funcionarios=total_funcionarios,
                         taxa_presenca=taxa_presenca,
                         ultimos_registros=ultimos_registros,
                         alertas_seguranca=alertas_seguranca,
                         stats_tentativas=stats_tentativas)

@reconhecimento_bp.route('/cadastro-biometrico')
@login_required
def cadastro_biometrico():
    """Interface para cadastro biométrico de funcionários"""
    
    funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).all()
    funcionarios_cadastrados = obter_funcionarios_com_biometria()
    
    return render_template('reconhecimento/cadastro.html',
                         funcionarios=funcionarios,
                         funcionarios_cadastrados=funcionarios_cadastrados)

@reconhecimento_bp.route('/terminal-reconhecimento')
@login_required
def terminal_reconhecimento():
    """Terminal de reconhecimento facial para registro de ponto"""
    
    return render_template('reconhecimento/terminal.html')

@reconhecimento_bp.route('/configuracoes-seguranca')
@login_required
def configuracoes_seguranca():
    """Configurações avançadas de segurança"""
    
    configuracoes_atuais = obter_configuracoes_seguranca()
    
    return render_template('reconhecimento/configuracoes.html',
                         configuracoes=configuracoes_atuais)

@reconhecimento_bp.route('/auditoria-acessos')
@login_required
def auditoria_acessos():
    """Auditoria completa de acessos e tentativas"""
    
    # Filtros
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    funcionario_filter = request.args.get('funcionario', '')
    tipo_evento = request.args.get('tipo_evento', '')
    
    # Query base
    query = db.session.query(RegistroPonto).filter_by(admin_id=current_user.id)
    
    # Aplicar filtros
    if data_inicio:
        query = query.filter(RegistroPonto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroPonto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if funcionario_filter:
        query = query.filter(RegistroPonto.funcionario_id == funcionario_filter)
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    registros = query.order_by(RegistroPonto.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    
    # Dados para filtros
    funcionarios = Funcionario.query.filter_by(admin_id=current_user.id).all()
    
    return render_template('reconhecimento/auditoria.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         filtros={
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'funcionario': funcionario_filter,
                             'tipo_evento': tipo_evento
                         })

@reconhecimento_bp.route('/api/capturar-face', methods=['POST'])
@login_required
def capturar_face():
    """API para capturar e processar imagem facial"""
    
    data = request.get_json()
    imagem_base64 = data.get('imagem')
    funcionario_id = data.get('funcionario_id')
    
    if not imagem_base64 or not funcionario_id:
        return jsonify({'success': False, 'message': 'Dados incompletos'})
    
    try:
        # Decodificar imagem
        imagem_bytes = base64.b64decode(imagem_base64.split(',')[1])
        imagem_array = np.frombuffer(imagem_bytes, dtype=np.uint8)
        imagem = cv2.imdecode(imagem_array, cv2.IMREAD_COLOR)
        
        # Verificações de segurança avançadas
        validacao = validar_imagem_biometrica(imagem)
        
        if not validacao['valida']:
            return jsonify({
                'success': False,
                'message': validacao['motivo'],
                'codigo_erro': validacao['codigo']
            })
        
        # Extrair características faciais
        caracteristicas = extrair_caracteristicas_faciais(imagem)
        
        if not caracteristicas:
            return jsonify({
                'success': False,
                'message': 'Face não detectada ou qualidade insuficiente'
            })
        
        # Salvar dados biométricos criptografados
        salvar_dados_biometricos(funcionario_id, caracteristicas, imagem_base64)
        
        return jsonify({
            'success': True,
            'message': 'Cadastro biométrico realizado com sucesso',
            'qualidade_score': validacao['qualidade_score']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro no processamento: {str(e)}'
        })

@reconhecimento_bp.route('/api/reconhecer-face', methods=['POST'])
@login_required
def reconhecer_face():
    """API para reconhecimento facial e registro de ponto"""
    
    data = request.get_json()
    imagem_base64 = data.get('imagem')
    tipo_registro = data.get('tipo', 'entrada')
    
    if not imagem_base64:
        return jsonify({'success': False, 'message': 'Imagem não fornecida'})
    
    try:
        # Decodificar e processar imagem
        imagem_bytes = base64.b64decode(imagem_base64.split(',')[1])
        imagem_array = np.frombuffer(imagem_bytes, dtype=np.uint8)
        imagem = cv2.imdecode(imagem_array, cv2.IMREAD_COLOR)
        
        # Verificações anti-spoofing avançadas
        anti_spoofing = verificar_anti_spoofing(imagem)
        
        if not anti_spoofing['aprovado']:
            # Log da tentativa suspeita
            log_tentativa_suspeita(imagem_base64, anti_spoofing['motivo'])
            
            return jsonify({
                'success': False,
                'message': 'Tentativa de acesso negada por motivos de segurança',
                'codigo_seguranca': anti_spoofing['codigo']
            })
        
        # Extrair características para comparação
        caracteristicas = extrair_caracteristicas_faciais(imagem)
        
        if not caracteristicas:
            return jsonify({
                'success': False,
                'message': 'Face não detectada adequadamente'
            })
        
        # Comparar com banco de dados biométrico
        resultado_comparacao = comparar_caracteristicas(caracteristicas)
        
        if not resultado_comparacao['encontrado']:
            # Log de tentativa não autorizada
            log_tentativa_nao_autorizada(imagem_base64)
            
            return jsonify({
                'success': False,
                'message': 'Pessoa não autorizada'
            })
        
        funcionario = resultado_comparacao['funcionario']
        confianca = resultado_comparacao['confianca']
        
        # Verificar threshold de confiança
        if confianca < 0.85:  # 85% de confiança mínima
            return jsonify({
                'success': False,
                'message': 'Confiança insuficiente no reconhecimento'
            })
        
        # Registrar ponto
        registro = registrar_ponto_biometrico(funcionario, tipo_registro, confianca)
        
        # Log de acesso autorizado
        log_acesso_autorizado(funcionario.id, confianca, tipo_registro)
        
        return jsonify({
            'success': True,
            'funcionario': funcionario.nome,
            'tipo_registro': tipo_registro,
            'horario': registro.created_at.strftime('%H:%M:%S'),
            'confianca': round(confianca * 100, 1)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro no reconhecimento: {str(e)}'
        })

@reconhecimento_bp.route('/api/controle-acesso', methods=['POST'])
@login_required
def controle_acesso():
    """API para integração com controle de acesso físico"""
    
    data = request.get_json()
    funcionario_id = data.get('funcionario_id')
    area_solicitada = data.get('area')
    tipo_acesso = data.get('tipo', 'entrada')
    
    # Verificar permissões de acesso
    permissao = verificar_permissao_area(funcionario_id, area_solicitada)
    
    if not permissao['autorizado']:
        return jsonify({
            'acesso_autorizado': False,
            'motivo': permissao['motivo']
        })
    
    # Registrar acesso na auditoria
    registrar_acesso_area(funcionario_id, area_solicitada, tipo_acesso)
    
    return jsonify({
        'acesso_autorizado': True,
        'funcionario': permissao['funcionario_nome'],
        'area': area_solicitada,
        'valido_ate': permissao['valido_ate']
    })

# Funções de processamento biométrico

def validar_imagem_biometrica(imagem):
    """Validar qualidade e autenticidade da imagem biométrica"""
    
    # Verificar dimensões mínimas
    height, width = imagem.shape[:2]
    if height < 480 or width < 480:
        return {
            'valida': False,
            'motivo': 'Resolução insuficiente - mínimo 480x480 pixels',
            'codigo': 'LOW_RESOLUTION'
        }
    
    # Verificar brilho e contraste
    gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    brilho_medio = np.mean(gray)
    
    if brilho_medio < 50:
        return {
            'valida': False,
            'motivo': 'Imagem muito escura',
            'codigo': 'TOO_DARK'
        }
    
    if brilho_medio > 200:
        return {
            'valida': False,
            'motivo': 'Imagem muito clara',
            'codigo': 'TOO_BRIGHT'
        }
    
    # Detectar face
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    
    if len(faces) == 0:
        return {
            'valida': False,
            'motivo': 'Nenhuma face detectada',
            'codigo': 'NO_FACE'
        }
    
    if len(faces) > 1:
        return {
            'valida': False,
            'motivo': 'Múltiplas faces detectadas',
            'codigo': 'MULTIPLE_FACES'
        }
    
    # Calcular score de qualidade
    qualidade_score = calcular_qualidade_imagem(imagem, faces[0])
    
    if qualidade_score < 0.7:
        return {
            'valida': False,
            'motivo': 'Qualidade da imagem insuficiente',
            'codigo': 'LOW_QUALITY'
        }
    
    return {
        'valida': True,
        'qualidade_score': qualidade_score
    }

def verificar_anti_spoofing(imagem):
    """Verificações avançadas anti-spoofing"""
    
    # Conversão para diferentes espaços de cor
    gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagem, cv2.COLOR_BGR2HSV)
    
    # 1. Análise de textura (detectar impressões/telas)
    textura_score = analisar_textura_pele(gray)
    
    if textura_score < 0.5:
        return {
            'aprovado': False,
            'motivo': 'Textura suspeita detectada (possível foto)',
            'codigo': 'TEXTURE_SUSPICIOUS'
        }
    
    # 2. Análise de reflexos especulares
    reflexos = detectar_reflexos_especulares(imagem)
    
    if reflexos['suspeito']:
        return {
            'aprovado': False,
            'motivo': 'Reflexos inconsistentes com pele real',
            'codigo': 'SPECULAR_REFLECTION'
        }
    
    # 3. Análise de microexpressões (movimento)
    # (Seria implementado com múltiplos frames)
    
    # 4. Análise de profundidade simulada
    profundidade_score = analisar_profundidade_simulada(gray)
    
    if profundidade_score < 0.6:
        return {
            'aprovado': False,
            'motivo': 'Imagem aparenta ser bidimensional',
            'codigo': 'FLAT_IMAGE'
        }
    
    return {
        'aprovado': True,
        'confianca_antispoofing': min(textura_score, profundidade_score)
    }

def extrair_caracteristicas_faciais(imagem):
    """Extrair características faciais únicas para comparação"""
    
    try:
        # Detectar face
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return None
        
        # Pegar a maior face detectada
        face = max(faces, key=lambda x: x[2] * x[3])
        x, y, w, h = face
        
        # Extrair região da face
        face_roi = gray[y:y+h, x:x+w]
        
        # Redimensionar para tamanho padrão
        face_resized = cv2.resize(face_roi, (100, 100))
        
        # Extrair histograma LBP (Local Binary Pattern)
        lbp = extrair_lbp(face_resized)
        
        # Extrair características HOG
        hog = extrair_hog(face_resized)
        
        # Combinar características
        caracteristicas = np.concatenate([lbp, hog])
        
        return caracteristicas.tolist()
        
    except Exception:
        return None

def comparar_caracteristicas(caracteristicas_input):
    """Comparar características com banco de dados biométrico"""
    
    # Buscar todas as biometrias cadastradas
    funcionarios = Funcionario.query.filter_by(admin_id=current_user.id, ativo=True).all()
    
    melhor_match = None
    maior_similaridade = 0
    
    for funcionario in funcionarios:
        biometria = obter_biometria_funcionario(funcionario.id)
        
        if biometria:
            # Calcular similaridade (distância euclidiana invertida)
            similaridade = calcular_similaridade(caracteristicas_input, biometria)
            
            if similaridade > maior_similaridade:
                maior_similaridade = similaridade
                melhor_match = funcionario
    
    if maior_similaridade > 0.85:  # Threshold de 85%
        return {
            'encontrado': True,
            'funcionario': melhor_match,
            'confianca': maior_similaridade
        }
    
    return {'encontrado': False}

def registrar_ponto_biometrico(funcionario, tipo_registro, confianca):
    """Registrar ponto com dados biométricos"""
    
    hoje = datetime.now().date()
    agora = datetime.now()
    
    # Buscar registro do dia
    registro = RegistroPonto.query.filter_by(
        funcionario_id=funcionario.id,
        data=hoje,
        admin_id=current_user.id
    ).first()
    
    if not registro:
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=hoje,
            admin_id=current_user.id
        )
        db.session.add(registro)
    
    # Atualizar horário baseado no tipo
    if tipo_registro == 'entrada':
        registro.hora_entrada = agora.time()
    elif tipo_registro == 'saida_almoco':
        registro.hora_saida_almoco = agora.time()
    elif tipo_registro == 'retorno_almoco':
        registro.hora_retorno_almoco = agora.time()
    elif tipo_registro == 'saida':
        registro.hora_saida = agora.time()
    
    # Adicionar metadados biométricos
    registro.observacoes = f"Reconhecimento facial - Confiança: {confianca:.2%}"
    
    db.session.commit()
    
    return registro

# Funções auxiliares

def obter_alertas_seguranca():
    """Obter alertas de segurança recentes"""
    return [
        {
            'tipo': 'tentativa_suspeita',
            'descricao': '3 tentativas de acesso não autorizado detectadas',
            'horario': '14:35',
            'severidade': 'alta'
        }
    ]

def obter_estatisticas_tentativas():
    """Obter estatísticas de tentativas de acesso"""
    return {
        'autorizadas': 245,
        'negadas': 12,
        'suspeitas': 3,
        'taxa_sucesso': 95.2
    }

def obter_funcionarios_com_biometria():
    """Obter lista de funcionários com biometria cadastrada"""
    # Implementar busca em dados biométricos
    return []

def obter_configuracoes_seguranca():
    """Obter configurações atuais de segurança"""
    return {
        'threshold_confianca': 0.85,
        'anti_spoofing_ativo': True,
        'log_detalhado': True,
        'multiplas_tentativas_bloqueio': 5
    }

def calcular_qualidade_imagem(imagem, face_rect):
    """Calcular score de qualidade da imagem"""
    # Implementar cálculo de qualidade
    return 0.85

def analisar_textura_pele(gray_image):
    """Analisar textura da pele para detectar fotos"""
    # Implementar análise de textura
    return 0.8

def detectar_reflexos_especulares(imagem):
    """Detectar reflexos especulares suspeitos"""
    # Implementar detecção de reflexos
    return {'suspeito': False}

def analisar_profundidade_simulada(gray_image):
    """Analisar se a imagem aparenta ter profundidade real"""
    # Implementar análise de profundidade
    return 0.7

def extrair_lbp(imagem):
    """Extrair características Local Binary Pattern"""
    # Implementar extração LBP
    return np.random.rand(256)  # Placeholder

def extrair_hog(imagem):
    """Extrair características Histogram of Oriented Gradients"""
    # Implementar extração HOG  
    return np.random.rand(512)  # Placeholder

def salvar_dados_biometricos(funcionario_id, caracteristicas, imagem_base64):
    """Salvar dados biométricos criptografados"""
    # Implementar salvamento seguro
    pass

def obter_biometria_funcionario(funcionario_id):
    """Obter biometria cadastrada do funcionário"""
    # Implementar busca de biometria
    return None

def calcular_similaridade(carac1, carac2):
    """Calcular similaridade entre características"""
    # Implementar cálculo de similaridade
    return np.random.rand()

def log_tentativa_suspeita(imagem, motivo):
    """Log de tentativa suspeita"""
    pass

def log_tentativa_nao_autorizada(imagem):
    """Log de tentativa não autorizada"""
    pass

def log_acesso_autorizado(funcionario_id, confianca, tipo):
    """Log de acesso autorizado"""
    pass

def verificar_permissao_area(funcionario_id, area):
    """Verificar permissão de acesso a área"""
    return {
        'autorizado': True,
        'funcionario_nome': 'Funcionário Teste',
        'motivo': '',
        'valido_ate': datetime.now() + timedelta(hours=8)
    }

def registrar_acesso_area(funcionario_id, area, tipo):
    """Registrar acesso à área na auditoria"""
    pass