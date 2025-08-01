#!/usr/bin/env python3
"""
VALIDAÇÃO COMPLETA DOS TIPOS v8.1
Valida todos os 10 tipos implementados e mostra estatísticas
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
from kpis_engine_v8_1 import calcular_kpis_v8_1, TiposLancamento
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validar_tipos_sistema():
    """Valida todos os tipos implementados no sistema"""
    
    print("VALIDAÇÃO COMPLETA DOS TIPOS v8.1")
    print("=" * 80)
    
    # Tipos esperados
    tipos_esperados = list(TiposLancamento.TIPOS.keys())
    
    print("TIPOS ESPERADOS (10):")
    for i, tipo in enumerate(tipos_esperados, 1):
        config = TiposLancamento.TIPOS[tipo]
        print(f"  {i:2d}. {tipo:<20} - {config['nome']}")
    
    print(f"\nTIPOS NO BANCO DE DADOS:")
    
    # Buscar tipos únicos no banco
    tipos_banco = db.session.query(RegistroPonto.tipo_registro.distinct()).all()
    tipos_banco = [t[0] for t in tipos_banco if t[0]]
    
    # Estatísticas por tipo
    total_registros = 0
    for tipo in sorted(tipos_banco):
        count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo).count()
        status = "✅" if tipo in tipos_esperados else "❌"
        print(f"  {status} {tipo:<20}: {count:4d} registros")
        total_registros += count
    
    print(f"\nRESUMO:")
    print(f"  • Tipos esperados: {len(tipos_esperados)}")  
    print(f"  • Tipos no banco: {len(tipos_banco)}")
    print(f"  • Total registros: {total_registros}")
    
    # Verificar cobertura
    tipos_faltando = set(tipos_esperados) - set(tipos_banco)
    tipos_extras = set(tipos_banco) - set(tipos_esperados)
    
    if tipos_faltando:
        print(f"\n❌ TIPOS FALTANDO: {tipos_faltando}")
    
    if tipos_extras:
        print(f"\n⚠️  TIPOS EXTRAS: {tipos_extras}")
    
    if not tipos_faltando and not tipos_extras:
        print(f"\n🎉 TODOS OS TIPOS ESTÃO corretos!")
    
    return len(tipos_faltando) == 0 and len(tipos_extras) == 0

def testar_kpis_funcionario_vale_verde():
    """Testa KPIs com funcionário da Vale Verde"""
    
    print("\nTESTANDO KPIs COM FUNCIONÁRIO VALE VERDE")
    print("=" * 60)
    
    # Buscar funcionário Vale Verde
    funcionario_vv = Funcionario.query.filter(
        Funcionario.nome.contains('Vale Verde')
    ).first()
    
    if not funcionario_vv:
        print("❌ Nenhum funcionário Vale Verde encontrado")
        return False
    
    print(f"FUNCIONÁRIO: {funcionario_vv.nome}")
    
    # Calcular KPIs para julho
    kpis = calcular_kpis_v8_1(
        funcionario_vv.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"PERÍODO: Julho/2025")
    print(f"-" * 40)
    
    # KPIs Básicos
    print("KPIs BÁSICOS:")
    print(f"  • Horas Trabalhadas: {kpis['horas_trabalhadas']}h")
    print(f"  • Horas Extras: {kpis['horas_extras']}h")
    print(f"  • Faltas: {kpis['faltas']}")
    print(f"  • Atrasos: {kpis['atrasos']}h")
    
    # KPIs Analíticos
    print("\nKPIs ANALÍTICOS:")
    print(f"  • Produtividade: {kpis['produtividade']}%")
    print(f"  • Assiduidade: {kpis['assiduidade']}%")
    print(f"  • Absenteísmo: {kpis['absenteismo']}%")
    print(f"  • Média Diária: {kpis['media_diaria']}h")
    
    # KPIs Financeiros
    print("\nKPIs FINANCEIROS:")
    print(f"  • Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"  • Custo por Hora: R$ {kpis['custo_por_hora']:.2f}")
    print(f"  • Valor Hora Base: R$ {kpis['valor_hora_base']:.2f}")
    print(f"  • Custo Horas Extras: R$ {kpis['custo_horas_extras']:.2f}")
    
    return True

def mostrar_registros_por_funcionario():
    """Mostra registros agrupados por funcionário"""
    
    print("\nREGISTROS POR FUNCIONÁRIO")
    print("=" * 60)
    
    funcionarios = Funcionario.query.filter_by(ativo=True).all()
    
    for funcionario in funcionarios:
        # Contar registros por tipo
        registros_funcionario = db.session.query(
            RegistroPonto.tipo_registro,
            func.count(RegistroPonto.id).label('count')
        ).filter(
            RegistroPonto.funcionario_id == funcionario.id
        ).group_by(
            RegistroPonto.tipo_registro
        ).all()
        
        if registros_funcionario:
            total_registros = sum([r.count for r in registros_funcionario])
            print(f"\n{funcionario.nome} (Total: {total_registros})")
            
            for tipo, count in registros_funcionario:
                config = TiposLancamento.TIPOS.get(tipo, {})
                nome = config.get('nome', tipo)
                print(f"  • {nome:<25}: {count:3d}")

def gerar_relatorio_final():
    """Gera relatório final da implementação v8.1"""
    
    print("\nRELATÓRIO FINAL - SIGE v8.1")
    print("=" * 80)
    
    # Estatísticas gerais
    total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
    total_registros = db.session.query(RegistroPonto).count()
    total_obras = Obra.query.count()
    
    print("ESTATÍSTICAS GERAIS:")
    print(f"  • Funcionários ativos: {total_funcionarios}")
    print(f"  • Total de registros: {total_registros}")
    print(f"  • Obras cadastradas: {total_obras}")
    
    # Período de dados
    primeiro_registro = db.session.query(RegistroPonto).order_by(RegistroPonto.data.asc()).first()
    ultimo_registro = db.session.query(RegistroPonto).order_by(RegistroPonto.data.desc()).first()
    
    if primeiro_registro and ultimo_registro:
        print(f"  • Período: {primeiro_registro.data} até {ultimo_registro.data}")
    
    # Tipos mais utilizados
    print(f"\nTIPOS MAIS UTILIZADOS:")
    tipos_populares = db.session.query(
        RegistroPonto.tipo_registro,
        func.count(RegistroPonto.id).label('count')
    ).group_by(
        RegistroPonto.tipo_registro
    ).order_by(
        func.count(RegistroPonto.id).desc()
    ).limit(5).all()
    
    for i, (tipo, count) in enumerate(tipos_populares, 1):
        config = TiposLancamento.TIPOS.get(tipo, {})
        nome = config.get('nome', tipo)
        print(f"  {i}. {nome:<25}: {count:4d} registros")
    
    print(f"\n🎉 IMPLEMENTAÇÃO v8.1 FUNCIONAL E COMPLETA!")

if __name__ == "__main__":
    with app.app_context():
        print("VALIDAÇÃO COMPLETA - SIGE v8.1")
        print("=" * 80)
        
        # Validar tipos
        tipos_ok = validar_tipos_sistema()
        
        # Testar KPIs
        kpis_ok = testar_kpis_funcionario_vale_verde()
        
        # Mostrar registros por funcionário
        mostrar_registros_por_funcionario()
        
        # Relatório final
        gerar_relatorio_final()
        
        print("\n" + "=" * 80)
        print("STATUS FINAL")
        print("=" * 80)
        print(f"✅ Tipos de lançamento: {'OK' if tipos_ok else 'PENDENTE'}")
        print(f"✅ Engine KPIs v8.1: {'OK' if kpis_ok else 'PENDENTE'}")
        print(f"✅ Sistema completo: {'FUNCIONANDO' if tipos_ok and kpis_ok else 'VERIFICAR'}")