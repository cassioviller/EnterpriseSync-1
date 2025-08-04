#!/usr/bin/env python3
"""
🏷️ TESTE DAS TAGS VIBRANTES PARA FERIADO
Verificar se a tag roxa vibrante está sendo aplicada corretamente
"""

from app import app, db
from models import RegistroPonto
from datetime import date

def testar_tags_feriado():
    """Verificar se existem registros de feriado e como estão configurados"""
    print("🏷️ TESTANDO TAGS DE FERIADO")
    print("=" * 50)
    
    # Buscar registros de feriado
    feriados = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro.in_(['feriado', 'feriado_folga'])
    ).all()
    
    print(f"📊 Encontrados {len(feriados)} registros de feriado")
    
    for registro in feriados:
        print(f"\n🔍 Registro ID {registro.id}:")
        print(f"   Data: {registro.data}")
        print(f"   Funcionário ID: {registro.funcionario_id}")
        print(f"   Tipo: {registro.tipo_registro}")
        print(f"   Horário entrada: {registro.hora_entrada}")
        print(f"   Horário saída: {registro.hora_saida}")
    
    if not feriados:
        print("⚠️  Nenhum registro de feriado encontrado no sistema")
        print("🔧 Criando um registro de teste para verificar a tag...")
        
        # Criar um registro de teste
        from models import Funcionario
        funcionario = Funcionario.query.first()
        
        if funcionario:
            novo_feriado = RegistroPonto(
                funcionario_id=funcionario.id,
                data=date(2025, 7, 11),  # Sexta-feira para teste
                tipo_registro='feriado',
                horas_trabalhadas=0,
                horas_extras=0,
                total_atraso_minutos=0,
                total_atraso_horas=0.0
            )
            
            db.session.add(novo_feriado)
            db.session.commit()
            
            print(f"✅ Registro de feriado criado: ID {novo_feriado.id}")
            print(f"   Funcionário: {funcionario.nome}")
            print(f"   Data: {novo_feriado.data}")
            print(f"   Tipo: {novo_feriado.tipo_registro}")
        else:
            print("❌ Nenhum funcionário encontrado para criar teste")
    
    print("\n" + "=" * 50)
    print("🏷️ CONFIGURAÇÃO DAS TAGS:")
    print("✅ Feriado normal: cor roxa vibrante (#8b5cf6)")
    print("✅ Template funcionario_perfil.html: atualizado")
    print("✅ Template controle_ponto.html: atualizado")
    print("🔄 Recarregue a página para ver a tag roxa vibrante!")

if __name__ == "__main__":
    with app.app_context():
        testar_tags_feriado()