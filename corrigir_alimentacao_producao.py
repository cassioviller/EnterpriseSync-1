#!/usr/bin/env python3
"""
🎯 CORREÇÃO FINAL: Módulo de Alimentação - Nomes dos Funcionários e Filtros
PROBLEMA: Registros não mostram nomes dos funcionários
SOLUÇÃO: Garantir JOIN correto e eager loading
"""

from app import app, db
from models import RegistroAlimentacao, Funcionario, Obra, Restaurante
from sqlalchemy.orm import joinedload
from datetime import datetime, date

def testar_alimentacao():
    with app.app_context():
        print("🎯 TESTE: Módulo de Alimentação")
        print("=" * 50)
        
        # Verificar registros existentes
        total_registros = RegistroAlimentacao.query.count()
        print(f"📊 Total de registros: {total_registros}")
        
        if total_registros == 0:
            print("❌ Nenhum registro encontrado")
            return
            
        # Testar query com JOIN
        registros_com_join = RegistroAlimentacao.query.join(
            Funcionario, RegistroAlimentacao.funcionario_id == Funcionario.id
        ).options(
            joinedload(RegistroAlimentacao.funcionario),
            joinedload(RegistroAlimentacao.obra_ref),
            joinedload(RegistroAlimentacao.restaurante_ref)
        ).limit(5).all()
        
        print(f"\n📋 AMOSTRA DE REGISTROS (com JOIN):")
        for i, registro in enumerate(registros_com_join, 1):
            nome_funcionario = registro.funcionario.nome if registro.funcionario else "NOME NÃO ENCONTRADO"
            obra_nome = registro.obra_ref.nome if registro.obra_ref else "SEM OBRA"
            restaurante_nome = registro.restaurante_ref.nome if registro.restaurante_ref else "SEM RESTAURANTE"
            
            print(f"   {i}. {nome_funcionario} - {registro.data} - R$ {registro.valor}")
            print(f"      Obra: {obra_nome} | Restaurante: {restaurante_nome}")
            print(f"      Tipo: {registro.tipo} | ID Funcionário: {registro.funcionario_id}")
        
        # Verificar integridade dos dados
        registros_sem_funcionario = RegistroAlimentacao.query.filter(
            ~RegistroAlimentacao.funcionario_id.in_(
                db.session.query(Funcionario.id)
            )
        ).count()
        
        print(f"\n🔍 DIAGNÓSTICO:")
        print(f"   • Registros com funcionário válido: {total_registros - registros_sem_funcionario}")
        print(f"   • Registros órfãos (sem funcionário): {registros_sem_funcionario}")
        
        if registros_sem_funcionario > 0:
            print(f"   ⚠️ Há registros com funcionário_id inválido")
            
        # Testar filtros por período (últimos 30 dias)
        data_limite = datetime.now().date() - datetime.timedelta(days=30)
        registros_recentes = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.data >= data_limite
        ).count()
        
        print(f"   • Registros últimos 30 dias: {registros_recentes}")
        
        # Verificar funcionários ativos
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).count()
        print(f"   • Funcionários ativos: {funcionarios_ativos}")
        
        print(f"\n✅ TESTE CONCLUÍDO")
        print(f"   • JOIN funcionando: {'✅' if registros_com_join else '❌'}")
        print(f"   • Nomes carregados: {'✅' if all(r.funcionario and r.funcionario.nome for r in registros_com_join) else '❌'}")

if __name__ == "__main__":
    testar_alimentacao()