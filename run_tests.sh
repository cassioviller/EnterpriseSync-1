#!/usr/bin/env bash
# run_tests.sh — Executa a suíte de testes Playwright (browser real) do SIGE v9.0
#
# Usa Playwright + Chromium headless (NÃO Flask test client).
# Requer: servidor rodando em http://localhost:5000 (Start application workflow).
#
# Uso:
#   bash run_tests.sh                    # Todos os blocos (pytest)
#   bash run_tests.sh --bloco1           # Apenas BLOCO 1 (Auth)
#   bash run_tests.sh --bloco2           # Apenas BLOCO 2 (Propostas)
#   bash run_tests.sh --bloco3           # Apenas BLOCO 3 (Obras/RDO)
#   bash run_tests.sh --bloco4           # Apenas BLOCO 4 (Folha)
#   bash run_tests.sh --bloco5           # Apenas BLOCO 5 (Almoxarifado)
#   bash run_tests.sh --bloco6           # Apenas BLOCO 6 (Financeiro)
#   bash run_tests.sh --bloco7           # Apenas BLOCO 7 (CRM/Frota/demais)
#   bash run_tests.sh --integracao       # Apenas testes de integração E2E
#   bash run_tests.sh --jornada          # Jornada E2E proposta→cronograma (browser real)
#   bash run_tests.sh --varredura        # Varredura de todas as páginas do menu (browser real)
#   bash run_tests.sh --standalone       # Modo standalone (sem pytest)
#
# Dependências de sistema (instaladas via nix):
#   nspr nss atk cups libdrm xorg.* libxkbcommon mesa pango cairo alsa-lib expat

set -euo pipefail

BLOCO_FILTER=""
STANDALONE=0
TARGET_FILE="tests/test_browser_all_modules.py"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bloco1)       BLOCO_FILTER="::TestBloco1Auth"; shift ;;
        --bloco2)       BLOCO_FILTER="::TestBloco2Propostas"; shift ;;
        --bloco3)       BLOCO_FILTER="::TestBloco3ObrasRdo"; shift ;;
        --bloco4)       BLOCO_FILTER="::TestBloco4Folha"; shift ;;
        --bloco5)       BLOCO_FILTER="::TestBloco5Almoxarifado"; shift ;;
        --bloco6)       BLOCO_FILTER="::TestBloco6Financeiro"; shift ;;
        --bloco7)       BLOCO_FILTER="::TestBloco7Demais"; shift ;;
        --integracao)   BLOCO_FILTER="-k integra"; shift ;;
        --jornada)      TARGET_FILE="tests/test_e2e_jornada_proposta_cronograma_playwright.py"; BLOCO_FILTER=""; shift ;;
        --varredura)    TARGET_FILE="tests/test_e2e_varredura_paginas_playwright.py"; BLOCO_FILTER=""; shift ;;
        --standalone)   STANDALONE=1; shift ;;
        *)              echo "Opção desconhecida: $1"; exit 1 ;;
    esac
done

mkdir -p tests/reports

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_HTML="tests/reports/playwright_report_${TIMESTAMP}.html"
REPORT_LATEST="tests/reports/playwright_report_latest.html"

# Verificar servidor; iniciar em background se não estiver rodando
if ! curl -sf --max-time 3 http://localhost:5000/ > /dev/null 2>&1; then
    echo "[INFO] Servidor não detectado — iniciando em background..."
    .pythonlibs/bin/gunicorn \
        --bind 0.0.0.0:5000 \
        --reuse-port \
        --workers 1 \
        --daemon \
        --pid /tmp/sige_test_gunicorn.pid \
        --log-file /tmp/sige_test_gunicorn.log \
        main:app
    # Aguardar até 20 s para o servidor subir
    for i in $(seq 1 20); do
        sleep 1
        if curl -sf --max-time 2 http://localhost:5000/ > /dev/null 2>&1; then
            echo "[INFO] Servidor iniciado (tentativa ${i})"
            break
        fi
    done
    if ! curl -sf --max-time 3 http://localhost:5000/ > /dev/null 2>&1; then
        echo "[ERRO] Servidor não respondeu após 20 s. Verifique /tmp/sige_test_gunicorn.log"
        exit 1
    fi
    SERVIDOR_INICIADO_AQUI=1
else
    SERVIDOR_INICIADO_AQUI=0
fi
echo "[INFO] Servidor OK em http://localhost:5000"

if [[ $STANDALONE -eq 1 ]]; then
    echo "[INFO] Executando em modo standalone (Python direto + Playwright)..."
    .pythonlibs/bin/python tests/test_browser_all_modules.py
    EXIT_CODE=$?
else
    echo "[INFO] Executando via pytest com Playwright browser real..."
    echo "[INFO] Relatório HTML: ${REPORT_HTML}"

    set +e
    if [[ -n "$BLOCO_FILTER" && "$BLOCO_FILTER" == "-k integra" ]]; then
        .pythonlibs/bin/pytest \
            "tests/test_browser_all_modules.py" \
            -k "integra" \
            --html="${REPORT_HTML}" \
            --self-contained-html \
            --tb=short \
            -v \
            2>&1 | tee "tests/reports/pytest_output_${TIMESTAMP}.txt"
    else
        .pythonlibs/bin/pytest \
            "${TARGET_FILE}${BLOCO_FILTER}" \
            --html="${REPORT_HTML}" \
            --self-contained-html \
            --tb=short \
            -v \
            2>&1 | tee "tests/reports/pytest_output_${TIMESTAMP}.txt"
    fi
    EXIT_CODE=$?
    set -e

    cp "${REPORT_HTML}" "${REPORT_LATEST}" 2>/dev/null || true
    echo ""
    echo "[INFO] Relatório HTML: ${REPORT_HTML}"
    echo "[INFO] Relatório HTML (latest): ${REPORT_LATEST}"
fi

# Parar servidor background, se foi iniciado por este script
if [[ "${SERVIDOR_INICIADO_AQUI:-0}" -eq 1 ]]; then
    if [[ -f /tmp/sige_test_gunicorn.pid ]]; then
        kill "$(cat /tmp/sige_test_gunicorn.pid)" 2>/dev/null || true
        rm -f /tmp/sige_test_gunicorn.pid
        echo "[INFO] Servidor background encerrado."
    fi
fi

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "[SUCESSO] Todos os testes passaram!"
else
    echo "[FALHA] Alguns testes falharam (código: ${EXIT_CODE})"
    echo "        Verifique ${REPORT_LATEST} para detalhes."
fi

exit $EXIT_CODE
