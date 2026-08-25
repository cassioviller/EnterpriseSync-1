"""Edição das faixas de alçada de um tenant — a A7 da fase 3 de compras.

📖 spec `docs/superpowers/specs/2026-08-15-alcadas-design.md`, decisões D6 e D7.

`FaixaAlcada` nunca teve CRUD: até aqui as faixas só existiam pela migration
243 e por UPDATE manual. O passo 1 do runbook manda conferir os tetos, o
`minimo_cotacoes` e as condições ativas ANTES de ligar a flag — e é por este
caminho que sai o UPDATE da D6 (a faixa de topo indo para
`minimo_cotacoes = 3`, que o backfill deliberadamente não fez).

**Por que as regras moram aqui e não no template.** A tela é a primeira
consumidora, não a única: o script de flag é a segunda e um SQL manual
continua sendo possível. Regra em `<input required>` protege exatamente um
caminho — o do navegador com JavaScript ligado.

Três invariantes, e nenhum deles tinha verificação em lugar nenhum até agora:

1. **Exatamente uma faixa ativa com `valor_ate IS NULL`** por tenant — o teto
   aberto. Era só docstring em `models.FaixaAlcada`; nunca houve constraint
   nem checagem. Sem ele, `faixa_para_valor` cai na falha fechada do fim da
   função e o tenant descobre na primeira compra grande.
2. **Tetos crescentes por `ordem`.** O degrau da A4 anda POSIÇÕES nessa lista
   ordenada; escada que desce faz o degrau punir menos do que a faixa base.
3. **`minimo_cotacoes` é 0 ou >= 2, nunca 1.** Uma cotação não é
   concorrência, é orçamento — e 1 é justamente o que alguém digita achando
   que está exigindo "pelo menos uma".

**A regra de convivência com o passado, que é a parte delicada.** Como o
invariante 1 nunca foi verificado, existe tenant que já está fora dele hoje
(faixa editada por SQL, faixa inativada à mão). Se a validação olhasse apenas
o estado final, esse tenant ficaria travado justamente na tela que existe para
consertá-lo — e o operador não teria caminho nenhum. Então a comparação é
ANTES × DEPOIS, por código de violação: **recusa-se o que a edição cria, nunca
o que ela herdou**. Violação que já existia e continua existindo vira AVISO,
visível na tela; violação nova é recusa. Consertar sempre passa, porque
consertar remove código sem acrescentar nenhum.
"""
import logging
from collections import namedtuple
from decimal import Decimal

from models import FaixaAlcada, db
from services.alcada_compras import CONDICOES_CONHECIDAS
from utils.decimal_br import ValorInvalido, parse_decimal_br

logger = logging.getLogger('faixa_alcada_admin')

# Teto máximo aceito num campo de valor. Não é regra de negócio — é a defesa
# contra o dedo escorregado que digita um teto de treze dígitos e desliga a
# escada inteira sem que nada reclame.
LIMITE_TETO = Decimal('999999999.99')

# Sanidade do número de aprovações. 1 é o mínimo (alçada sem aprovador não é
# alçada) e 10 é folga larga sobre a maior escada plausível.
MIN_APROVACOES = 1
MAX_APROVACOES = 10

# O tamanho de `faixa_alcada.condicoes_ativas` (String(120)). As quatro
# conhecidas somam 63 caracteres com as vírgulas, mas a lista vai crescer
# (frete e validade da proposta já esperam no backlog da seção 2) e o corte
# silencioso do banco seria uma condição desligada que ninguém pediu.
LIMITE_CONDICOES = 120


class FaixaInvalida(ValueError):
    """Erros de validação, com a lista completa — não só o primeiro.

    Molde de `services.timbre_pdf.TimbreInvalido`: quem está arrumando a
    escada de alçada quer ver tudo o que está errado de uma vez, e não
    descobrir um problema por tentativa de salvar.
    """

    def __init__(self, erros):
        self.erros = list(erros)
        super().__init__('; '.join(self.erros))


# A projeção de uma faixa para efeito de invariante. Tupla e não o objeto do
# ORM de propósito: validar exige simular o estado DEPOIS da edição, e simular
# mexendo no objeto mapeado sujaria a sessão com uma alteração que a validação
# ainda pode recusar.
_Linha = namedtuple('_Linha', 'id ordem valor_ate ativo')


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def listar_faixas(admin_id, incluir_inativas=True):
    """As faixas do tenant, na ordem da escada.

    Inativas entram por padrão: elas não valem para `faixa_para_valor`, mas
    quem abre a tela precisa vê-las — faixa inativada por engano é uma das
    formas de o tenant ficar sem teto aberto.
    """
    q = FaixaAlcada.query.filter_by(admin_id=admin_id)
    if not incluir_inativas:
        q = q.filter_by(ativo=True)
    return q.order_by(FaixaAlcada.ordem.asc()).all()


def faixa_do_tenant(admin_id, faixa_id):
    """A faixa, se ela for DESTE tenant. `None` caso contrário.

    Nunca busca por `id` sozinho. Quem chama pela rota transforma o `None` em
    404 — e não em 403, que já seria vazamento: confirmaria ao vizinho que
    aquele id existe e é de alguém.
    """
    return FaixaAlcada.query.filter_by(id=faixa_id, admin_id=admin_id).first()


# ---------------------------------------------------------------------------
# Os invariantes
# ---------------------------------------------------------------------------

def _violacoes(linhas):
    """Os invariantes quebrados neste conjunto de faixas, como {código: texto}.

    Avalia só as ATIVAS: faixa inativa não é consultada por
    `faixa_para_valor`, e exigir que ela componha a escada impediria de
    guardar uma faixa desligada para uso futuro.

    O código é estável entre duas chamadas com o mesmo defeito — é o que
    permite comparar antes × depois e distinguir violação criada de violação
    herdada.
    """
    ativas = sorted([l for l in linhas if l.ativo], key=lambda l: l.ordem)
    achados = {}

    abertas = [l for l in ativas if l.valor_ate is None]
    if not abertas:
        achados['teto_aberto_ausente'] = (
            'nenhuma faixa ativa com teto aberto (valor em branco): compra '
            'acima do maior teto ficaria sem faixa que a cubra')
    elif len(abertas) > 1:
        achados['teto_aberto_duplicado'] = (
            f'{len(abertas)} faixas ativas com teto aberto (ordens '
            f'{", ".join(str(l.ordem) for l in abertas)}); tem que ser '
            f'exatamente uma')
    elif ativas and abertas[0].ordem != ativas[-1].ordem:
        achados['teto_aberto_fora_do_fim'] = (
            f'a faixa de teto aberto é a de ordem {abertas[0].ordem}, mas a '
            f'última da escada é a de ordem {ativas[-1].ordem}; o teto aberto '
            f'é sempre a última')

    # Teto de faixa aberta (NULL) não entra na comparação de nenhum dos dois
    # lados: uma faixa DEPOIS do teto aberto é o defeito já relatado como
    # 'teto_aberto_fora_do_fim', e repetir aqui só multiplicaria a mensagem
    # sobre o mesmo fato.
    anterior = None
    for linha in ativas:
        if (anterior is not None
                and anterior.valor_ate is not None
                and linha.valor_ate is not None
                and linha.valor_ate <= anterior.valor_ate):
            achados[f'teto_nao_cresce:{linha.ordem}'] = (
                f'o teto da faixa de ordem {linha.ordem} não é maior que o da '
                f'faixa de ordem {anterior.ordem}; os tetos têm que crescer '
                f'com a ordem')
        anterior = linha
    return achados


def diagnosticar(admin_id):
    """Os invariantes quebrados HOJE neste tenant, em português.

    Devolve lista de textos — vazia quando está tudo certo. A tela mostra o
    resultado no topo, e o sensor da A8 tem aqui o mesmo julgamento que a tela
    faz, sem reimplementá-lo.
    """
    linhas = [_Linha(f.id, f.ordem, f.valor_ate, bool(f.ativo))
              for f in listar_faixas(admin_id)]
    return list(_violacoes(linhas).values())


# ---------------------------------------------------------------------------
# Validação dos campos
# ---------------------------------------------------------------------------

def _para_inteiro(bruto, campo, erros, minimo=0):
    texto = str(bruto if bruto is not None else '').strip()
    if not texto:
        erros.append(f'{campo}: preencha um número inteiro')
        return None
    try:
        valor = int(texto)
    except (TypeError, ValueError):
        erros.append(f'{campo}: {texto!r} não é um número inteiro')
        return None
    if valor < minimo:
        erros.append(f'{campo}: não pode ser menor que {minimo}')
        return None
    return valor


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


def _para_condicoes(bruto, erros):
    """Os códigos marcados, na ORDEM CANÔNICA de `CONDICOES_CONHECIDAS`.

    Ordem canônica e não a de chegada do formulário: dois tenants com as
    mesmas condições ativas guardam o mesmo texto, e comparar duas faixas
    passa a ser comparar duas strings.

    Código desconhecido é RECUSA aqui, e não o aviso-e-ignora de
    `condicoes_ativas_da_faixa`. Os dois estão certos: na leitura, um typo
    herdado não pode travar uma aprovação em curso; na escrita, aceitá-lo
    seria gravar de propósito o que o motor nunca vai executar.
    """
    if bruto is None:
        marcados = []
    elif isinstance(bruto, (list, tuple, set)):
        marcados = list(bruto)
    else:
        marcados = [p for p in str(bruto).split(',')]

    limpos = set()
    for item in marcados:
        codigo = str(item or '').strip().lower()
        if not codigo:
            continue
        if codigo not in CONDICOES_CONHECIDAS:
            erros.append(f'condição desconhecida: {codigo!r}')
            continue
        limpos.add(codigo)

    texto = ','.join(c for c in CONDICOES_CONHECIDAS if c in limpos)
    if len(texto) > LIMITE_CONDICOES:
        erros.append(f'condições: passam de {LIMITE_CONDICOES} caracteres')
    return texto


def _booleano(bruto):
    """Checkbox de formulário: ausente é False, presente é True.

    Aceita também o booleano puro, porque o script e o teste chamam o serviço
    sem passar por um `request.form`.
    """
    if isinstance(bruto, bool):
        return bruto
    return str(bruto or '').strip().lower() in ('on', 'true', '1', 'sim')


def ler_formulario(form):
    """Extrai os campos da faixa de um `request.form`, ainda CRUS.

    Existe para que a rota não conheça os nomes dos campos duas vezes (no
    template e nela) e para que o `getlist` dos checkboxes fique num lugar só.
    """
    getlist = getattr(form, 'getlist', None)
    condicoes = getlist('condicoes') if getlist else form.get('condicoes')
    return {
        'ordem': form.get('ordem'),
        'valor_ate': form.get('valor_ate'),
        'aprovacoes_necessarias': form.get('aprovacoes_necessarias'),
        'minimo_cotacoes': form.get('minimo_cotacoes'),
        'exige_admin': form.get('exige_admin'),
        'ativo': form.get('ativo'),
        'condicoes': condicoes,
    }


def validar(admin_id, faixa_id, dados):
    """Valida os campos e devolve o dicionário limpo. Levanta `FaixaInvalida`.

    `faixa_id` é `None` quando a faixa está nascendo — o que muda é só a
    conferência de `ordem` repetida, que precisa ignorar a própria linha.
    """
    erros = []

    ordem = _para_inteiro(dados.get('ordem'), 'ordem', erros, minimo=1)
    if ordem is not None:
        q = FaixaAlcada.query.filter_by(admin_id=admin_id, ordem=ordem)
        if faixa_id is not None:
            # `id != NULL` é NULL em SQL e não filtraria nada: na criação a
            # comparação simplesmente não existe.
            q = q.filter(FaixaAlcada.id != faixa_id)
        repetida = q.first()
        if repetida is not None:
            # `uq_faixa_alcada_admin_ordem` já barra isto no banco. A recusa
            # aqui é para que o operador leia um motivo em português em vez de
            # um IntegrityError de dentro do commit.
            erros.append(f'ordem: já existe uma faixa de ordem {ordem} neste '
                         f'tenant')

    valor_ate = _para_teto(dados.get('valor_ate'), erros)

    aprovacoes = _para_inteiro(dados.get('aprovacoes_necessarias'),
                               'aprovações necessárias', erros,
                               minimo=MIN_APROVACOES)
    if aprovacoes is not None and aprovacoes > MAX_APROVACOES:
        erros.append(f'aprovações necessárias: no máximo {MAX_APROVACOES}')

    minimo_cotacoes = _para_inteiro(dados.get('minimo_cotacoes'),
                                    'mínimo de cotações', erros, minimo=0)
    if minimo_cotacoes == 1:
        erros.append('mínimo de cotações: use 0 (não exige mapa) ou 2 ou mais. '
                     'Uma cotação só não é concorrência, é orçamento')

    condicoes = _para_condicoes(dados.get('condicoes'), erros)

    if erros:
        raise FaixaInvalida(erros)

    return {
        'ordem': ordem,
        'valor_ate': valor_ate,
        'aprovacoes_necessarias': aprovacoes,
        'minimo_cotacoes': minimo_cotacoes,
        # `exige_mapa_concorrencia` não é campo de formulário: a A3 a
        # transformou em derivada (`minimo_cotacoes > 0`) e ela permanece na
        # tabela só porque coluna não se remove no mesmo release em que se
        # muda o leitor. Mantê-la em sincronia aqui evita que um SELECT antigo
        # descreva o contrário do que o motor faz.
        'exige_mapa_concorrencia': minimo_cotacoes > 0,
        'exige_admin': _booleano(dados.get('exige_admin')),
        'ativo': _booleano(dados.get('ativo')),
        'condicoes_ativas': condicoes,
    }


def _conferir_invariantes(admin_id, faixa_id, limpo):
    """Compara os invariantes ANTES × DEPOIS. Devolve os avisos herdados.

    Levanta `FaixaInvalida` com as violações que ESTA edição cria. As que já
    existiam e continuam existindo voltam como aviso: recusá-las travaria o
    tenant já inconsistente na única tela capaz de consertá-lo.
    """
    atuais = [_Linha(f.id, f.ordem, f.valor_ate, bool(f.ativo))
              for f in listar_faixas(admin_id)]
    antes = _violacoes(atuais)

    nova = _Linha(faixa_id, limpo['ordem'], limpo['valor_ate'], limpo['ativo'])
    projetadas = [l for l in atuais if faixa_id is None or l.id != faixa_id]
    projetadas.append(nova)
    depois = _violacoes(projetadas)

    criadas = [texto for codigo, texto in depois.items() if codigo not in antes]
    if criadas:
        raise FaixaInvalida(criadas)

    herdadas = [texto for codigo, texto in depois.items() if codigo in antes]
    if herdadas:
        logger.warning('tenant %s salvou faixa mantendo %d violação(ões) '
                       'anterior(es) de invariante', admin_id, len(herdadas))
    return herdadas


def salvar_faixa(admin_id, faixa_id, dados):
    """Valida e aplica a edição. Devolve `(faixa, avisos)`. **NÃO commita.**

    Mesmo contrato de `registrar_aprovacao` e de `services.timbre_pdf.importar`:
    quem persiste é a rota, junto com o resto da transação da tela.

    `faixa_id = None` cria uma faixa nova. `faixa_id` de outro tenant levanta
    `FaixaInvalida` — mas a rota nem chega aqui nesse caso: ela resolve a
    faixa por `faixa_do_tenant` e devolve 404 antes.
    """
    faixa = None
    if faixa_id is not None:
        faixa = faixa_do_tenant(admin_id, faixa_id)
        if faixa is None:
            raise FaixaInvalida(['faixa inexistente neste tenant'])

    limpo = validar(admin_id, faixa_id, dados)
    avisos = _conferir_invariantes(admin_id, faixa_id, limpo)

    if faixa is None:
        faixa = FaixaAlcada(admin_id=admin_id)
        db.session.add(faixa)

    for campo, valor in limpo.items():
        setattr(faixa, campo, valor)

    logger.info('faixa de alçada %s do tenant %s salva (ordem=%s, teto=%s, '
                'minimo_cotacoes=%s, condicoes=%r)',
                faixa_id or 'nova', admin_id, limpo['ordem'],
                limpo['valor_ate'], limpo['minimo_cotacoes'],
                limpo['condicoes_ativas'])
    return faixa, avisos
