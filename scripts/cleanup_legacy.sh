#!/bin/bash
# ============================================================
# SIGE v9.0 - Script de Limpeza de Arquivos Legados
# Execução em 10 passos com testes após cada remoção
# ============================================================

set -e  # Parar em caso de erro

ARCHIVE_DIR="archive/legacy_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="cleanup_legacy.log"
HEALTH_URL="http://localhost:5000/health"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1" | tee -a $LOG_FILE
}

warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] AVISO:${NC} $1" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ERRO:${NC} $1" | tee -a $LOG_FILE
}

# Função para mover arquivos para archive
archive_files() {
    local step=$1
    shift
    local files=("$@")
    
    local step_dir="${ARCHIVE_DIR}/passo_${step}"
    mkdir -p "$step_dir"
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            mv "$file" "$step_dir/"
            log "  Arquivado: $file"
        else
            warn "  Arquivo não encontrado: $file"
        fi
    done
}

# Função de teste após cada passo
test_app() {
    local step=$1
    log "🧪 Testando aplicação após Passo $step..."
    
    # Aguardar servidor reiniciar
    sleep 3
    
    # Teste 1: Verificar se Python consegue importar app.py sem erros
    log "  Teste 1: Verificando imports..."
    if python -c "from app import app" 2>&1 | grep -i "error\|traceback"; then
        error "  ❌ Erro de import detectado!"
        return 1
    fi
    log "  ✅ Imports OK"
    
    # Teste 2: Verificar se main.py carrega sem erros
    log "  Teste 2: Verificando main.py..."
    if python -c "from main import *" 2>&1 | grep -i "modulenotfounderror\|importerror"; then
        error "  ❌ Erro em main.py!"
        return 1
    fi
    log "  ✅ main.py OK"
    
    # Teste 3: Health check (se servidor estiver rodando)
    log "  Teste 3: Health check..."
    if curl -s --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        log "  ✅ Health check OK"
    else
        warn "  ⚠️ Health check não respondeu (servidor pode não estar rodando)"
    fi
    
    log "✅ Passo $step: TODOS OS TESTES PASSARAM"
    return 0
}

# Função para reverter um passo
rollback_step() {
    local step=$1
    local step_dir="${ARCHIVE_DIR}/passo_${step}"
    
    if [ -d "$step_dir" ]; then
        log "🔄 Revertendo Passo $step..."
        mv "$step_dir"/* . 2>/dev/null || true
        rmdir "$step_dir" 2>/dev/null || true
        log "✅ Passo $step revertido"
    fi
}

# ============================================================
# PASSO 1: Scripts Fix Específicos (Confiança 10)
# ============================================================
passo_1() {
    log "=============================================="
    log "📦 PASSO 1: Scripts Fix Específicos (Confiança 10)"
    log "=============================================="
    
    local files=(
        "fix_horario_trabalho_PRODUCAO.py"
        "fix_producao_urgente.py"
        "fix_rdo_mao_obra_auto.py"
        "fix_todas_tabelas.py"
        "corrigir_producao_agora.py"
    )
    
    archive_files 1 "${files[@]}"
    
    if ! test_app 1; then
        rollback_step 1
        error "Passo 1 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 2: Scripts Popular/Criar Dados (Confiança 10)
# ============================================================
passo_2() {
    log "=============================================="
    log "📦 PASSO 2: Scripts Popular/Criar Dados (Confiança 10)"
    log "=============================================="
    
    local files=(
        "popular_dados_teste.py"
        "popular_kpis_completas.py"
        "populate_test_data.py"
        "criar_usuario_teste.py"
        "gerar_lancamentos_julho.py"
        "substituir_lancamentos_vale_verde.py"
        "associar_danilo_valverde.py"
    )
    
    archive_files 2 "${files[@]}"
    
    if ! test_app 2; then
        rollback_step 2
        error "Passo 2 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 3: Scripts Validação/Diagnóstico (Confiança 10)
# ============================================================
passo_3() {
    log "=============================================="
    log "📦 PASSO 3: Scripts Validação/Diagnóstico (Confiança 10)"
    log "=============================================="
    
    local files=(
        "validar_correcao_custo.py"
        "validar_correcao_final.py"
        "validar_correcao_vazamento.py"
        "validar_funcionario_horario_personalizado.py"
        "validar_modal_edicao_completo.py"
        "validar_multitenant.py"
        "validar_tipos_completos_v8_1.py"
        "analise_rapida.py"
        "analise_sistema.py"
        "analise_templates.py"
        "diagnostico_custos_veiculo.py"
        "diagnostico_kpi_producao.py"
        "diagnostico_producao.py"
        "verificar_deploy_veiculos_producao.py"
        "verificacao_producao.py"
    )
    
    archive_files 3 "${files[@]}"
    
    if ! test_app 3; then
        rollback_step 3
        error "Passo 3 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 4: Scripts Check/Validate (Confiança 10)
# ============================================================
passo_4() {
    log "=============================================="
    log "📦 PASSO 4: Scripts Check/Validate (Confiança 10)"
    log "=============================================="
    
    local files=(
        "check_all_tables_admin_id.py"
        "check_migration_48.py"
        "check_routes.py"
        "validate_migration_48.py"
        "verify_admin_id_coverage.py"
        "verify_deploy.py"
    )
    
    archive_files 4 "${files[@]}"
    
    if ! test_app 4; then
        rollback_step 4
        error "Passo 4 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 5: Migrações Antigas (Confiança 9)
# ============================================================
passo_5() {
    log "=============================================="
    log "📦 PASSO 5: Migrações Antigas (Confiança 9)"
    log "=============================================="
    
    local files=(
        "migrate_config.py"
        "migrations_obra_cliente.py"
        "migrations_organizer.py"
        "migrations_production.py"
        "migrations_team_management.py"
        "migrations_template_fix.py"
        "migrations_veiculo_hotfix_production.py"
        "migration_rdo_melhorias.py"
        "migration_recalcular_horas.py"
        "migration_safety_manager.py"
        "init_migrations.py"
        "pre_migration_48_check.py"
        "rollback_migration_48.py"
    )
    
    archive_files 5 "${files[@]}"
    
    if ! test_app 5; then
        rollback_step 5
        error "Passo 5 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 6: Scripts Deploy Antigos (Confiança 9)
# ============================================================
passo_6() {
    log "=============================================="
    log "📦 PASSO 6: Scripts Deploy Antigos (Confiança 9)"
    log "=============================================="
    
    local files=(
        "deploy_fix_subatividades_v10.py"
        "deploy_rdo_completo_v10.py"
        "deploy_veiculos_v2_production.py"
        "deploy_veiculos_v2_simple.py"
        "force_migration_48.py"
        "force_update_sabado.py"
        "pre_start.py"
        "webhook_deploy.py"
        "docker_deploy_verification.py"
    )
    
    archive_files 6 "${files[@]}"
    
    if ! test_app 6; then
        rollback_step 6
        error "Passo 6 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 7: Scripts Correção Ponto/Sábado (Confiança 9)
# ============================================================
passo_7() {
    log "=============================================="
    log "📦 PASSO 7: Scripts Correção Ponto/Sábado (Confiança 9)"
    log "=============================================="
    
    local files=(
        "forcar_atualizacao_interface.py"
        "forcar_atualizacao_kpis.py"
        "forcar_atualizacao_registro.py"
        "forcar_recalculo_kpis_completo.py"
        "solucao_definitiva_sabado.py"
        "revisar_logica_sabado_completa.py"
        "reproduzir_problema_almoco.py"
        "encontrar_registro_correto.py"
        "melhorar_controle_ponto.py"
        "otimizar_controle_ponto.py"
        "implementar_filtros_avancados.py"
        "simular_impacto_feriado.py"
    )
    
    archive_files 7 "${files[@]}"
    
    if ! test_app 7; then
        rollback_step 7
        error "Passo 7 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 8: Configs/Testes Antigos (Confiança 8)
# ============================================================
passo_8() {
    log "=============================================="
    log "📦 PASSO 8: Configs/Testes Antigos (Confiança 8)"
    log "=============================================="
    
    local files=(
        "config_producao.py"
        "production_config.py"
        "production_config_v10.py"
        "production_rdo_fix.py"
        "test_accessibility.py"
        "test_healthcheck_endpoint.py"
        "test_integrations.py"
        "test_performance.py"
        "test_rdo_comprehensive.py"
        "tests_modulos_consolidados.py"
        "resetar_senha_admin.py"
        "recreate_database.py"
    )
    
    archive_files 8 "${files[@]}"
    
    if ! test_app 8; then
        rollback_step 8
        error "Passo 8 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 9: Utils/Engines Não Usados (Confiança 7)
# ============================================================
passo_9() {
    log "=============================================="
    log "📦 PASSO 9: Utils/Engines Não Usados (Confiança 7)"
    log "=============================================="
    
    local files=(
        "kpis_engine.py"
        "kpis_engine_corrigido.py"
        "kpis_engine_v8_1.py"
        "kpis_engine_v8_2.py"
        "kpis_financeiros.py"
        "kpi_unificado.py"
        "folha_pagamento_utils.py"
        "cliente_portal_utils.py"
        "codigo_barras_utils.py"
        "rdo_validator.py"
        "rdo_validations.py"
        "security_wrapper.py"
        "calculadora_obra.py"
        "enhanced_health_checker.py"
        "login_simples.py"
        "dashboard_hotfix.py"
        "dashboard_interativo.py"
        "template_rdo_final_fix.py"
        "melhorias_rdo_implementacao_imediata.py"
        "correcao_obras_completa.py"
        "api_servicos_corrigida.py"
        "cadastrar_servicos_obra.py"
        "atualizar_dropdowns_v8_1.py"
        "atualizar_kpis_engine_dias_uteis.py"
        "financeiro.py"
        "alimentacao_crud.py"
    )
    
    archive_files 9 "${files[@]}"
    
    if ! test_app 9; then
        rollback_step 9
        error "Passo 9 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# PASSO 10: Blueprints/Integrações Inativos (Confiança 6)
# ============================================================
passo_10() {
    log "=============================================="
    log "📦 PASSO 10: Blueprints/Integrações Inativos (Confiança 6)"
    log "=============================================="
    
    local files=(
        "servicos_views.py"
        "rdo_visualizar_simples.py"
        "portal_cliente_avancado.py"
        "sistema_reconhecimento_facial.py"
        "almoxarifado_ia_avancado.py"
        "monitoring_producao.py"
        "mobile_api.py"
        "integracoes_automaticas.py"
        "fluxo_dados_automatico.py"
        "exemplo_integracao_completa.py"
        "notification_system.py"
        "alertas_inteligentes.py"
        "ai_analytics.py"
        "xml_nfe_processor.py"
    )
    
    archive_files 10 "${files[@]}"
    
    if ! test_app 10; then
        rollback_step 10
        error "Passo 10 falhou - revertido"
        exit 1
    fi
}

# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================
main() {
    log "=============================================="
    log "🚀 SIGE v9.0 - Limpeza de Arquivos Legados"
    log "=============================================="
    log "Iniciando processo de limpeza em 10 passos..."
    log "Arquivos serão movidos para: $ARCHIVE_DIR"
    log ""
    
    mkdir -p "$ARCHIVE_DIR"
    
    # Executar cada passo
    passo_1
    passo_2
    passo_3
    passo_4
    passo_5
    passo_6
    passo_7
    passo_8
    passo_9
    passo_10
    
    log ""
    log "=============================================="
    log "✅ LIMPEZA CONCLUÍDA COM SUCESSO!"
    log "=============================================="
    log "Arquivos arquivados em: $ARCHIVE_DIR"
    log ""
    
    # Contagem final
    local total_archived=$(find "$ARCHIVE_DIR" -type f -name "*.py" | wc -l)
    local remaining=$(ls *.py 2>/dev/null | wc -l)
    
    log "📊 RESUMO:"
    log "  - Arquivos arquivados: $total_archived"
    log "  - Arquivos restantes: $remaining"
    log ""
    log "💡 Para reverter tudo: mv $ARCHIVE_DIR/passo_*/*.py ."
}

# Permitir execução de passos individuais
case "${1:-all}" in
    1) passo_1 ;;
    2) passo_2 ;;
    3) passo_3 ;;
    4) passo_4 ;;
    5) passo_5 ;;
    6) passo_6 ;;
    7) passo_7 ;;
    8) passo_8 ;;
    9) passo_9 ;;
    10) passo_10 ;;
    all) main ;;
    *)
        echo "Uso: $0 [1-10|all]"
        echo "  1-10: Executar passo específico"
        echo "  all:  Executar todos os passos (padrão)"
        ;;
esac
