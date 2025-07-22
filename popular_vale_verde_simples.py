#!/usr/bin/env python3
"""
Populador Simples - Construtora Vale Verde
Sistema SIGE v8.0 - Adiciona dados sem limpar existentes
"""

from app import app, db
from models import *
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time, timedelta
import random

def criar_registros_ponto_julho():
    """Cria registros de ponto para julho/2024"""
    print("⏲️ Criando registros de ponto julho/2024...")
    
    funcionarios = Funcionario.query.all()
    if not funcionarios:
        print("   ❌ Nenhum funcionário encontrado!")
        return
    
    dias_julho = []
    for dia in range(1, 32):  # Julho tem 31 dias
        data = date(2024, 7, dia)
        dia_semana = data.weekday()  # 0=segunda, 6=domingo
        
        # Pular domingos para a maioria dos funcionários
        if dia_semana == 6:  # Domingo
            continue
            
        dias_julho.append(data)
    
    total_registros = 0
    
    for funcionario in funcionarios:
        horario = funcionario.horario_trabalho_id
        if not horario:
            continue
            
        horario_trabalho = HorarioTrabalho.query.get(horario)
        if not horario_trabalho:
            continue
        
        for data_ponto in dias_julho:
            # 90% chance de trabalhar no dia
            if random.random() < 0.1:
                continue
                
            # Definir tipo de registro baseado no dia
            dia_semana = data_ponto.weekday()
            if dia_semana == 5:  # Sábado
                if random.random() < 0.3:  # 30% chance de trabalhar sábado
                    tipo_registro = 'sabado_horas_extras'
                else:
                    continue
            else:
                # Chance de diferentes tipos
                rand = random.random()
                if rand < 0.05:  # 5% falta
                    tipo_registro = 'falta'
                elif rand < 0.08:  # 3% falta justificada
                    tipo_registro = 'falta_justificada'
                else:
                    tipo_registro = 'trabalho_normal'
            
            # Calcular horários baseado no tipo
            if tipo_registro in ['falta', 'falta_justificada']:
                entrada = None
                saida = None
                saida_almoco = None
                retorno_almoco = None
                horas_trabalhadas = 0
                horas_extras = 0
            else:
                # Horário normal com pequenas variações
                entrada_base = horario_trabalho.entrada
                variacao = random.randint(-10, 15)  # -10 a +15 minutos
                entrada = (datetime.combine(date.today(), entrada_base) + timedelta(minutes=variacao)).time()
                
                saida_base = horario_trabalho.saida
                variacao_saida = random.randint(-5, 60)  # -5 a +60 minutos
                saida = (datetime.combine(date.today(), saida_base) + timedelta(minutes=variacao_saida)).time()
                
                # Almoço (apenas para horários que têm)
                if horario_trabalho.nome != 'Estagiario':
                    saida_almoco = horario_trabalho.saida_almoco
                    retorno_almoco = horario_trabalho.retorno_almoco
                else:
                    saida_almoco = None
                    retorno_almoco = None
                
                # Calcular horas
                entrada_dt = datetime.combine(data_ponto, entrada)
                saida_dt = datetime.combine(data_ponto, saida)
                
                total_horas = (saida_dt - entrada_dt).total_seconds() / 3600
                
                # Subtrair almoço se houver
                if saida_almoco and retorno_almoco:
                    total_horas -= 1  # 1 hora de almoço
                
                horas_trabalhadas = round(total_horas, 2)
                
                # Calcular extras
                horas_normais = horario_trabalho.horas_diarias
                if tipo_registro == 'sabado_horas_extras':
                    horas_extras = horas_trabalhadas  # Todo sábado é extra
                elif horas_trabalhadas > horas_normais:
                    horas_extras = round(horas_trabalhadas - horas_normais, 2)
                else:
                    horas_extras = 0
                
                # Percentual de extras
                if tipo_registro == 'sabado_horas_extras':
                    percentual_extras = 50.0
                else:
                    percentual_extras = 50.0 if horas_extras > 0 else 0.0
            
            # Verificar se já existe registro
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_ponto
            ).first()
            
            if not registro_existente:
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_ponto,
                    entrada=entrada,
                    saida=saida,
                    saida_almoco=saida_almoco,
                    retorno_almoco=retorno_almoco,
                    horas_trabalhadas=horas_trabalhadas,
                    horas_extras=horas_extras,
                    tipo_registro=tipo_registro,
                    percentual_extras=percentual_extras
                )
                
                db.session.add(registro)
                total_registros += 1
    
    db.session.commit()
    print(f"   ✅ {total_registros} registros de ponto criados")

def criar_registros_alimentacao_julho():
    """Cria registros de alimentação para julho/2024"""
    print("🍽️ Criando registros de alimentação julho/2024...")
    
    funcionarios = Funcionario.query.all()
    restaurantes = Restaurante.query.all()
    obras = Obra.query.all()
    
    if not (funcionarios and restaurantes and obras):
        print("   ❌ Dados básicos não encontrados!")
        return
    
    total_registros = 0
    
    # Criar 3-4 lançamentos por semana
    for semana in range(4):  # 4 semanas em julho
        for dia_semana in [1, 3, 5]:  # Seg, Qua, Sex
            dia = semana * 7 + dia_semana
            if dia > 31:
                continue
                
            data_registro = date(2024, 7, dia)
            
            # Escolher restaurante e obra aleatórios
            restaurante = random.choice(restaurantes)
            obra = random.choice(obras)
            
            # Escolher 3-8 funcionários aleatórios
            funcionarios_sorteados = random.sample(funcionarios, random.randint(3, 8))
            
            for funcionario in funcionarios_sorteados:
                # Verificar se já existe
                registro_existente = RegistroAlimentacao.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_registro,
                    restaurante_id=restaurante.id
                ).first()
                
                if not registro_existente:
                    # Valores realistas
                    tipos_refeicao = ['Almoço', 'Lanche', 'Jantar']
                    valores = {'Almoço': random.uniform(15, 25), 'Lanche': random.uniform(8, 15), 'Jantar': random.uniform(18, 30)}
                    
                    tipo = random.choice(tipos_refeicao)
                    valor = round(valores[tipo], 2)
                    
                    registro = RegistroAlimentacao(
                        funcionario_id=funcionario.id,
                        data=data_registro,
                        restaurante_id=restaurante.id,
                        obra_id=obra.id,
                        tipo_refeicao=tipo,
                        valor=valor
                    )
                    
                    db.session.add(registro)
                    total_registros += 1
    
    db.session.commit()
    print(f"   ✅ {total_registros} registros de alimentação criados")

def criar_rdos_julho():
    """Cria RDOs para julho/2024"""
    print("📋 Criando RDOs julho/2024...")
    
    obras = Obra.query.all()
    funcionarios = Funcionario.query.filter(Funcionario.funcao_ref.has(nome__in=['Mestre de Obras', 'Engenheiro Civil'])).all()
    
    if not (obras and funcionarios):
        print("   ❌ Obras ou funcionários responsáveis não encontrados!")
        return
    
    total_rdos = 0
    
    for obra in obras:
        # 8-12 RDOs por obra no mês
        num_rdos = random.randint(8, 12)
        
        for i in range(num_rdos):
            data_rdo = date(2024, 7, random.randint(1, 31))
            
            # Verificar se já existe RDO nesta data/obra
            rdo_existente = RDO.query.filter_by(obra_id=obra.id, data=data_rdo).first()
            if rdo_existente:
                continue
            
            responsavel = random.choice(funcionarios)
            
            # Atividades realistas
            atividades = [
                "Execução de alvenaria - parede externa bloco 2",
                "Concretagem de laje - 15m³ de concreto bombeado",
                "Instalação elétrica - fiação apartamentos 101-105",
                "Revestimento cerâmico - banheiros bloco A",
                "Pintura interna - apartamentos térreo",
                "Instalação hidráulica - prumadas água fria",
                "Estrutura metálica - montagem pilares galpão",
                "Cobertura telha metálica - área 200m²",
                "Acabamentos - colocação de rodapés",
                "Paisagismo - plantio de grama área comum"
            ]
            
            # Problemas ocasionais
            problemas = [
                None, None, None,  # 70% sem problemas
                "Chuva pela manhã atrasou serviços externos",
                "Falta de material - aguardando entrega de blocos",
                "Equipamento em manutenção - betoneira",
                "Funcionário afastado por atestado médico"
            ]
            
            rdo = RDO(
                obra_id=obra.id,
                data=data_rdo,
                funcionario_id=responsavel.id,
                atividades_executadas=random.choice(atividades),
                problemas_encontrados=random.choice(problemas),
                observacoes="Tempo bom, produtividade normal" if not random.choice(problemas) else "Produtividade afetada",
                tempo_clima="Ensolarado" if random.random() < 0.7 else random.choice(["Nublado", "Chuvoso", "Vento forte"])
            )
            
            db.session.add(rdo)
            total_rdos += 1
    
    db.session.commit()
    print(f"   ✅ {total_rdos} RDOs criados")

def criar_custos_diversos():
    """Cria custos diversos para julho/2024"""
    print("💰 Criando custos diversos julho/2024...")
    
    obras = Obra.query.all()
    veiculos = Veiculo.query.all()
    funcionarios = Funcionario.query.all()
    
    total_custos = 0
    
    # Custos de obra
    if obras:
        for obra in obras:
            for i in range(random.randint(15, 25)):  # 15-25 custos por obra
                data_custo = date(2024, 7, random.randint(1, 31))
                
                tipos_custo = ['Material', 'Equipamento', 'Serviço', 'Transporte']
                descricoes = {
                    'Material': ['Cimento 50kg', 'Bloco cerâmico', 'Ferro 12mm', 'Tinta acrílica', 'Cerâmica 45x45'],
                    'Equipamento': ['Aluguel betoneira', 'Aluguel andaime', 'Manutenção vibrador', 'Combustível gerador'],
                    'Serviço': ['Mão de obra terceirizada', 'Frete materiais', 'Ensaio concreto', 'Topografia'],
                    'Transporte': ['Frete blocos', 'Combustível caminhão', 'Pedágio', 'Manutenção veículo']
                }
                
                tipo = random.choice(tipos_custo)
                descricao = random.choice(descricoes[tipo])
                valor = round(random.uniform(50, 2000), 2)
                
                custo = CustoObra(
                    obra_id=obra.id,
                    data=data_custo,
                    descricao=descricao,
                    tipo=tipo,
                    valor=valor,
                    fornecedor=f"Fornecedor {random.choice(['ABC', 'XYZ', 'DEF', 'GHI'])} Ltda"
                )
                
                db.session.add(custo)
                total_custos += 1
    
    # Custos de veículos
    if veiculos:
        for veiculo in veiculos:
            for i in range(random.randint(8, 15)):  # 8-15 custos por veículo
                data_custo = date(2024, 7, random.randint(1, 31))
                
                tipos_veiculo = ['Combustível', 'Manutenção', 'Seguro', 'IPVA', 'Lavagem']
                tipo = random.choice(tipos_veiculo)
                
                valores_base = {
                    'Combustível': random.uniform(80, 300),
                    'Manutenção': random.uniform(150, 800),
                    'Seguro': random.uniform(200, 500),
                    'IPVA': random.uniform(300, 1200),
                    'Lavagem': random.uniform(15, 40)
                }
                
                valor = round(valores_base[tipo], 2)
                
                custo = CustoVeiculo(
                    veiculo_id=veiculo.id,
                    data=data_custo,
                    tipo_custo=tipo,
                    valor=valor,
                    descricao=f"{tipo} - {veiculo.marca} {veiculo.modelo}",
                    km_atual=random.randint(45000, 55000)
                )
                
                db.session.add(custo)
                total_custos += 1
    
    # Outros custos para funcionários
    if funcionarios:
        for funcionario in funcionarios:
            for i in range(random.randint(3, 8)):  # 3-8 outros custos por funcionário
                data_custo = date(2024, 7, random.randint(1, 31))
                
                tipos_outros = ['Vale Transporte', 'Vale Alimentação', 'EPI', 'Desconto VT', 'Benefícios']
                tipo = random.choice(tipos_outros)
                
                valores_outros = {
                    'Vale Transporte': random.uniform(150, 300),
                    'Vale Alimentação': random.uniform(200, 500),
                    'EPI': random.uniform(50, 200),
                    'Desconto VT': random.uniform(30, 60),
                    'Benefícios': random.uniform(100, 400)
                }
                
                valor = round(valores_outros[tipo], 2)
                
                outro = OutroCusto(
                    funcionario_id=funcionario.id,
                    data=data_custo,
                    tipo=tipo,
                    valor=valor,
                    descricao=f"{tipo} - {funcionario.nome}"
                )
                
                db.session.add(outro)
                total_custos += 1
    
    db.session.commit()
    print(f"   ✅ {total_custos} custos diversos criados")

def main():
    """Função principal"""
    print("🎯 POPULANDO DADOS COMPLEMENTARES - CONSTRUTORA VALE VERDE")
    print("=" * 80)
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("🏢 Empresa: Construtora Vale Verde Ltda")
    print("📊 Período: Julho/2024")
    
    with app.app_context():
        try:
            # Verificar se há funcionários
            funcionarios = Funcionario.query.count()
            if funcionarios == 0:
                print("❌ Nenhum funcionário encontrado! Execute primeiro o script de estrutura básica.")
                return False
            
            print(f"👥 Funcionários encontrados: {funcionarios}")
            
            # 1. Criar registros de ponto
            criar_registros_ponto_julho()
            
            # 2. Criar registros de alimentação
            criar_registros_alimentacao_julho()
            
            # 3. Criar RDOs
            criar_rdos_julho()
            
            # 4. Criar custos diversos
            criar_custos_diversos()
            
            # Estatísticas finais
            stats = {
                'pontos': RegistroPonto.query.filter(RegistroPonto.data >= date(2024, 7, 1), RegistroPonto.data <= date(2024, 7, 31)).count(),
                'alimentacao': RegistroAlimentacao.query.filter(RegistroAlimentacao.data >= date(2024, 7, 1), RegistroAlimentacao.data <= date(2024, 7, 31)).count(),
                'rdos': RDO.query.filter(RDO.data >= date(2024, 7, 1), RDO.data <= date(2024, 7, 31)).count(),
                'custos_obra': CustoObra.query.filter(CustoObra.data >= date(2024, 7, 1), CustoObra.data <= date(2024, 7, 31)).count(),
                'custos_veiculo': CustoVeiculo.query.filter(CustoVeiculo.data >= date(2024, 7, 1), CustoVeiculo.data <= date(2024, 7, 31)).count(),
                'outros_custos': OutroCusto.query.filter(OutroCusto.data >= date(2024, 7, 1), OutroCusto.data <= date(2024, 7, 31)).count()
            }
            
            print("=" * 80)
            print("🎉 POPULAÇÃO DE DADOS COMPLEMENTARES CONCLUÍDA!")
            print(f"   ⏲️ Registros de ponto (jul/24): {stats['pontos']}")
            print(f"   🍽️ Registros alimentação (jul/24): {stats['alimentacao']}")
            print(f"   📋 RDOs (jul/24): {stats['rdos']}")
            print(f"   🏗️ Custos de obra (jul/24): {stats['custos_obra']}")
            print(f"   🚗 Custos veículos (jul/24): {stats['custos_veiculo']}")
            print(f"   💰 Outros custos (jul/24): {stats['outros_custos']}")
            
            print(f"\n💡 CREDENCIAIS DE ACESSO:")
            print(f"   🔐 Super Admin: axiom / cassio123")
            print(f"   🔐 Admin: admin / admin123")
            print(f"   🔐 Funcionários: [codigo] / 123456")
            
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Erro durante a população: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    main()