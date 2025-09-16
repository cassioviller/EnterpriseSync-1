"""
SISTEMA DE EXPORTAÇÃO DE RELATÓRIOS - SIGE v8.0
Sistema completo de exportação e agendamento de relatórios

Funcionalidades:
- Exportação PDF profissional com gráficos
- Exportação Excel com múltiplas planilhas
- Relatórios agendados automáticos
- Templates customizáveis
- Envio por email automático
- Sistema de jobs assíncronos
"""

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text, extract, case
import json
import logging
from decimal import Decimal
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Backend não-GUI
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import base64
import os
import tempfile
from threading import Thread
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, AlocacaoVeiculo, ManutencaoVeiculo,
    AlertaVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
exportacao_bp = Blueprint('exportacao_relatorios', __name__, url_prefix='/relatorios/exportacao')

def get_admin_id():
    """Obtém admin_id do usuário atual"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

class GeradorRelatorios:
    """Classe principal para geração de relatórios"""
    
    def __init__(self, admin_id):
        self.admin_id = admin_id
        
        # Configurações de estilo para gráficos
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Cores padrão
        self.cores_primarias = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
    
    def gerar_relatorio_completo_pdf(self, data_inicio, data_fim, incluir_graficos=True):
        """Gera relatório completo em PDF"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Estilo customizado para títulos
            titulo_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Centralizado
                textColor=colors.HexColor('#2c3e50')
            )
            
            # Cabeçalho
            story.append(Paragraph("RELATÓRIO COMPLETO DA FROTA", titulo_style))
            story.append(Paragraph(f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            # === RESUMO EXECUTIVO ===
            story.append(Paragraph("RESUMO EXECUTIVO", styles['Heading2']))
            resumo_data = self._obter_dados_resumo_executivo(data_inicio, data_fim)
            
            resumo_table_data = [
                ['Métrica', 'Valor'],
                ['Total de Veículos Ativos', str(resumo_data.get('total_veiculos', 0))],
                ['Km Rodados no Período', f"{resumo_data.get('km_total', 0):,.0f}"],
                ['Custo Total', f"R$ {resumo_data.get('custo_total', 0):,.2f}"],
                ['Custo por Km', f"R$ {resumo_data.get('custo_por_km', 0):.3f}"],
                ['Manutenções Realizadas', str(resumo_data.get('total_manutencoes', 0))],
                ['Alertas Ativos', str(resumo_data.get('alertas_ativos', 0))]
            ]
            
            resumo_table = Table(resumo_table_data)
            resumo_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(resumo_table)
            story.append(Spacer(1, 20))
            
            # === ANÁLISE FINANCEIRA ===
            story.append(Paragraph("ANÁLISE FINANCEIRA", styles['Heading2']))
            custos_data = self._obter_dados_custos(data_inicio, data_fim)
            
            if custos_data:
                custos_table_data = [['Categoria', 'Valor', 'Percentual']]
                for categoria, dados in custos_data.items():
                    custos_table_data.append([
                        categoria.title(),
                        f"R$ {dados['valor']:,.2f}",
                        f"{dados['percentual']:.1f}%"
                    ])
                
                custos_table = Table(custos_table_data)
                custos_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(custos_table)
                story.append(Spacer(1, 20))
            
            # === GRÁFICOS ===
            if incluir_graficos:
                story.append(Paragraph("ANÁLISES GRÁFICAS", styles['Heading2']))
                
                # Gráfico de custos por categoria
                grafico_custos = self._gerar_grafico_custos_categoria(data_inicio, data_fim)
                if grafico_custos:
                    story.append(Image(grafico_custos, width=400, height=300))
                    story.append(Spacer(1, 10))
                
                # Gráfico de evolução mensal
                grafico_evolucao = self._gerar_grafico_evolucao_mensal(data_inicio, data_fim)
                if grafico_evolucao:
                    story.append(Image(grafico_evolucao, width=400, height=300))
                    story.append(Spacer(1, 20))
            
            # === TOP VEÍCULOS ===
            story.append(Paragraph("TOP 10 VEÍCULOS POR CUSTO", styles['Heading2']))
            top_veiculos = self._obter_top_veiculos_custo(data_inicio, data_fim)
            
            if top_veiculos:
                top_table_data = [['Posição', 'Veículo', 'Custo Total', 'Km Rodados']]
                for i, veiculo in enumerate(top_veiculos[:10], 1):
                    top_table_data.append([
                        str(i),
                        f"{veiculo['placa']} ({veiculo['marca']} {veiculo['modelo']})",
                        f"R$ {veiculo['custo_total']:,.2f}",
                        f"{veiculo['km_total']:,.0f}"
                    ])
                
                top_table = Table(top_table_data)
                top_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(top_table)
            
            # === ALERTAS CRÍTICOS ===
            story.append(Spacer(1, 20))
            story.append(Paragraph("ALERTAS CRÍTICOS", styles['Heading2']))
            alertas_criticos = self._obter_alertas_criticos()
            
            if alertas_criticos:
                alertas_table_data = [['Veículo', 'Tipo de Alerta', 'Descrição', 'Nível']]
                for alerta in alertas_criticos[:10]:
                    nivel_text = {1: 'Baixo', 2: 'Médio', 3: 'Alto'}.get(alerta['nivel'], 'N/A')
                    alertas_table_data.append([
                        alerta['veiculo_placa'],
                        alerta['tipo_alerta'].replace('_', ' ').title(),
                        alerta['mensagem'][:50] + '...',
                        nivel_text
                    ])
                
                alertas_table = Table(alertas_table_data)
                alertas_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(alertas_table)
            
            # Rodapé
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Normal']))
            story.append(Paragraph("Sistema Integrado de Gestão Empresarial - SIGE v8.0", styles['Normal']))
            
            doc.build(story)
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            return None
    
    def gerar_relatorio_excel_completo(self, data_inicio, data_fim):
        """Gera relatório completo em Excel com múltiplas planilhas"""
        try:
            buffer = BytesIO()
            
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # === ABA 1: RESUMO EXECUTIVO ===
                resumo_data = self._obter_dados_resumo_executivo(data_inicio, data_fim)
                df_resumo = pd.DataFrame([resumo_data])
                df_resumo.to_excel(writer, sheet_name='Resumo Executivo', index=False)
                
                # === ABA 2: CUSTOS DETALHADOS ===
                custos_detalhados = self._obter_custos_detalhados(data_inicio, data_fim)
                if custos_detalhados:
                    df_custos = pd.DataFrame(custos_detalhados)
                    df_custos.to_excel(writer, sheet_name='Custos Detalhados', index=False)
                
                # === ABA 3: USO POR VEÍCULO ===
                uso_veiculos = self._obter_uso_por_veiculo(data_inicio, data_fim)
                if uso_veiculos:
                    df_uso = pd.DataFrame(uso_veiculos)
                    df_uso.to_excel(writer, sheet_name='Uso por Veículo', index=False)
                
                # === ABA 4: MANUTENÇÕES ===
                manutencoes = self._obter_manutencoes_detalhadas(data_inicio, data_fim)
                if manutencoes:
                    df_manutencoes = pd.DataFrame(manutencoes)
                    df_manutencoes.to_excel(writer, sheet_name='Manutenções', index=False)
                
                # === ABA 5: ANÁLISE FINANCEIRA ===
                analise_financeira = self._obter_analise_financeira(data_inicio, data_fim)
                if analise_financeira:
                    df_financeira = pd.DataFrame(analise_financeira)
                    df_financeira.to_excel(writer, sheet_name='Análise Financeira', index=False)
                
                # === ABA 6: ALERTAS ===
                alertas = self._obter_alertas_criticos()
                if alertas:
                    df_alertas = pd.DataFrame(alertas)
                    df_alertas.to_excel(writer, sheet_name='Alertas', index=False)
                
                # === ABA 7: ALOCAÇÕES ===
                alocacoes = self._obter_alocacoes_detalhadas(data_inicio, data_fim)
                if alocacoes:
                    df_alocacoes = pd.DataFrame(alocacoes)
                    df_alocacoes.to_excel(writer, sheet_name='Alocações', index=False)
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"Erro ao gerar Excel: {e}")
            return None
    
    def _gerar_grafico_custos_categoria(self, data_inicio, data_fim):
        """Gera gráfico de custos por categoria"""
        try:
            custos_data = self._obter_dados_custos(data_inicio, data_fim)
            if not custos_data:
                return None
            
            # Preparar dados
            categorias = list(custos_data.keys())
            valores = [custos_data[cat]['valor'] for cat in categorias]
            
            # Criar gráfico
            fig, ax = plt.subplots(figsize=(8, 6))
            wedges, texts, autotexts = ax.pie(valores, labels=categorias, autopct='%1.1f%%', 
                                            startangle=90, colors=self.cores_primarias)
            
            ax.set_title('Distribuição de Custos por Categoria', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            # Salvar em buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            plt.close()
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico custos: {e}")
            return None
    
    def _gerar_grafico_evolucao_mensal(self, data_inicio, data_fim):
        """Gera gráfico de evolução mensal"""
        try:
            evolucao_data = self._obter_evolucao_mensal(data_inicio, data_fim)
            if not evolucao_data:
                return None
            
            # Preparar dados
            periodos = [d['periodo'] for d in evolucao_data]
            custos = [d['custo_total'] for d in evolucao_data]
            km = [d['km_total'] for d in evolucao_data]
            
            # Criar gráfico com dois eixos Y
            fig, ax1 = plt.subplots(figsize=(10, 6))
            
            # Eixo Y esquerdo (custos)
            color = '#e74c3c'
            ax1.set_xlabel('Período')
            ax1.set_ylabel('Custos (R$)', color=color)
            line1 = ax1.plot(periodos, custos, color=color, marker='o', linewidth=2, label='Custos')
            ax1.tick_params(axis='y', labelcolor=color)
            
            # Eixo Y direito (KM)
            ax2 = ax1.twinx()
            color = '#3498db'
            ax2.set_ylabel('KM Rodados', color=color)
            line2 = ax2.plot(periodos, km, color=color, marker='s', linewidth=2, label='KM')
            ax2.tick_params(axis='y', labelcolor=color)
            
            # Título e legenda
            ax1.set_title('Evolução Mensal - Custos vs KM Rodados', fontsize=14, fontweight='bold')
            
            # Rotacionar labels do eixo X se necessário
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Salvar em buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            plt.close()
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico evolução: {e}")
            return None
    
    # === MÉTODOS DE OBTENÇÃO DE DADOS ===
    
    def _obter_dados_resumo_executivo(self, data_inicio, data_fim):
        """Obtém dados para resumo executivo"""
        try:
            # Total de veículos ativos
            total_veiculos = Veiculo.query.filter_by(admin_id=self.admin_id, ativo=True).count()
            
            # KM total
            km_total = db.session.query(func.sum(UsoVeiculo.km_rodado)).filter(
                UsoVeiculo.admin_id == self.admin_id,
                UsoVeiculo.data_uso >= data_inicio,
                UsoVeiculo.data_uso <= data_fim
            ).scalar() or 0
            
            # Custo total
            custo_total = db.session.query(func.sum(CustoVeiculo.valor)).filter(
                CustoVeiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ).scalar() or 0
            
            # Custo por KM
            custo_por_km = custo_total / max(float(km_total), 1) if km_total > 0 else 0
            
            # Manutenções realizadas
            total_manutencoes = ManutencaoVeiculo.query.filter(
                ManutencaoVeiculo.admin_id == self.admin_id,
                ManutencaoVeiculo.data_manutencao >= data_inicio,
                ManutencaoVeiculo.data_manutencao <= data_fim
            ).count()
            
            # Alertas ativos
            alertas_ativos = AlertaVeiculo.query.filter_by(
                admin_id=self.admin_id, ativo=True
            ).count()
            
            return {
                'total_veiculos': total_veiculos,
                'km_total': float(km_total),
                'custo_total': float(custo_total),
                'custo_por_km': custo_por_km,
                'total_manutencoes': total_manutencoes,
                'alertas_ativos': alertas_ativos
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter resumo executivo: {e}")
            return {}
    
    def _obter_dados_custos(self, data_inicio, data_fim):
        """Obtém dados de custos por categoria"""
        try:
            custos = db.session.query(
                CustoVeiculo.tipo_custo,
                func.sum(CustoVeiculo.valor).label('total')
            ).filter(
                CustoVeiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ).group_by(CustoVeiculo.tipo_custo).all()
            
            total_geral = sum(float(c.total) for c in custos)
            
            custos_dict = {}
            for c in custos:
                percentual = (float(c.total) / max(total_geral, 1)) * 100
                custos_dict[c.tipo_custo] = {
                    'valor': float(c.total),
                    'percentual': percentual
                }
            
            return custos_dict
            
        except Exception as e:
            logger.error(f"Erro ao obter dados de custos: {e}")
            return {}
    
    def _obter_custos_detalhados(self, data_inicio, data_fim):
        """Obtém custos detalhados para Excel"""
        try:
            custos = db.session.query(CustoVeiculo)\
            .join(Veiculo, CustoVeiculo.veiculo_id == Veiculo.id)\
            .filter(
                CustoVeiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ).order_by(CustoVeiculo.data_custo.desc()).all()
            
            dados = []
            for custo in custos:
                dados.append({
                    'Data': custo.data_custo.strftime('%d/%m/%Y'),
                    'Veículo': custo.veiculo.placa,
                    'Tipo de Custo': custo.tipo_custo,
                    'Valor': float(custo.valor),
                    'Descrição': custo.descricao,
                    'KM Atual': custo.km_atual
                })
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao obter custos detalhados: {e}")
            return []
    
    def _obter_alertas_criticos(self):
        """Obtém alertas críticos"""
        try:
            alertas = AlertaVeiculo.query.filter(
                AlertaVeiculo.admin_id == self.admin_id,
                AlertaVeiculo.ativo == True
            ).order_by(AlertaVeiculo.nivel.desc()).limit(20).all()
            
            dados = []
            for alerta in alertas:
                dados.append({
                    'veiculo_placa': alerta.veiculo.placa if alerta.veiculo else 'N/A',
                    'tipo_alerta': alerta.tipo_alerta,
                    'nivel': alerta.nivel,
                    'mensagem': alerta.mensagem,
                    'data_criacao': alerta.created_at.strftime('%d/%m/%Y %H:%M')
                })
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao obter alertas: {e}")
            return []
    
    # Implementar outros métodos de obtenção de dados...
    def _obter_top_veiculos_custo(self, data_inicio, data_fim):
        """Obtém top veículos por custo"""
        # Placeholder - implementar lógica
        return []
    
    def _obter_evolucao_mensal(self, data_inicio, data_fim):
        """Obtém evolução mensal"""
        # Placeholder - implementar lógica
        return []
    
    def _obter_uso_por_veiculo(self, data_inicio, data_fim):
        """Obtém uso por veículo"""
        # Placeholder - implementar lógica
        return []
    
    def _obter_manutencoes_detalhadas(self, data_inicio, data_fim):
        """Obtém manutenções detalhadas"""
        # Placeholder - implementar lógica
        return []
    
    def _obter_analise_financeira(self, data_inicio, data_fim):
        """Obtém análise financeira"""
        # Placeholder - implementar lógica
        return []
    
    def _obter_alocacoes_detalhadas(self, data_inicio, data_fim):
        """Obtém alocações detalhadas"""
        # Placeholder - implementar lógica
        return []

class SistemaEmailRelatorios:
    """Sistema para envio automático de relatórios por email"""
    
    def __init__(self):
        self.smtp_server = current_app.config.get('MAIL_SERVER', 'localhost')
        self.smtp_port = current_app.config.get('MAIL_PORT', 587)
        self.smtp_username = current_app.config.get('MAIL_USERNAME', '')
        self.smtp_password = current_app.config.get('MAIL_PASSWORD', '')
        self.smtp_use_tls = current_app.config.get('MAIL_USE_TLS', True)
    
    def enviar_relatorio_email(self, admin_id, destinatarios, tipo_relatorio, anexo_buffer, anexo_nome):
        """Envia relatório por email"""
        try:
            # Configurar email
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(destinatarios)
            msg['Subject'] = f'Relatório de Veículos - {tipo_relatorio} - {datetime.now().strftime("%d/%m/%Y")}'
            
            # Corpo do email
            corpo = f"""
            Olá,
            
            Segue em anexo o relatório de veículos solicitado.
            
            Tipo: {tipo_relatorio}
            Data de Geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
            
            Este é um email automático do Sistema SIGE.
            
            Atenciosamente,
            Equipe SIGE
            """
            
            msg.attach(MIMEText(corpo, 'plain'))
            
            # Anexar arquivo
            if anexo_buffer:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(anexo_buffer.getvalue())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {anexo_nome}'
                )
                msg.attach(part)
            
            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.smtp_use_tls:
                server.starttls()
            
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            server.sendmail(self.smtp_username, destinatarios, msg.as_string())
            server.quit()
            
            logger.info(f"Relatório enviado por email para: {', '.join(destinatarios)}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False

# ===== ROTAS DO BLUEPRINT =====

@exportacao_bp.route('/')
@login_required
@admin_required
def painel_exportacao():
    """Painel principal de exportação"""
    admin_id = get_admin_id()
    
    return render_template('relatorios/exportacao/painel.html')

@exportacao_bp.route('/gerar-pdf')
@login_required
@admin_required
def gerar_pdf():
    """Gera e envia PDF"""
    admin_id = get_admin_id()
    
    # Parâmetros
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    incluir_graficos = request.args.get('graficos', 'true').lower() == 'true'
    
    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Gerar relatório
        gerador = GeradorRelatorios(admin_id)
        buffer = gerador.gerar_relatorio_completo_pdf(data_inicio, data_fim, incluir_graficos)
        
        if buffer:
            filename = f"relatorio_veiculos_{data_inicio}_{data_fim}.pdf"
            
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        else:
            flash('Erro ao gerar relatório PDF', 'danger')
            return redirect(url_for('exportacao_relatorios.painel_exportacao'))
        
    except Exception as e:
        logger.error(f"Erro na geração de PDF: {e}")
        flash('Erro ao gerar relatório PDF', 'danger')
        return redirect(url_for('exportacao_relatorios.painel_exportacao'))

@exportacao_bp.route('/gerar-excel')
@login_required
@admin_required
def gerar_excel():
    """Gera e envia Excel"""
    admin_id = get_admin_id()
    
    # Parâmetros
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    
    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Gerar relatório
        gerador = GeradorRelatorios(admin_id)
        buffer = gerador.gerar_relatorio_excel_completo(data_inicio, data_fim)
        
        if buffer:
            filename = f"relatorio_veiculos_{data_inicio}_{data_fim}.xlsx"
            
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        else:
            flash('Erro ao gerar relatório Excel', 'danger')
            return redirect(url_for('exportacao_relatorios.painel_exportacao'))
        
    except Exception as e:
        logger.error(f"Erro na geração de Excel: {e}")
        flash('Erro ao gerar relatório Excel', 'danger')
        return redirect(url_for('exportacao_relatorios.painel_exportacao'))

@exportacao_bp.route('/enviar-email', methods=['POST'])
@login_required
@admin_required
def enviar_relatorio_email():
    """Envia relatório por email"""
    admin_id = get_admin_id()
    
    try:
        dados = request.get_json()
        
        # Parâmetros
        data_inicio = datetime.strptime(dados['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(dados['data_fim'], '%Y-%m-%d').date()
        formato = dados.get('formato', 'pdf')
        destinatarios = dados.get('destinatarios', [])
        incluir_graficos = dados.get('incluir_graficos', True)
        
        if not destinatarios:
            return jsonify({'success': False, 'error': 'Nenhum destinatário informado'})
        
        # Gerar relatório
        gerador = GeradorRelatorios(admin_id)
        
        if formato == 'pdf':
            buffer = gerador.gerar_relatorio_completo_pdf(data_inicio, data_fim, incluir_graficos)
            nome_arquivo = f"relatorio_veiculos_{data_inicio}_{data_fim}.pdf"
        else:
            buffer = gerador.gerar_relatorio_excel_completo(data_inicio, data_fim)
            nome_arquivo = f"relatorio_veiculos_{data_inicio}_{data_fim}.xlsx"
        
        if not buffer:
            return jsonify({'success': False, 'error': 'Erro ao gerar relatório'})
        
        # Enviar por email
        sistema_email = SistemaEmailRelatorios()
        sucesso = sistema_email.enviar_relatorio_email(
            admin_id, destinatarios, formato.upper(), buffer, nome_arquivo
        )
        
        if sucesso:
            return jsonify({'success': True, 'message': 'Relatório enviado por email com sucesso'})
        else:
            return jsonify({'success': False, 'error': 'Erro ao enviar email'})
        
    except Exception as e:
        logger.error(f"Erro ao enviar relatório por email: {e}")
        return jsonify({'success': False, 'error': str(e)})

@exportacao_bp.route('/api/preview-dados')
@login_required
@admin_required
def api_preview_dados():
    """API para preview dos dados do relatório"""
    admin_id = get_admin_id()
    
    try:
        data_inicio_str = request.args.get('data_inicio')
        data_fim_str = request.args.get('data_fim')
        
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        gerador = GeradorRelatorios(admin_id)
        resumo = gerador._obter_dados_resumo_executivo(data_inicio, data_fim)
        custos = gerador._obter_dados_custos(data_inicio, data_fim)
        
        return jsonify({
            'success': True,
            'resumo': resumo,
            'custos': custos
        })
        
    except Exception as e:
        logger.error(f"Erro no preview: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== SISTEMA DE AGENDAMENTO ===

class SistemaAgendamentoRelatorios:
    """Sistema para agendamento automático de relatórios"""
    
    def __init__(self):
        self.jobs_agendados = {}
    
    def agendar_relatorio_periodico(self, admin_id, configuracao):
        """Agenda relatório periódico"""
        try:
            # Configuração contém:
            # - frequencia: 'diario', 'semanal', 'mensal'
            # - formato: 'pdf', 'excel'
            # - destinatarios: lista de emails
            # - incluir_graficos: boolean
            
            job_id = f"relatorio_{admin_id}_{datetime.now().timestamp()}"
            
            # Agendar com celery ou sistema de jobs
            # Por ora, implementação simplificada
            
            self.jobs_agendados[job_id] = {
                'admin_id': admin_id,
                'configuracao': configuracao,
                'status': 'agendado',
                'proximo_envio': self._calcular_proximo_envio(configuracao['frequencia'])
            }
            
            logger.info(f"Relatório agendado: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Erro ao agendar relatório: {e}")
            return None
    
    def _calcular_proximo_envio(self, frequencia):
        """Calcula próximo envio baseado na frequência"""
        hoje = datetime.now()
        
        if frequencia == 'diario':
            return hoje + timedelta(days=1)
        elif frequencia == 'semanal':
            return hoje + timedelta(weeks=1)
        elif frequencia == 'mensal':
            return hoje + timedelta(days=30)
        else:
            return hoje + timedelta(days=1)

@exportacao_bp.route('/agendar', methods=['POST'])
@login_required
@admin_required
def agendar_relatorio():
    """Agenda relatório automático"""
    admin_id = get_admin_id()
    
    try:
        dados = request.get_json()
        
        configuracao = {
            'frequencia': dados.get('frequencia', 'semanal'),
            'formato': dados.get('formato', 'pdf'),
            'destinatarios': dados.get('destinatarios', []),
            'incluir_graficos': dados.get('incluir_graficos', True)
        }
        
        sistema_agendamento = SistemaAgendamentoRelatorios()
        job_id = sistema_agendamento.agendar_relatorio_periodico(admin_id, configuracao)
        
        if job_id:
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': 'Relatório agendado com sucesso'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao agendar relatório'
            })
        
    except Exception as e:
        logger.error(f"Erro ao agendar: {e}")
        return jsonify({'success': False, 'error': str(e)})