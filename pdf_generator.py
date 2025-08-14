"""
Gerador de PDF para relatórios do SIGE
Funcionalidade: Exportar perfil de funcionário com KPIs e controle de ponto
"""

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.platypus.flowables import PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime
import locale

# Configurar locale para formato brasileiro
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        pass  # Fallback para inglês se não conseguir configurar

class FuncionarioPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Configurar estilos personalizados para o PDF"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.HexColor('#34495e'),
            borderWidth=1,
            borderColor=colors.HexColor('#bdc3c7'),
            borderPadding=8,
            backColor=colors.HexColor('#ecf0f1')
        ))
        
        self.styles.add(ParagraphStyle(
            name='KPIValue',
            parent=self.styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2980b9')
        ))

    def gerar_pdf_funcionario(self, funcionario, kpis, registros_ponto, data_inicio, data_fim):
        """
        Gerar PDF completo do perfil do funcionário
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Elementos do PDF
        story = []
        
        # Cabeçalho
        story.append(Paragraph("SIGE - Sistema Integrado de Gestão Empresarial", self.styles['CustomTitle']))
        story.append(Paragraph("Estruturas do Vale", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Título do relatório
        titulo = f"Relatório de Funcionário - {funcionario.nome}"
        story.append(Paragraph(titulo, self.styles['CustomTitle']))
        
        # Período do relatório
        periodo_texto = f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        story.append(Paragraph(periodo_texto, self.styles['Normal']))
        story.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", self.styles['Normal']))
        story.append(Spacer(1, 30))
        
        # Dados do funcionário
        story.append(Paragraph("DADOS DO FUNCIONÁRIO", self.styles['SectionHeader']))
        story.extend(self._criar_dados_funcionario(funcionario))
        story.append(Spacer(1, 20))
        
        # KPIs
        story.append(Paragraph("INDICADORES DE DESEMPENHO (KPIs)", self.styles['SectionHeader']))
        story.extend(self._criar_secao_kpis(kpis))
        story.append(Spacer(1, 20))
        
        # Controle de Ponto
        story.append(Paragraph("CONTROLE DE PONTO", self.styles['SectionHeader']))
        story.extend(self._criar_tabela_ponto(registros_ponto))
        
        # Rodapé
        story.append(Spacer(1, 30))
        story.append(Paragraph("Relatório gerado automaticamente pelo SIGE v8.0", 
                              ParagraphStyle('Footer', parent=self.styles['Normal'], 
                                           fontSize=8, alignment=TA_CENTER, 
                                           textColor=colors.grey)))
        
        # Construir PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

    def _criar_dados_funcionario(self, funcionario):
        """Criar seção com dados básicos do funcionário"""
        elementos = []
        
        data = [
            ['Nome Completo:', funcionario.nome],
            ['Função:', funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Não informado'],
            ['Salário:', f'R$ {funcionario.salario:,.2f}' if funcionario.salario else 'Não informado'],
            ['Data de Admissão:', funcionario.data_admissao.strftime('%d/%m/%Y') if funcionario.data_admissao else 'Não informado'],
            ['Status:', 'Ativo' if funcionario.ativo else 'Inativo'],
            ['Departamento:', funcionario.departamento_ref.nome if funcionario.departamento_ref else 'Não informado'],
            ['ID do Sistema:', str(funcionario.id)]
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ]))
        
        elementos.append(table)
        return elementos

    def _criar_secao_kpis(self, kpis):
        """Criar seção com KPIs do funcionário"""
        elementos = []
        
        # KPIs principais em formato de tabela
        kpi_data = [
            ['Indicador', 'Valor', 'Observações'],
            ['Horas Trabalhadas', f"{kpis.get('horas_trabalhadas', 0):.1f}h", 'Total do período'],
            ['Horas Extras', f"{kpis.get('horas_extras', 0):.1f}h", 'Acima da jornada normal'],
            ['Faltas', str(kpis.get('faltas', 0)), 'Ausências não justificadas'],
            ['Faltas Justificadas', str(kpis.get('faltas_justificadas', 0)), 'Ausências com justificativa'],
            ['Taxa de Eficiência', f"{kpis.get('taxa_eficiencia', 0):.1f}%", 'Produtividade geral'],
            ['Taxa de Absenteísmo', f"{kpis.get('absenteismo', 0):.1f}%", 'Percentual de faltas'],
            ['Dias Trabalhados', str(kpis.get('dias_trabalhados', 0)), 'Dias com presença'],
            ['Média Horas/Dia', f"{kpis.get('media_horas_dia', 0):.1f}h", 'Média diária de trabalho']
        ]
        
        kpi_table = Table(kpi_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elementos.append(kpi_table)
        elementos.append(Spacer(1, 15))
        
        # KPIs financeiros separados
        elementos.append(Paragraph("Indicadores Financeiros Detalhados:", self.styles['Heading3']))
        
        # Tabela principal com valores
        financeiro_data = [
            ['Item', 'Quantidade', 'Valor Unit.', 'Valor Total'],
            ['Horas Extras', f"{kpis.get('horas_extras', 0):.1f}h", f"R$ {kpis.get('valor_hora_atual', 0) * 1.5:,.2f}", f"R$ {kpis.get('valor_horas_extras', 0):,.2f}"],
            ['Faltas Injustificadas', f"{kpis.get('faltas', 0)} dias", f"R$ {kpis.get('valor_hora_atual', 0) * 8:,.2f}", f"R$ {kpis.get('valor_faltas', 0):,.2f}"],
            ['Faltas Justificadas', f"{kpis.get('faltas_justificadas', 0)} dias", f"R$ {kpis.get('valor_hora_atual', 0) * 8:,.2f}", f"R$ {kpis.get('valor_faltas_justificadas', 0):,.2f}"],
            ['DSR Perdido (Lei 605/49)', f"{kpis.get('dsr_perdido_dias', 0)} semana(s)", f"R$ {kpis.get('valor_hora_atual', 0) * 8:,.2f}", f"R$ {kpis.get('valor_dsr_perdido', 0):,.2f}"]
        ]
        
        financeiro_table = Table(financeiro_data, colWidths=[2.2*inch, 1.3*inch, 1.3*inch, 1.5*inch])
        financeiro_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            # Destacar valores negativos (descontos)
            ('BACKGROUND', (0, 2), (-1, 4), colors.HexColor('#ffe6e6')),  # Faltas e DSR em vermelho claro
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e6ffe6'))   # Horas extras em verde claro
        ]))
        
        elementos.append(financeiro_table)
        elementos.append(Spacer(1, 10))
        
        # Resumo financeiro
        elementos.append(Paragraph("Resumo Financeiro:", self.styles['Heading3']))
        
        resumo_data = [
            ['Custo Total Mão de Obra', f"R$ {kpis.get('custo_mao_obra', 0):,.2f}"],
            ['Valor Hora Atual', f"R$ {kpis.get('valor_hora_atual', 0):,.2f}"],
            ['Total Descontos (Faltas + DSR)', f"R$ {kpis.get('valor_faltas', 0) + kpis.get('valor_dsr_perdido', 0):,.2f}"],
            ['Custo Líquido do Período', f"R$ {kpis.get('custo_total_geral', 0) - kpis.get('valor_faltas', 0) - kpis.get('valor_dsr_perdido', 0):,.2f}"]
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3.5*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e8')),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#fff2e8')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda'))  # Linha final destacada
        ]))
        
        elementos.append(financeiro_table)
        return elementos

    def _criar_tabela_ponto(self, registros_ponto):
        """Criar tabela detalhada do controle de ponto"""
        elementos = []
        
        if not registros_ponto:
            elementos.append(Paragraph("Nenhum registro de ponto encontrado para o período.", self.styles['Normal']))
            return elementos
        
        # Cabeçalho da tabela
        headers = ['Data', 'Tipo', 'Entrada', 'Saída Almoço', 'Retorno', 'Saída', 'H. Trab.', 'H. Extras']
        
        # Dados da tabela
        data = [headers]
        
        for registro in registros_ponto:
            # Formatar tipo de registro
            tipo_map = {
                'trabalhado': 'Normal',
                'sabado_horas_extras': 'Sábado',
                'domingo_horas_extras': 'Domingo', 
                'feriado_trabalhado': 'Feriado Trab.',
                'falta': 'Falta',
                'falta_justificada': 'Falta Just.',
                'sabado_folga': 'Sáb. Folga',
                'domingo_folga': 'Dom. Folga'
            }
            tipo = tipo_map.get(registro.tipo_registro, registro.tipo_registro or 'N/A')
            
            # Formatar horários
            entrada = registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else '-'
            almoco_saida = registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else '-'
            almoco_retorno = registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else '-'
            saida = registro.hora_saida.strftime('%H:%M') if registro.hora_saida else '-'
            
            # Para faltas, mostrar texto ao invés de horários
            if registro.tipo_registro in ['falta', 'falta_justificada']:
                entrada = almoco_saida = almoco_retorno = saida = 'FALTA'
            
            row = [
                registro.data.strftime('%d/%m/%Y'),
                tipo,
                entrada,
                almoco_saida,
                almoco_retorno,
                saida,
                f"{registro.horas_trabalhadas:.1f}h" if registro.horas_trabalhadas else '-',
                f"{registro.horas_extras:.1f}h" if registro.horas_extras else '-'
            ]
            data.append(row)
        
        # Criar tabela
        table = Table(data, colWidths=[0.8*inch, 0.8*inch, 0.6*inch, 0.7*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch])
        table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Linhas alternadas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            
            # Destacar fins de semana e feriados
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        
        # Aplicar cores especiais baseadas no tipo
        for i, registro in enumerate(registros_ponto, 1):
            if registro.tipo_registro == 'sabado_horas_extras':
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#d5f4e6'))]))
            elif registro.tipo_registro == 'domingo_horas_extras':
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#dbeafe'))]))
            elif registro.tipo_registro == 'feriado_trabalhado':
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fef3cd'))]))
            elif registro.tipo_registro in ['falta', 'falta_justificada']:
                cor = colors.HexColor('#f8d7da') if registro.tipo_registro == 'falta' else colors.HexColor('#d1ecf1')
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), cor)]))
        
        elementos.append(table)
        
        # Resumo do período
        elementos.append(Spacer(1, 15))
        total_horas = sum(r.horas_trabalhadas or 0 for r in registros_ponto)
        total_extras = sum(r.horas_extras or 0 for r in registros_ponto)
        total_faltas = len([r for r in registros_ponto if r.tipo_registro == 'falta'])
        
        resumo_texto = f"""
        <b>Resumo do Período:</b><br/>
        • Total de registros: {len(registros_ponto)}<br/>
        • Horas trabalhadas: {total_horas:.1f}h<br/>
        • Horas extras: {total_extras:.1f}h<br/>
        • Total de faltas: {total_faltas}
        """
        
        elementos.append(Paragraph(resumo_texto, self.styles['Normal']))
        
        return elementos

def gerar_pdf_funcionario(funcionario, kpis, registros_ponto, data_inicio, data_fim):
    """Função helper para gerar PDF do funcionário"""
    generator = FuncionarioPDFGenerator()
    return generator.gerar_pdf_funcionario(funcionario, kpis, registros_ponto, data_inicio, data_fim)