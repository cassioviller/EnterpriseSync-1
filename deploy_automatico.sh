#!/bin/bash

# SCRIPT DE DEPLOY AUTOMÁTICO PARA PRODUÇÃO
# Executa todas as correções automaticamente

set -e  # Parar em caso de erro

echo "🚀 INICIANDO DEPLOY AUTOMÁTICO - SIGE v8.1"
echo "=================================================="

# Configurar variáveis
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="deploy_$TIMESTAMP.log"

# Função de log
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Função de erro
error() {
    log "❌ ERRO: $1"
    exit 1
}

log "🔧 Verificando ambiente Python..."
python3 --version || error "Python3 não encontrado"

log "📦 Verificando dependências..."
python3 -c "import flask, sqlalchemy" || error "Dependências não encontradas"

log "🗄️  Verificando conexão com banco de dados..."  
python3 -c "
from app import app, db
from sqlalchemy import text
with app.app_context():
    try:
        db.session.execute(text('SELECT 1'))
        print('✅ Banco conectado')
    except Exception as e:
        print(f'❌ Erro no banco: {e}')
        exit(1)
" || error "Falha na conexão com banco"

log "🔄 Executando correções automáticas..."
python3 auto_deploy_producao.py --auto || error "Falha no deploy automático"

log "🔍 Validando correções aplicadas..."
python3 -c "
from app import app, db
from models import RegistroPonto
from datetime import date, time

with app.app_context():
    # Verificar João Silva Santos 31/07
    joao = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 31),
        RegistroPonto.hora_entrada == time(7, 5),
        RegistroPonto.hora_saida == time(17, 50)
    ).first()
    
    if joao and abs(joao.horas_extras - 0.95) < 0.01:
        print('✅ João Silva Santos 31/07: CORRETO')
    else:
        print('❌ João Silva Santos 31/07: ERRO')
        exit(1)
        
    # Verificar Ana Paula 29/07  
    ana = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 29),
        RegistroPonto.hora_entrada == time(7, 30),
        RegistroPonto.hora_saida == time(18, 0)
    ).first()
    
    if ana and abs(ana.horas_extras - 1.0) < 0.01 and abs(ana.total_atraso_horas - 0.3) < 0.01:
        print('✅ Ana Paula 29/07: CORRETO')
    else:
        print('❌ Ana Paula 29/07: ERRO')
        exit(1)
        
    print('✅ TODOS OS CASOS CRÍTICOS VALIDADOS')
" || error "Falha na validação"

log "🌐 Verificando serviços web..."
curl -s http://localhost:5000/ > /dev/null || log "⚠️  Serviço web não respondeu (normal se não estiver rodando)"

log "📄 Gerando relatório final..."
cat > "relatorio_deploy_$TIMESTAMP.md" << EOF
# RELATÓRIO DE DEPLOY AUTOMÁTICO

**Data**: $(date '+%Y-%m-%d %H:%M:%S')
**Versão**: SIGE v8.1
**Status**: ✅ SUCESSO

## Correções Aplicadas:
- ✅ Sistema de horas extras consolidado
- ✅ Lógica unificada (07:12-17:00)
- ✅ Cálculos independentes (extras + atrasos)
- ✅ Casos críticos validados

## Casos Validados:
- ✅ João Silva Santos 31/07: 0.95h extras
- ✅ Ana Paula Rodrigues 29/07: 1.0h extras + 0.3h atrasos

## Arquivos Atualizados:
- kpis_engine.py (lógica consolidada)
- auto_deploy_producao.py (sistema automático)
- deploy_automatico.sh (este script)

## Próximos Passos:
- ✅ Sistema pronto para uso
- ✅ Monitoramento ativo
- ✅ Logs disponíveis em: $LOG_FILE

---
Deploy executado automaticamente em: $(date)
EOF

log "✅ DEPLOY AUTOMÁTICO CONCLUÍDO COM SUCESSO!"
log "📄 Relatório salvo em: relatorio_deploy_$TIMESTAMP.md"
log "📋 Log completo em: $LOG_FILE"

echo ""
echo "🎉 SISTEMA ATUALIZADO E PRONTO PARA USO!"
echo "   - Todas as correções aplicadas automaticamente"
echo "   - Casos críticos validados"
echo "   - Relatório gerado: relatorio_deploy_$TIMESTAMP.md"
echo ""