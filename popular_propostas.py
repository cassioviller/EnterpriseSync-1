#!/usr/bin/env python3

from main import app
from models import *
from datetime import date, datetime, timedelta
import random

def criar_propostas_teste():
    with app.app_context():
        try:
            print("💼 CRIANDO DADOS DE TESTE PARA PROPOSTAS")
            
            # ====== CLIENTES ======
            print("\n👔 CRIANDO CLIENTES:")
            clientes_criados = []
            
            clientes_data = [
                {"nome": "Construtora Moderna Ltda", "cnpj": "12.345.678/0001-99", "email": "contato@moderna.com.br", "telefone": "(11) 99999-0001"},
                {"nome": "Incorporadora Premium", "cnpj": "98.765.432/0001-11", "email": "ana@premium.com.br", "telefone": "(11) 99999-0002"},
                {"nome": "Engenharia & Obras S/A", "cnpj": "11.222.333/0001-44", "email": "roberto@obras.com.br", "telefone": "(11) 99999-0003"}
            ]
            
            for cliente_data in clientes_data:
                cliente = Cliente(
                    nome=cliente_data["nome"],
                    cnpj=cliente_data["cnpj"],
                    email=cliente_data["email"],
                    telefone=cliente_data["telefone"],
                    admin_id=10
                )
                db.session.add(cliente)
                clientes_criados.append(cliente)
                print(f"   ✓ {cliente_data['nome']}")
            
            db.session.commit()
            
            # ====== TEMPLATES DE PROPOSTAS ======
            print("\n📄 CRIANDO TEMPLATES DE PROPOSTAS:")
            templates_criados = []
            
            templates_data = [
                {
                    "nome": "Fundação e Estrutura",
                    "categoria": "Construção",
                    "descricao": "Template para serviços de fundação e estrutura",
                    "itens_padrao": [
                        {"descricao": "Escavação e preparo do terreno", "valor": 5000.00, "unidade": "m²"},
                        {"descricao": "Fundação em concreto armado", "valor": 12000.00, "unidade": "m³"},
                        {"descricao": "Estrutura de pilares e vigas", "valor": 18000.00, "unidade": "m³"}
                    ]
                },
                {
                    "nome": "Acabamentos e Pintura", 
                    "categoria": "Acabamento",
                    "descricao": "Template para serviços de acabamento",
                    "itens_padrao": [
                        {"descricao": "Reboco interno e externo", "valor": 3500.00, "unidade": "m²"},
                        {"descricao": "Pintura interna (látex)", "valor": 2800.00, "unidade": "m²"},
                        {"descricao": "Pintura externa (acrílica)", "valor": 3200.00, "unidade": "m²"}
                    ]
                },
                {
                    "nome": "Instalações Básicas",
                    "categoria": "Instalações", 
                    "descricao": "Template para instalações elétricas e hidráulicas",
                    "itens_padrao": [
                        {"descricao": "Instalação elétrica completa", "valor": 8500.00, "unidade": "un"},
                        {"descricao": "Instalação hidráulica", "valor": 6200.00, "unidade": "un"},
                        {"descricao": "Instalação de gás", "valor": 3400.00, "unidade": "un"}
                    ]
                }
            ]
            
            for template_data in templates_data:
                template = PropostaTemplate(
                    nome=template_data["nome"],
                    categoria=template_data["categoria"],
                    descricao=template_data["descricao"],
                    ativo=True,
                    admin_id=10,
                    criado_por=10,
                    criado_em=datetime.now()
                )
                db.session.add(template)
                templates_criados.append(template)
                print(f"   ✓ {template_data['nome']}")
            
            db.session.commit()
            
            # ====== PROPOSTAS ======
            print("\n💰 CRIANDO PROPOSTAS:")
            
            import time
            timestamp_suffix = str(int(time.time()))[-4:]
            
            propostas_criadas = []
            
            propostas_data = [
                {
                    "numero": f"PROP-{timestamp_suffix}-001",
                    "cliente": clientes_criados[0],
                    "titulo": "Construção Residencial - Casa Moderna",
                    "valor_total": 85000.00,
                    "status": "RASCUNHO"
                },
                {
                    "numero": f"PROP-{timestamp_suffix}-002", 
                    "cliente": clientes_criados[1],
                    "titulo": "Acabamento - Edifício Comercial",
                    "valor_total": 45000.00,
                    "status": "ENVIADA"
                },
                {
                    "numero": f"PROP-{timestamp_suffix}-003",
                    "cliente": clientes_criados[2], 
                    "titulo": "Reforma e Instalações - Galpão Industrial",
                    "valor_total": 125000.00,
                    "status": "APROVADA"
                }
            ]
            
            for proposta_data in propostas_data:
                # Usar SQL direto para evitar incompatibilidades do modelo
                from sqlalchemy import text
                sql = text("""
                INSERT INTO propostas_comerciais (numero_proposta, data_proposta, cliente_nome, assunto, valor_total, status, admin_id, criado_em)
                VALUES (:numero_proposta, :data_proposta, :cliente_nome, :assunto, :valor_total, :status, :admin_id, :criado_em)
                RETURNING id
                """)
                
                result = db.session.execute(sql, {
                    'numero_proposta': proposta_data["numero"],
                    'data_proposta': date.today(),
                    'cliente_nome': proposta_data["cliente"].nome,
                    'assunto': proposta_data["titulo"],
                    'valor_total': proposta_data["valor_total"],
                    'status': proposta_data["status"],
                    'admin_id': 10,
                    'criado_em': datetime.now()
                })
                proposta_id = result.fetchone()[0]
                propostas_criadas.append({'id': proposta_id, 'numero': proposta_data["numero"]})
                print(f"   ✓ {proposta_data['titulo']} - R$ {proposta_data['valor_total']:,.2f}")
            
            db.session.commit()
            
            # ====== ITENS DAS PROPOSTAS ======
            print("\n📋 CRIANDO ITENS DAS PROPOSTAS:")
            
            # Adicionar itens para cada proposta
            for i, proposta_dict in enumerate(propostas_criadas):
                template_itens = templates_data[i]["itens_padrao"]
                
                for j, item_data in enumerate(template_itens):
                    # Usar SQL direto também para os itens
                    item_sql = text("""
                    INSERT INTO proposta_itens (proposta_id, item_numero, descricao, quantidade, preco_unitario, unidade, ordem)
                    VALUES (:proposta_id, :item_numero, :descricao, :quantidade, :preco_unitario, :unidade, :ordem)
                    """)
                    
                    db.session.execute(item_sql, {
                        'proposta_id': proposta_dict['id'],
                        'item_numero': j + 1,  # Campo obrigatório
                        'descricao': item_data["descricao"],
                        'quantidade': 1.0,
                        'preco_unitario': item_data["valor"],
                        'unidade': item_data["unidade"],
                        'ordem': j + 1
                    })
                
                print(f"   ✓ {len(templates_data[i]['itens_padrao'])} itens para {proposta_dict['numero']}")
            
            db.session.commit()
            
            print(f"""
✅ DADOS DE TESTE PARA PROPOSTAS CRIADOS COM SUCESSO!

📊 RESUMO:
   👔 {len(clientes_criados)} Clientes
   📄 {len(templates_criados)} Templates
   💰 {len(propostas_criadas)} Propostas
   
🎯 IDENTIFICAÇÃO DOS DADOS:
   Sufixo timestamp: {timestamp_suffix}
   Números: PROP-{timestamp_suffix}-XXX
   
💼 VALORES TOTAIS:
   {propostas_data[0]['titulo']}: R$ {propostas_data[0]['valor_total']:,.2f}
   {propostas_data[1]['titulo']}: R$ {propostas_data[1]['valor_total']:,.2f}
   {propostas_data[2]['titulo']}: R$ {propostas_data[2]['valor_total']:,.2f}
   
✅ PROPOSTAS PRONTAS PARA TESTES!
            """)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    criar_propostas_teste()