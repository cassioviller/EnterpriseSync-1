#!/usr/bin/env python3
"""
🔄 FORÇA ATUALIZAÇÃO: Recriar registros de sábado com dados corretos
Para resolver definitivamente o problema da interface de produção
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def force_update_sabado():
    """Força atualização completa do registro de sábado problemático"""
    print("🔄 FORÇA ATUALIZAÇÃO DO SÁBADO 05/07/2025")
    print("=" * 50)
    
    # Buscar o registro específico
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5),
        RegistroPonto.horas_trabalhadas == 7.92
    ).first()
    
    if not registro:
        print("❌ Registro específico não encontrado")
        return False
    
    funcionario = Funcionario.query.filter_by(id=registro.funcionario_id).first()
    nome = funcionario.nome if funcionario else f"ID {registro.funcionario_id}"
    
    print(f"📍 ATUALIZANDO REGISTRO DE {nome}")
    print(f"   ID: {registro.id}")
    print(f"   Data: {registro.data}")
    print(f"   Entrada: {registro.hora_entrada}")
    print(f"   Saída: {registro.hora_saida}")
    
    # RECALCULAR TUDO DO ZERO
    entrada = registro.hora_entrada
    saida = registro.hora_saida
    
    # Calcular horas trabalhadas novamente
    if entrada and saida:
        from datetime import datetime, timedelta
        
        entrada_dt = datetime.combine(registro.data, entrada)
        saida_dt = datetime.combine(registro.data, saida)
        
        # Subtrair hora de almoço (1h)
        total_minutos = (saida_dt - entrada_dt).total_seconds() / 60
        horas_com_almoco = total_minutos / 60
        horas_trabalhadas = horas_com_almoco - 1.0  # Descontar 1h de almoço
        
        print(f"🔢 RECÁLCULO:")
        print(f"   Total com almoço: {horas_com_almoco:.2f}h")
        print(f"   Menos 1h almoço: {horas_trabalhadas:.2f}h")
    else:
        horas_trabalhadas = 0
    
    # FORÇAR VALORES CORRETOS PARA SÁBADO
    print("🔧 APLICANDO LÓGICA DE SÁBADO TRABALHADO...")
    
    # 1. Atualizar horas trabalhadas
    registro.horas_trabalhadas = horas_trabalhadas
    
    # 2. TODAS as horas = EXTRAS (sábado)
    registro.horas_extras = horas_trabalhadas
    registro.percentual_extras = 50.0
    
    # 3. ZERO atrasos (sábado não tem atraso)
    registro.total_atraso_minutos = 0
    registro.total_atraso_horas = 0.0
    registro.minutos_atraso_entrada = 0
    registro.minutos_atraso_saida = 0
    
    # 4. Tipo correto
    registro.tipo_registro = 'sabado_horas_extras'
    
    # 5. Limpar campos problemáticos
    registro.observacoes = None
    
    print(f"✅ VALORES FINAIS:")
    print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
    print(f"   Horas extras: {registro.horas_extras}")
    print(f"   Atraso minutos: {registro.total_atraso_minutos}")
    print(f"   Atraso horas: {registro.total_atraso_horas}")
    print(f"   Tipo: {registro.tipo_registro}")
    print(f"   Percentual: {registro.percentual_extras}%")
    
    try:
        db.session.commit()
        print("\n✅ ATUALIZAÇÃO FORÇADA APLICADA!")
        
        # Verificar novamente
        db.session.refresh(registro)
        print(f"🔍 VERIFICAÇÃO FINAL:")
        print(f"   Horas extras: {registro.horas_extras}")
        print(f"   Atraso: {registro.total_atraso_minutos}min")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        db.session.rollback()
        return False

def criar_versao_de_cache():
    """Cria um timestamp para forçar atualização de cache"""
    import time
    versao = int(time.time())
    
    print(f"\n📦 VERSÃO DE CACHE CRIADA: {versao}")
    print("   Use este valor para forçar atualização do navegador")
    
    return versao

if __name__ == "__main__":
    with app.app_context():
        print("🚀 FORÇA ATUALIZAÇÃO PARA RESOLVER PROBLEMA DE PRODUÇÃO")
        print("=" * 70)
        
        # 1. Forçar atualização
        sucesso = force_update_sabado()
        
        if sucesso:
            # 2. Criar versão de cache
            versao = criar_versao_de_cache()
            
            print("\n" + "=" * 70)
            print("🎯 ATUALIZAÇÃO FORÇADA CONCLUÍDA!")
            print("✅ O registro 05/07/2025 agora deve mostrar:")
            print("   - Horas extras: 7.92h")
            print("   - Atraso: 0min (deve aparecer como '-')")
            print("   - Tag: SÁBADO")
            print("\n🔄 PARA RESOLVER O CACHE:")
            print("   1. Ctrl+Shift+R (recarregar forçado)")
            print("   2. Ou Ctrl+F5")
            print("   3. Ou limpar cache do navegador")
            print(f"   4. Versão atual: {versao}")
        else:
            print("\n❌ FALHA NA ATUALIZAÇÃO FORÇADA")
        
        print("=" * 70)