#!/usr/bin/env python3
"""
🔍 VERIFICAÇÃO COMPLETA: Módulo Outros Custos
Análise completa da estrutura, deploy, dados e correções
"""

import os
import re
import datetime
from app import app, db
from models import OutroCusto
import inspect

def verificar_estrutura_banco():
    """Verifica estrutura atual da tabela outro_custo"""
    print("🔍 VERIFICANDO ESTRUTURA DO BANCO...")
    
    # Verificar colunas existentes
    from sqlalchemy import text
    result = db.session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'outro_custo'
        ORDER BY ordinal_position
    """))
    
    colunas = list(result)
    
    print("📊 COLUNAS DA TABELA outro_custo:")
    for coluna in colunas:
        print(f"   - {coluna[0]} ({coluna[1]}) - Nullable: {coluna[2]} - Default: {coluna[3]}")
    
    # Verificar se admin_id existe
    admin_id_existe = any(col[0] == 'admin_id' for col in colunas)
    print(f"\n🔍 COLUNA admin_id EXISTE: {admin_id_existe}")
    
    # Verificar índices
    indices = db.session.execute(text("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'outro_custo'
    """))
    
    print("\n📊 ÍNDICES:")
    for indice in indices:
        print(f"   - {indice[0]}: {indice[1]}")
    
    return colunas, admin_id_existe

def verificar_modelo_python():
    """Verifica definição atual do modelo OutroCusto"""
    print("\n🔍 VERIFICANDO MODELO PYTHON...")
    
    # Verificar atributos da classe
    atributos = [attr for attr in dir(OutroCusto) if not attr.startswith('_')]
    print("📊 ATRIBUTOS DO MODELO:")
    for attr in sorted(atributos):
        print(f"   - {attr}")
    
    # Verificar colunas definidas
    colunas_modelo = []
    if hasattr(OutroCusto, '__table__'):
        colunas_modelo = list(OutroCusto.__table__.columns.keys())
        print("\n📊 COLUNAS DEFINIDAS NO MODELO:")
        for coluna in colunas_modelo:
            column_obj = OutroCusto.__table__.columns[coluna]
            tipo = str(column_obj.type)
            nullable = column_obj.nullable
            print(f"   - {coluna} ({tipo}) - Nullable: {nullable}")
    
    # Verificar relacionamentos
    relacionamentos = []
    if hasattr(OutroCusto, '__mapper__'):
        relacionamentos = list(OutroCusto.__mapper__.relationships.keys())
        print("\n📊 RELACIONAMENTOS:")
        for rel in relacionamentos:
            print(f"   - {rel}")
    
    return atributos, colunas_modelo, relacionamentos

def verificar_rotas():
    """Verifica rotas relacionadas a outros custos"""
    print("\n🔍 VERIFICANDO ROTAS...")
    
    rotas_outros_custos = []
    
    for rule in app.url_map.iter_rules():
        rule_lower = rule.rule.lower()
        endpoint_lower = rule.endpoint.lower() if rule.endpoint else ''
        
        if any(termo in rule_lower or termo in endpoint_lower for termo in ['outro', 'custo']):
            rotas_outros_custos.append({
                'endpoint': rule.endpoint,
                'rule': rule.rule,
                'methods': sorted(list(rule.methods - {'HEAD', 'OPTIONS'}))
            })
    
    print("📊 ROTAS RELACIONADAS A OUTROS CUSTOS:")
    for rota in sorted(rotas_outros_custos, key=lambda x: x['rule']):
        print(f"   - {rota['rule']} ({', '.join(rota['methods'])}) → {rota['endpoint']}")
    
    return rotas_outros_custos

def verificar_configuracao():
    """Verifica configurações atuais do app"""
    print("\n🔍 VERIFICANDO CONFIGURAÇÃO...")
    
    print("📊 CONFIGURAÇÕES DO APP:")
    print(f"   - DEBUG: {app.config.get('DEBUG', 'Não definido')}")
    print(f"   - ENV: {app.config.get('ENV', 'Não definido')}")
    print(f"   - DATABASE_URL: {'Definido' if app.config.get('DATABASE_URL') else 'Não definido'}")
    print(f"   - SECRET_KEY: {'Definido' if app.config.get('SECRET_KEY') else 'Não definido'}")
    
    print("\n📊 VARIÁVEIS DE AMBIENTE:")
    env_vars = ['FLASK_ENV', 'FLASK_APP', 'DATABASE_URL', 'SECRET_KEY', 'SESSION_SECRET']
    for var in env_vars:
        valor = os.environ.get(var)
        print(f"   - {var}: {'Definido' if valor else 'Não definido'}")
    
    print("\n📊 MODO DE EXECUÇÃO:")
    print(f"   - __name__: {__name__}")
    print(f"   - app.name: {app.name}")

def verificar_dados_outros_custos():
    """Verifica estado atual dos dados"""
    print("\n🔍 VERIFICANDO DADOS ATUAIS...")
    
    # Contar total de registros
    total = OutroCusto.query.count()
    print(f"📊 TOTAL DE REGISTROS: {total}")
    
    # Verificar por tipo
    tipos = db.session.query(OutroCusto.tipo, db.func.count(OutroCusto.id)).group_by(OutroCusto.tipo).all()
    print("\n📊 REGISTROS POR TIPO:")
    for tipo, count in sorted(tipos):
        print(f"   - {tipo}: {count}")
    
    # Verificar por categoria
    categorias = db.session.query(OutroCusto.categoria, db.func.count(OutroCusto.id)).group_by(OutroCusto.categoria).all()
    print("\n📊 REGISTROS POR CATEGORIA:")
    for categoria, count in sorted(categorias):
        print(f"   - {categoria}: {count}")
    
    # Verificar valores problemáticos
    print("\n📊 ANÁLISE DE VALORES:")
    
    # Bônus negativos
    bonus_negativos = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%bonus%'),
        OutroCusto.valor < 0
    ).all()
    print(f"   - Bônus negativos: {len(bonus_negativos)}")
    
    # Adicionais negativos
    adicionais_negativos = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%adicional%'),
        OutroCusto.valor < 0
    ).all()
    print(f"   - Adicionais negativos: {len(adicionais_negativos)}")
    
    # Descontos positivos
    descontos_positivos = OutroCusto.query.filter(
        OutroCusto.tipo.ilike('%desconto%'),
        OutroCusto.valor > 0
    ).all()
    print(f"   - Descontos positivos: {len(descontos_positivos)}")
    
    # Registros sem admin_id
    sem_admin_id = OutroCusto.query.filter(OutroCusto.admin_id == None).count()
    print(f"   - Sem admin_id: {sem_admin_id}")
    
    # Mostrar exemplos problemáticos
    if bonus_negativos:
        print("\n📊 EXEMPLOS DE BÔNUS NEGATIVOS:")
        for bonus in bonus_negativos[:3]:
            print(f"   - ID {bonus.id}: {bonus.tipo} = R$ {bonus.valor} (Func: {bonus.funcionario_id})")
    
    if adicionais_negativos:
        print("\n📊 EXEMPLOS DE ADICIONAIS NEGATIVOS:")
        for adicional in adicionais_negativos[:3]:
            print(f"   - ID {adicional.id}: {adicional.tipo} = R$ {adicional.valor} (Func: {adicional.funcionario_id})")
    
    if descontos_positivos:
        print("\n📊 EXEMPLOS DE DESCONTOS POSITIVOS:")
        for desconto in descontos_positivos[:3]:
            print(f"   - ID {desconto.id}: {desconto.tipo} = R$ {desconto.valor} (Func: {desconto.funcionario_id})")
    
    return {
        'total': total,
        'bonus_negativos': len(bonus_negativos),
        'adicionais_negativos': len(adicionais_negativos),
        'descontos_positivos': len(descontos_positivos),
        'sem_admin_id': sem_admin_id,
        'tipos': dict(tipos),
        'categorias': dict(categorias)
    }

def verificar_arquivos_admin_id():
    """Identifica arquivos com referência a admin_id"""
    print("\n🔧 PROCURANDO REFERÊNCIAS A admin_id...")
    
    arquivos_com_admin_id = []
    linhas_problematicas = []
    
    # Procurar em arquivos Python
    for root, dirs, files in os.walk('.'):
        # Ignorar diretórios desnecessários
        if any(ignore in root for ignore in ['__pycache__', '.git', 'venv', 'env']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines, 1):
                            line_lower = line.lower()
                            if 'admin_id' in line_lower and any(term in line_lower for term in ['outro_custo', 'outrocusto']):
                                arquivos_com_admin_id.append(filepath)
                                linhas_problematicas.append({
                                    'arquivo': filepath,
                                    'linha': i,
                                    'conteudo': line.strip()
                                })
                except Exception as e:
                    print(f"   ❌ Erro ao ler {filepath}: {e}")
    
    print("📊 ARQUIVOS COM REFERÊNCIA A admin_id E outro_custo:")
    arquivos_unicos = list(set(arquivos_com_admin_id))
    for arquivo in sorted(arquivos_unicos):
        print(f"   - {arquivo}")
    
    print("\n📊 LINHAS PROBLEMÁTICAS:")
    for linha_info in linhas_problematicas:
        print(f"   {linha_info['arquivo']}:{linha_info['linha']}")
        print(f"     {linha_info['conteudo']}")
    
    return arquivos_unicos, linhas_problematicas

def verificar_templates():
    """Verifica templates relacionados a outros custos"""
    print("\n🔍 VERIFICANDO TEMPLATES...")
    
    templates_relacionados = []
    
    # Procurar em arquivos HTML
    for root, dirs, files in os.walk('templates'):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if any(term in content.lower() for term in ['outro_custo', 'outros custos', 'outrocusto']):
                            templates_relacionados.append(filepath)
                except Exception as e:
                    print(f"   ❌ Erro ao ler {filepath}: {e}")
    
    print("📊 TEMPLATES RELACIONADOS A OUTROS CUSTOS:")
    for template in sorted(templates_relacionados):
        print(f"   - {template}")
        
        # Verificar se tem JavaScript que pode causar erro
        try:
            with open(template, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if 'corrigirImagemQuebrada' in content:
                    print(f"     ✅ Contém função corrigirImagemQuebrada")
                elif 'img' in content.lower() and 'onerror' in content.lower():
                    print(f"     ⚠️  Contém imagens com onerror mas sem função corrigirImagemQuebrada")
        except:
            pass
    
    return templates_relacionados

def main():
    """Executa verificação completa"""
    with app.app_context():
        print("🚨 VERIFICAÇÃO COMPLETA - OUTROS CUSTOS")
        print("=" * 60)
        
        # Estrutura do banco
        colunas, admin_id_existe = verificar_estrutura_banco()
        
        # Modelo Python
        atributos, colunas_modelo, relacionamentos = verificar_modelo_python()
        
        # Rotas
        rotas = verificar_rotas()
        
        # Configuração
        verificar_configuracao()
        
        # Dados atuais
        stats_dados = verificar_dados_outros_custos()
        
        # Arquivos com admin_id
        arquivos_admin, linhas_admin = verificar_arquivos_admin_id()
        
        # Templates
        templates = verificar_templates()
        
        # Gerar relatório final
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO FINAL")
        print("=" * 60)
        
        timestamp = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        print(f"\n🕒 Data/Hora: {timestamp}")
        print(f"📊 Total de registros: {stats_dados['total']}")
        print(f"🔍 Admin_id existe no banco: {admin_id_existe}")
        print(f"📝 Colunas no modelo: {len(colunas_modelo)}")
        print(f"🛣️  Rotas relacionadas: {len(rotas)}")
        print(f"📄 Templates encontrados: {len(templates)}")
        print(f"⚠️  Arquivos com admin_id problemático: {len(arquivos_admin)}")
        
        print(f"\n🚨 PROBLEMAS IDENTIFICADOS:")
        total_problemas = (stats_dados['bonus_negativos'] + 
                          stats_dados['adicionais_negativos'] + 
                          stats_dados['descontos_positivos'])
        
        if total_problemas > 0:
            print(f"   ❌ {total_problemas} registros com valores incorretos")
            print(f"     - Bônus negativos: {stats_dados['bonus_negativos']}")
            print(f"     - Adicionais negativos: {stats_dados['adicionais_negativos']}")
            print(f"     - Descontos positivos: {stats_dados['descontos_positivos']}")
        else:
            print("   ✅ Todos os valores estão corretos!")
        
        if stats_dados['sem_admin_id'] > 0:
            print(f"   ⚠️  {stats_dados['sem_admin_id']} registros sem admin_id")
        
        if len(linhas_admin) > 0:
            print(f"   ⚠️  {len(linhas_admin)} linhas de código com referências problemáticas a admin_id")
        
        print(f"\n📈 STATUS GERAL:")
        if total_problemas == 0 and stats_dados['sem_admin_id'] == 0 and len(linhas_admin) == 0:
            print("   🎉 SISTEMA FUNCIONANDO PERFEITAMENTE!")
        elif total_problemas == 0:
            print("   ✅ VALORES CORRETOS, mas há questões menores")
        else:
            print("   ❌ HÁ PROBLEMAS QUE PRECISAM SER CORRIGIDOS")

if __name__ == "__main__":
    main()