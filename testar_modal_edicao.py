#!/usr/bin/env python3
"""
🔧 TESTE: Modal de edição de registro de ponto
Verificar se o endpoint está funcionando corretamente
"""

from app import app, db
from models import RegistroPonto, Funcionario
import requests
from datetime import date

def testar_endpoint_edicao():
    """Testar endpoint de edição via requisição"""
    print("🧪 TESTE: Endpoint de edição de registro")
    print("=" * 60)
    
    with app.app_context():
        # Buscar um registro existente
        registro = RegistroPonto.query.first()
        if not registro:
            print("❌ Nenhum registro encontrado")
            return
        
        print(f"📋 Testando registro ID: {registro.id}")
        print(f"   Funcionário: {registro.funcionario_ref.nome}")
        print(f"   Data: {registro.data}")
        print(f"   Tipo: {registro.tipo_registro}")
        
        # Simular requisição GET
        try:
            with app.test_client() as client:
                # Login simulado (pode ser necessário ajustar)
                response = client.get(f'/ponto/registro/{registro.id}')
                
                print(f"📡 Status: {response.status_code}")
                print(f"📄 Content-Type: {response.content_type}")
                
                if response.status_code == 200:
                    if response.is_json:
                        data = response.get_json()
                        print("✅ JSON válido retornado:")
                        print(f"   Success: {data.get('success')}")
                        if data.get('registro'):
                            reg = data['registro']
                            print(f"   Funcionário: {reg.get('funcionario', {}).get('nome')}")
                            print(f"   Data: {reg.get('data_formatada')}")
                            print(f"   Horários: {reg.get('horarios')}")
                            print(f"   Obras disponíveis: {len(data.get('obras_disponiveis', []))}")
                        else:
                            print("❌ Campo 'registro' não encontrado")
                    else:
                        print("❌ Resposta não é JSON")
                        print(f"Conteúdo: {response.data.decode()[:200]}")
                else:
                    print(f"❌ Erro HTTP {response.status_code}")
                    print(f"Resposta: {response.data.decode()[:200]}")
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")

def verificar_funcoes_auxiliares():
    """Verificar se todas as funções auxiliares existem"""
    print(f"\n🔍 VERIFICAÇÃO: Funções auxiliares")
    print("=" * 60)
    
    try:
        from views import (
            serializar_registro_completo, 
            obter_obras_usuario,
            obter_tipos_registro_validos,
            verificar_permissao_edicao_ponto
        )
        print("✅ Todas as funções auxiliares importadas com sucesso")
        
        # Testar tipos de registro
        tipos = obter_tipos_registro_validos()
        print(f"✅ Tipos de registro: {len(tipos)} encontrados")
        
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
    except Exception as e:
        print(f"❌ Erro geral: {e}")

def simular_dados_edicao():
    """Simular como os dados deveriam aparecer no frontend"""
    print(f"\n📊 SIMULAÇÃO: Dados de edição")
    print("=" * 60)
    
    with app.app_context():
        registro = RegistroPonto.query.first()
        if not registro:
            print("❌ Nenhum registro encontrado")
            return
        
        funcionario = registro.funcionario_ref
        
        # Simular estrutura de dados
        dados_simulados = {
            'success': True,
            'registro': {
                'id': registro.id,
                'funcionario': {
                    'id': funcionario.id,
                    'nome': funcionario.nome,
                    'codigo': funcionario.codigo
                },
                'data': registro.data.strftime('%Y-%m-%d'),
                'data_formatada': registro.data.strftime('%d/%m/%Y'),
                'tipo_registro': registro.tipo_registro,
                'horarios': {
                    'entrada': registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else '',
                    'almoco_saida': registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else '',
                    'almoco_retorno': registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else '',
                    'saida': registro.hora_saida.strftime('%H:%M') if registro.hora_saida else ''
                },
                'valores_calculados': {
                    'horas_trabalhadas': float(registro.horas_trabalhadas or 0),
                    'horas_extras': float(registro.horas_extras or 0),
                    'percentual_extras': float(registro.percentual_extras or 0)
                },
                'obra_id': registro.obra_id,
                'observacoes': registro.observacoes or ''
            },
            'obras_disponiveis': [
                {'id': 1, 'nome': 'Obra Teste 1'},
                {'id': 2, 'nome': 'Obra Teste 2'}
            ]
        }
        
        print("📋 ESTRUTURA CORRETA DOS DADOS:")
        print(f"   ID: {dados_simulados['registro']['id']}")
        print(f"   Funcionário: {dados_simulados['registro']['funcionario']['nome']}")
        print(f"   Data: {dados_simulados['registro']['data_formatada']}")
        print(f"   Entrada: {dados_simulados['registro']['horarios']['entrada']}")
        print(f"   Saída: {dados_simulados['registro']['horarios']['saida']}")
        print(f"   Obras: {len(dados_simulados['obras_disponiveis'])}")
        
        return dados_simulados

if __name__ == "__main__":
    print("🧪 DIAGNÓSTICO COMPLETO: Modal de edição de ponto")
    print("=" * 80)
    
    # 1. Testar endpoint
    testar_endpoint_edicao()
    
    # 2. Verificar funções
    verificar_funcoes_auxiliares()
    
    # 3. Simular dados
    dados = simular_dados_edicao()
    
    print(f"\n🎯 RESUMO:")
    print(f"   Endpoint testado")
    print(f"   Funções verificadas")
    print(f"   Estrutura de dados simulada")
    print(f"\n✅ Se todos os testes passaram, o modal deveria funcionar")
    print(f"❌ Se algum teste falhou, há problema no backend")