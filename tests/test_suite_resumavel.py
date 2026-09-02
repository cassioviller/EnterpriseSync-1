"""O runner retomável da suíte, conferido no gate.

Por que este arquivo existe: em 01/09 três gates e uma suíte morreram com a
sessão, e o registro que sobrou dizia "interrompida a ~18% com 2 FAILED".
O log real dizia 62% e 7 FAILED. Um placar parcial foi lido como se fosse o
placar, e uma decisão foi tomada em cima dele.

O runner existe para que isso não seja possível: progresso durável por chunk
(uma morte custa um chunk, não 46 minutos) e um veredito que **grita
INCOMPLETO** quando falta chunk, em vez de somar o que tem e parecer verde.

⚠️ O teste que mais importa aqui é `test_veredito_de_rodada_incompleta...`.
Se ele for afrouxado, o runner volta a poder mentir — que é o defeito que ele
foi escrito para tornar impossível.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import suite_resumavel as sr  # mesmo padrão de test_cronograma_diagnostico_tenant.py

pytestmark = pytest.mark.integration

DIR_TESTES = os.path.dirname(os.path.abspath(__file__))


# ── leitura do placar do pytest ──────────────────────────────────────────────

def test_placar_e_lido_da_linha_de_resumo_do_pytest():
    linha = "= 12 failed, 3333 passed, 8 skipped, 72 xfailed, 16855 warnings, 68 errors in 2768.05s (0:46:08) ="
    assert sr.parse_placar(linha) == {
        "failed": 12, "passed": 3333, "skipped": 8, "xfailed": 72, "errors": 68,
    }


def test_placar_do_modo_quieto_tambem_e_lido():
    """Em -q o pytest imprime o resumo SEM os "=" em volta. Se o leitor exigir
    os "=", toda rodada quieta vira "não terminou" e o runner nunca fecha."""
    assert sr.parse_placar("11 passed in 0.14s") == {
        "failed": 0, "passed": 11, "skipped": 0, "xfailed": 0, "errors": 0,
    }
    assert sr.parse_placar("2 failed, 18 passed in 6.61s") == {
        "failed": 2, "passed": 18, "skipped": 0, "xfailed": 0, "errors": 0,
    }


def test_placar_de_rodada_limpa_zera_o_que_nao_apareceu():
    assert sr.parse_placar("= 20 passed in 1.18s =") == {
        "failed": 0, "passed": 20, "skipped": 0, "xfailed": 0, "errors": 0,
    }


def test_linha_que_nao_e_resumo_nao_vira_placar():
    """Sem isto, um log truncado no meio viraria placar de zeros — que soma
    igual a "tudo passou". Foi exatamente assim que o registro de 01/09 mentiu."""
    assert sr.parse_placar("tests/test_x.py::test_y PASSED [ 62%]") is None
    assert sr.parse_placar("") is None


# ── divisão em chunks ────────────────────────────────────────────────────────

def test_todo_arquivo_de_teste_entra_em_exatamente_um_chunk():
    """Um runner que perde arquivo em silêncio é pior que nenhum runner."""
    chunks = sr.descobrir_chunks(DIR_TESTES)
    distribuidos = [arq for c in chunks for arq in c.arquivos]
    na_pasta = sorted(
        n for n in os.listdir(DIR_TESTES)
        if n.startswith("test_") and n.endswith(".py")
    )
    assert sorted(distribuidos) == na_pasta
    assert len(distribuidos) == len(set(distribuidos)), "arquivo em dois chunks"


def test_tamanho_do_chunk_de_gate_e_parametrizavel():
    """Necessário para provar a retomada de verdade num diretório sintético,
    sem esperar 4 min por chunk de 20 arquivos."""
    chunks = sr.descobrir_chunks(DIR_TESTES, tamanho_chunk_gate=3)
    de_gate = [c for c in chunks if c.nome.startswith("gate_")]
    assert de_gate, "nenhum chunk de gate"
    assert all(len(c.arquivos) <= 3 for c in de_gate)
    assert max(len(c.arquivos) for c in de_gate) == 3


def test_arquivo_de_browser_roda_sozinho_no_seu_chunk():
    """Isolamento de processo é o que impede um arquivo de derrubar o próximo —
    a lição de 02/09 (fixture de sessão, 80 baixas). Ver
    tests/test_contrato_isolamento_playwright.py."""
    chunks = sr.descobrir_chunks(DIR_TESTES)
    por_arquivo = {arq: c for c in chunks for arq in c.arquivos}
    chunk = por_arquivo["test_browser_all_modules.py"]
    assert chunk.arquivos == ["test_browser_all_modules.py"]


# ── retomada ─────────────────────────────────────────────────────────────────

def test_chunk_com_registro_no_ledger_nao_roda_de_novo(tmp_path):
    chunks = sr.descobrir_chunks(DIR_TESTES)
    dir_done = tmp_path / "done"
    dir_done.mkdir()
    primeiro = chunks[0]
    (dir_done / f"{primeiro.nome}.json").write_text(json.dumps(
        {"chunk": primeiro.nome, "arquivos": primeiro.arquivos,
         "placar": {"passed": 1, "failed": 0,
         "skipped": 0, "xfailed": 0, "errors": 0}, "exit_code": 0}))

    pendentes = sr.chunks_pendentes(chunks, str(dir_done))

    assert primeiro.nome not in [c.nome for c in pendentes]
    assert len(pendentes) == len(chunks) - 1


def test_registro_de_outro_conjunto_de_arquivos_nao_conta_como_feito(tmp_path):
    """Os nomes de chunk são posicionais (gate_00, gate_01...). Acrescentar um
    arquivo de teste desloca a numeração, e o registro de ontem passa a ter o
    nome de um chunk que hoje cobre OUTROS arquivos. Se a retomada olhar só o
    nome, ela pula um chunk que nunca rodou — e o veredito diz completo sobre
    uma rodada furada. O registro só vale para a lista de arquivos que gravou.
    """
    chunks = sr.descobrir_chunks(DIR_TESTES)
    dir_done = tmp_path / "done"
    dir_done.mkdir()
    primeiro = chunks[0]
    (dir_done / f"{primeiro.nome}.json").write_text(json.dumps({
        "chunk": primeiro.nome,
        "arquivos": ["test_arquivo_que_nao_esta_mais_neste_chunk.py"],
        "placar": {"passed": 1, "failed": 0, "skipped": 0, "xfailed": 0, "errors": 0},
        "exit_code": 0,
    }))

    pendentes = sr.chunks_pendentes(chunks, str(dir_done))

    assert primeiro.nome in [c.nome for c in pendentes], (
        "registro de outro conjunto de arquivos foi aceito como se fosse deste chunk"
    )


def test_ledger_vazio_deixa_tudo_pendente(tmp_path):
    chunks = sr.descobrir_chunks(DIR_TESTES)
    assert len(sr.chunks_pendentes(chunks, str(tmp_path))) == len(chunks)


# ── veredito ─────────────────────────────────────────────────────────────────

def _registro(nome, **placar):
    base = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "errors": 0}
    base.update(placar)
    return {"chunk": nome, "placar": base, "exit_code": 1 if base["failed"] or base["errors"] else 0}


def test_veredito_soma_os_placares_dos_chunks():
    texto, codigo = sr.veredito(
        total_de_chunks=2,
        registros=[_registro("a", passed=10), _registro("b", passed=5, skipped=2)],
    )
    assert "15 passed" in texto
    assert "2 skipped" in texto
    assert codigo == 0


def test_veredito_de_rodada_incompleta_diz_incompleto_e_sai_diferente_de_zero():
    """O coração deste arquivo. Faltando chunk, NÃO existe placar — existe uma
    rodada incompleta. Somar o que veio e chamar de verde é o defeito."""
    texto, codigo = sr.veredito(
        total_de_chunks=10,
        registros=[_registro("a", passed=10), _registro("b", passed=5)],
    )
    assert "INCOMPLETO" in texto
    assert "2 de 10" in texto
    assert codigo != 0, "rodada incompleta jamais pode sair com 0"
    assert "SUCESSO" not in texto


def test_veredito_completo_com_falha_nao_diz_sucesso():
    texto, codigo = sr.veredito(
        total_de_chunks=2,
        registros=[_registro("a", passed=10), _registro("b", passed=5, failed=1)],
    )
    assert "INCOMPLETO" not in texto
    assert "SUCESSO" not in texto
    assert "1 failed" in texto
    assert codigo != 0


def test_veredito_completo_e_verde_diz_sucesso():
    texto, codigo = sr.veredito(
        total_de_chunks=1, registros=[_registro("a", passed=10)],
    )
    assert "SUCESSO" in texto
    assert codigo == 0


# ── a ponte com o run_tests.sh ───────────────────────────────────────────────

def test_run_tests_sh_aceita_arquivos_e_roda_exatamente_eles(tmp_path):
    """A ponte entre o runner e o ambiente (libs do Chromium, servidor).

    Se `--arquivos` não chegar ao pytest com os alvos certos, o chunk roda
    outra coisa, a linha de resumo aparece do mesmo jeito e o runner grava um
    placar ERRADO como se fosse o do chunk — falha silenciosa. Por isso este
    teste confere a contagem, não só a existência do resumo.
    """
    alvo = "tests/test_contrato_isolamento_playwright.py"
    esperado = sr.parse_placar(
        _pytest_direto(alvo)
    )
    assert esperado is not None, "não consegui medir o alvo direto pelo pytest"

    log = tmp_path / "ponte.log"
    with open(log, "w", encoding="utf-8") as saida:
        subprocess.run(["bash", "run_tests.sh", "--arquivos", alvo],
                       cwd=sr.RAIZ, stdout=saida, stderr=subprocess.STDOUT,
                       env={**os.environ, "PYTHONUNBUFFERED": "1"}, timeout=600)

    obtido = sr.placar_do_log(str(log))
    assert obtido is not None, (
        f"run_tests.sh --arquivos não produziu linha de resumo. Log: {log.read_text()[-800:]}"
    )
    assert obtido == esperado, (
        f"run_tests.sh --arquivos rodou coisa diferente do pytest direto: "
        f"{obtido} != {esperado}"
    )


def _pytest_direto(alvo):
    saida = subprocess.run(
        [sys.executable, "-m", "pytest", alvo, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=sr.RAIZ, capture_output=True, text=True, timeout=600,
    ).stdout
    for linha in reversed(saida.splitlines()):
        if sr.parse_placar(linha) is not None:
            return linha
    return ""
