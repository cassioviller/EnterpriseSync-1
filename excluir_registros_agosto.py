#!/usr/bin/env python3
"""
EXCLUSÃO: Registros de Alimentação com Data Incorreta em Agosto
Excluir registros de 01/08 a 05/08/2025 que foram criados por erro
"""

from app import app, db
from models import RegistroAlimentacao, Funcionario
from datetime import date
from sqlalchemy import and_

def listar_registros_agosto():
    """Lista todos os registros incorretos de agosto"""
    
    with app.app_context():
        print("🔍 REGISTROS DE AGOSTO PARA EXCLUSÃO")
        print("=" * 60)
        
        # Buscar registros de agosto
        registros_agosto = RegistroAlimentacao.query.filter(
            and_(
                RegistroAlimentacao.data >= date(2025, 8, 1),
                RegistroAlimentacao.data <= date(2025, 8, 5)
            )
        ).order_by(RegistroAlimentacao.data, RegistroAlimentacao.funcionario_id).all()
        
        print(f"📊 Total encontrados: {len(registros_agosto)} registros")
        
        if not registros_agosto:
            print("✅ Nenhum registro incorreto encontrado")
            return []
        
        # Mostrar detalhes
        print("\n📋 Lista completa:")
        for i, reg in enumerate(registros_agosto, 1):
            funcionario = Funcionario.query.get(reg.funcionario_id)
            funcionario_nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            print(f"{i:2d}. {reg.data.strftime('%d/%m/%Y')} - {funcionario_nome}")
            print(f"     {reg.tipo} - R$ {reg.valor} - {reg.restaurante.nome if reg.restaurante else 'Sem restaurante'}")
        
        return registros_agosto

def confirmar_exclusao(registros):
    """Confirma exclusão com o usuário"""
    
    if not registros:
        return False
    
    print(f"\n⚠️ ATENÇÃO: Você está prestes a excluir {len(registros)} registros")
    print("Esta ação NÃO pode ser desfeita!")
    
    resposta = input("\n❓ Confirma a exclusão de TODOS os registros de agosto? (digite 'CONFIRMO' para continuar): ")
    
    return resposta == 'CONFIRMO'

def excluir_registros(registros):
    """Exclui os registros do banco de dados"""
    
    with app.app_context():
        print("\n🗑️ EXCLUINDO REGISTROS...")
        print("-" * 40)
        
        excluidos = 0
        
        try:
            for reg in registros:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                funcionario_nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                
                print(f"   🗑️ Excluindo: {reg.data.strftime('%d/%m/%Y')} - {funcionario_nome}")
                
                db.session.delete(reg)
                excluidos += 1
            
            # Salvar mudanças
            db.session.commit()
            
            print(f"\n🎉 SUCESSO: {excluidos} registros excluídos!")
            print("   Registros incorretos de agosto foram removidos")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")
            return False
        
        return True

def verificar_julio_apos_exclusao():
    """Verifica registros de julho após exclusão"""
    
    with app.app_context():
        print("\n📊 VERIFICAÇÃO FINAL: Registros em julho")
        print("-" * 50)
        
        registros_julho = RegistroAlimentacao.query.filter(
            and_(
                RegistroAlimentacao.data >= date(2025, 7, 1),
                RegistroAlimentacao.data <= date(2025, 7, 31)
            )
        ).order_by(RegistroAlimentacao.data.desc()).all()
        
        print(f"✅ Total em julho: {len(registros_julho)} registros")
        
        # Verificar se há registros de 30/07
        registros_30_julho = [r for r in registros_julho if r.data.day == 30]
        print(f"✅ Registros em 30/07: {len(registros_30_julho)}")
        
        # Mostrar últimos registros
        if registros_julho:
            print("\nÚltimos 5 registros de julho:")
            for reg in registros_julho[:5]:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                funcionario_nome = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
                print(f"   {reg.data.strftime('%d/%m/%Y')}: {funcionario_nome} - {reg.tipo}")

if __name__ == "__main__":
    print("🚨 EXCLUSÃO DE REGISTROS INCORRETOS DE AGOSTO")
    print("=" * 60)
    
    # Listar registros
    registros = listar_registros_agosto()
    
    if not registros:
        print("\n✅ Nenhum registro para excluir")
        exit(0)
    
    # Confirmar exclusão
    if confirmar_exclusao(registros):
        # Executar exclusão
        sucesso = excluir_registros(registros)
        
        if sucesso:
            # Verificar resultado
            verificar_julio_apos_exclusao()
        
    else:
        print("\n⚠️ Exclusão cancelada pelo usuário")
        print("   Nenhum registro foi alterado")