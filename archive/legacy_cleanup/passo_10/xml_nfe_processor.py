# ===== PROCESSADOR XML NFE AVANÇADO - CONFORME REUNIÃO TÉCNICA =====

import hashlib
from models import NotaFiscal, Fornecedor, Produto, CategoriaProduto, MovimentacaoEstoque
from app import db
from datetime import datetime
from decimal import Decimal
import re

# Import condicional para XML
try:
    import xml.etree.ElementTree as ET
    LXML_AVAILABLE = True
except ImportError:
    try:
        from lxml import etree as ET
        LXML_AVAILABLE = True
    except ImportError:
        LXML_AVAILABLE = False

class ProcessadorXMLNFe:
    """Processador completo de XML NFe com validações e automação"""
    
    def __init__(self, admin_id):
        self.admin_id = admin_id
        self.namespaces = {
            'nfe': 'http://www.portalfiscal.inf.br/nfe'
        }
    
    def processar_xml(self, xml_content, usuario_id):
        """Processar XML completo com todas as validações"""
        if not LXML_AVAILABLE:
            return {'erro': 'Processamento XML não disponível. Biblioteca XML não encontrada.'}
        
        try:
            # Validar se é XML válido
            validacao_estrutura = self._validar_estrutura_xml(xml_content)
            if not validacao_estrutura['valido']:
                return validacao_estrutura
            
            # Parse do XML
            root = ET.fromstring(xml_content)
            
            # Verificar duplicata
            xml_hash = hashlib.sha256(xml_content.encode()).hexdigest()
            if self._verificar_duplicata(xml_hash):
                return {'erro': 'XML já foi importado anteriormente', 'duplicata': True}
            
            # Extrair dados principais
            dados_nfe = self._extrair_dados_nfe(root)
            if 'erro' in dados_nfe:
                return dados_nfe
            
            # Processar fornecedor
            resultado_fornecedor = self._processar_fornecedor(dados_nfe['emitente'])
            if 'erro' in resultado_fornecedor:
                return resultado_fornecedor
            
            # Criar nota fiscal
            nota_fiscal = self._criar_nota_fiscal(
                dados_nfe, 
                resultado_fornecedor['fornecedor_id'], 
                xml_content, 
                xml_hash
            )
            
            # Processar produtos
            resultado_produtos = self._processar_produtos(
                dados_nfe['produtos'], 
                nota_fiscal.id, 
                usuario_id
            )
            
            # Confirmar transação
            db.session.commit()
            
            return {
                'sucesso': True,
                'nota_fiscal_id': nota_fiscal.id,
                'fornecedor': resultado_fornecedor['fornecedor'],
                'produtos_processados': resultado_produtos['produtos_processados'],
                'produtos_criados': resultado_produtos['produtos_criados'],
                'produtos_atualizados': resultado_produtos['produtos_atualizados'],
                'valor_total_importado': float(dados_nfe['valor_total']),
                'resumo': self._gerar_resumo_processamento(dados_nfe, resultado_produtos)
            }
            
        except ET.ParseError as e:
            return {'erro': f'XML mal formado: {str(e)}'}
        except Exception as e:
            db.session.rollback()
            return {'erro': f'Erro interno: {str(e)}'}
    
    def _validar_estrutura_xml(self, xml_content):
        """Validar estrutura básica do XML NFe"""
        try:
            root = ET.fromstring(xml_content)
            
            # Verificar se é NFe
            if root.tag not in ['nfeProc', 'NFe']:
                return {'valido': False, 'erro': 'Não é um XML de NFe válido'}
            
            # Buscar nó principal
            if root.tag == 'nfeProc':
                nfe_node = root.find('.//nfe:NFe', self.namespaces)
            else:
                nfe_node = root
            
            if nfe_node is None:
                return {'valido': False, 'erro': 'Estrutura de NFe não encontrada'}
            
            # Verificar infNFe
            inf_nfe = nfe_node.find('nfe:infNFe', self.namespaces)
            if inf_nfe is None:
                return {'valido': False, 'erro': 'Nó infNFe não encontrado'}
            
            # Verificar chave de acesso
            chave = inf_nfe.get('Id', '').replace('NFe', '')
            if len(chave) != 44:
                return {'valido': False, 'erro': 'Chave de acesso inválida'}
            
            return {'valido': True}
            
        except ET.ParseError:
            return {'valido': False, 'erro': 'XML mal formado'}
    
    def _verificar_duplicata(self, xml_hash):
        """Verificar se XML já foi importado"""
        return NotaFiscal.query.filter_by(
            xml_hash=xml_hash,
            admin_id=self.admin_id
        ).first() is not None
    
    def _extrair_dados_nfe(self, root):
        """Extrair todos os dados da NFe"""
        try:
            # Encontrar nó principal
            if root.tag == 'nfeProc':
                nfe_node = root.find('.//nfe:NFe', self.namespaces)
            else:
                nfe_node = root
            
            inf_nfe = nfe_node.find('nfe:infNFe', self.namespaces)
            
            # Chave de acesso
            chave_acesso = inf_nfe.get('Id', '').replace('NFe', '')
            
            # Dados da identificação
            ide = inf_nfe.find('nfe:ide', self.namespaces)
            numero = ide.find('nfe:nNF', self.namespaces).text
            serie = ide.find('nfe:serie', self.namespaces).text
            data_emissao_str = ide.find('nfe:dhEmi', self.namespaces).text
            data_emissao = datetime.fromisoformat(data_emissao_str.replace('Z', '+00:00')).date()
            
            # Dados do emitente
            emit = inf_nfe.find('nfe:emit', self.namespaces)
            emitente = self._extrair_dados_emitente(emit)
            
            # Dados dos produtos
            produtos = self._extrair_produtos(inf_nfe)
            
            # Totais
            total = inf_nfe.find('nfe:total/nfe:ICMSTot', self.namespaces)
            valor_produtos = Decimal(total.find('nfe:vProd', self.namespaces).text)
            valor_frete = Decimal(total.find('nfe:vFrete', self.namespaces).text or '0')
            valor_desconto = Decimal(total.find('nfe:vDesc', self.namespaces).text or '0')
            valor_total = Decimal(total.find('nfe:vNF', self.namespaces).text)
            
            return {
                'chave_acesso': chave_acesso,
                'numero': numero,
                'serie': serie,
                'data_emissao': data_emissao,
                'emitente': emitente,
                'produtos': produtos,
                'valor_produtos': valor_produtos,
                'valor_frete': valor_frete,
                'valor_desconto': valor_desconto,
                'valor_total': valor_total
            }
            
        except Exception as e:
            return {'erro': f'Erro ao extrair dados da NFe: {str(e)}'}
    
    def _extrair_dados_emitente(self, emit):
        """Extrair dados do fornecedor/emitente"""
        cnpj = emit.find('nfe:CNPJ', self.namespaces)
        if cnpj is None:
            # Tentar CPF para pessoa física
            cpf = emit.find('nfe:CPF', self.namespaces)
            if cpf is not None:
                return {'documento': cpf.text, 'tipo': 'CPF'}
            else:
                raise ValueError('CNPJ/CPF do emitente não encontrado')
        
        razao_social = emit.find('nfe:xNome', self.namespaces).text
        nome_fantasia = emit.find('nfe:xFant', self.namespaces)
        ie = emit.find('nfe:IE', self.namespaces)
        
        # Endereço
        endereco_node = emit.find('nfe:enderEmit', self.namespaces)
        endereco = self._extrair_endereco(endereco_node) if endereco_node is not None else {}
        
        return {
            'documento': cnpj.text,
            'tipo': 'CNPJ',
            'razao_social': razao_social,
            'nome_fantasia': nome_fantasia.text if nome_fantasia is not None else None,
            'inscricao_estadual': ie.text if ie is not None else None,
            'endereco': endereco
        }
    
    def _extrair_endereco(self, endereco_node):
        """Extrair dados de endereço"""
        endereco = {}
        
        campos_endereco = {
            'logradouro': 'nfe:xLgr',
            'numero': 'nfe:nro',
            'complemento': 'nfe:xCpl',
            'bairro': 'nfe:xBairro',
            'municipio': 'nfe:xMun',
            'uf': 'nfe:UF',
            'cep': 'nfe:CEP'
        }
        
        for campo, xpath in campos_endereco.items():
            elemento = endereco_node.find(xpath, self.namespaces)
            if elemento is not None:
                endereco[campo] = elemento.text
        
        return endereco
    
    def _extrair_produtos(self, inf_nfe):
        """Extrair produtos da NFe"""
        produtos = []
        detalhes = inf_nfe.findall('nfe:det', self.namespaces)
        
        for det in detalhes:
            prod = det.find('nfe:prod', self.namespaces)
            
            # Dados básicos
            codigo_produto = prod.find('nfe:cProd', self.namespaces).text
            codigo_barras = prod.find('nfe:cEAN', self.namespaces)
            nome_produto = prod.find('nfe:xProd', self.namespaces).text
            ncm = prod.find('nfe:NCM', self.namespaces)
            
            # Unidade e quantidade
            unidade = prod.find('nfe:uCom', self.namespaces).text
            quantidade = Decimal(prod.find('nfe:qCom', self.namespaces).text)
            valor_unitario = Decimal(prod.find('nfe:vUnCom', self.namespaces).text)
            
            # Impostos e valores
            imposto = det.find('nfe:imposto', self.namespaces)
            dados_fiscais = self._extrair_impostos(imposto) if imposto is not None else {}
            
            produto = {
                'codigo_fornecedor': codigo_produto,
                'codigo_barras': codigo_barras.text if codigo_barras is not None and codigo_barras.text != 'SEM GTIN' else None,
                'nome': nome_produto,
                'ncm': ncm.text if ncm is not None else None,
                'unidade': unidade,
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': quantidade * valor_unitario,
                'dados_fiscais': dados_fiscais
            }
            
            produtos.append(produto)
        
        return produtos
    
    def _extrair_impostos(self, imposto_node):
        """Extrair dados de impostos"""
        impostos = {}
        
        # ICMS
        icms = imposto_node.find('.//nfe:ICMS*/nfe:vICMS', self.namespaces)
        if icms is not None:
            impostos['icms'] = Decimal(icms.text)
        
        # IPI
        ipi = imposto_node.find('.//nfe:IPI/nfe:IPITrib/nfe:vIPI', self.namespaces)
        if ipi is not None:
            impostos['ipi'] = Decimal(ipi.text)
        
        # PIS
        pis = imposto_node.find('.//nfe:PIS*/nfe:vPIS', self.namespaces)
        if pis is not None:
            impostos['pis'] = Decimal(pis.text)
        
        # COFINS
        cofins = imposto_node.find('.//nfe:COFINS*/nfe:vCOFINS', self.namespaces)
        if cofins is not None:
            impostos['cofins'] = Decimal(cofins.text)
        
        return impostos
    
    def _processar_fornecedor(self, dados_emitente):
        """Processar/criar fornecedor"""
        try:
            # Buscar fornecedor existente
            fornecedor = Fornecedor.query.filter_by(
                cnpj=dados_emitente['documento'],
                admin_id=self.admin_id
            ).first()
            
            if fornecedor:
                # Atualizar dados se necessário
                if dados_emitente.get('nome_fantasia') and not fornecedor.nome_fantasia:
                    fornecedor.nome_fantasia = dados_emitente['nome_fantasia']
                
                if dados_emitente.get('inscricao_estadual') and not fornecedor.inscricao_estadual:
                    fornecedor.inscricao_estadual = dados_emitente['inscricao_estadual']
                
                db.session.flush()
                
                return {
                    'fornecedor_id': fornecedor.id,
                    'fornecedor': fornecedor,
                    'criado': False
                }
            
            # Criar novo fornecedor
            endereco_completo = self._formatar_endereco(dados_emitente.get('endereco', {}))
            
            novo_fornecedor = Fornecedor(
                razao_social=dados_emitente['razao_social'],
                nome_fantasia=dados_emitente.get('nome_fantasia'),
                cnpj=dados_emitente['documento'],
                inscricao_estadual=dados_emitente.get('inscricao_estadual'),
                endereco=endereco_completo,
                admin_id=self.admin_id
            )
            
            db.session.add(novo_fornecedor)
            db.session.flush()
            
            return {
                'fornecedor_id': novo_fornecedor.id,
                'fornecedor': novo_fornecedor,
                'criado': True
            }
            
        except Exception as e:
            return {'erro': f'Erro ao processar fornecedor: {str(e)}'}
    
    def _formatar_endereco(self, endereco_dict):
        """Formatar endereço para texto"""
        if not endereco_dict:
            return None
        
        partes = []
        
        if endereco_dict.get('logradouro'):
            logradouro = endereco_dict['logradouro']
            if endereco_dict.get('numero'):
                logradouro += f", {endereco_dict['numero']}"
            if endereco_dict.get('complemento'):
                logradouro += f", {endereco_dict['complemento']}"
            partes.append(logradouro)
        
        if endereco_dict.get('bairro'):
            partes.append(endereco_dict['bairro'])
        
        if endereco_dict.get('municipio') and endereco_dict.get('uf'):
            partes.append(f"{endereco_dict['municipio']}/{endereco_dict['uf']}")
        
        if endereco_dict.get('cep'):
            partes.append(f"CEP: {endereco_dict['cep']}")
        
        return ' - '.join(partes) if partes else None
    
    def _criar_nota_fiscal(self, dados_nfe, fornecedor_id, xml_content, xml_hash):
        """Criar registro de nota fiscal"""
        nota_fiscal = NotaFiscal(
            numero=dados_nfe['numero'],
            serie=dados_nfe['serie'],
            chave_acesso=dados_nfe['chave_acesso'],
            fornecedor_id=fornecedor_id,
            data_emissao=dados_nfe['data_emissao'],
            valor_produtos=dados_nfe['valor_produtos'],
            valor_frete=dados_nfe['valor_frete'],
            valor_desconto=dados_nfe['valor_desconto'],
            valor_total=dados_nfe['valor_total'],
            xml_content=xml_content,
            xml_hash=xml_hash,
            status='Processada',
            data_importacao=datetime.utcnow(),
            admin_id=self.admin_id
        )
        
        db.session.add(nota_fiscal)
        db.session.flush()
        
        return nota_fiscal
    
    def _processar_produtos(self, produtos_xml, nota_fiscal_id, usuario_id):
        """Processar produtos da NFe"""
        produtos_processados = []
        produtos_criados = 0
        produtos_atualizados = 0
        
        for produto_xml in produtos_xml:
            resultado = self._processar_produto_individual(
                produto_xml, 
                nota_fiscal_id, 
                usuario_id
            )
            
            produtos_processados.append(resultado)
            
            if resultado.get('criado'):
                produtos_criados += 1
            elif resultado.get('atualizado'):
                produtos_atualizados += 1
        
        return {
            'produtos_processados': produtos_processados,
            'produtos_criados': produtos_criados,
            'produtos_atualizados': produtos_atualizados
        }
    
    def _processar_produto_individual(self, produto_xml, nota_fiscal_id, usuario_id):
        """Processar um produto individual"""
        try:
            # Buscar produto existente por código de barras
            produto = None
            if produto_xml.get('codigo_barras'):
                produto = Produto.query.filter_by(
                    codigo_barras=produto_xml['codigo_barras'],
                    admin_id=self.admin_id,
                    ativo=True
                ).first()
            
            # Se não encontrou, buscar por nome similar
            if not produto:
                produto = self._buscar_produto_por_nome(produto_xml['nome'])
            
            # Criar produto se não existir
            if not produto:
                produto = self._criar_produto_do_xml(produto_xml)
                criado = True
                atualizado = False
            else:
                # Atualizar dados do produto se necessário
                atualizado = self._atualizar_produto_do_xml(produto, produto_xml)
                criado = False
            
            # Criar movimentação de entrada (importar função aqui para evitar imports circulares)
            from almoxarifado_utils import atualizar_estoque_produto
            movimentacao = atualizar_estoque_produto(
                produto_id=produto.id,
                quantidade=produto_xml['quantidade'],
                tipo_movimentacao='ENTRADA',
                valor_unitario=produto_xml['valor_unitario'],
                nota_fiscal_id=nota_fiscal_id,
                usuario_id=usuario_id,
                observacoes=f'Importação XML NFe - {produto_xml["codigo_fornecedor"]}'
            )
            
            return {
                'produto_id': produto.id,
                'produto_nome': produto.nome,
                'quantidade': float(produto_xml['quantidade']),
                'valor_unitario': float(produto_xml['valor_unitario']),
                'valor_total': float(produto_xml['valor_total']),
                'movimentacao_id': movimentacao.id,
                'criado': criado,
                'atualizado': atualizado,
                'sucesso': True
            }
            
        except Exception as e:
            return {
                'produto_nome': produto_xml.get('nome', 'N/A'),
                'erro': str(e),
                'sucesso': False
            }
    
    def _buscar_produto_por_nome(self, nome_produto):
        """Buscar produto por nome similar"""
        # Busca exata primeiro
        produto = Produto.query.filter(
            Produto.admin_id == self.admin_id,
            Produto.nome.ilike(nome_produto),
            Produto.ativo == True
        ).first()
        
        if produto:
            return produto
        
        # Busca por palavras-chave (75% de similaridade)
        palavras = re.findall(r'\w+', nome_produto.lower())
        if len(palavras) >= 2:
            from sqlalchemy import and_, or_
            
            condicoes = []
            for palavra in palavras:
                if len(palavra) >= 4:  # Palavras significativas
                    condicoes.append(Produto.nome.ilike(f'%{palavra}%'))
            
            if len(condicoes) >= 2:
                produto = Produto.query.filter(
                    Produto.admin_id == self.admin_id,
                    Produto.ativo == True,
                    and_(*condicoes[:2])  # Pelo menos 2 palavras em comum
                ).first()
                
                return produto
        
        return None
    
    def _criar_produto_do_xml(self, produto_xml):
        """Criar novo produto baseado nos dados do XML"""
        from codigo_barras_utils import gerar_codigo_interno
        
        # Determinar categoria (simplificado)
        categoria = self._determinar_categoria_por_nome(produto_xml['nome'])
        
        # Gerar código interno
        codigo_interno = gerar_codigo_interno(
            self.admin_id, 
            categoria.codigo if categoria else None
        )
        
        # Padronizar unidade de medida
        unidade_padronizada = self._padronizar_unidade(produto_xml['unidade'])
        
        produto = Produto(
            codigo_interno=codigo_interno,
            codigo_barras=produto_xml.get('codigo_barras'),
            nome=produto_xml['nome'][:200],  # Truncar se necessário
            descricao=f"Importado de NFe - NCM: {produto_xml.get('ncm', 'N/A')}",
            categoria_id=categoria.id if categoria else None,
            unidade_medida=unidade_padronizada,
            ultimo_valor_compra=produto_xml['valor_unitario'],
            valor_medio=produto_xml['valor_unitario'],
            estoque_minimo=10,  # Valor padrão
            admin_id=self.admin_id
        )
        
        db.session.add(produto)
        db.session.flush()
        
        return produto
    
    def _determinar_categoria_por_nome(self, nome_produto):
        """Determinar categoria baseada no nome do produto"""
        # Mapeamento de palavras-chave para categorias
        mapeamentos = {
            'cimento': 'CIM',
            'ferro': 'FER',
            'aço': 'FER',
            'tinta': 'TIN',
            'elétric': 'ELE',
            'hidráulic': 'HID',
            'madeira': 'MAD',
            'ferrament': 'FER',
            'parafuso': 'FIX',
            'prego': 'FIX',
            'solda': 'SOL'
        }
        
        nome_lower = nome_produto.lower()
        
        for palavra_chave, codigo_categoria in mapeamentos.items():
            if palavra_chave in nome_lower:
                categoria = CategoriaProduto.query.filter_by(
                    codigo=codigo_categoria,
                    admin_id=self.admin_id
                ).first()
                
                if categoria:
                    return categoria
        
        # Categoria padrão
        return CategoriaProduto.query.filter_by(
            codigo='GER',
            admin_id=self.admin_id
        ).first()
    
    def _padronizar_unidade(self, unidade_xml):
        """Padronizar unidade de medida"""
        mapeamento_unidades = {
            'PC': 'UN',
            'UNID': 'UN',
            'PECA': 'UN',
            'PEÇA': 'UN',
            'KG': 'KG',
            'QUILOGRAMA': 'KG',
            'G': 'G',
            'GRAMA': 'G',
            'L': 'L',
            'LITRO': 'L',
            'ML': 'ML',
            'M': 'M',
            'METRO': 'M',
            'CM': 'CM',
            'SC': 'SC',
            'SACO': 'SC',
            'CX': 'CX',
            'CAIXA': 'CX'
        }
        
        unidade_upper = unidade_xml.upper().strip()
        return mapeamento_unidades.get(unidade_upper, unidade_upper[:10])
    
    def _atualizar_produto_do_xml(self, produto, produto_xml):
        """Atualizar produto existente com dados do XML"""
        atualizado = False
        
        # Atualizar código de barras se estava vazio
        if not produto.codigo_barras and produto_xml.get('codigo_barras'):
            produto.codigo_barras = produto_xml['codigo_barras']
            atualizado = True
        
        # Atualizar último valor de compra
        if produto_xml['valor_unitario'] != produto.ultimo_valor_compra:
            produto.ultimo_valor_compra = produto_xml['valor_unitario']
            atualizado = True
        
        if atualizado:
            db.session.flush()
        
        return atualizado
    
    def _gerar_resumo_processamento(self, dados_nfe, resultado_produtos):
        """Gerar resumo do processamento"""
        return {
            'numero_nf': f"{dados_nfe['numero']}/{dados_nfe['serie']}",
            'data_emissao': dados_nfe['data_emissao'].isoformat(),
            'total_produtos': len(dados_nfe['produtos']),
            'produtos_criados': resultado_produtos['produtos_criados'],
            'produtos_atualizados': resultado_produtos['produtos_atualizados'],
            'valor_total': float(dados_nfe['valor_total']),
            'chave_acesso': dados_nfe['chave_acesso'][:8] + '...'
        }

# ===== FUNÇÕES UTILITÁRIAS =====

def validar_xml_nfe_rapido(xml_content):
    """Validação rápida de XML NFe"""
    if not LXML_AVAILABLE:
        return {'valido': False, 'erro': 'Processamento XML não disponível'}
    
    try:
        root = ET.fromstring(xml_content)
        
        # Verificar estrutura básica
        if root.tag not in ['nfeProc', 'NFe']:
            return {'valido': False, 'erro': 'Não é um XML NFe'}
        
        # Verificar se tem produtos
        produtos = root.findall('.//det', {'nfe': 'http://www.portalfiscal.inf.br/nfe'})
        if len(produtos) == 0:
            return {'valido': False, 'erro': 'NFe sem produtos'}
        
        return {'valido': True, 'total_produtos': len(produtos)}
        
    except ET.ParseError:
        return {'valido': False, 'erro': 'XML mal formado'}

def extrair_resumo_xml(xml_content):
    """Extrair apenas resumo do XML para pré-visualização"""
    if not LXML_AVAILABLE:
        return {'valido': False, 'erro': 'Processamento XML não disponível'}
    
    try:
        root = ET.fromstring(xml_content)
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Buscar dados básicos
        if root.tag == 'nfeProc':
            inf_nfe = root.find('.//nfe:infNFe', ns)
        else:
            inf_nfe = root.find('nfe:infNFe', ns)
        
        # Dados básicos
        ide = inf_nfe.find('nfe:ide', ns)
        numero = ide.find('nfe:nNF', ns).text
        serie = ide.find('nfe:serie', ns).text
        
        # Emitente
        emit = inf_nfe.find('nfe:emit', ns)
        razao_social = emit.find('nfe:xNome', ns).text
        cnpj = emit.find('nfe:CNPJ', ns).text
        
        # Total
        total = inf_nfe.find('nfe:total/nfe:ICMSTot', ns)
        valor_total = total.find('nfe:vNF', ns).text
        
        # Produtos
        produtos = inf_nfe.findall('nfe:det', ns)
        
        return {
            'numero_serie': f"{numero}/{serie}",
            'fornecedor': razao_social,
            'cnpj': cnpj,
            'valor_total': float(valor_total),
            'total_produtos': len(produtos),
            'valido': True
        }
        
    except Exception as e:
        return {'valido': False, 'erro': str(e)}