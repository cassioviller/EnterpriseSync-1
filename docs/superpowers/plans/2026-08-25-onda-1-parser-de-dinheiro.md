# Onda 1 — O Dinheiro Entra Certo: Um Parser Só Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — pronto para executar** — 6 tasks. 🔬 O código do próprio plano foi extraído e executado antes da entrega: **32 passed**. A Task 2 **destrava o push dos 25 commits**.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que todo valor em dinheiro digitado no sistema seja lido por **um único parser**, que recusa entrada ambígua em vez de adivinhar — fechando os cinco defeitos que hoje gravam contrato, pedido, teto de alçada e baixa de pagamento com fator de 100 ou 1000 de erro.

**Architecture:** Nasce `utils/decimal_br.py` com uma função, `parse_decimal_br`. Os cinco parsers artesanais de hoje passam a delegar para ela; nenhum some da assinatura pública, para não quebrar chamador. A regra nova é uma só: **`1.500` é ambíguo e é recusado** — pode ser mil e quinhentos (BR) ou um e meio (EN), e adivinhar errado custa 1000×. Tudo o mais que hoje funciona continua funcionando, com os mesmos resultados.

**Tech Stack:** Python 3, `decimal.Decimal`, Flask, pytest. Sem dependência nova.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 1) — a evidência por achado, com `arquivo:linha` e cenário de falha, está em `docs/auditoria/achados-code-review-2026-08-25.md` §1, §2 e §5.

## Global Constraints

- **`Decimal`, nunca `float`, para dinheiro.** Onde o chamador de hoje usa `float`, a conversão para `float` acontece **na borda dele**, depois do parse — não dentro do parser.
- **Entrada ambígua é recusada, nunca adivinhada.** A exceção carrega o nome do campo e diz ao operador **o que digitar** para desambiguar.
- **Nenhum parser existente é apagado.** `_parse_valor`, `_parse_br_decimal`, `_parse_br_number` e `_para_teto` continuam existindo e com a mesma assinatura; passam a ser cascas finas sobre `parse_decimal_br`. Apagá-los quebraria `tests/test_orcamento_formato_br.py:39`, que os importa por nome.
- **TDD sem exceção.** Escreva o teste, rode e **veja o RED**, e só então escreva o código. Cite o RED na mensagem de commit.
- **Nenhum teste hoje verde muda de resultado.** 🔬 Conferido em 25/08: `tests/test_orcamento_formato_br.py` exercita `'1.234,56'` e `'25'`, ambos inequívocos; `tests/test_faixa_alcada_tela.py` usa `Decimal('30000.00')` direto, sem passar por parser. **Nenhum teste do repositório fixa o comportamento de entrada só-com-ponto.** Se algum passar a falhar, **pare** e reporte — significa que esta premissa caiu.
- **Nada de migration.** Esta onda não toca schema.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua de 23/08: **2560 passed, 6 skipped, 201 deselected, 2 xfailed**.

---

## A regra de desambiguação, escrita uma vez

Esta tabela é o contrato de `parse_decimal_br`. Todo caso de teste sai dela.

| Entrada | Separadores | Leitura | Resultado |
|---|---|---|---|
| `1234.56` | um ponto, 2 casas | decimal | `1234.56` |
| `1234,56` | uma vírgula | decimal | `1234.56` |
| `1.234,56` | ponto e vírgula, vírgula por último | BR | `1234.56` |
| `1,234.56` | vírgula e ponto, ponto por último | EN | `1234.56` |
| `1.234.567` | dois ou mais pontos | milhar BR | `1234567` |
| `1,234,567` | duas ou mais vírgulas | milhar EN | `1234567` |
| `1.5` | um ponto, 1 casa | decimal | `1.5` |
| `1.50` | um ponto, 2 casas | decimal | `1.50` |
| `1.5000` | um ponto, 4 casas | decimal | `1.5` |
| **`1.500`** | **um ponto, exatamente 3 casas** | **AMBÍGUO** | **`ValorAmbiguo`** |
| `150000.00` | um ponto, 2 casas | decimal | `150000.00` |
| `1500` | nenhum | inteiro | `1500` |
| `R$ 1.234,56` | prefixo | BR | `1234.56` |
| `` (vazio) | — | usa `default`, ou levanta se não houver | — |
| `abc` | — | inválido | `ValorInvalido` |

**Por que exatamente 3 casas é a fronteira:** o milhar BR agrupa **sempre** em três (`1.500`, `150.000`). Um decimal de exatamente três casas existe, mas em dinheiro é raro; um milhar de três é a norma. Nas outras contagens não há conflito: `1.50` e `150000.00` só podem ser decimais, porque milhar não agrupa em 2. É por isso que 🔴 `views/aditivos_views.py:102` erra hoje — ele trata `150000.00` como milhar e produz `15000000`.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `utils/decimal_br.py` | **Criar** | A única leitura de dinheiro digitado. Duas exceções e uma função. ~70 linhas |
| `tests/test_decimal_br.py` | **Criar** | A tabela acima, caso a caso, sem banco nem app. Rápido |
| `tests/test_onda1_dinheiro_entra_certo.py` | **Criar** | Os cinco defeitos, cada um provado pela porta por onde o operador entra (rota HTTP ou serviço) |
| `views/aditivos_views.py` | Modificar `:102` | Task 2 — **destrava o push** |
| `compras_views.py` | Modificar `:2851-2854` | Task 3 |
| `services/faixa_alcada_admin.py` | Modificar `_para_teto` `:206` | Task 4 |
| `financeiro_views.py` | Modificar `_parse_valor` `:36`, `baixar` `:525`, `receber_conta` `:840` | Task 5 |
| `financeiro_service.py` | Modificar `:110`, `:127` | Task 5 — a view não pode ser a única guarda |
| `views/orcamentos_views.py` | Modificar `_parse_br_decimal` `:65` | Task 6 |

---

### Task 1: O parser único

**Files:**
- Create: `utils/decimal_br.py`
- Test: `tests/test_decimal_br.py`

**Interfaces:**
- Consumes: nada. É a base da onda.
- Produces:
  - `parse_decimal_br(raw, *, campo='valor', default=SEM_DEFAULT, minimo=None, maximo=None) -> Decimal | None`
  - `class ValorInvalido(ValueError)`
  - `class ValorAmbiguo(ValorInvalido)`
  - `SEM_DEFAULT` — sentinela; passar `default=None` devolve `None` para entrada vazia, enquanto **não** passar `default` levanta `ValorInvalido`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_decimal_br.py`:

```python
"""A tabela de desambiguação de `parse_decimal_br`, caso a caso.

Sem banco, sem app, sem fixture: é função pura. Se este arquivo ficar lento,
alguma coisa está errada.

O caso que dá nome à onda é `1.500`: hoje quatro parsers do repositório o leem
de quatro jeitos e três deles erram por 1000×. Aqui ele é RECUSADO.
"""
from decimal import Decimal

import pytest

from utils.decimal_br import (SEM_DEFAULT, ValorAmbiguo, ValorInvalido,
                              parse_decimal_br)


@pytest.mark.parametrize('entrada,esperado', [
    ('1234.56', '1234.56'),
    ('1234,56', '1234.56'),
    ('1.234,56', '1234.56'),
    ('1,234.56', '1234.56'),
    ('1.234.567', '1234567'),
    ('1,234,567', '1234567'),
    ('1.5', '1.5'),
    ('1.50', '1.50'),
    ('1.5000', '1.5000'),
    ('150000.00', '150000.00'),
    ('1500', '1500'),
    ('R$ 1.234,56', '1234.56'),
    ('  25  ', '25'),
    ('0', '0'),
    ('-100', '-100'),
    ('-1.234,56', '-1234.56'),
])
def test_le_o_que_nao_e_ambiguo(entrada, esperado):
    assert parse_decimal_br(entrada) == Decimal(esperado)


@pytest.mark.parametrize('entrada', ['1.500', '150.000', '-1.500', '0.000'])
def test_recusa_o_ponto_com_tres_casas(entrada):
    """`1.500` tanto pode ser mil e quinhentos quanto um e meio.

    Adivinhar custa 1000×; é o defeito de `compras_views.py:2853` e de
    `services/faixa_alcada_admin.py:206`.
    """
    with pytest.raises(ValorAmbiguo) as exc:
        parse_decimal_br(entrada, campo='preço')
    # a mensagem precisa ensinar o operador a desambiguar, não só reclamar
    texto = str(exc.value)
    assert 'preço' in texto
    assert ',' in texto


def test_o_ambiguo_e_uma_especie_de_invalido():
    """Quem só quer saber se deu erro captura `ValorInvalido` e pega os dois."""
    assert issubclass(ValorAmbiguo, ValorInvalido)


@pytest.mark.parametrize('entrada', ['abc', 'R$', '--3', '1.2.3,4,5', '.'])
def test_recusa_o_que_nao_e_numero(entrada):
    with pytest.raises(ValorInvalido):
        parse_decimal_br(entrada, campo='valor')


def test_vazio_sem_default_levanta():
    """Campo de dinheiro em branco é decisão do chamador, não do parser."""
    for vazio in (None, '', '   '):
        with pytest.raises(ValorInvalido) as exc:
            parse_decimal_br(vazio, campo='valor_pago')
        assert 'valor_pago' in str(exc.value)


def test_vazio_com_default_devolve_o_default():
    assert parse_decimal_br('', default=Decimal('0')) == Decimal('0')
    assert parse_decimal_br(None, default=None) is None


def test_passa_numero_adiante_sem_mexer():
    """Chamador que já tem Decimal não deveria ter que virar string."""
    assert parse_decimal_br(Decimal('7.25')) == Decimal('7.25')
    assert parse_decimal_br(1500) == Decimal('1500')
    assert parse_decimal_br(1.5) == Decimal('1.5')


def test_minimo_e_maximo():
    assert parse_decimal_br('10', minimo=Decimal('0')) == Decimal('10')
    with pytest.raises(ValorInvalido) as exc:
        parse_decimal_br('-100', campo='valor_pago', minimo=Decimal('0'))
    assert 'valor_pago' in str(exc.value)
    with pytest.raises(ValorInvalido):
        parse_decimal_br('999', campo='teto', maximo=Decimal('500'))


def test_o_default_tambem_respeita_a_faixa():
    """Default fora da faixa é bug de chamador e precisa aparecer."""
    with pytest.raises(ValorInvalido):
        parse_decimal_br('', default=Decimal('-1'), minimo=Decimal('0'))


def test_sentinela_e_distinguivel_de_none():
    assert SEM_DEFAULT is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_decimal_br.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.decimal_br'`

- [ ] **Step 3: Write minimal implementation**

Create `utils/decimal_br.py`:

```python
"""A única leitura de dinheiro digitado.

Antes deste módulo o repositório tinha CINCO parsers artesanais — em
`views/aditivos_views.py`, `compras_views.py`, `services/faixa_alcada_admin.py`,
`financeiro_views.py` e `views/orcamentos_views.py` — e os cinco discordavam
sobre `1.500`. Três erravam por 1000×; um, o do aditivo, lia `150000.00` como
quinze milhões e lançava a diferença no razão.

A regra aqui é uma só: **entrada ambígua é recusada**. O milhar brasileiro
agrupa sempre em três, então um único ponto com exatamente três casas depois
não tem leitura segura — e adivinhar custa mil vezes o valor.
"""
from decimal import Decimal, InvalidOperation

__all__ = ['SEM_DEFAULT', 'ValorAmbiguo', 'ValorInvalido', 'parse_decimal_br']


class ValorInvalido(ValueError):
    """O texto não é um número que se possa cobrar de alguém."""


class ValorAmbiguo(ValorInvalido):
    """`1.500` tanto pode ser mil e quinhentos quanto um e meio."""


SEM_DEFAULT = object()
# Escapes explícitas, nunca o caractere literal: um espaço invisível não
# sobrevive a copiar-e-colar, e a primeira versão deste módulo perdeu o
# U+202F exatamente assim — virou um segundo U+0020, silenciosamente.
# 'R$', espaço comum, espaço não-quebrável e o separador estreito que o
# `Intl.NumberFormat` do navegador produz em pt-BR.
_LIXO = ('R$', 'r$', ' ', '\xa0', '\u202f')


def _limpar(texto):
    for ruido in _LIXO:
        texto = texto.replace(ruido, '')
    return texto.strip()


def _normalizar_separadores(texto, campo):
    """Devolve o texto com '.' como separador decimal e nada de milhar."""
    tem_virgula = ',' in texto
    tem_ponto = '.' in texto

    if tem_virgula and tem_ponto:
        # o ÚLTIMO separador é o decimal: 1.234,56 é BR, 1,234.56 é EN
        if texto.rfind(',') > texto.rfind('.'):
            return texto.replace('.', '').replace(',', '.')
        return texto.replace(',', '')

    if tem_virgula:
        # mais de uma vírgula só pode ser milhar EN
        if texto.count(',') > 1:
            return texto.replace(',', '')
        return texto.replace(',', '.')

    if tem_ponto:
        # mais de um ponto só pode ser milhar BR
        if texto.count('.') > 1:
            return texto.replace('.', '')
        inteiro, _, fracao = texto.partition('.')
        if len(fracao) == 3 and inteiro.lstrip('+-').isdigit():
            raise ValorAmbiguo(
                f'{campo}: {texto!r} é ambíguo — o ponto com três casas tanto '
                f'pode ser milhar quanto decimal. Escreva '
                f'{texto.replace(".", "")},00 para o valor cheio, ou '
                f'{inteiro},{fracao} para a fração.')
        return texto

    return texto


def parse_decimal_br(raw, *, campo='valor', default=SEM_DEFAULT,
                     minimo=None, maximo=None):
    """Lê um valor em dinheiro digitado por gente, em pt-BR ou en-US.

    `campo` entra na mensagem de erro — é o que o operador vê na tela.
    `default` é usado para entrada vazia; sem ele, vazio LEVANTA.
    `minimo`/`maximo` são inclusivos e valem também para o `default`.
    """
    if isinstance(raw, Decimal):
        valor = raw
    elif isinstance(raw, bool):
        # bool é int em Python, e ninguém quis dizer "True reais"
        raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')
    elif isinstance(raw, (int, float)):
        valor = Decimal(str(raw))
    else:
        texto = _limpar(str(raw)) if raw is not None else ''
        if not texto:
            if default is SEM_DEFAULT:
                raise ValorInvalido(f'{campo}: não pode ficar em branco')
            if default is None:
                return None
            valor = (default if isinstance(default, Decimal)
                     else Decimal(str(default)))
            return _conferir_faixa(valor, campo, minimo, maximo)
        try:
            valor = Decimal(_normalizar_separadores(texto, campo))
        except ValorInvalido:
            raise
        except (InvalidOperation, ValueError, ArithmeticError):
            raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')
        if not valor.is_finite():
            raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')

    return _conferir_faixa(valor, campo, minimo, maximo)


def _conferir_faixa(valor, campo, minimo, maximo):
    if minimo is not None and valor < minimo:
        raise ValorInvalido(f'{campo}: precisa ser no mínimo {minimo}')
    if maximo is not None and valor > maximo:
        raise ValorInvalido(f'{campo}: acima do limite de {maximo}')
    return valor
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_decimal_br.py -v`
Expected: PASS — todos os casos da tabela.

- [ ] **Step 5: Commit**

```bash
git add utils/decimal_br.py tests/test_decimal_br.py
git commit -m "feat(dinheiro): um parser só, e ele recusa o que é ambíguo

RED: ModuleNotFoundError: No module named 'utils.decimal_br'

O milhar brasileiro agrupa sempre em três, então '1.500' com um ponto e três
casas não tem leitura segura. Os cinco parsers artesanais do repositório
adivinhavam, cada um de um jeito, e três erravam por 1000x."
```

---

### Task 2: O aditivo para de inflar o contrato em 100×

> 🔴 **Esta task destrava o push dos 25 commits.** Enquanto ela não fechar,
> `main` não deve subir: 📖 `views/aditivos_views.py:102` grava contrato inflado
> em `obra.valor_contrato` **e** lança a diferença no razão via
> `lancar_delta_contrato`.

**Files:**
- Modify: `views/aditivos_views.py:102` (dentro de `abrir`)
- Test: `tests/test_onda1_dinheiro_entra_certo.py` (criar)

**Interfaces:**
- Consumes: `parse_decimal_br`, `ValorInvalido` de `utils.decimal_br` (Task 1).
- Produces: nada para tasks seguintes. O contrato da rota não muda: `ValorInvalido` é subclasse de `ValueError`, e 📖 `views/aditivos_views.py:115` **já** captura `ValueError` e devolve 400 com a mensagem no flash. **Não acrescente `except` novo.**

- [ ] **Step 1: Write the failing test**

Create `tests/test_onda1_dinheiro_entra_certo.py`:

```python
"""Onda 1 — os cinco lugares em que o dinheiro entrava errado.

Cada teste entra pela porta do operador (rota HTTP ou serviço), não pelo
parser: o parser já tem `tests/test_decimal_br.py`. O que se prova aqui é que
a correção chegou ao caminho vivo.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda1-dinheiro'
    yield


@pytest.fixture(autouse=True, scope='module')
def _schema():
    """As 271-273 são idempotentes; rodá-las aqui é seguro.

    O boot da suíte roda com SIGE_BOOT_DDL=0 (conftest) — nem create_all nem
    migrações.
    """
    from migrations import (_migration_271_obra_contrato_versao,
                            _migration_272_aditivo_contrato,
                            _migration_273_medicao_contrato_versionada)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
        _migration_273_medicao_contrato_versionada()
    yield


def _novo_admin(prefixo='onda1'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {prefixo} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _nova_obra(admin, valor_contrato=0.0):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(admin_id=admin.id, nome=f'Cliente {suf}',
                      email=f'cli_{suf}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra {suf}', codigo=f'OBR{suf}',
                data_inicio=date(2026, 1, 10), admin_id=admin.id,
                cliente_id=cliente.id, valor_contrato=valor_contrato)
    db.session.add(obra)
    db.session.flush()
    return obra


# ---------------------------------------------------------------------------
# Task 2 — o aditivo
# ---------------------------------------------------------------------------

def test_aditivo_nao_le_150000_ponto_00_como_quinze_milhoes():
    """🔴 `views/aditivos_views.py:102` fazia `.replace('.', '')` sem condição.

    Um teclado numérico produz ponto. `150000.00` virava `15000000`, e a
    aprovação gravava R$ 15.000.000,00 em `obra.valor_contrato` e lançava
    ~R$ 14,85M de receita no razão.
    """
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_adit')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'acréscimo de escopo',
              'valor_novo': '150000.00'},
        follow_redirects=True)
    assert resposta.status_code in (200, 400)

    with app.app_context():
        from models import AditivoContrato
        aditivo = AditivoContrato.query.filter_by(obra_id=obra_id).first()
        assert aditivo is not None, 'o aditivo precisa ter sido aberto'
        assert Decimal(str(aditivo.valor_novo)) == Decimal('150000.00'), (
            f'150000.00 virou {aditivo.valor_novo} — o parser inflou o '
            f'contrato')


def test_aditivo_recusa_valor_ambiguo_em_vez_de_adivinhar():
    """`1.500` não é lido: é devolvido ao operador para desambiguar."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_ambig')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'teste', 'valor_novo': '1.500'})
    assert resposta.status_code == 400
    assert 'ambíguo' in resposta.get_data(as_text=True)

    with app.app_context():
        from models import AditivoContrato
        assert AditivoContrato.query.filter_by(obra_id=obra_id).count() == 0, (
            'entrada ambígua não pode abrir aditivo nenhum')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -v`
Expected: FAIL — o primeiro teste falha com `150000.00 virou 15000000.00`; o segundo falha porque a rota devolve 302/200 e abre o aditivo em vez de recusar.

- [ ] **Step 3: Write minimal implementation**

Em `views/aditivos_views.py`, no topo do arquivo, junto dos outros imports:

```python
from utils.decimal_br import parse_decimal_br
```

E em `abrir`, trocar o bloco de `:96-104`:

```python
        prazo = (request.form.get('prazo_delta_dias') or '').strip()
        valor = (request.form.get('valor_novo') or '').strip()
        aditivo = abrir_aditivo(
            obra,
            tipo=(request.form.get('tipo') or '').strip(),
            motivo=(request.form.get('motivo') or '').strip(),
            valor_novo=(valor.replace('.', '').replace(',', '.')
                        if valor else None),
            prazo_delta_dias=int(prazo) if prazo else None,
            criado_por_id=getattr(current_user, 'id', None),
        )
```

por:

```python
        prazo = (request.form.get('prazo_delta_dias') or '').strip()
        # `default=None`: aditivo de prazo puro não traz valor, e isso é
        # legítimo (D2 da Fase 6). O que não pode é ADIVINHAR um valor
        # ambíguo — `ValorAmbiguo` é `ValueError` e cai no `except` de baixo,
        # que devolve 400 com a mensagem na tela.
        valor_novo = parse_decimal_br(
            request.form.get('valor_novo'), campo='valor do aditivo',
            default=None, minimo=Decimal('0'))
        aditivo = abrir_aditivo(
            obra,
            tipo=(request.form.get('tipo') or '').strip(),
            motivo=(request.form.get('motivo') or '').strip(),
            valor_novo=valor_novo,
            prazo_delta_dias=int(prazo) if prazo else None,
            criado_por_id=getattr(current_user, 'id', None),
        )
```

Se `Decimal` ainda não estiver importado em `views/aditivos_views.py`, acrescente `from decimal import Decimal` ao topo.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -v`
Expected: PASS — 2 passed.

Depois, a suíte da Fase 6, que não pode ter mexido:
Run: `python -m pytest tests/test_fase6_aditivo.py -v`
Expected: PASS, com a mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add views/aditivos_views.py tests/test_onda1_dinheiro_entra_certo.py
git commit -m "fix(aditivo): o contrato para de ser inflado em 100x

RED: '150000.00 virou 15000000.00 — o parser inflou o contrato'

O campo é <input type=text inputmode=decimal>, e teclado numerico produz
ponto. O replace('.','') sem condicao lia 150000.00 como quinze milhoes,
gravava em obra.valor_contrato e lancava ~R\$ 14,85M no razao.

Este era o defeito que bloqueava o push dos 25 commits."
```

---

### Task 3: O pedido para de ser emitido a 1/1000 do preço

**Files:**
- Modify: `compras_views.py:2851-2854` (dentro do laço de itens da emissão)
- Test: `tests/test_onda1_dinheiro_entra_certo.py` (acrescentar)

**Interfaces:**
- Consumes: `parse_decimal_br`, `ValorInvalido` de `utils.decimal_br`.
- Produces: nada. `preco` continua sendo `float` na variável local — a conversão acontece na borda, depois do parse.

⚠️ **O que torna este achado caro:** 📖 o valor errado é **menor** que o estimado, então a guarda 3 (`valor_total > aprovado`, `compras_views.py:2868`) **deixa passar**. GCP, `ContaPagar` e a entrada do almoxarifado herdam o número errado sem nenhum alarme.

- [ ] **Step 1: Write the failing test**

Acrescentar ao fim de `tests/test_onda1_dinheiro_entra_certo.py`:

```python
# ---------------------------------------------------------------------------
# Task 3 — a emissão do pedido
# ---------------------------------------------------------------------------

def test_preco_real_ambiguo_nao_vira_um_milesimo():
    """🔴 `compras_views.py:2853`: `'1.500'` virava `1.5`.

    E como 1,5 é MENOR que o estimado, a guarda 3 (`valor_total > aprovado`)
    deixava passar em silêncio.

    Testado no nível do parser porque a emissão exige requisição aprovada,
    fornecedor e alçada — cenário que `tests/test_fase3_alcada.py` já monta.
    O que esta task muda é a leitura, e é ela que se prova aqui.
    """
    from utils.decimal_br import ValorAmbiguo, parse_decimal_br
    with pytest.raises(ValorAmbiguo):
        parse_decimal_br('1.500', campo='preço real')
    # e o que NÃO é ambíguo continua entrando
    assert parse_decimal_br('1500,00', campo='preço real') == Decimal('1500.00')
    assert parse_decimal_br('1500.00', campo='preço real') == Decimal('1500.00')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py::test_preco_real_ambiguo_nao_vira_um_milesimo -v`
Expected: PASS se a Task 1 já entrou — este teste sozinho não cobre a mudança em `compras_views.py`. **Por isso o RED de verdade desta task é o passo seguinte**, e é ele que a mensagem de commit cita.

- [ ] **Step 3: Provar o RED no caminho vivo**

Antes de tocar em `compras_views.py`, rode no shell:

```bash
python -c "
import compras_views, inspect
fonte = inspect.getsource(compras_views)
assert \"bruto.replace('.', '').replace(',', '.')\" in fonte, 'ja corrigido?'
print('RED confirmado: o parser artesanal ainda esta em compras_views.py')
"
```
Expected: `RED confirmado: o parser artesanal ainda esta em compras_views.py`

- [ ] **Step 4: Write minimal implementation**

Em `compras_views.py`, no topo, junto dos outros imports:

```python
from utils.decimal_br import ValorInvalido, parse_decimal_br
```

E trocar o bloco de `:2849-2857`:

```python
        bruto = (precos_reais[idx] if idx < len(precos_reais) else '') or ''
        bruto = str(bruto).strip()
        if bruto:
            try:
                preco = float(bruto.replace('.', '').replace(',', '.')
                              if ',' in bruto else bruto)
            except ValueError:
                preco = float(item.preco_estimado or 0)
        else:
            preco = float(item.preco_estimado or 0)
```

por:

```python
        bruto = (precos_reais[idx] if idx < len(precos_reais) else '') or ''
        # Campo vazio = vale o estimado da requisição (regra do comprador).
        # Campo AMBÍGUO não é vazio: recusar é a única saída, porque o valor
        # errado seria MENOR que o estimado e a guarda 3 o deixaria passar.
        try:
            preco_lido = parse_decimal_br(
                bruto, campo=f'preço real de {item.descricao!r}', default=None)
        except ValorInvalido as erro:
            flash(str(erro), 'danger')
            return redirect(url_for('compras.requisicao_detalhe',
                                    requisicao_id=requisicao_id))
        preco = float(preco_lido if preco_lido is not None
                      else (item.preco_estimado or 0))
```

🔬 O caminho de retorno **não é inventado**: é o mesmo que a guarda 3 já usa
vinte linhas abaixo (📖 `compras_views.py:2874` — `flash(..., 'danger')` +
`redirect(url_for('compras.requisicao_detalhe', requisicao_id=requisicao_id))`).
Recusa de preço e estouro de alçada saem pela mesma porta, com o mesmo nível de
flash.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -v`
Expected: PASS

Run: `python -m pytest tests/test_fase3_alcada.py tests/test_alcadas_avancadas.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 6: Commit**

```bash
git add compras_views.py tests/test_onda1_dinheiro_entra_certo.py
git commit -m "fix(compras): o pedido para de ser emitido a 1/1000 do preco

RED: o parser artesanal ainda estava em compras_views.py (inspect.getsource)

'1.500' virava 1.5 na emissao. E como o valor errado e MENOR que o estimado,
a guarda 3 (valor_total > aprovado) deixava passar em silencio: GCP,
ContaPagar e a entrada do almoxarifado herdavam o numero errado.

Achado n 6 da revisao da Fase 3, ainda vivo no caminho de emissao."
```

---

### Task 4: O teto da alçada para de virar R$ 30

**Files:**
- Modify: `services/faixa_alcada_admin.py:203-211` (corpo de `_para_teto`)
- Test: `tests/test_onda1_dinheiro_entra_certo.py` (acrescentar)

**Interfaces:**
- Consumes: `parse_decimal_br`, `ValorInvalido` de `utils.decimal_br`.
- Produces: `_para_teto(bruto, erros)` mantém **exatamente** a assinatura e o contrato de hoje — devolve `Decimal` quantizado em 2 casas, ou `None`, e acumula mensagens em `erros`. **Não levanta.** É assim que `_violacoes` a consome.

⚠️ 📖 O docstring de hoje diz aceitar `30.000` de propósito, porque "quem copia da tela cola de volta com ponto de milhar". A intenção é boa e o resultado é R$ 30,00 — a escada continua monotônica, `_violacoes` não levanta nada, e a primeira faixa do tenant passa a cobrir só compras abaixo de R$ 30. **A correção é recusar com mensagem, não continuar adivinhando.** O docstring muda junto.

- [ ] **Step 1: Write the failing test**

Acrescentar ao fim de `tests/test_onda1_dinheiro_entra_certo.py`:

```python
# ---------------------------------------------------------------------------
# Task 4 — o teto da faixa de alçada
# ---------------------------------------------------------------------------

def test_teto_com_ponto_de_milhar_nao_vira_trinta_reais():
    """🔴 `services/faixa_alcada_admin.py:206`: `'30.000'` virava R$ 30,00.

    A escada seguia monotônica, `_violacoes` não levantava nada, e a primeira
    faixa do tenant passava a cobrir só compras abaixo de R$ 30.
    """
    from services.faixa_alcada_admin import _para_teto

    erros = []
    assert _para_teto('30.000', erros) is None
    assert erros, 'ambíguo precisa virar erro visível, não R$ 30,00'
    assert any('ambíguo' in e for e in erros), erros


def test_teto_continua_aceitando_os_dois_formatos_inequivocos():
    """O que a tela produz de fato continua entrando."""
    from services.faixa_alcada_admin import _para_teto

    for entrada in ('30000.00', '30.000,00', '30000'):
        erros = []
        assert _para_teto(entrada, erros) == Decimal('30000.00'), entrada
        assert erros == [], (entrada, erros)


def test_teto_vazio_continua_sendo_teto_aberto():
    """`valor_ate` NULL é o teto aberto — invariante da faixa. Não regrediu."""
    from services.faixa_alcada_admin import _para_teto

    for vazio in ('', '   ', None):
        erros = []
        assert _para_teto(vazio, erros) is None
        assert erros == []


def test_teto_zero_e_negativo_continuam_recusados():
    from services.faixa_alcada_admin import _para_teto

    for ruim in ('0', '-5'):
        erros = []
        assert _para_teto(ruim, erros) is None
        assert erros, ruim
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -k teto -v`
Expected: FAIL em `test_teto_com_ponto_de_milhar_nao_vira_trinta_reais` — `_para_teto('30.000', erros)` devolve `Decimal('30.00')` e `erros` fica vazio.

- [ ] **Step 3: Write minimal implementation**

Em `services/faixa_alcada_admin.py`, no topo:

```python
from utils.decimal_br import ValorInvalido, parse_decimal_br
```

E trocar o corpo de `_para_teto` por:

```python
def _para_teto(bruto, erros):
    """O teto da faixa. Vazio é o TETO ABERTO (NULL), não zero.

    Aceita `30000.00` e `30.000,00`. **Recusa `30.000`**: o ponto com três
    casas tanto pode ser milhar quanto decimal, e adivinhar transformava o
    teto de trinta mil em trinta reais — em silêncio, porque a escada
    continuava monotônica e `_violacoes` não tinha o que reclamar.

    Não levanta: acumula em `erros`, que é o contrato que `_violacoes` espera.
    """
    try:
        # 🔬 LIMITE_TETO = Decimal('999999999.99') (`:50`) — já é Decimal,
        # então entra direto como `maximo` e a mensagem sai idêntica à de antes.
        valor = parse_decimal_br(bruto, campo='teto', default=None,
                                 maximo=LIMITE_TETO)
    except ValorInvalido as erro:
        erros.append(str(erro))
        return None
    if valor is None:
        return None
    if valor <= 0:
        erros.append('teto: precisa ser maior que zero (deixe em branco para '
                     'a faixa de teto aberto)')
        return None
    return valor.quantize(Decimal('0.01'))
```

⚠️ `InvalidOperation` pode ficar sem uso no `import` do módulo depois desta
troca. Confira e remova só se nenhum outro ponto do arquivo o usar:

```bash
grep -n "InvalidOperation" services/faixa_alcada_admin.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -k teto -v`
Expected: PASS — 4 passed.

Run: `python -m pytest tests/test_faixa_alcada_tela.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add services/faixa_alcada_admin.py tests/test_onda1_dinheiro_entra_certo.py
git commit -m "fix(alcada): o teto de 30.000 para de virar R\$ 30,00

RED: _para_teto('30.000', erros) devolvia Decimal('30.00') com erros == []

O docstring aceitava o ponto de milhar de proposito, para nao culpar o
operador pelo formato que a propria tela lhe deu. A intencao estava certa e o
resultado era R\$ 30,00: a escada seguia monotonica, _violacoes nao levantava
nada, e a primeira faixa do tenant passava a cobrir so compras abaixo de 30
reais. Agora recusa com mensagem, em vez de adivinhar."
```

---

### Task 5: A baixa de pagamento para de aceitar valor negativo

**Files:**
- Modify: `financeiro_views.py:36` (`_parse_valor`), `:525` (`baixar`), `:840` (`receber_conta`)
- Modify: `financeiro_service.py:110`, `:127` (`baixar_pagamento`)
- Test: `tests/test_onda1_dinheiro_entra_certo.py` (acrescentar)

**Interfaces:**
- Consumes: `parse_decimal_br`, `ValorInvalido` de `utils.decimal_br`.
- Produces: `_parse_valor(raw) -> float` mantém assinatura e tipo de retorno. Passa a **levantar `ValorInvalido`** para entrada ambígua ou inválida, onde antes devolvia lixo silencioso.

⚠️ 📖 `_parse_valor` de hoje é **o mais correto dos cinco** — trata os dois separadores por `rfind`. Seu único buraco é a entrada só-com-ponto (`1.500` → `1.5`). A parte cara desta task não é o parser: é que 📖 **não existe validação de sinal em lugar nenhum**. Hoje `-100` **credita** o banco (`saldo_atual -= -100`), deixa `saldo = 1100`, mantém a conta PENDENTE e mostra sucesso.

**A validação vai no serviço, não só na view.** A view não pode ser a única guarda — 📖 `financeiro_service.baixar_pagamento` (`:110`, `:127`) tem outros chamadores.

- [ ] **Step 1: Write the failing test**

Acrescentar ao fim de `tests/test_onda1_dinheiro_entra_certo.py`:

```python
# ---------------------------------------------------------------------------
# Task 5 — a baixa de pagamento
# ---------------------------------------------------------------------------

def test_parse_valor_do_financeiro_recusa_ambiguo():
    """`_parse_valor` era o melhor dos cinco e ainda lia `1.500` como 1,5."""
    from financeiro_views import _parse_valor
    from utils.decimal_br import ValorAmbiguo

    assert _parse_valor('1.234,56') == 1234.56
    assert _parse_valor('1,234.56') == 1234.56
    assert _parse_valor('1234.56') == 1234.56
    with pytest.raises(ValorAmbiguo):
        _parse_valor('1.500')


def test_baixar_pagamento_recusa_valor_negativo():
    """🔴 `-100` CREDITAVA o banco: `saldo_atual -= -100`.

    A conta ficava PENDENTE com saldo maior que o original, e a tela mostrava
    sucesso.
    """
    from utils.decimal_br import ValorInvalido, parse_decimal_br

    with pytest.raises(ValorInvalido):
        parse_decimal_br('-100', campo='valor_pago', minimo=Decimal('0.01'))
    assert parse_decimal_br('100', campo='valor_pago',
                            minimo=Decimal('0.01')) == Decimal('100')


def test_servico_de_baixa_rejeita_negativo_mesmo_sem_passar_pela_view():
    """A view não pode ser a única guarda: o serviço tem outros chamadores."""
    import inspect

    import financeiro_service
    fonte = inspect.getsource(financeiro_service.FinanceiroService
                              .baixar_pagamento)
    assert ('minimo' in fonte or 'valor_pago <= 0' in fonte
            or '<= 0' in fonte), (
        'baixar_pagamento precisa recusar valor não-positivo no próprio '
        'serviço, não só na view')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -k "parse_valor or negativo or servico_de_baixa" -v`
Expected: FAIL — `_parse_valor('1.500')` devolve `1.5` em vez de levantar, e `baixar_pagamento` não tem guarda de sinal.

- [ ] **Step 3: Write minimal implementation**

**3a.** Em `financeiro_views.py`, no topo:

```python
from utils.decimal_br import ValorInvalido, parse_decimal_br
```

E trocar o corpo de `_parse_valor` (mantendo o docstring que já existe acima
dele) por:

```python
    return float(parse_decimal_br(raw, campo='valor', default=Decimal('0')))
```

**3b.** 🔬 Os dois campos têm nomes diferentes — conferido em 25/08.

Em `financeiro_views.py:525`, dentro de `baixar`, trocar:

```python
            valor_pago = Decimal(request.form.get('valor_pago'))
```

por:

```python
            valor_pago = parse_decimal_br(
                request.form.get('valor_pago'), campo='valor pago',
                minimo=Decimal('0.01'))
```

Em `financeiro_views.py:840`, dentro de `receber_conta`, trocar:

```python
            valor_recebido = Decimal(request.form.get('valor_recebido'))
```

por:

```python
            valor_recebido = parse_decimal_br(
                request.form.get('valor_recebido'), campo='valor recebido',
                minimo=Decimal('0.01'))
```

📖 As duas linhas **já estão dentro de um `try`** cujo `except` genérico mostra
"Erro ao registrar…" ao operador. `ValorInvalido` é `ValueError`: se a rota já
tiver um `except ValueError` específico — 📖 `receber_conta` tem, e o comentário
de `:849-852` explica por quê — a mensagem do parser chega à tela sozinha.
**Não crie caminho de erro novo em nenhuma das duas.**

**3c.** Em `financeiro_service.py`, no início de `baixar_pagamento`, antes de
qualquer escrita:

```python
        # A view não é a única porta: este serviço tem outros chamadores.
        # `-100` creditava o banco (`saldo_atual -= -100`), deixava a conta
        # PENDENTE com saldo MAIOR que o original, e a tela dizia sucesso.
        valor_pago = parse_decimal_br(valor_pago, campo='valor pago',
                                      minimo=Decimal('0.01'))
```

com `from utils.decimal_br import parse_decimal_br` no topo do arquivo.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -v`
Expected: PASS

Run: `python -m pytest tests/test_b5_baixa_conta_pagar.py tests/test_b5_estorno_devolve_banco.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add financeiro_views.py financeiro_service.py tests/test_onda1_dinheiro_entra_certo.py
git commit -m "fix(financeiro): baixa de pagamento recusa negativo e ambiguo

RED: _parse_valor('1.500') devolvia 1.5; baixar_pagamento sem guarda de sinal

_parse_valor era o mais correto dos cinco parsers e ainda lia '1.500' como
um e meio. E nao havia validacao de sinal em lugar nenhum: -100 CREDITAVA o
banco (saldo_atual -= -100), deixava a conta PENDENTE com saldo maior que o
original, e a tela mostrava sucesso.

A guarda entra no SERVICO, nao so na view: baixar_pagamento tem outros
chamadores."
```

---

### Task 6: O último parser artesanal delega, e a onda fecha

**Files:**
- Modify: `views/orcamentos_views.py:65-79` (`_parse_br_decimal`)
- Test: `tests/test_orcamento_formato_br.py` (já existe — **não** modificar; serve de rede)

**Interfaces:**
- Consumes: `parse_decimal_br` de `utils.decimal_br`.
- Produces: `_parse_br_decimal(raw, default='0') -> Decimal` mantém assinatura. 🔬 `tests/test_orcamento_formato_br.py:39` o importa por nome — **não renomeie e não apague**.

⚠️ Diferença de contrato: hoje `_parse_br_decimal` **engole** erro e devolve o
default (`except Exception: return Decimal(str(default))`). Passa a **levantar**
para entrada ambígua. 🔬 Conferido em 25/08: os casos que
`tests/test_orcamento_formato_br.py` exercita (`'1.234,56'` e `'25'`) são
inequívocos e continuam passando.

- [ ] **Step 1: Run the existing test to record the baseline**

Run: `python -m pytest tests/test_orcamento_formato_br.py -v`
Expected: PASS. **Anote a contagem** — é a régua do passo 4.

- [ ] **Step 2: Write the failing test**

Acrescentar ao fim de `tests/test_onda1_dinheiro_entra_certo.py`:

```python
# ---------------------------------------------------------------------------
# Task 6 — o último parser artesanal
# ---------------------------------------------------------------------------

def test_parse_br_decimal_do_orcamento_recusa_ambiguo():
    """Continua aceitando o que aceitava; para de engolir o ambíguo."""
    from utils.decimal_br import ValorAmbiguo
    from views.orcamentos_views import _parse_br_decimal

    assert _parse_br_decimal('1.234,56') == Decimal('1234.56')
    assert _parse_br_decimal('25') == Decimal('25')
    assert _parse_br_decimal('') == Decimal('0')
    assert _parse_br_decimal(None) == Decimal('0')
    assert _parse_br_decimal(Decimal('7.25')) == Decimal('7.25')
    with pytest.raises(ValorAmbiguo):
        _parse_br_decimal('1.500')


def test_nenhum_parser_artesanal_de_dinheiro_sobrou():
    """A onda fecha quando o `replace` à mão sai dos cinco arquivos.

    Se este teste falhar, um parser novo nasceu — leia a Onda 1 antes de
    escrever o sexto.
    """
    import inspect

    import compras_views
    import financeiro_views
    import services.faixa_alcada_admin as faixa
    import views.aditivos_views as aditivos
    import views.orcamentos_views as orcamentos

    padrao = "replace('.', '').replace(',', '.')"
    for modulo in (aditivos, compras_views, faixa, financeiro_views,
                   orcamentos):
        fonte = inspect.getsource(modulo)
        assert padrao not in fonte, (
            f'{modulo.__name__} ainda tem parser artesanal de dinheiro')
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -k "orcamento or artesanal" -v`
Expected: FAIL — `_parse_br_decimal('1.500')` devolve `Decimal('1.500')` em vez de levantar, e `views.orcamentos_views` ainda casa o padrão.

- [ ] **Step 4: Write minimal implementation**

Em `views/orcamentos_views.py`, no topo:

```python
from utils.decimal_br import parse_decimal_br
```

E trocar o corpo de `_parse_br_decimal` por:

```python
def _parse_br_decimal(raw, default='0') -> Decimal:
    """Task #165: versão Decimal de _parse_br_number, para colunas Numeric.

    Onda 1 (25/08): delega para `utils.decimal_br.parse_decimal_br`. Aceita o
    mesmo que aceitava; **levanta** para entrada ambígua, onde antes devolvia
    o default em silêncio.
    """
    return parse_decimal_br(raw, campo='valor', default=Decimal(str(default)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda1_dinheiro_entra_certo.py -v`
Expected: PASS

Run: `python -m pytest tests/test_orcamento_formato_br.py -v`
Expected: PASS, **com a mesma contagem anotada no passo 1**.

- [ ] **Step 6: Run the full gate**

Run: `bash run_tests.sh --gate`
Expected: **2560 passed, 6 skipped, 201 deselected, 2 xfailed** — ou mais verdes, nunca menos.

⚠️ Se o número de passed **subir**, diga em quanto e por quê (os testes novos
desta onda entram no gate). Se algum teste antes verde falhar, **pare e
reporte**: significa que a premissa "nenhum teste fixa o comportamento
só-com-ponto" caiu, e a decisão volta a ser humana.

- [ ] **Step 7: Commit**

```bash
git add views/orcamentos_views.py tests/test_onda1_dinheiro_entra_certo.py
git commit -m "fix(orcamento): o ultimo parser artesanal delega, e a onda fecha

RED: _parse_br_decimal('1.500') devolvia Decimal('1.500') em vez de levantar

Cinco parsers artesanais viraram um. O teste
test_nenhum_parser_artesanal_de_dinheiro_sobrou guarda a porta: se o sexto
nascer, ele falha.

Gate verde apos a onda."
```

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` — marcar como corrigidos
      os cinco achados desta onda: `views/aditivos_views.py:102`,
      `compras_views.py:2853`, `services/faixa_alcada_admin.py:206`,
      `financeiro_views.py:36` e `financeiro_views.py:525`.
- [ ] **Empurrar os 25 commits.** A Task 2 era o bloqueio (D1); com ela fechada,
      `git push` deixa de publicar um defeito de dinheiro.
