"""Task #11 + Task #38 — pytest do helper utils.rdo_horas.normalizar_horas_funcionario.

Cobre:
  * Comportamento histórico (divisão igual entre N atividades) — Task #11.
  * Distribuição com pesos via argumento `pesos` — Task #38.

Os casos vêm direto da seção "Steps → Testes" da Task #38:
  - Funcionário em 1 tarefa → não altera, painel não aparece.
  - 2 tarefas, principal 70 → 5,6h / 2,4h.
  - 2 tarefas, principal 50 → 4h / 4h.
  - 3 tarefas, principal 80 → 6,4h / 0,8h / 0,8h.
  - 3 tarefas, principal 100 → 8h / 0h / 0h.
  - 3 tarefas, principal 0 → 0h / 4h / 4h.
  - 3 tarefas, sem peso (apontador pulou) → 8/3h cada.
  - Mistura: principal com peso, NULLs dividem o restante igual.

Task #5 — hora extra removida do RDO. As tuplas agora seguem o
formato ``(func_id, atividade_key, horas, *meta)`` (sem horas_extras).

Executar com:
    pytest tests/utils/test_rdo_horas.py -q
"""
from __future__ import annotations

import math
import os
import sys

# Permitir rodar via `python tests/utils/test_rdo_horas.py` direto também.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.rdo_horas import normalizar_horas_funcionario


def _horas_por_chave(resultado, func_id):
    """Devolve dict {atividade_key: horas} para o func_id pedido."""
    return {
        item[1]: item[2]
        for item in resultado
        if item[0] == func_id
    }


def _aprox(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(a, b, abs_tol=tol)


# ── Comportamento histórico (sem pesos) ─────────────────────────────────


def test_funcionario_em_uma_tarefa_nao_altera():
    entries = [(10, ('sub', 'A'), 8.0)]
    resultado = normalizar_horas_funcionario(entries)
    assert resultado == [(10, ('sub', 'A'), 8.0)]


def test_funcionario_em_uma_tarefa_painel_nao_aparece_helper_sem_pesos():
    """Mesmo que o caller passe `pesos`, helper ignora se N==1 (sem painel)."""
    entries = [(10, ('sub', 'A'), 8.0)]
    resultado = normalizar_horas_funcionario(
        entries, pesos={(10, ('sub', 'A')): 70}
    )
    assert resultado == [(10, ('sub', 'A'), 8.0)]


def test_divisao_igual_entre_3_atividades_quando_sem_peso():
    """Cenário histórico: 3 tarefas, sem pesos → 8/3h cada (~2,67h)."""
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (10, ('sub', 'C'), 8.0),
    ]
    resultado = normalizar_horas_funcionario(entries)
    horas = _horas_por_chave(resultado, 10)
    esperado = 8.0 / 3.0
    for k in [('sub', 'A'), ('sub', 'B'), ('sub', 'C')]:
        assert _aprox(horas[k], esperado), f"chave {k}: {horas[k]} != {esperado}"


def test_divisao_igual_preserva_metadados():
    entries = [
        (10, ('sub', 'A'), 8.0, 'pedreiro'),
        (10, ('sub', 'B'), 8.0, 'pedreiro'),
    ]
    resultado = normalizar_horas_funcionario(entries)
    for item in resultado:
        assert _aprox(item[2], 4.0)
        assert item[3] == 'pedreiro'


# ── Distribuição com pesos (Task #38) ────────────────────────────────────


def test_2_tarefas_principal_70_gera_56h_e_24h():
    """Caso clássico do PRD: 8h, principal 70% → 5,6h / 2,4h."""
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 70}  # 'B' fica NULL
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 5.6)
    assert _aprox(horas[('sub', 'B')], 2.4)


def test_2_tarefas_principal_50_gera_4h_e_4h():
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 50}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 4.0)
    assert _aprox(horas[('sub', 'B')], 4.0)


def test_3_tarefas_principal_80_gera_64h_e_08h_e_08h():
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (10, ('sub', 'C'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 80}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 6.4)
    assert _aprox(horas[('sub', 'B')], 0.8)
    assert _aprox(horas[('sub', 'C')], 0.8)


def test_3_tarefas_principal_100_gera_8h_e_zeros():
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (10, ('sub', 'C'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 100}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 8.0)
    assert _aprox(horas[('sub', 'B')], 0.0)
    assert _aprox(horas[('sub', 'C')], 0.0)


def test_3_tarefas_principal_0_gera_0h_e_4h_e_4h():
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (10, ('sub', 'C'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 0}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 0.0)
    assert _aprox(horas[('sub', 'B')], 4.0)
    assert _aprox(horas[('sub', 'C')], 4.0)


def test_mistura_peso_principal_e_outros_null_distribuem_restante():
    """3 tarefas, principal 60%, outras 2 NULL → 4,8h / 1,6h / 1,6h."""
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (10, ('sub', 'C'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 60}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas = _horas_por_chave(resultado, 10)
    assert _aprox(horas[('sub', 'A')], 4.8)
    assert _aprox(horas[('sub', 'B')], 1.6)
    assert _aprox(horas[('sub', 'C')], 1.6)


def test_pesos_so_de_um_funcionario_nao_afetam_outro_grupo():
    """Funcionário 11 não tem pesos → mantém divisão igual mesmo
    quando o funcionário 10 tem pesos definidos no mesmo dict."""
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
        (11, ('sub', 'A'), 8.0),
        (11, ('sub', 'C'), 8.0),
    ]
    pesos = {(10, ('sub', 'A')): 70}
    resultado = normalizar_horas_funcionario(entries, pesos=pesos)
    horas_10 = _horas_por_chave(resultado, 10)
    horas_11 = _horas_por_chave(resultado, 11)
    assert _aprox(horas_10[('sub', 'A')], 5.6)
    assert _aprox(horas_10[('sub', 'B')], 2.4)
    assert _aprox(horas_11[('sub', 'A')], 4.0)
    assert _aprox(horas_11[('sub', 'C')], 4.0)


def test_pesos_clamp_acima_de_100_e_abaixo_de_0():
    """Apontador digitando 150 ou -10 → clamp 100/0 dentro do helper."""
    entries = [
        (10, ('sub', 'A'), 8.0),
        (10, ('sub', 'B'), 8.0),
    ]
    resultado_alto = normalizar_horas_funcionario(
        entries, pesos={(10, ('sub', 'A')): 150}
    )
    horas_alto = _horas_por_chave(resultado_alto, 10)
    assert _aprox(horas_alto[('sub', 'A')], 8.0)
    assert _aprox(horas_alto[('sub', 'B')], 0.0)

    resultado_baixo = normalizar_horas_funcionario(
        entries, pesos={(10, ('sub', 'A')): -50}
    )
    horas_baixo = _horas_por_chave(resultado_baixo, 10)
    # peso clampa em 0 → principal A=0; restante 100% para a única
    # tarefa NULL (B), que portanto recebe a jornada-base inteira.
    assert _aprox(horas_baixo[('sub', 'A')], 0.0)
    assert _aprox(horas_baixo[('sub', 'B')], 8.0)


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q']))
