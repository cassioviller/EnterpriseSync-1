# 📋 INSTRUÇÕES DE DEPLOY - SIGE v8.0

## 🚨 Problema Identificado
O banco de dados não está sendo criado no EasyPanel.

## 🔧 Soluções para Testar (Execute uma de cada vez)

### Solução 1: Script Direto
```bash
cd /app && python -c "
from app import app, db
from models import *
with app.app_context():
    print('Criando tabelas...')
    db.create_all()
    print('Tabelas criadas!')
    
    # Listar tabelas
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    print(f'Total de tabelas: {len(tables)}')
    for table in tables:
        print(f'  - {table}')
"
```

### Solução 2: Usar Migrations
```bash
cd /app
export FLASK_APP=app.py
flask db upgrade
```

### Solução 3: Script de Preparação
```bash
cd /app && python preparar_producao_sige_v8.py
```

### Solução 4: Script Mais Simples
```bash
cd /app && python criar_banco_simples.py
```

### Solução 5: Diagnóstico Completo
```bash
cd /app && python test_docker_health.py
```

## 📊 Informações para Você Me Reportar

Após executar qualquer solução, me envie:

1. **Comando executado**
2. **Saída completa** (copie tudo que aparecer)
3. **Se deu erro**, qual foi o erro exato

## 🎯 O que Esperamos Ver

Se funcionar, você deve ver algo como:
```
Criando tabelas...
Tabelas criadas!
Total de tabelas: 33
  - alembic_version
  - centro_custo
  - custo_obra
  - custo_veiculo
  - departamento
  - fluxo_caixa
  - funcao
  - funcionario
  - horario_trabalho
  - obra
  - ... (mais tabelas)
```

## 💡 Dicas de Troubleshooting

Se nada funcionar:
1. Verifique se está no diretório `/app`  
2. Verifique se o arquivo `app.py` existe
3. Tente: `ls -la` para ver os arquivos
4. Tente: `python --version` para ver se Python funciona

Execute uma solução de cada vez e me reporte o resultado!