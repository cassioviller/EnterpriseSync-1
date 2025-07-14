#!/usr/bin/env python3
"""
Script para extrair todos os registros de ponto do Cássio 
exatamente como estão no banco de dados
"""

from app import app, db
from models import Funcionario, RegistroPonto, RegistroAlimentacao, OutroCusto
from datetime import date

def extrair_registros_cassio():
    """
    Extrai todos os registros de ponto do Cássio para junho/2025
    """
    
    with app.app_context():
        # Buscar funcionário Cássio
        cassio = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
        if not cassio:
            print("Funcionário Cássio não encontrado!")
            return
        
        # Período de análise
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        # Buscar registros de ponto
        registros_ponto = RegistroPonto.query.filter_by(funcionario_id=cassio.id).filter(
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        ).order_by(RegistroPonto.data).all()
        
        print("## Registros de Ponto Completos - Banco de Dados")
        print("### Extraídos diretamente do sistema SIGE v6.1")
        print()
        
        for i, registro in enumerate(registros_ponto, 1):
            print(f"#### **Registro {i:02d} - {registro.data.strftime('%d/%m/%Y (%A)')}**")
            print(f"- **Tipo de Registro:** {registro.tipo_registro}")
            print(f"- **Entrada:** {registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else 'Não registrado'}")
            print(f"- **Saída Almoço:** {registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else 'Não registrado'}")
            print(f"- **Volta Almoço:** {registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else 'Não registrado'}")
            print(f"- **Saída:** {registro.hora_saida.strftime('%H:%M') if registro.hora_saida else 'Não registrado'}")
            print(f"- **Horas Trabalhadas:** {registro.horas_trabalhadas or 0:.1f}h")
            print(f"- **Horas Extras:** {registro.horas_extras or 0:.1f}h")
            print(f"- **Atraso Entrada:** {registro.minutos_atraso_entrada or 0} minutos")
            print(f"- **Atraso Saída:** {registro.minutos_atraso_saida or 0} minutos")
            print(f"- **Total Atraso:** {registro.total_atraso_minutos or 0} minutos")
            print(f"- **Total Atraso Horas:** {registro.total_atraso_horas or 0:.2f}h")
            print(f"- **Meio Período:** {'Sim' if registro.meio_periodo else 'Não'}")
            print(f"- **Saída Antecipada:** {'Sim' if registro.saida_antecipada else 'Não'}")
            print(f"- **Percentual Extras:** {registro.percentual_extras or 0}%")
            print(f"- **Obra ID:** {registro.obra_id or 'Não especificado'}")
            print(f"- **Observações:** {registro.observacoes or 'Nenhuma'}")
            print()
        
        # Buscar outros custos
        outros_custos = OutroCusto.query.filter_by(funcionario_id=cassio.id).filter(
            OutroCusto.data >= data_inicio,
            OutroCusto.data <= data_fim
        ).order_by(OutroCusto.data).all()
        
        print("## Registros de Outros Custos - Banco de Dados")
        print("### Extraídos diretamente do sistema SIGE v6.1")
        print()
        
        for i, custo in enumerate(outros_custos, 1):
            print(f"#### **Custo {i:02d} - {custo.data.strftime('%d/%m/%Y')}**")
            print(f"- **Tipo:** {custo.tipo}")
            print(f"- **Valor:** R$ {custo.valor:,.2f}")
            print(f"- **Descrição:** {custo.descricao or 'Nenhuma'}")
            print()
        
        # Buscar registros de alimentação
        alimentacao = RegistroAlimentacao.query.filter_by(funcionario_id=cassio.id).filter(
            RegistroAlimentacao.data >= data_inicio,
            RegistroAlimentacao.data <= data_fim
        ).order_by(RegistroAlimentacao.data).all()
        
        print("## Registros de Alimentação - Banco de Dados")
        print("### Extraídos diretamente do sistema SIGE v6.1")
        print()
        
        if alimentacao:
            for i, reg in enumerate(alimentacao, 1):
                print(f"#### **Alimentação {i:02d} - {reg.data.strftime('%d/%m/%Y')}**")
                print(f"- **Restaurante ID:** {reg.restaurante_id}")
                print(f"- **Valor:** R$ {reg.valor:,.2f}")
                print(f"- **Tipo Refeição:** {reg.tipo_refeicao or 'Não especificado'}")
                print()
        else:
            print("**Nenhum registro de alimentação encontrado para este período.**")
            print()

if __name__ == "__main__":
    extrair_registros_cassio()