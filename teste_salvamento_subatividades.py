#!/usr/bin/env python3
"""
Teste específico para validar salvamento de subatividades RDO
Simula exatamente os dados que o usuário preencheu manualmente
"""

import requests
import json
from datetime import date

def testar_salvamento_direto():
    """Teste direto no banco de dados para verificar salvamento"""
    from app import app, db
    from models import RDO, RDOServicoSubatividade, Obra
    
    with app.app_context():
        print("🧪 TESTE DE SALVAMENTO DIRETO NO BANCO")
        print("=" * 50)
        
        # Simular salvamento direto das subatividades que o usuário preencheu
        obra_id = 40
        
        # Buscar ou criar RDO de teste
        rdo_teste = RDO.query.filter_by(
            obra_id=obra_id,
            data_relatorio=date.today()
        ).first()
        
        if not rdo_teste:
            rdo_teste = RDO()
            rdo_teste.obra_id = obra_id
            rdo_teste.numero_rdo = f"RDO-TESTE-{date.today().strftime('%Y%m%d')}"
            rdo_teste.data_relatorio = date.today()
            rdo_teste.status = 'Rascunho'
            rdo_teste.admin_id = 10
            rdo_teste.criado_por_id = 15  # Funcionário padrão
            db.session.add(rdo_teste)
            db.session.flush()
            print(f"✅ RDO de teste criado: {rdo_teste.numero_rdo} (ID: {rdo_teste.id})")
        else:
            # Limpar subatividades existentes para teste limpo
            RDOServicoSubatividade.query.filter_by(rdo_id=rdo_teste.id).delete()
            print(f"♻️ RDO existente limpo: {rdo_teste.numero_rdo} (ID: {rdo_teste.id})")
        
        # Simular exatamente os dados que o usuário preencheu
        subatividades_usuario = [
            {
                'nome': 'Montagem de Pilares',
                'percentual': 100.0,
                'observacoes': 'Concluído conforme especificação técnica',
                'servico_id': 58  # Estrutura Metálica
            },
            {
                'nome': 'Instalação de Vigas',
                'percentual': 100.0, 
                'observacoes': 'Vigas instaladas e alinhadas corretamente',
                'servico_id': 58  # Estrutura Metálica
            },
            {
                'nome': 'Soldagem de bases',
                'percentual': 100.0,
                'observacoes': 'Soldagem executada por profissional qualificado',
                'servico_id': 59  # Soldagem Especializada
            }
        ]
        
        # Salvar subatividades no banco
        for sub_data in subatividades_usuario:
            rdo_subatividade = RDOServicoSubatividade()
            rdo_subatividade.rdo_id = rdo_teste.id
            rdo_subatividade.nome_subatividade = sub_data['nome']
            rdo_subatividade.percentual_conclusao = sub_data['percentual']
            rdo_subatividade.observacoes_tecnicas = sub_data['observacoes']
            rdo_subatividade.servico_id = sub_data['servico_id']
            rdo_subatividade.admin_id = 10
            
            db.session.add(rdo_subatividade)
            print(f"💾 Subatividade salva: {sub_data['nome']} - {sub_data['percentual']}%")
        
        try:
            db.session.commit()
            print("✅ COMMIT realizado com sucesso!")
            
            # Verificar se foi salvo
            subatividades_salvas = RDOServicoSubatividade.query.filter_by(rdo_id=rdo_teste.id).all()
            print(f"✅ Verificação: {len(subatividades_salvas)} subatividades encontradas no banco")
            
            for i, sub in enumerate(subatividades_salvas, 1):
                print(f"   {i}. {sub.nome_subatividade}: {sub.percentual_conclusao}%")
                print(f"      Obs: {sub.observacoes_tecnicas[:50]}...")
                print(f"      Serviço ID: {sub.servico_id}")
            
            return True, rdo_teste.id
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ ERRO no commit: {e}")
            return False, None

def testar_api_carregamento(rdo_id):
    """Testar se a API de carregamento funciona corretamente"""
    print("\n📡 TESTE DA API DE CARREGAMENTO")
    print("=" * 50)
    
    url = f"http://localhost:5000/api/test/rdo/ultimo-rdo-dados/40"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Success: {data.get('success', False)}")
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Total Subatividades: {data.get('total_subatividades', 0)}")
        
        if data.get('success') and data.get('subatividades'):
            print("✅ SUBATIVIDADES CARREGADAS:")
            for i, sub in enumerate(data['subatividades'], 1):
                print(f"   {i}. {sub.get('nome_subatividade', 'N/A')}: {sub.get('percentual_conclusao', 0)}%")
                print(f"      Serviço: {sub.get('servico_nome', 'N/A')}")
            return True
        else:
            print("❌ API não carregou subatividades")
            return False
            
    except Exception as e:
        print(f"❌ ERRO na API: {e}")
        return False

def testar_fluxo_completo():
    """Testar fluxo completo: salvar → carregar → verificar"""
    print("\n🔄 TESTE DO FLUXO COMPLETO")
    print("=" * 50)
    
    print("ETAPA 1: Salvamento direto...")
    salvou, rdo_id = testar_salvamento_direto()
    
    if not salvou:
        print("❌ Falha no salvamento - interrompendo teste")
        return False
    
    print("\nETAPA 2: Carregamento via API...")
    carregou = testar_api_carregamento(rdo_id)
    
    if not carregou:
        print("❌ Falha no carregamento - API não funciona")
        return False
    
    print("\n✅ FLUXO COMPLETO FUNCIONANDO!")
    print("   1. Dados são salvos corretamente no banco")
    print("   2. API carrega os dados salvos")
    print("   3. Frontend deveria receber os dados")
    
    return True

def identificar_problema_frontend():
    """Identificar se o problema está no frontend"""
    print("\n🎯 DIAGNÓSTICO DO PROBLEMA FRONTEND")
    print("=" * 50)
    
    print("❓ POSSÍVEIS CAUSAS NO FRONTEND:")
    print("1. Campos do formulário com nomes incorretos")
    print("2. JavaScript não processando corretamente os dados da API")
    print("3. Template não renderizando os campos corretos")
    print("4. Conflict entre dados manuais e automáticos")
    
    print("\n💡 VERIFICAÇÕES SUGERIDAS:")
    print("1. Inspecionar elementos na página criar RDO")
    print("2. Verificar nomes dos campos: name='nome_subatividade_1', etc.")
    print("3. Conferir se JavaScript preenche campos corretamente")
    print("4. Testar submissão do formulário com dados manuais")

def main():
    print("🚨 TESTE COMPLETO DE SALVAMENTO DE SUBATIVIDADES RDO")
    print("=" * 60)
    
    # Executar teste completo
    sucesso = testar_fluxo_completo()
    
    if sucesso:
        print("\n🎉 CONCLUSÃO: Sistema de banco de dados está funcionando!")
        print("📋 O problema deve estar no frontend/template")
        identificar_problema_frontend()
    else:
        print("\n⚠️ PROBLEMA IDENTIFICADO no sistema de salvamento")
    
    print("\n📝 PRÓXIMAS AÇÕES:")
    print("1. Se teste passou: verificar template novo.html")
    print("2. Se teste falhou: corrigir lógica de salvamento") 
    print("3. Testar manualmente: criar RDO → preencher → salvar")

if __name__ == "__main__":
    main()