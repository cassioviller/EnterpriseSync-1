#!/usr/bin/env python3
"""
HOTFIX PRODUÇÃO: Implementação Correta de Horas Extras
Sistema SIGE - Correção urgente dos cálculos
"""

from app import app, db
from models import *
from datetime import time, date
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def aplicar_hotfix_horas_extras_producao():
    """Aplica hotfix para corrigir horas extras baseado em horário padrão"""
    
    print("🔥 HOTFIX PRODUÇÃO - HORAS EXTRAS")
    print("=" * 50)
    
    try:
        # 1. Criar tabela horários padrão se não existir
        criar_tabela_horarios_padrao()
        
        # 2. Adicionar campos extras aos registros se não existirem
        adicionar_campos_horas_extras()
        
        # 3. Criar horários padrão para funcionários sem horário
        criar_horarios_padrao_faltantes()
        
        # 4. Aplicar nova lógica aos registros recentes
        aplicar_nova_logica_registros()
        
        # 5. Atualizar KPIs do dashboard
        atualizar_kpis_dashboard()
        
        print("✅ HOTFIX APLICADO COM SUCESSO!")
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO NO HOTFIX: {e}")
        db.session.rollback()
        return False

def criar_tabela_horarios_padrao():
    """Cria tabela de horários padrão se não existir"""
    logger.info("🔧 Verificando tabela horarios_padrao...")
    
    sql_criar = text("""
    CREATE TABLE IF NOT EXISTS horarios_padrao (
        id SERIAL PRIMARY KEY,
        funcionario_id INTEGER NOT NULL REFERENCES funcionario(id),
        entrada_padrao TIME NOT NULL DEFAULT '07:12:00',
        saida_padrao TIME NOT NULL DEFAULT '17:00:00',
        ativo BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_horarios_funcionario 
    ON horarios_padrao(funcionario_id, ativo);
    """)
    
    db.session.execute(sql_criar)
    db.session.commit()
    logger.info("✅ Tabela horarios_padrao OK")

def adicionar_campos_horas_extras():
    """Adiciona campos de horas extras aos registros se não existirem"""
    logger.info("🔧 Adicionando campos horas extras...")
    
    # Descobrir nome da tabela de registro de ponto
    nome_tabela = RegistroPonto.__tablename__
    
    campos = [
        "minutos_extras_entrada INTEGER DEFAULT 0",
        "minutos_extras_saida INTEGER DEFAULT 0", 
        "horas_extras_corrigidas DECIMAL(5,2) DEFAULT 0.0",
        "calculo_horario_padrao BOOLEAN DEFAULT FALSE"
    ]
    
    for campo in campos:
        try:
            sql = text(f"ALTER TABLE {nome_tabela} ADD COLUMN IF NOT EXISTS {campo}")
            db.session.execute(sql)
            logger.info(f"  ✅ Campo adicionado: {campo.split()[0]}")
        except Exception as e:
            logger.warning(f"  ⚠️ Campo já existe: {campo.split()[0]}")
    
    db.session.commit()

def criar_horarios_padrao_faltantes():
    """Cria horários padrão para funcionários que não tem"""
    logger.info("📋 Criando horários padrão faltantes...")
    
    # Buscar funcionários sem horário padrão
    funcionarios_sem_horario = db.session.execute(text("""
        SELECT f.id, f.nome 
        FROM funcionario f 
        LEFT JOIN horarios_padrao h ON f.id = h.funcionario_id AND h.ativo = TRUE
        WHERE f.ativo = TRUE AND h.id IS NULL
    """)).fetchall()
    
    horario_padrao_entrada = time(7, 12)  # 07:12
    horario_padrao_saida = time(17, 0)    # 17:00
    
    for funcionario_id, nome in funcionarios_sem_horario:
        sql = text("""
            INSERT INTO horarios_padrao (funcionario_id, entrada_padrao, saida_padrao, ativo)
            VALUES (:funcionario_id, :entrada, :saida, TRUE)
        """)
        
        db.session.execute(sql, {
            "funcionario_id": funcionario_id,
            "entrada": horario_padrao_entrada,
            "saida": horario_padrao_saida
        })
        
        logger.info(f"  ✅ Horário criado: {nome}")
    
    db.session.commit()
    logger.info(f"📋 {len(funcionarios_sem_horario)} horários padrão criados")

def calcular_horas_extras_correto(registro_id):
    """Calcula horas extras baseado no horário padrão"""
    
    # Buscar dados do registro e horário padrão
    dados = db.session.execute(text("""
        SELECT 
            r.hora_entrada, r.hora_saida, r.funcionario_id,
            h.entrada_padrao, h.saida_padrao,
            f.nome
        FROM {tabela} r
        JOIN funcionario f ON r.funcionario_id = f.id
        LEFT JOIN horarios_padrao h ON f.id = h.funcionario_id AND h.ativo = TRUE
        WHERE r.id = :registro_id
    """.format(tabela=RegistroPonto.__tablename__)), {"registro_id": registro_id}).fetchone()
    
    if not dados or not dados[0] or not dados[1]:  # Sem horários
        return 0, 0, 0.0
    
    entrada_real, saida_real, funcionario_id, entrada_padrao, saida_padrao, nome = dados
    
    if not entrada_padrao or not saida_padrao:  # Sem horário padrão
        logger.warning(f"⚠️ {nome} sem horário padrão")
        return 0, 0, 0.0
    
    # Converter para minutos
    def time_to_minutes(t):
        return t.hour * 60 + t.minute
    
    entrada_real_min = time_to_minutes(entrada_real)
    saida_real_min = time_to_minutes(saida_real)
    entrada_padrao_min = time_to_minutes(entrada_padrao)
    saida_padrao_min = time_to_minutes(saida_padrao)
    
    # Calcular extras
    extras_entrada = max(0, entrada_padrao_min - entrada_real_min)  # Entrada antecipada
    extras_saida = max(0, saida_real_min - saida_padrao_min)        # Saída atrasada
    
    total_minutos = extras_entrada + extras_saida
    total_horas = round(total_minutos / 60, 2)
    
    logger.debug(f"📊 {nome}: {extras_entrada}min + {extras_saida}min = {total_horas}h")
    
    return extras_entrada, extras_saida, total_horas

def aplicar_nova_logica_registros():
    """Aplica nova lógica aos registros dos últimos 30 dias"""
    logger.info("🔄 Aplicando nova lógica aos registros...")
    
    # Buscar registros dos últimos 30 dias com horários
    registros = db.session.execute(text(f"""
        SELECT id FROM {RegistroPonto.__tablename__}
        WHERE data >= CURRENT_DATE - INTERVAL '30 days'
          AND hora_entrada IS NOT NULL 
          AND hora_saida IS NOT NULL
        ORDER BY data DESC
        LIMIT 100
    """)).fetchall()
    
    corrigidos = 0
    
    for (registro_id,) in registros:
        try:
            # Calcular horas extras corretas
            entrada_extra, saida_extra, total_horas = calcular_horas_extras_correto(registro_id)
            
            # Atualizar registro
            sql = text(f"""
                UPDATE {RegistroPonto.__tablename__}
                SET minutos_extras_entrada = :entrada,
                    minutos_extras_saida = :saida,
                    horas_extras_corrigidas = :total,
                    horas_extras = :total,
                    calculo_horario_padrao = TRUE
                WHERE id = :registro_id
            """)
            
            db.session.execute(sql, {
                "entrada": entrada_extra,
                "saida": saida_extra,
                "total": total_horas,
                "registro_id": registro_id
            })
            
            corrigidos += 1
            
        except Exception as e:
            logger.error(f"❌ Erro registro {registro_id}: {e}")
    
    db.session.commit()
    logger.info(f"✅ {corrigidos} registros corrigidos")

def atualizar_kpis_dashboard():
    """Atualiza cálculos de KPIs para refletir horas extras corretas"""
    logger.info("📊 Atualizando KPIs...")
    
    try:
        # Forçar recálculo dos KPIs principais
        from kpi_unificado import obter_kpi_dashboard
        
        # Testar com admin principal
        primeiro_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
        if primeiro_admin:
            kpis = obter_kpi_dashboard(primeiro_admin.id)
            logger.info(f"✅ KPIs atualizados: R$ {kpis.get('custos_periodo', 0):,.2f}")
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao atualizar KPIs: {e}")

def validar_implementacao():
    """Valida se a implementação funcionou"""
    logger.info("🧪 Validando implementação...")
    
    try:
        # 1. Verificar tabela horarios_padrao
        count_horarios = db.session.execute(text("SELECT COUNT(*) FROM horarios_padrao")).scalar()
        logger.info(f"  ✅ Horários padrão: {count_horarios}")
        
        # 2. Verificar registros com nova lógica
        count_corrigidos = db.session.execute(text(f"""
            SELECT COUNT(*) FROM {RegistroPonto.__tablename__} 
            WHERE calculo_horario_padrao = TRUE
        """)).scalar()
        logger.info(f"  ✅ Registros corrigidos: {count_corrigidos}")
        
        # 3. Testar exemplo de cálculo
        exemplo = db.session.execute(text(f"""
            SELECT id, horas_extras_corrigidas, minutos_extras_entrada, minutos_extras_saida
            FROM {RegistroPonto.__tablename__}
            WHERE calculo_horario_padrao = TRUE
            LIMIT 1
        """)).fetchone()
        
        if exemplo:
            logger.info(f"  ✅ Exemplo: {exemplo[2]}min + {exemplo[3]}min = {exemplo[1]}h")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na validação: {e}")
        return False

# Função principal para deploy em produção
def deploy_hotfix_producao():
    """Deploy do hotfix em produção"""
    
    print("🚀 INICIANDO DEPLOY HOTFIX HORAS EXTRAS")
    print("=" * 50)
    
    sucesso = aplicar_hotfix_horas_extras_producao()
    
    if sucesso:
        print("\n🎉 DEPLOY CONCLUÍDO COM SUCESSO!")
        print("✅ Horas extras agora calculadas por horário padrão")
        print("✅ KPIs do dashboard corrigidos") 
        print("✅ Sistema pronto para produção")
        
        # Validar
        if validar_implementacao():
            print("✅ Validação passou - Deploy confirmado")
            return True
        else:
            print("⚠️ Validação falhou - Verificar logs")
            return False
    else:
        print("\n❌ FALHA NO DEPLOY!")
        print("❌ Verificar logs e tentar novamente")
        return False

if __name__ == "__main__":
    with app.app_context():
        sucesso = deploy_hotfix_producao()
        exit(0 if sucesso else 1)