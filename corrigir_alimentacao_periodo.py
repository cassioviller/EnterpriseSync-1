#!/usr/bin/env python3
"""
CORREÇÃO: Sistema de Lançamento de Alimentação por Período
Sistema SIGE - Data: 05 de Agosto de 2025

PROBLEMA IDENTIFICADO:
- Lançamento por período está salvando datas incorretas
- Necessário verificar e corrigir a lógica de processamento de datas

CORREÇÃO:
- Adicionar logs detalhados na função nova_alimentacao
- Verificar conversão de datas do formulário
- Garantir que as datas sejam processadas corretamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import RegistroAlimentacao, Funcionario, Obra, Restaurante
from datetime import datetime, timedelta, date
from flask import request

def adicionar_debug_views():
    """Adiciona debug na função nova_alimentacao do views.py"""
    
    print("🔧 ADICIONANDO DEBUG NO SISTEMA DE ALIMENTAÇÃO")
    print("=" * 60)
    
    # Ler o arquivo views.py
    with open('views.py', 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Encontrar a função nova_alimentacao e adicionar logs
    debug_code = '''        # DEBUG: Log dos dados recebidos
        print(f"🔍 DEBUG - Dados do formulário:")
        print(f"   data_inicio: {data_inicio}")
        print(f"   data_fim: {data_fim}")
        print(f"   data_unica: {data_unica}")
        
        if data_inicio and data_fim:
            print(f"   Convertendo datas do período...")
            print(f"   inicio convertido: {inicio}")
            print(f"   fim convertido: {fim}")
        elif data_unica:
            print(f"   Data única convertida: {datetime.strptime(data_unica, '%Y-%m-%d').date()}")
        
        print(f"   Datas para processamento: {datas_processamento}")'''
    
    # Verificar se o debug já foi adicionado
    if "DEBUG - Dados do formulário" in conteudo:
        print("✅ Debug já está presente no código")
        return
    
    # Adicionar debug após a linha que define datas_processamento
    linha_adicionar = "        # Dados básicos do formulário"
    
    if linha_adicionar in conteudo:
        conteudo_modificado = conteudo.replace(
            linha_adicionar,
            debug_code + "\n        \n" + linha_adicionar
        )
        
        # Salvar o arquivo modificado
        with open('views.py', 'w', encoding='utf-8') as f:
            f.write(conteudo_modificado)
        
        print("✅ Debug adicionado com sucesso!")
        print("📝 Próximos testes de lançamento mostrarão logs detalhados")
    else:
        print("❌ Não foi possível encontrar o local para adicionar debug")

def testar_conversao_datas():
    """Testa a conversão de datas igual ao views.py"""
    
    print("\n🧪 TESTANDO CONVERSÃO DE DATAS:")
    print("-" * 40)
    
    # Simular dados que vêm do formulário
    casos_teste = [
        ("2025-08-05", "2025-08-07"),  # Hoje até daqui 2 dias
        ("2025-08-01", "2025-08-05"),  # 1º agosto até hoje
        ("2025-07-29", "2025-07-31"),  # Período passado
    ]
    
    for data_inicio_str, data_fim_str in casos_teste:
        print(f"\n📅 Teste: {data_inicio_str} até {data_fim_str}")
        
        try:
            # Converter exatamente como no views.py
            inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            
            print(f"   ✅ Início convertido: {inicio} (tipo: {type(inicio)})")
            print(f"   ✅ Fim convertido: {fim} (tipo: {type(fim)})")
            
            # Gerar datas
            datas_processamento = []
            data_atual = inicio
            
            while data_atual <= fim:
                datas_processamento.append(data_atual)
                data_atual += timedelta(days=1)
            
            print(f"   📋 Datas geradas: {datas_processamento}")
            print(f"   📊 Total de dias: {len(datas_processamento)}")
            
        except Exception as e:
            print(f"   ❌ Erro na conversão: {str(e)}")

def verificar_registros_problema():
    """Verifica se há registros com datas problemáticas"""
    
    print("\n🔍 VERIFICANDO REGISTROS PROBLEMÁTICOS:")
    print("-" * 50)
    
    with app.app_context():
        # Buscar registros dos últimos 30 dias
        data_limite = date.today() - timedelta(days=30)
        
        registros = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.created_at >= datetime.now() - timedelta(days=7)  # Criados na última semana
        ).order_by(RegistroAlimentacao.created_at.desc()).limit(20).all()
        
        print(f"📊 Analisando {len(registros)} registros criados nos últimos 7 dias")
        
        problemas_encontrados = []
        
        for reg in registros:
            funcionario = Funcionario.query.get(reg.funcionario_id)
            nome_func = funcionario.nome if funcionario else f"ID:{reg.funcionario_id}"
            
            # Verificar se a data está muito diferente da data de criação
            diferenca_dias = abs((reg.data - reg.created_at.date()).days)
            
            if diferenca_dias > 7:  # Mais de 7 dias de diferença
                problemas_encontrados.append({
                    'id': reg.id,
                    'funcionario': nome_func,
                    'data_registro': reg.data,
                    'data_criacao': reg.created_at.date(),
                    'diferenca_dias': diferenca_dias
                })
        
        if problemas_encontrados:
            print(f"⚠️ Encontrados {len(problemas_encontrados)} registros com possíveis problemas:")
            for problema in problemas_encontrados:
                print(f"   • ID {problema['id']}: {problema['funcionario']}")
                print(f"     Data do registro: {problema['data_registro']}")
                print(f"     Data de criação: {problema['data_criacao']}")
                print(f"     Diferença: {problema['diferenca_dias']} dias")
                print()
        else:
            print("✅ Nenhum problema evidente encontrado")

if __name__ == "__main__":
    adicionar_debug_views()
    testar_conversao_datas()
    verificar_registros_problema()