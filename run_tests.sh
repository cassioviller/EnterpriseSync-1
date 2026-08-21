#!/usr/bin/env bash
# run_tests.sh — Executa a suíte de testes Playwright (browser real) do SIGE v9.0
#
# Usa Playwright + Chromium headless (NÃO Flask test client).
# Requer: servidor rodando em http://localhost:5000 (Start application workflow).
#
# Uso:
#   bash run_tests.sh                    # Smoke browser canônico (test_browser_all_modules)
#   bash run_tests.sh --gate             # Gate rápido: pytest tests/ -m "not browser" (lógica/DB/HTTP)
#   bash run_tests.sh --suite            # Suíte INTEIRA: pytest tests/ (gate + browser)
#   bash run_tests.sh --bloco1           # Apenas BLOCO 1 (Auth)
#   bash run_tests.sh --bloco2           # Apenas BLOCO 2 (Propostas)
#   bash run_tests.sh --bloco3           # Apenas BLOCO 3 (Obras/RDO)
#   bash run_tests.sh --bloco4           # Apenas BLOCO 4 (Folha)
#   bash run_tests.sh --bloco5           # Apenas BLOCO 5 (Almoxarifado)
#   bash run_tests.sh --bloco6           # Apenas BLOCO 6 (Financeiro)
#   bash run_tests.sh --bloco7           # Apenas BLOCO 7 (CRM/Frota/demais)
#   bash run_tests.sh --integracao       # Apenas testes de integração E2E
#   bash run_tests.sh --java             # Família que sobe a JVM/MPXJ (pula sem JDK)
#   bash run_tests.sh --jornada          # Jornada E2E proposta→cronograma (browser real)
#   bash run_tests.sh --varredura        # Varredura de todas as páginas do menu (browser real)
#   bash run_tests.sh --standalone       # Modo standalone (sem pytest)
#
# Dependências de sistema do Chromium (nspr, nss, libgbm, libxkbcommon, libudev,
# alsa): NÃO vêm do .replit. Este script as resolve sozinho via nix-build e
# cacheia o LD_LIBRARY_PATH em .cache/ms-playwright/ld-library-path.txt —
# ver garantir_libs_chromium() abaixo.

set -euo pipefail

BLOCO_FILTER=""
MARKER_ARGS=()
STANDALONE=0
TARGET_FILE="tests/test_browser_all_modules.py"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --gate)         TARGET_FILE="tests/"; MARKER_ARGS=(-m "not browser"); shift ;;
        --suite)        TARGET_FILE="tests/"; shift ;;
        --bloco1)       BLOCO_FILTER="::TestBloco1Auth"; shift ;;
        --bloco2)       BLOCO_FILTER="::TestBloco2Propostas"; shift ;;
        --bloco3)       BLOCO_FILTER="::TestBloco3ObrasRdo"; shift ;;
        --bloco4)       BLOCO_FILTER="::TestBloco4Folha"; shift ;;
        --bloco5)       BLOCO_FILTER="::TestBloco5Almoxarifado"; shift ;;
        --bloco6)       BLOCO_FILTER="::TestBloco6Financeiro"; shift ;;
        --bloco7)       BLOCO_FILTER="::TestBloco7Demais"; shift ;;
        --integracao)   BLOCO_FILTER="-k integra"; shift ;;
        # --java roda SÓ a família com JVM (parser MPXJ, migração das baias).
        # O --gate continua incluindo essa família: sem JDK ela pula sozinha
        # (marcador registrado em tests/conftest.py), com JDK ela cobre.
        --java)         TARGET_FILE="tests/"; MARKER_ARGS=(-m "java"); shift ;;
        --jornada)      TARGET_FILE="tests/test_e2e_jornada_proposta_cronograma_playwright.py"; BLOCO_FILTER=""; shift ;;
        --varredura)    TARGET_FILE="tests/test_e2e_varredura_paginas_playwright.py"; BLOCO_FILTER=""; shift ;;
        --standalone)   STANDALONE=1; shift ;;
        *)              echo "Opção desconhecida: $1"; exit 1 ;;
    esac
done

mkdir -p tests/reports

# Chromium do Playwright precisa de libs de sistema que este ambiente não tem
# no caminho padrão (🔬 21/08: `ldd` acusa libnspr4, libnss3, libgbm,
# libxkbcommon, libudev e libasound). Sem elas, todo teste de browser morre em
# "BrowserType.launch: Target page, context or browser has been closed".
# Resolve via nix-build das saídas `out` — `nix-shell -p` daria as `-dev`, que
# só têm headers — e cacheia o resultado para não reconstruir a cada execução.
# No nixpkgs 25.05 a libgbm é pacote separado do mesa.
garantir_libs_chromium() {
    local bin cache outs libs p
    bin=$(ls -d .cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>/dev/null | head -1 || true)
    [[ -z "$bin" ]] && return 0                       # sem Chromium instalado: nada a fazer
    if ! ldd "$bin" 2>/dev/null | grep -q "not found"; then return 0; fi

    cache=".cache/ms-playwright/ld-library-path.txt"
    if [[ -s "$cache" ]]; then
        export LD_LIBRARY_PATH="$(cat "$cache")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        if ! ldd "$bin" 2>/dev/null | grep -q "not found"; then
            echo "[INFO] Libs do Chromium via cache ($cache)"
            return 0
        fi
    fi
    if ! command -v nix-build >/dev/null 2>&1; then
        echo "[AVISO] Chromium sem libs de sistema e sem nix-build — testes de browser vão falhar no launch"
        return 0
    fi

    echo "[INFO] Resolvendo libs do Chromium via nix-build (nspr nss mesa libgbm libxkbcommon systemd alsa-lib)..."
    outs=$(timeout 300 nix-build --no-out-link '<nixpkgs>' \
            -A nspr -A nss -A mesa -A libgbm -A libxkbcommon -A systemd -A alsa-lib 2>/dev/null || true)
    libs=""
    for p in $outs; do [[ -d "$p/lib" ]] && libs="$libs:$p/lib"; done
    libs="${libs#:}"
    if [[ -z "$libs" ]]; then
        echo "[AVISO] nix-build não devolveu caminhos — testes de browser vão falhar no launch"
        return 0
    fi
    export LD_LIBRARY_PATH="$libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    if ldd "$bin" 2>/dev/null | grep -q "not found"; then
        echo "[AVISO] ainda faltam libs ao Chromium:"
        ldd "$bin" 2>/dev/null | grep "not found"
    else
        echo "$libs" > "$cache"
        echo "[INFO] Libs do Chromium resolvidas e cacheadas em $cache"
    fi
}
garantir_libs_chromium

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
            "${MARKER_ARGS[@]}" \
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
