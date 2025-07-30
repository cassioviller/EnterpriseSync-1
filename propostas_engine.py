#!/usr/bin/env python3
"""
MÓDULO DE PROPOSTAS COMERCIAIS AUTOMÁTICAS - SIGE v8.1
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Engine completo para geração e gestão de propostas comerciais
Funcionalidades:
- Cálculo automático de valores baseado em serviços e quantidades
- Geração de PDFs profissionais
- Conversão automática para obras quando aprovadas
- Controle de status e histórico

Autor: Manus AI
Data: 30 de Julho de 2025
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from app import db
from models import (
    Proposta, ItemProposta, StatusProposta, HistoricoStatusProposta,
    Servico, Obra, Usuario, Funcionario, ServicoObra
)
from flask_login import current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
import os
import tempfile

class PropostasEngine:
    """Engine principal para gestão de propostas comerciais"""
    
    def __init__(self):
        self.margem_lucro_padrao = 30.0  # 30% margem padrão
        self.prazo_validade_dias = 30    # 30 dias validade padrão
        
    def gerar_numero_proposta(self, admin_id=None):
        """Gera número sequencial para nova proposta"""
        ano_atual = datetime.now().year
        
        # Busca último número do ano para o admin
        query = Proposta.query.filter(
            Proposta.numero_proposta.like(f'PROP-{ano_atual}-%')
        )
        
        if admin_id:
            query = query.filter(Proposta.admin_id == admin_id)
            
        ultima_proposta = query.order_by(Proposta.id.desc()).first()
        
        if ultima_proposta:
            # Extrai o número sequencial
            partes = ultima_proposta.numero_proposta.split('-')
            proximo_numero = int(partes[2]) + 1
        else:
            proximo_numero = 1
            
        return f'PROP-{ano_atual}-{proximo_numero:03d}'
    
    def calcular_valores_proposta(self, itens_dados):
        """
        Calcula valores totais da proposta baseado nos itens
        
        Args:
            itens_dados: Lista de dicts com servico_id, quantidade, preco_unitario
            
        Returns:
            dict com valor_total, itens_processados
        """
        valor_total = Decimal('0.00')
        itens_processados = []
        
        for item_data in itens_dados:
            servico = Servico.query.get(item_data['servico_id'])
            if not servico:
                continue
                
            quantidade = Decimal(str(item_data['quantidade']))
            preco_unitario = Decimal(str(item_data.get('preco_unitario', servico.preco_unitario)))
            valor_item = quantidade * preco_unitario
            
            item_processado = {
                'servico_id': servico.id,
                'servico_nome': servico.nome,
                'unidade': servico.unidade_medida,
                'quantidade': quantidade,
                'preco_unitario': preco_unitario,
                'valor_total': valor_item,
                'especificacoes': item_data.get('especificacoes', ''),
                'observacoes': item_data.get('observacoes', '')
            }
            
            itens_processados.append(item_processado)
            valor_total += valor_item
        
        return {
            'valor_total': float(valor_total),
            'itens_processados': itens_processados
        }
    
    def criar_proposta(self, dados_proposta, itens_dados, admin_id=None):
        """
        Cria nova proposta com itens
        
        Args:
            dados_proposta: Dict com dados básicos da proposta
            itens_dados: Lista de itens de serviço
            admin_id: ID do admin para multi-tenant
            
        Returns:
            Proposta criada ou None se erro
        """
        try:
            # Calcula valores
            calculo = self.calcular_valores_proposta(itens_dados)
            
            # Data de validade
            data_validade = datetime.now().date() + timedelta(days=self.prazo_validade_dias)
            if dados_proposta.get('data_validade'):
                data_validade = datetime.strptime(dados_proposta['data_validade'], '%Y-%m-%d').date()
            
            # Cria proposta
            proposta = Proposta(
                numero_proposta=self.gerar_numero_proposta(admin_id),
                cliente_nome=dados_proposta['cliente_nome'],
                cliente_documento=dados_proposta.get('cliente_documento', ''),
                cliente_endereco=dados_proposta.get('cliente_endereco', ''),
                cliente_telefone=dados_proposta.get('cliente_telefone', ''),
                cliente_email=dados_proposta.get('cliente_email', ''),
                titulo_projeto=dados_proposta['titulo_projeto'],
                descricao_projeto=dados_proposta.get('descricao_projeto', ''),
                local_execucao=dados_proposta['local_execucao'],
                area_total_m2=float(dados_proposta.get('area_total_m2', 0)),
                peso_total_kg=float(dados_proposta.get('peso_total_kg', 0)),
                valor_total=calculo['valor_total'],
                desconto_percentual=float(dados_proposta.get('desconto_percentual', 0)),
                margem_lucro_percentual=float(dados_proposta.get('margem_lucro_percentual', self.margem_lucro_padrao)),
                prazo_execucao_dias=int(dados_proposta.get('prazo_execucao_dias', 30)),
                data_validade=data_validade,
                observacoes=dados_proposta.get('observacoes', ''),
                condicoes_pagamento=dados_proposta.get('condicoes_pagamento', ''),
                garantias=dados_proposta.get('garantias', ''),
                responsavel_comercial_id=dados_proposta.get('responsavel_comercial_id'),
                admin_id=admin_id,
                status=StatusProposta.RASCUNHO
            )
            
            # Aplica desconto se informado
            if proposta.desconto_percentual > 0:
                proposta.valor_com_desconto = proposta.valor_total * (1 - proposta.desconto_percentual / 100)
            else:
                proposta.valor_com_desconto = proposta.valor_total
            
            db.session.add(proposta)
            db.session.flush()  # Para obter o ID
            
            # Cria itens
            ordem = 1
            for item_data in calculo['itens_processados']:
                item = ItemProposta(
                    proposta_id=proposta.id,
                    servico_id=item_data['servico_id'],
                    quantidade=item_data['quantidade'],
                    unidade=item_data['unidade'],
                    preco_unitario=item_data['preco_unitario'],
                    valor_total=item_data['valor_total'],
                    especificacoes=item_data['especificacoes'],
                    observacoes=item_data['observacoes'],
                    ordem=ordem
                )
                db.session.add(item)
                ordem += 1
            
            db.session.commit()
            
            # Registra histórico
            self.registrar_mudanca_status(proposta.id, None, StatusProposta.RASCUNHO, 
                                        "Proposta criada")
            
            return proposta
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar proposta: {str(e)}")
            return None
    
    def alterar_status_proposta(self, proposta_id, novo_status, motivo="", usuario_id=None):
        """
        Altera status da proposta e registra histórico
        
        Args:
            proposta_id: ID da proposta
            novo_status: Novo status (StatusProposta)
            motivo: Motivo da alteração
            usuario_id: ID do usuário que fez a alteração
        """
        proposta = Proposta.query.get(proposta_id)
        if not proposta:
            return False
        
        status_anterior = proposta.status
        proposta.status = novo_status
        
        if novo_status == StatusProposta.APROVADA:
            proposta.data_aprovacao = datetime.utcnow()
        
        db.session.commit()
        
        # Registra histórico
        self.registrar_mudanca_status(proposta_id, status_anterior, novo_status, motivo, usuario_id)
        
        return True
    
    def registrar_mudanca_status(self, proposta_id, status_anterior, status_novo, motivo="", usuario_id=None):
        """Registra mudança de status no histórico"""
        if not usuario_id and current_user.is_authenticated:
            usuario_id = current_user.id
        
        historico = HistoricoStatusProposta(
            proposta_id=proposta_id,
            status_anterior=status_anterior,
            status_novo=status_novo,
            usuario_id=usuario_id,
            motivo=motivo
        )
        
        db.session.add(historico)
        db.session.commit()
    
    def converter_proposta_para_obra(self, proposta_id):
        """
        Converte proposta aprovada em obra
        
        Args:
            proposta_id: ID da proposta aprovada
            
        Returns:
            Obra criada ou None se erro
        """
        proposta = Proposta.query.get(proposta_id)
        if not proposta or proposta.status != StatusProposta.APROVADA:
            return None
        
        if proposta.obra_gerada_id:
            # Já foi convertida
            return Obra.query.get(proposta.obra_gerada_id)
        
        try:
            # Cria obra
            obra = Obra(
                nome=f"{proposta.titulo_projeto} - {proposta.cliente_nome}",
                codigo=f"OB-{proposta.numero_proposta}",
                endereco=proposta.local_execucao,
                data_inicio=datetime.now().date(),
                data_previsao_fim=datetime.now().date() + timedelta(days=proposta.prazo_execucao_dias),
                orcamento=proposta.valor_com_desconto or proposta.valor_total,
                valor_contrato=proposta.valor_com_desconto or proposta.valor_total,
                area_total_m2=proposta.area_total_m2,
                status='Em andamento',
                responsavel_id=proposta.responsavel_comercial_id,
                admin_id=proposta.admin_id
            )
            
            db.session.add(obra)
            db.session.flush()  # Para obter o ID
            
            # Vincula proposta à obra
            proposta.obra_gerada_id = obra.id
            
            # Cria ServicoObra para cada item da proposta
            for item in proposta.itens:
                servico_obra = ServicoObra(
                    obra_id=obra.id,
                    servico_id=item.servico_id,
                    quantidade_planejada=item.quantidade,
                    observacoes=f"Importado da proposta {proposta.numero_proposta}"
                )
                db.session.add(servico_obra)
            
            db.session.commit()
            
            # Registra no histórico
            self.registrar_mudanca_status(proposta_id, StatusProposta.APROVADA, StatusProposta.APROVADA,
                                        f"Convertida para obra {obra.codigo}")
            
            return obra
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao converter proposta para obra: {str(e)}")
            return None
    
    def gerar_pdf_proposta(self, proposta_id):
        """
        Gera PDF profissional da proposta
        
        Args:
            proposta_id: ID da proposta
            
        Returns:
            Caminho do arquivo PDF gerado
        """
        proposta = Proposta.query.get(proposta_id)
        if not proposta:
            return None
        
        # Cria arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Configuração do documento
            doc = SimpleDocTemplate(
                temp_path,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            # Estilos
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.darkblue
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.darkblue
            )
            
            normal_style = styles['Normal']
            normal_style.fontSize = 10
            
            # Conteúdo do PDF
            story = []
            
            # Cabeçalho
            story.append(Paragraph("PROPOSTA COMERCIAL", title_style))
            story.append(Paragraph(f"Nº {proposta.numero_proposta}", styles['Heading3']))
            story.append(Spacer(1, 20))
            
            # Dados da empresa (você pode personalizar)
            empresa_data = [
                ['ESTRUTURAS DO VALE LTDA'],
                ['CNPJ: 00.000.000/0001-00'],
                ['Endereço: Sua cidade, Estado'],
                ['Telefone: (00) 0000-0000'],
                ['Email: contato@estruturasdovale.com.br']
            ]
            
            empresa_table = Table(empresa_data, colWidths=[10*cm])
            empresa_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            story.append(empresa_table)
            story.append(Spacer(1, 20))
            
            # Dados do cliente
            story.append(Paragraph("DADOS DO CLIENTE", heading_style))
            cliente_data = [
                ['Cliente:', proposta.cliente_nome],
                ['Documento:', proposta.cliente_documento or 'Não informado'],
                ['Telefone:', proposta.cliente_telefone or 'Não informado'],
                ['Email:', proposta.cliente_email or 'Não informado'],
                ['Endereço:', proposta.cliente_endereco or 'Não informado']
            ]
            
            cliente_table = Table(cliente_data, colWidths=[3*cm, 10*cm])
            cliente_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(cliente_table)
            story.append(Spacer(1, 20))
            
            # Dados do projeto
            story.append(Paragraph("DADOS DO PROJETO", heading_style))
            projeto_data = [
                ['Título:', proposta.titulo_projeto],
                ['Local de Execução:', proposta.local_execucao],
                ['Área Total:', f"{proposta.area_total_m2} m²" if proposta.area_total_m2 else 'Não informado'],
                ['Peso Total:', f"{proposta.peso_total_kg} kg" if proposta.peso_total_kg else 'Não informado'],
                ['Prazo de Execução:', f"{proposta.prazo_execucao_dias} dias"],
                ['Validade da Proposta:', proposta.data_validade.strftime('%d/%m/%Y')]
            ]
            
            projeto_table = Table(projeto_data, colWidths=[3*cm, 10*cm])
            projeto_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(projeto_table)
            story.append(Spacer(1, 20))
            
            # Descrição do projeto
            if proposta.descricao_projeto:
                story.append(Paragraph("DESCRIÇÃO DO PROJETO", heading_style))
                story.append(Paragraph(proposta.descricao_projeto, normal_style))
                story.append(Spacer(1, 20))
            
            # Escopo de serviços
            story.append(Paragraph("ESCOPO DE SERVIÇOS", heading_style))
            
            # Cabeçalho da tabela
            servicos_data = [['Item', 'Descrição', 'Qtd', 'Unid.', 'Valor Unit.', 'Valor Total']]
            
            total_geral = 0
            for i, item in enumerate(proposta.itens, 1):
                servicos_data.append([
                    str(i),
                    item.servico.nome,
                    f"{item.quantidade:.2f}",
                    item.unidade,
                    f"R$ {item.preco_unitario:.2f}",
                    f"R$ {item.valor_total:.2f}"
                ])
                total_geral += float(item.valor_total)
            
            # Linha de total
            servicos_data.append(['', '', '', '', 'TOTAL:', f"R$ {total_geral:.2f}"])
            
            servicos_table = Table(servicos_data, colWidths=[1*cm, 6*cm, 1.5*cm, 1*cm, 2*cm, 2.5*cm])
            servicos_table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Dados
                ('FONTSIZE', (0, 1), (-1, -2), 9),
                ('ALIGN', (0, 1), (0, -2), 'CENTER'),  # Item
                ('ALIGN', (2, 1), (2, -2), 'CENTER'),  # Quantidade
                ('ALIGN', (3, 1), (3, -2), 'CENTER'),  # Unidade
                ('ALIGN', (4, 1), (-1, -2), 'RIGHT'),  # Valores
                
                # Total
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (4, -1), (-1, -1), 'RIGHT'),
                
                # Bordas
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(servicos_table)
            story.append(Spacer(1, 20))
            
            # Resumo financeiro
            story.append(Paragraph("RESUMO FINANCEIRO", heading_style))
            
            valor_final = proposta.valor_com_desconto if proposta.desconto_percentual > 0 else proposta.valor_total
            
            financeiro_data = [
                ['Valor Total dos Serviços:', f"R$ {proposta.valor_total:.2f}"]
            ]
            
            if proposta.desconto_percentual > 0:
                financeiro_data.extend([
                    ['Desconto:', f"{proposta.desconto_percentual:.1f}%"],
                    ['Valor com Desconto:', f"R$ {valor_final:.2f}"]
                ])
            
            financeiro_data.append(['VALOR FINAL DA PROPOSTA:', f"R$ {valor_final:.2f}"])
            
            financeiro_table = Table(financeiro_data, colWidths=[8*cm, 5*cm])
            financeiro_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -2), 11),
                ('FONTSIZE', (0, -1), (-1, -1), 14),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(financeiro_table)
            story.append(Spacer(1, 20))
            
            # Condições de pagamento
            if proposta.condicoes_pagamento:
                story.append(Paragraph("CONDIÇÕES DE PAGAMENTO", heading_style))
                story.append(Paragraph(proposta.condicoes_pagamento, normal_style))
                story.append(Spacer(1, 15))
            
            # Garantias
            if proposta.garantias:
                story.append(Paragraph("GARANTIAS", heading_style))
                story.append(Paragraph(proposta.garantias, normal_style))
                story.append(Spacer(1, 15))
            
            # Observações
            if proposta.observacoes:
                story.append(Paragraph("OBSERVAÇÕES", heading_style))
                story.append(Paragraph(proposta.observacoes, normal_style))
                story.append(Spacer(1, 15))
            
            # Rodapé
            story.append(Spacer(1, 30))
            story.append(Paragraph("Esta proposta é válida até " + proposta.data_validade.strftime('%d/%m/%Y'), 
                                  normal_style))
            story.append(Spacer(1, 10))
            story.append(Paragraph("Atenciosamente,", normal_style))
            story.append(Spacer(1, 30))
            story.append(Paragraph("ESTRUTURAS DO VALE LTDA", styles['Heading3']))
            
            # Gera o PDF
            doc.build(story)
            
            return temp_path
            
        except Exception as e:
            print(f"Erro ao gerar PDF da proposta: {str(e)}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
    
    def listar_propostas(self, admin_id=None, status=None, limite=50):
        """
        Lista propostas com filtros
        
        Args:
            admin_id: ID do admin para multi-tenant
            status: Status específico
            limite: Limite de registros
            
        Returns:
            Query de propostas filtradas
        """
        query = Proposta.query
        
        if admin_id:
            query = query.filter(Proposta.admin_id == admin_id)
        
        if status:
            query = query.filter(Proposta.status == status)
        
        return query.order_by(Proposta.created_at.desc()).limit(limite)
    
    def estatisticas_propostas(self, admin_id=None):
        """
        Calcula estatísticas das propostas
        
        Args:
            admin_id: ID do admin para multi-tenant
            
        Returns:
            Dict com estatísticas
        """
        query = Proposta.query
        if admin_id:
            query = query.filter(Proposta.admin_id == admin_id)
        
        total = query.count()
        aprovadas = query.filter(Proposta.status == StatusProposta.APROVADA).count()
        rejeitadas = query.filter(Proposta.status == StatusProposta.REJEITADA).count()
        em_analise = query.filter(Proposta.status == StatusProposta.EM_ANALISE).count()
        
        # Valor total das propostas
        valor_total = db.session.query(db.func.sum(Proposta.valor_total)).filter(
            Proposta.admin_id == admin_id if admin_id else True
        ).scalar() or 0
        
        # Valor das aprovadas
        valor_aprovadas = db.session.query(db.func.sum(Proposta.valor_com_desconto)).filter(
            Proposta.status == StatusProposta.APROVADA,
            Proposta.admin_id == admin_id if admin_id else True
        ).scalar() or 0
        
        # Taxa de conversão
        taxa_conversao = (aprovadas / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'aprovadas': aprovadas,
            'rejeitadas': rejeitadas,
            'em_analise': em_analise,
            'valor_total': valor_total,
            'valor_aprovadas': valor_aprovadas,
            'taxa_conversao': taxa_conversao
        }

# Instância global do engine
propostas_engine = PropostasEngine()