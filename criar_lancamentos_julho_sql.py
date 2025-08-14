#!/usr/bin/env python3
"""
Gerar SQL para criar lançamentos de julho 2025 para Pedro Santos Vale Verde (ID 132)
"""

from datetime import date
import calendar

def gerar_sql_lancamentos_julho():
    """Gerar comandos SQL para inserir registros de julho 2025"""
    
    funcionario_id = 132
    ano = 2025
    mes = 7
    
    # Obter todos os dias do mês
    primeiro_dia, ultimo_dia = calendar.monthrange(ano, mes)
    
    sql_commands = []
    
    # Primeiro, limpar registros existentes
    sql_commands.append(f"""
-- Limpar registros existentes do funcionário 132 em julho 2025
DELETE FROM registro_ponto 
WHERE funcionario_id = {funcionario_id} 
AND data >= '2025-07-01' AND data <= '2025-07-31';
""")
    
    for dia in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, dia)
        dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
        
        # Valores padrão
        tipo_registro = 'trabalho_normal'
        hora_entrada = "'07:12'"
        hora_almoco_saida = "'12:00'"
        hora_almoco_retorno = "'13:00'"
        hora_saida = "'17:00'"
        horas_trabalhadas = 8.8
        horas_extras = 0.0
        total_atraso_minutos = 0
        total_atraso_horas = 0.0
        
        # Segunda a sexta: trabalho normal
        if dia_semana < 5:  # Segunda a sexta
            tipo_registro = 'trabalho_normal'
            
            # Adicionar variações realistas
            if dia % 7 == 0:  # A cada 7 dias, adicionar horas extras
                hora_saida = "'19:00'"
                horas_trabalhadas = 10.8
                horas_extras = 2.0
            
            if dia % 10 == 0:  # A cada 10 dias, pequeno atraso
                hora_entrada = "'07:30'"
                total_atraso_minutos = 18
                total_atraso_horas = 0.3
                
        elif dia_semana == 5:  # Sábado
            if dia % 2 == 0:  # Trabalha sábados alternados
                tipo_registro = 'sabado_trabalhado'
                hora_entrada = "'07:12'"
                hora_almoco_saida = "NULL"
                hora_almoco_retorno = "NULL"
                hora_saida = "'12:00'"
                horas_trabalhadas = 4.8
                horas_extras = 4.8
            else:
                tipo_registro = 'sabado_folga'
                hora_entrada = "NULL"
                hora_almoco_saida = "NULL"
                hora_almoco_retorno = "NULL"
                hora_saida = "NULL"
                horas_trabalhadas = 0.0
                horas_extras = 0.0
                
        else:  # Domingo
            tipo_registro = 'domingo_folga'
            hora_entrada = "NULL"
            hora_almoco_saida = "NULL"
            hora_almoco_retorno = "NULL"
            hora_saida = "NULL"
            horas_trabalhadas = 0.0
            horas_extras = 0.0
        
        # Adicionar faltas
        if dia in [15, 25]:  # 2 faltas no mês
            tipo_registro = 'falta'
            hora_entrada = "NULL"
            hora_almoco_saida = "NULL"
            hora_almoco_retorno = "NULL"
            hora_saida = "NULL"
            horas_trabalhadas = 0.0
            horas_extras = 0.0
        
        # Gerar comando SQL
        sql_command = f"""
INSERT INTO registro_ponto (
    funcionario_id, data, tipo_registro, hora_entrada, hora_almoco_saida, 
    hora_almoco_retorno, hora_saida, horas_trabalhadas, horas_extras,
    total_atraso_minutos, total_atraso_horas, observacoes
) VALUES (
    {funcionario_id}, 
    '{data_atual}', 
    '{tipo_registro}', 
    {hora_entrada}, 
    {hora_almoco_saida}, 
    {hora_almoco_retorno}, 
    {hora_saida}, 
    {horas_trabalhadas}, 
    {horas_extras},
    {total_atraso_minutos},
    {total_atraso_horas},
    'Gerado automaticamente - Pedro Santos Vale Verde - {data_atual.strftime("%d/%m/%Y")}'
);"""
        
        sql_commands.append(sql_command)
    
    return sql_commands

if __name__ == '__main__':
    commands = gerar_sql_lancamentos_julho()
    
    print("-- SQL para criar lançamentos de julho 2025 para Pedro Santos Vale Verde")
    print("-- Funcionário ID: 132")
    print("-- Horário: 7h12 às 17h")
    print("")
    
    for cmd in commands:
        print(cmd)
        print("")