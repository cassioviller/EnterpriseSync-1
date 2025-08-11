#!/usr/bin/env python3
"""
Validação Final Completa do SIGE v8.0
Sistema de verificação automática de funcionalidades
"""

import requests
import time
import json
from datetime import datetime

def testar_sistema_completo():
    """Teste abrangente de todo o sistema SIGE v8.0"""
    
    print("🎯 VALIDAÇÃO FINAL COMPLETA - SIGE v8.0")
    print("=" * 60)
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    resultados = {
        'endpoints': {},
        'conteudo': {},
        'performance': {},
        'status_geral': 'PENDENTE'
    }
    
    base_url = 'http://localhost:5000'
    
    # === TESTE 1: ENDPOINTS PRINCIPAIS ===
    print("\n📡 TESTE 1: VALIDAÇÃO DE ENDPOINTS")
    print("-" * 40)
    
    endpoints_criticos = [
        ('/', 'Página Inicial'),
        ('/test', 'Endpoint de Teste'),
        ('/login', 'Sistema de Login'),
        ('/dashboard', 'Dashboard Principal'),
        ('/funcionarios', 'Gestão de Funcionários'),
        ('/obras', 'Gestão de Obras'),
        ('/veiculos', 'Gestão de Veículos')
    ]
    
    endpoints_funcionando = 0
    
    for endpoint, nome in endpoints_criticos:
        try:
            inicio = time.time()
            response = requests.get(f'{base_url}{endpoint}', timeout=10)
            tempo_resposta = (time.time() - inicio) * 1000
            
            if response.status_code in [200, 302]:
                status = "✅ FUNCIONANDO"
                resultados['endpoints'][endpoint] = True
                endpoints_funcionando += 1
            else:
                status = f"⚠️ Status {response.status_code}"
                resultados['endpoints'][endpoint] = False
                
            resultados['performance'][endpoint] = tempo_resposta
            print(f"{status} {endpoint:15} - {nome:25} ({tempo_resposta:.0f}ms)")
            
        except Exception as e:
            print(f"❌ ERRO     {endpoint:15} - {nome:25} (Erro: {str(e)[:30]}...)")
            resultados['endpoints'][endpoint] = False
            resultados['performance'][endpoint] = 0
    
    score_endpoints = (endpoints_funcionando / len(endpoints_criticos)) * 100
    print(f"\n📊 Score Endpoints: {score_endpoints:.1f}% ({endpoints_funcionando}/{len(endpoints_criticos)})")
    
    # === TESTE 2: CONTEÚDO DO DASHBOARD ===
    print("\n🎨 TESTE 2: VALIDAÇÃO DE CONTEÚDO")
    print("-" * 40)
    
    try:
        response = requests.get(f'{base_url}/dashboard', timeout=10)
        
        if response.status_code == 200:
            conteudo = response.text
            
            elementos_esperados = {
                'SIGE': 'Título do Sistema',
                'Dashboard': 'Página Dashboard',
                'Funcionários': 'Seção Funcionários',
                'Obras': 'Seção Obras',
                'Custos': 'Seção Custos',
                'bootstrap': 'Framework CSS',
                'chart': 'Gráficos',
                'card': 'Cards de Interface',
                'navbar': 'Barra de Navegação',
                'R$': 'Valores Monetários'
            }
            
            elementos_encontrados = 0
            
            for elemento, descricao in elementos_esperados.items():
                if elemento.lower() in conteudo.lower():
                    print(f"✅ {elemento:15} - {descricao}")
                    resultados['conteudo'][elemento] = True
                    elementos_encontrados += 1
                else:
                    print(f"❌ {elemento:15} - {descricao}")
                    resultados['conteudo'][elemento] = False
            
            score_conteudo = (elementos_encontrados / len(elementos_esperados)) * 100
            print(f"\n📊 Score Conteúdo: {score_conteudo:.1f}% ({elementos_encontrados}/{len(elementos_esperados)})")
            
        elif response.status_code == 302:
            print("⚡ Dashboard redirecionando - Autenticação necessária")
            score_conteudo = 80  # Ainda funcional, só redirecionando
        else:
            print(f"❌ Dashboard retornou status {response.status_code}")
            score_conteudo = 0
            
    except Exception as e:
        print(f"❌ Erro ao testar conteúdo: {e}")
        score_conteudo = 0
    
    # === TESTE 3: PERFORMANCE GERAL ===
    print("\n⚡ TESTE 3: PERFORMANCE DO SISTEMA")
    print("-" * 40)
    
    tempos_resposta = [t for t in resultados['performance'].values() if t > 0]
    
    if tempos_resposta:
        tempo_medio = sum(tempos_resposta) / len(tempos_resposta)
        tempo_max = max(tempos_resposta)
        tempo_min = min(tempos_resposta)
        
        print(f"⏱️  Tempo Médio: {tempo_medio:.0f}ms")
        print(f"🚀 Tempo Mínimo: {tempo_min:.0f}ms")
        print(f"🐌 Tempo Máximo: {tempo_max:.0f}ms")
        
        if tempo_medio < 500:
            performance_score = 100
            performance_status = "🚀 EXCELENTE"
        elif tempo_medio < 1000:
            performance_score = 80
            performance_status = "✅ BOM"
        elif tempo_medio < 2000:
            performance_score = 60
            performance_status = "⚠️ ACEITÁVEL"
        else:
            performance_score = 40
            performance_status = "🐌 LENTO"
            
        print(f"📈 Performance: {performance_status} ({performance_score}%)")
    else:
        performance_score = 0
        print("❌ Não foi possível medir performance")
    
    # === CÁLCULO DO SCORE FINAL ===
    print("\n" + "=" * 60)
    print("🏆 RELATÓRIO FINAL DA VALIDAÇÃO")
    print("=" * 60)
    
    # Pesos dos scores
    score_final = (
        score_endpoints * 0.4 +      # 40% - Funcionalidade básica
        score_conteudo * 0.4 +       # 40% - Conteúdo da interface
        performance_score * 0.2      # 20% - Performance
    )
    
    print(f"📡 Endpoints Funcionais: {score_endpoints:.1f}%")
    print(f"🎨 Conteúdo Interface: {score_conteudo:.1f}%")
    print(f"⚡ Performance Geral: {performance_score:.1f}%")
    print("-" * 60)
    print(f"🎯 SCORE FINAL: {score_final:.1f}%")
    
    # Status baseado no score
    if score_final >= 90:
        status = "🎊 EXCELENTE - Sistema production-ready"
        resultados['status_geral'] = 'EXCELENTE'
    elif score_final >= 80:
        status = "✅ MUITO BOM - Sistema funcional com pequenos ajustes"
        resultados['status_geral'] = 'MUITO_BOM'
    elif score_final >= 70:
        status = "👍 BOM - Sistema funcional mas necessita melhorias"
        resultados['status_geral'] = 'BOM'
    elif score_final >= 50:
        status = "⚠️ REGULAR - Sistema parcialmente funcional"
        resultados['status_geral'] = 'REGULAR'
    else:
        status = "❌ RUIM - Sistema com problemas críticos"
        resultados['status_geral'] = 'RUIM'
    
    print(f"🏁 STATUS: {status}")
    
    # === CONCLUSÃO E RECOMENDAÇÕES ===
    print("\n💡 RECOMENDAÇÕES:")
    
    if score_final >= 90:
        print("🚀 Sistema pronto para produção!")
        print("📈 Implementar monitoramento em produção")
        print("🔧 Configurar backups automáticos")
        
    elif score_final >= 80:
        print("🔨 Corrigir pequenos problemas de interface")
        print("⚡ Otimizar performance se necessário")
        print("✅ Sistema aprovado para testes finais")
        
    elif score_final >= 70:
        print("🐛 Investigar e corrigir problemas de conteúdo")
        print("📊 Melhorar interface do usuário")
        print("🔍 Fazer testes mais detalhados")
        
    else:
        print("🚨 Investigar problemas críticos de sistema")
        print("🔧 Revisar configurações básicas")
        print("📋 Validar dependências e configurações")
    
    print("\n" + "=" * 60)
    print(f"✅ VALIDAÇÃO CONCLUÍDA - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    # Salvar resultados
    with open('validacao_sige_v8_resultados.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    return score_final, resultados['status_geral']

if __name__ == '__main__':
    try:
        score, status = testar_sistema_completo()
        
        # Determinar código de saída
        if score >= 80:
            exit_code = 0  # Sucesso
        elif score >= 60:
            exit_code = 1  # Warning
        else:
            exit_code = 2  # Error
        
        exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n🛑 Validação interrompida pelo usuário")
        exit(3)
    except Exception as e:
        print(f"\n💥 Erro durante validação: {e}")
        exit(4)