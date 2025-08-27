# SISTEMA DE SALVAMENTO RDO COMPATÍVEL COM SCHEMA ATUAL
# Corrige problema de campos incompatíveis entre modelo e database

from flask import Blueprint, request, jsonify, redirect, url_for, flash, render_template
from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Obra, Funcionario, SubAtividade
from bypass_auth import obter_admin_id, obter_usuario_atual
from datetime import datetime, date
from sqlalchemy import desc, and_
import logging

rdo_salvar_bp = Blueprint('rdo_salvar', __name__)
logger = logging.getLogger(__name__)

def gerar_numero_rdo_unico():
    """Gera número único para RDO"""
    ano_atual = datetime.now().year
    
    # Buscar último RDO do ano
    ultimo_rdo = RDO.query.filter(
        RDO.numero_rdo.contains(f'RDO-{ano_atual}-')
    ).order_by(desc(RDO.numero_rdo)).first()
    
    if ultimo_rdo:
        try:
            ultimo_numero = int(ultimo_rdo.numero_rdo.split('-')[-1])
            proximo_numero = ultimo_numero + 1
        except:
            proximo_numero = 1
    else:
        proximo_numero = 1
    
    return f'RDO-{ano_atual}-{proximo_numero:03d}'

@rdo_salvar_bp.route('/funcionario-rdo-consolidado', methods=['GET', 'POST'])
def funcionario_rdo_consolidado():
    """Rota principal do RDO consolidado - GET para mostrar formulário, POST para salvar"""
    admin_id = obter_admin_id()
    
    if request.method == 'POST':
        # Processar salvamento
        return processar_salvamento_rdo()
    
    # GET - Mostrar formulário
    try:
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        logger.debug(f"Carregando RDO: {len(obras)} obras, {len(funcionarios)} funcionários")
        
        return render_template('funcionario/rdo_consolidado.html',
                             obras=obras,
                             funcionarios=funcionarios,
                             modo_edicao=False,
                             dados_salvos={})
        
    except Exception as e:
        logger.error(f"Erro ao carregar formulário RDO: {str(e)}")
        flash('Erro ao carregar formulário RDO', 'error')
        return redirect(url_for('main.funcionario_dashboard'))

def processar_salvamento_rdo():
    """Processa salvamento do RDO usando schema compatível com logging detalhado"""
    print("="*80)
    print("🔍 INÍCIO DO SALVAMENTO RDO - DEBUG DETALHADO")
    print("="*80)
    
    try:
        # Passo 1: Obter admin_id
        admin_id = obter_admin_id()
        print(f"✅ Admin ID obtido: {admin_id}")
        
        # Passo 2: Obter usuário atual (sem vinculação com funcionário)
        usuario_id = obter_usuario_atual()
        print(f"✅ Usuário ID obtido: {usuario_id}")
        
        # Verificar se usuário tem acesso (sem verificar funcionário)
        from models import Usuario
        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            print(f"❌ ERRO: Usuário ID={usuario_id} não encontrado na base de dados")
            flash('Erro: Usuário não encontrado na base de dados. Contacte o administrador.', 'error')
            return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))
        
        print(f"✅ Usuário encontrado: {usuario.username} (admin_id={usuario.admin_id})")
        
        # Passo 3: Obter dados do formulário
        dados = request.form.to_dict()
        print(f"✅ Dados recebidos: {len(dados)} campos")
        print(f"🔍 Campos principais: {[k for k in dados.keys() if not k.startswith('funcionario_') and not k.startswith('subatividade_')]}")
        
        # Verificar se é finalização ou rascunho
        finalizar = dados.get('finalizar_rdo') == 'true'
        status = 'Finalizado' if finalizar else 'Rascunho'
        print(f"✅ Status definido: {status} (finalizar={finalizar})")
        
        # Passo 4: Criar novo RDO
        print("🔍 Criando novo RDO...")
        rdo = RDO()
        rdo.numero_rdo = gerar_numero_rdo_unico()
        rdo.admin_id = admin_id
        rdo.criado_por_id = usuario_id
        
        print(f"✅ RDO básico criado - Número: {rdo.numero_rdo}")
        
        # Passo 5: Validar e definir dados básicos
        print("🔍 Definindo dados básicos...")
        
        if dados.get('data_relatorio'):
            try:
                rdo.data_relatorio = datetime.strptime(dados.get('data_relatorio'), '%Y-%m-%d').date()
                print(f"✅ Data definida: {rdo.data_relatorio}")
            except ValueError as e:
                print(f"❌ Erro ao converter data: {e}")
                rdo.data_relatorio = date.today()
        else:
            rdo.data_relatorio = date.today()
            print(f"✅ Data padrão definida: {rdo.data_relatorio}")
        
        # Validar obra_id
        obra_id = dados.get('obra_id')
        if obra_id:
            try:
                rdo.obra_id = int(obra_id)
                obra = Obra.query.get(rdo.obra_id)
                if not obra:
                    print(f"❌ ERRO: Obra ID={obra_id} não encontrada")
                    flash(f'Erro: Obra ID={obra_id} não encontrada', 'error')
                    return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))
                print(f"✅ Obra validada: {obra.nome}")
            except ValueError:
                print(f"❌ ERRO: obra_id inválido: {obra_id}")
                flash('Erro: ID da obra inválido', 'error')
                return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))
        else:
            print("❌ ERRO: obra_id não informado")
            flash('Erro: Obra não selecionada', 'error')
            return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))
            
        rdo.clima_geral = dados.get('clima_geral', '')
        rdo.condicoes_trabalho = dados.get('condicoes_trabalho', '')
        rdo.comentario_geral = dados.get('observacoes', '')
        rdo.status = status
        
        print("✅ Dados básicos definidos")
        
        # Passo 6: Salvar RDO principal
        print("🔍 Salvando RDO principal...")
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID sem commit completo
        
        print(f"✅ RDO salvo com ID: {rdo.id}")
        
        # Passo 7: Processar equipe
        print("🔍 Processando equipe...")
        resultado_equipe = processar_equipe_schema_atual(rdo, dados)
        print(f"✅ Equipe processada: {resultado_equipe}")
        
        # Passo 8: Processar subatividades
        print("🔍 Processando subatividades...")
        resultado_subatividades = processar_subatividades_schema_atual(rdo, dados)
        print(f"✅ Subatividades processadas: {resultado_subatividades}")
        
        # Passo 9: Commit final
        print("🔍 Executando commit final...")
        db.session.commit()
        print("✅ SALVAMENTO CONCLUÍDO COM SUCESSO!")
        
        if finalizar:
            flash(f'RDO {rdo.numero_rdo} finalizado com sucesso!', 'success')
        else:
            flash(f'RDO {rdo.numero_rdo} salvo como rascunho!', 'info')
        
        return redirect(url_for('main.funcionario_dashboard'))
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO NO SALVAMENTO: {str(e)}")
        print(f"❌ Tipo do erro: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback completo:\n{traceback.format_exc()}")
        
        db.session.rollback()
        flash(f'ERRO DETALHADO - {type(e).__name__}: {str(e)}', 'error')
        return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))

def processar_equipe_schema_atual(rdo, dados):
    """Processa equipe usando schema atual (funcao_exercida) com logging detalhado"""
    print("   📋 Iniciando processamento da equipe...")
    funcionarios_processados = 0
    
    # Encontrar campos de funcionários
    campos_funcionarios = [k for k in dados.keys() if k.startswith('funcionario_') and k.endswith('_horas')]
    print(f"   🔍 Campos de funcionários encontrados: {campos_funcionarios}")
    
    if not campos_funcionarios:
        print("   ⚠️ Nenhum campo de funcionário encontrado nos dados")
        return "Nenhum funcionário no formulário"
    
    for key, value in dados.items():
        if key.startswith('funcionario_') and key.endswith('_horas'):
            funcionario_id = key.replace('funcionario_', '').replace('_horas', '')
            
            try:
                horas = float(value) if value else 0
                print(f"   🔍 Funcionário {funcionario_id}: {horas} horas")
                
                if horas > 0:
                    funcao = dados.get(f'funcionario_{funcionario_id}_funcao', 'Funcionário')
                    print(f"   ✅ Adicionando funcionário {funcionario_id}: {funcao} - {horas}h")
                    
                    # Verificar se funcionário existe
                    funcionario = Funcionario.query.get(int(funcionario_id))
                    if not funcionario:
                        print(f"   ❌ Funcionário ID={funcionario_id} não encontrado")
                        continue
                    
                    # Usar schema atual com funcao_exercida
                    mao_obra = RDOMaoObra()
                    mao_obra.rdo_id = rdo.id
                    mao_obra.funcionario_id = int(funcionario_id)
                    mao_obra.funcao_exercida = funcao  # Campo correto do schema
                    mao_obra.horas_trabalhadas = horas
                    
                    db.session.add(mao_obra)
                    funcionarios_processados += 1
                    print(f"   ✅ Funcionário {funcionario.nome} adicionado com sucesso")
                    
                else:
                    print(f"   ⏭️ Funcionário {funcionario_id} ignorado (0 horas)")
                    
            except (ValueError, TypeError) as e:
                print(f"   ❌ Erro ao processar funcionário {funcionario_id}: {e}")
                continue
    
    resultado = f"{funcionarios_processados} funcionários processados"
    print(f"   📊 {resultado}")
    return resultado

def processar_subatividades_schema_atual(rdo, dados):
    """Processa subatividades usando schema atual (sem subatividade_id) com logging detalhado"""
    print("   📋 Iniciando processamento das subatividades...")
    subatividades_processadas = 0
    
    # Encontrar campos de subatividades
    campos_subatividades = [k for k in dados.keys() if k.startswith('subatividade_') and k.endswith('_percentual')]
    print(f"   🔍 Campos de subatividades encontrados: {campos_subatividades}")
    
    if not campos_subatividades:
        print("   ⚠️ Nenhum campo de subatividade encontrado nos dados")
        return "Nenhuma subatividade no formulário"
    
    for key, value in dados.items():
        if key.startswith('subatividade_') and key.endswith('_percentual'):
            subatividade_id = key.replace('subatividade_', '').replace('_percentual', '')
            
            try:
                percentual = float(value) if value else 0
                print(f"   🔍 Subatividade {subatividade_id}: {percentual}%")
                
                if percentual > 0:
                    # Obter dados da subatividade
                    subatividade = SubAtividade.query.get(int(subatividade_id))
                    
                    if subatividade:
                        print(f"   ✅ Subatividade encontrada: {subatividade.nome} (Serviço ID: {subatividade.servico_id})")
                        
                        # Usar schema atual - sem campo subatividade_id
                        registro = RDOServicoSubatividade()
                        registro.rdo_id = rdo.id
                        registro.servico_id = subatividade.servico_id
                        registro.nome_subatividade = subatividade.nome
                        registro.percentual_conclusao = percentual  # Campo correto do schema
                        registro.observacoes_tecnicas = ''  # Sem observações específicas
                        registro.admin_id = rdo.admin_id
                        
                        db.session.add(registro)
                        subatividades_processadas += 1
                        print(f"   ✅ Subatividade {subatividade.nome} adicionada: {percentual}%")
                        
                    else:
                        print(f"   ❌ Subatividade ID={subatividade_id} não encontrada na base de dados")
                        
                else:
                    print(f"   ⏭️ Subatividade {subatividade_id} ignorada (0%)")
                        
            except (ValueError, TypeError) as e:
                print(f"   ❌ Erro ao processar subatividade {subatividade_id}: {e}")
                continue
    
    resultado = f"{subatividades_processadas} subatividades processadas"
    print(f"   📊 {resultado}")
    return resultado

@rdo_salvar_bp.route('/api/rdo/salvar-rapido', methods=['POST'])
def salvar_rdo_rapido():
    """API endpoint para salvamento rápido via AJAX"""
    admin_id = obter_admin_id()
    
    try:
        dados = request.get_json()
        
        # Criar RDO simples
        rdo = RDO()
        rdo.numero_rdo = gerar_numero_rdo_unico()
        rdo.admin_id = admin_id
        rdo.criado_por_id = obter_usuario_atual()
        rdo.data_relatorio = date.today()
        rdo.obra_id = dados.get('obra_id')
        rdo.status = 'Rascunho'
        
        db.session.add(rdo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO salvo com sucesso',
            'rdo_id': rdo.id,
            'numero_rdo': rdo.numero_rdo
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar RDO rápido: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@rdo_salvar_bp.route('/funcionario-rdo-novo')
def funcionario_rdo_novo():
    """Redireciona para o formulário consolidado"""
    return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))

@rdo_salvar_bp.route('/rdos')
def listar_rdos():
    """Lista RDOs do funcionário"""
    admin_id = obter_admin_id()
    
    try:
        rdos = RDO.query.filter_by(admin_id=admin_id).order_by(desc(RDO.data_relatorio)).all()
        return render_template('funcionario/lista_rdos.html', rdos=rdos)
        
    except Exception as e:
        logger.error(f"Erro ao listar RDOs: {str(e)}")
        flash('Erro ao carregar RDOs', 'error')
        return redirect(url_for('main.funcionario_dashboard'))

# Endpoint para teste
@rdo_salvar_bp.route('/rdo/teste-salvamento')
def teste_salvamento():
    """Endpoint para testar o sistema de salvamento"""
    admin_id = obter_admin_id()
    
    try:
        # Dados de teste
        dados_teste = {
            'data_relatorio': date.today().strftime('%Y-%m-%d'),
            'obra_id': '1',
            'clima_geral': 'Ensolarado',
            'condicoes_trabalho': 'Normais',
            'observacoes': 'Teste de salvamento automático',
            'funcionario_96_horas': '8',
            'funcionario_96_funcao': 'Engenheiro',
            'subatividade_1_percentual': '50'
        }
        
        # Simular request.form
        from werkzeug.datastructures import ImmutableMultiDict
        request.form = ImmutableMultiDict(dados_teste)
        
        resultado = processar_salvamento_rdo()
        
        return jsonify({
            'success': True,
            'message': 'Teste de salvamento executado',
            'admin_id': admin_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__
        })