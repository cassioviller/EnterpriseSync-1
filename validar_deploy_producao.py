#!/usr/bin/env python3
"""
SCRIPT DE VALIDAÇÃO: Deploy de Produção - Sistema SIGE
Verifica se o deploy de horas extras foi aplicado corretamente
"""

from app import app, db
from models import *
from datetime import date, time
import sys

def verificar_estrutura_banco():
    """Verifica se as tabelas e campos necessários existem"""
    print("🔍 VERIFICANDO ESTRUTURA DO BANCO...")
    
    verificacoes = []
    
    # 1. Verificar tabela horarios_padrao
    try:
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) FROM horarios_padrao")).scalar()
        verificacoes.append(("✅ Tabela horarios_padrao", f"{result} registros"))
    except Exception as e:
        verificacoes.append(("❌ Tabela horarios_padrao", f"ERRO: {e}"))
    
    # 2. Verificar campos em registros_ponto
    try:
        from sqlalchemy import text
        from models import RegistroPonto
        nome_tabela = RegistroPonto.__tablename__
        db.session.execute(text(f"SELECT minutos_extras_entrada, minutos_extras_saida, horas_extras_calculadas FROM {nome_tabela} LIMIT 1"))
        verificacoes.append(("✅ Campos extras em registros_ponto", "OK"))
    except Exception as e:
        verificacoes.append(("❌ Campos extras em registros_ponto", f"ERRO: {e}"))
    
    # 3. Verificar funcionários com horário padrão
    try:
        from sqlalchemy import text
        funcionarios_com_horario = db.session.execute(text("""
            SELECT COUNT(DISTINCT f.id) 
            FROM funcionarios f 
            JOIN horarios_padrao h ON f.id = h.funcionario_id 
            WHERE h.ativo = TRUE
        """)).scalar()
        verificacoes.append(("✅ Funcionários com horário padrão", f"{funcionarios_com_horario}"))
    except Exception as e:
        verificacoes.append(("❌ Funcionários com horário padrão", f"ERRO: {e}"))
    
    # Imprimir resultados
    for status, info in verificacoes:
        print(f"{status}: {info}")
    
    return all("✅" in v[0] for v in verificacoes)

def testar_calculo_horas_extras():
    """Testa o cálculo de horas extras com dados reais"""
    print("\n🧮 TESTANDO CÁLCULO DE HORAS EXTRAS...")
    
    # Buscar um registro recente com horários
    registro = RegistroPonto.query.filter(
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).order_by(RegistroPonto.data.desc()).first()
    
    if not registro:
        print("❌ Nenhum registro de ponto encontrado para teste")
        return False
    
    print(f"📋 Testando com: {registro.funcionario_ref.nome} - {registro.data}")
    print(f"   Horários: {registro.hora_entrada} às {registro.hora_saida}")
    
    # Verificar se tem horário padrão
    from sqlalchemy import text
    horario_padrao = db.session.execute(text("""
        SELECT entrada_padrao, saida_padrao 
        FROM horarios_padrao 
        WHERE funcionario_id = :funcionario_id AND ativo = TRUE
        LIMIT 1
    """), {"funcionario_id": registro.funcionario_id}).fetchone()
    
    if not horario_padrao:
        print("❌ Funcionário sem horário padrão")
        return False
    
    print(f"   Padrão: {horario_padrao[0]} às {horario_padrao[1]}")
    
    # Calcular horas extras manualmente
    from implementar_horario_padrao_completo import calcular_horas_extras_por_horario_padrao
    
    try:
        entrada_extra, saida_extra, total_extra, sucesso = calcular_horas_extras_por_horario_padrao(registro)
        
        if sucesso:
            print(f"✅ CÁLCULO FUNCIONOU:")
            print(f"   Entrada antecipada: {entrada_extra} min")
            print(f"   Saída atrasada: {saida_extra} min") 
            print(f"   Total: {total_extra} horas")
            
            # Verificar se foi salvo no banco
            if hasattr(registro, 'horas_extras_calculadas'):
                print(f"   Salvo no banco: {registro.horas_extras_calculadas} horas")
            
            return True
        else:
            print("❌ Falha no cálculo")
            return False
            
    except Exception as e:
        print(f"❌ ERRO NO TESTE: {e}")
        return False

def verificar_kpis_dashboard():
    """Verifica se os KPIs do dashboard estão funcionando"""
    print("\n📊 VERIFICANDO KPIs DO DASHBOARD...")
    
    try:
        from kpi_unificado import obter_kpi_dashboard
        
        # Pegar o primeiro admin disponível
        admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
        if not admin:
            print("❌ Nenhum admin encontrado")
            return False
        
        kpis = obter_kpi_dashboard(admin.id)
        
        print(f"✅ KPIs obtidos para admin {admin.nome}:")
        print(f"   Funcionários ativos: {kpis.get('funcionarios_ativos', 0)}")
        print(f"   Obras ativas: {kpis.get('obras_ativas', 0)}")
        print(f"   Custos período: R$ {kpis.get('custos_periodo', 0):,.2f}")
        
        # Verificar obras
        obras = kpis.get('obras', [])
        print(f"   Obras com custos: {len(obras)}")
        
        for obra in obras[:3]:  # Top 3
            print(f"     • {obra['nome']}: R$ {obra['custo_total']:,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO NOS KPIs: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_apis_funcionando():
    """Testa se as APIs estão respondendo"""
    print("\n🌐 TESTANDO APIs...")
    
    from app import app
    
    with app.test_client() as client:
        testes = [
            ('/health', "Health check"),
            ('/', "Página inicial"),
            ('/login', "Página de login")
        ]
        
        resultados = []
        
        for rota, descricao in testes:
            try:
                response = client.get(rota)
                if response.status_code in [200, 302]:  # 302 = redirect OK
                    resultados.append(f"✅ {descricao}: {response.status_code}")
                else:
                    resultados.append(f"❌ {descricao}: {response.status_code}")
            except Exception as e:
                resultados.append(f"❌ {descricao}: ERRO {e}")
        
        for resultado in resultados:
            print(f"   {resultado}")
        
        return all("✅" in r for r in resultados)

def relatorio_validacao_completo():
    """Gera relatório completo da validação"""
    print("=" * 60)
    print("🚀 RELATÓRIO DE VALIDAÇÃO - DEPLOY HORAS EXTRAS")
    print("=" * 60)
    
    testes = [
        ("Estrutura do Banco", verificar_estrutura_banco),
        ("Cálculo de Horas Extras", testar_calculo_horas_extras), 
        ("KPIs Dashboard", verificar_kpis_dashboard),
        ("APIs Funcionando", verificar_apis_funcionando)
    ]
    
    resultados = []
    
    for nome, funcao in testes:
        print(f"\n📋 EXECUTANDO: {nome}")
        print("-" * 40)
        
        try:
            sucesso = funcao()
            status = "✅ PASSOU" if sucesso else "❌ FALHOU"
            resultados.append((nome, sucesso))
            print(f"\n{status}: {nome}")
        except Exception as e:
            print(f"\n❌ ERRO: {nome} - {e}")
            resultados.append((nome, False))
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("=" * 60)
    
    passou = 0
    total = len(resultados)
    
    for nome, sucesso in resultados:
        status = "✅" if sucesso else "❌"
        print(f"{status} {nome}")
        if sucesso:
            passou += 1
    
    print(f"\n🎯 RESULTADO GERAL: {passou}/{total} testes passaram")
    
    if passou == total:
        print("🎉 DEPLOY VALIDADO COM SUCESSO!")
        print("✅ Sistema pronto para produção")
        return True
    else:
        print("⚠️ DEPLOY COM PROBLEMAS!")
        print("❌ Corrigir falhas antes de produção")
        return False

if __name__ == "__main__":
    with app.app_context():
        sucesso_geral = relatorio_validacao_completo()
        
        # Exit code para scripts de deploy
        sys.exit(0 if sucesso_geral else 1)