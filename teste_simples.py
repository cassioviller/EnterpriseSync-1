#!/usr/bin/env python3
"""
Script Simplificado para Teste de Custos SIGE v8.0
Cria funcionários, obra e registros para validar cálculos
"""

import sys
sys.path.append('.')
from models import *
from datetime import datetime, date, timedelta
import random

# Conectar ao banco
from app import app, db

def main():
    """Função principal do teste simplificado"""
    with app.app_context():
        try:
            print('🎯 TESTE SIMPLIFICADO SIGE v8.0')
            print('=' * 50)
            
            # 1. Buscar obra existente ou usar uma disponível
            obra = Obra.query.filter_by(admin_id=10).first()
            if not obra:
                print('❌ Nenhuma obra encontrada!')
                return
            
            print(f'✅ Usando obra: {obra.nome} (ID: {obra.id})')
            
            # 2. Buscar funcionários existentes
            funcionarios = Funcionario.query.filter_by(admin_id=10, ativo=True).limit(3).all()
            if len(funcionarios) < 3:
                print('❌ Menos de 3 funcionários encontrados!')
                return
            
            print(f'✅ Usando funcionários: {[f.nome for f in funcionarios]}')
            
            # 3. Limpar dados de teste antigos (setembro 2025)
            data_inicio = date(2025, 9, 1)
            data_fim = date(2025, 9, 30)
            
            # Limpar RDOs de teste (usando filter simples devido a limitação SQLAlchemy)
            rdos_teste = RDO.query.filter_by(obra_id=obra.id).all()
            rdos_teste = [r for r in rdos_teste if r.data >= data_inicio and r.data <= data_fim and 'teste' in (r.observacoes or '')]
            
            for rdo in rdos_teste:
                # Limpar registros relacionados
                RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
                db.session.delete(rdo)
            
            # Limpar pontos de teste
            pontos_teste = RegistroPonto.query.filter_by(obra_id=obra.id).all()
            for ponto in pontos_teste:
                if ponto.data >= data_inicio and ponto.data <= data_fim:
                    db.session.delete(ponto)
            
            # Limpar alimentação de teste  
            alimentacao_teste = RegistroAlimentacao.query.filter_by(obra_id=obra.id).all()
            for alim in alimentacao_teste:
                if alim.data >= data_inicio and alim.data <= data_fim and 'teste' in (alim.observacoes or ''):
                    db.session.delete(alim)
            
            # Limpar transporte de teste
            transporte_teste = OutroCusto.query.filter_by(obra_id=obra.id).all()
            for trans in transporte_teste:
                if trans.data >= data_inicio and trans.data <= data_fim and 'teste' in (trans.descricao or ''):
                    db.session.delete(trans)
            
            db.session.commit()
            print('✅ Dados de teste antigos limpos')
            
            # 4. Criar registros para uma semana (5 dias úteis)
            semana_inicio = date(2025, 9, 2)  # Segunda-feira
            semana_fim = date(2025, 9, 6)     # Sexta-feira
            
            data_atual = semana_inicio
            rdos_criados = 0
            pontos_criados = 0
            alimentacao_criados = 0
            transporte_criados = 0
            
            while data_atual <= semana_fim:
                print(f'📅 Criando registros para {data_atual.strftime("%d/%m/%Y")}')
                
                # Criar RDO
                rdo = RDO(
                    obra_id=obra.id,
                    data=data_atual,
                    clima='Ensolarado',
                    local='Campo',
                    atividades_executadas=f'Teste de validação SIGE - {data_atual.strftime("%d/%m/%Y")}',
                    materiais_utilizados='Materiais teste',
                    observacoes='RDO teste para validação custos',
                    admin_id=10
                )
                db.session.add(rdo)
                db.session.flush()
                rdos_criados += 1
                
                # Para cada funcionário
                for funcionario in funcionarios:
                    # Horas trabalhadas (7-9h)
                    horas_trabalhadas = round(random.uniform(7.0, 9.0), 1)
                    
                    # Adicionar ao RDO
                    rdo_mao_obra = RDOMaoObra(
                        rdo_id=rdo.id,
                        funcionario_id=funcionario.id,
                        horas_trabalhadas=horas_trabalhadas,
                        atividade='Atividades teste'
                    )
                    db.session.add(rdo_mao_obra)
                    
                    # Criar ponto
                    entrada = datetime.combine(data_atual, datetime.min.time().replace(hour=7, minute=30))
                    saida_almoco = datetime.combine(data_atual, datetime.min.time().replace(hour=11, minute=30))
                    volta_almoco = datetime.combine(data_atual, datetime.min.time().replace(hour=12, minute=30))
                    saida = datetime.combine(data_atual, datetime.min.time().replace(hour=17, minute=0))
                    
                    registro_ponto = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        entrada=entrada,
                        saida_almoco=saida_almoco,
                        volta_almoco=volta_almoco,
                        saida=saida,
                        obra_id=obra.id,
                        admin_id=10
                    )
                    db.session.add(registro_ponto)
                    pontos_criados += 1
                    
                    # Alimentação (R$ 20)
                    alimentacao = RegistroAlimentacao(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo_refeicao='Almoço',
                        valor=20.00,
                        obra_id=obra.id,
                        observacoes='Alimentação teste SIGE',
                        admin_id=10
                    )
                    db.session.add(alimentacao)
                    alimentacao_criados += 1
                    
                    # Transporte (R$ 12)
                    transporte = OutroCusto(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo='Transporte',
                        descricao='Vale transporte teste SIGE',
                        valor=12.00,
                        obra_id=obra.id,
                        admin_id=10
                    )
                    db.session.add(transporte)
                    transporte_criados += 1
                
                data_atual += timedelta(days=1)
            
            # Commit final
            db.session.commit()
            
            print('=' * 50)
            print('🎉 TESTE SIMPLIFICADO CONCLUÍDO!')
            print(f'📊 Período: {semana_inicio.strftime("%d/%m/%Y")} a {semana_fim.strftime("%d/%m/%Y")}')
            print(f'🏗️  Obra: {obra.nome} (ID: {obra.id})')
            print(f'👥 Funcionários: {len(funcionarios)}')
            print(f'📋 RDOs criados: {rdos_criados}')
            print(f'⏰ Pontos criados: {pontos_criados}')
            print(f'🍽️  Alimentação: {alimentacao_criados}')
            print(f'🚌 Transporte: {transporte_criados}')
            print('')
            print('💰 VALORES ESPERADOS POR DIA:')
            for funcionario in funcionarios:
                salario_diario = (funcionario.salario or 2000) / 22  # 22 dias úteis
                print(f'  {funcionario.nome}: R$ {salario_diario:.2f} (mão de obra) + R$ 20,00 (alimentação) + R$ 12,00 (transporte)')
            
            total_mao_obra = sum([(f.salario or 2000) / 22 for f in funcionarios]) * 5  # 5 dias
            total_alimentacao = len(funcionarios) * 20 * 5  # 5 dias
            total_transporte = len(funcionarios) * 12 * 5   # 5 dias
            total_geral = total_mao_obra + total_alimentacao + total_transporte
            
            print('')
            print('📊 TOTAIS ESPERADOS (5 dias):')
            print(f'  Mão de obra: R$ {total_mao_obra:.2f}')
            print(f'  Alimentação: R$ {total_alimentacao:.2f}')
            print(f'  Transporte: R$ {total_transporte:.2f}')
            print(f'  TOTAL: R$ {total_geral:.2f}')
            print('')
            print('🔍 Verificar estes valores na página de detalhes da obra!')
            
        except Exception as e:
            db.session.rollback()
            print(f'❌ ERRO: {str(e)}')
            raise

if __name__ == '__main__':
    main()