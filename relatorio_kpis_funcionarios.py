#!/usr/bin/env python3
"""
Relatório detalhado de KPIs para funcionário, obra, veículo e restaurante
Mostra todos os lançamentos, valores e como cada KPI foi calculado
"""

from app import app, db
from datetime import date, datetime
from models import *
from kpis_engine_v3 import calcular_kpis_funcionario_v3
import json

def relatorio_funcionario_detalhado(funcionario_id, data_inicio, data_fim):
    """Relatório detalhado de um funcionário"""
    funcionario = Funcionario.query.get(funcionario_id)
    if not funcionario:
        return None
    
    print(f"\n{'='*80}")
    print(f"RELATÓRIO DETALHADO - FUNCIONÁRIO: {funcionario.nome} ({funcionario.codigo})")
    print(f"PERÍODO: {data_inicio} a {data_fim}")
    print(f"{'='*80}")
    
    # 1. DADOS BÁSICOS
    print(f"\n1. DADOS BÁSICOS:")
    print(f"   - Nome: {funcionario.nome}")
    print(f"   - Código: {funcionario.codigo}")
    print(f"   - CPF: {funcionario.cpf}")
    print(f"   - Salário: R$ {funcionario.salario:,.2f}")
    print(f"   - Salário/hora: R$ {funcionario.salario/220:.2f}")
    print(f"   - Departamento: {funcionario.departamento.nome if funcionario.departamento else 'N/A'}")
    print(f"   - Função: {funcionario.funcao.nome if funcionario.funcao else 'N/A'}")
    
    # 2. REGISTROS DE PONTO
    print(f"\n2. REGISTROS DE PONTO:")
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    total_horas_trabalhadas = 0
    total_horas_extras = 0
    total_faltas = 0
    total_atrasos_minutos = 0
    
    for registro in registros_ponto:
        print(f"   - {registro.data}: {registro.tipo_registro or 'trabalho_normal'}")
        if registro.hora_entrada:
            print(f"     Entrada: {registro.hora_entrada}")
            print(f"     Saída: {registro.hora_saida}")
            print(f"     Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
            print(f"     Horas trabalhadas: {registro.horas_trabalhadas:.1f}h")
            print(f"     Horas extras: {registro.horas_extras:.1f}h")
            print(f"     Atrasos: {registro.total_atraso_minutos:.0f} min")
            total_horas_trabalhadas += registro.horas_trabalhadas or 0
            total_horas_extras += registro.horas_extras or 0
            total_atrasos_minutos += registro.total_atraso_minutos or 0
        else:
            print(f"     Tipo: {registro.tipo_registro}")
            if registro.tipo_registro == 'falta':
                total_faltas += 1
        print(f"     Obra: {registro.obra.nome if registro.obra else 'N/A'}")
        print(f"     Observações: {registro.observacoes or 'N/A'}")
        print()
    
    print(f"   TOTAIS CONSOLIDADOS:")
    print(f"   - Horas trabalhadas: {total_horas_trabalhadas:.1f}h")
    print(f"   - Horas extras: {total_horas_extras:.1f}h")
    print(f"   - Faltas: {total_faltas}")
    print(f"   - Atrasos: {total_atrasos_minutos/60:.2f}h")
    
    # 3. REGISTROS DE ALIMENTAÇÃO
    print(f"\n3. REGISTROS DE ALIMENTAÇÃO:")
    registros_alimentacao = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).order_by(RegistroAlimentacao.data).all()
    
    total_alimentacao = 0
    for registro in registros_alimentacao:
        print(f"   - {registro.data}: {registro.restaurante.nome}")
        print(f"     Tipo: {registro.tipo_refeicao}")
        print(f"     Valor: R$ {registro.valor:.2f}")
        print(f"     Observações: {registro.observacoes or 'N/A'}")
        total_alimentacao += registro.valor
        print()
    
    print(f"   TOTAL ALIMENTAÇÃO: R$ {total_alimentacao:.2f}")
    
    # 4. OUTROS CUSTOS
    print(f"\n4. OUTROS CUSTOS:")
    outros_custos = OutroCusto.query.filter(
        OutroCusto.funcionario_id == funcionario_id,
        OutroCusto.data >= data_inicio,
        OutroCusto.data <= data_fim
    ).order_by(OutroCusto.data).all()
    
    total_outros_custos = 0
    for custo in outros_custos:
        print(f"   - {custo.data}: {custo.tipo}")
        print(f"     Categoria: {custo.categoria}")
        print(f"     Valor: R$ {custo.valor:.2f}")
        print(f"     Descrição: {custo.descricao or 'N/A'}")
        total_outros_custos += custo.valor
        print()
    
    print(f"   TOTAL OUTROS CUSTOS: R$ {total_outros_custos:.2f}")
    
    # 5. OCORRÊNCIAS
    print(f"\n5. OCORRÊNCIAS:")
    ocorrencias = Ocorrencia.query.filter(
        Ocorrencia.funcionario_id == funcionario_id,
        Ocorrencia.data_inicio >= data_inicio,
        Ocorrencia.data_inicio <= data_fim
    ).order_by(Ocorrencia.data_inicio).all()
    
    for ocorrencia in ocorrencias:
        print(f"   - {ocorrencia.data_inicio} a {ocorrencia.data_fim}: {ocorrencia.tipo_ocorrencia.nome}")
        print(f"     Status: {ocorrencia.status}")
        print(f"     Descrição: {ocorrencia.descricao or 'N/A'}")
        print()
    
    # 6. CÁLCULO DOS KPIs
    print(f"\n6. CÁLCULO DOS KPIs:")
    kpis = calcular_kpis_funcionario_v3(funcionario_id, data_inicio, data_fim)
    
    print(f"   FÓRMULAS E CÁLCULOS:")
    print(f"   - Horas trabalhadas: {kpis['horas_trabalhadas']:.1f}h (soma dos registros)")
    print(f"   - Horas extras: {kpis['horas_extras']:.1f}h (soma dos registros)")
    print(f"   - Faltas: {kpis['faltas']} (contagem de registros tipo 'falta')")
    print(f"   - Atrasos: {kpis['atrasos']:.2f}h (soma atrasos ÷ 60)")
    print(f"   - Horas perdidas: {kpis['horas_perdidas']:.1f}h = (faltas × 8) + atrasos = ({kpis['faltas']} × 8) + {kpis['atrasos']:.2f}")
    print(f"   - Custo mão de obra: R$ {kpis['custo_mao_obra']:,.2f}")
    print(f"     Cálculo: (horas_trabalhadas × salário_hora) + (horas_extras × salário_hora × 1.5)")
    print(f"     = ({kpis['horas_trabalhadas']:.1f} × {funcionario.salario/220:.2f}) + ({kpis['horas_extras']:.1f} × {funcionario.salario/220:.2f} × 1.5)")
    print(f"   - Custo alimentação: R$ {kpis['custo_alimentacao']:,.2f} (soma dos registros)")
    print(f"   - Custo transporte: R$ {kpis['custo_transporte']:,.2f} (não implementado)")
    print(f"   - Outros custos: R$ {kpis['outros_custos']:,.2f} (soma dos registros)")
    print(f"   - Produtividade: {kpis['produtividade']:.1f}% = (horas_trabalhadas ÷ horas_esperadas) × 100")
    print(f"     = ({kpis['horas_trabalhadas']:.1f} ÷ {kpis['horas_esperadas']:.1f}) × 100")
    print(f"   - Absenteísmo: {kpis['absenteismo']:.1f}% = (faltas ÷ dias_úteis) × 100")
    print(f"     = ({kpis['faltas']} ÷ {kpis['dias_uteis']}) × 100")
    
    return kpis

def relatorio_obra_detalhado(obra_id, data_inicio, data_fim):
    """Relatório detalhado de uma obra"""
    obra = Obra.query.get(obra_id)
    if not obra:
        return None
    
    print(f"\n{'='*80}")
    print(f"RELATÓRIO DETALHADO - OBRA: {obra.nome}")
    print(f"PERÍODO: {data_inicio} a {data_fim}")
    print(f"{'='*80}")
    
    # 1. DADOS BÁSICOS
    print(f"\n1. DADOS BÁSICOS:")
    print(f"   - Nome: {obra.nome}")
    print(f"   - Localização: {obra.localizacao}")
    print(f"   - Status: {obra.status}")
    print(f"   - Data início: {obra.data_inicio}")
    print(f"   - Data fim prevista: {obra.data_fim_prevista}")
    print(f"   - Orçamento: R$ {obra.orcamento:,.2f}")
    print(f"   - Descrição: {obra.descricao or 'N/A'}")
    
    # 2. CUSTOS DA OBRA
    print(f"\n2. CUSTOS DA OBRA:")
    custos_obra = CustoObra.query.filter(
        CustoObra.obra_id == obra_id,
        CustoObra.data >= data_inicio,
        CustoObra.data <= data_fim
    ).order_by(CustoObra.data).all()
    
    total_custos_obra = 0
    custos_por_tipo = {}
    
    for custo in custos_obra:
        print(f"   - {custo.data}: {custo.tipo}")
        print(f"     Valor: R$ {custo.valor:.2f}")
        print(f"     Descrição: {custo.descricao or 'N/A'}")
        total_custos_obra += custo.valor
        custos_por_tipo[custo.tipo] = custos_por_tipo.get(custo.tipo, 0) + custo.valor
        print()
    
    print(f"   TOTAIS POR TIPO:")
    for tipo, valor in custos_por_tipo.items():
        print(f"   - {tipo.title()}: R$ {valor:,.2f}")
    print(f"   TOTAL CUSTOS OBRA: R$ {total_custos_obra:,.2f}")
    
    # 3. CUSTOS DE VEÍCULOS
    print(f"\n3. CUSTOS DE VEÍCULOS:")
    custos_veiculos = CustoVeiculo.query.filter(
        CustoVeiculo.obra_id == obra_id,
        CustoVeiculo.data_custo >= data_inicio,
        CustoVeiculo.data_custo <= data_fim
    ).order_by(CustoVeiculo.data_custo).all()
    
    total_custos_veiculos = 0
    for custo in custos_veiculos:
        print(f"   - {custo.data_custo}: {custo.veiculo.modelo} ({custo.veiculo.placa})")
        print(f"     Tipo: {custo.tipo_custo}")
        print(f"     Valor: R$ {custo.valor:.2f}")
        print(f"     Fornecedor: {custo.fornecedor or 'N/A'}")
        print(f"     Descrição: {custo.descricao or 'N/A'}")
        total_custos_veiculos += custo.valor
        print()
    
    print(f"   TOTAL CUSTOS VEÍCULOS: R$ {total_custos_veiculos:,.2f}")
    
    # 4. MÃO DE OBRA
    print(f"\n4. MÃO DE OBRA:")
    registros_ponto = RegistroPonto.query.filter(
        RegistroPonto.obra_id == obra_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).order_by(RegistroPonto.data).all()
    
    funcionarios_obra = {}
    total_horas_obra = 0
    total_custo_mao_obra = 0
    
    for registro in registros_ponto:
        funcionario = registro.funcionario
        if funcionario.id not in funcionarios_obra:
            funcionarios_obra[funcionario.id] = {
                'nome': funcionario.nome,
                'codigo': funcionario.codigo,
                'salario': funcionario.salario,
                'horas_trabalhadas': 0,
                'horas_extras': 0,
                'dias_trabalhados': 0,
                'custo_total': 0
            }
        
        if registro.horas_trabalhadas:
            funcionarios_obra[funcionario.id]['horas_trabalhadas'] += registro.horas_trabalhadas
            funcionarios_obra[funcionario.id]['horas_extras'] += registro.horas_extras or 0
            funcionarios_obra[funcionario.id]['dias_trabalhados'] += 1
            total_horas_obra += registro.horas_trabalhadas
            
            # Calcular custo
            salario_hora = funcionario.salario / 220
            custo_normal = registro.horas_trabalhadas * salario_hora
            custo_extra = (registro.horas_extras or 0) * salario_hora * 1.5
            custo_registro = custo_normal + custo_extra
            funcionarios_obra[funcionario.id]['custo_total'] += custo_registro
            total_custo_mao_obra += custo_registro
    
    for func_id, dados in funcionarios_obra.items():
        print(f"   - {dados['nome']} ({dados['codigo']}):")
        print(f"     Horas trabalhadas: {dados['horas_trabalhadas']:.1f}h")
        print(f"     Horas extras: {dados['horas_extras']:.1f}h")
        print(f"     Dias trabalhados: {dados['dias_trabalhados']}")
        print(f"     Custo total: R$ {dados['custo_total']:,.2f}")
        print()
    
    print(f"   TOTAL HORAS OBRA: {total_horas_obra:.1f}h")
    print(f"   TOTAL CUSTO MÃO DE OBRA: R$ {total_custo_mao_obra:,.2f}")
    
    # 5. RDOs
    print(f"\n5. RDOs (RELATÓRIOS DIÁRIOS DE OBRA):")
    rdos = RDO.query.filter(
        RDO.obra_id == obra_id,
        RDO.data_relatorio >= data_inicio,
        RDO.data_relatorio <= data_fim
    ).order_by(RDO.data_relatorio).all()
    
    for rdo in rdos:
        print(f"   - {rdo.data_relatorio}: {rdo.numero_rdo}")
        print(f"     Status: {rdo.status}")
        print(f"     Criado por: {rdo.criado_por.nome}")
        print(f"     Tempo: {rdo.tempo_manha} / {rdo.tempo_tarde} / {rdo.tempo_noite}")
        print(f"     Comentário: {rdo.comentario_geral or 'N/A'}")
        print()
    
    # 6. RESUMO DE CUSTOS
    print(f"\n6. RESUMO DE CUSTOS:")
    custo_total = total_custos_obra + total_custos_veiculos + total_custo_mao_obra
    print(f"   - Custos diretos da obra: R$ {total_custos_obra:,.2f}")
    print(f"   - Custos de veículos: R$ {total_custos_veiculos:,.2f}")
    print(f"   - Custo mão de obra: R$ {total_custo_mao_obra:,.2f}")
    print(f"   - CUSTO TOTAL: R$ {custo_total:,.2f}")
    print(f"   - Orçamento: R$ {obra.orcamento:,.2f}")
    print(f"   - Percentual executado: {(custo_total/obra.orcamento)*100:.1f}%")
    
    return {
        'custos_obra': total_custos_obra,
        'custos_veiculos': total_custos_veiculos,
        'custo_mao_obra': total_custo_mao_obra,
        'custo_total': custo_total,
        'funcionarios': len(funcionarios_obra),
        'horas_totais': total_horas_obra,
        'rdos': len(rdos)
    }

def relatorio_veiculo_detalhado(veiculo_id, data_inicio, data_fim):
    """Relatório detalhado de um veículo"""
    veiculo = Veiculo.query.get(veiculo_id)
    if not veiculo:
        return None
    
    print(f"\n{'='*80}")
    print(f"RELATÓRIO DETALHADO - VEÍCULO: {veiculo.modelo} ({veiculo.placa})")
    print(f"PERÍODO: {data_inicio} a {data_fim}")
    print(f"{'='*80}")
    
    # 1. DADOS BÁSICOS
    print(f"\n1. DADOS BÁSICOS:")
    print(f"   - Modelo: {veiculo.modelo}")
    print(f"   - Placa: {veiculo.placa}")
    print(f"   - Ano: {veiculo.ano}")
    print(f"   - Status: {veiculo.status}")
    print(f"   - Tipo: {veiculo.tipo or 'N/A'}")
    print(f"   - Cor: {veiculo.cor or 'N/A'}")
    print(f"   - Observações: {veiculo.observacoes or 'N/A'}")
    
    # 2. CUSTOS DO VEÍCULO
    print(f"\n2. CUSTOS DO VEÍCULO:")
    custos_veiculo = CustoVeiculo.query.filter(
        CustoVeiculo.veiculo_id == veiculo_id,
        CustoVeiculo.data_custo >= data_inicio,
        CustoVeiculo.data_custo <= data_fim
    ).order_by(CustoVeiculo.data_custo).all()
    
    total_custos = 0
    custos_por_tipo = {}
    custos_por_obra = {}
    
    for custo in custos_veiculo:
        print(f"   - {custo.data_custo}: {custo.tipo_custo}")
        print(f"     Valor: R$ {custo.valor:.2f}")
        print(f"     Obra: {custo.obra.nome}")
        print(f"     Fornecedor: {custo.fornecedor or 'N/A'}")
        print(f"     Descrição: {custo.descricao or 'N/A'}")
        total_custos += custo.valor
        
        # Agrupar por tipo
        custos_por_tipo[custo.tipo_custo] = custos_por_tipo.get(custo.tipo_custo, 0) + custo.valor
        
        # Agrupar por obra
        custos_por_obra[custo.obra.nome] = custos_por_obra.get(custo.obra.nome, 0) + custo.valor
        print()
    
    print(f"   TOTAIS POR TIPO:")
    for tipo, valor in custos_por_tipo.items():
        print(f"   - {tipo.title()}: R$ {valor:,.2f}")
    
    print(f"\n   TOTAIS POR OBRA:")
    for obra, valor in custos_por_obra.items():
        print(f"   - {obra}: R$ {valor:,.2f}")
    
    print(f"\n   TOTAL CUSTOS: R$ {total_custos:,.2f}")
    
    # 3. ANÁLISE DE CUSTOS
    print(f"\n3. ANÁLISE DE CUSTOS:")
    num_registros = len(custos_veiculo)
    if num_registros > 0:
        custo_medio = total_custos / num_registros
        print(f"   - Número de lançamentos: {num_registros}")
        print(f"   - Custo médio por lançamento: R$ {custo_medio:.2f}")
        
        # Calcular custo por dia
        dias_periodo = (data_fim - data_inicio).days + 1
        custo_por_dia = total_custos / dias_periodo
        print(f"   - Custo por dia (período): R$ {custo_por_dia:.2f}")
        
        # Tipo de custo mais comum
        tipo_mais_comum = max(custos_por_tipo, key=custos_por_tipo.get)
        print(f"   - Tipo de custo mais comum: {tipo_mais_comum}")
        print(f"   - Obra com mais custos: {max(custos_por_obra, key=custos_por_obra.get)}")
    
    return {
        'total_custos': total_custos,
        'custos_por_tipo': custos_por_tipo,
        'custos_por_obra': custos_por_obra,
        'num_registros': num_registros
    }

def relatorio_restaurante_detalhado(restaurante_id, data_inicio, data_fim):
    """Relatório detalhado de um restaurante"""
    restaurante = Restaurante.query.get(restaurante_id)
    if not restaurante:
        return None
    
    print(f"\n{'='*80}")
    print(f"RELATÓRIO DETALHADO - RESTAURANTE: {restaurante.nome}")
    print(f"PERÍODO: {data_inicio} a {data_fim}")
    print(f"{'='*80}")
    
    # 1. DADOS BÁSICOS
    print(f"\n1. DADOS BÁSICOS:")
    print(f"   - Nome: {restaurante.nome}")
    print(f"   - Endereço: {restaurante.endereco or 'N/A'}")
    print(f"   - Telefone: {restaurante.telefone or 'N/A'}")
    print(f"   - Email: {restaurante.email or 'N/A'}")
    print(f"   - Preço padrão: R$ {restaurante.preco_padrao:.2f}")
    print(f"   - Status: {'Ativo' if restaurante.ativo else 'Inativo'}")
    
    # 2. REGISTROS DE ALIMENTAÇÃO
    print(f"\n2. REGISTROS DE ALIMENTAÇÃO:")
    registros_alimentacao = RegistroAlimentacao.query.filter(
        RegistroAlimentacao.restaurante_id == restaurante_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim
    ).order_by(RegistroAlimentacao.data).all()
    
    total_valor = 0
    funcionarios_atendidos = set()
    refeicoes_por_dia = {}
    refeicoes_por_funcionario = {}
    
    for registro in registros_alimentacao:
        print(f"   - {registro.data}: {registro.funcionario.nome} ({registro.funcionario.codigo})")
        print(f"     Tipo: {registro.tipo_refeicao}")
        print(f"     Valor: R$ {registro.valor:.2f}")
        print(f"     Observações: {registro.observacoes or 'N/A'}")
        
        total_valor += registro.valor
        funcionarios_atendidos.add(registro.funcionario_id)
        
        # Agrupar por dia
        data_str = registro.data.strftime('%Y-%m-%d')
        refeicoes_por_dia[data_str] = refeicoes_por_dia.get(data_str, 0) + 1
        
        # Agrupar por funcionário
        nome_func = registro.funcionario.nome
        if nome_func not in refeicoes_por_funcionario:
            refeicoes_por_funcionario[nome_func] = {'count': 0, 'valor': 0}
        refeicoes_por_funcionario[nome_func]['count'] += 1
        refeicoes_por_funcionario[nome_func]['valor'] += registro.valor
        print()
    
    print(f"   TOTAL VALOR: R$ {total_valor:,.2f}")
    print(f"   FUNCIONÁRIOS ATENDIDOS: {len(funcionarios_atendidos)}")
    print(f"   TOTAL REFEIÇÕES: {len(registros_alimentacao)}")
    
    # 3. ANÁLISE POR FUNCIONÁRIO
    print(f"\n3. ANÁLISE POR FUNCIONÁRIO:")
    for funcionario, dados in refeicoes_por_funcionario.items():
        print(f"   - {funcionario}:")
        print(f"     Refeições: {dados['count']}")
        print(f"     Valor total: R$ {dados['valor']:.2f}")
        print(f"     Valor médio: R$ {dados['valor']/dados['count']:.2f}")
    
    # 4. ANÁLISE POR DIA
    print(f"\n4. ANÁLISE POR DIA:")
    for data, count in sorted(refeicoes_por_dia.items()):
        print(f"   - {data}: {count} refeições")
    
    # 5. ESTATÍSTICAS
    print(f"\n5. ESTATÍSTICAS:")
    if len(registros_alimentacao) > 0:
        valor_medio = total_valor / len(registros_alimentacao)
        print(f"   - Valor médio por refeição: R$ {valor_medio:.2f}")
        print(f"   - Refeições por funcionário (média): {len(registros_alimentacao)/len(funcionarios_atendidos):.1f}")
        
        # Calcular faturamento por dia
        dias_periodo = (data_fim - data_inicio).days + 1
        faturamento_por_dia = total_valor / dias_periodo
        print(f"   - Faturamento por dia (período): R$ {faturamento_por_dia:.2f}")
        
        # Funcionário que mais consumiu
        func_mais_consumo = max(refeicoes_por_funcionario, key=lambda x: refeicoes_por_funcionario[x]['valor'])
        print(f"   - Funcionário com maior consumo: {func_mais_consumo}")
        print(f"     Valor: R$ {refeicoes_por_funcionario[func_mais_consumo]['valor']:.2f}")
    
    return {
        'total_valor': total_valor,
        'funcionarios_atendidos': len(funcionarios_atendidos),
        'total_refeicoes': len(registros_alimentacao),
        'refeicoes_por_funcionario': refeicoes_por_funcionario,
        'valor_medio': total_valor / len(registros_alimentacao) if len(registros_alimentacao) > 0 else 0
    }

def main():
    """Função principal - gera relatórios detalhados"""
    with app.app_context():
        print("RELATÓRIOS DETALHADOS - SIGE v5.0")
        print("="*80)
        
        # Período de análise
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        # Buscar entidades para relatório
        funcionario = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
        obra = Obra.query.filter_by(status='Em andamento').first()
        veiculo = Veiculo.query.first()
        restaurante = Restaurante.query.first()
        
        # Gerar relatórios
        if funcionario:
            relatorio_funcionario_detalhado(funcionario.id, data_inicio, data_fim)
        
        if obra:
            relatorio_obra_detalhado(obra.id, data_inicio, data_fim)
        
        if veiculo:
            relatorio_veiculo_detalhado(veiculo.id, data_inicio, data_fim)
        
        if restaurante:
            relatorio_restaurante_detalhado(restaurante.id, data_inicio, data_fim)
        
        print(f"\n{'='*80}")
        print("RELATÓRIOS CONCLUÍDOS!")
        print("="*80)

if __name__ == "__main__":
    main()