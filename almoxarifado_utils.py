from models import db
# ===== MÓDULO 4: ALMOXARIFADO INTELIGENTE - BASEADO NA REUNIÃO TÉCNICA =====

import hashlib
from models import (Produto, CategoriaProduto, Fornecedor, NotaFiscal, MovimentacaoEstoque, RDO, Funcionario, Obra, Usuario)
import xml.etree.ElementTree as ET
from decimal import Decimal
import re
import base64
import io
from datetime import date, datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# ===== FUNÇÕES DE CÓDIGO DE BARRAS =====

def validar_codigo_barras(codigo):
    """Validar código de barras (EAN-13, EAN-8, Code-128)"""
    if not codigo:
        return False
    
    # Remover espaços e caracteres especiais
    codigo = re.sub(r'[^0-9]', '', codigo)
    
    # EAN-13 (13 dígitos)
    if len(codigo) == 13:
        return validar_ean13(codigo)
    
    # EAN-8 (8 dígitos)
    elif len(codigo) == 8:
        return validar_ean8(codigo)
    
    # Code-128 ou outros formatos (aceitar se tiver entre 4 e 50 caracteres)
    elif 4 <= len(codigo) <= 50:
        return True
    
    return False

def validar_ean13(codigo):
    """Validar código EAN-13 com dígito verificador"""
    if len(codigo) != 13:
        return False
    
    try:
        # Calcular dígito verificador
        soma = 0
        for i, digito in enumerate(codigo[:-1]):
            peso = 1 if i % 2 == 0 else 3
            soma += int(digito) * peso
        
        digito_verificador = (10 - (soma % 10)) % 10
        return int(codigo[-1]) == digito_verificador
    except:
        return False

def validar_ean8(codigo):
    """Validar código EAN-8 com dígito verificador"""
    if len(codigo) != 8:
        return False
    
    try:
        # Calcular dígito verificador
        soma = 0
        for i, digito in enumerate(codigo[:-1]):
            peso = 3 if i % 2 == 0 else 1
            soma += int(digito) * peso
        
        digito_verificador = (10 - (soma % 10)) % 10
        return int(codigo[-1]) == digito_verificador
    except:
        return False

def gerar_codigo_interno(admin_id, categoria_codigo=None):
    """Gerar código interno único para produto"""
    # Formato: CAT001, CAT002, etc.
    if not categoria_codigo:
        categoria_codigo = "PRD"
    
    # Buscar último código da categoria
    ultimo_produto = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.codigo_interno.like(f'{categoria_codigo}%')
    ).order_by(Produto.codigo_interno.desc()).first()
    
    if ultimo_produto:
        try:
            ultimo_numero = int(ultimo_produto.codigo_interno[3:])
            novo_numero = ultimo_numero + 1
        except:
            novo_numero = 1
    else:
        novo_numero = 1
    
    return f"{categoria_codigo}{novo_numero:03d}"

# ===== FUNÇÕES DE ESTOQUE =====

def atualizar_estoque_produto(produto_id, quantidade, tipo_movimentacao, **kwargs):
    """Atualizar estoque do produto e criar movimentação"""
    produto = Produto.query.get(produto_id)
    if not produto:
        raise ValueError("Produto não encontrado")
    
    # Validar quantidade
    if quantidade <= 0:
        raise ValueError("Quantidade deve ser positiva")
    
    # Validar tipo de movimentação
    tipos_validos = ['ENTRADA', 'SAIDA', 'DEVOLUCAO', 'AJUSTE']
    if tipo_movimentacao not in tipos_validos:
        raise ValueError(f"Tipo de movimentação inválido. Use: {', '.join(tipos_validos)}")
    
    # Calcular nova quantidade
    quantidade_anterior = produto.estoque_atual
    
    if tipo_movimentacao == 'ENTRADA':
        nova_quantidade = quantidade_anterior + quantidade
    elif tipo_movimentacao == 'SAIDA':
        if quantidade_anterior < quantidade:
            raise ValueError(f"Estoque insuficiente. Disponível: {quantidade_anterior}")
        nova_quantidade = quantidade_anterior - quantidade
    elif tipo_movimentacao == 'DEVOLUCAO':
        nova_quantidade = quantidade_anterior + quantidade
    elif tipo_movimentacao == 'AJUSTE':
        # Para ajuste, a quantidade é o valor final desejado
        nova_quantidade = quantidade
        quantidade = nova_quantidade - quantidade_anterior  # Diferença para movimentação
    
    # Atualizar estoque
    produto.estoque_atual = nova_quantidade
    
    # Atualizar valor médio se for entrada com valor
    valor_unitario = kwargs.get('valor_unitario')
    if tipo_movimentacao == 'ENTRADA' and valor_unitario:
        valor_total_anterior = quantidade_anterior * produto.valor_medio
        valor_total_entrada = quantidade * valor_unitario
        valor_total_novo = valor_total_anterior + valor_total_entrada
        
        if nova_quantidade > 0:
            produto.valor_medio = valor_total_novo / nova_quantidade
        
        produto.ultimo_valor_compra = valor_unitario
    
    # Criar movimentação
    movimentacao = MovimentacaoEstoque(
        produto_id=produto_id,
        tipo_movimentacao=tipo_movimentacao,
        quantidade=abs(quantidade),
        quantidade_anterior=quantidade_anterior,
        quantidade_posterior=nova_quantidade,
        valor_unitario=valor_unitario,
        valor_total=abs(quantidade) * valor_unitario if valor_unitario else None,
        data_movimentacao=kwargs.get('data_movimentacao', datetime.utcnow()),
        nota_fiscal_id=kwargs.get('nota_fiscal_id'),
        rdo_id=kwargs.get('rdo_id'),
        funcionario_id=kwargs.get('funcionario_id'),
        obra_id=kwargs.get('obra_id'),
        usuario_id=kwargs.get('usuario_id'),
        observacoes=kwargs.get('observacoes'),
        ip_address=kwargs.get('ip_address'),
        admin_id=produto.admin_id
    )
    
    db.session.add(movimentacao)
    db.session.commit()
    
    return movimentacao

def calcular_estoque_minimo_inteligente(produto_id, dias_historico=90):
    """Calcular estoque mínimo baseado em IA"""
    produto = Produto.query.get(produto_id)
    if not produto:
        return 0
    
    # Buscar movimentações de saída dos últimos X dias
    data_inicio = datetime.utcnow() - timedelta(days=dias_historico)
    
    movimentacoes = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.produto_id == produto_id,
        MovimentacaoEstoque.tipo_movimentacao == 'SAIDA',
        MovimentacaoEstoque.data_movimentacao >= data_inicio
    ).all()
    
    if not movimentacoes:
        return produto.estoque_minimo or 10  # Valor padrão
    
    # Calcular consumo médio diário
    total_consumido = sum(mov.quantidade for mov in movimentacoes)
    consumo_medio_diario = total_consumido / dias_historico
    
    # Aplicar margem de segurança (30 dias de consumo)
    estoque_minimo_sugerido = consumo_medio_diario * 30
    
    # Considerar sazonalidade (picos de consumo)
    consumos_diarios = defaultdict(float)
    for mov in movimentacoes:
        data_mov = mov.data_movimentacao.date()
        consumos_diarios[data_mov] += mov.quantidade
    
    if consumos_diarios:
        consumos = list(consumos_diarios.values())
        consumo_maximo = max(consumos)
        
        # Se o pico for muito maior que a média, aumentar margem
        if consumo_maximo > (consumo_medio_diario * 2):
            estoque_minimo_sugerido *= 1.5
    
    return max(estoque_minimo_sugerido, 1)  # Mínimo de 1 unidade

def prever_ruptura_estoque(produto_id, dias_futuros=30):
    """Prever quando o estoque pode acabar"""
    produto = Produto.query.get(produto_id)
    if not produto:
        return None
    
    # Calcular consumo médio dos últimos 30 dias
    data_inicio = datetime.utcnow() - timedelta(days=30)
    
    movimentacoes_saida = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.produto_id == produto_id,
        MovimentacaoEstoque.tipo_movimentacao == 'SAIDA',
        MovimentacaoEstoque.data_movimentacao >= data_inicio
    ).all()
    
    if not movimentacoes_saida:
        return None  # Sem histórico de consumo
    
    total_consumido = sum(mov.quantidade for mov in movimentacoes_saida)
    consumo_medio_diario = total_consumido / 30
    
    if consumo_medio_diario <= 0:
        return None
    
    # Calcular dias até ruptura
    dias_restantes = produto.estoque_atual / consumo_medio_diario
    
    if dias_restantes <= dias_futuros:
        data_ruptura = datetime.now() + timedelta(days=dias_restantes)
        return {
            'previsao_ruptura': data_ruptura.strftime('%d/%m/%Y'),
            'dias_restantes': int(dias_restantes),
            'consumo_medio_diario': float(consumo_medio_diario),
            'recomendacao_compra': True
        }
    
    return None

# ===== FUNÇÕES DE PROCESSAMENTO XML NFE =====

def processar_xml_nfe(xml_content, admin_id):
    """Processar XML de Nota Fiscal Eletrônica"""
    try:
        # Validar XML
        xml_hash = hashlib.sha256(xml_content.encode()).hexdigest()
        
        # Verificar se já existe
        nf_existente = NotaFiscal.query.filter_by(xml_hash=xml_hash).first()
        if nf_existente:
            return {'erro': 'Nota fiscal já foi importada anteriormente'}
        
        # Fazer parse do XML
        root = ET.fromstring(xml_content)
        
        # Namespaces da NFe
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Buscar dados principais
        inf_nfe = root.find('.//nfe:infNFe', ns)
        if inf_nfe is None:
            return {'erro': 'XML inválido: estrutura de NFe não encontrada'}
        
        # Chave de acesso
        chave_acesso = inf_nfe.get('Id', '').replace('NFe', '')
        
        # Dados do emitente (fornecedor)
        emit = inf_nfe.find('nfe:emit', ns)
        cnpj = emit.find('nfe:CNPJ', ns).text
        
        # Buscar ou criar fornecedor
        fornecedor = Fornecedor.query.filter_by(
            cnpj=cnpj,
            admin_id=admin_id
        ).first()
        
        if not fornecedor:
            razao_social = emit.find('nfe:xNome', ns)
            nome_fantasia = emit.find('nfe:xFant', ns)
            
            fornecedor = Fornecedor(
                razao_social=razao_social.text if razao_social is not None else 'Não informado',
                nome_fantasia=nome_fantasia.text if nome_fantasia is not None else None,
                cnpj=cnpj,
                admin_id=admin_id
            )
            db.session.add(fornecedor)
            db.session.flush()
        
        # Dados da nota fiscal
        ide = inf_nfe.find('nfe:ide', ns)
        numero_nf = ide.find('nfe:nNF', ns).text
        serie_nf = ide.find('nfe:serie', ns).text
        data_emissao = datetime.strptime(ide.find('nfe:dhEmi', ns).text[:10], '%Y-%m-%d').date()
        
        # Valores totais
        total = inf_nfe.find('nfe:total/nfe:ICMSTot', ns)
        valor_produtos = Decimal(total.find('nfe:vProd', ns).text)
        valor_frete = Decimal(total.find('nfe:vFrete', ns).text or '0')
        valor_desconto = Decimal(total.find('nfe:vDesc', ns).text or '0')
        valor_total = Decimal(total.find('nfe:vNF', ns).text)
        
        # Criar nota fiscal
        nota_fiscal = NotaFiscal(
            numero=numero_nf,
            serie=serie_nf,
            chave_acesso=chave_acesso,
            fornecedor_id=fornecedor.id,
            data_emissao=data_emissao,
            valor_produtos=valor_produtos,
            valor_frete=valor_frete,
            valor_desconto=valor_desconto,
            valor_total=valor_total,
            xml_content=xml_content,
            xml_hash=xml_hash,
            status='Pendente',
            admin_id=admin_id
        )
        
        db.session.add(nota_fiscal)
        db.session.flush()
        
        # Extrair produtos
        produtos_xml = []
        detalhes = inf_nfe.findall('nfe:det', ns)
        
        for det in detalhes:
            prod = det.find('nfe:prod', ns)
            
            codigo_produto = prod.find('nfe:cProd', ns).text
            codigo_barras = prod.find('nfe:cEAN', ns)
            nome_produto = prod.find('nfe:xProd', ns).text
            unidade = prod.find('nfe:uCom', ns).text
            quantidade = Decimal(prod.find('nfe:qCom', ns).text)
            valor_unitario = Decimal(prod.find('nfe:vUnCom', ns).text)
            
            produtos_xml.append({
                'codigo_produto': codigo_produto,
                'codigo_barras': codigo_barras.text if codigo_barras is not None else None,
                'nome': nome_produto,
                'unidade': unidade,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': quantidade * valor_unitario
            })
        
        db.session.commit()
        
        return {
            'sucesso': True,
            'nota_fiscal_id': nota_fiscal.id,
            'fornecedor': {
                'id': fornecedor.id,
                'razao_social': fornecedor.razao_social,
                'cnpj': fornecedor.cnpj
            },
            'produtos': produtos_xml,
            'resumo': {
                'numero': numero_nf,
                'serie': serie_nf,
                'data_emissao': data_emissao.isoformat(),
                'valor_total': float(valor_total),
                'quantidade_produtos': len(produtos_xml)
            }
        }
        
    except ET.ParseError:
        return {'erro': 'XML inválido: erro de formatação'}
    except Exception as e:
        return {'erro': f'Erro ao processar XML: {str(e)}'}

# ===== FUNÇÕES DE INTEGRAÇÃO COM RDO =====

def obter_materiais_rdo(rdo_id):
    """Obter materiais lançados em um RDO específico"""
    movimentacoes = MovimentacaoEstoque.query.filter_by(
        rdo_id=rdo_id,
        tipo_movimentacao='SAIDA'
    ).all()
    
    materiais = []
    for mov in movimentacoes:
        materiais.append({
            'id': mov.id,
            'produto_id': mov.produto_id,
            'produto_nome': mov.produto.nome,
            'produto_unidade': mov.produto.unidade_medida,
            'quantidade': float(mov.quantidade),
            'valor_unitario': float(mov.valor_unitario) if mov.valor_unitario else None,
            'valor_total': float(mov.valor_total) if mov.valor_total else None,
            'data_lancamento': mov.data_movimentacao.isoformat(),
            'usuario_nome': mov.usuario.nome if mov.usuario else None,
            'observacoes': mov.observacoes
        })
    
    return materiais

def lancar_material_rdo(rdo_id, produto_id, quantidade, usuario_id, observacoes=None):
    """Lançar material em um RDO específico"""
    # Validar RDO
    rdo = RDO.query.get(rdo_id)
    if not rdo:
        raise ValueError("RDO não encontrado")
    
    # Validar produto
    produto = Produto.query.get(produto_id)
    if not produto:
        raise ValueError("Produto não encontrado")
    
    # Obter dados da obra e funcionário através da alocação
    alocacao = AlocacaoEquipe.query.filter_by(rdo_gerado_id=rdo_id).first()
    funcionario_id = alocacao.funcionario_id if alocacao else None
    obra_id = rdo.obra_id
    
    # Criar movimentação de saída
    movimentacao = atualizar_estoque_produto(
        produto_id=produto_id,
        quantidade=quantidade,
        tipo_movimentacao='SAIDA',
        rdo_id=rdo_id,
        funcionario_id=funcionario_id,
        obra_id=obra_id,
        usuario_id=usuario_id,
        observacoes=observacoes or f'Material usado no RDO {rdo.numero_rdo}'
    )
    
    return movimentacao

# ===== FUNÇÕES DE RELATÓRIOS =====

def gerar_relatorio_estoque(admin_id, filtros=None):
    """Gerar relatório completo de estoque"""
    query = Produto.query.filter_by(admin_id=admin_id, ativo=True)
    
    # Aplicar filtros
    if filtros:
        if filtros.get('categoria_id'):
            query = query.filter_by(categoria_id=filtros['categoria_id'])
        
        if filtros.get('status_estoque'):
            status = filtros['status_estoque']
            if status == 'BAIXO':
                query = query.filter(Produto.estoque_atual <= Produto.estoque_minimo)
            elif status == 'CRITICO':
                query = query.filter(Produto.estoque_atual <= (Produto.estoque_minimo * 0.5))
            elif status == 'ZERADO':
                query = query.filter(Produto.estoque_atual <= 0)
    
    produtos = query.order_by(Produto.nome).all()
    
    relatorio = {
        'produtos': [],
        'resumo': {
            'total_produtos': len(produtos),
            'valor_total_estoque': 0,
            'produtos_baixo_estoque': 0,
            'produtos_criticos': 0,
            'produtos_zerados': 0
        }
    }
    
    for produto in produtos:
        item = {
            'id': produto.id,
            'codigo_interno': produto.codigo_interno,
            'nome': produto.nome,
            'categoria': produto.categoria.nome,
            'unidade_medida': produto.unidade_medida,
            'estoque_atual': float(produto.estoque_atual),
            'estoque_minimo': float(produto.estoque_minimo),
            'valor_medio': float(produto.valor_medio),
            'valor_estoque': float(produto.valor_estoque_atual),
            'status_estoque': produto.status_estoque
        }
        
        relatorio['produtos'].append(item)
        relatorio['resumo']['valor_total_estoque'] += item['valor_estoque']
        
        if produto.status_estoque == 'BAIXO':
            relatorio['resumo']['produtos_baixo_estoque'] += 1
        elif produto.status_estoque == 'CRITICO':
            relatorio['resumo']['produtos_criticos'] += 1
        elif produto.status_estoque == 'ZERADO':
            relatorio['resumo']['produtos_zerados'] += 1
    
    return relatorio

def calcular_kpis_almoxarifado(admin_id):
    """Calcular KPIs do almoxarifado"""
    hoje = datetime.now().date()
    inicio_mes = hoje.replace(day=1)
    
    # Total de produtos ativos
    total_produtos = Produto.query.filter_by(admin_id=admin_id, ativo=True).count()
    
    # Produtos com estoque baixo
    produtos_baixo = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.ativo == True,
        Produto.estoque_atual <= Produto.estoque_minimo
    ).count()
    
    # Valor total do estoque
    produtos = Produto.query.filter_by(admin_id=admin_id, ativo=True).all()
    valor_total_estoque = sum(produto.valor_estoque_atual for produto in produtos)
    
    # Movimentações do mês
    movimentacoes_mes = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.admin_id == admin_id,
        MovimentacaoEstoque.data_movimentacao >= inicio_mes
    ).count()
    
    # Entradas e saídas do mês
    entradas_mes = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.admin_id == admin_id,
        MovimentacaoEstoque.tipo_movimentacao == 'ENTRADA',
        MovimentacaoEstoque.data_movimentacao >= inicio_mes
    ).count()
    
    saidas_mes = MovimentacaoEstoque.query.filter(
        MovimentacaoEstoque.admin_id == admin_id,
        MovimentacaoEstoque.tipo_movimentacao == 'SAIDA',
        MovimentacaoEstoque.data_movimentacao >= inicio_mes
    ).count()
    
    return {
        'total_produtos': total_produtos,
        'produtos_baixo_estoque': produtos_baixo,
        'valor_total_estoque': float(valor_total_estoque),
        'movimentacoes_mes': movimentacoes_mes,
        'entradas_mes': entradas_mes,
        'saidas_mes': saidas_mes,
        'taxa_reposicao': round((produtos_baixo / total_produtos * 100) if total_produtos > 0 else 0, 2),
        'giro_mes': round((saidas_mes / total_produtos) if total_produtos > 0 else 0, 2)
    }

# ===== FUNÇÕES DE MOVIMENTAÇÃO MANUAL (CRUD) =====

def apply_movimento_manual(movimento):
    """
    Aplica um movimento manual ao estoque com controle de lote/valor/FIFO
    
    Args:
        movimento: Objeto AlmoxarifadoMovimento
        
    Returns:
        dict: {'sucesso': bool, 'mensagem': str}
    """
    from models import AlmoxarifadoItem, AlmoxarifadoEstoque
    from sqlalchemy import func
    
    try:
        if not movimento.impacta_estoque:
            return {'sucesso': True, 'mensagem': 'Movimento não impacta estoque'}
        
        item = AlmoxarifadoItem.query.get(movimento.item_id)
        if not item:
            return {'sucesso': False, 'mensagem': 'Item não encontrado'}
        
        # Garantir que quantidade é Decimal (evitar erro de tipo Decimal + float)
        if not isinstance(movimento.quantidade, Decimal):
            movimento.quantidade = Decimal(str(movimento.quantidade))
        
        # ===== SERIALIZADOS =====
        if item.tipo_controle == 'SERIALIZADO':
            if movimento.tipo_movimento == 'ENTRADA':
                # Verificar se número de série já existe
                estoque_existente = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    admin_id=movimento.admin_id
                ).first()
                
                if estoque_existente:
                    return {'sucesso': False, 'mensagem': f'Número de série {movimento.numero_serie} já cadastrado'}
                
                novo_estoque = AlmoxarifadoEstoque(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    quantidade=1,
                    status='DISPONIVEL',
                    valor_unitario=movimento.valor_unitario,
                    lote=movimento.lote,
                    admin_id=movimento.admin_id
                )
                db.session.add(novo_estoque)
                
            elif movimento.tipo_movimento == 'SAIDA':
                # Buscar item DISPONIVEL (não EM_USO)
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    status='DISPONIVEL',
                    admin_id=movimento.admin_id
                ).first()
                
                if not estoque:
                    return {'sucesso': False, 'mensagem': f'Item serializado {movimento.numero_serie} não disponível no estoque'}
                
                estoque.status = 'EM_USO'
                estoque.funcionario_atual_id = movimento.funcionario_id
                estoque.obra_id = movimento.obra_id
                
            elif movimento.tipo_movimento == 'DEVOLUCAO':
                # Buscar item EM_USO para devolver
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    status='EM_USO',
                    admin_id=movimento.admin_id
                ).first()
                
                if not estoque:
                    return {'sucesso': False, 'mensagem': f'Item serializado {movimento.numero_serie} não está em uso'}
                
                estoque.status = 'DISPONIVEL'
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
        
        # ===== CONSUMÍVEIS =====
        else:
            if movimento.tipo_movimento == 'ENTRADA':
                # ENTRADA: Criar novo registro por lote/valor ou incrementar existente exato
                if movimento.lote or movimento.valor_unitario:
                    # Buscar registro com mesmo lote E valor (segregação correta)
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        valor_unitario=movimento.valor_unitario,
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        # Incrementa no mesmo lote/valor
                        estoque.quantidade += movimento.quantidade
                    else:
                        # Cria novo registro para novo lote/valor
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            lote=movimento.lote,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
                else:
                    # Sem lote/valor: usa primeiro disponível
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        estoque.quantidade += movimento.quantidade
                    else:
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            lote=movimento.lote,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
                    
            elif movimento.tipo_movimento == 'SAIDA':
                # VALIDAR estoque total ANTES de aplicar
                estoque_total = db.session.query(func.coalesce(func.sum(AlmoxarifadoEstoque.quantidade), 0)).filter_by(
                    item_id=item.id,
                    status='DISPONIVEL',
                    admin_id=movimento.admin_id
                ).scalar() or 0
                
                if estoque_total < movimento.quantidade:
                    return {
                        'sucesso': False, 
                        'mensagem': f'Estoque insuficiente. Disponível: {estoque_total} {item.unidade or "un"}'
                    }
                
                # SAIDA: Consumir por FIFO (primeiro lote mais antigo) ou lote específico
                quantidade_restante = movimento.quantidade
                
                if movimento.lote:
                    # Consumir de lote específico
                    estoques = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        admin_id=movimento.admin_id
                    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()
                else:
                    # FIFO: lotes mais antigos primeiro
                    estoques = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()
                
                # Consumir de múltiplos lotes se necessário
                for estoque in estoques:
                    if quantidade_restante <= 0:
                        break
                    
                    if estoque.quantidade >= quantidade_restante:
                        # Este lote tem suficiente
                        estoque.quantidade -= quantidade_restante
                        quantidade_restante = 0
                    else:
                        # Consumir tudo deste lote e continuar
                        quantidade_restante -= estoque.quantidade
                        estoque.quantidade = 0
                
                if quantidade_restante > 0:
                    return {
                        'sucesso': False, 
                        'mensagem': f'Erro ao consumir estoque. Faltam {quantidade_restante} unidades'
                    }
                    
            elif movimento.tipo_movimento == 'DEVOLUCAO':
                # DEVOLUÇÃO: Incrementar no lote original ou criar novo
                if movimento.lote:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        estoque.quantidade += movimento.quantidade
                    else:
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            lote=movimento.lote,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
                else:
                    # Sem lote: usar primeiro disponível ou criar
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        estoque.quantidade += movimento.quantidade
                    else:
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
        
        db.session.flush()
        return {'sucesso': True, 'mensagem': 'Estoque atualizado com sucesso'}
        
    except Exception as e:
        logger.error(f'Erro ao aplicar movimento {movimento.id}: {str(e)}')
        return {'sucesso': False, 'mensagem': f'Erro ao aplicar movimento: {str(e)}'}


def rollback_movimento_manual(movimento):
    """
    Reverte um movimento manual do estoque (para edição/exclusão)
    Lógica inversa ao apply_movimento_manual
    
    Args:
        movimento: Objeto AlmoxarifadoMovimento
        
    Returns:
        dict: {'sucesso': bool, 'mensagem': str}
    """
    from models import AlmoxarifadoItem, AlmoxarifadoEstoque
    from sqlalchemy import func
    
    try:
        if not movimento.impacta_estoque:
            return {'sucesso': True, 'mensagem': 'Movimento não impacta estoque'}
        
        item = AlmoxarifadoItem.query.get(movimento.item_id)
        if not item:
            return {'sucesso': False, 'mensagem': 'Item não encontrado'}
        
        # Garantir que quantidade é Decimal (evitar erro de tipo Decimal + float)
        if not isinstance(movimento.quantidade, Decimal):
            movimento.quantidade = Decimal(str(movimento.quantidade))
        
        # ===== SERIALIZADOS =====
        if item.tipo_controle == 'SERIALIZADO':
            if movimento.tipo_movimento == 'ENTRADA':
                # Rollback ENTRADA: Remover item do estoque (não importa o status)
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    admin_id=movimento.admin_id
                ).first()
                
                if estoque:
                    db.session.delete(estoque)
                else:
                    logger.warning(f'Rollback ENTRADA: Item serializado {movimento.numero_serie} não encontrado')
                    
            elif movimento.tipo_movimento == 'SAIDA':
                # Rollback SAIDA: Item está EM_USO, reverter para DISPONIVEL
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    admin_id=movimento.admin_id
                ).first()
                
                if estoque:
                    # Verificar se está realmente EM_USO (esperado após SAIDA)
                    if estoque.status == 'EM_USO':
                        estoque.status = 'DISPONIVEL'
                        estoque.funcionario_atual_id = None
                        estoque.obra_id = None
                    else:
                        logger.warning(f'Rollback SAIDA: Item {movimento.numero_serie} com status inesperado {estoque.status}')
                        # Reverter mesmo assim para não travar
                        estoque.status = 'DISPONIVEL'
                        estoque.funcionario_atual_id = None
                        estoque.obra_id = None
                else:
                    return {'sucesso': False, 'mensagem': f'Item serializado {movimento.numero_serie} não encontrado para rollback'}
                    
            elif movimento.tipo_movimento == 'DEVOLUCAO':
                # Rollback DEVOLUCAO: Item está DISPONIVEL, reverter para EM_USO
                estoque = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    numero_serie=movimento.numero_serie,
                    admin_id=movimento.admin_id
                ).first()
                
                if estoque:
                    # Verificar se está DISPONIVEL (esperado após DEVOLUCAO)
                    if estoque.status == 'DISPONIVEL':
                        estoque.status = 'EM_USO'
                        estoque.funcionario_atual_id = movimento.funcionario_id
                        estoque.obra_id = movimento.obra_id
                    else:
                        logger.warning(f'Rollback DEVOLUCAO: Item {movimento.numero_serie} com status inesperado {estoque.status}')
                        # Reverter mesmo assim
                        estoque.status = 'EM_USO'
                        estoque.funcionario_atual_id = movimento.funcionario_id
                        estoque.obra_id = movimento.obra_id
                else:
                    return {'sucesso': False, 'mensagem': f'Item serializado {movimento.numero_serie} não encontrado para rollback'}
        
        # ===== CONSUMÍVEIS =====
        else:
            if movimento.tipo_movimento == 'ENTRADA':
                # Rollback ENTRADA: Subtrair quantidade (reverter adição)
                # Buscar pelo lote/valor específico se existir
                if movimento.lote or movimento.valor_unitario:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        valor_unitario=movimento.valor_unitario,
                        admin_id=movimento.admin_id
                    ).first()
                else:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).first()
                
                if estoque:
                    if estoque.quantidade >= movimento.quantidade:
                        estoque.quantidade -= movimento.quantidade
                        # Remover registro se quantidade zerar
                        if estoque.quantidade == 0:
                            db.session.delete(estoque)
                    else:
                        logger.warning(f'Rollback ENTRADA: Quantidade insuficiente para reverter. Estoque: {estoque.quantidade}, Movimento: {movimento.quantidade}')
                        # Zerar mesmo assim para não deixar negativo
                        db.session.delete(estoque)
                else:
                    logger.warning(f'Rollback ENTRADA: Estoque não encontrado para item {item.id}')
                    
            elif movimento.tipo_movimento == 'SAIDA':
                # Rollback SAIDA: Adicionar quantidade de volta (reverter subtração)
                # Preferir adicionar no lote original se existir
                if movimento.lote:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        estoque.quantidade += movimento.quantidade
                    else:
                        # Criar novo registro com o lote original
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            lote=movimento.lote,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
                else:
                    # Sem lote: adicionar em registro existente ou criar novo
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).first()
                    
                    if estoque:
                        estoque.quantidade += movimento.quantidade
                    else:
                        novo_estoque = AlmoxarifadoEstoque(
                            item_id=item.id,
                            quantidade=movimento.quantidade,
                            status='DISPONIVEL',
                            valor_unitario=movimento.valor_unitario,
                            admin_id=movimento.admin_id
                        )
                        db.session.add(novo_estoque)
                    
            elif movimento.tipo_movimento == 'DEVOLUCAO':
                # Rollback DEVOLUCAO: Subtrair quantidade (reverter adição)
                if movimento.lote:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        lote=movimento.lote,
                        admin_id=movimento.admin_id
                    ).first()
                else:
                    estoque = AlmoxarifadoEstoque.query.filter_by(
                        item_id=item.id,
                        status='DISPONIVEL',
                        admin_id=movimento.admin_id
                    ).first()
                
                if estoque:
                    if estoque.quantidade >= movimento.quantidade:
                        estoque.quantidade -= movimento.quantidade
                        # Remover se zerar
                        if estoque.quantidade == 0:
                            db.session.delete(estoque)
                    else:
                        logger.warning(f'Rollback DEVOLUCAO: Quantidade insuficiente. Zerando estoque.')
                        db.session.delete(estoque)
                else:
                    logger.warning(f'Rollback DEVOLUCAO: Estoque não encontrado para item {item.id}')
        
        db.session.flush()
        return {'sucesso': True, 'mensagem': 'Movimento revertido com sucesso'}
        
    except Exception as e:
        logger.error(f'Erro ao reverter movimento {movimento.id}: {str(e)}')
        return {'sucesso': False, 'mensagem': f'Erro ao reverter movimento: {str(e)}'}
