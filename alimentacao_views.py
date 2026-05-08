from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Restaurante, AlimentacaoLancamento, RegistroAlimentacao, Funcionario, Obra, AlimentacaoItem, AlimentacaoLancamentoItem, CentroCusto, CustoObra
from datetime import datetime
from sqlalchemy import func
from decimal import Decimal
import logging
import re
from utils.tenant import is_v2_active

logger = logging.getLogger(__name__)

alimentacao_bp = Blueprint('alimentacao', __name__, url_prefix='/alimentacao')

MAX_QTD_POR_ITEM = 200

# ===== HELPER FUNCTION =====
def get_admin_id():
    """Retorna admin_id do usuário atual"""
    if current_user.is_authenticated:
        return current_user.admin_id if current_user.admin_id else current_user.id
    return None

# ===== RESTAURANTES - CRUD COMPLETO =====

@alimentacao_bp.route('/restaurantes')
@login_required
def restaurantes_lista():
    """Lista todos os restaurantes"""
    admin_id = get_admin_id()
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    return render_template('alimentacao/restaurantes_lista.html', restaurantes=restaurantes)

@alimentacao_bp.route('/restaurantes/novo', methods=['GET', 'POST'])
@login_required
def restaurante_novo():
    """Criar novo restaurante"""
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            restaurante = Restaurante(
                nome=request.form['nome'],
                endereco=request.form.get('endereco', ''),
                telefone=request.form.get('telefone', ''),
                razao_social=request.form.get('razao_social', ''),
                cnpj=request.form.get('cnpj', ''),
                pix=request.form.get('pix', ''),
                nome_conta=request.form.get('nome_conta', ''),
                admin_id=admin_id
            )
            db.session.add(restaurante)
            db.session.commit()
            flash('Restaurante cadastrado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar restaurante: {e}")
            flash('Erro ao cadastrar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_novo.html')

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/editar', methods=['GET', 'POST'])
@login_required
def restaurante_editar(restaurante_id):
    """Editar restaurante"""
    admin_id = get_admin_id()
    restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            restaurante.nome = request.form['nome']
            restaurante.endereco = request.form.get('endereco', '')
            restaurante.telefone = request.form.get('telefone', '')
            restaurante.razao_social = request.form.get('razao_social', '')
            restaurante.cnpj = request.form.get('cnpj', '')
            restaurante.pix = request.form.get('pix', '')
            restaurante.nome_conta = request.form.get('nome_conta', '')
            db.session.commit()
            flash('Restaurante atualizado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar restaurante: {e}")
            flash('Erro ao atualizar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_editar.html', restaurante=restaurante)

@alimentacao_bp.route('/restaurante/<int:restaurante_id>')
@login_required
def restaurante_detalhes(restaurante_id):
    """Exibir detalhes do restaurante e seus lançamentos"""
    admin_id = get_admin_id()
    
    # Buscar restaurante com validação multi-tenant
    restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
    
    # 🔄 HÍBRIDO: Buscar de AMBAS as tabelas (antigo e novo)
    # Modelo ANTIGO: RegistroAlimentacao (dados históricos)
    registros_antigos = RegistroAlimentacao.query.filter_by(
        restaurante_id=restaurante_id, 
        admin_id=admin_id
    ).all()
    
    # Modelo NOVO: AlimentacaoLancamento (lançamentos novos)
    lancamentos_novos = AlimentacaoLancamento.query.filter_by(
        restaurante_id=restaurante_id, 
        admin_id=admin_id
    ).all()
    
    # Adapter: Normaliza modelo ANTIGO para formato do template
    class LancamentoAdapter:
        """Adapter para normalizar RegistroAlimentacao para o formato esperado pelo template"""
        def __init__(self, registro):
            self.data = registro.data
            self.obra = registro.obra_ref  # Objeto ORM (ou None)
            self.valor_total = float(registro.valor)
            self.funcionarios = [registro.funcionario_ref] if registro.funcionario_ref else []
            self.valor_por_funcionario = float(registro.valor) if registro.funcionario_ref else 0
            self.descricao = registro.tipo or '-'
            self._origem = 'antigo'
    
    # Combinar ambos em lista unificada
    lancamentos = []
    
    # Adicionar registros antigos (via adapter)
    for reg in registros_antigos:
        lancamentos.append(LancamentoAdapter(reg))
    
    # Adicionar lançamentos novos (já no formato correto)
    lancamentos.extend(lancamentos_novos)
    
    # Ordenar por data (mais recente primeiro)
    lancamentos.sort(key=lambda x: x.data, reverse=True)
    
    # Calcular estatísticas (soma de ambas as tabelas)
    total_gasto = sum(reg.valor for reg in registros_antigos) + sum(lanc.valor_total for lanc in lancamentos_novos)
    total_lancamentos = len(registros_antigos) + len(lancamentos_novos)
    
    return render_template('alimentacao/restaurante_detalhes.html', 
                         restaurante=restaurante,
                         lancamentos=lancamentos,
                         total_gasto=total_gasto,
                         total_lancamentos=total_lancamentos)

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/deletar', methods=['POST'])
@login_required
def restaurante_deletar(restaurante_id):
    """Deletar restaurante"""
    try:
        admin_id = get_admin_id()
        restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
        db.session.delete(restaurante)
        db.session.commit()
        flash('Restaurante excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar restaurante: {e}")
        flash('Erro ao excluir restaurante', 'error')
    
    return redirect(url_for('alimentacao.restaurantes_lista'))

# ===== LANÇAMENTOS - CRUD =====

@alimentacao_bp.route('/')
@login_required
def index():
    """Página principal com cards dos restaurantes"""
    admin_id = get_admin_id()
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    return render_template('alimentacao/index.html', restaurantes=restaurantes)

@alimentacao_bp.route('/lancamentos')
@login_required
def lancamentos_lista():
    """Lista todos os lançamentos de alimentação"""
    admin_id = get_admin_id()
    
    # Buscar lançamentos do modelo novo (AlimentacaoLancamento)
    lancamentos = AlimentacaoLancamento.query.filter_by(admin_id=admin_id).order_by(
        AlimentacaoLancamento.data.desc()
    ).all()
    
    return render_template('alimentacao/lancamentos_lista.html', lancamentos=lancamentos)

@alimentacao_bp.route('/lancamentos/novo', methods=['GET', 'POST'])
@login_required
def lancamento_novo():
    """Criar novo lançamento com rateio"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            
            # VALIDAÇÃO TENANT: Verificar restaurante
            restaurante_id = int(request.form['restaurante_id'])
            restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first()
            if not restaurante:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar restaurante_id={restaurante_id}")
                flash('Restaurante inválido ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar obra
            obra_id = int(request.form['obra_id'])
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar obra_id={obra_id}")
                flash('Obra inválida ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar funcionários
            funcionarios_ids = request.form.getlist('funcionarios')
            if not funcionarios_ids:
                flash('Selecione pelo menos um funcionário', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Validar cada funcionário contra admin_id
            funcionarios_validos = []
            for func_id in funcionarios_ids:
                funcionario = Funcionario.query.filter_by(id=int(func_id), admin_id=admin_id).first()
                if funcionario:
                    funcionarios_validos.append(funcionario)
                else:
                    logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar funcionario_id={func_id}")
            
            if not funcionarios_validos:
                flash('Nenhum funcionário válido selecionado', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Criar lançamento (agora seguro)
            lancamento = AlimentacaoLancamento(
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                valor_total=Decimal(request.form['valor_total']),
                descricao=request.form.get('descricao', ''),
                restaurante_id=restaurante.id,  # Usar objeto validado
                obra_id=obra.id,  # Usar objeto validado
                admin_id=admin_id
            )
            db.session.add(lancamento)
            db.session.flush()
            
            # Associar funcionários com admin_id (INSERT direto pois tabela tem coluna admin_id)
            from sqlalchemy import text
            for funcionario in funcionarios_validos:
                db.session.execute(
                    text("""INSERT INTO alimentacao_funcionarios_assoc 
                            (lancamento_id, funcionario_id, admin_id) 
                            VALUES (:lancamento_id, :funcionario_id, :admin_id)"""),
                    {'lancamento_id': lancamento.id, 'funcionario_id': funcionario.id, 'admin_id': admin_id}
                )
            
            db.session.commit()
            
            # ✅ NOVO: Emitir evento para integração com Financeiro (Tarefa 9)
            try:
                from event_manager import EventManager
                EventManager.emit('alimentacao_lancamento_criado', {
                    'lancamento_id': lancamento.id,
                    'restaurante_id': lancamento.restaurante_id,
                    'obra_id': lancamento.obra_id,
                    'valor_total': float(lancamento.valor_total)
                }, admin_id)
                logger.info(f"✅ Evento 'alimentacao_lancamento_criado' emitido para lançamento {lancamento.id}")
            except Exception as e:
                logger.error(f"❌ Erro ao emitir evento alimentacao_lancamento_criado: {e}")
            
            flash(f'Lançamento criado! Valor por funcionário: R$ {lancamento.valor_por_funcionario:.2f}', 'success')
            return redirect(url_for('alimentacao.index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar lançamento: {e}")
            flash('Erro ao criar lançamento', 'error')
    
    # GET - carregar dados para o formulário
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id).order_by(Funcionario.nome).all()
    
    return render_template('alimentacao/lancamento_novo.html', 
                         restaurantes=restaurantes, 
                         obras=obras, 
                         funcionarios=funcionarios)


# ===== NOVO SISTEMA v2 - MÚLTIPLOS ITENS =====
@alimentacao_bp.route('/lancamentos/novo-v2', methods=['GET', 'POST'])
@login_required
def lancamento_novo_v2():
    """Criar novo lançamento v2 com múltiplos itens e seleção mobile-friendly.
    V2 feature flag: adiciona detalhamento por funcionário e centro de custo por item.
    """
    admin_id = get_admin_id()
    v2 = is_v2_active()

    def _render_form(status=200):
        """Carrega contexto do formulário e renderiza o template V2."""
        _restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
        _obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
        _funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        _itens = AlimentacaoItem.query.filter_by(admin_id=admin_id, ativo=True).order_by(AlimentacaoItem.ordem).all()
        _centros = CentroCusto.query.filter_by(admin_id=admin_id, ativo=True).order_by(CentroCusto.nome).all()
        _itens_json = [{'id': i.id, 'nome': i.nome, 'preco_padrao': float(i.preco_padrao),
                        'icone': i.icone or 'fas fa-utensils', 'is_default': i.is_default}
                       for i in _itens]
        _centros_json = [{'id': c.id, 'nome': c.nome, 'codigo': c.codigo, 'obra_id': c.obra_id}
                         for c in _centros]
        _func_json = [{'id': f.id, 'nome': f.nome,
                       'funcao': f.funcao_ref.nome if f.funcao_ref else ''}
                      for f in _funcionarios]
        _rest_sel = request.args.get('restaurante_id', type=int)
        resp = render_template('alimentacao/lancamento_novo_v2.html',
                               restaurantes=_restaurantes, obras=_obras,
                               funcionarios=_funcionarios, itens_cadastrados=_itens,
                               itens_json=_itens_json, centros_custo=_centros,
                               centros_custo_json=_centros_json, funcionarios_json=_func_json,
                               restaurante_id_selecionado=_rest_sel, v2=v2)
        return resp, status

    if request.method == 'POST':
        try:
            logger.info(f"[ALIMENTACAO] Processando novo lancamento para admin_id={admin_id} v2={v2}")

            # --- Validação cabeçalho ---
            obra_id = request.form.get('obra_id')
            if not obra_id:
                flash('Selecione uma obra', 'error')
                return redirect(url_for('alimentacao.lancamento_novo_v2'))

            obra = Obra.query.filter_by(id=int(obra_id), admin_id=admin_id).first()
            if not obra:
                flash('Obra inválida', 'error')
                return redirect(url_for('alimentacao.lancamento_novo_v2'))

            restaurante_id = request.form.get('restaurante_id')
            restaurante = None
            if restaurante_id:
                restaurante = Restaurante.query.filter_by(id=int(restaurante_id), admin_id=admin_id).first()

            # --- Processar itens do formulário ---
            itens_data = []
            indices = set()
            for key in request.form.keys():
                match = re.match(r'itens\[(\d+)\]', key)
                if match:
                    indices.add(int(match.group(1)))

            for idx in sorted(indices):
                item_id = request.form.get(f'itens[{idx}][item_id]')
                preco_raw = request.form.get(f'itens[{idx}][preco]')
                nome_custom = request.form.get(f'itens[{idx}][nome]')

                if not preco_raw:
                    continue
                preco_decimal = Decimal(preco_raw)
                if preco_decimal <= 0:
                    continue

                # Determinar nome do item
                if item_id and item_id != 'custom':
                    item_ref = AlimentacaoItem.query.filter_by(id=int(item_id), admin_id=admin_id).first()
                    nome_item = item_ref.nome if item_ref else nome_custom or 'Item'
                else:
                    nome_item = nome_custom or 'Item personalizado'

                item_entry = {
                    'item_id': int(item_id) if item_id and item_id != 'custom' else None,
                    'nome': nome_item,
                    'preco': preco_decimal,
                    'funcionario_id': None,
                    'centro_custo_id': None,
                    'quantidade': 1,
                }

                if v2:
                    # V2: quantidade, funcionário e centro de custo por linha
                    qtd_raw = request.form.get(f'itens[{idx}][quantidade]', '1')
                    try:
                        qtd_int = int(qtd_raw)
                    except (ValueError, TypeError):
                        flash(f'Quantidade inválida no item {idx + 1}: informe um número inteiro entre 1 e {MAX_QTD_POR_ITEM}.', 'error')
                        return _render_form(status=422)
                    if qtd_int < 1 or qtd_int > MAX_QTD_POR_ITEM:
                        flash(f'Quantidade {qtd_int} fora do limite no item {idx + 1}: deve ser entre 1 e {MAX_QTD_POR_ITEM}.', 'error')
                        return _render_form(status=422)
                    item_entry['quantidade'] = qtd_int

                    func_id_raw = request.form.get(f'itens[{idx}][funcionario_id]')
                    if func_id_raw and func_id_raw != '0':
                        func_obj = Funcionario.query.filter_by(id=int(func_id_raw), admin_id=admin_id).first()
                        if func_obj:
                            item_entry['funcionario_id'] = func_obj.id

                    cc_id_raw = request.form.get(f'itens[{idx}][centro_custo_id]')
                    if cc_id_raw and cc_id_raw != '0':
                        cc_obj = CentroCusto.query.filter_by(id=int(cc_id_raw), admin_id=admin_id).first()
                        if cc_obj:
                            item_entry['centro_custo_id'] = cc_obj.id
                else:
                    # V1: quantidade = número de funcionários selecionados
                    funcionarios_ids = request.form.getlist('funcionarios')
                    item_entry['quantidade'] = len(funcionarios_ids) if funcionarios_ids else 1

                item_entry['subtotal'] = preco_decimal * item_entry['quantidade']
                itens_data.append(item_entry)

            if not itens_data:
                flash('Adicione pelo menos um item com preço válido', 'error')
                return redirect(url_for('alimentacao.lancamento_novo_v2'))

            # V1: validar funcionários globais
            funcionarios_validos = []
            if not v2:
                funcionarios_ids = request.form.getlist('funcionarios')
                if not funcionarios_ids:
                    flash('Selecione pelo menos um funcionário', 'error')
                    return redirect(url_for('alimentacao.lancamento_novo_v2'))
                for func_id in funcionarios_ids:
                    f = Funcionario.query.filter_by(id=int(func_id), admin_id=admin_id).first()
                    if f:
                        funcionarios_validos.append(f)
                if not funcionarios_validos:
                    flash('Nenhum funcionário válido selecionado', 'error')
                    return redirect(url_for('alimentacao.lancamento_novo_v2'))

            valor_total = sum(item['subtotal'] for item in itens_data)
            if valor_total <= 0:
                flash('O valor total deve ser maior que zero', 'error')
                return redirect(url_for('alimentacao.lancamento_novo_v2'))

            # --- Criar lançamento principal ---
            lancamento = AlimentacaoLancamento(
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                valor_total=valor_total,
                descricao=request.form.get('descricao', ''),
                restaurante_id=restaurante.id if restaurante else None,
                obra_id=obra.id,
                admin_id=admin_id
            )
            db.session.add(lancamento)
            db.session.flush()

            # V1: associar funcionários globais
            if not v2 and funcionarios_validos:
                from sqlalchemy import text
                for funcionario in funcionarios_validos:
                    db.session.execute(
                        text("""INSERT INTO alimentacao_funcionarios_assoc
                                (lancamento_id, funcionario_id, admin_id)
                                VALUES (:lancamento_id, :funcionario_id, :admin_id)"""),
                        {'lancamento_id': lancamento.id, 'funcionario_id': funcionario.id, 'admin_id': admin_id}
                    )

            # --- Criar itens do lançamento ---
            for item in itens_data:
                lancamento_item = AlimentacaoLancamentoItem(
                    lancamento_id=lancamento.id,
                    item_id=item['item_id'],
                    nome_item=item['nome'],
                    preco_unitario=item['preco'],
                    quantidade=item['quantidade'],
                    subtotal=item['subtotal'],
                    funcionario_id=item['funcionario_id'],
                    centro_custo_id=item['centro_custo_id'],
                    admin_id=admin_id
                )
                db.session.add(lancamento_item)

            db.session.flush()

            # --- Passo 4 V2: Criar CustoObra agrupado por centro_custo_id ---
            if v2:
                from collections import defaultdict
                grupos = defaultdict(Decimal)
                for item in itens_data:
                    chave = item['centro_custo_id']
                    grupos[chave] += item['subtotal']

                num_itens = len(itens_data)
                restaurante_nome = restaurante.nome if restaurante else 'Alimentação'
                data_lancamento = datetime.strptime(request.form['data'], '%Y-%m-%d').date()

                for cc_id, valor_grupo in grupos.items():
                    custo = CustoObra(
                        obra_id=obra.id,
                        centro_custo_id=cc_id,
                        tipo='alimentacao',
                        descricao=f"Refeições - {restaurante_nome} - {num_itens} itens",
                        valor=float(valor_grupo),
                        data=data_lancamento,
                        admin_id=admin_id
                    )
                    db.session.add(custo)
                    logger.info(f"[ALIMENTACAO_V2] CustoObra criado: obra={obra.id} cc={cc_id} valor={valor_grupo}")

            db.session.commit()

            # Lançamento contábil automático V2
            try:
                from contabilidade_utils import gerar_lancamento_contabil_automatico
                if v2:
                    gerar_lancamento_contabil_automatico(
                        admin_id=admin_id,
                        tipo_operacao='despesa_alimentacao',
                        valor=float(valor_total),
                        data=lancamento.data,
                        descricao=f"Alimentação - {lancamento.descricao or 'Refeições'}",
                    )
            except Exception as _e:
                logger.warning(f"[WARN] Lancamento contabil alimentacao nao gerado: {_e}")

            # Integração automática: Gestão de Custos V2
            try:
                from utils.financeiro_integration import registrar_custo_automatico
                _rest_nome = restaurante.nome if restaurante else 'Alimentação'
                registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='ALIMENTACAO',
                    entidade_nome=_rest_nome,
                    entidade_id=restaurante.id if restaurante else None,
                    data=lancamento.data,
                    descricao=lancamento.descricao or f'Refeições — {_rest_nome}',
                    valor=float(valor_total),
                    obra_id=obra.id if obra else None,
                    origem_tabela='alimentacao_lancamento',
                    origem_id=lancamento.id,
                )
                from app import db as _db
                _db.session.commit()
                logger.info(f"[OK] GestaoCusto ALIMENTACAO registrado para {_rest_nome}")
            except Exception as _e:
                logger.warning(f"[WARN] Gestao custo alimentacao nao registrado: {_e}")

            # --- Emitir evento para integração ---
            try:
                from event_manager import EventManager
                EventManager.emit('alimentacao_lancamento_criado', {
                    'lancamento_id': lancamento.id,
                    'restaurante_id': lancamento.restaurante_id,
                    'obra_id': lancamento.obra_id,
                    'valor_total': float(lancamento.valor_total)
                }, admin_id)
            except Exception as e:
                logger.error(f"[ERROR] Erro ao emitir evento alimentacao: {e}")

            # Reembolso a Funcionários V2
            if v2:
                try:
                    from utils.financeiro_integration import processar_reembolsos_form
                    n_reimb = processar_reembolsos_form(
                        request_form=request.form,
                        admin_id=admin_id,
                        data_despesa=lancamento.data,
                        descricao_origem=lancamento.descricao or 'Alimentação',
                        obra_id=lancamento.obra_id,
                        origem_tabela='alimentacao_lancamento',
                        origem_id=lancamento.id,
                    )
                    if n_reimb:
                        db.session.commit()
                        logger.info(f"[OK] {n_reimb} reembolso(s) registrado(s) alimentacao {lancamento.id}")
                except Exception as _re:
                    logger.warning(f"[WARN] Reembolso alimentacao nao processado: {_re}")

            msg = f'Lançamento criado com sucesso! Total: R$ {valor_total:.2f}'
            if v2:
                msg += f' ({len(itens_data)} itens detalhados)'
            else:
                msg += f' ({len(funcionarios_validos)} funcionários)'
            flash(msg, 'success')
            return redirect(url_for('alimentacao.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar lancamento v2: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Erro ao criar lançamento: {str(e)}', 'error')

    # --- GET: renderizar formulário ---
    return _render_form()


# ===== API PARA ITENS CADASTRADOS =====
@alimentacao_bp.route('/api/itens')
@login_required
def api_itens():
    """Retorna lista de itens cadastrados para AJAX"""
    admin_id = get_admin_id()
    itens = AlimentacaoItem.query.filter_by(admin_id=admin_id, ativo=True).order_by(AlimentacaoItem.ordem).all()
    return jsonify([{
        'id': item.id,
        'nome': item.nome,
        'preco_padrao': float(item.preco_padrao),
        'icone': item.icone,
        'is_default': item.is_default
    } for item in itens])


# ===== CRUD DE ITENS CADASTRADOS =====
@alimentacao_bp.route('/itens')
@login_required
def itens_lista():
    """Lista itens cadastrados de alimentação"""
    admin_id = get_admin_id()
    itens = AlimentacaoItem.query.filter_by(admin_id=admin_id).order_by(AlimentacaoItem.ordem).all()
    return render_template('alimentacao/itens_lista.html', itens=itens)


@alimentacao_bp.route('/itens/novo', methods=['GET', 'POST'])
@login_required
def item_novo():
    """Criar novo item de alimentação"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            item = AlimentacaoItem(
                nome=request.form['nome'],
                preco_padrao=Decimal(request.form.get('preco_padrao', '0')),
                descricao=request.form.get('descricao', ''),
                icone=request.form.get('icone', 'fas fa-utensils'),
                ordem=int(request.form.get('ordem', '0')),
                admin_id=admin_id
            )
            db.session.add(item)
            db.session.commit()
            flash('Item cadastrado com sucesso!', 'success')
            return redirect(url_for('alimentacao.itens_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar item: {e}")
            flash('Erro ao cadastrar item', 'error')
    
    return render_template('alimentacao/item_novo.html')


@alimentacao_bp.route('/itens/<int:item_id>/editar', methods=['GET', 'POST'])
@login_required
def item_editar(item_id):
    """Editar item de alimentação"""
    admin_id = get_admin_id()
    item = AlimentacaoItem.query.filter_by(id=item_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            item.nome = request.form['nome']
            item.preco_padrao = Decimal(request.form.get('preco_padrao', '0'))
            item.descricao = request.form.get('descricao', '')
            item.icone = request.form.get('icone', 'fas fa-utensils')
            item.ordem = int(request.form.get('ordem', '0'))
            item.ativo = request.form.get('ativo') == 'on'
            db.session.commit()
            flash('Item atualizado com sucesso!', 'success')
            return redirect(url_for('alimentacao.itens_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar item: {e}")
            flash('Erro ao atualizar item', 'error')
    
    return render_template('alimentacao/item_editar.html', item=item)


# ===== DASHBOARD DE ALIMENTAÇÃO (TAREFA 8) =====
@alimentacao_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard de Alimentação com KPIs e gráficos"""
    try:
        from datetime import date, timedelta

        logger.info("📊 [ALIMENTACAO_DASHBOARD] Iniciando dashboard...")
        admin_id = get_admin_id()
        
        if not admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Capturar filtros da URL
        filtro_data_inicio = request.args.get('data_inicio')
        filtro_data_fim = request.args.get('data_fim')
        filtro_restaurante_id = request.args.get('restaurante_id', type=int)
        filtro_obra_id = request.args.get('obra_id', type=int)
        
        # Converter datas se fornecidas
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date() if filtro_data_inicio else None
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date() if filtro_data_fim else None
        
        # 🔄 HÍBRIDO: Contar de AMBAS as tabelas
        # Query base para modelo ANTIGO
        query_antigo = RegistroAlimentacao.query.filter_by(admin_id=admin_id)
        if data_inicio:
            query_antigo = query_antigo.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            query_antigo = query_antigo.filter(RegistroAlimentacao.data <= data_fim)
        if filtro_restaurante_id:
            query_antigo = query_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            query_antigo = query_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
        
        # Query base para modelo NOVO
        query_novo = AlimentacaoLancamento.query.filter_by(admin_id=admin_id)
        if data_inicio:
            query_novo = query_novo.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            query_novo = query_novo.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            query_novo = query_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            query_novo = query_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        # KPI 1: Total de Refeições (soma de ambas as tabelas)
        total_refeicoes = query_antigo.count() + query_novo.count()
        
        # KPI 2: Custo Total (soma de ambas as tabelas)
        custo_antigo = db.session.query(
            func.coalesce(func.sum(RegistroAlimentacao.valor), Decimal('0'))
        ).filter(RegistroAlimentacao.admin_id == admin_id)
        
        custo_novo = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(AlimentacaoLancamento.admin_id == admin_id)
        
        # Aplicar mesmos filtros
        if data_inicio:
            custo_antigo = custo_antigo.filter(RegistroAlimentacao.data >= data_inicio)
            custo_novo = custo_novo.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            custo_antigo = custo_antigo.filter(RegistroAlimentacao.data <= data_fim)
            custo_novo = custo_novo.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            custo_antigo = custo_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
            custo_novo = custo_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custo_antigo = custo_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
            custo_novo = custo_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custo_total = float(custo_antigo.scalar() or 0) + float(custo_novo.scalar() or 0)
        
        # KPI 3: Custo Médio por Refeição
        custo_medio_refeicao = round(custo_total / total_refeicoes, 2) if total_refeicoes > 0 else 0
        
        # KPI 4: Custos do Mês Atual (com comparação)
        hoje = date.today()
        inicio_mes_atual = date(hoje.year, hoje.month, 1)
        fim_mes_anterior = inicio_mes_atual - timedelta(days=1)
        inicio_mes_anterior = date(fim_mes_anterior.year, fim_mes_anterior.month, 1)
        
        # 🔄 HÍBRIDO: Custos do mês atual (ambas as tabelas)
        custos_mes_atual_antigo = db.session.query(
            func.coalesce(func.sum(RegistroAlimentacao.valor), Decimal('0'))
        ).filter(
            RegistroAlimentacao.admin_id == admin_id,
            RegistroAlimentacao.data >= inicio_mes_atual
        )
        custos_mes_atual_novo = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            AlimentacaoLancamento.data >= inicio_mes_atual
        )
        if filtro_restaurante_id:
            custos_mes_atual_antigo = custos_mes_atual_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
            custos_mes_atual_novo = custos_mes_atual_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custos_mes_atual_antigo = custos_mes_atual_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
            custos_mes_atual_novo = custos_mes_atual_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custos_mes_atual = float(custos_mes_atual_antigo.scalar() or 0) + float(custos_mes_atual_novo.scalar() or 0)
        
        # 🔄 HÍBRIDO: Custos do mês anterior (ambas as tabelas)
        custos_mes_anterior_antigo = db.session.query(
            func.coalesce(func.sum(RegistroAlimentacao.valor), Decimal('0'))
        ).filter(
            RegistroAlimentacao.admin_id == admin_id,
            RegistroAlimentacao.data >= inicio_mes_anterior,
            RegistroAlimentacao.data <= fim_mes_anterior
        )
        custos_mes_anterior_novo = db.session.query(
            func.coalesce(func.sum(AlimentacaoLancamento.valor_total), Decimal('0'))
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            AlimentacaoLancamento.data >= inicio_mes_anterior,
            AlimentacaoLancamento.data <= fim_mes_anterior
        )
        if filtro_restaurante_id:
            custos_mes_anterior_antigo = custos_mes_anterior_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
            custos_mes_anterior_novo = custos_mes_anterior_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            custos_mes_anterior_antigo = custos_mes_anterior_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
            custos_mes_anterior_novo = custos_mes_anterior_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        
        custos_mes_anterior = float(custos_mes_anterior_antigo.scalar() or 0) + float(custos_mes_anterior_novo.scalar() or 0)
        
        # Calcular variação percentual
        if custos_mes_anterior > 0:
            variacao_percentual = round(((custos_mes_atual - custos_mes_anterior) / custos_mes_anterior) * 100, 1)
        else:
            variacao_percentual = 100.0 if custos_mes_atual > 0 else 0.0
        
        # 🔄 HÍBRIDO: Gráfico 1 - Top 5 Funcionários (mais refeições)
        # Contar de modelo ANTIGO (1 funcionário por registro)
        top_func_antigo = db.session.query(
            Funcionario.id,
            Funcionario.nome,
            func.count(RegistroAlimentacao.id).label('total')
        ).join(
            RegistroAlimentacao,
            Funcionario.id == RegistroAlimentacao.funcionario_id
        ).filter(
            RegistroAlimentacao.admin_id == admin_id,
            Funcionario.admin_id == admin_id
        )
        if data_inicio:
            top_func_antigo = top_func_antigo.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            top_func_antigo = top_func_antigo.filter(RegistroAlimentacao.data <= data_fim)
        if filtro_restaurante_id:
            top_func_antigo = top_func_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_func_antigo = top_func_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
        top_func_antigo = top_func_antigo.group_by(Funcionario.id, Funcionario.nome).all()
        
        # Contar de modelo NOVO (many-to-many via association table)
        from models import alimentacao_funcionarios_assoc
        top_func_novo = db.session.query(
            Funcionario.id,
            Funcionario.nome,
            func.count(alimentacao_funcionarios_assoc.c.lancamento_id).label('total')
        ).join(
            alimentacao_funcionarios_assoc,
            Funcionario.id == alimentacao_funcionarios_assoc.c.funcionario_id
        ).join(
            AlimentacaoLancamento,
            AlimentacaoLancamento.id == alimentacao_funcionarios_assoc.c.lancamento_id
        ).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            Funcionario.admin_id == admin_id
        )
        if data_inicio:
            top_func_novo = top_func_novo.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            top_func_novo = top_func_novo.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            top_func_novo = top_func_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_func_novo = top_func_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        top_func_novo = top_func_novo.group_by(Funcionario.id, Funcionario.nome).all()
        
        # Combinar e somar
        func_dict = {}
        for func_id, func_nome, total in top_func_antigo:
            func_dict[func_id] = {'nome': func_nome, 'total_refeicoes': int(total)}
        for func_id, func_nome, total in top_func_novo:
            if func_id in func_dict:
                func_dict[func_id]['total_refeicoes'] += int(total)
            else:
                func_dict[func_id] = {'nome': func_nome, 'total_refeicoes': int(total)}
        
        # Ordenar e pegar top 5
        top_funcionarios = sorted(
            [(nome_data['nome'], fid, nome_data['total_refeicoes']) 
             for fid, nome_data in func_dict.items()],
            key=lambda x: x[2],
            reverse=True
        )[:5]
        
        # 🔄 HÍBRIDO: Gráfico 2 - Top 5 Obras (mais gastos)
        # Somar de modelo ANTIGO
        top_obras_antigo = db.session.query(
            Obra.id,
            Obra.nome,
            func.sum(RegistroAlimentacao.valor).label('total')
        ).join(RegistroAlimentacao).filter(
            RegistroAlimentacao.admin_id == admin_id,
            Obra.admin_id == admin_id
        )
        if data_inicio:
            top_obras_antigo = top_obras_antigo.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            top_obras_antigo = top_obras_antigo.filter(RegistroAlimentacao.data <= data_fim)
        if filtro_restaurante_id:
            top_obras_antigo = top_obras_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_obras_antigo = top_obras_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
        top_obras_antigo = top_obras_antigo.group_by(Obra.id, Obra.nome).all()
        
        # Somar de modelo NOVO
        top_obras_novo = db.session.query(
            Obra.id,
            Obra.nome,
            func.sum(AlimentacaoLancamento.valor_total).label('total')
        ).join(AlimentacaoLancamento).filter(
            AlimentacaoLancamento.admin_id == admin_id,
            Obra.admin_id == admin_id
        )
        if data_inicio:
            top_obras_novo = top_obras_novo.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            top_obras_novo = top_obras_novo.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            top_obras_novo = top_obras_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            top_obras_novo = top_obras_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        top_obras_novo = top_obras_novo.group_by(Obra.id, Obra.nome).all()
        
        # Combinar e somar
        obra_dict = {}
        for obra_id, obra_nome, total in top_obras_antigo:
            obra_dict[obra_id] = {'nome': obra_nome, 'total_gastos': float(total or 0)}
        for obra_id, obra_nome, total in top_obras_novo:
            if obra_id in obra_dict:
                obra_dict[obra_id]['total_gastos'] += float(total or 0)
            else:
                obra_dict[obra_id] = {'nome': obra_nome, 'total_gastos': float(total or 0)}
        
        # Ordenar e pegar top 5
        top_obras = sorted(
            [(nome_data['nome'], oid, nome_data['total_gastos']) 
             for oid, nome_data in obra_dict.items()],
            key=lambda x: x[2],
            reverse=True
        )[:5]
        
        # 🔄 HÍBRIDO: Gráfico 3 - Evolução Mensal
        # Agrupar modelo ANTIGO
        evolucao_antigo = db.session.query(
            func.to_char(RegistroAlimentacao.data, 'YYYY-MM').label('mes'),
            func.sum(RegistroAlimentacao.valor).label('total')
        ).filter(RegistroAlimentacao.admin_id == admin_id)
        if data_inicio:
            evolucao_antigo = evolucao_antigo.filter(RegistroAlimentacao.data >= data_inicio)
        if data_fim:
            evolucao_antigo = evolucao_antigo.filter(RegistroAlimentacao.data <= data_fim)
        if filtro_restaurante_id:
            evolucao_antigo = evolucao_antigo.filter(RegistroAlimentacao.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            evolucao_antigo = evolucao_antigo.filter(RegistroAlimentacao.obra_id == filtro_obra_id)
        evolucao_antigo = evolucao_antigo.group_by(func.to_char(RegistroAlimentacao.data, 'YYYY-MM')).all()
        
        # Agrupar modelo NOVO
        evolucao_novo = db.session.query(
            func.to_char(AlimentacaoLancamento.data, 'YYYY-MM').label('mes'),
            func.sum(AlimentacaoLancamento.valor_total).label('total')
        ).filter(AlimentacaoLancamento.admin_id == admin_id)
        if data_inicio:
            evolucao_novo = evolucao_novo.filter(AlimentacaoLancamento.data >= data_inicio)
        if data_fim:
            evolucao_novo = evolucao_novo.filter(AlimentacaoLancamento.data <= data_fim)
        if filtro_restaurante_id:
            evolucao_novo = evolucao_novo.filter(AlimentacaoLancamento.restaurante_id == filtro_restaurante_id)
        if filtro_obra_id:
            evolucao_novo = evolucao_novo.filter(AlimentacaoLancamento.obra_id == filtro_obra_id)
        evolucao_novo = evolucao_novo.group_by(func.to_char(AlimentacaoLancamento.data, 'YYYY-MM')).all()
        
        # Combinar por mês
        mes_dict = {}
        for mes, total in evolucao_antigo:
            mes_dict[mes] = float(total or 0)
        for mes, total in evolucao_novo:
            if mes in mes_dict:
                mes_dict[mes] += float(total or 0)
            else:
                mes_dict[mes] = float(total or 0)
        
        # Ordenar e pegar últimos 6 meses
        evolucao_mensal = sorted(
            [(mes, total) for mes, total in mes_dict.items()],
            key=lambda x: x[0],
            reverse=True
        )[:6]
        
        # Buscar restaurantes e obras para os filtros
        restaurantes_disponiveis = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
        obras_disponiveis = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        logger.info(f"✅ [ALIMENTACAO_DASHBOARD] KPIs calculados: Refeições={total_refeicoes}, Custo Total={custo_total}")
        
        return render_template('alimentacao/dashboard.html',
                             total_refeicoes=total_refeicoes,
                             custo_total=custo_total,
                             custo_medio_refeicao=custo_medio_refeicao,
                             custos_mes_atual=custos_mes_atual,
                             variacao_percentual=variacao_percentual,
                             top_funcionarios=top_funcionarios,
                             top_obras=top_obras,
                             evolucao_mensal=evolucao_mensal,
                             restaurantes_disponiveis=restaurantes_disponiveis,
                             obras_disponiveis=obras_disponiveis,
                             filtros={
                                 'restaurante_id': filtro_restaurante_id,
                                 'obra_id': filtro_obra_id,
                                 'data_inicio': filtro_data_inicio,
                                 'data_fim': filtro_data_fim
                             })
        
    except Exception as e:
        logger.error(f"❌ [ALIMENTACAO_DASHBOARD] Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar dashboard de alimentação. Tente novamente.', 'error')
        return redirect(url_for('alimentacao.index'))
