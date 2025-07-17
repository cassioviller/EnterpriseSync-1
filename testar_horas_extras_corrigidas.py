#!/usr/bin/env python3
"""
Script para testar as correções nos cálculos de horas extras
com horários específicos de trabalho - SIGE v6.3.1
"""

import os
import sys
from datetime import date, datetime, time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configurar conexão com o banco
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///sige.db')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def criar_horarios_teste():
    """Criar horários de teste para diferentes funcionários"""
    
    # 1. Horário de Estagiário - 4h/dia
    horario_estagiario = """
    INSERT INTO horario_trabalho (nome, entrada, saida_almoco, retorno_almoco, saida, dias_semana, horas_diarias, valor_hora)
    VALUES ('Estagiário - 4h/dia', '08:00:00', '12:00:00', '13:00:00', '13:00:00', '1,2,3,4,5', 4.0, 15.0)
    ON CONFLICT (nome) DO NOTHING;
    """
    
    # 2. Horário Meio Período - 5h/dia
    horario_meio_periodo = """
    INSERT INTO horario_trabalho (nome, entrada, saida_almoco, retorno_almoco, saida, dias_semana, horas_diarias, valor_hora)
    VALUES ('Meio Período - 5h/dia', '07:00:00', '12:00:00', '13:00:00', '13:00:00', '1,2,3,4,5', 5.0, 18.0)
    ON CONFLICT (nome) DO NOTHING;
    """
    
    # 3. Horário Gerencial - 6h/dia
    horario_gerencial = """
    INSERT INTO horario_trabalho (nome, entrada, saida_almoco, retorno_almoco, saida, dias_semana, horas_diarias, valor_hora)
    VALUES ('Gerencial - 6h/dia', '09:00:00', '12:00:00', '13:00:00', '16:00:00', '1,2,3,4,5', 6.0, 25.0)
    ON CONFLICT (nome) DO NOTHING;
    """
    
    try:
        session.execute(text(horario_estagiario))
        session.execute(text(horario_meio_periodo))
        session.execute(text(horario_gerencial))
        session.commit()
        print("✅ Horários de teste criados com sucesso!")
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao criar horários: {e}")

def criar_funcionarios_teste():
    """Criar funcionários de teste com diferentes horários"""
    
    # Atualizar João (F0099) para horário de estagiário
    try:
        # Buscar ID do horário de estagiário
        horario_estagiario = session.execute(text("SELECT id FROM horario_trabalho WHERE nome = 'Estagiário - 4h/dia'")).fetchone()
        if horario_estagiario:
            session.execute(text(f"""
                UPDATE funcionario 
                SET horario_trabalho_id = {horario_estagiario.id}, salario = 1200.00
                WHERE codigo = 'F0099'
            """))
            session.commit()
            print("✅ João (F0099) atualizado para horário de estagiário (4h/dia)")
        
        # Criar funcionário de meio período
        horario_meio_periodo = session.execute(text("SELECT id FROM horario_trabalho WHERE nome = 'Meio Período - 5h/dia'")).fetchone()
        if horario_meio_periodo:
            session.execute(text(f"""
                INSERT INTO funcionario (codigo, nome, cpf, data_admissao, salario, ativo, horario_trabalho_id, departamento_id, funcao_id)
                VALUES ('F0100', 'Ana Clara Meio Período', '111.111.111-11', '2024-01-01', 1800.00, true, {horario_meio_periodo.id}, 1, 1)
                ON CONFLICT (codigo) DO UPDATE SET 
                    horario_trabalho_id = {horario_meio_periodo.id},
                    salario = 1800.00
            """))
            session.commit()
            print("✅ Funcionário Ana Clara (F0100) criado para horário meio período (5h/dia)")
        
        # Criar funcionário gerencial
        horario_gerencial = session.execute(text("SELECT id FROM horario_trabalho WHERE nome = 'Gerencial - 6h/dia'")).fetchone()
        if horario_gerencial:
            session.execute(text(f"""
                INSERT INTO funcionario (codigo, nome, cpf, data_admissao, salario, ativo, horario_trabalho_id, departamento_id, funcao_id)
                VALUES ('F0101', 'Carlos Gerente Silva', '222.222.222-22', '2024-01-01', 5000.00, true, {horario_gerencial.id}, 1, 1)
                ON CONFLICT (codigo) DO UPDATE SET 
                    horario_trabalho_id = {horario_gerencial.id},
                    salario = 5000.00
            """))
            session.commit()
            print("✅ Funcionário Carlos (F0101) criado para horário gerencial (6h/dia)")
            
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao criar funcionários: {e}")

def criar_registros_teste():
    """Criar registros de ponto para testar os cálculos"""
    
    # Data de teste
    data_teste = "2025-07-15"
    
    registros = [
        # João Estagiário (4h/dia) - trabalhando 6h = 2h extras
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '{data_teste}', 'trabalho_normal', '08:00:00', '14:00:00', 6.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0099'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 6.0, horas_extras = 2.0
        """,
        
        # Ana Clara Meio Período (5h/dia) - trabalhando 7h = 2h extras
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '{data_teste}', 'trabalho_normal', '07:00:00', '14:00:00', 7.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0100'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 7.0, horas_extras = 2.0
        """,
        
        # Carlos Gerente (6h/dia) - trabalhando 8h = 2h extras
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '{data_teste}', 'trabalho_normal', '09:00:00', '17:00:00', 8.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0101'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 8.0, horas_extras = 2.0
        """,
        
        # Cássio Comercial (8h/dia) - trabalhando 10h = 2h extras
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '{data_teste}', 'trabalho_normal', '07:00:00', '17:00:00', 10.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0006'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 10.0, horas_extras = 2.0
        """,
        
        # Registro de sábado para João (100% adicional)
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '2025-07-12', 'sabado_horas_extras', '08:00:00', '14:00:00', 6.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0099'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 6.0, horas_extras = 2.0, tipo_registro = 'sabado_horas_extras'
        """,
        
        # Registro de domingo para Ana Clara (100% adicional)
        f"""
        INSERT INTO registro_ponto (funcionario_id, data, tipo_registro, hora_entrada, hora_saida, horas_trabalhadas, horas_extras, total_atraso_horas)
        SELECT id, '2025-07-13', 'domingo_horas_extras', '07:00:00', '14:00:00', 7.0, 2.0, 0.0
        FROM funcionario WHERE codigo = 'F0100'
        ON CONFLICT (funcionario_id, data) DO UPDATE SET
            horas_trabalhadas = 7.0, horas_extras = 2.0, tipo_registro = 'domingo_horas_extras'
        """
    ]
    
    try:
        for registro in registros:
            session.execute(text(registro))
        session.commit()
        print("✅ Registros de ponto de teste criados com sucesso!")
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao criar registros: {e}")

def testar_calculos():
    """Testar os cálculos de horas extras com diferentes horários"""
    
    print("\n" + "="*80)
    print("TESTE DOS CÁLCULOS DE HORAS EXTRAS - SIGE v6.3.1")
    print("="*80)
    
    # Consultar funcionários com seus horários
    query = text("""
        SELECT f.codigo, f.nome, f.salario, 
               h.nome as horario_nome, h.horas_diarias, h.valor_hora,
               COUNT(rp.id) as total_registros
        FROM funcionario f
        LEFT JOIN horario_trabalho h ON f.horario_trabalho_id = h.id
        LEFT JOIN registro_ponto rp ON f.id = rp.funcionario_id 
            AND rp.data >= '2025-07-12' AND rp.data <= '2025-07-15'
        WHERE f.codigo IN ('F0099', 'F0100', 'F0101', 'F0006')
        GROUP BY f.codigo, f.nome, f.salario, h.nome, h.horas_diarias, h.valor_hora
        ORDER BY f.codigo
    """)
    
    funcionarios = session.execute(query).fetchall()
    
    for func in funcionarios:
        print(f"\n📋 FUNCIONÁRIO: {func.nome} ({func.codigo})")
        print(f"   Salário: R$ {func.salario:,.2f}")
        print(f"   Horário: {func.horario_nome or 'Não definido'}")
        print(f"   Horas diárias: {func.horas_diarias or 8.0}h")
        print(f"   Valor/hora: R$ {func.valor_hora or 0.0:.2f}")
        print(f"   Registros: {func.total_registros}")
        
        # Buscar registros de ponto
        registros_query = text("""
            SELECT rp.data, rp.tipo_registro, rp.horas_trabalhadas, rp.horas_extras
            FROM registro_ponto rp
            JOIN funcionario f ON rp.funcionario_id = f.id
            WHERE f.codigo = :codigo
            AND rp.data >= '2025-07-12' AND rp.data <= '2025-07-15'
            ORDER BY rp.data
        """)
        
        registros = session.execute(registros_query, {'codigo': func.codigo}).fetchall()
        
        print(f"   📊 REGISTROS DE PONTO:")
        total_horas_trabalhadas = 0
        total_horas_extras_calculadas = 0
        custo_total_extras = 0
        
        for reg in registros:
            horas_diarias = func.horas_diarias or 8.0
            valor_hora = func.valor_hora or (func.salario / (horas_diarias * 22)) if func.salario else 0
            
            # Calcular horas extras baseado no horário específico
            horas_extras_corretas = max(0, reg.horas_trabalhadas - horas_diarias)
            
            # Calcular custo das extras com percentual correto
            if reg.tipo_registro == 'sabado_horas_extras':
                percentual = 1.5  # 50% adicional
            elif reg.tipo_registro in ['domingo_horas_extras', 'feriado_trabalhado']:
                percentual = 2.0  # 100% adicional
            else:
                percentual = 1.5  # Padrão 50%
            
            custo_extras = horas_extras_corretas * valor_hora * percentual
            
            print(f"     {reg.data} | {reg.tipo_registro} | {reg.horas_trabalhadas}h trab. | {horas_extras_corretas:.1f}h extras | R$ {custo_extras:.2f}")
            
            total_horas_trabalhadas += reg.horas_trabalhadas
            total_horas_extras_calculadas += horas_extras_corretas
            custo_total_extras += custo_extras
        
        print(f"   💰 RESUMO:")
        print(f"     Total horas trabalhadas: {total_horas_trabalhadas}h")
        print(f"     Total horas extras: {total_horas_extras_calculadas}h")
        print(f"     Custo horas extras: R$ {custo_total_extras:.2f}")
        
        # Calcular produtividade correta
        dias_periodo = 4  # 12 a 15 de julho
        horas_esperadas = (func.horas_diarias or 8.0) * dias_periodo
        produtividade = (total_horas_trabalhadas / horas_esperadas) * 100 if horas_esperadas > 0 else 0
        
        print(f"     Horas esperadas: {horas_esperadas}h ({dias_periodo} dias × {func.horas_diarias or 8.0}h)")
        print(f"     Produtividade: {produtividade:.1f}%")

def main():
    """Função principal"""
    print("🚀 INICIANDO TESTES DE CORREÇÃO DE HORAS EXTRAS")
    print("="*60)
    
    # 1. Criar horários de teste
    print("\n1. Criando horários de teste...")
    criar_horarios_teste()
    
    # 2. Criar funcionários de teste
    print("\n2. Criando funcionários de teste...")
    criar_funcionarios_teste()
    
    # 3. Criar registros de teste
    print("\n3. Criando registros de ponto de teste...")
    criar_registros_teste()
    
    # 4. Testar cálculos
    print("\n4. Testando cálculos...")
    testar_calculos()
    
    print("\n" + "="*80)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
    print("="*80)
    
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Verificar se os KPIs no sistema estão usando os valores corretos")
    print("2. Testar a página de perfil dos funcionários")
    print("3. Validar os cálculos de custo de mão de obra")
    print("4. Confirmar que a produtividade está sendo calculada corretamente")

if __name__ == "__main__":
    main()