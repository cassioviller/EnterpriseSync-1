#!/usr/bin/env python3
"""
MIGRAÇÃO PARA TIPOS v8.1 - Padronização e Novos Tipos
Migra tipos existentes e adiciona novos tipos de lançamento
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
from sqlalchemy import func
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrar_tipos_existentes():
    """Migra tipos existentes para o padrão v8.1"""
    
    # Mapear tipos antigos para novos
    mapeamento_tipos = {
        # Tipos de trabalho
        'trabalhado': 'trabalho_normal',
        'trabalho_normal': 'trabalho_normal',
        'presente': 'trabalho_normal',
        'normal': 'trabalho_normal',
        
        # Tipos de extras
        'sabado_horas_extras': 'sabado_trabalhado',
        'sabado_trabalhado': 'sabado_trabalhado',
        'domingo_horas_extras': 'domingo_trabalhado',
        'domingo_trabalhado': 'domingo_trabalhado',
        'feriado_trabalhado': 'feriado_trabalhado',
        
        # Tipos de ausência
        'falta': 'falta',
        'falta_injustificada': 'falta',
        'falta_justificada': 'falta_justificada',
        'atestado': 'falta_justificada',
        'atestado_medico': 'falta_justificada',
        
        # Meio período
        'meio_periodo': 'trabalho_normal',  # Será diferenciado pelas horas
        
        # Tipos inválidos encontrados - migrar para folgas
        'sabado_nao_trabalhado': 'sabado_folga',
        'domingo_nao_trabalhado': 'domingo_folga',
        'feriado': 'feriado_folga'
    }
    
    registros_atualizados = 0
    print("MIGRANDO TIPOS EXISTENTES...")
    print("-" * 50)
    
    for tipo_antigo, tipo_novo in mapeamento_tipos.items():
        # Contar registros
        count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo_antigo).count()
        
        if count > 0:
            # Atualizar registros
            db.session.query(RegistroPonto).filter_by(tipo_registro=tipo_antigo).update({
                'tipo_registro': tipo_novo
            })
            
            registros_atualizados += count
            print(f"  • {tipo_antigo} → {tipo_novo}: {count} registros")
    
    db.session.commit()
    print(f"\n✅ Total migrado: {registros_atualizados} registros")
    
    return registros_atualizados

def criar_registros_folga_automaticos():
    """Cria registros automáticos para sábados/domingos não trabalhados"""
    
    print("\nCRIANDO REGISTROS DE FOLGA AUTOMÁTICOS...")
    print("-" * 50)
    
    # Buscar funcionários ativos
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    
    # Período para criar folgas (último mês)
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    registros_criados = 0
    
    for funcionario in funcionarios:
        # Percorrer cada dia do período
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            # Verificar se é sábado ou domingo
            dia_semana = data_atual.weekday()  # 0=Segunda, 6=Domingo
            
            if dia_semana in [5, 6]:  # Sábado=5, Domingo=6
                # Verificar se já existe registro para o dia
                registro_existente = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == funcionario.id,
                    RegistroPonto.data == data_atual
                ).first()
                
                if not registro_existente:
                    # Determinar tipo de folga
                    if dia_semana == 5:  # Sábado
                        tipo_folga = 'sabado_folga'
                    else:  # Domingo
                        tipo_folga = 'domingo_folga'
                    
                    # Criar registro de folga
                    registro_folga = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo_registro=tipo_folga,
                        horas_trabalhadas=0,
                        observacoes='Folga automática - gerada pelo sistema'
                    )
                    
                    db.session.add(registro_folga)
                    registros_criados += 1
            
            data_atual += timedelta(days=1)
    
    db.session.commit()
    print(f"✅ Registros de folga criados: {registros_criados}")
    
    return registros_criados

def validar_tipos_v8_1():
    """Valida se todos os tipos estão corretos no padrão v8.1"""
    
    print("\nVALIDANDO TIPOS v8.1...")
    print("-" * 50)
    
    # Tipos válidos v8.1
    tipos_validos = [
        'trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado',
        'falta', 'falta_justificada', 'ferias',
        'sabado_folga', 'domingo_folga', 'feriado_folga'
    ]
    
    # Buscar tipos únicos no banco
    tipos_banco = db.session.query(RegistroPonto.tipo_registro.distinct()).all()
    tipos_banco = [t[0] for t in tipos_banco if t[0]]  # Extrair valores não nulos
    
    print(f"Tipos encontrados no banco: {len(tipos_banco)}")
    
    tipos_invalidos = []
    for tipo in tipos_banco:
        if tipo not in tipos_validos:
            tipos_invalidos.append(tipo)
    
    if tipos_invalidos:
        print(f"❌ Tipos inválidos encontrados: {tipos_invalidos}")
        
        # Contar registros por tipo inválido
        for tipo in tipos_invalidos:
            count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo).count()
            print(f"  • {tipo}: {count} registros")
    else:
        print("✅ Todos os tipos estão no padrão v8.1")
    
    # Estatísticas finais
    print(f"\nESTATÍSTICAS FINAIS:")
    for tipo in tipos_validos:
        count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo).count()
        if count > 0:
            print(f"  • {tipo}: {count} registros")
    
    return len(tipos_invalidos) == 0

def aplicar_migracao_completa():
    """Aplica migração completa para v8.1"""
    
    print("=" * 80)
    print("MIGRAÇÃO COMPLETA PARA SIGE v8.1")
    print("=" * 80)
    
    # Etapa 1: Migrar tipos existentes
    registros_migrados = migrar_tipos_existentes()
    
    # Etapa 2: Criar registros de folga automáticos
    folgas_criadas = criar_registros_folga_automaticos()
    
    # Etapa 3: Validar resultado
    tipos_validos = validar_tipos_v8_1()
    
    # Resumo final
    print("\n" + "=" * 80)
    print("RESUMO DA MIGRAÇÃO")
    print("=" * 80)
    print(f"✅ Registros migrados: {registros_migrados}")
    print(f"✅ Folgas criadas: {folgas_criadas}")
    print(f"✅ Tipos válidos: {'SIM' if tipos_validos else 'NÃO'}")
    
    # Total de registros
    total_registros = db.session.query(RegistroPonto).count()
    print(f"📊 Total de registros: {total_registros}")
    
    if tipos_validos:
        print("\n🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Sistema está pronto para usar engine v8.1")
    else:
        print("\n⚠️  MIGRAÇÃO INCOMPLETA")
        print("Ainda existem tipos inválidos no sistema")

if __name__ == "__main__":
    with app.app_context():
        aplicar_migracao_completa()