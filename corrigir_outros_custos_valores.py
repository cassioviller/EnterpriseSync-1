#!/usr/bin/env python3
"""
🔧 CORREÇÃO IMEDIATA: Outros Custos - Valores Incorretos
Corrige valores negativos para bônus e adicionais
"""

from app import app, db
from models import OutroCusto
from datetime import datetime

def corrigir_valor_outro_custo(tipo, valor_original):
    """
    Corrige sinal do valor baseado no tipo
    
    Args:
        tipo (str): Tipo do custo (bonus, adicional, desconto, outros)
        valor_original (float): Valor original inserido
        
    Returns:
        float: Valor com sinal correto
    """
    if not tipo:
        return valor_original
        
    tipo_lower = tipo.lower().strip()
    
    # LÓGICA CORRETA:
    if tipo_lower in ['bonus', 'bônus', 'adicional', 'outros']:
        # Deve ser POSITIVO
        return abs(valor_original)
    elif 'desconto' in tipo_lower:
        # Deve ser NEGATIVO (inclui "Desconto VT", "desconto", etc.)
        return -abs(valor_original)
    else:
        # Manter original
        return valor_original

def corrigir_outros_custos_existentes():
    """Corrige valores de todos os registros existentes"""
    print("🔄 CORRIGINDO OUTROS CUSTOS EXISTENTES...")
    
    # Buscar todos os registros
    registros = OutroCusto.query.all()
    
    print(f"📊 ENCONTRADOS {len(registros)} REGISTROS")
    
    corrigidos = 0
    
    for registro in registros:
        valor_original = registro.valor
        tipo = registro.tipo
        
        # Aplicar correção
        valor_correto = corrigir_valor_outro_custo(tipo, valor_original)
        
        # Atualizar se necessário
        if valor_correto != valor_original:
            print(f"📊 CORRIGINDO:")
            print(f"   ID: {registro.id}")
            print(f"   Funcionário ID: {registro.funcionario_id}")
            print(f"   Tipo: {tipo}")
            print(f"   Descrição: {registro.descricao}")
            print(f"   Valor: {valor_original} → {valor_correto}")
            print(f"   Data: {registro.data}")
            
            registro.valor = valor_correto
            corrigidos += 1
    
    # Salvar todas as alterações
    if corrigidos > 0:
        db.session.commit()
        print(f"✅ CORRIGIDOS {corrigidos} REGISTROS")
    else:
        print("ℹ️  NENHUM REGISTRO PRECISOU SER CORRIGIDO")
        
    return corrigidos

def validar_outros_custos():
    """Valida se os valores estão corretos"""
    print("🔍 VALIDANDO OUTROS CUSTOS...")
    
    # Verificar bônus (devem ser positivos)
    bonus = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%bonus%')
    ).all()
    
    bonus_negativos = [b for b in bonus if b.valor < 0]
    
    print(f"📊 BÔNUS TOTAL: {len(bonus)}")
    print(f"📊 BÔNUS NEGATIVOS: {len(bonus_negativos)} (deveria ser 0)")
    
    if bonus_negativos:
        for b in bonus_negativos:
            print(f"   ❌ ID {b.id}: {b.tipo} = R$ {b.valor}")
    
    # Verificar adicionais (devem ser positivos)
    adicionais = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%adicional%')
    ).all()
    
    adicionais_negativos = [a for a in adicionais if a.valor < 0]
    
    print(f"📊 ADICIONAIS TOTAL: {len(adicionais)}")
    print(f"📊 ADICIONAIS NEGATIVOS: {len(adicionais_negativos)} (deveria ser 0)")
    
    if adicionais_negativos:
        for a in adicionais_negativos:
            print(f"   ❌ ID {a.id}: {a.tipo} = R$ {a.valor}")
    
    # Verificar descontos (devem ser negativos)
    descontos = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%desconto%')
    ).all()
    
    descontos_positivos = [d for d in descontos if d.valor > 0]
    
    print(f"📊 DESCONTOS TOTAL: {len(descontos)}")
    print(f"📊 DESCONTOS POSITIVOS: {len(descontos_positivos)} (deveria ser 0)")
    
    if descontos_positivos:
        for d in descontos_positivos:
            print(f"   ❌ ID {d.id}: {d.tipo} = R$ {d.valor}")
    
    # Resumo
    total_problemas = len(bonus_negativos) + len(adicionais_negativos) + len(descontos_positivos)
    
    if total_problemas == 0:
        print("✅ TODOS OS VALORES ESTÃO CORRETOS!")
        return True
    else:
        print(f"❌ AINDA HÁ {total_problemas} VALORES INCORRETOS")
        return False

def main():
    """Executa correção completa"""
    with app.app_context():
        print("🚨 INICIANDO CORREÇÃO DE OUTROS CUSTOS")
        print("=" * 50)
        
        # 1. Validação inicial
        print("\n1️⃣ VALIDAÇÃO INICIAL:")
        validar_outros_custos()
        
        # 2. Correção dos registros
        print("\n2️⃣ APLICANDO CORREÇÕES:")
        corrigidos = corrigir_outros_custos_existentes()
        
        # 3. Validação final
        print("\n3️⃣ VALIDAÇÃO FINAL:")
        sucesso = validar_outros_custos()
        
        # 4. Resumo
        print("\n🎯 RESUMO:")
        print(f"   Registros corrigidos: {corrigidos}")
        print(f"   Status: {'✅ SUCESSO' if sucesso else '❌ FALHOU'}")
        
        if sucesso and corrigidos > 0:
            print("\n🎉 CORREÇÃO CONCLUÍDA COM SUCESSO!")
            print("   • Bônus e Adicionais agora são POSITIVOS")
            print("   • Descontos permanecem NEGATIVOS")
            print("   • Sistema funcionando corretamente")

if __name__ == "__main__":
    main()