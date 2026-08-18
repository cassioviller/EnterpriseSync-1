#!/usr/bin/env python3
"""O roteiro do manual de compras — as 16 telas, os campos e os números.

Esta é a FONTE ÚNICA. Dela saem as três coisas que não podem divergir:

  * a caixa numerada desenhada sobre o campo (scripts/anotar_captura.py);
  * a legenda numerada embaixo da figura (scripts/gerar_manual_compras.py);
  * a ordem dos passos no PDF.

Nada de id fixo. 📖 A captura de 22/07 fixou `OBRA_ID = 1276` e por isso não
roda mais. Aqui os ids são RESOLVIDOS do banco pelos números estáveis que o
seed garante (`RC-2026-0001`, `PC-2026-0101`), então o roteiro sobrevive a
qualquer rodada nova de `scripts/seed_manual_compras.py`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anotar_captura import Campo, Tela


def resolver_ids():
    """Traduz os números estáveis do cenário nos ids desta rodada."""
    from app import app
    from models import ContaPagar, PedidoCompra, RequisicaoCompra, Usuario
    from seed_manual_compras import MARCA

    with app.app_context():
        adm = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
        if not adm:
            raise SystemExit('cenário não existe — rode scripts/seed_manual_compras.py')

        def rc(numero):
            r = RequisicaoCompra.query.filter_by(admin_id=adm.id, numero=numero).first()
            if not r:
                raise SystemExit(f'requisição {numero} não existe — refaça o seed')
            return r.id

        def pc(numero):
            p = PedidoCompra.query.filter_by(admin_id=adm.id, numero=numero).first()
            if not p:
                raise SystemExit(f'pedido {numero} não existe — refaça o seed')
            return p

        ped_a, ped_b, ped_c = pc('PC-2026-0101'), pc('PC-2026-0102'), pc('PC-2026-0103')
        conta_c = ContaPagar.query.filter_by(pedido_compra_id=ped_c.id).first()
        if not conta_c:
            raise SystemExit('a conta do PC-2026-0103 não existe — refaça o seed')

        return {
            'rc_rascunho': rc('RC-2026-0001'),
            'rc_aguardando': rc('RC-2026-0002'),
            'rc_rejeitada': rc('RC-2026-0003'),
            'rc_aprovada': rc('RC-2026-0004'),
            'ped_a': ped_a.id, 'ped_b': ped_b.id, 'ped_c': ped_c.id,
            'conta_c': conta_c.id,
        }


def montar(ids):
    """As 16 telas, na ordem em que a pessoa as encontra."""
    return [

        # ---------------- ATO 1 — o solicitante pede ----------------
        Tela(
            slug='01_login', titulo='Entrar no sistema', papel='anon',
            rota='/login',
            resumo='Todo mundo entra por aqui. O que você vê depois depende do '
                   'seu perfil: quem pede vê a obra, quem aprova vê a fila.',
            campos=[
                Campo(1, 'input[name="username"]', 'Usuário ou e-mail', True),
                Campo(2, 'input[name="password"]', 'Senha', True),
                Campo(3, 'button[type="submit"]', 'Entrar'),
            ],
            depois='O sistema abre na tela inicial do seu perfil.',
            recorte='form'),

        Tela(
            slug='02_lista_requisicoes', titulo='A lista de requisições',
            papel='solicitante', rota='/compras/requisicoes',
            resumo='O ponto de partida de toda compra. Aqui estão as suas '
                   'requisições e em que pé cada uma está.',
            campos=[
                Campo(1, 'a[href*="/compras/requisicoes/nova"]', 'Nova requisição'),
            ],
            atencao='Se você tentar ir direto em Compras → Nova compra, o sistema '
                    'traz você de volta para cá. Com a governança de compras ligada, '
                    'toda compra começa por uma requisição — não dá para pular.'),

        Tela(
            slug='03_nova_requisicao', titulo='Preencher a requisição',
            papel='solicitante', rota='/compras/requisicoes/nova',
            resumo='Onde você diz o que precisa, para qual obra e para quando. '
                   'O preço é ESTIMADO: quem fecha o valor é o comprador, depois.',
            campos=[
                Campo(1, 'select[name="obra_id"]', 'Obra', True,
                      'Sem obra a requisição não existe — é o que faz o custo '
                      'chegar no lugar certo.'),
                Campo(2, 'input[name="data_necessidade"]', 'Data de necessidade',
                      nota='Quando o material tem de estar na obra, não quando '
                           'você quer que seja comprado.'),
                Campo(3, 'textarea[name="justificativa"]', 'Justificativa',
                      nota='Opcional no dia a dia — MAS vira obrigatória se você '
                           'marcar o campo 4.'),
                Campo(4, 'input[name="emergencial"]', 'Rito de emergência',
                      nota='Marque só quando for. Ao marcar, a justificativa passa '
                           'a ser exigida e a aprovação segue outro caminho.'),
                Campo(5, 'select[name="mapa_v2_id"]', 'Mapa de concorrência',
                      nota='Se já existe cotação para este material, ligue aqui. '
                           'Quando a empresa exige cotação, este campo passa a '
                           'ser cobrado na aprovação.'),
                Campo(6, 'input[name="item_descricao[]"]', 'Descrição do item', True),
                Campo(7, 'input[name="item_unidade[]"]', 'Unidade', True,
                      'sc, m³, br, un — a mesma que o fornecedor usa na nota.'),
                Campo(8, 'input[name="item_quantidade[]"]', 'Quantidade', True),
                Campo(9, 'input[name="item_preco[]"]', 'Preço estimado',
                      nota='Chute informado. Serve para a aprovação saber a ordem '
                           'de grandeza.'),
                Campo(10, 'select[name="item_almoxarifado_id[]"]', 'Catálogo',
                      nota='Ligando ao catálogo, a entrada no estoque sai automática '
                           'quando o material chegar.'),
            ],
            depois='A requisição nasce em RASCUNHO. Ela ainda é sua: ninguém '
                   'foi avisado e nada foi comprado.'),

        Tela(
            slug='04_rascunho_itens', titulo='Conferir e ajustar os itens',
            papel='solicitante', rota='/compras/requisicoes/{rc_rascunho}',
            resumo='Enquanto está em RASCUNHO, tudo é editável. É aqui que você '
                   'corrige quantidade, acrescenta linha ou tira item.',
            campos=[
                Campo(1, 'form[action*="/itens"]', 'Bloco de itens'),
            ],
            atencao='Depois de enviar para aprovação, esta edição some. Confira '
                    'agora. Se a sua empresa exigir cotação para esta faixa de '
                    'valor, aparece aqui também um bloco para vincular o mapa de '
                    'cotação — ele só existe quando a regra de alçada pede.'),

        Tela(
            slug='05_enviar', titulo='Enviar para aprovação',
            papel='solicitante', rota='/compras/requisicoes/{rc_rascunho}',
            resumo='O ato que tira a requisição das suas mãos.',
            campos=[
                Campo(1, 'form[action*="/enviar"] button', 'Enviar para aprovação'),
            ],
            depois='A requisição vai para AGUARDANDO APROVAÇÃO e aparece na fila '
                   'de quem aprova. A partir daqui você só acompanha.'),

        # ---------------- ATO 2 — o gestor decide ----------------
        Tela(
            slug='06_fila_aprovacao', titulo='A fila de aprovação',
            papel='gestor', rota='/compras/aprovacao',
            resumo='Tudo que está esperando a sua decisão, em um lugar só.',
            campos=[]),

        Tela(
            slug='07_aprovar', titulo='Aprovar',
            papel='gestor', rota='/compras/requisicoes/{rc_aguardando}',
            resumo='Você vê o que foi pedido, para qual obra e quanto custa por '
                   'estimativa. Aprovar libera a compra — não a faz.',
            campos=[
                Campo(1, 'form[action*="/aprovar"] input[name="observacao"]',
                      'Observação',
                      nota='Opcional, mas é o que o comprador vai ler antes de '
                           'negociar.'),
                Campo(2, 'form[action*="/aprovar"] button', 'Aprovar'),
            ],
            depois='A requisição vai para APROVADA e some da sua fila.'),

        Tela(
            slug='08_rejeitar', titulo='Rejeitar',
            papel='gestor', rota='/compras/requisicoes/{rc_aguardando}',
            resumo='Rejeitar não é matar o pedido. É devolver para conserto.',
            campos=[
                Campo(1, 'form[action*="/rejeitar"] input[name="motivo"]',
                      'Motivo', True,
                      'Escreva o que precisa mudar. É a única coisa que o '
                      'solicitante vai ver.'),
                Campo(2, 'form[action*="/rejeitar"] button', 'Rejeitar'),
            ],
            depois='A requisição volta para o solicitante, marcada como REJEITADA, '
                   'com o seu motivo à vista.'),

        Tela(
            slug='09_corrigir', titulo='Corrigir e reenviar',
            papel='solicitante', rota='/compras/requisicoes/{rc_rejeitada}',
            resumo='Foi rejeitada. Você lê o motivo, conserta e manda de novo — '
                   'sem começar do zero.',
            campos=[
                Campo(1, 'form[action*="/corrigir"] button', 'Corrigir requisição'),
            ],
            depois='Ela volta para RASCUNHO, editável de novo. O histórico guarda '
                   'os dois momentos: a rejeição e a correção.',
            atencao='Requisição rejeitada NÃO está perdida. Se você não achar este '
                    'botão, você está olhando a requisição de outra pessoa.'),

        # ---------------- ATO 3 — o comprador emite ----------------
        Tela(
            slug='10_emitir_pedido', titulo='Emitir o pedido de compra',
            papel='comprador', rota='/compras/requisicoes/{rc_aprovada}',
            resumo='A requisição vira pedido. Aqui entra o fornecedor escolhido e '
                   'o valor REAL negociado.',
            campos=[
                Campo(1, 'form[action*="/emitir-pedido"] select[name="fornecedor_id"]',
                      'Fornecedor', True),
                Campo(2, 'form[action*="/emitir-pedido"] input[name="numero"]',
                      'Número do pedido',
                      nota='Em branco, o sistema numera sozinho.'),
                Campo(3, 'form[action*="/emitir-pedido"] input[name="data_compra"]',
                      'Data da compra', True),
                Campo(4, 'form[action*="/emitir-pedido"] select[name="condicao_pagamento"]',
                      'Condição de pagamento', True,
                      'É o que define quando a conta vence.'),
                Campo(5, 'form[action*="/emitir-pedido"] input[name="parcelas"]',
                      'Parcelas'),
                Campo(6, 'form[action*="/emitir-pedido"] input[name="item_preco_real[]"]',
                      'Preço fechado por item',
                      nota='O valor que você NEGOCIOU. Em branco, vale o estimado '
                           'da requisição. O total não pode passar do que foi '
                           'aprovado — se passou, volte para uma requisição nova.'),
                Campo(7, 'form[action*="/emitir-pedido"] button', 'Emitir pedido'),
            ],
            depois='Nasce o pedido de compra E nasce a conta a pagar. A requisição '
                   'vira CONVERTIDA e não muda mais de estado.',
            atencao='Deste ponto não se volta pela requisição. Desfazer é excluir o '
                    'pedido, que é outra operação. E se este bloco não aparecer '
                    'para você, é o seu papel NESTA obra: emitir pedido é do '
                    'Comprador. Quem é Gestor aprova, mas não emite — é a mesma '
                    'separação que impede aprovar a própria compra.'),

        # ---------------- ATO 4 — o dinheiro ----------------
        Tela(
            slug='11_pedido_triade', titulo='O painel das três pernas',
            papel='admin', rota='/compras/{ped_a}',
            resumo='A conta nasceu BLOQUEADA. Ela só pode ser paga quando as três '
                   'pernas fecham: o pedido, o recebimento com atesto e a nota '
                   'fiscal. O painel diz qual falta.',
            campos=[],
            atencao='Se você tentar pagar agora, o sistema recusa e diz o que está '
                    'faltando. Não é travamento: é o controle funcionando.'),

        Tela(
            slug='12_recebimento', titulo='Receber e atestar',
            papel='admin', rota='/compras/{ped_a}/recebimento',
            resumo='O material chegou. Quem recebe confere e atesta a quantidade — '
                   'e é isso que autoriza o pagamento, não a nota.',
            campos=[
                Campo(1, 'input[name="data_recebimento"]', 'Data do recebimento', True),
                Campo(2, 'input[name^="qtd_"]', 'Quantidade recebida', True,
                      'A quantidade REAL que chegou. Se veio menos, ponha menos: '
                      'o saldo continua em aberto.'),
                Campo(3, 'input[name="encerra_saldo"]', 'Encerrar o saldo',
                      nota='Marque quando o fornecedor não vai mais entregar o resto.'),
                Campo(4, 'textarea[name="observacao"]', 'Observação'),
            ],
            depois='A perna do atesto fecha e o valor atestado aparece no painel.'),

        Tela(
            slug='13_nota', titulo='Lançar a nota fiscal',
            papel='admin', rota='/compras/{ped_b}/nota',
            resumo='A terceira perna. Sem ela a conta continua bloqueada.',
            campos=[
                Campo(1, 'input[name="numero"]', 'Número da nota', True),
                Campo(2, 'input[name="serie"]', 'Série'),
                Campo(3, 'input[name="valor_total"]', 'Valor total', True,
                      'Use vírgula para os centavos: 2.336,00. O sistema recusa '
                      'valor ambíguo em vez de adivinhar.'),
                Campo(4, 'input[name="data_emissao"]', 'Data de emissão', True),
                Campo(5, 'input[name="data_vencimento"]', 'Vencimento', True),
                Campo(6, 'input[name="chave_acesso"]', 'Chave de acesso'),
            ],
            depois='Com pedido, atesto e nota, a tríade fecha.',
            atencao='Só quem é administrador lança nota. Se o campo não aparece '
                    'para você, é o seu perfil.'),

        Tela(
            slug='14_liberar', titulo='Liberar para pagamento',
            papel='admin', rota='/compras/{ped_b}',
            resumo='Tríade fechada. Este é o botão que destrava a conta.',
            campos=[
                Campo(1, 'form[action*="/liberar"] button', 'Liberar para pagamento'),
            ],
            depois='A conta sai de BLOQUEADA e passa a aceitar baixa.',
            atencao='Se faltar uma perna, o botão vira "Liberar com ressalva" e '
                    'exige uma justificativa de pelo menos 15 caracteres. É '
                    'exceção auditável — fica registrada com o seu nome.'),

        Tela(
            slug='15_pagar', titulo='Dar baixa na conta',
            papel='admin', rota='/financeiro/contas-pagar/{conta_c}/pagar',
            resumo='A conta liberada finalmente aceita o pagamento.',
            campos=[
                Campo(1, 'input[name="valor_pago"]', 'Valor pago', True,
                      'Pode ser parcial: o saldo continua em aberto.'),
                Campo(2, 'input[name="data_pagamento"]', 'Data do pagamento', True),
                Campo(3, 'select[name="banco_id"]', 'Banco', True,
                      'De qual conta saiu o dinheiro.'),
                Campo(4, 'select[name="forma_pagamento"]', 'Forma de pagamento'),
            ],
            depois='A conta vira PAGA e o saldo do banco desce.'),

        Tela(
            slug='16_lote', titulo='Montar o lote de pagamento',
            papel='admin', rota='/financeiro/fechamento-pagamentos',
            resumo='Em vez de pagar uma a uma, junte as contas do ciclo num lote. '
                   'Quem monta e quem fecha devem ser pessoas diferentes.',
            campos=[
                Campo(1, 'input[name="data_fechamento"]', 'Data do fechamento', True),
                Campo(2, 'input[name="conta_ids"]', 'Contas do lote', True,
                      'Marque as que entram neste pagamento.'),
            ],
            depois='O lote fecha com o nome de quem fechou. É a segregação de '
                   'função: quem monta não fecha.'),
    ]


def telas(ids=None):
    ids = ids or resolver_ids()
    montadas = montar(ids)
    for t in montadas:
        t.rota = t.rota.format(**ids)
    return montadas


if __name__ == '__main__':
    for t in telas():
        marcas = ', '.join(str(c.numero) for c in t.campos) or '—'
        print(f'{t.slug:24s} {t.papel:12s} {t.rota:52s} campos: {marcas}')
