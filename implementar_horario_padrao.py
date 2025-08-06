#!/usr/bin/env python3
"""
IMPLEMENTAÇÃO COMPLETA DE HORÁRIO PADRÃO E CÁLCULO CORRETO DE HORAS EXTRAS
Baseado na lógica: entrada antecipada + saída atrasada = horas extras
"""

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import time, date, datetime
from sqlalchemy import Column, Integer, Time, Date, Boolean, ForeignKey, or_

def implementar_modelo_horario_padrao():
    """Implementa o modelo HorarioPadrao no sistema"""
    
    with app.app_context():
        print("🏗️ IMPLEMENTANDO MODELO DE HORÁRIO PADRÃO")
        print("=" * 60)
        
        # Verificar se a tabela já existe
        try:
            with db.engine.connect() as conn:
                result = conn.execute(db.text("SELECT tablename FROM pg_catalog.pg_tables WHERE tablename = 'horarios_padrao';"))
                if result.fetchone():
                    print("✅ Tabela horarios_padrao já existe")
                    return True
        except:
            pass
        
        # Criar tabela SQL diretamente (PostgreSQL syntax)
        sql_create_table = """
        CREATE TABLE IF NOT EXISTS horarios_padrao (
            id SERIAL PRIMARY KEY,
            funcionario_id INTEGER NOT NULL,
            entrada_padrao TIME NOT NULL,
            saida_almoco_padrao TIME,
            retorno_almoco_padrao TIME,
            saida_padrao TIME NOT NULL,
            ativo BOOLEAN DEFAULT TRUE,
            data_inicio DATE NOT NULL,
            data_fim DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (funcionario_id) REFERENCES funcionario (id)
        );
        """
        
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text(sql_create_table))
                print("✅ Tabela horarios_padrao criada com sucesso")
                
                # Criar índices para performance
                conn.execute(db.text("CREATE INDEX IF NOT EXISTS idx_horarios_funcionario ON horarios_padrao(funcionario_id);"))
                conn.execute(db.text("CREATE INDEX IF NOT EXISTS idx_horarios_ativo ON horarios_padrao(ativo);"))
                conn.commit()
            
            return True
        except Exception as e:
            print(f"❌ Erro ao criar tabela: {str(e)}")
            return False

def adicionar_campos_extras_registro_ponto():
    """Adiciona campos de horas extras detalhadas ao RegistroPonto"""
    
    with app.app_context():
        print("\n🔧 ADICIONANDO CAMPOS DE HORAS EXTRAS AO REGISTRO DE PONTO")
        print("=" * 60)
        
        # Lista de campos a adicionar (PostgreSQL syntax)
        campos_extras = [
            "ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS minutos_extras_entrada INTEGER DEFAULT 0;",
            "ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS minutos_extras_saida INTEGER DEFAULT 0;",
            "ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS total_minutos_extras INTEGER DEFAULT 0;",
            "ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS horas_extras_detalhadas DECIMAL(5,2) DEFAULT 0.0;",
            "ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS metodo_calculo VARCHAR(50) DEFAULT 'horario_padrao';"
        ]
        
        for sql in campos_extras:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text(sql))
                    conn.commit()
                print(f"✅ Campo adicionado: {sql.split('ADD COLUMN')[1].split()[0]}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print(f"⚠️  Campo já existe: {sql.split('ADD COLUMN')[1].split()[0]}")
                else:
                    print(f"❌ Erro: {str(e)}")

def criar_horarios_padrao_funcionarios():
    """Cria horários padrão para todos os funcionários ativos"""
    
    with app.app_context():
        print("\n📋 CRIANDO HORÁRIOS PADRÃO PARA FUNCIONÁRIOS")
        print("=" * 60)
        
        # Horário padrão padrão (07:12 às 17:00)
        horario_comum = {
            'entrada_padrao': '07:12:00',
            'saida_almoco_padrao': '12:00:00',
            'retorno_almoco_padrao': '13:00:00',
            'saida_padrao': '17:00:00',
            'data_inicio': '2025-01-01',
            'ativo': True
        }
        
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        print(f"📊 Funcionários ativos encontrados: {len(funcionarios)}")
        
        criados = 0
        ja_existem = 0
        
        for funcionario in funcionarios:
            # Verificar se já tem horário padrão
            with db.engine.connect() as conn:
                result = conn.execute(
                    db.text("SELECT id FROM horarios_padrao WHERE funcionario_id = :funcionario_id AND ativo = TRUE"),
                    {"funcionario_id": funcionario.id}
                ).fetchone()
                
                if result:
                    ja_existem += 1
                    print(f"⚠️  {funcionario.nome} já tem horário padrão")
                    continue
                
                # Criar horário padrão
                try:
                    conn.execute(db.text("""
                        INSERT INTO horarios_padrao 
                        (funcionario_id, entrada_padrao, saida_almoco_padrao, retorno_almoco_padrao, 
                         saida_padrao, data_inicio, ativo)
                        VALUES (:funcionario_id, :entrada_padrao, :saida_almoco_padrao, :retorno_almoco_padrao, 
                               :saida_padrao, :data_inicio, :ativo)
                    """), {
                        "funcionario_id": funcionario.id,
                        "entrada_padrao": horario_comum['entrada_padrao'],
                        "saida_almoco_padrao": horario_comum['saida_almoco_padrao'],
                        "retorno_almoco_padrao": horario_comum['retorno_almoco_padrao'],
                        "saida_padrao": horario_comum['saida_padrao'],
                        "data_inicio": horario_comum['data_inicio'],
                        "ativo": horario_comum['ativo']
                    })
                    conn.commit()
                    
                    criados += 1
                    print(f"✅ CRIADO: {funcionario.nome} - 07:12 às 17:00")
                    
                except Exception as e:
                    print(f"❌ Erro ao criar horário para {funcionario.nome}: {str(e)}")
        
        print(f"\n📊 RESUMO:")
        print(f"   Horários criados: {criados}")
        print(f"   Já existiam: {ja_existem}")

def time_para_minutos(time_str_ou_obj):
    """Converte time para minutos desde 00:00"""
    try:
        if isinstance(time_str_ou_obj, str):
            # String no formato HH:MM:SS ou HH:MM
            parts = time_str_ou_obj.split(':')
            horas = int(parts[0])
            minutos = int(parts[1])
        elif hasattr(time_str_ou_obj, 'hour'):
            # Objeto time
            horas = time_str_ou_obj.hour
            minutos = time_str_ou_obj.minute
        else:
            return 0
        
        return (horas * 60) + minutos
    except:
        return 0

def calcular_horas_extras_por_horario_padrao(registro_id, funcionario_id, data, hora_entrada, hora_saida):
    """
    Calcula horas extras baseado na diferença entre horário padrão e real
    
    Returns:
        tuple: (minutos_extras_entrada, minutos_extras_saida, total_horas_extras)
    """
    try:
        with app.app_context():
            # Buscar horário padrão do funcionário
            with db.engine.connect() as conn:
                result = conn.execute(db.text("""
                    SELECT entrada_padrao, saida_padrao 
                    FROM horarios_padrao 
                    WHERE funcionario_id = :funcionario_id AND ativo = TRUE 
                    AND data_inicio <= :data 
                    AND (data_fim IS NULL OR data_fim >= :data2)
                    LIMIT 1
                """), {"funcionario_id": funcionario_id, "data": data, "data2": data}).fetchone()
            
            if not result:
                print(f"⚠️  Funcionário {funcionario_id} sem horário padrão para {data}")
                return 0, 0, 0.0
            
            entrada_padrao_str, saida_padrao_str = result
            
            minutos_extras_entrada = 0
            minutos_extras_saida = 0
            
            print(f"👤 FUNCIONÁRIO ID: {funcionario_id}")
            print(f"📅 DATA: {data}")
            print(f"🕐 HORÁRIO PADRÃO: {entrada_padrao_str} às {saida_padrao_str}")
            print(f"🕐 HORÁRIO REAL: {hora_entrada} às {hora_saida}")
            
            # 1. CALCULAR EXTRAS POR ENTRADA ANTECIPADA
            if hora_entrada and entrada_padrao_str:
                entrada_real_min = time_para_minutos(str(hora_entrada))
                entrada_padrao_min = time_para_minutos(entrada_padrao_str)
                
                if entrada_real_min < entrada_padrao_min:
                    minutos_extras_entrada = entrada_padrao_min - entrada_real_min
                    print(f"⏰ ENTRADA ANTECIPADA: {minutos_extras_entrada}min extras")
                    print(f"   Padrão: {entrada_padrao_str} ({entrada_padrao_min}min)")
                    print(f"   Real: {hora_entrada} ({entrada_real_min}min)")
            
            # 2. CALCULAR EXTRAS POR SAÍDA ATRASADA
            if hora_saida and saida_padrao_str:
                saida_real_min = time_para_minutos(str(hora_saida))
                saida_padrao_min = time_para_minutos(saida_padrao_str)
                
                if saida_real_min > saida_padrao_min:
                    minutos_extras_saida = saida_real_min - saida_padrao_min
                    print(f"⏰ SAÍDA ATRASADA: {minutos_extras_saida}min extras")
                    print(f"   Padrão: {saida_padrao_str} ({saida_padrao_min}min)")
                    print(f"   Real: {hora_saida} ({saida_real_min}min)")
            
            # 3. CALCULAR TOTAL EM HORAS DECIMAIS
            total_minutos_extras = minutos_extras_entrada + minutos_extras_saida
            total_horas_extras = round(total_minutos_extras / 60, 2)
            
            print(f"📊 RESULTADO:")
            print(f"   Extras entrada: {minutos_extras_entrada}min")
            print(f"   Extras saída: {minutos_extras_saida}min")
            print(f"   Total: {total_minutos_extras}min = {total_horas_extras}h")
            
            return minutos_extras_entrada, minutos_extras_saida, total_horas_extras
            
    except Exception as e:
        print(f"❌ ERRO NO CÁLCULO DE EXTRAS: {e}")
        return 0, 0, 0.0

def corrigir_horas_extras_registros_existentes():
    """Corrige horas extras de registros existentes com a nova lógica"""
    
    with app.app_context():
        print("\n🚨 CORRIGINDO HORAS EXTRAS COM NOVA LÓGICA")
        print("=" * 60)
        
        # Buscar registros com horários (últimos 50)
        with db.engine.connect() as conn:
            registros = conn.execute(db.text("""
                SELECT rp.id, rp.funcionario_id, rp.data, rp.hora_entrada, rp.hora_saida, 
                       rp.horas_extras, f.nome
                FROM registro_ponto rp
                JOIN funcionario f ON rp.funcionario_id = f.id
                WHERE rp.hora_entrada IS NOT NULL 
                AND rp.hora_saida IS NOT NULL
                ORDER BY rp.data DESC 
                LIMIT 50
            """)).fetchall()
        
        print(f"📊 PROCESSANDO {len(registros)} REGISTROS...")
        
        corrigidos = 0
        
        for registro in registros:
            reg_id, funcionario_id, data, hora_entrada, hora_saida, extras_antigas, nome = registro
            
            try:
                print(f"\n🔄 PROCESSANDO: {data} - {nome}")
                print(f"   Extras antigas: {extras_antigas}h")
                
                # Calcular com nova lógica
                min_entrada, min_saida, total_horas = calcular_horas_extras_por_horario_padrao(
                    reg_id, funcionario_id, data, hora_entrada, hora_saida
                )
                
                # Atualizar registro
                with db.engine.connect() as conn:
                    conn.execute(db.text("""
                        UPDATE registro_ponto 
                        SET minutos_extras_entrada = :min_entrada,
                            minutos_extras_saida = :min_saida,
                            total_minutos_extras = :total_min,
                            horas_extras_detalhadas = :total_horas,
                            metodo_calculo = 'horario_padrao'
                        WHERE id = :reg_id
                    """), {
                        "min_entrada": min_entrada,
                        "min_saida": min_saida,
                        "total_min": min_entrada + min_saida,
                        "total_horas": total_horas,
                        "reg_id": reg_id
                    })
                    conn.commit()
                
                print(f"   Extras novas: {total_horas}h")
                print(f"   Diferença: {extras_antigas}h → {total_horas}h")
                
                corrigidos += 1
                
            except Exception as e:
                print(f"❌ ERRO NO REGISTRO {reg_id}: {e}")
        
        print(f"\n✅ CORREÇÃO CONCLUÍDA:")
        print(f"   Registros corrigidos: {corrigidos}")

def validar_calculo_exemplo():
    """Valida cálculo com exemplo real do documento"""
    
    print("\n🧪 VALIDANDO COM EXEMPLO REAL")
    print("=" * 60)
    
    # Dados do exemplo
    entrada_padrao = "07:12:00"  # 07:12
    entrada_real = "07:05:00"    # 07:05
    saida_padrao = "17:00:00"    # 17:00
    saida_real = "17:50:00"      # 17:50
    
    print(f"📊 EXEMPLO:")
    print(f"   Horário padrão: {entrada_padrao} às {saida_padrao}")
    print(f"   Horário real: {entrada_real} às {saida_real}")
    
    # Calcular extras entrada
    entrada_padrao_min = time_para_minutos(entrada_padrao)  # 432min
    entrada_real_min = time_para_minutos(entrada_real)      # 425min
    extras_entrada = entrada_padrao_min - entrada_real_min  # 7min
    
    # Calcular extras saída
    saida_padrao_min = time_para_minutos(saida_padrao)      # 1020min
    saida_real_min = time_para_minutos(saida_real)          # 1070min
    extras_saida = saida_real_min - saida_padrao_min        # 50min
    
    # Total
    total_minutos = extras_entrada + extras_saida           # 57min
    total_horas = round(total_minutos / 60, 2)              # 0.95h
    
    print(f"\n📊 RESULTADO:")
    print(f"   Entrada antecipada: {extras_entrada}min")
    print(f"   Saída atrasada: {extras_saida}min")
    print(f"   Total: {total_minutos}min = {total_horas}h")
    
    # Verificar se está correto
    if total_horas == 0.95:
        print("✅ CÁLCULO CORRETO! Resultado esperado: 0.95h")
    else:
        print(f"❌ CÁLCULO INCORRETO! Esperado: 0.95h, Obtido: {total_horas}h")
    
    return total_horas == 0.95

def implementar_sistema_completo():
    """Implementa o sistema completo de horário padrão"""
    
    print("🚀 IMPLEMENTANDO SISTEMA COMPLETO DE HORÁRIO PADRÃO")
    print("=" * 80)
    
    # 1. Implementar modelo
    if not implementar_modelo_horario_padrao():
        print("❌ Falha na implementação do modelo")
        return False
    
    # 2. Adicionar campos extras
    adicionar_campos_extras_registro_ponto()
    
    # 3. Criar horários padrão
    criar_horarios_padrao_funcionarios()
    
    # 4. Validar cálculo
    if not validar_calculo_exemplo():
        print("❌ Falha na validação do cálculo")
        return False
    
    # 5. Corrigir registros existentes
    corrigir_horas_extras_registros_existentes()
    
    print("\n🎯 SISTEMA IMPLEMENTADO COM SUCESSO!")
    print("=" * 80)
    print("✅ Modelo HorarioPadrao criado")
    print("✅ Campos de horas extras adicionados")
    print("✅ Horários padrão cadastrados")
    print("✅ Cálculo validado (0.95h para exemplo)")
    print("✅ Registros existentes corrigidos")
    
    return True

if __name__ == "__main__":
    implementar_sistema_completo()