"""
Script para verificar cobertura de admin_id em todas as tabelas
"""
import re

# Ler models.py
with open('models.py', 'r') as f:
    content = f.read()

# Encontrar todas as classes
class_pattern = r'class (\w+)\(db\.Model\):\s*\n\s*__tablename__\s*=\s*[\'"](\w+)[\'"]'
classes = re.findall(class_pattern, content)

# Verificar admin_id em cada classe
results = []

for class_name, table_name in classes:
    # Encontrar o bloco da classe
    class_start = content.find(f'class {class_name}(db.Model):')
    if class_start == -1:
        continue
    
    # Encontrar o próximo 'class' para delimitar
    next_class = content.find('\nclass ', class_start + 1)
    if next_class == -1:
        class_block = content[class_start:]
    else:
        class_block = content[class_start:next_class]
    
    # Verificar se tem admin_id
    has_admin_id = 'admin_id' in class_block
    
    # Verificar se tem ForeignKey para usuario
    has_fk = 'db.ForeignKey(\'usuario.id\')' in class_block or 'ForeignKey("usuario.id")' in class_block
    
    results.append({
        'class': class_name,
        'table': table_name,
        'has_admin_id': has_admin_id,
        'has_fk': has_fk
    })

# Classificar resultados
print("=" * 100)
print("📊 ANÁLISE COMPLETA: admin_id em TODAS as tabelas do sistema")
print("=" * 100)
print()

# Tabelas COM admin_id
with_admin = [r for r in results if r['has_admin_id']]
without_admin = [r for r in results if not r['has_admin_id']]

print(f"✅ TABELAS COM admin_id: {len(with_admin)}/{len(results)}")
print("─" * 100)
for r in with_admin:
    fk_status = "✅ FK" if r['has_fk'] else "❌ SEM FK"
    print(f"  ✅ {r['table']:40s} (class {r['class']:30s}) {fk_status}")
print()

print(f"❌ TABELAS SEM admin_id: {len(without_admin)}/{len(results)}")
print("─" * 100)
for r in without_admin:
    print(f"  ❌ {r['table']:40s} (class {r['class']:30s})")
print()

# Verificar quais tabelas SEM admin_id são globais (OK) vs multi-tenant (PROBLEMA)
print("=" * 100)
print("🔍 ANÁLISE DE TABELAS SEM admin_id")
print("=" * 100)
print()

# Tabelas que DEVEM ser globais (sem admin_id)
global_tables = {
    'migration_history',  # Sistema
    'tipo_ocorrencia',    # Catálogo global
    'calendario_util',    # Calendário nacional
    'categoria_produto',  # Catálogo global
    'parametros_legais',  # Leis nacionais
    'plano_contas',       # Plano contábil padrão
}

print("✅ TABELAS GLOBAIS (OK sem admin_id):")
print("─" * 100)
for r in without_admin:
    if r['table'] in global_tables:
        print(f"  ✅ {r['table']:40s} - Catálogo/Sistema global")
print()

print("⚠️  TABELAS QUE PODEM PRECISAR DE admin_id:")
print("─" * 100)
for r in without_admin:
    if r['table'] not in global_tables:
        print(f"  ⚠️  {r['table']:40s} (class {r['class']:30s})")
print()

# Resumo
print("=" * 100)
print("📊 RESUMO FINAL")
print("=" * 100)
print(f"Total de tabelas: {len(results)}")
print(f"Com admin_id: {len(with_admin)} ({len(with_admin)*100//len(results)}%)")
print(f"Sem admin_id: {len(without_admin)} ({len(without_admin)*100//len(results)}%)")
print(f"  - Globais (OK): {sum(1 for r in without_admin if r['table'] in global_tables)}")
print(f"  - A verificar: {sum(1 for r in without_admin if r['table'] not in global_tables)}")
print()
