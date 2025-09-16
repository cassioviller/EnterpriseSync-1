"""
Sistema Avançado de Gestão de Custos de Veículos
Módulo de views para funcionalidades avançadas de controle de custos,
manutenções, documentos fiscais e relatórios financeiros.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort, current_app, send_file
from flask_login import login_required, current_user
from sqlalchemy import func, text, desc, asc, and_, or_, extract
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta
import json
import io
import logging
from decimal import Decimal

# Importações dos modelos e formulários
from app import db
from models import (Veiculo, CustoVeiculo, UsoVeiculo, ManutencaoVeiculo, 
                   DocumentoFiscal, AlertaVeiculo, Usuario, Obra, TipoUsuario)
from forms import (CustoVeiculoForm, ManutencaoVeiculoForm, DocumentoFiscalForm, 
                  AlertaVeiculoForm, FiltroVeiculosForm, RelatorioTCOForm)
from auth import admin_required
try:
    from utils.circuit_breaker import database_heavy_query_breaker, pdf_generation_breaker
except ImportError:
    # Fallback caso não tenha circuit breaker
    class DummyBreaker:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    database_heavy_query_breaker = DummyBreaker()
    pdf_generation_breaker = DummyBreaker()

# Configurar logging
logger = logging.getLogger(__name__)

# Criar blueprint para sistema avançado de veículos
veiculos_avancado_bp = Blueprint('veiculos_avancado', __name__, url_prefix='/veiculos-avancado')

# =============================================
# FUNÇÕES AUXILIARES
# =============================================

def get_admin_id():
    """Obtém admin_id baseado no tipo de usuário"""
    return current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id

def calcular_kpis_veiculo(veiculo_id, admin_id, periodo_dias=30):
    """Calcula KPIs básicos de um veículo"""
    try:
        data_limite = date.today() - timedelta(days=periodo_dias)
        
        # Custos do período
        custos_periodo = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.veiculo_id == veiculo_id,
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_limite
        ).scalar() or 0
        
        # Média de custos mensais
        custos_mensais = db.session.query(
            func.extract('month', CustoVeiculo.data_custo).label('mes'),
            func.sum(CustoVeiculo.valor).label('total')
        ).filter(
            CustoVeiculo.veiculo_id == veiculo_id,
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= date.today() - timedelta(days=365)
        ).group_by(func.extract('month', CustoVeiculo.data_custo)).all()
        
        media_mensal = sum([c.total for c in custos_mensais]) / len(custos_mensais) if custos_mensais else 0
        
        # KM percorrido no período
        usos_periodo = db.session.query(func.sum(UsoVeiculo.km_percorrido)).filter(
            UsoVeiculo.veiculo_id == veiculo_id,
            UsoVeiculo.admin_id == admin_id,
            UsoVeiculo.data_uso >= data_limite,
            UsoVeiculo.km_percorrido.isnot(None)
        ).scalar() or 0
        
        # Custo por KM
        custo_por_km = custos_periodo / usos_periodo if usos_periodo > 0 else 0
        
        # Últimas manutenções
        ultima_manutencao = db.session.query(ManutencaoVeiculo).filter(
            ManutencaoVeiculo.veiculo_id == veiculo_id,
            ManutencaoVeiculo.admin_id == admin_id
        ).order_by(desc(ManutencaoVeiculo.data_manutencao)).first()
        
        return {
            'custos_periodo': custos_periodo,
            'media_mensal': media_mensal,
            'km_periodo': usos_periodo,
            'custo_por_km': custo_por_km,
            'ultima_manutencao': ultima_manutencao
        }
    except Exception as e:
        logger.error(f"Erro ao calcular KPIs do veículo {veiculo_id}: {str(e)}")
        return {}

# =============================================
# ROTAS PARA MANUTENÇÕES
# =============================================

@veiculos_avancado_bp.route('/manutencoes')
@admin_required
def lista_manutencoes():
    """Lista todas as manutenções com filtros avançados"""
    try:
        admin_id = get_admin_id()
        
        # Filtros básicos
        veiculo_id = request.args.get('veiculo_id', type=int)
        categoria = request.args.get('categoria')
        tipo_manutencao = request.args.get('tipo_manutencao')
        status = request.args.get('status')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Query base
        query = db.session.query(ManutencaoVeiculo).filter(
            ManutencaoVeiculo.admin_id == admin_id
        ).options(joinedload(ManutencaoVeiculo.veiculo))
        
        # Aplicar filtros
        if veiculo_id:
            query = query.filter(ManutencaoVeiculo.veiculo_id == veiculo_id)
        if categoria:
            query = query.filter(ManutencaoVeiculo.categoria == categoria)
        if tipo_manutencao:
            query = query.filter(ManutencaoVeiculo.tipo_manutencao == tipo_manutencao)
        if status:
            query = query.filter(ManutencaoVeiculo.status == status)
        if data_inicio:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            query = query.filter(ManutencaoVeiculo.data_manutencao >= data_inicio_obj)
        if data_fim:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            query = query.filter(ManutencaoVeiculo.data_manutencao <= data_fim_obj)
        
        # Ordenação
        query = query.order_by(desc(ManutencaoVeiculo.data_manutencao))
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        manutencoes = query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Veículos para filtro
        veiculos = db.session.query(Veiculo).filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True
        ).all()
        
        # Estatísticas básicas
        total_manutencoes = query.count()
        valor_total_mes = db.session.query(func.sum(ManutencaoVeiculo.valor_total)).filter(
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.data_manutencao >= date.today().replace(day=1)
        ).scalar() or 0
        
        # Próximas manutenções vencidas
        manutencoes_vencidas = db.session.query(Veiculo).join(
            ManutencaoVeiculo, Veiculo.id == ManutencaoVeiculo.veiculo_id
        ).filter(
            Veiculo.admin_id == admin_id,
            or_(
                ManutencaoVeiculo.proxima_manutencao_data < date.today(),
                and_(
                    ManutencaoVeiculo.proxima_manutencao_km < Veiculo.km_atual,
                    ManutencaoVeiculo.proxima_manutencao_km.isnot(None),
                    Veiculo.km_atual.isnot(None)
                )
            )
        ).distinct().count()
        
        estatisticas = {
            'total_manutencoes': total_manutencoes,
            'valor_total_mes': valor_total_mes,
            'manutencoes_vencidas': manutencoes_vencidas
        }
        
        return render_template('veiculos_avancado/lista_manutencoes.html',
                             manutencoes=manutencoes,
                             veiculos=veiculos,
                             estatisticas=estatisticas,
                             filtros=request.args)
        
    except Exception as e:
        logger.error(f"Erro ao listar manutenções: {str(e)}")
        flash('Erro ao carregar lista de manutenções.', 'error')
        return redirect(url_for('main.index'))

@veiculos_avancado_bp.route('/manutencoes/nova/<int:veiculo_id>', methods=['GET', 'POST'])
@admin_required
def nova_manutencao(veiculo_id):
    """Cadastra nova manutenção"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se veículo existe e pertence ao admin
        veiculo = db.session.query(Veiculo).filter(
            Veiculo.id == veiculo_id,
            Veiculo.admin_id == admin_id
        ).first_or_404()
        
        form = ManutencaoVeiculoForm()
        form.veiculo_id.data = veiculo_id
        
        if form.validate_on_submit():
            try:
                # Criar nova manutenção
                manutencao = ManutencaoVeiculo(
                    veiculo_id=veiculo_id,
                    tipo_manutencao=form.tipo_manutencao.data,
                    categoria=form.categoria.data,
                    prioridade=form.prioridade.data,
                    data_manutencao=form.data_manutencao.data,
                    km_manutencao=form.km_manutencao.data,
                    descricao=form.descricao.data,
                    pecas_utilizadas=form.pecas_utilizadas.data,
                    servicos_executados=form.servicos_executados.data,
                    valor_pecas=form.valor_pecas.data or 0.0,
                    valor_mao_obra=form.valor_mao_obra.data or 0.0,
                    valor_total=form.valor_total.data,
                    oficina=form.oficina.data,
                    mecanico_responsavel=form.mecanico_responsavel.data,
                    numero_os=form.numero_os.data,
                    garantia_meses=form.garantia_meses.data or 3,
                    garantia_km=form.garantia_km.data or 10000,
                    proxima_manutencao_km=form.proxima_manutencao_km.data,
                    proxima_manutencao_data=form.proxima_manutencao_data.data,
                    intervalo_km=form.intervalo_km.data,
                    intervalo_meses=form.intervalo_meses.data,
                    status=form.status.data,
                    observacoes=form.observacoes.data,
                    admin_id=admin_id
                )
                
                # Calcular próxima manutenção automaticamente se não informada
                if not form.proxima_manutencao_km.data or not form.proxima_manutencao_data.data:
                    manutencao.calcular_proxima_manutencao()
                
                db.session.add(manutencao)
                
                # Criar custo associado se não existir
                if not form.custo_veiculo_id.data:
                    custo = CustoVeiculo(
                        veiculo_id=veiculo_id,
                        data_custo=form.data_manutencao.data,
                        valor=form.valor_total.data,
                        tipo_custo='manutencao',
                        descricao=f"Manutenção {form.categoria.data}: {form.descricao.data}",
                        km_atual=form.km_manutencao.data,
                        categoria_manutencao=form.categoria.data,
                        admin_id=admin_id
                    )
                    db.session.add(custo)
                    db.session.flush()  # Para obter o ID
                    manutencao.custo_veiculo_id = custo.id
                
                db.session.commit()
                
                logger.info(f"Manutenção criada: Admin {admin_id}, Veículo {veiculo_id}, Valor R$ {form.valor_total.data}")
                flash(f'Manutenção de {form.categoria.data} registrada com sucesso!', 'success')
                return redirect(url_for('veiculos_avancado.detalhes_manutencao', id=manutencao.id))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao salvar manutenção: {str(e)}")
                flash('Erro ao registrar manutenção. Tente novamente.', 'error')
        
        return render_template('veiculos_avancado/nova_manutencao.html',
                             form=form, veiculo=veiculo)
        
    except Exception as e:
        logger.error(f"Erro na nova manutenção: {str(e)}")
        flash('Erro ao acessar formulário de manutenção.', 'error')
        return redirect(url_for('veiculos_avancado.lista_manutencoes'))

@veiculos_avancado_bp.route('/manutencoes/<int:id>')
@admin_required
def detalhes_manutencao(id):
    """Exibe detalhes de uma manutenção específica"""
    try:
        admin_id = get_admin_id()
        
        manutencao = db.session.query(ManutencaoVeiculo).options(
            joinedload(ManutencaoVeiculo.veiculo),
            joinedload(ManutencaoVeiculo.custo_veiculo),
            joinedload(ManutencaoVeiculo.documentos_fiscais)
        ).filter(
            ManutencaoVeiculo.id == id,
            ManutencaoVeiculo.admin_id == admin_id
        ).first_or_404()
        
        # Histórico de manutenções do mesmo veículo
        historico = db.session.query(ManutencaoVeiculo).filter(
            ManutencaoVeiculo.veiculo_id == manutencao.veiculo_id,
            ManutencaoVeiculo.admin_id == admin_id,
            ManutencaoVeiculo.id != id
        ).order_by(desc(ManutencaoVeiculo.data_manutencao)).limit(10).all()
        
        # Alertas relacionados
        alertas = db.session.query(AlertaVeiculo).filter(
            AlertaVeiculo.veiculo_id == manutencao.veiculo_id,
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.tipo_alerta == 'manutencao_vencida',
            AlertaVeiculo.ativo == True
        ).all()
        
        return render_template('veiculos_avancado/detalhes_manutencao.html',
                             manutencao=manutencao,
                             historico=historico,
                             alertas=alertas)
        
    except Exception as e:
        logger.error(f"Erro ao carregar detalhes da manutenção {id}: {str(e)}")
        flash('Erro ao carregar detalhes da manutenção.', 'error')
        return redirect(url_for('veiculos_avancado.lista_manutencoes'))

# =============================================
# ROTAS PARA DOCUMENTOS FISCAIS
# =============================================

@veiculos_avancado_bp.route('/documentos')
@admin_required
def lista_documentos():
    """Lista documentos fiscais com filtros"""
    try:
        admin_id = get_admin_id()
        
        # Filtros
        veiculo_id = request.args.get('veiculo_id', type=int)
        tipo_documento = request.args.get('tipo_documento')
        validado = request.args.get('validado')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Query base
        query = db.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.admin_id == admin_id
        ).options(joinedload(DocumentoFiscal.veiculo))
        
        # Aplicar filtros
        if veiculo_id:
            query = query.filter(DocumentoFiscal.veiculo_id == veiculo_id)
        if tipo_documento:
            query = query.filter(DocumentoFiscal.tipo_documento == tipo_documento)
        if validado == 'sim':
            query = query.filter(DocumentoFiscal.validado == True)
        elif validado == 'nao':
            query = query.filter(DocumentoFiscal.validado == False)
        if data_inicio:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            query = query.filter(DocumentoFiscal.data_emissao >= data_inicio_obj)
        if data_fim:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
            query = query.filter(DocumentoFiscal.data_emissao <= data_fim_obj)
        
        # Ordenação
        query = query.order_by(desc(DocumentoFiscal.data_emissao))
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        documentos = query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Veículos para filtro
        veiculos = db.session.query(Veiculo).filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True
        ).all()
        
        # Estatísticas
        total_documentos = query.count()
        valor_total = db.session.query(func.sum(DocumentoFiscal.valor_documento)).filter(
            DocumentoFiscal.admin_id == admin_id
        ).scalar() or 0
        documentos_pendentes = db.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.admin_id == admin_id,
            DocumentoFiscal.validado == False
        ).count()
        
        estatisticas = {
            'total_documentos': total_documentos,
            'valor_total': valor_total,
            'documentos_pendentes': documentos_pendentes
        }
        
        return render_template('veiculos_avancado/lista_documentos.html',
                             documentos=documentos,
                             veiculos=veiculos,
                             estatisticas=estatisticas,
                             filtros=request.args)
        
    except Exception as e:
        logger.error(f"Erro ao listar documentos: {str(e)}")
        flash('Erro ao carregar lista de documentos.', 'error')
        return redirect(url_for('main.index'))

@veiculos_avancado_bp.route('/documentos/novo/<int:veiculo_id>', methods=['GET', 'POST'])
@admin_required
def novo_documento(veiculo_id):
    """Cadastra novo documento fiscal"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se veículo existe
        veiculo = db.session.query(Veiculo).filter(
            Veiculo.id == veiculo_id,
            Veiculo.admin_id == admin_id
        ).first_or_404()
        
        form = DocumentoFiscalForm()
        form.veiculo_id.data = veiculo_id
        
        if form.validate_on_submit():
            try:
                documento = DocumentoFiscal(
                    veiculo_id=veiculo_id,
                    custo_veiculo_id=form.custo_veiculo_id.data or None,
                    manutencao_id=form.manutencao_id.data or None,
                    tipo_documento=form.tipo_documento.data,
                    numero_documento=form.numero_documento.data,
                    serie=form.serie.data,
                    data_emissao=form.data_emissao.data,
                    valor_documento=form.valor_documento.data,
                    cnpj_emissor=form.cnpj_emissor.data,
                    nome_emissor=form.nome_emissor.data,
                    endereco_emissor=form.endereco_emissor.data,
                    valor_icms=form.valor_icms.data or 0.0,
                    valor_pis=form.valor_pis.data or 0.0,
                    valor_cofins=form.valor_cofins.data or 0.0,
                    valor_iss=form.valor_iss.data or 0.0,
                    valor_desconto=form.valor_desconto.data or 0.0,
                    observacoes_validacao=form.observacoes_validacao.data,
                    admin_id=admin_id
                )
                
                # TODO: Implementar upload de arquivo digitalizado
                
                db.session.add(documento)
                db.session.commit()
                
                logger.info(f"Documento fiscal criado: Admin {admin_id}, Veículo {veiculo_id}, Valor R$ {form.valor_documento.data}")
                flash(f'Documento {form.tipo_documento.data} registrado com sucesso!', 'success')
                return redirect(url_for('veiculos_avancado.lista_documentos'))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao salvar documento: {str(e)}")
                flash('Erro ao registrar documento. Tente novamente.', 'error')
        
        return render_template('veiculos_avancado/novo_documento.html',
                             form=form, veiculo=veiculo)
        
    except Exception as e:
        logger.error(f"Erro no novo documento: {str(e)}")
        flash('Erro ao acessar formulário de documento.', 'error')
        return redirect(url_for('veiculos_avancado.lista_documentos'))

# =============================================
# ROTAS PARA ALERTAS
# =============================================

@veiculos_avancado_bp.route('/alertas')
@admin_required
def lista_alertas():
    """Lista alertas ativos com filtros"""
    try:
        admin_id = get_admin_id()
        
        # Filtros
        veiculo_id = request.args.get('veiculo_id', type=int)
        tipo_alerta = request.args.get('tipo_alerta')
        categoria = request.args.get('categoria')
        ativo = request.args.get('ativo', 'sim')
        
        # Query base
        query = db.session.query(AlertaVeiculo).filter(
            AlertaVeiculo.admin_id == admin_id
        ).options(joinedload(AlertaVeiculo.veiculo))
        
        # Aplicar filtros
        if veiculo_id:
            query = query.filter(AlertaVeiculo.veiculo_id == veiculo_id)
        if tipo_alerta:
            query = query.filter(AlertaVeiculo.tipo_alerta == tipo_alerta)
        if categoria:
            query = query.filter(AlertaVeiculo.categoria == categoria)
        if ativo == 'sim':
            query = query.filter(AlertaVeiculo.ativo == True)
        elif ativo == 'nao':
            query = query.filter(AlertaVeiculo.ativo == False)
        
        # Ordenação por prioridade e data
        query = query.order_by(
            desc(AlertaVeiculo.categoria == 'urgente'),
            desc(AlertaVeiculo.categoria == 'importante'),
            asc(AlertaVeiculo.data_vencimento)
        )
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        alertas = query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Veículos para filtro
        veiculos = db.session.query(Veiculo).filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True
        ).all()
        
        # Estatísticas
        alertas_urgentes = db.session.query(AlertaVeiculo).filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.categoria == 'urgente',
            AlertaVeiculo.ativo == True
        ).count()
        
        alertas_vencidos = db.session.query(AlertaVeiculo).filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.data_vencimento < date.today(),
            AlertaVeiculo.ativo == True
        ).count()
        
        estatisticas = {
            'alertas_urgentes': alertas_urgentes,
            'alertas_vencidos': alertas_vencidos,
            'total_ativos': query.filter(AlertaVeiculo.ativo == True).count()
        }
        
        return render_template('veiculos_avancado/lista_alertas.html',
                             alertas=alertas,
                             veiculos=veiculos,
                             estatisticas=estatisticas,
                             filtros=request.args)
        
    except Exception as e:
        logger.error(f"Erro ao listar alertas: {str(e)}")
        flash('Erro ao carregar lista de alertas.', 'error')
        return redirect(url_for('main.index'))

# =============================================
# ROTAS PARA RELATÓRIOS E DASHBOARD
# =============================================

@veiculos_avancado_bp.route('/dashboard')
@admin_required
def dashboard_financeiro():
    """Dashboard financeiro avançado para gestão de custos de veículos"""
    try:
        admin_id = get_admin_id()
        
        # Período de análise (último ano)
        data_limite = date.today() - timedelta(days=365)
        
        # KPIs principais
        with database_heavy_query_breaker:
            # Total de veículos ativos
            total_veiculos = db.session.query(Veiculo).filter(
                Veiculo.admin_id == admin_id,
                Veiculo.ativo == True
            ).count()
            
            # Custos totais do período
            custos_totais = db.session.query(func.sum(CustoVeiculo.valor)).filter(
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).scalar() or 0
            
            # Custos do mês atual
            inicio_mes = date.today().replace(day=1)
            custos_mes = db.session.query(func.sum(CustoVeiculo.valor)).filter(
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= inicio_mes
            ).scalar() or 0
            
            # Média mensal
            media_mensal = custos_totais / 12 if custos_totais > 0 else 0
            
            # Distribuição por tipo de custo
            custos_por_tipo = db.session.query(
                CustoVeiculo.tipo_custo,
                func.sum(CustoVeiculo.valor).label('total')
            ).filter(
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).group_by(CustoVeiculo.tipo_custo).all()
            
            # Top 5 veículos mais caros
            top_veiculos = db.session.query(
                Veiculo.placa,
                Veiculo.modelo,
                func.sum(CustoVeiculo.valor).label('total_custos')
            ).join(CustoVeiculo).filter(
                Veiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).group_by(Veiculo.id, Veiculo.placa, Veiculo.modelo).order_by(
                desc('total_custos')
            ).limit(5).all()
            
            # Evolução mensal de custos
            evolucao_mensal = db.session.query(
                func.extract('month', CustoVeiculo.data_custo).label('mes'),
                func.sum(CustoVeiculo.valor).label('total')
            ).filter(
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).group_by(func.extract('month', CustoVeiculo.data_custo)).order_by('mes').all()
            
            # Alertas críticos
            alertas_criticos = db.session.query(AlertaVeiculo).filter(
                AlertaVeiculo.admin_id == admin_id,
                AlertaVeiculo.categoria == 'urgente',
                AlertaVeiculo.ativo == True
            ).count()
            
            # Manutenções vencidas
            manutencoes_vencidas = db.session.query(ManutencaoVeiculo).filter(
                ManutencaoVeiculo.admin_id == admin_id,
                or_(
                    ManutencaoVeiculo.proxima_manutencao_data < date.today(),
                    and_(
                        ManutencaoVeiculo.proxima_manutencao_km < Veiculo.km_atual,
                        ManutencaoVeiculo.proxima_manutencao_km.isnot(None)
                    )
                )
            ).count()
        
        # Preparar dados para gráficos
        dados_grafico_tipos = {
            'labels': [item.tipo_custo.title() for item in custos_por_tipo],
            'values': [float(item.total) for item in custos_por_tipo]
        }
        
        dados_grafico_evolucao = {
            'labels': [f"Mês {int(item.mes)}" for item in evolucao_mensal],
            'values': [float(item.total) for item in evolucao_mensal]
        }
        
        kpis = {
            'total_veiculos': total_veiculos,
            'custos_totais': custos_totais,
            'custos_mes': custos_mes,
            'media_mensal': media_mensal,
            'alertas_criticos': alertas_criticos,
            'manutencoes_vencidas': manutencoes_vencidas,
            'custo_por_veiculo': custos_totais / total_veiculos if total_veiculos > 0 else 0
        }
        
        return render_template('veiculos_avancado/dashboard_financeiro.html',
                             kpis=kpis,
                             top_veiculos=top_veiculos,
                             dados_grafico_tipos=dados_grafico_tipos,
                             dados_grafico_evolucao=dados_grafico_evolucao)
        
    except Exception as e:
        logger.error(f"Erro no dashboard financeiro: {str(e)}")
        flash('Erro ao carregar dashboard financeiro.', 'error')
        return redirect(url_for('main.index'))

@veiculos_avancado_bp.route('/relatorio-tco/<int:veiculo_id>')
@admin_required  
def relatorio_tco(veiculo_id):
    """Relatório de TCO (Total Cost of Ownership) de um veículo"""
    try:
        admin_id = get_admin_id()
        
        # Verificar se veículo existe
        veiculo = db.session.query(Veiculo).filter(
            Veiculo.id == veiculo_id,
            Veiculo.admin_id == admin_id
        ).first_or_404()
        
        # Parâmetros do relatório
        periodo = request.args.get('periodo', '1_ano')
        
        # Definir período de análise
        if periodo == '3_meses':
            data_limite = date.today() - timedelta(days=90)
        elif periodo == '6_meses':
            data_limite = date.today() - timedelta(days=180)
        elif periodo == '2_anos':
            data_limite = date.today() - timedelta(days=730)
        else:  # 1_ano (padrão)
            data_limite = date.today() - timedelta(days=365)
        
        with database_heavy_query_breaker:
            # Custos por categoria
            custos_categoria = db.session.query(
                CustoVeiculo.tipo_custo,
                func.sum(CustoVeiculo.valor).label('total'),
                func.count(CustoVeiculo.id).label('quantidade')
            ).filter(
                CustoVeiculo.veiculo_id == veiculo_id,
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).group_by(CustoVeiculo.tipo_custo).all()
            
            # Total de custos
            total_custos = sum([c.total for c in custos_categoria])
            
            # KM percorrido no período
            km_periodo = db.session.query(func.sum(UsoVeiculo.km_percorrido)).filter(
                UsoVeiculo.veiculo_id == veiculo_id,
                UsoVeiculo.admin_id == admin_id,
                UsoVeiculo.data_uso >= data_limite,
                UsoVeiculo.km_percorrido.isnot(None)
            ).scalar() or 0
            
            # Custo por KM
            custo_por_km = total_custos / km_periodo if km_periodo > 0 else 0
            
            # Histórico mensal
            historico_mensal = db.session.query(
                func.extract('month', CustoVeiculo.data_custo).label('mes'),
                func.extract('year', CustoVeiculo.data_custo).label('ano'),
                func.sum(CustoVeiculo.valor).label('total')
            ).filter(
                CustoVeiculo.veiculo_id == veiculo_id,
                CustoVeiculo.admin_id == admin_id,
                CustoVeiculo.data_custo >= data_limite
            ).group_by(
                func.extract('month', CustoVeiculo.data_custo),
                func.extract('year', CustoVeiculo.data_custo)
            ).order_by('ano', 'mes').all()
            
            # Manutenções do período
            manutencoes = db.session.query(ManutencaoVeiculo).filter(
                ManutencaoVeiculo.veiculo_id == veiculo_id,
                ManutencaoVeiculo.admin_id == admin_id,
                ManutencaoVeiculo.data_manutencao >= data_limite
            ).order_by(desc(ManutencaoVeiculo.data_manutencao)).all()
        
        # Calcular análise de TCO
        dias_periodo = (date.today() - data_limite).days
        meses_periodo = dias_periodo / 30
        
        tco_analise = {
            'total_custos': total_custos,
            'custo_mensal': total_custos / meses_periodo if meses_periodo > 0 else 0,
            'custo_diario': total_custos / dias_periodo if dias_periodo > 0 else 0,
            'custo_por_km': custo_por_km,
            'km_periodo': km_periodo,
            'km_medio_mes': km_periodo / meses_periodo if meses_periodo > 0 else 0,
            'total_manutencoes': len(manutencoes),
            'valor_manutencoes': sum([m.valor_total for m in manutencoes])
        }
        
        return render_template('veiculos_avancado/relatorio_tco.html',
                             veiculo=veiculo,
                             custos_categoria=custos_categoria,
                             tco_analise=tco_analise,
                             historico_mensal=historico_mensal,
                             manutencoes=manutencoes,
                             periodo=periodo)
        
    except Exception as e:
        logger.error(f"Erro no relatório TCO: {str(e)}")
        flash('Erro ao gerar relatório de TCO.', 'error')
        return redirect(url_for('veiculos_avancado.dashboard_financeiro'))

# =============================================
# ROTAS DE API PARA AJAX
# =============================================

@veiculos_avancado_bp.route('/api/kpis-veiculo/<int:veiculo_id>')
@admin_required
def api_kpis_veiculo(veiculo_id):
    """API para obter KPIs de um veículo específico"""
    try:
        admin_id = get_admin_id()
        kpis = calcular_kpis_veiculo(veiculo_id, admin_id)
        return jsonify(kpis)
    except Exception as e:
        logger.error(f"Erro na API KPIs: {str(e)}")
        return jsonify({'error': 'Erro ao calcular KPIs'}), 500

@veiculos_avancado_bp.route('/api/alertas/marcar-visualizado/<int:alerta_id>', methods=['POST'])
@admin_required
def api_marcar_alerta_visualizado(alerta_id):
    """API para marcar alerta como visualizado"""
    try:
        admin_id = get_admin_id()
        
        alerta = db.session.query(AlertaVeiculo).filter(
            AlertaVeiculo.id == alerta_id,
            AlertaVeiculo.admin_id == admin_id
        ).first_or_404()
        
        alerta.visualizado = True
        alerta.data_visualizacao = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Alerta marcado como visualizado'})
        
    except Exception as e:
        logger.error(f"Erro ao marcar alerta: {str(e)}")
        return jsonify({'error': 'Erro ao marcar alerta'}), 500

@veiculos_avancado_bp.route('/api/custos-grafico/<int:veiculo_id>')
@admin_required
def api_custos_grafico(veiculo_id):
    """API para dados de gráfico de custos de um veículo"""
    try:
        admin_id = get_admin_id()
        periodo_dias = request.args.get('periodo', 365, type=int)
        data_limite = date.today() - timedelta(days=periodo_dias)
        
        # Custos mensais
        custos_mensais = db.session.query(
            func.extract('month', CustoVeiculo.data_custo).label('mes'),
            func.sum(CustoVeiculo.valor).label('total')
        ).filter(
            CustoVeiculo.veiculo_id == veiculo_id,
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= data_limite
        ).group_by(func.extract('month', CustoVeiculo.data_custo)).all()
        
        dados = {
            'labels': [f"Mês {int(c.mes)}" for c in custos_mensais],
            'values': [float(c.total) for c in custos_mensais]
        }
        
        return jsonify(dados)
        
    except Exception as e:
        logger.error(f"Erro na API gráfico: {str(e)}")
        return jsonify({'error': 'Erro ao obter dados do gráfico'}), 500