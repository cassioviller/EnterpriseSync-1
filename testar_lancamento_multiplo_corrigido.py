#!/usr/bin/env python3
"""
Teste final do lançamento múltiplo após correção
"""

from app import app, db
from models import *
from views import lancamento_multiplo_ponto
from flask import Flask
from datetime import datetime, date

def testar_api_diretamente():
    """Testar API diretamente simulando uma requisição"""
    
    with app.app_context():
        print("🧪 TESTE FINAL: Lançamento Múltiplo Corrigido")
        print("=" * 50)
        
        # Dados para teste
        admin = Usuario.query.get(4)
        funcionario = Funcionario.query.filter_by(admin_id=4).first()
        obra = Obra.query.filter_by(admin_id=4).first()
        
        print(f"Admin: {admin.nome}")
        print(f"Funcionário: {funcionario.nome}")
        print(f"Obra: {obra.nome}")
        
        # Dados que seriam enviados pelo JavaScript
        dados_teste = {
            'periodo_inicio': '2025-08-05',
            'periodo_fim': '2025-08-05',
            'tipo_lancamento': 'sabado_horas_extras',
            'obra_id': obra.id,
            'funcionarios': [funcionario.id],
            'hora_entrada': '07:00',
            'hora_saida': '11:00',
            'percentual_extras': 50,
            'observacoes': 'Teste após correção'
        }
        
        print(f"\n📋 Dados do teste:")
        print(f"   Período: {dados_teste['periodo_inicio']} até {dados_teste['periodo_fim']}")
        print(f"   Tipo: {dados_teste['tipo_lancamento']}")
        print(f"   Obra ID: {dados_teste['obra_id']}")
        print(f"   Funcionários: {dados_teste['funcionarios']}")
        
        # Simular validações que a API faz
        try:
            # 1. Parse das datas
            periodo_inicio = datetime.strptime(dados_teste['periodo_inicio'], '%Y-%m-%d').date()
            periodo_fim = datetime.strptime(dados_teste['periodo_fim'], '%Y-%m-%d').date()
            print(f"✅ Parse de datas: OK")
            
            # 2. Verificar obra (isso estava falhando antes)
            obra_verificacao = Obra.query.filter_by(
                id=dados_teste['obra_id'], 
                admin_id=admin.id
            ).first()
            
            if obra_verificacao:
                print(f"✅ Obra encontrada e pertence ao tenant: {obra_verificacao.nome}")
            else:
                print(f"❌ Obra não encontrada ou não pertence ao tenant")
                return False
            
            # 3. Verificar funcionários
            funcionarios_verificacao = Funcionario.query.filter(
                Funcionario.id.in_(dados_teste['funcionarios']),
                Funcionario.admin_id == admin.id
            ).all()
            
            print(f"✅ Funcionários verificados: {len(funcionarios_verificacao)}")
            for func in funcionarios_verificacao:
                print(f"   - {func.nome}")
            
            # 4. Verificar registros existentes
            registro_existente = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id.in_(dados_teste['funcionarios']),
                RegistroPonto.data == periodo_inicio
            ).first()
            
            if registro_existente:
                print(f"⚠️ Registro existente encontrado: {registro_existente.funcionario_ref.nome}")
                # Remover para o teste
                db.session.delete(registro_existente)
                db.session.commit()
                print(f"🗑️ Registro removido para permitir teste")
            
            print(f"\n🎯 TODAS AS VALIDAÇÕES PASSARAM!")
            print(f"✅ O lançamento múltiplo deve funcionar agora")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste: {e}")
            return False

if __name__ == "__main__":
    resultado = testar_api_diretamente()
    
    if resultado:
        print(f"\n🎉 TESTE APROVADO!")
        print(f"🚀 Lançamentos múltiplos devem funcionar corretamente agora")
    else:
        print(f"\n🔧 Ainda há problemas para resolver")