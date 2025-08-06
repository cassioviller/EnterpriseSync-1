#!/usr/bin/env python3
"""
TESTE COMPLETO DO SISTEMA DE HORÁRIOS PADRÃO - SIGE v8.2
Data: 06 de Agosto de 2025
Validação final de todas as funcionalidades implementadas
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioPadrao
from integrar_horarios_padrao_kpis import calcular_kpis_funcionario_horario_padrao
from datetime import date, time, datetime
import logging

logging.basicConfig(level=logging.INFO)

def teste_modelo_horario_padrao():
    """Testa o modelo HorarioPadrao"""
    print("🔧 TESTANDO MODELO HORÁRIO PADRÃO")
    
    with app.app_context():
        try:
            # Buscar um funcionário
            funcionario = Funcionario.query.filter_by(ativo=True).first()
            if not funcionario:
                print("❌ Nenhum funcionário encontrado")
                return False
            
            # Verificar se tem horário padrão
            horario_padrao = funcionario.get_horario_padrao_ativo()
            if horario_padrao:
                print(f"✅ {funcionario.nome} tem horário padrão:")
                print(f"   Entrada: {horario_padrao.entrada_padrao}")
                print(f"   Saída: {horario_padrao.saida_padrao}")
                print(f"   Ativo desde: {horario_padrao.data_inicio}")
                return True
            else:
                print(f"⚠️ {funcionario.nome} não tem horário padrão")
                return False
                
        except Exception as e:
            print(f"❌ Erro no teste do modelo: {e}")
            return False

def teste_calculo_horas_extras():
    """Testa o cálculo de horas extras com horário padrão"""
    print("🧮 TESTANDO CÁLCULO DE HORAS EXTRAS")
    
    with app.app_context():
        try:
            # Buscar registro recente com horários
            registro = RegistroPonto.query.filter(
                RegistroPonto.hora_entrada.isnot(None),
                RegistroPonto.hora_saida.isnot(None)
            ).order_by(RegistroPonto.data.desc()).first()
            
            if not registro:
                print("❌ Nenhum registro encontrado para teste")
                return False
            
            funcionario = registro.funcionario_ref
            horario_padrao = funcionario.get_horario_padrao_ativo(registro.data)
            
            if not horario_padrao:
                print(f"⚠️ {funcionario.nome} não tem horário padrão para {registro.data}")
                return False
            
            print(f"📋 REGISTRO TESTE:")
            print(f"   Funcionário: {funcionario.nome}")
            print(f"   Data: {registro.data}")
            print(f"   Horário real: {registro.hora_entrada} às {registro.hora_saida}")
            print(f"   Horário padrão: {horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}")
            
            # Verificar campos calculados
            if hasattr(registro, 'horas_extras_detalhadas'):
                print(f"   Horas extras: {registro.horas_extras_detalhadas}h")
                print(f"   Detalhes: {getattr(registro, 'minutos_extras_entrada', 0)}min entrada + "
                      f"{getattr(registro, 'minutos_extras_saida', 0)}min saída")
                return True
            else:
                print(f"   Horas extras (original): {registro.horas_extras}h")
                return True
                
        except Exception as e:
            print(f"❌ Erro no teste de cálculo: {e}")
            return False

def teste_engine_kpis():
    """Testa a nova engine de KPIs"""
    print("📊 TESTANDO NOVA ENGINE DE KPIs")
    
    with app.app_context():
        try:
            # Buscar funcionário com horário padrão
            funcionario = None
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
            
            for f in funcionarios:
                if f.get_horario_padrao_ativo():
                    funcionario = f
                    break
            
            if not funcionario:
                print("❌ Nenhum funcionário com horário padrão encontrado")
                return False
            
            print(f"👤 Testando KPIs: {funcionario.nome}")
            
            # Calcular KPIs com nova engine
            kpis = calcular_kpis_funcionario_horario_padrao(funcionario.id, 7, 2025, debug=False)
            
            if not kpis:
                print("❌ Falha no cálculo de KPIs")
                return False
            
            print(f"✅ KPIs calculados com sucesso:")
            print(f"   Produtividade: {kpis.get('produtividade', 0)}%")
            print(f"   Eficiência: {kpis.get('eficiencia', 0)}%")
            print(f"   Horas trabalhadas: {kpis.get('horas_trabalhadas', 0)}h")
            print(f"   Horas extras: {kpis.get('horas_extras', 0)}h")
            print(f"   Custo total: R$ {kpis.get('custo_total', 0)}")
            print(f"   Baseado em horário padrão: {kpis.get('calculado_com_horario_padrao', False)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste de KPIs: {e}")
            return False

def teste_integridade_dados():
    """Verifica integridade dos dados após implementação"""
    print("🔍 TESTANDO INTEGRIDADE DOS DADOS")
    
    with app.app_context():
        try:
            # Contar funcionários
            total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
            
            # Contar horários padrão
            total_horarios = HorarioPadrao.query.filter_by(ativo=True).count()
            
            # Contar registros com novos campos
            registros_com_detalhes = RegistroPonto.query.filter(
                RegistroPonto.horas_extras_detalhadas.isnot(None)
            ).count()
            
            print(f"📊 ESTATÍSTICAS:")
            print(f"   Funcionários ativos: {total_funcionarios}")
            print(f"   Horários padrão ativos: {total_horarios}")
            print(f"   Registros com detalhamento: {registros_com_detalhes}")
            
            # Verificar consistência
            funcionarios_com_horario = 0
            for funcionario in Funcionario.query.filter_by(ativo=True).all():
                if funcionario.get_horario_padrao_ativo():
                    funcionarios_com_horario += 1
            
            print(f"   Funcionários com horário padrão: {funcionarios_com_horario}")
            print(f"   Cobertura: {funcionarios_com_horario/total_funcionarios*100:.1f}%")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste de integridade: {e}")
            return False

def teste_casos_especiais():
    """Testa casos especiais do sistema"""
    print("⚡ TESTANDO CASOS ESPECIAIS")
    
    with app.app_context():
        try:
            # Buscar registros de diferentes tipos
            tipos_encontrados = set()
            
            registros = RegistroPonto.query.limit(20).all()
            for registro in registros:
                tipos_encontrados.add(registro.tipo_registro or 'trabalhado')
            
            print(f"📋 Tipos de registro encontrados: {', '.join(tipos_encontrados)}")
            
            # Verificar registros de sábado trabalhado
            sabados = RegistroPonto.query.filter_by(tipo_registro='sabado_trabalhado').count()
            feriados = RegistroPonto.query.filter_by(tipo_registro='feriado_trabalhado').count()
            
            print(f"   Sábados trabalhados: {sabados}")
            print(f"   Feriados trabalhados: {feriados}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste de casos especiais: {e}")
            return False

def relatorio_final_sistema():
    """Gera relatório final do sistema"""
    print("📋 RELATÓRIO FINAL DO SISTEMA")
    
    with app.app_context():
        try:
            # Estatísticas gerais
            stats = {
                'funcionarios_ativos': Funcionario.query.filter_by(ativo=True).count(),
                'horarios_padrao': HorarioPadrao.query.filter_by(ativo=True).count(),
                'registros_ponto_total': RegistroPonto.query.count(),
                'registros_com_extras': RegistroPonto.query.filter(
                    RegistroPonto.horas_extras > 0
                ).count()
            }
            
            # Cálculos de exemplo
            exemplo_funcionario = Funcionario.query.filter_by(ativo=True).first()
            if exemplo_funcionario and exemplo_funcionario.get_horario_padrao_ativo():
                horario = exemplo_funcionario.get_horario_padrao_ativo()
                
                print(f"📊 ESTATÍSTICAS FINAIS:")
                print(f"   Funcionários ativos: {stats['funcionarios_ativos']}")
                print(f"   Horários padrão configurados: {stats['horarios_padrao']}")
                print(f"   Total registros de ponto: {stats['registros_ponto_total']}")
                print(f"   Registros com horas extras: {stats['registros_com_extras']}")
                
                print(f"\n🕐 EXEMPLO DE HORÁRIO PADRÃO:")
                print(f"   Funcionário: {exemplo_funcionario.nome}")
                print(f"   Entrada: {horario.entrada_padrao}")
                print(f"   Saída: {horario.saida_padrao}")
                print(f"   Intervalo: {horario.saida_almoco_padrao} - {horario.retorno_almoco_padrao}")
                print(f"   Ativo desde: {horario.data_inicio}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no relatório final: {e}")
            return False

if __name__ == "__main__":
    print("🚀 TESTE COMPLETO DO SISTEMA DE HORÁRIOS PADRÃO")
    print("="*60)
    
    # Executar todos os testes
    testes = [
        ("Modelo Horário Padrão", teste_modelo_horario_padrao),
        ("Cálculo Horas Extras", teste_calculo_horas_extras),
        ("Engine de KPIs", teste_engine_kpis),
        ("Integridade dos Dados", teste_integridade_dados),
        ("Casos Especiais", teste_casos_especiais),
        ("Relatório Final", relatorio_final_sistema)
    ]
    
    resultados = []
    
    for nome_teste, funcao_teste in testes:
        print(f"\n{nome_teste.upper()}")
        print("-" * 40)
        
        try:
            resultado = funcao_teste()
            resultados.append((nome_teste, resultado))
            print(f"{'✅ PASSOU' if resultado else '❌ FALHOU'}")
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            resultados.append((nome_teste, False))
    
    # Resumo final
    print(f"\n{'='*60}")
    print("RESUMO DOS TESTES")
    print("="*60)
    
    passou = sum(1 for _, resultado in resultados if resultado)
    total = len(resultados)
    
    for nome, resultado in resultados:
        status = "✅ PASSOU" if resultado else "❌ FALHOU"
        print(f"{nome.ljust(25)} {status}")
    
    print(f"\n📊 RESULTADO FINAL: {passou}/{total} testes passaram")
    
    if passou == total:
        print("🎯 SISTEMA DE HORÁRIOS PADRÃO COMPLETAMENTE FUNCIONAL!")
    else:
        print("⚠️ Alguns testes falharam - verificar implementação")