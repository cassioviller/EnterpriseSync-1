#!/usr/bin/env python3
"""
Debug do problema de lançamentos múltiplos
Vou criar logs detalhados para identificar o problema
"""

from app import app, db
from models import *
from datetime import datetime, timedelta

def debug_problema_lancamento():
    """Debug completo do problema"""
    
    with app.app_context():
        print("🐛 DEBUG: Problema de Lançamentos Múltiplos")
        print("=" * 60)
        
        # 1. Verificar dados do último teste
        print("\n📊 Verificando dados atuais:")
        total_funcionarios = Funcionario.query.count()
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).count()
        obras = Obra.query.count()
        registros_ponto = RegistroPonto.query.count()
        
        print(f"Funcionários: {total_funcionarios} (ativos: {funcionarios_ativos})")
        print(f"Obras: {obras}")
        print(f"Registros de ponto: {registros_ponto}")
        
        # 2. Testar a função manualmente
        print("\n🧪 Simulando lançamento múltiplo:")
        
        # Dados de teste similares ao que vem do frontend
        dados_teste = {
            'periodo_inicio': '2025-07-05',
            'periodo_fim': '2025-07-05', 
            'tipo_lancamento': 'sabado_horas_extras',
            'obra_id': 1,
            'funcionarios': [1],  # Carlos Alberto Rigolo
            'hora_entrada': '07:00',
            'hora_saida': '16:03',
            'percentual_extras': 50,
            'sem_intervalo': False,
            'observacoes': 'Teste debug'
        }
        
        print(f"Dados de teste: {dados_teste}")
        
        # Simular processamento
        try:
            periodo_inicio = datetime.strptime(dados_teste['periodo_inicio'], '%Y-%m-%d').date()
            periodo_fim = datetime.strptime(dados_teste['periodo_fim'], '%Y-%m-%d').date()
            tipo_lancamento = dados_teste['tipo_lancamento']
            obra_id = dados_teste['obra_id']
            funcionarios_ids = dados_teste['funcionarios']
            
            print(f"✅ Parsing dos dados OK")
            print(f"   Período: {periodo_inicio} até {periodo_fim}")
            print(f"   Tipo: {tipo_lancamento}")
            print(f"   Obra ID: {obra_id}")
            print(f"   Funcionários: {funcionarios_ids}")
            
            # Verificar se obra existe
            obra = Obra.query.get(obra_id)
            if not obra:
                print(f"❌ Obra {obra_id} não encontrada!")
                return False
            print(f"✅ Obra encontrada: {obra.nome}")
            
            # Verificar funcionários
            funcionarios = Funcionario.query.filter(
                Funcionario.id.in_(funcionarios_ids)
            ).all()
            
            print(f"✅ Funcionários encontrados: {len(funcionarios)}")
            for func in funcionarios:
                print(f"   - {func.nome} (ID: {func.id}, Ativo: {func.ativo})")
            
            # Verificar registros existentes
            registro_existente = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id.in_(funcionarios_ids),
                RegistroPonto.data == periodo_inicio
            ).first()
            
            if registro_existente:
                print(f"⚠️ Já existe registro para {registro_existente.funcionario_ref.nome} em {periodo_inicio}")
            else:
                print(f"✅ Sem registros conflitantes")
            
            # Verificar horário de trabalho
            for funcionario in funcionarios:
                if funcionario.horario_trabalho_id:
                    horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
                    print(f"   Horário de {funcionario.nome}: {horario.nome if horario else 'Não encontrado'}")
                else:
                    print(f"   {funcionario.nome}: Sem horário configurado")
            
            print(f"\n🎯 Simulação concluída com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro na simulação: {e}")
            return False

if __name__ == "__main__":
    debug_problema_lancamento()