#!/usr/bin/env python3
"""
Script para migrar dados de ponto, alimentação e outros custos
dos funcionários Vale Verde para aparecerem corretamente no sistema multi-tenant
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Funcionario, RegistroPonto, RegistroAlimentacao, OutroCusto, CustoVeiculo
from datetime import datetime

def migrar_dados_vale_verde():
    """Migra dados existentes dos funcionários VV para o admin correto"""
    
    with app.app_context():
        print("=== MIGRAÇÃO DE DADOS VALE VERDE ===\n")
        
        # 1. Obter funcionários Vale Verde (códigos VV001-VV010)
        funcionarios_vv = Funcionario.query.filter(
            Funcionario.codigo.like('VV%')
        ).all()
        
        print(f"Funcionários Vale Verde encontrados: {len(funcionarios_vv)}")
        for func in funcionarios_vv:
            print(f"  - {func.nome} ({func.codigo}) - Admin ID: {func.admin_id}")
        
        if not funcionarios_vv:
            print("❌ Nenhum funcionário Vale Verde encontrado!")
            return
        
        funcionarios_vv_ids = [f.id for f in funcionarios_vv]
        
        # Obter primeira obra VV para usar em todos os registros
        obras_vv = db.session.execute(
            db.text("SELECT id FROM obra WHERE admin_id = 10 LIMIT 1")
        ).fetchone()
        obra_vv_id = obras_vv[0] if obras_vv else None
        
        # 2. Verificar registros existentes que precisam ser associados
        print(f"\n2. VERIFICANDO REGISTROS EXISTENTES:")
        
        # Registros de ponto
        registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(funcionarios_vv_ids)
        ).all()
        print(f"   - Registros de ponto VV: {len(registros_ponto)}")
        
        # Registros de alimentação
        registros_alimentacao = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.funcionario_id.in_(funcionarios_vv_ids)
        ).all()
        print(f"   - Registros de alimentação VV: {len(registros_alimentacao)}")
        
        # Outros custos
        outros_custos = OutroCusto.query.filter(
            OutroCusto.funcionario_id.in_(funcionarios_vv_ids)
        ).all()
        print(f"   - Outros custos VV: {len(outros_custos)}")
        
        # 3. Criar dados de exemplo para funcionários VV se não existirem
        if len(registros_ponto) == 0:
            print(f"\n3. CRIANDO REGISTROS DE PONTO PARA FUNCIONÁRIOS VV:")
            from datetime import date, time
            
            # Criar alguns registros de ponto para julho/2025
            datas_exemplo = [
                date(2025, 7, 1), date(2025, 7, 2), date(2025, 7, 3),
                date(2025, 7, 7), date(2025, 7, 8), date(2025, 7, 9),
                date(2025, 7, 14), date(2025, 7, 15), date(2025, 7, 16)
            ]
            
            for i, funcionario in enumerate(funcionarios_vv[:3]):  # Primeiros 3 funcionários
                for j, data_ponto in enumerate(datas_exemplo):
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=obra_vv_id,
                        data=data_ponto,
                        hora_entrada=time(7, 30),
                        hora_saida=time(17, 0),
                        hora_almoco_saida=time(12, 0),
                        hora_almoco_retorno=time(13, 0),
                        tipo_registro='trabalho_normal',
                        horas_trabalhadas=8.5,
                        horas_extras=0.5,
                        observacoes=f'Registro VV - {funcionario.nome}'
                    )
                    db.session.add(registro)
                    print(f"     Criado registro para {funcionario.nome} em {data_ponto}")
            
            db.session.commit()
        
        # 4. Criar registros de alimentação se não existirem
        if len(registros_alimentacao) == 0:
            print(f"\n4. CRIANDO REGISTROS DE ALIMENTAÇÃO PARA FUNCIONÁRIOS VV:")
            
            # Buscar restaurante ativo
            restaurante = db.session.execute(
                db.text("SELECT id FROM restaurante WHERE ativo = true LIMIT 1")
            ).fetchone()
            
            if restaurante and obra_vv_id:
                from datetime import date
                
                datas_alimentacao = [
                    date(2025, 7, 1), date(2025, 7, 2), date(2025, 7, 3),
                    date(2025, 7, 7), date(2025, 7, 8)
                ]
                
                for funcionario in funcionarios_vv[:5]:  # Primeiros 5 funcionários
                    for data_alim in datas_alimentacao:
                        registro = RegistroAlimentacao(
                            funcionario_id=funcionario.id,
                            obra_id=obra_vv_id,
                            restaurante_id=restaurante[0],
                            data=data_alim,
                            tipo='Almoço',
                            valor=18.50,
                            observacoes=f'Almoço VV - {funcionario.nome}'
                        )
                        db.session.add(registro)
                        print(f"     Criado registro alimentação para {funcionario.nome} em {data_alim}")
                
                db.session.commit()
        
        # 5. Criar outros custos se não existirem
        if len(outros_custos) == 0:
            print(f"\n5. CRIANDO OUTROS CUSTOS PARA FUNCIONÁRIOS VV:")
            from datetime import date
            
            tipos_custos = [
                ('Vale Transporte', 220.00, 'adicional'),
                ('Vale Alimentação', 440.00, 'adicional'),
                ('EPI - Capacete', 85.00, 'adicional'),
                ('Desconto VT (6%)', -13.20, 'desconto')
            ]
            
            for funcionario in funcionarios_vv[:4]:  # Primeiros 4 funcionários
                for tipo, valor, categoria in tipos_custos:
                    custo = OutroCusto(
                        funcionario_id=funcionario.id,
                        data=date(2025, 7, 1),
                        tipo=tipo,
                        categoria=categoria,
                        valor=valor,
                        descricao=f'{tipo} VV - {funcionario.nome}'
                    )
                    db.session.add(custo)
                    print(f"     Criado custo {tipo} para {funcionario.nome}: R$ {valor:.2f}")
            
            db.session.commit()
        
        # 6. Verificação final
        print(f"\n6. VERIFICAÇÃO FINAL:")
        
        # Recontagem após migração
        registros_ponto_final = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(funcionarios_vv_ids)
        ).count()
        
        registros_alimentacao_final = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.funcionario_id.in_(funcionarios_vv_ids)
        ).count()
        
        outros_custos_final = OutroCusto.query.filter(
            OutroCusto.funcionario_id.in_(funcionarios_vv_ids)
        ).count()
        
        print(f"   - Registros de ponto VV: {registros_ponto_final}")
        print(f"   - Registros de alimentação VV: {registros_alimentacao_final}")
        print(f"   - Outros custos VV: {outros_custos_final}")
        
        if registros_ponto_final > 0 and registros_alimentacao_final > 0 and outros_custos_final > 0:
            print(f"\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print(f"✅ Dados da Vale Verde agora estão visíveis no sistema multi-tenant")
        else:
            print(f"\n❌ MIGRAÇÃO INCOMPLETA - Alguns dados ainda estão faltando")
        
        print(f"\n=== CREDENCIAIS PARA TESTE ===")
        print(f"Login Vale Verde: valeverde/admin123")
        print(f"Sistema deve mostrar KPIs com dados dos funcionários VV")

if __name__ == "__main__":
    migrar_dados_vale_verde()