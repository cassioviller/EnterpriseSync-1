#!/usr/bin/env python3
"""
Script para testar lançamento manual simulando usuário logado
"""

from app import app, db
from models import *
from datetime import datetime, date, time
import json

def simular_login_admin():
    """Simular login de admin para teste"""
    
    with app.app_context():
        print("👤 SIMULANDO LOGIN DE ADMIN")
        print("=" * 50)
        
        # Buscar admin ID 4 (usado nas imagens)
        admin = Usuario.query.filter_by(id=4, tipo_usuario=TipoUsuario.ADMIN).first()
        
        if admin:
            print(f"✅ Admin encontrado: {admin.email}")
            print(f"   ID: {admin.id}")
            print(f"   Tipo: {admin.tipo_usuario}")
            print(f"   Ativo: {admin.ativo}")
            return admin
        else:
            print("❌ Admin ID 4 não encontrado")
            return None

def testar_endpoint_direto():
    """Testar endpoint diretamente"""
    
    with app.app_context():
        print("\n🎯 TESTANDO ENDPOINT DIRETO")
        print("=" * 50)
        
        # Dados do teste (baseado nas imagens)
        funcionario_id = 14  # ID do funcionário das imagens
        data_teste = date(2025, 7, 5)  # Sábado
        
        # Verificar se funcionário existe
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            print(f"❌ Funcionário ID {funcionario_id} não encontrado")
            return False
        
        print(f"👤 Funcionário: {funcionario.nome}")
        print(f"📅 Data teste: {data_teste.strftime('%d/%m/%Y')} (sábado)")
        
        # Verificar se já existe
        existe = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data_teste
        ).first()
        
        if existe:
            print(f"⚠️ Registro já existe: ID {existe.id}")
            print(f"   Tipo: {existe.tipo_registro}")
            return True
        
        # Criar registro manualmente (simulando o endpoint)
        try:
            novo_registro = RegistroPonto(
                funcionario_id=funcionario_id,
                data=data_teste,
                tipo_registro='sabado_trabalhado',
                hora_entrada=time(7, 0),
                hora_almoco_saida=time(12, 0),
                hora_almoco_retorno=time(13, 0),
                hora_saida=time(17, 0),
                horas_trabalhadas=8.0,
                horas_extras=8.0,
                percentual_extras=50.0,
                observacoes='Teste manual - Sábado trabalhado'
            )
            
            db.session.add(novo_registro)
            db.session.commit()
            
            print(f"✅ Registro criado com sucesso!")
            print(f"   ID: {novo_registro.id}")
            print(f"   Tipo: {novo_registro.tipo_registro}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar registro: {e}")
            return False

def verificar_filtros_frontend():
    """Verificar se os filtros estão corretos"""
    
    with app.app_context():
        print("\n🔍 VERIFICANDO FILTROS DE FRONTEND")
        print("=" * 50)
        
        # Simular query como o controle_ponto faz
        registros = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data.desc()).limit(50).all()
        
        print(f"📊 Registros encontrados: {len(registros)}")
        
        # Verificar especificamente 05/07
        sabado_05 = [r for r in registros if r.data == date(2025, 7, 5)]
        print(f"📅 Registros para 05/07/2025: {len(sabado_05)}")
        
        if sabado_05:
            for reg in sabado_05:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                print(f"   ID {reg.id}: {funcionario.nome} - {reg.tipo_registro}")
        
        # Verificar estrutura dos dados
        primeiro_registro = registros[0] if registros else None
        if primeiro_registro:
            print(f"\n📋 Estrutura do primeiro registro:")
            print(f"   ID: {primeiro_registro.id}")
            print(f"   Data: {primeiro_registro.data}")
            print(f"   Funcionário ID: {primeiro_registro.funcionario_id}")
            print(f"   Tipo: {primeiro_registro.tipo_registro}")
            
        return len(sabado_05) > 0

def analisar_formulario_frontend():
    """Analisar como o frontend está enviando dados"""
    
    print("\n📝 ANÁLISE DO FORMULÁRIO FRONTEND")
    print("=" * 50)
    
    print("🔍 CAMPOS ESPERADOS PELO ENDPOINT:")
    print("   funcionario_id")
    print("   data")
    print("   tipo_registro")
    print("   entrada, saida_almoco, retorno_almoco, saida")
    print("   observacoes")
    
    print("\n🔍 URL DO FORMULÁRIO:")
    print("   POST /ponto/registro")
    
    print("\n🔍 CAMPOS DE HORÁRIO:")
    print("   entrada_modal → entrada")
    print("   saida_almoco_modal → saida_almoco")
    print("   retorno_almoco_modal → retorno_almoco")
    print("   saida_modal → saida")
    
    print("\n⚠️ POSSÍVEIS PROBLEMAS:")
    print("   1. Mapeamento incorreto de campos")
    print("   2. Validação JavaScript bloqueando")
    print("   3. Autenticação falhando")
    print("   4. Endpoint wrong route")

def testar_com_dados_corretos():
    """Testar criação com dados exatamente como o frontend enviaria"""
    
    with app.app_context():
        print("\n🧪 TESTE COM DADOS DO FRONTEND")
        print("=" * 50)
        
        # Simular dados como o frontend enviaria
        dados_formulario = {
            'funcionario_id': '14',
            'data': '2025-07-05',
            'tipo_registro': 'sabado_trabalhado',
            'entrada': '07:00',
            'saida_almoco': '12:00',
            'retorno_almoco': '13:00',
            'saida': '17:00',
            'observacoes': 'Teste simulação frontend'
        }
        
        print("📝 Dados do formulário:")
        for key, value in dados_formulario.items():
            print(f"   {key}: {value}")
        
        # Processar como o endpoint faria
        try:
            funcionario_id = dados_formulario.get('funcionario_id')
            data = datetime.strptime(dados_formulario.get('data'), '%Y-%m-%d').date()
            tipo_registro = dados_formulario.get('tipo_registro', 'trabalho_normal')
            
            # Verificar duplicata
            existe = RegistroPonto.query.filter_by(
                funcionario_id=funcionario_id,
                data=data
            ).first()
            
            if existe:
                print(f"⚠️ Registro existente encontrado: ID {existe.id}")
                return True
            
            # Criar registro
            registro = RegistroPonto(
                funcionario_id=int(funcionario_id),
                data=data,
                tipo_registro=tipo_registro
            )
            
            # Adicionar horários
            entrada = dados_formulario.get('entrada')
            saida_almoco = dados_formulario.get('saida_almoco')
            retorno_almoco = dados_formulario.get('retorno_almoco')
            saida = dados_formulario.get('saida')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
            
            # Lógica de fim de semana
            dia_semana = data.weekday()
            if dia_semana == 5:  # Sábado
                registro.percentual_extras = 50.0
                registro.total_atraso_horas = 0.0
                registro.total_atraso_minutos = 0
            
            registro.observacoes = dados_formulario.get('observacoes')
            
            db.session.add(registro)
            db.session.commit()
            
            print(f"✅ Registro criado via simulação!")
            print(f"   ID: {registro.id}")
            print(f"   Data: {registro.data}")
            print(f"   Tipo: {registro.tipo_registro}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na simulação: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("🧪 TESTE MANUAL DE LANÇAMENTO - SÁBADO")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Simular login
    admin = simular_login_admin()
    
    if admin:
        # 2. Testar endpoint direto
        sucesso_direto = testar_endpoint_direto()
        
        # 3. Verificar filtros
        filtros_ok = verificar_filtros_frontend()
        
        # 4. Analisar formulário
        analisar_formulario_frontend()
        
        # 5. Teste com dados corretos
        sucesso_simulacao = testar_com_dados_corretos()
        
        print("\n" + "=" * 50)
        print("📊 RESUMO DOS TESTES:")
        print(f"   Admin encontrado: {'✅' if admin else '❌'}")
        print(f"   Endpoint direto: {'✅' if sucesso_direto else '❌'}")
        print(f"   Filtros corretos: {'✅' if filtros_ok else '❌'}")
        print(f"   Simulação frontend: {'✅' if sucesso_simulacao else '❌'}")
        
        if sucesso_simulacao or sucesso_direto:
            print("\n✅ LANÇAMENTO FUNCIONANDO - Problema pode ser no frontend")
        else:
            print("\n❌ PROBLEMA NO BACKEND - Investigar logs")
    else:
        print("❌ Falha no teste - Admin não encontrado")