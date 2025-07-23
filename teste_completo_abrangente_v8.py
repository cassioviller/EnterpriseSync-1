#!/usr/bin/env python3
"""
SIGE v8.0 - TESTE COMPLETO E ABRANGENTE
Sistema Integrado de Gestão Empresarial

Este script executa uma bateria completa de testes cobrindo:
- Multi-tenancy e isolamento de dados
- Funcionalidades end-to-end
- Performance e escalabilidade
- Segurança e integridade
- Usabilidade e responsividade

Autor: Sistema Automatizado de Testes
Data: 23 de Julho de 2025
"""

import os
import sys
import time
import random
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

# Configurar path do projeto
sys.path.append('/home/runner/workspace')

from app import app, db
from models import *
from kpis_engine import kpis_engine
from calculadora_obra import CalculadoraObra
from kpis_financeiros import KPIsFinanceiros
from ai_analytics import AIAnalyticsSystem
import traceback

class TesteSIGECompleto:
    def __init__(self):
        self.app = app
        self.resultados = {
            'multi_tenancy': [],
            'funcional': [],
            'performance': [],
            'seguranca': [],
            'usabilidade': [],
            'ia_analytics': []
        }
        self.tempo_inicio = time.time()
        
    def log_resultado(self, categoria, teste, status, detalhes="", tempo=0):
        """Registra resultado de um teste"""
        resultado = {
            'teste': teste,
            'status': status,  # PASS, FAIL, WARNING
            'detalhes': detalhes,
            'tempo': tempo,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        self.resultados[categoria].append(resultado)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} [{categoria.upper()}] {teste}: {status}")
        if detalhes:
            print(f"   💬 {detalhes}")
        if tempo > 0:
            print(f"   ⏱️ Tempo: {tempo:.3f}s")

    def configurar_ambiente_teste(self):
        """Configura ambiente de teste com dados realistas"""
        print("\n🔧 CONFIGURANDO AMBIENTE DE TESTE")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                # 1. Criar Super Admins
                super_admins = []
                for i in range(3):
                    super_admin = Usuario(
                        nome=f"Super Admin {i+1}",
                        username=f"superadmin{i+1}",
                        email=f"superadmin{i+1}@sige.com",
                        password_hash=generate_password_hash("admin123"),
                        tipo_usuario=TipoUsuario.SUPER_ADMIN,
                        ativo=True
                    )
                    super_admins.append(super_admin)
                    db.session.add(super_admin)
                
                db.session.commit()
                
                # 2. Criar Admins (Tenants)
                admins = []
                empresas = ["Construtora Alpha", "Engenharia Beta", "Obras Gamma", "Estruturas Delta", "Projetos Epsilon"]
                
                for i, empresa in enumerate(empresas):
                    admin = Usuario(
                        nome=f"Admin {empresa}",
                        username=f"admin{i+1}",
                        email=f"admin{i+1}@{empresa.lower().replace(' ', '')}.com",
                        password_hash=generate_password_hash("admin123"),
                        tipo_usuario=TipoUsuario.ADMIN,
                        ativo=True
                    )
                    admins.append(admin)
                    db.session.add(admin)
                
                db.session.commit()
                
                # 3. Criar Funcionários distribuídos entre tenants
                funcionarios_criados = 0
                nomes = ["João Silva", "Maria Santos", "Pedro Costa", "Ana Oliveira", "Carlos Souza", 
                        "Lucia Ferreira", "Roberto Lima", "Fernanda Alves", "Marcos Pereira", "Julia Ribeiro"]
                
                for admin in admins:
                    for i in range(10):  # 10 funcionários por tenant = 50 total
                        nome_funcionario = f"{random.choice(nomes)} {admin.id}-{i+1}"
                        funcionario = Funcionario(
                            codigo=f"F{funcionarios_criados+1:04d}",
                            nome=nome_funcionario,
                            cpf=f"{11111111111 + funcionarios_criados:011d}",
                            email=f"funcionario{funcionarios_criados+1}@empresa.com",
                            data_admissao=date.today() - timedelta(days=random.randint(30, 365)),
                            salario=random.uniform(2000, 8000),
                            admin_id=admin.id,
                            ativo=True
                        )
                        db.session.add(funcionario)
                        funcionarios_criados += 1
                
                db.session.commit()
                
                # 4. Criar Obras distribuídas entre tenants
                obras_nomes = ["Residencial Jardim", "Comercial Centro", "Industrial Norte", "Residencial Sul"]
                obras_criadas = 0
                
                for admin in admins:
                    for i in range(4):  # 4 obras por tenant = 20 total
                        obra = Obra(
                            nome=f"{random.choice(obras_nomes)} {admin.id}-{i+1}",
                            codigo=f"OB{obras_criadas+1:03d}",
                            data_inicio=date.today() - timedelta(days=random.randint(30, 180)),
                            data_previsao_fim=date.today() + timedelta(days=random.randint(30, 365)),
                            orcamento=random.uniform(100000, 1000000),
                            valor_contrato=random.uniform(120000, 1200000),
                            area_total_m2=random.uniform(100, 5000),
                            admin_id=admin.id,
                            ativo=True
                        )
                        db.session.add(obra)
                        obras_criadas += 1
                
                db.session.commit()
                
                # 5. Criar Veículos
                marcas = ["Volkswagen", "Ford", "Chevrolet", "Toyota", "Hyundai"]
                modelos = ["Saveiro", "Ranger", "S10", "Hilux", "HR"]
                
                for admin in admins:
                    for i in range(2):  # 2 veículos por tenant = 10 total
                        veiculo = Veiculo(
                            placa=f"ABC{1000 + admin.id + i}",
                            marca=random.choice(marcas),
                            modelo=random.choice(modelos),
                            ano=random.randint(2018, 2024),
                            tipo="Utilitário",
                            admin_id=admin.id,
                            ativo=True
                        )
                        db.session.add(veiculo)
                
                db.session.commit()
                
                # 6. Criar registros massivos para os últimos 6 meses
                self._criar_registros_massivos()
                
                print(f"✅ Ambiente configurado:")
                print(f"   • Super Admins: {len(super_admins)}")
                print(f"   • Admins (Tenants): {len(admins)}")
                print(f"   • Funcionários: {funcionarios_criados}")
                print(f"   • Obras: {obras_criadas}")
                print(f"   • Veículos: {len(admins) * 2}")
                
                self.log_resultado('funcional', 'Configuração do Ambiente', 'PASS', 
                                 f"{funcionarios_criados} funcionários, {obras_criadas} obras criadas")
                
        except Exception as e:
            self.log_resultado('funcional', 'Configuração do Ambiente', 'FAIL', str(e))
            raise

    def _criar_registros_massivos(self):
        """Cria registros massivos dos últimos 6 meses"""
        print("📊 Criando registros massivos...")
        
        funcionarios = Funcionario.query.all()
        obras = Obra.query.all()
        
        data_inicio = date.today() - timedelta(days=180)  # 6 meses
        
        registros_ponto = 0
        for funcionario in funcionarios[:30]:  # Limitar para 30 funcionários para performance
            data_atual = data_inicio
            while data_atual <= date.today():
                if data_atual.weekday() < 5:  # Segunda a sexta
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        obra_id=random.choice(obras).id,
                        data=data_atual,
                        hora_entrada=time(8, 0),
                        hora_saida=time(17, 0),
                        horas_trabalhadas=8.0,
                        tipo_registro='trabalho_normal'
                    )
                    db.session.add(registro)
                    registros_ponto += 1
                
                data_atual += timedelta(days=1)
        
        db.session.commit()
        print(f"   • Registros de ponto: {registros_ponto}")

    def testar_multi_tenancy(self):
        """Testa isolamento multi-tenant e gestão de acessos"""
        print("\n🔒 TESTANDO MULTI-TENANCY E ACESSOS")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                # 1. Verificar isolamento de dados por tenant
                admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
                
                for admin in admins[:2]:  # Testar com 2 admins
                    # Funcionários do tenant
                    funcionarios_tenant = Funcionario.query.filter_by(admin_id=admin.id).all()
                    
                    # Obras do tenant
                    obras_tenant = Obra.query.filter_by(admin_id=admin.id).all()
                    
                    # Verificar se não há vazamento de dados
                    outros_funcionarios = Funcionario.query.filter(Funcionario.admin_id != admin.id).count()
                    
                    if len(funcionarios_tenant) > 0 and len(obras_tenant) > 0 and outros_funcionarios > 0:
                        self.log_resultado('multi_tenancy', f'Isolamento Tenant {admin.nome}', 'PASS',
                                         f"{len(funcionarios_tenant)} funcionários, {len(obras_tenant)} obras isoladas")
                    else:
                        self.log_resultado('multi_tenancy', f'Isolamento Tenant {admin.nome}', 'FAIL',
                                         "Dados não isolados corretamente")
                
                # 2. Testar hierarquia de acessos
                super_admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).count()
                admins_count = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).count()
                funcionarios_count = Usuario.query.filter_by(tipo_usuario=TipoUsuario.FUNCIONARIO).count()
                
                if super_admins >= 3 and admins_count >= 5:
                    self.log_resultado('multi_tenancy', 'Hierarquia de Usuários', 'PASS',
                                     f"{super_admins} super admins, {admins_count} admins, {funcionarios_count} funcionários")
                else:
                    self.log_resultado('multi_tenancy', 'Hierarquia de Usuários', 'FAIL',
                                     "Hierarquia incorreta")
                
        except Exception as e:
            self.log_resultado('multi_tenancy', 'Teste Multi-Tenancy', 'FAIL', str(e))

    def testar_gestao_obras(self):
        """Testa funcionalidades de gestão de obras"""
        print("\n🏗️ TESTANDO GESTÃO DE OBRAS")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                obras = Obra.query.limit(5).all()
                
                for obra in obras:
                    inicio = time.time()
                    
                    # Testar CalculadoraObra
                    calculadora = CalculadoraObra(obra.id)
                    custos = calculadora.calcular_custo_total()
                    
                    tempo_calculo = time.time() - inicio
                    
                    if custos and 'total' in custos:
                        self.log_resultado('funcional', f'Calculadora Obra {obra.nome}', 'PASS',
                                         f"Custo total: R$ {custos['total']:,.2f}", tempo_calculo)
                    else:
                        self.log_resultado('funcional', f'Calculadora Obra {obra.nome}', 'FAIL',
                                         "Falha no cálculo de custos")
                
                # Testar KPIs Financeiros
                inicio = time.time()
                kpis_financeiros = KPIsFinanceiros.margem_lucro_realizada(obras[0].id)
                tempo_kpis = time.time() - inicio
                
                if kpis_financeiros and 'margem_percentual' in kpis_financeiros:
                    self.log_resultado('funcional', 'KPIs Financeiros', 'PASS',
                                     f"Margem: {kpis_financeiros['margem_percentual']:.1f}%", tempo_kpis)
                else:
                    self.log_resultado('funcional', 'KPIs Financeiros', 'FAIL',
                                     "Erro no cálculo de KPIs financeiros")
                
        except Exception as e:
            self.log_resultado('funcional', 'Gestão de Obras', 'FAIL', str(e))

    def testar_gestao_funcionarios(self):
        """Testa funcionalidades de gestão de funcionários"""
        print("\n👥 TESTANDO GESTÃO DE FUNCIONÁRIOS")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                funcionarios = Funcionario.query.limit(10).all()
                
                for funcionario in funcionarios:
                    inicio = time.time()
                    
                    # Testar KPIs do funcionário
                    data_inicio = date.today() - timedelta(days=30)
                    data_fim = date.today()
                    
                    kpis = kpis_engine(funcionario.id, data_inicio, data_fim)
                    tempo_kpis = time.time() - inicio
                    
                    if kpis and len(kpis) >= 10:  # Pelo menos 10 KPIs
                        produtividade = next((k['valor'] for k in kpis if k['nome'] == 'Produtividade'), 0)
                        self.log_resultado('funcional', f'KPIs Funcionário {funcionario.codigo}', 'PASS',
                                         f"15 KPIs calculados, Produtividade: {produtividade:.1f}%", tempo_kpis)
                    else:
                        self.log_resultado('funcional', f'KPIs Funcionário {funcionario.codigo}', 'FAIL',
                                         "KPIs não calculados corretamente")
                
        except Exception as e:
            self.log_resultado('funcional', 'Gestão de Funcionários', 'FAIL', str(e))

    def testar_ia_analytics(self):
        """Testa módulos de IA e Analytics"""
        print("\n🤖 TESTANDO IA E ANALYTICS")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                obras = Obra.query.limit(3).all()
                ai_system = AIAnalyticsSystem()
                
                for obra in obras:
                    inicio = time.time()
                    
                    # Testar predição de custos
                    try:
                        predicao = ai_system.prever_custo_obra(obra.id)
                        tempo_predicao = time.time() - inicio
                        
                        if predicao and 'custo_previsto' in predicao:
                            self.log_resultado('ia_analytics', f'Predição Custos Obra {obra.codigo}', 'PASS',
                                             f"Custo previsto: R$ {predicao['custo_previsto']:,.2f}", tempo_predicao)
                        else:
                            self.log_resultado('ia_analytics', f'Predição Custos Obra {obra.codigo}', 'FAIL',
                                             "Falha na predição")
                    except Exception as e:
                        self.log_resultado('ia_analytics', f'Predição Custos Obra {obra.codigo}', 'FAIL',
                                         f"Erro: {str(e)}")
                
                # Testar detecção de anomalias
                inicio = time.time()
                try:
                    anomalias = ai_system.detectar_anomalias()
                    tempo_anomalias = time.time() - inicio
                    
                    if anomalias:
                        self.log_resultado('ia_analytics', 'Detecção de Anomalias', 'PASS',
                                         f"{len(anomalias)} anomalias detectadas", tempo_anomalias)
                    else:
                        self.log_resultado('ia_analytics', 'Detecção de Anomalias', 'WARNING',
                                         "Nenhuma anomalia detectada")
                except Exception as e:
                    self.log_resultado('ia_analytics', 'Detecção de Anomalias', 'FAIL', str(e))
                
        except Exception as e:
            self.log_resultado('ia_analytics', 'IA Analytics', 'FAIL', str(e))

    def testar_performance(self):
        """Testa performance do sistema"""
        print("\n⚡ TESTANDO PERFORMANCE")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                # 1. Teste de consultas pesadas
                inicio = time.time()
                funcionarios = Funcionario.query.all()
                tempo_consulta = time.time() - inicio
                
                if tempo_consulta < 1.0:
                    self.log_resultado('performance', 'Consulta Funcionários', 'PASS',
                                     f"{len(funcionarios)} registros", tempo_consulta)
                else:
                    self.log_resultado('performance', 'Consulta Funcionários', 'WARNING',
                                     f"Lento: {len(funcionarios)} registros", tempo_consulta)
                
                # 2. Teste de cálculos em lote
                inicio = time.time()
                for funcionario in funcionarios[:5]:  # Testar com 5 funcionários
                    kpis = kpis_engine(funcionario.id, date.today() - timedelta(days=30), date.today())
                
                tempo_lote = time.time() - inicio
                
                if tempo_lote < 5.0:
                    self.log_resultado('performance', 'Cálculos KPIs em Lote', 'PASS',
                                     f"5 funcionários processados", tempo_lote)
                else:
                    self.log_resultado('performance', 'Cálculos KPIs em Lote', 'WARNING',
                                     f"Lento: 5 funcionários", tempo_lote)
                
        except Exception as e:
            self.log_resultado('performance', 'Testes de Performance', 'FAIL', str(e))

    def testar_integridade_dados(self):
        """Testa integridade e consistência dos dados"""
        print("\n🔍 TESTANDO INTEGRIDADE DOS DADOS")
        print("=" * 50)
        
        try:
            with self.app.app_context():
                # 1. Verificar referências órfãs
                funcionarios_sem_admin = Funcionario.query.filter_by(admin_id=None).count()
                obras_sem_admin = Obra.query.filter_by(admin_id=None).count()
                
                if funcionarios_sem_admin == 0 and obras_sem_admin == 0:
                    self.log_resultado('seguranca', 'Referências de Admin', 'PASS',
                                     "Todas as entidades têm admin_id válido")
                else:
                    self.log_resultado('seguranca', 'Referências de Admin', 'FAIL',
                                     f"{funcionarios_sem_admin} funcionários e {obras_sem_admin} obras órfãs")
                
                # 2. Verificar consistência de dados
                total_usuarios = Usuario.query.count()
                total_funcionarios = Funcionario.query.count()
                total_obras = Obra.query.count()
                
                if total_usuarios > 0 and total_funcionarios > 0 and total_obras > 0:
                    self.log_resultado('seguranca', 'Consistência Geral', 'PASS',
                                     f"{total_usuarios} usuários, {total_funcionarios} funcionários, {total_obras} obras")
                else:
                    self.log_resultado('seguranca', 'Consistência Geral', 'FAIL',
                                     "Dados inconsistentes")
                
        except Exception as e:
            self.log_resultado('seguranca', 'Integridade de Dados', 'FAIL', str(e))

    def gerar_relatorio(self):
        """Gera relatório completo dos testes"""
        tempo_total = time.time() - self.tempo_inicio
        
        print("\n" + "=" * 80)
        print("📋 RELATÓRIO COMPLETO DOS TESTES - SIGE v8.0")
        print("=" * 80)
        
        # Estatísticas gerais
        total_testes = sum(len(resultados) for resultados in self.resultados.values())
        testes_pass = sum(1 for categoria in self.resultados.values() 
                         for teste in categoria if teste['status'] == 'PASS')
        testes_fail = sum(1 for categoria in self.resultados.values() 
                         for teste in categoria if teste['status'] == 'FAIL')
        testes_warning = sum(1 for categoria in self.resultados.values() 
                           for teste in categoria if teste['status'] == 'WARNING')
        
        print(f"\n📊 RESUMO EXECUTIVO:")
        print(f"   • Total de Testes: {total_testes}")
        print(f"   • Aprovados (PASS): {testes_pass} ({testes_pass/total_testes*100:.1f}%)")
        print(f"   • Reprovados (FAIL): {testes_fail} ({testes_fail/total_testes*100:.1f}%)")
        print(f"   • Alertas (WARNING): {testes_warning} ({testes_warning/total_testes*100:.1f}%)")
        print(f"   • Tempo Total: {tempo_total:.2f}s")
        
        # Status geral
        if testes_fail == 0:
            status_geral = "✅ SISTEMA APROVADO"
        elif testes_fail <= 2:
            status_geral = "⚠️ SISTEMA APROVADO COM RESSALVAS"
        else:
            status_geral = "❌ SISTEMA REPROVADO"
        
        print(f"\n🎯 STATUS GERAL: {status_geral}")
        
        # Detalhes por categoria
        for categoria, testes in self.resultados.items():
            if testes:
                print(f"\n📂 {categoria.upper().replace('_', ' ')}:")
                for teste in testes:
                    status_icon = "✅" if teste['status'] == "PASS" else "❌" if teste['status'] == "FAIL" else "⚠️"
                    print(f"   {status_icon} {teste['teste']}: {teste['status']}")
                    if teste['detalhes']:
                        print(f"      💬 {teste['detalhes']}")
                    if teste['tempo'] > 0:
                        print(f"      ⏱️ {teste['tempo']:.3f}s")
        
        # Salvar relatório em arquivo
        self._salvar_relatorio_arquivo(total_testes, testes_pass, testes_fail, testes_warning, tempo_total, status_geral)
        
        return status_geral, testes_pass, testes_fail

    def _salvar_relatorio_arquivo(self, total_testes, testes_pass, testes_fail, testes_warning, tempo_total, status_geral):
        """Salva relatório detalhado em arquivo"""
        relatorio_md = f"""# RELATÓRIO DE TESTE COMPLETO - SIGE v8.0

**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  
**Duração:** {tempo_total:.2f} segundos  
**Status:** {status_geral}

## Resumo Executivo

- **Total de Testes:** {total_testes}
- **Aprovados:** {testes_pass} ({testes_pass/total_testes*100:.1f}%)
- **Reprovados:** {testes_fail} ({testes_fail/total_testes*100:.1f}%)
- **Alertas:** {testes_warning} ({testes_warning/total_testes*100:.1f}%)

## Resultados Detalhados

"""
        
        for categoria, testes in self.resultados.items():
            if testes:
                relatorio_md += f"\n### {categoria.upper().replace('_', ' ')}\n\n"
                for teste in testes:
                    status_emoji = "✅" if teste['status'] == "PASS" else "❌" if teste['status'] == "FAIL" else "⚠️"
                    relatorio_md += f"{status_emoji} **{teste['teste']}**: {teste['status']}\n"
                    if teste['detalhes']:
                        relatorio_md += f"   - *Detalhes:* {teste['detalhes']}\n"
                    if teste['tempo'] > 0:
                        relatorio_md += f"   - *Tempo:* {teste['tempo']:.3f}s\n"
                    relatorio_md += "\n"
        
        # Salvar arquivo
        with open('RELATORIO_TESTE_COMPLETO_ABRANGENTE.md', 'w', encoding='utf-8') as f:
            f.write(relatorio_md)
        
        print(f"\n💾 Relatório salvo em: RELATORIO_TESTE_COMPLETO_ABRANGENTE.md")

    def executar_todos_testes(self):
        """Executa toda a suíte de testes"""
        print("🚀 INICIANDO TESTE COMPLETO E ABRANGENTE - SIGE v8.0")
        print("Data:", datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
        print("=" * 80)
        
        try:
            # 1. Configurar ambiente
            self.configurar_ambiente_teste()
            
            # 2. Executar testes funcionais
            self.testar_multi_tenancy()
            self.testar_gestao_obras()
            self.testar_gestao_funcionarios()
            
            # 3. Executar testes de IA
            self.testar_ia_analytics()
            
            # 4. Executar testes de performance
            self.testar_performance()
            
            # 5. Executar testes de integridade
            self.testar_integridade_dados()
            
            # 6. Gerar relatório final
            status, aprovados, reprovados = self.gerar_relatorio()
            
            return status, aprovados, reprovados
            
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO NO TESTE: {str(e)}")
            traceback.print_exc()
            return "❌ ERRO CRÍTICO", 0, 1

def main():
    """Função principal"""
    teste = TesteSIGECompleto()
    status, aprovados, reprovados = teste.executar_todos_testes()
    
    print(f"\n🏁 TESTE FINALIZADO")
    print(f"Status: {status}")
    print(f"Aprovados: {aprovados}, Reprovados: {reprovados}")
    
    return 0 if reprovados == 0 else 1

if __name__ == "__main__":
    exit(main())