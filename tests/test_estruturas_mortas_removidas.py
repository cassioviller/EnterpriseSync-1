"""B4 — o que foi aposentado continua aposentado, e o que ficou continua vivo.

## Por que um arreio, e não greps

**Contra uma REMOÇÃO, um teste textual é pior que inútil.** Um
`assert "EventManager.emit('material_saida'" in texto` fica **VERMELHO ao apagar
o código morto** — reprova a limpeza correta, e o reflexo de quem vê vermelho é
desfazer a remoção.

E, no outro sentido, se a remoção quebrar de verdade, **nenhum grep vê**: o texto
que sobrou está sintaticamente perfeito. Os dois modos de falha reais deste bloco
só aparecem de um jeito:

* **o decorador solto.** `@event_handler` adota a função imediatamente ABAIXO
  dele (`event_manager.py:75-85` faz `register(...); return func`, por posição,
  sem checar duplicata). Cortar o corpo de `material_saida` e deixar o decorador
  vivo faz ele adotar `criar_conta_pagar_entrada_material` — que passa a estar
  registrado em **dois eventos**. O plano descreve o efeito como "a entrada roda
  duas vezes"; **medido, é outra coisa e é pior**: dar SAÍDA de material passaria
  a criar `GestaoCustoPai` como se fosse ENTRADA. Só inspecionando
  `EventManager._handlers` se enxerga; um teste que chame a função direto passa
  feliz;
* **a exclusão que estoura FK.** As quatro FKs de `notificacao_cliente` são
  `NO ACTION`, e as rotas de exclusão de RDO **capturam a exceção, fazem rollback
  e redirecionam** — então **302 sai igual no sucesso e no fracasso**. A prova é
  contar linhas no banco depois, nunca o status.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints E dispara os imports do boot
from app import app, db

from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

DIA = date(2026, 1, 1)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-mortas'
    yield


# ---------------------------------------------------------------------------
# Cenário 4 — o registro de eventos (B4.1 e B4.2)
# ---------------------------------------------------------------------------

def test_handlers_orfaos_saem_do_registro():
    """`nota_fiscal_paga` e `material_saida` deixam de ter handler.

    Os dois eram handlers sem emissor (o primeiro) ou com emissores inertes (o
    segundo). Esta asserção é barata e é a que monta o arquivo — o recorte manda
    escrevê-la primeiro por isso.
    """
    from event_manager import EventManager

    assert 'nota_fiscal_paga' not in EventManager._handlers, (
        'o handler órfão de nota_fiscal_paga ainda está registrado — o arquivo '
        'handlers/financeiro_handlers.py ou o import de app.py sobreviveu')
    assert 'material_saida' not in EventManager._handlers, (
        'material_saida ainda tem handler registrado')


def test_entrada_de_material_tem_um_unico_handler():
    """🔴 **A asserção que fecha a armadilha do decorador.**

    Deixar `@event_handler('material_saida')` vivo e sem função abaixo faz ele
    adotar a PRÓXIMA, que é `criar_conta_pagar_entrada_material`.

    🔬 **A primeira asserção deste teste não bastava, e a sabotagem provou.** Ela
    contava os handlers de `material_entrada` — mas o decorador solto registra a
    função sob `material_saida`, então `material_entrada` continua com um
    elemento e a contagem passa. O que se afirma agora é o invariante certo: essa
    função aparece em **exatamente um** evento.

    Nenhum teste que chame a função direto vê isso. Nenhum grep vê — o arquivo
    fica sintaticamente perfeito. Só a inspeção do registro vê.
    """
    from event_manager import EventManager

    nomes = [f.__name__ for f in EventManager._handlers.get('material_entrada', [])]
    assert nomes == ['criar_conta_pagar_entrada_material'], (
        f'material_entrada tem {len(nomes)} handler(s): {nomes}')

    # 🔬 A asserção acima NÃO basta, e a sabotagem provou. Com o decorador solto,
    # a função é registrada sob `material_saida` — `material_entrada` continua
    # com um elemento e a lista acima passa. O que o decorador solto realmente
    # faz é **pendurar o handler de ENTRADA num segundo evento**, e é isso que
    # se afirma aqui.
    #
    # Consequência prática, e ela é pior do que "roda duas vezes": enquanto os
    # emissores de saída existirem, dar SAÍDA de material passaria a criar
    # `GestaoCustoPai` como se fosse ENTRADA.
    eventos_do_handler = sorted(
        evento for evento, fns in EventManager._handlers.items()
        if any(f.__name__ == 'criar_conta_pagar_entrada_material' for f in fns))
    assert eventos_do_handler == ['material_entrada'], (
        f'criar_conta_pagar_entrada_material está registrado em '
        f'{eventos_do_handler} — em mais de um evento significa decorador solto '
        f'adotando a função de baixo')


def test_o_registro_nao_perdeu_os_handlers_vivos():
    """O par das duas asserções acima, e sem ele elas seriam meias-verdades.

    Um `_handlers` vazio satisfaria os dois `not in` de cima. Este teste afirma
    que o que deve continuar registrado continuou — a remoção é cirúrgica, não
    uma limpeza geral.
    """
    from event_manager import EventManager

    for evento in ('rdo_finalizado', 'material_entrada', 'proposta_aprovada'):
        assert EventManager._handlers.get(evento), (
            f'o evento {evento} ficou SEM handler — a remoção do B4 levou junto '
            f'o que devia ficar')
