#!/usr/bin/env python3
"""
VALIDAR FUNCIONÁRIO COM HORÁRIO PERSONALIZADO
Verificar se os cálculos estão corretos para horário 9h-16h
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioTrabalho
from datetime import time

def validar_funcionario_personalizado():
    """Valida os cálculos do funcionário com horário 9h-16h"""
    
    with app.app_context():
        print("🔍 VALIDAÇÃO DO FUNCIONÁRIO COM HORÁRIO PERSONALIZADO")
        print("=" * 60)
        
        # Buscar funcionário de teste
        funcionario = Funcionario.query.filter_by(nome="Carlos Silva Teste").first()
        if not funcionario:
            print("❌ Funcionário de teste não encontrado!")
            return
        
        print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
        
        # Verificar horário de trabalho
        if funcionario.horario_trabalho_id:
            horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
            if horario:
                print(f"🕘 Horário: {horario.entrada} - {horario.saida} ({horario.nome})")
        else:
            print("⚠️  Funcionário sem horário específico definido")
        
        # Buscar registros
        registros = RegistroPonto.query.filter_by(funcionario_id=funcionario.id).order_by(RegistroPonto.data).all()
        
        print(f"\n📊 ANÁLISE DE {len(registros)} REGISTROS:")
        print("=" * 60)
        
        # Casos para validação manual
        casos_teste = [
            {"entrada": time(9, 0), "saida": time(16, 0), "extras_esperado": 0.0, "atrasos_esperado": 0.0, "desc": "Horário exato"},
            {"entrada": time(8, 45), "saida": time(16, 0), "extras_esperado": 0.25, "atrasos_esperado": 0.0, "desc": "15min antes"},
            {"entrada": time(9, 15), "saida": time(16, 0), "extras_esperado": 0.0, "atrasos_esperado": 0.25, "desc": "15min atraso"},
            {"entrada": time(9, 0), "saida": time(16, 30), "extras_esperado": 0.5, "atrasos_esperado": 0.0, "desc": "30min extras"},
            {"entrada": time(8, 50), "saida": time(16, 45), "extras_esperado": 0.92, "atrasos_esperado": 0.0, "desc": "10min antes + 45min extras"},
            {"entrada": time(9, 30), "saida": time(16, 0), "extras_esperado": 0.0, "atrasos_esperado": 0.5, "desc": "30min atraso"},
            {"entrada": time(9, 45), "saida": time(15, 30), "extras_esperado": 0.0, "atrasos_esperado": 1.25, "desc": "45min atraso + 30min saída antes"},
        ]
        
        validacoes_corretas = 0
        validacoes_total = 0
        
        for caso in casos_teste:
            # Buscar registro correspondente
            registro = None
            for r in registros:
                if (r.hora_entrada == caso["entrada"] and 
                    r.hora_saida == caso["saida"] and
                    r.tipo_registro == "trabalho_normal"):
                    registro = r
                    break
            
            if registro:
                extras_real = registro.horas_extras or 0
                atrasos_real = registro.total_atraso_horas or 0
                
                extras_ok = abs(extras_real - caso["extras_esperado"]) < 0.05
                atrasos_ok = abs(atrasos_real - caso["atrasos_esperado"]) < 0.05
                
                status = "✅" if (extras_ok and atrasos_ok) else "❌"
                print(f"{status} {caso['desc']}")
                print(f"    {registro.hora_entrada}-{registro.hora_saida}")
                print(f"    Extras: {extras_real}h (esperado: {caso['extras_esperado']}h) {'✅' if extras_ok else '❌'}")
                print(f"    Atrasos: {atrasos_real}h (esperado: {caso['atrasos_esperado']}h) {'✅' if atrasos_ok else '❌'}")
                print()
                
                if extras_ok and atrasos_ok:
                    validacoes_corretas += 1
                validacoes_total += 1
        
        # Mostrar todos os registros
        print("📋 TODOS OS REGISTROS:")
        print("-" * 60)
        
        for registro in registros:
            if registro.hora_entrada and registro.hora_saida:
                print(f"📅 {registro.data.strftime('%d/%m/%Y')} | "
                      f"{registro.hora_entrada}-{registro.hora_saida} | "
                      f"Tipo: {registro.tipo_registro} | "
                      f"Trabalhadas: {registro.horas_trabalhadas}h | "
                      f"Extras: {registro.horas_extras or 0}h | "
                      f"Atrasos: {registro.total_atraso_horas or 0}h")
            else:
                print(f"📅 {registro.data.strftime('%d/%m/%Y')} | "
                      f"Tipo: {registro.tipo_registro} | "
                      f"Sem horários (falta/folga/férias)")
        
        # Resumo final
        print(f"\n🎯 RESUMO DA VALIDAÇÃO:")
        print(f"   Casos testados: {validacoes_total}")
        print(f"   Casos corretos: {validacoes_corretas}")
        print(f"   Taxa de acerto: {(validacoes_corretas/validacoes_total*100):.1f}%" if validacoes_total > 0 else "N/A")
        
        if validacoes_corretas == validacoes_total:
            print(f"   ✅ TODOS OS CÁLCULOS ESTÃO CORRETOS!")
        else:
            print(f"   ⚠️  {validacoes_total - validacoes_corretas} casos precisam de correção")
        
        # Estatísticas gerais
        total_extras = sum(r.horas_extras or 0 for r in registros)
        total_atrasos = sum(r.total_atraso_horas or 0 for r in registros)
        dias_com_extras = len([r for r in registros if (r.horas_extras or 0) > 0])
        dias_com_atrasos = len([r for r in registros if (r.total_atraso_horas or 0) > 0])
        
        print(f"\n📈 ESTATÍSTICAS GERAIS:")
        print(f"   Total horas extras: {total_extras}h")
        print(f"   Total horas atrasos: {total_atrasos}h") 
        print(f"   Dias com extras: {dias_com_extras}")
        print(f"   Dias com atrasos: {dias_com_atrasos}")

if __name__ == "__main__":
    validar_funcionario_personalizado()