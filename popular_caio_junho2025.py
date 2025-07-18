#!/usr/bin/env python3
"""
Script para popular mês completo de junho/2025 para Caio Fabio Silva de Azevedo
"""

from app import app
from datetime import date, datetime, time

def popular_caio_junho():
    with app.app_context():
        from models import db, Funcionario, RegistroPonto, OutroCusto, RegistroAlimentacao
        
        print("=== POPULANDO JUNHO/2025 PARA CAIO FABIO ===")
        
        # Buscar funcionário
        caio = Funcionario.query.filter_by(nome="Caio Fabio Silva de Azevedo").first()
        if not caio:
            print("   - Funcionário não encontrado!")
            return
        
        print(f"   - Funcionário: {caio.nome} ({caio.codigo})")
        print(f"   - ID: {caio.id}")
        
        # Limpar registros existentes de junho/2025
        RegistroPonto.query.filter_by(funcionario_id=caio.id).filter(
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).delete()
        
        OutroCusto.query.filter_by(funcionario_id=caio.id).filter(
            OutroCusto.data >= date(2025, 6, 1),
            OutroCusto.data <= date(2025, 6, 30)
        ).delete()
        
        RegistroAlimentacao.query.filter_by(funcionario_id=caio.id).filter(
            RegistroAlimentacao.data >= date(2025, 6, 1),
            RegistroAlimentacao.data <= date(2025, 6, 30)
        ).delete()
        
        db.session.commit()
        print("   - Registros anteriores limpos")
        
        # Criar registros de ponto para junho/2025
        registros_ponto = []
        
        # Semana 1: 1-7 junho (dom-sab)
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 2), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 3), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 4), tipo_registro="trabalho_normal", hora_entrada=time(7, 25), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.6, horas_extras=0.0, total_atraso_horas=0.22, total_atraso_minutos=13, observacoes="13min atraso entrada"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 5), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 6), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(16, 45), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.55, horas_extras=0.0, total_atraso_horas=0.25, total_atraso_minutos=15, observacoes="15min saída antecipada"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 7), tipo_registro="sabado_horas_extras", hora_entrada=time(7, 12), hora_saida=time(13, 0), hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=5.8, horas_extras=5.8, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Sábado - horas extras"))
        
        # Semana 2: 8-14 junho (dom-sab)
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 9), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 10), tipo_registro="falta", hora_entrada=None, hora_saida=None, hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=0.0, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Falta não justificada"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 11), tipo_registro="falta_justificada", hora_entrada=None, hora_saida=None, hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=0.0, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Consulta médica"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 12), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 13), tipo_registro="meio_periodo", hora_entrada=time(7, 12), hora_saida=time(12, 0), hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=4.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Meio período - manhã"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 14), tipo_registro="sabado_horas_extras", hora_entrada=time(7, 12), hora_saida=time(12, 0), hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=4.8, horas_extras=4.8, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Sábado - horas extras"))
        
        # Semana 3: 15-21 junho (dom-sab)
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 15), tipo_registro="domingo_horas_extras", hora_entrada=time(8, 0), hora_saida=time(14, 0), hora_almoco_saida=None, hora_almoco_retorno=None, horas_trabalhadas=6.0, horas_extras=6.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Domingo - horas extras"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 16), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 17), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 18), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 19), tipo_registro="feriado_trabalhado", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=8.8, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes="Corpus Christi trabalhado"))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 20), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        
        # Semana 4: 22-28 junho (dom-sab)
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 23), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 24), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 25), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 26), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 27), tipo_registro="trabalho_normal", hora_entrada=time(7, 30), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.5, horas_extras=0.0, total_atraso_horas=0.3, total_atraso_minutos=18, observacoes="18min atraso entrada"))
        
        # Semana 5: 29-30 junho (dom-seg)
        registros_ponto.append(RegistroPonto(funcionario_id=caio.id, data=date(2025, 6, 30), tipo_registro="trabalho_normal", hora_entrada=time(7, 12), hora_saida=time(17, 0), hora_almoco_saida=time(12, 0), hora_almoco_retorno=time(13, 0), horas_trabalhadas=8.8, horas_extras=0.0, total_atraso_horas=0.0, total_atraso_minutos=0, observacoes=""))
        
        # Adicionar todos os registros
        for registro in registros_ponto:
            db.session.add(registro)
        
        db.session.commit()
        print(f"   - Registros de ponto criados: {len(registros_ponto)}")
        
        # Criar outros custos
        outros_custos = [
            OutroCusto(funcionario_id=caio.id, data=date(2025, 6, 1), tipo="Vale Transporte", categoria="adicional", valor=200.00, descricao="Vale transporte mensal"),
            OutroCusto(funcionario_id=caio.id, data=date(2025, 6, 1), tipo="Desconto VT 6%", categoria="desconto", valor=-12.00, descricao="Desconto vale transporte"),
            OutroCusto(funcionario_id=caio.id, data=date(2025, 6, 15), tipo="Vale Alimentação", categoria="adicional", valor=450.00, descricao="Vale alimentação mensal"),
            OutroCusto(funcionario_id=caio.id, data=date(2025, 6, 20), tipo="EPI - Capacete", categoria="adicional", valor=25.00, descricao="Equipamento de proteção"),
            OutroCusto(funcionario_id=caio.id, data=date(2025, 6, 25), tipo="Uniforme", categoria="adicional", valor=80.00, descricao="Uniforme de trabalho"),
        ]
        
        for custo in outros_custos:
            db.session.add(custo)
        
        db.session.commit()
        print(f"   - Outros custos criados: {len(outros_custos)}")
        
        # Criar registros de alimentação
        alimentacao = [
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 2), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 3), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 4), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 5), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 6), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 9), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 12), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 16), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 17), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 18), tipo="lanche", valor=12.00, observacoes="Lanche - R$ 12,00"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 19), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 20), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 23), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 24), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
            RegistroAlimentacao(funcionario_id=caio.id, data=date(2025, 6, 25), tipo="almoco", valor=18.50, observacoes="Almoço - R$ 18,50"),
        ]
        
        for refeicao in alimentacao:
            db.session.add(refeicao)
        
        db.session.commit()
        print(f"   - Registros de alimentação criados: {len(alimentacao)}")
        
        print(f"\n=== RESUMO DO MÊS POPULADO ===")
        print(f"   - Funcionário: {caio.nome}")
        print(f"   - Registros de ponto: {len(registros_ponto)}")
        print(f"   - Outros custos: {len(outros_custos)}")
        print(f"   - Registros de alimentação: {len(alimentacao)}")
        
        return caio

if __name__ == "__main__":
    caio = popular_caio_junho()
    print(f"\nMês populado com sucesso para {caio.nome}!")
    print(f"Acesse: /funcionarios/{caio.id}/perfil")