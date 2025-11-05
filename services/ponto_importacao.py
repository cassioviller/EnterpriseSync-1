"""
Serviço de Importação de Pontos via Excel
Sistema SIGE v9.0
"""

from io import BytesIO
from datetime import datetime, date, time
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class PontoExcelService:
    """Serviço para gerar planilhas modelo e importar pontos"""
    
    @staticmethod
    def gerar_planilha_modelo(funcionarios: List, mes_referencia: date = None) -> BytesIO:
        """
        Gera planilha Excel modelo com uma aba por funcionário ativo
        
        Args:
            funcionarios: Lista de objetos Funcionario ativos
            mes_referencia: Mês de referência para gerar dias (padrão: mês atual)
        
        Returns:
            BytesIO com o arquivo Excel
        """
        if not mes_referencia:
            mes_referencia = date.today()
        
        # Criar workbook
        wb = Workbook()
        
        # Se não houver funcionários, criar uma planilha de aviso
        if not funcionarios:
            ws = wb.active
            ws.title = "Aviso"
            ws['A1'] = "⚠️ ATENÇÃO"
            ws['A1'].font = Font(bold=True, size=16, color="FF0000")
            ws['A3'] = "Não há funcionários ativos cadastrados no sistema."
            ws['A4'] = "Por favor, cadastre funcionários antes de gerar a planilha de importação."
            ws.column_dimensions['A'].width = 60
            
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            return buffer
        
        wb.remove(wb.active)  # Remover sheet padrão
        
        # Estilos
        header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Criar uma aba para cada funcionário
        for func in funcionarios:
            # Nome da aba: "Código - Nome" (limitado a 31 caracteres do Excel)
            sheet_name = f"{func.codigo} - {func.nome}"[:31]
            ws = wb.create_sheet(title=sheet_name)
            
            # Cabeçalho informativo
            ws['A1'] = f"REGISTRO DE PONTO - {func.nome.upper()}"
            ws['A1'].font = Font(bold=True, size=14)
            ws.merge_cells('A1:E1')
            
            ws['A2'] = f"Código: {func.codigo}"
            ws['B2'] = f"CPF: {func.cpf}"
            ws['C2'] = f"Cargo: {func.funcao_ref.nome if func.funcao_ref else 'N/A'}"
            
            # Linha em branco
            current_row = 4
            
            # Cabeçalho da tabela
            headers = ['Data', 'Entrada', 'Saída', 'Início Almoço', 'Fim Almoço']
            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=current_row, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = border
            
            # Gerar dias do mês
            import calendar
            ano = mes_referencia.year
            mes = mes_referencia.month
            _, ultimo_dia = calendar.monthrange(ano, mes)
            
            current_row += 1
            for dia in range(1, ultimo_dia + 1):
                data_dia = date(ano, mes, dia)
                
                # Data
                cell = ws.cell(row=current_row, column=1, value=data_dia.strftime('%d/%m/%Y'))
                cell.border = border
                cell.alignment = Alignment(horizontal='center')
                
                # Horários vazios (usuário preencherá)
                for col in range(2, 6):
                    cell = ws.cell(row=current_row, column=col, value='')
                    cell.border = border
                    cell.alignment = Alignment(horizontal='center')
                
                current_row += 1
            
            # Instruções no final
            current_row += 2
            ws[f'A{current_row}'] = "INSTRUÇÕES:"
            ws[f'A{current_row}'].font = Font(bold=True, color="FF0000")
            
            current_row += 1
            instrucoes = [
                "• Preencha os horários no formato HH:MM (exemplo: 08:00)",
                "• Deixe em branco os campos de dias não trabalhados",
                "• Não altere as datas ou o formato da planilha",
                "• Não exclua ou adicione linhas",
                "• Não renomeie as abas"
            ]
            for instrucao in instrucoes:
                ws[f'A{current_row}'] = instrucao
                current_row += 1
            
            # Ajustar largura das colunas
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 12
            ws.column_dimensions['C'].width = 12
            ws.column_dimensions['D'].width = 15
            ws.column_dimensions['E'].width = 15
        
        # Salvar em BytesIO
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def validar_e_importar(
        excel_file: BytesIO,
        funcionarios_map: Dict[str, int],
        admin_id: int
    ) -> Tuple[List[Dict], List[str]]:
        """
        Valida e prepara dados do Excel para importação
        
        Args:
            excel_file: Arquivo Excel em BytesIO
            funcionarios_map: Dict {codigo_funcionario: funcionario_id}
            admin_id: ID do admin (multi-tenant)
        
        Returns:
            Tupla (registros_validos, erros)
        """
        registros_validos = []
        erros = []
        
        try:
            wb = load_workbook(excel_file)
        except Exception as e:
            erros.append(f"Erro ao ler arquivo Excel: {str(e)}")
            return [], erros
        
        # Processar cada aba (uma por funcionário)
        for sheet_name in wb.sheetnames:
            try:
                ws = wb[sheet_name]
                
                # Extrair código do funcionário do nome da aba (formato: "CÓDIGO - Nome")
                if ' - ' not in sheet_name:
                    erros.append(f"Aba '{sheet_name}': formato inválido (esperado 'CÓDIGO - Nome')")
                    continue
                
                codigo_func = sheet_name.split(' - ')[0].strip()
                
                # Verificar se funcionário existe
                if codigo_func not in funcionarios_map:
                    erros.append(f"Aba '{sheet_name}': funcionário com código '{codigo_func}' não encontrado ou inativo")
                    continue
                
                funcionario_id = funcionarios_map[codigo_func]
                
                # Encontrar linha do cabeçalho (procurar por "Data")
                header_row = None
                for row in range(1, 10):  # Procurar nas primeiras 10 linhas
                    if ws.cell(row=row, column=1).value == 'Data':
                        header_row = row
                        break
                
                if not header_row:
                    erros.append(f"Aba '{sheet_name}': cabeçalho não encontrado")
                    continue
                
                # Processar dados a partir da linha após o cabeçalho
                for row in range(header_row + 1, ws.max_row + 1):
                    data_cell = ws.cell(row=row, column=1).value
                    
                    # Pular linhas vazias
                    if not data_cell:
                        continue
                    
                    # Converter data
                    try:
                        if isinstance(data_cell, datetime):
                            data_ponto = data_cell.date()
                        elif isinstance(data_cell, date):
                            data_ponto = data_cell
                        elif isinstance(data_cell, str):
                            data_ponto = datetime.strptime(data_cell, '%d/%m/%Y').date()
                        else:
                            erros.append(f"Aba '{sheet_name}', linha {row}: formato de data inválido '{data_cell}'")
                            continue
                    except Exception as e:
                        erros.append(f"Aba '{sheet_name}', linha {row}: erro ao converter data '{data_cell}': {str(e)}")
                        continue
                    
                    # Ler horários
                    entrada = PontoExcelService._parse_time(ws.cell(row=row, column=2).value)
                    saida = PontoExcelService._parse_time(ws.cell(row=row, column=3).value)
                    almoco_inicio = PontoExcelService._parse_time(ws.cell(row=row, column=4).value)
                    almoco_fim = PontoExcelService._parse_time(ws.cell(row=row, column=5).value)
                    
                    # Pular se todos os horários estiverem vazios
                    if not any([entrada, saida, almoco_inicio, almoco_fim]):
                        continue
                    
                    # Validar lógica de horários
                    if entrada and saida and entrada >= saida:
                        erros.append(
                            f"Aba '{sheet_name}', linha {row}, data {data_ponto.strftime('%d/%m/%Y')}: "
                            f"Horário de entrada ({entrada}) deve ser menor que saída ({saida})"
                        )
                        continue
                    
                    if almoco_inicio and almoco_fim and almoco_inicio >= almoco_fim:
                        erros.append(
                            f"Aba '{sheet_name}', linha {row}, data {data_ponto.strftime('%d/%m/%Y')}: "
                            f"Início do almoço ({almoco_inicio}) deve ser menor que fim ({almoco_fim})"
                        )
                        continue
                    
                    # Registro válido
                    registros_validos.append({
                        'funcionario_id': funcionario_id,
                        'data': data_ponto,
                        'hora_entrada': entrada,
                        'hora_saida': saida,
                        'hora_almoco_saida': almoco_inicio,
                        'hora_almoco_retorno': almoco_fim,
                        'admin_id': admin_id,
                        'tipo_registro': 'trabalhado'
                    })
                    
            except Exception as e:
                erros.append(f"Erro ao processar aba '{sheet_name}': {str(e)}")
                logger.error(f"Erro ao processar aba '{sheet_name}': {e}", exc_info=True)
        
        return registros_validos, erros
    
    @staticmethod
    def _parse_time(value) -> time | None:
        """Converte valor de célula Excel para objeto time"""
        if not value:
            return None
        
        try:
            if isinstance(value, time):
                return value
            elif isinstance(value, datetime):
                return value.time()
            elif isinstance(value, str):
                # Tentar formatos HH:MM ou HH:MM:SS
                value = value.strip()
                if ':' in value:
                    parts = value.split(':')
                    if len(parts) >= 2:
                        hora = int(parts[0])
                        minuto = int(parts[1])
                        segundo = int(parts[2]) if len(parts) > 2 else 0
                        return time(hora, minuto, segundo)
            elif isinstance(value, (int, float)):
                # Excel pode armazenar tempo como fração de dia
                total_seconds = int(value * 86400)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return time(hours, minutes, seconds)
        except Exception as e:
            logger.warning(f"Erro ao converter horário '{value}': {e}")
        
        return None
