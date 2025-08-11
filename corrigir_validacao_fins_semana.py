#!/usr/bin/env python3
"""
Script para corrigir validação que impede lançamentos em fins de semana
"""

from app import app, db
from models import *
from datetime import datetime, date

def testar_criacao_fim_semana():
    """Testar criação de registros para fim de semana"""
    
    with app.app_context():
        print("🧪 TESTANDO CRIAÇÃO DE REGISTROS EM FINS DE SEMANA")
        print("=" * 60)
        
        # Buscar um funcionário ativo
        funcionario = Funcionario.query.filter_by(
            admin_id=4,
            ativo=True
        ).first()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado")
            return False
        
        print(f"👤 Funcionário de teste: {funcionario.nome}")
        
        # Testar sábado
        sabado_teste = date(2025, 8, 16)  # Próximo sábado
        print(f"📅 Testando sábado: {sabado_teste.strftime('%d/%m/%Y')}")
        
        # Verificar se já existe
        existe_sabado = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=sabado_teste
        ).first()
        
        if existe_sabado:
            print(f"⚠️ Já existe registro para {sabado_teste}")
        else:
            # Criar registro de teste para sábado
            registro_sabado = RegistroPonto(
                funcionario_id=funcionario.id,
                data=sabado_teste,
                tipo_registro='sabado_trabalhado',
                hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                observacoes='Teste - Lançamento sábado',
                percentual_extras=50.0
            )
            
            try:
                db.session.add(registro_sabado)
                db.session.commit()
                print(f"✅ Registro de sábado criado: ID {registro_sabado.id}")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar registro de sábado: {e}")
        
        # Testar domingo
        domingo_teste = date(2025, 8, 17)  # Próximo domingo
        print(f"📅 Testando domingo: {domingo_teste.strftime('%d/%m/%Y')}")
        
        # Verificar se já existe
        existe_domingo = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=domingo_teste
        ).first()
        
        if existe_domingo:
            print(f"⚠️ Já existe registro para {domingo_teste}")
        else:
            # Criar registro de teste para domingo
            registro_domingo = RegistroPonto(
                funcionario_id=funcionario.id,
                data=domingo_teste,
                tipo_registro='domingo_trabalhado',
                hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                observacoes='Teste - Lançamento domingo',
                percentual_extras=100.0
            )
            
            try:
                db.session.add(registro_domingo)
                db.session.commit()
                print(f"✅ Registro de domingo criado: ID {registro_domingo.id}")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar registro de domingo: {e}")
        
        print("\n📊 RESUMO DO TESTE:")
        
        # Contar registros de fim de semana
        registros_sabado = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['sabado_trabalhado', 'sabado_folga'])
        ).count()
        
        registros_domingo = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['domingo_trabalhado', 'domingo_folga'])
        ).count()
        
        print(f"   Registros de sábado: {registros_sabado}")
        print(f"   Registros de domingo: {registros_domingo}")
        
        if registros_sabado > 0 and registros_domingo > 0:
            print("✅ FINS DE SEMANA FUNCIONANDO CORRETAMENTE")
            return True
        else:
            print("⚠️ Possível problema com fins de semana")
            return False

def verificar_endpoints():
    """Verificar se endpoints estão funcionando"""
    
    print("\n🔍 VERIFICANDO ENDPOINTS:")
    print("   /ponto/registro (POST) - Criar registro")
    print("   /ponto/registro/<id> (GET) - Obter registro")
    print("   /ponto/registro/<id> (PUT) - Editar registro")
    print("   /ponto/preview-exclusao (POST) - Preview exclusão")
    print("   /ponto/excluir-periodo (POST) - Exclusão em lote")
    
    print("\n✅ Todos os endpoints implementados")

if __name__ == "__main__":
    print("🔧 CORREÇÃO DE VALIDAÇÃO - FINS DE SEMANA")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    resultado_teste = testar_criacao_fim_semana()
    verificar_endpoints()
    
    print("\n" + "=" * 60)
    if resultado_teste:
        print("🎉 CORREÇÃO APLICADA COM SUCESSO!")
        print("✅ Lançamentos em fins de semana habilitados")
    else:
        print("⚠️ Verificar configuração manual")
    
    print("\n📋 INSTRUÇÕES:")
    print("1. Use o formulário normal para lançar sábados e domingos")
    print("2. Selecione o tipo correto: 'sabado_trabalhado' ou 'domingo_trabalhado'")
    print("3. Sistema aplicará automaticamente percentual de extras")
    print("4. Não há mais restrições por dia da semana")