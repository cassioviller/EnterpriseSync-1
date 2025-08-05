#!/usr/bin/env python3
"""
🎯 APLICAR NOVA LÓGICA: Entrada Antecipada + Saída Posterior = Horas Extras
EXEMPLO: 07:07-17:29 vs 07:12-17:00 = 5min + 29min = 34min extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import datetime, time

def aplicar_nova_logica_completa():
    with app.app_context():
        print("🎯 APLICAÇÃO: Nova Lógica Completa de Horas Extras")
        print("=" * 60)
        
        # Buscar funcionário com horário Comercial Vale Verde
        funcionario = Funcionario.query.join(
            Funcionario.horario_trabalho
        ).filter(
            Funcionario.horario_trabalho.has(nome='Comercial Vale Verde')
        ).first()
        
        if not funcionario:
            print("❌ Funcionário com horário Comercial Vale Verde não encontrado")
            return
            
        print(f"📋 FUNCIONÁRIO ENCONTRADO:")
        print(f"   • Nome: {funcionario.nome}")
        print(f"   • Horário: {funcionario.horario_trabalho.nome}")
        print(f"   • Padrão: {funcionario.horario_trabalho.entrada}-{funcionario.horario_trabalho.saida}")
        
        # Criar exemplo prático com entrada antecipada
        data_teste = datetime(2025, 7, 31).date()
        
        # Verificar se já existe
        registro_existente = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data == data_teste
        ).first()
        
        if registro_existente:
            db.session.delete(registro_existente)
            db.session.commit()
        
        # Criar novo registro: 07:07-17:29 (entrada antecipada + saída posterior)
        novo_registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=data_teste,
            hora_entrada=time(7, 7),      # 5min antes de 07:12
            hora_saida=time(17, 29),      # 29min depois de 17:00
            hora_almoco_saida=time(12, 0),
            hora_almoco_retorno=time(13, 0),
            tipo_registro='trabalhado',
            obra_id=12
        )
        
        db.session.add(novo_registro)
        db.session.commit()
        
        print(f"\n✅ REGISTRO CRIADO:")
        print(f"   • Data: {data_teste}")
        print(f"   • Entrada: 07:07 (5min antes de 07:12)")
        print(f"   • Saída: 17:29 (29min depois de 17:00)")
        print(f"   • Extras esperados: 5 + 29 = 34min = 0.57h")
        
        # Aplicar nova lógica
        engine = KPIsEngine()
        engine.calcular_e_atualizar_ponto(novo_registro.id)
        
        # Recarregar
        db.session.refresh(novo_registro)
        
        print(f"\n📊 RESULTADO DA NOVA LÓGICA:")
        print(f"   • Horas extras: {novo_registro.horas_extras}h")
        print(f"   • Em minutos: {novo_registro.horas_extras * 60:.0f} min")
        print(f"   • Percentual: {novo_registro.percentual_extras}%")
        print(f"   • Horas trabalhadas: {novo_registro.horas_trabalhadas}h")
        
        # VALIDAÇÃO
        esperado_min = 5 + 29  # 34 minutos
        esperado_h = esperado_min / 60.0  # 0.567 horas
        calculado_min = novo_registro.horas_extras * 60
        
        diferenca = abs(calculado_min - esperado_min)
        correto = diferenca <= 1  # Tolerância de 1 minuto
        
        print(f"\n🎯 VALIDAÇÃO:")
        print(f"   • Esperado: {esperado_min} min ({esperado_h:.2f}h)")
        print(f"   • Calculado: {calculado_min:.0f} min ({novo_registro.horas_extras:.2f}h)")
        print(f"   • Diferença: {diferenca:.0f} min")
        print(f"   • Status: {'✅' if correto else '❌'}")
        
        return novo_registro.id

if __name__ == "__main__":
    aplicar_nova_logica_completa()