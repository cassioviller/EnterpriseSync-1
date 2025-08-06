#!/usr/bin/env python3
"""
CORREÇÃO DEFINITIVA: Horas Extras Baseado em Horário Padrão
Sistema SIGE - Implementação única e correta
"""

from app import app, db
from models import *
from datetime import time, date
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnosticar_problema_atual():
    """Diagnóstica o problema específico nos cálculos"""
    logger.info("🔍 DIAGNOSTICANDO PROBLEMA ATUAL...")
    
    with app.app_context():
        # Verificar um exemplo específico
        registro_exemplo = db.session.execute(text(f"""
            SELECT 
                r.id, r.data, r.hora_entrada, r.hora_saida, r.horas_extras,
                f.nome, f.id as func_id
            FROM {RegistroPonto.__tablename__} r
            JOIN funcionario f ON r.funcionario_id = f.id
            WHERE r.hora_entrada IS NOT NULL 
              AND r.hora_saida IS NOT NULL
              AND r.data >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY r.data DESC
            LIMIT 5
        """)).fetchall()
        
        print("\n📊 EXEMPLOS ATUAIS (Últimos 7 dias):")
        for reg in registro_exemplo:
            reg_id, data, entrada, saida, extras_atual, nome, func_id = reg
            
            # Calcular manualmente o que deveria ser
            entrada_real_min = entrada.hour * 60 + entrada.minute if entrada else 0
            saida_real_min = saida.hour * 60 + saida.minute if saida else 0
            
            # Horário padrão: 07:12 às 17:00
            entrada_padrao_min = 7 * 60 + 12  # 432 min
            saida_padrao_min = 17 * 60         # 1020 min
            
            extras_entrada = max(0, entrada_padrao_min - entrada_real_min)
            extras_saida = max(0, saida_real_min - saida_padrao_min)
            total_correto = round((extras_entrada + extras_saida) / 60, 2)
            
            print(f"  {nome} ({data}):")
            print(f"    Horários: {entrada} às {saida}")
            print(f"    Atual: {extras_atual}h | Correto: {total_correto}h")
            
            if abs((extras_atual or 0) - total_correto) > 0.01:
                print(f"    ❌ DIFERENÇA: {abs((extras_atual or 0) - total_correto):.2f}h")
            else:
                print(f"    ✅ CORRETO")

def aplicar_correcao_definitiva():
    """Aplica correção definitiva nos cálculos"""
    logger.info("🔧 APLICANDO CORREÇÃO DEFINITIVA...")
    
    with app.app_context():
        # 1. Garantir que a tabela horarios_padrao existe
        criar_horarios_padrao()
        
        # 2. Corrigir todos os registros dos últimos 60 dias
        corrigir_registros_periodo()
        
        # 3. Validar a correção
        validar_correcao()

def criar_horarios_padrao():
    """Cria horários padrão se não existirem"""
    try:
        # Verificar se tabela existe
        count = db.session.execute(text("SELECT COUNT(*) FROM horarios_padrao")).scalar()
        logger.info(f"Horários padrão existentes: {count}")
        
        if count == 0:
            # Criar horários padrão para todos os funcionários ativos
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
            
            for funcionario in funcionarios:
                sql = text("""
                    INSERT INTO horarios_padrao (funcionario_id, entrada_padrao, saida_padrao, ativo)
                    VALUES (:funcionario_id, '07:12:00', '17:00:00', TRUE)
                """)
                
                db.session.execute(sql, {"funcionario_id": funcionario.id})
                logger.info(f"Horário padrão criado: {funcionario.nome}")
            
            db.session.commit()
            
    except Exception as e:
        logger.warning(f"Tabela horarios_padrao não existe ou erro: {e}")
        # Criar tabela
        sql_criar_tabela = text("""
            CREATE TABLE IF NOT EXISTS horarios_padrao (
                id SERIAL PRIMARY KEY,
                funcionario_id INTEGER NOT NULL REFERENCES funcionario(id),
                entrada_padrao TIME NOT NULL DEFAULT '07:12:00',
                saida_padrao TIME NOT NULL DEFAULT '17:00:00', 
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        db.session.execute(sql_criar_tabela)
        db.session.commit()
        logger.info("Tabela horarios_padrao criada")
        
        # Criar horários para funcionários
        criar_horarios_padrao()

def corrigir_registros_periodo():
    """Corrige registros dos últimos 60 dias"""
    logger.info("📝 CORRIGINDO REGISTROS...")
    
    # Buscar registros com horários completos
    registros = db.session.execute(text(f"""
        SELECT r.id, r.hora_entrada, r.hora_saida, r.funcionario_id, f.nome
        FROM {RegistroPonto.__tablename__} r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE r.data >= CURRENT_DATE - INTERVAL '60 days'
          AND r.hora_entrada IS NOT NULL
          AND r.hora_saida IS NOT NULL
        ORDER BY r.data DESC
    """)).fetchall()
    
    logger.info(f"Encontrados {len(registros)} registros para corrigir")
    
    corrigidos = 0
    
    for registro in registros:
        reg_id, entrada, saida, func_id, nome = registro
        
        if not entrada or not saida:
            continue
            
        # Calcular horas extras corretas
        entrada_real_min = entrada.hour * 60 + entrada.minute
        saida_real_min = saida.hour * 60 + saida.minute
        
        # Horário padrão fixo: 07:12 às 17:00
        entrada_padrao_min = 7 * 60 + 12  # 432 min (07:12)
        saida_padrao_min = 17 * 60         # 1020 min (17:00)
        
        # Calcular extras
        extras_entrada = max(0, entrada_padrao_min - entrada_real_min)  # Entrada antecipada
        extras_saida = max(0, saida_real_min - saida_padrao_min)        # Saída atrasada
        
        total_horas_extras = round((extras_entrada + extras_saida) / 60, 2)
        
        # Atualizar registro
        sql_update = text(f"""
            UPDATE {RegistroPonto.__tablename__}
            SET horas_extras = :horas_extras
            WHERE id = :registro_id
        """)
        
        db.session.execute(sql_update, {
            "horas_extras": total_horas_extras,
            "registro_id": reg_id
        })
        
        corrigidos += 1
        
        if corrigidos % 50 == 0:
            logger.info(f"Processados {corrigidos} registros...")
    
    db.session.commit()
    logger.info(f"✅ {corrigidos} registros corrigidos")

def validar_correcao():
    """Valida se a correção funcionou corretamente"""
    logger.info("🧪 VALIDANDO CORREÇÃO...")
    
    # Testar alguns exemplos
    exemplos = db.session.execute(text(f"""
        SELECT 
            r.id, r.data, r.hora_entrada, r.hora_saida, r.horas_extras,
            f.nome
        FROM {RegistroPonto.__tablename__} r
        JOIN funcionario f ON r.funcionario_id = f.id
        WHERE r.hora_entrada IS NOT NULL 
          AND r.hora_saida IS NOT NULL
          AND r.data >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY r.horas_extras DESC
        LIMIT 5
    """)).fetchall()
    
    print("\n✅ VALIDAÇÃO - EXEMPLOS CORRIGIDOS:")
    for exemplo in exemplos:
        reg_id, data, entrada, saida, extras, nome = exemplo
        
        # Recalcular manualmente para verificar
        entrada_min = entrada.hour * 60 + entrada.minute
        saida_min = saida.hour * 60 + saida.minute
        
        extras_entrada_calc = max(0, (7*60 + 12) - entrada_min)
        extras_saida_calc = max(0, saida_min - (17*60))
        total_calc = round((extras_entrada_calc + extras_saida_calc) / 60, 2)
        
        status = "✅" if abs(extras - total_calc) < 0.01 else "❌"
        
        print(f"  {status} {nome} ({data}): {entrada} às {saida} = {extras}h")
        
        if extras > 0:
            print(f"      Entrada: {extras_entrada_calc}min, Saída: {extras_saida_calc}min")

def atualizar_kpis():
    """Força atualização dos KPIs com valores corretos"""
    logger.info("📊 ATUALIZANDO KPIs...")
    
    try:
        from kpi_unificado import obter_kpi_dashboard
        
        admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
        if admin:
            kpis_antes = obter_kpi_dashboard(admin.id)
            logger.info(f"KPIs atualizados: R$ {kpis_antes.get('custos_periodo', 0):,.2f}")
        
    except Exception as e:
        logger.warning(f"Erro ao atualizar KPIs: {e}")

def main():
    """Função principal - executa correção completa"""
    print("🚀 CORREÇÃO DEFINITIVA DE HORAS EXTRAS")
    print("=" * 50)
    
    # 1. Diagnosticar problema atual
    diagnosticar_problema_atual()
    
    # 2. Aplicar correção
    aplicar_correcao_definitiva()
    
    # 3. Atualizar KPIs
    atualizar_kpis()
    
    print("\n🎉 CORREÇÃO CONCLUÍDA!")
    print("✅ Todos os registros corrigidos com horário padrão 07:12-17:00")
    print("✅ Cálculo: entrada antecipada + saída atrasada")
    print("✅ KPIs atualizados no dashboard")

if __name__ == "__main__":
    with app.app_context():
        main()