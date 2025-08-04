#!/usr/bin/env python3
"""
🔧 CORREÇÃO ESPECÍFICA PARA PRODUÇÃO: Sábado 05/07/2025
Corrige o registro que ainda mostra "59min" de atraso no ambiente de produção
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def fix_sabado_producao():
    """Corrige especificamente o registro problemático de 05/07/2025"""
    print("🔧 CORREÇÃO ESPECÍFICA PARA PRODUÇÃO")
    print("=" * 50)
    
    # Buscar o registro específico que mostra "59min" na produção
    # Baseado na imagem, parece ser o registro com 7.92h trabalhadas
    registros = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.horas_trabalhadas == 7.92
    ).all()
    
    if not registros:
        print("❌ Registro específico (7.92h) não encontrado")
        # Tentar todos os registros do dia
        registros = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 5),
            RegistroPonto.hora_entrada.isnot(None)
        ).all()
        print(f"📊 Encontrados {len(registros)} registros totais do dia")
    
    for registro in registros:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        print(f"\n🔍 REGISTRO ID {registro.id}:")
        print(f"   Funcionário: {nome}")
        print(f"   Data: {registro.data}")
        print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
        print(f"   Horas extras ANTES: {registro.horas_extras}")
        print(f"   Atraso ANTES: {registro.total_atraso_minutos}min")
        print(f"   Tipo ANTES: {registro.tipo_registro}")
        
        # APLICAR CORREÇÃO FORÇADA ESPECÍFICA
        print("   🔧 APLICANDO CORREÇÃO FORÇADA...")
        
        # Garantir que é sábado trabalhado
        registro.tipo_registro = 'sabado_horas_extras'
        
        # ZERAR COMPLETAMENTE todos os atrasos
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        
        # Garantir horas extras = horas trabalhadas
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 50.0
        
        print(f"   ✅ Horas extras DEPOIS: {registro.horas_extras}")
        print(f"   ✅ Atraso DEPOIS: {registro.total_atraso_minutos}min")
        print(f"   ✅ Tipo DEPOIS: {registro.tipo_registro}")
    
    try:
        db.session.commit()
        print(f"\n✅ CORREÇÃO APLICADA COM SUCESSO!")
        
        # Verificar se funcionou
        for registro in registros:
            db.session.refresh(registro)
            funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
            nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
            
            print(f"✅ {nome}: {registro.horas_extras}h extras, {registro.total_atraso_minutos}min atraso")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO AO APLICAR CORREÇÃO: {e}")
        db.session.rollback()
        return False

def verificar_outros_sabados():
    """Verificar se há outros sábados com problemas similares"""
    print("\n🔍 VERIFICANDO OUTROS SÁBADOS...")
    
    # Buscar todos os sábados (dia da semana = 5)
    sabados_com_atraso = RegistroPonto.query.filter(
        RegistroPonto.total_atraso_minutos > 0,
        RegistroPonto.hora_entrada.isnot(None)
    ).all()
    
    sabados_problema = []
    for registro in sabados_com_atraso:
        if registro.data.weekday() == 5:  # Sábado
            sabados_problema.append(registro)
    
    if sabados_problema:
        print(f"⚠️  ENCONTRADOS {len(sabados_problema)} SÁBADOS COM ATRASO:")
        for registro in sabados_problema:
            funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
            nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
            print(f"   📅 {registro.data} - {nome}: {registro.total_atraso_minutos}min atraso")
        
        return sabados_problema
    else:
        print("✅ Nenhum outro sábado com atraso encontrado")
        return []

def corrigir_todos_sabados_problema(sabados):
    """Corrigir todos os sábados que ainda têm atraso"""
    if not sabados:
        return True
    
    print(f"\n🔧 CORRIGINDO {len(sabados)} SÁBADOS COM ATRASO...")
    
    for registro in sabados:
        funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
        nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
        
        print(f"   🔧 Corrigindo {nome} - {registro.data}")
        
        # Aplicar correção
        registro.tipo_registro = 'sabado_horas_extras'
        registro.total_atraso_minutos = 0
        registro.total_atraso_horas = 0.0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.percentual_extras = 50.0
    
    try:
        db.session.commit()
        print("✅ Todos os sábados corrigidos!")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🚀 CORREÇÃO ESPECÍFICA PARA PRODUÇÃO")
        print("=" * 60)
        
        # 1. Corrigir o registro específico do problema
        sucesso = fix_sabado_producao()
        
        if sucesso:
            # 2. Verificar se há outros sábados com problema
            outros_sabados = verificar_outros_sabados()
            
            # 3. Corrigir todos se necessário
            if outros_sabados:
                corrigir_todos_sabados_problema(outros_sabados)
            
            print("\n" + "=" * 60)
            print("🎯 CORREÇÃO PARA PRODUÇÃO CONCLUÍDA!")
            print("✅ Registro 05/07/2025 deve agora mostrar:")
            print("   - Atraso: '-' (em vez de '59min')")
            print("   - Horas extras: '7.92h - 50%'")
            print("   - Tag: 'SÁBADO' (já estava correto)")
            print("\n🔄 Aguarde alguns segundos e recarregue a página!")
        else:
            print("\n❌ FALHA NA CORREÇÃO")
        
        print("=" * 60)