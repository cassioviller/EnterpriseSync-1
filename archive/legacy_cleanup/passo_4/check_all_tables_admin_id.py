"""
Análise completa de admin_id em todas as tabelas
"""
import re

# Ler models.py
with open('models.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar todas as classes
in_class = False
current_class = None
current_table = None
class_content = []
all_classes = []

for i, line in enumerate(lines):
    # Nova classe
    if re.match(r'^class \w+\(db\.Model\):', line):
        # Salvar classe anterior
        if current_class:
            all_classes.append({
                'class': current_class,
                'table': current_table,
                'content': '\n'.join(class_content),
                'line': i
            })
        
        # Nova classe
        current_class = re.search(r'class (\w+)\(', line).group(1)
        current_table = None
        class_content = [line]
        in_class = True
    
    elif in_class:
        class_content.append(line)
        
        # Encontrar tablename
        if '__tablename__' in line and not current_table:
            match = re.search(r'__tablename__\s*=\s*[\'"](\w+)[\'"]', line)
            if match:
                current_table = match.group(1)
        
        # Fim da classe (nova classe ou fim do arquivo)
        if line.strip() == '' and i > 0 and lines[i-1].strip() == '':
            # Duas linhas vazias = fim da classe
            pass

# Adicionar última classe
if current_class:
    all_classes.append({
        'class': current_class,
        'table': current_table or current_class.lower(),
        'content': '\n'.join(class_content),
        'line': len(lines)
    })

# Analisar cada classe
results = []
for cls in all_classes:
    has_admin_id = 'admin_id' in cls['content']
    has_fk_usuario = "ForeignKey('usuario.id')" in cls['content'] or 'ForeignKey("usuario.id")' in cls['content']
    
    # Só adicionar se tiver tablename
    if cls['table']:
        results.append({
            'class': cls['class'],
            'table': cls['table'],
            'has_admin_id': has_admin_id,
            'has_fk': has_fk_usuario,
            'line': cls['line']
        })

# Ordenar por nome
results.sort(key=lambda x: x['table'] or '')

# Exibir resultados
print("=" * 120)
print("📊 ANÁLISE COMPLETA: admin_id em TODAS as {} tabelas do sistema".format(len(results)))
print("=" * 120)
print()

with_admin = [r for r in results if r['has_admin_id']]
without_admin = [r for r in results if not r['has_admin_id']]

print(f"✅ TABELAS COM admin_id: {len(with_admin)}/{len(results)} ({len(with_admin)*100//len(results) if results else 0}%)")
print("─" * 120)
for r in sorted(with_admin, key=lambda x: x['table']):
    fk_status = "✅ FK" if r['has_fk'] else "⚠️  SEM FK"
    print(f"  ✅ {r['table']:45s} {r['class']:35s} {fk_status}")
print()

print(f"❌ TABELAS SEM admin_id: {len(without_admin)}/{len(results)} ({len(without_admin)*100//len(results) if results else 0}%)")
print("─" * 120)

# Tabelas que DEVEM ser globais
GLOBAL_TABLES = {
    'migration_history', 'tipo_ocorrencia', 'calendario_util',
    'parametros_legais', 'categoria_produto',
}

# Tabelas de catálogo que PODEM ser globais ou por tenant
CATALOG_TABLES = {
    'categoria_servico', 'servico_mestre', 'sub_servico',
    'tabela_composicao', 'item_tabela_composicao',
    'subatividade_mestre', 'proposta_template', 'servico_template',
}

for r in sorted(without_admin, key=lambda x: x['table']):
    if r['table'] in GLOBAL_TABLES:
        status = "✅ GLOBAL (OK)"
    elif r['table'] in CATALOG_TABLES:
        status = "🟡 CATÁLOGO (verificar)"
    else:
        status = "🔴 MULTI-TENANT (FALTA admin_id!)"
    
    print(f"  {status:30s} {r['table']:45s} {r['class']:35s}")

print()
print("=" * 120)
print("📊 RESUMO POR CATEGORIA")
print("=" * 120)

global_count = sum(1 for r in without_admin if r['table'] in GLOBAL_TABLES)
catalog_count = sum(1 for r in without_admin if r['table'] in CATALOG_TABLES)
missing_count = sum(1 for r in without_admin if r['table'] not in GLOBAL_TABLES and r['table'] not in CATALOG_TABLES)

print(f"✅ Com admin_id:           {len(with_admin):3d} tabelas")
print(f"✅ Sem admin_id (global):  {global_count:3d} tabelas - OK")
print(f"🟡 Sem admin_id (catálogo): {catalog_count:3d} tabelas - Verificar se devem ser por tenant")
print(f"🔴 Sem admin_id (FALTA):   {missing_count:3d} tabelas - PRECISA adicionar admin_id!")
print()

if missing_count > 0:
    print("⚠️  ATENÇÃO: As seguintes tabelas PODEM precisar de admin_id:")
    print("─" * 120)
    for r in sorted(without_admin, key=lambda x: x['table']):
        if r['table'] not in GLOBAL_TABLES and r['table'] not in CATALOG_TABLES:
            print(f"  🔴 {r['table']:45s} (class {r['class']:30s})")
    print()
