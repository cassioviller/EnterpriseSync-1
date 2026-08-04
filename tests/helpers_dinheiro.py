"""Semeadores e coletores de estado de dinheiro — B0 do plano consolidado.

Existe por um motivo que vale escrever por extenso: **a suíte sabia exercitar
rota e sabia afirmar sobre banco, mas nunca ligou as duas coisas no caminho do
dinheiro.** Nenhum teste do repositório afirmava sobre ``GestaoCustoFilho`` ou
``CustoObra`` depois de um POST nas rotas de RDO ou de ponto. O resultado foi um
gate de 1778 asserções verdes sobre uma regressão que zerou o custo de
mensalista em duas das três rotas de RDO.

A regra deste módulo: **um coletor devolve estado do banco, nunca o resultado de
uma função de produção.** Se o teste chamar o mesmo serviço que a rota chama, ele
mede o serviço e não o caminho — que foi exatamente como
``tests/test_p1_dedup_cross_origem.py`` passou verde emitindo o evento à mão.

Três armadilhas que os coletores tratam, todas já pagas uma vez:

1. **Sessão velha.** Os handlers commitam por dentro; o objeto que o teste tem em
   mãos é o de antes. Todo coletor chama ``db.session.expire_all()`` antes de
   reler (padrão de ``tests/test_gestao_custo_filho_tenant.py:105``).
2. **Contagem global.** A base de desenvolvimento é compartilhada entre
   execuções. Coletor sem ``admin_id`` conta o mundo — todo coletor daqui filtra
   por tenant, sem exceção.
3. **A combinação que mede a guarda.** Este módulo **não** oferece semeador que
   crie ``RegistroPonto`` e RDO na mesma data por acidente. Quem quiser os dois
   chama duas funções explícitas — porque semear ponto no dia do RDO faz
   ``existe_ponto_no_dia`` (`event_manager.py:722-726`) pular o lançamento antes
   de o defeito ser alcançado, e o teste passa a medir a guarda, não o custo.
"""
import uuid
from datetime import date

from app import db
from models import (CustoObra, GestaoCustoFilho, GestaoCustoPai, RDO,
                    RDOCustoDiario, RDOMaoObra, TarefaCronograma)

# As duas categorias sob as quais mão de obra é lançada na Gestão de Custos V2.
# Vêm de `event_manager.py:837` e `:853` — o dedup do p1 cruza as duas, e um
# coletor que olhasse só 'SALARIO' perderia metade do que quer medir.
CATEGORIAS_MAO_DE_OBRA = ('SALARIO', 'MAO_OBRA_DIRETA')

# Benefícios lançados por dia trabalhado (`event_manager.py:934`).
CATEGORIAS_BENEFICIO = ('ALIMENTACAO', 'TRANSPORTE')


# ---------------------------------------------------------------------------
# Semeadores
# ---------------------------------------------------------------------------

def tarefa_da_obra(tenant, nome='Tarefa do arreio', duracao_dias=5):
    """Uma ``TarefaCronograma`` do cronograma INTERNO da obra do tenant.

    ``is_cliente=False`` é o default do modelo e é o que importa: o cronograma
    do cliente é outra população (`TarefaCronograma.do_cronograma_interno`), e
    apontar numa tarefa de cliente não é o caminho que as rotas de RDO usam.
    """
    tarefa = TarefaCronograma(
        obra_id=tenant.obra_id, admin_id=tenant.admin_id,
        nome_tarefa=nome, duracao_dias=duracao_dias, ordem=1)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def rdo_da_obra(tenant, data, estado='rascunho'):
    """Um RDO da obra do tenant, sem mão de obra ainda.

    ``numero_rdo`` é UNIQUE global (`models.py`), então carrega um sufixo
    aleatório: a base de dev é reaproveitada entre execuções e um número fixo
    quebraria a segunda rodada — não o código.
    """
    rdo = RDO(
        numero_rdo=f'ARR{uuid.uuid4().hex[:10].upper()}',
        data_relatorio=data, obra_id=tenant.obra_id,
        admin_id=tenant.admin_id, estado=estado)
    db.session.add(rdo)
    db.session.commit()
    return rdo


def mao_de_obra(rdo, tenant, horas=8.0, tarefa=None, funcao='Servente'):
    """Uma linha de ``RDOMaoObra`` no RDO.

    Precisa existir ANTES do POST em ``/rdo/finalizar/<id>``: a rota sai por
    `crud_rdo_completo.py:576-578` com flash+redirect quando o RDO não tem
    subatividade nem funcionário, e o teste viraria um 302 sem significado.
    """
    linha = RDOMaoObra(
        rdo_id=rdo.id, admin_id=tenant.admin_id,
        funcionario_id=tenant.funcionario_id,
        funcao_exercida=funcao, horas_trabalhadas=horas,
        tarefa_cronograma_id=tarefa.id if tarefa else None)
    db.session.add(linha)
    db.session.commit()
    return linha


def form_rdo(tenant, data, tarefa_id=None, horas=8.0, sub_mestre_id=None,
             flat_func=False):
    """O dict de formulário com as chaves REAIS que as rotas parseiam.

    ``cron_tarefa_<tarefa_id>_func_<func_id>_horas`` casa com o regex de
    `rdo_editar_sistema.py:401` (espelho em ``views/rdo.py``);
    ``sub_func_<sub_mestre_id>_<func_id>_horas`` casa com o de
    `rdo_editar_sistema.py:370`.

    Isto não é conveniência: ``POST /rdo/editar/<id>`` **apaga e reescreve** a
    mão de obra a partir do formulário (`rdo_editar_sistema.py:445-491`). Postar
    sem estas chaves zera a equipe, e o teste que olhasse dinheiro depois disso
    estaria medindo o próprio apagamento.

    ``flat_func=True`` acrescenta ``funcionario_<id>_nome`` e ``_horas``.

    🔬 **As rotas não parseiam todas o mesmo formulário, e isso já produziu um
    teste vacuoso.** ``POST /rdo/salvar`` (`views/rdo.py:3292-3316`) **ignora**
    as chaves ``cron_tarefa_*``/``sub_func_*``: ele lê ou os campos achatados
    ``funcionario_<id>_nome`` + ``_horas`` (Path A), ou o JSON ``mao_obra``
    (Path B). Postar nele sem ``flat_func=True`` cria um RDO **sem mão de obra
    nenhuma** — e aí `gerar_custos_mao_obra_rdo` sai em
    `services/rdo_custos.py:386-387` (``if not registros: return 0``) e todo
    assert de dinheiro depois disso mede o vazio em vez de medir a rota. Foi
    exatamente assim que `test_rdo_salvar_unificado_*` passou verde afirmando
    no nome que a rota "gera custo", sem nunca ter conferido.
    """
    dados = {
        'obra_id': str(tenant.obra_id),
        'admin_id_form': str(tenant.admin_id),
        'data_relatorio': data.isoformat(),
    }
    if tarefa_id:
        chave = f'cron_tarefa_{tarefa_id}_func_{tenant.funcionario_id}_horas'
        dados[chave] = str(horas)
    if sub_mestre_id:
        chave = f'sub_func_{sub_mestre_id}_{tenant.funcionario_id}_horas'
        dados[chave] = str(horas)
    if flat_func:
        dados[f'funcionario_{tenant.funcionario_id}_nome'] = (
            f'Funcionario {tenant.marca}')
        dados[f'funcionario_{tenant.funcionario_id}_horas'] = str(horas)
    return dados


# ---------------------------------------------------------------------------
# Coletores de ESTADO
# ---------------------------------------------------------------------------

def _expirar():
    """Descarta o cache de identidade da sessão do teste.

    Sem isto, um objeto lido antes do POST volta com os valores de antes,
    porque o handler commitou em outra sessão.
    """
    db.session.expire_all()


def filhos_por_categoria(tenant, categorias, data=None):
    """``GestaoCustoFilho`` do tenant nas categorias dadas.

    A categoria mora no PAI (`GestaoCustoPai.tipo_categoria`), então o filtro
    exige o join — filtrar só o filho devolveria material e combustível junto.
    """
    _expirar()
    q = (db.session.query(GestaoCustoFilho)
         .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
         .filter(GestaoCustoFilho.admin_id == tenant.admin_id,
                 GestaoCustoPai.tipo_categoria.in_(list(categorias))))
    if data is not None:
        q = q.filter(GestaoCustoFilho.data_referencia == data)
    return q.all()


def filhos_mao_de_obra(tenant, data=None):
    """Só mão de obra — o que A05 zerou."""
    return filhos_por_categoria(tenant, CATEGORIAS_MAO_DE_OBRA, data)


def filhos_beneficio(tenant, data=None):
    """VA e VT. Somem junto com a mão de obra no defeito de A05, porque o bloco
    de benefícios (`event_manager.py:889-957`) está DEPOIS do ``continue``."""
    return filhos_por_categoria(tenant, CATEGORIAS_BENEFICIO, data)


def custos_obra(tenant, data=None, categoria=None, qualquer_obra=False):
    """``CustoObra`` da obra do tenant.

    ``qualquer_obra=True`` amplia para TODAS as obras do tenant.

    🔬 Não é conveniência: a invariante da B1.6 — um custo de ponto por
    (funcionário, dia) — é **entre obras**, e um coletor preso a
    ``tenant.obra_id`` não consegue nem enxergar a violação. Um teste de troca
    de obra usando o escopo estreito acha zero linha e passa a acusar o oposto
    do que investiga.
    """
    _expirar()
    q = CustoObra.query.filter_by(admin_id=tenant.admin_id)
    if not qualquer_obra:
        q = q.filter(CustoObra.obra_id == tenant.obra_id)
    if data is not None:
        q = q.filter(CustoObra.data == data)
    if categoria is not None:
        q = q.filter(CustoObra.categoria == categoria)
    return q.all()


def custo_diario(rdo_id):
    """``RDOCustoDiario`` do RDO — a tabela que o caminho antigo escrevia.

    Vale por si: um ``RDOCustoDiario`` com ``componente_folha > 0`` e ZERO
    ``GestaoCustoFilho`` é a assinatura exata do defeito de
    `event_manager.py:729-733` — a linha de custo do dia existe e não virou
    lançamento.
    """
    _expirar()
    return RDOCustoDiario.query.filter_by(rdo_id=rdo_id).all()


def linhas_mao_de_obra(rdo_id):
    """``RDOMaoObra`` do RDO — para provar que o POST não apagou a equipe."""
    _expirar()
    return RDOMaoObra.query.filter_by(rdo_id=rdo_id).all()


def soma(linhas, campo='valor'):
    """Soma um campo Numeric/Float de uma lista de linhas, como float."""
    return float(sum(float(getattr(l, campo) or 0) for l in linhas))


# ---------------------------------------------------------------------------
# Asserção
# ---------------------------------------------------------------------------

def assert_custo_do_dia(tenant, data, valor_esperado, linhas_esperadas=1,
                        tolerancia=0.01):
    """Afirma contagem E soma dos filhos de mão de obra do dia.

    Os dois juntos, de propósito. A asserção do p1 era ``len(custos) <= 1``
    (`tests/test_p1_dedup_cross_origem.py:112`) — **verdadeira para zero**, que
    é o defeito. Contagem sozinha não distingue "perdeu o custo" de "contou
    certo"; soma sozinha não pega duplicata que se cancela.

    A mensagem de falha diz QUAL dos dois lados quebrou, porque "assert failed"
    sobre uma contagem manda quem lê abrir o banco à mão.
    """
    linhas = filhos_mao_de_obra(tenant, data)
    total = soma(linhas)

    if len(linhas) != linhas_esperadas:
        diagnostico = ('perdeu o custo' if len(linhas) < linhas_esperadas
                       else 'contou a mais')
        detalhe = ' | '.join(
            f'{l.origem_tabela}={float(l.valor):.2f}' for l in linhas) or '(nenhuma)'
        raise AssertionError(
            f'{diagnostico}: esperava {linhas_esperadas} linha(s) de mão de obra '
            f'em {data} para o tenant {tenant.marca}, encontrou {len(linhas)}. '
            f'Linhas: {detalhe}')

    if abs(total - valor_esperado) > tolerancia:
        raise AssertionError(
            f'valor divergente: esperava R$ {valor_esperado:.2f} em {data} '
            f'para o tenant {tenant.marca}, encontrou R$ {total:.2f} '
            f'({len(linhas)} linha(s)).')

    return linhas
