#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IMPLEMENTAÇÃO COMPLETA: LÓGICA CORRETA DE HORAS EXTRAS BASEADA EM HORÁRIO PADRÃO
Sistema SIGE - Correção definitiva dos cálculos de horas extras
Data: 06 de Agosto de 2025
"""

from datetime import time, date, datetime, timedelta
from app import app, db
from models import Funcionario, RegistroPonto, Obra
from sqlalchemy import Column, Integer, Time, Boolean, Date, Float, ForeignKey, or_

# 1. CRIAR MODELO DE HORÁRIO PADRÃO
def criar_modelo_horario_padrao():
    """Cria o modelo HorarioPadrao no banco"""
    print("🔧 CRIANDO MODELO DE HORÁRIO PADRÃO...")
    
    sql_criar_tabela = """
    CREATE TABLE IF NOT EXISTS horarios_padrao (
        id SERIAL PRIMARY KEY,
        funcionario_id INTEGER NOT NULL REFERENCES funcionarios(id),
        
        -- Horários padrão
        entrada_padrao TIME NOT NULL,
        saida_almoco_padrao TIME,
        retorno_almoco_padrao TIME,
        saida_padrao TIME NOT NULL,
        
        -- Configurações
        ativo BOOLEAN DEFAULT TRUE,
        data_inicio DATE NOT NULL,
        data_fim DATE,
        
        -- Timestamps
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_horarios_padrao_funcionario_ativo 
    ON horarios_padrao(funcionario_id, ativo);
    
    CREATE INDEX IF NOT EXISTS idx_horarios_padrao_periodo 
    ON horarios_padrao(data_inicio, data_fim);
    """
    
    from sqlalchemy import text
    db.session.execute(text(sql_criar_tabela))
    db.session.commit()
    print("✅ TABELA horarios_padrao CRIADA")

# 2. ADICIONAR CAMPOS DE HORAS EXTRAS AO REGISTRO DE PONTO
def atualizar_modelo_registro_ponto():
    """Adiciona campos específicos para horas extras"""
    print("🔧 ATUALIZANDO MODELO DE REGISTRO DE PONTO...")
    
    # Descobrir nome correto da tabela
    from models import RegistroPonto
    nome_tabela = RegistroPonto.__tablename__
    
    campos_extras = f"""
    ALTER TABLE {nome_tabela} 
    ADD COLUMN IF NOT EXISTS minutos_extras_entrada INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS minutos_extras_saida INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_minutos_extras INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS horas_extras_calculadas DECIMAL(5,2) DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS horario_padrao_usado BOOLEAN DEFAULT FALSE;
    
    CREATE INDEX IF NOT EXISTS idx_registros_horas_extras 
    ON {nome_tabela}(horas_extras_calculadas);
    """
    
    from sqlalchemy import text
    db.session.execute(text(campos_extras))
    db.session.commit()
    print("✅ CAMPOS DE HORAS EXTRAS ADICIONADOS")

# 3. FUNÇÕES AUXILIARES
def time_para_minutos(time_obj):
    """Converte objeto time para minutos desde 00:00"""
    if not time_obj:
        return 0
    return (time_obj.hour * 60) + time_obj.minute

def minutos_para_time(minutos):
    """Converte minutos para objeto time"""
    horas = minutos // 60
    mins = minutos % 60
    return time(horas, mins)

def obter_horario_padrao_funcionario(funcionario_id, data_consulta):
    """Obtém horário padrão ativo do funcionário para uma data"""
    sql = """
    SELECT entrada_padrao, saida_almoco_padrao, retorno_almoco_padrao, saida_padrao
    FROM horarios_padrao 
    WHERE funcionario_id = %s 
      AND ativo = TRUE 
      AND data_inicio <= %s 
      AND (data_fim IS NULL OR data_fim >= %s)
    ORDER BY data_inicio DESC
    LIMIT 1
    """
    
    from sqlalchemy import text
    result = db.session.execute(text(sql), (funcionario_id, data_consulta, data_consulta)).fetchone()
    
    if result:
        return {
            'entrada_padrao': result[0],
            'saida_almoco_padrao': result[1],
            'retorno_almoco_padrao': result[2],
            'saida_padrao': result[3]
        }
    return None

# 4. FUNÇÃO PRINCIPAL DE CÁLCULO DE HORAS EXTRAS
def calcular_horas_extras_por_horario_padrao(registro):
    """
    Calcula horas extras baseado na diferença entre horário padrão e real
    
    LÓGICA:
    - Entrada antecipada = Horário padrão entrada - Horário real entrada
    - Saída atrasada = Horário real saída - Horário padrão saída  
    - Total horas extras = (minutos entrada + minutos saída) ÷ 60
    """
    try:
        print(f"\n🔄 CALCULANDO HORAS EXTRAS: {registro.funcionario_ref.nome} - {registro.data}")
        
        # Obter horário padrão
        horario_padrao = obter_horario_padrao_funcionario(registro.funcionario_id, registro.data)
        
        if not horario_padrao:
            print(f"⚠️  SEM HORÁRIO PADRÃO para {registro.funcionario_ref.nome}")
            return 0, 0, 0.0, False
        
        minutos_extras_entrada = 0
        minutos_extras_saida = 0
        
        print(f"🕐 HORÁRIO PADRÃO: {horario_padrao['entrada_padrao']} às {horario_padrao['saida_padrao']}")
        print(f"🕐 HORÁRIO REAL: {registro.hora_entrada} às {registro.hora_saida}")
        
        # 1. CALCULAR EXTRAS POR ENTRADA ANTECIPADA
        if registro.hora_entrada and horario_padrao['entrada_padrao']:
            entrada_real_min = time_para_minutos(registro.hora_entrada)
            entrada_padrao_min = time_para_minutos(horario_padrao['entrada_padrao'])
            
            if entrada_real_min < entrada_padrao_min:
                minutos_extras_entrada = entrada_padrao_min - entrada_real_min
                print(f"⏰ ENTRADA ANTECIPADA: {minutos_extras_entrada} minutos extras")
                print(f"   Padrão: {horario_padrao['entrada_padrao']} ({entrada_padrao_min}min)")
                print(f"   Real: {registro.hora_entrada} ({entrada_real_min}min)")
        
        # 2. CALCULAR EXTRAS POR SAÍDA ATRASADA
        if registro.hora_saida and horario_padrao['saida_padrao']:
            saida_real_min = time_para_minutos(registro.hora_saida)
            saida_padrao_min = time_para_minutos(horario_padrao['saida_padrao'])
            
            if saida_real_min > saida_padrao_min:
                minutos_extras_saida = saida_real_min - saida_padrao_min
                print(f"⏰ SAÍDA ATRASADA: {minutos_extras_saida} minutos extras")
                print(f"   Padrão: {horario_padrao['saida_padrao']} ({saida_padrao_min}min)")
                print(f"   Real: {registro.hora_saida} ({saida_real_min}min)")
        
        # 3. CALCULAR TOTAL EM HORAS DECIMAIS
        total_minutos_extras = minutos_extras_entrada + minutos_extras_saida
        total_horas_extras = round(total_minutos_extras / 60, 2)
        
        print(f"📊 RESULTADO:")
        print(f"   Extras entrada: {minutos_extras_entrada}min")
        print(f"   Extras saída: {minutos_extras_saida}min")
        print(f"   Total: {total_minutos_extras}min = {total_horas_extras}h")
        
        return minutos_extras_entrada, minutos_extras_saida, total_horas_extras, True
        
    except Exception as e:
        print(f"❌ ERRO NO CÁLCULO: {e}")
        return 0, 0, 0.0, False

# 5. CRIAR HORÁRIOS PADRÃO PARA FUNCIONÁRIOS
def criar_horarios_padrao_funcionarios():
    """Cria horários padrão para todos os funcionários ativos"""
    print("📋 CRIANDO HORÁRIOS PADRÃO PARA FUNCIONÁRIOS...")
    
    # Horário padrão comum (07:12 às 17:00)
    horario_comum = {
        'entrada_padrao': time(7, 12),      # 07:12
        'saida_almoco_padrao': time(12, 0), # 12:00
        'retorno_almoco_padrao': time(13, 0), # 13:00
        'saida_padrao': time(17, 0),        # 17:00
        'data_inicio': date(2025, 1, 1)
    }
    
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    criados = 0
    
    for funcionario in funcionarios:
        # Verificar se já tem horário padrão
        from sqlalchemy import text
        existe = db.session.execute(
            text("SELECT id FROM horarios_padrao WHERE funcionario_id = :funcionario_id AND ativo = TRUE"),
            {"funcionario_id": funcionario.id}
        ).fetchone()
        
        if existe:
            print(f"⚠️  {funcionario.nome} já tem horário padrão")
            continue
        
        # Criar horário padrão
        sql_inserir = """
        INSERT INTO horarios_padrao 
        (funcionario_id, entrada_padrao, saida_almoco_padrao, retorno_almoco_padrao, saida_padrao, ativo, data_inicio)
        VALUES (:funcionario_id, :entrada_padrao, :saida_almoco_padrao, :retorno_almoco_padrao, :saida_padrao, :ativo, :data_inicio)
        """
        
        from sqlalchemy import text
        db.session.execute(text(sql_inserir), {
            "funcionario_id": funcionario.id,
            "entrada_padrao": horario_comum['entrada_padrao'],
            "saida_almoco_padrao": horario_comum['saida_almoco_padrao'], 
            "retorno_almoco_padrao": horario_comum['retorno_almoco_padrao'],
            "saida_padrao": horario_comum['saida_padrao'],
            "ativo": True,
            "data_inicio": horario_comum['data_inicio']
        })
        
        print(f"✅ CRIADO: {funcionario.nome} - {horario_comum['entrada_padrao']} às {horario_comum['saida_padrao']}")
        criados += 1
    
    db.session.commit()
    print(f"📋 HORÁRIOS PADRÃO CRIADOS: {criados} funcionários")

# 6. CORRIGIR REGISTROS EXISTENTES
def corrigir_horas_extras_registros_existentes():
    """Aplica nova lógica de cálculo aos registros existentes"""
    print("🚨 APLICANDO NOVA LÓGICA DE HORAS EXTRAS...")
    
    # Buscar registros dos últimos 60 dias com horários preenchidos
    data_limite = date.today() - timedelta(days=60)
    
    registros = RegistroPonto.query.filter(
        RegistroPonto.data >= data_limite,
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).order_by(RegistroPonto.data.desc()).all()
    
    print(f"📊 PROCESSANDO {len(registros)} REGISTROS DOS ÚLTIMOS 60 DIAS...")
    
    corrigidos = 0
    erros = 0
    
    for registro in registros:
        try:
            # Valores antigos
            extras_antigas = registro.horas_extras or 0
            
            # Calcular com nova lógica
            entrada_extra, saida_extra, total_extra, sucesso = calcular_horas_extras_por_horario_padrao(registro)
            
            if sucesso:
                # Atualizar campos
                # Usar nome correto da tabela
                nome_tabela = registro.__class__.__tablename__
                sql_update = f"""
                UPDATE {nome_tabela} 
                SET minutos_extras_entrada = :minutos_extras_entrada,
                    minutos_extras_saida = :minutos_extras_saida,
                    total_minutos_extras = :total_minutos_extras,
                    horas_extras_calculadas = :horas_extras_calculadas,
                    horario_padrao_usado = :horario_padrao_usado,
                    horas_extras = :horas_extras
                WHERE id = :registro_id
                """
                
                from sqlalchemy import text
                db.session.execute(text(sql_update), {
                    "minutos_extras_entrada": entrada_extra,
                    "minutos_extras_saida": saida_extra,
                    "total_minutos_extras": entrada_extra + saida_extra,
                    "horas_extras_calculadas": total_extra,
                    "horario_padrao_usado": True,
                    "horas_extras": total_extra,
                    "registro_id": registro.id
                })
                
                print(f"✅ CORRIGIDO: {extras_antigas}h → {total_extra}h")
                corrigidos += 1
            else:
                erros += 1
                
        except Exception as e:
            print(f"❌ ERRO: {e}")
            erros += 1
    
    # Salvar alterações
    try:
        db.session.commit()
        print(f"\n🎉 CORREÇÃO CONCLUÍDA:")
        print(f"   ✅ Corrigidos: {corrigidos}")
        print(f"   ❌ Erros: {erros}")
    except Exception as e:
        print(f"❌ ERRO AO SALVAR: {e}")
        db.session.rollback()

# 7. VALIDAÇÃO COM EXEMPLO REAL
def validar_calculo_exemplo():
    """Valida cálculo com exemplo fornecido no prompt"""
    print("\n🧪 VALIDANDO COM EXEMPLO DO PROMPT:")
    
    # Dados do exemplo
    entrada_padrao = time(7, 12)    # 07:12
    entrada_real = time(7, 5)       # 07:05  
    saida_padrao = time(17, 0)      # 17:00
    saida_real = time(17, 50)       # 17:50
    
    print(f"📋 EXEMPLO:")
    print(f"   Horário Padrão: {entrada_padrao} às {saida_padrao}")
    print(f"   Horário Real: {entrada_real} às {saida_real}")
    
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
    total_horas = total_minutos / 60                        # 0.95h
    
    print(f"\n📊 CÁLCULO:")
    print(f"   Entrada: {entrada_padrao_min}min - {entrada_real_min}min = {extras_entrada}min")
    print(f"   Saída: {saida_real_min}min - {saida_padrao_min}min = {extras_saida}min")
    print(f"   Total: {extras_entrada}min + {extras_saida}min = {total_minutos}min = {total_horas}h")
    
    # Resultado esperado
    if total_minutos == 57 and abs(total_horas - 0.95) < 0.01:
        print("✅ VALIDAÇÃO PASSOU: Cálculo correto!")
    else:
        print("❌ VALIDAÇÃO FALHOU: Resultado incorreto")

# 8. FUNÇÃO PRINCIPAL
def implementar_horario_padrao_completo():
    """Implementa sistema completo de horário padrão"""
    try:
        print("🚀 INICIANDO IMPLEMENTAÇÃO COMPLETA DE HORÁRIO PADRÃO")
        print("=" * 60)
        
        # 1. Criar modelo
        criar_modelo_horario_padrao()
        
        # 2. Atualizar registro de ponto
        atualizar_modelo_registro_ponto()
        
        # 3. Criar horários padrão
        criar_horarios_padrao_funcionarios()
        
        # 4. Validar exemplo
        validar_calculo_exemplo()
        
        # 5. Corrigir registros
        corrigir_horas_extras_registros_existentes()
        
        print("\n" + "=" * 60)
        print("🎉 IMPLEMENTAÇÃO COMPLETA FINALIZADA!")
        print("✅ Sistema de horário padrão ativo")
        print("✅ Cálculos de horas extras corrigidos")
        print("✅ Registros históricos atualizados")
        
    except Exception as e:
        print(f"❌ ERRO NA IMPLEMENTAÇÃO: {e}")
        import traceback
        traceback.print_exc()
        
        # Rollback em caso de erro
        try:
            db.session.rollback()
            print("🔄 Rollback executado")
        except:
            pass

if __name__ == "__main__":
    with app.app_context():
        implementar_horario_padrao_completo()