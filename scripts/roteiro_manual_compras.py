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

from anotar_captura import Acao, Campo, Tela


def resolver_ids():
    """Traduz os números estáveis do cenário nos ids desta rodada."""
    from app import app
    from models import ContaPagar, Obra, PedidoCompra, RequisicaoCompra, Usuario
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

        def obra(codigo):
            o = Obra.query.filter_by(admin_id=adm.id, codigo=codigo).first()
            if not o:
                raise SystemExit(f'obra {codigo} não existe — refaça o seed')
            return o.id

        return {
            # As DUAS obras: as ações escolhem a obra pelo `value` do <select>,
            # e QUAL delas decide o que a tela mostra. 📌 A obra limpa não tem
            # requisição nenhuma; a `OB-MANUAL` chega com a janela do
            # anti-fracionamento cheia. É essa diferença que separa a tela do
            # aviso de alçada da tela do degrau — e não dá para separá-las por
            # etapa, porque 📖 o formulário não tem campo de etapa (ver o
            # comentário na tela `10_subiu_de_faixa`).
            'obra_limpa': obra('OB-LIMPA'),
            'obra_manual': obra('OB-MANUAL'),
            'rc_rascunho': rc('RC-2026-0001'),
            'rc_aguardando': rc('RC-2026-0002'),
            'rc_rejeitada': rc('RC-2026-0003'),
            'rc_aprovada': rc('RC-2026-0004'),
            'ped_a': ped_a.id, 'ped_b': ped_b.id, 'ped_c': ped_c.id,
            'conta_c': conta_c.id,
        }


# Os itens que as ações digitam. Saem do catálogo que o seed monta, para que a
# figura mostre material de obra de verdade — e o preço vai com VÍRGULA, porque
# 📖 `_itens_do_form` troca vírgula por ponto e é o parser leniente.
ITEM = ('Cimento CP-II-Z-32 — saco 50 kg', '20', '39,90')


def montar(ids):
    """As 22 telas, na ordem em que a pessoa as encontra."""
    return [

        # ---------------- ATO 1 — o solicitante pede ----------------
        Tela(
            slug='01_login', titulo='Entrar no sistema', papel='anon',
            ato='Antes de tudo', ato_resumo='Entrar no sistema.',
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
            ato='Ato 1 — Quem precisa, pede',
            ato_resumo='O encarregado da obra abre a requisição, e descobre o '
                       'que a alçada vai exigir. Nada foi comprado ainda.',
            papel='solicitante', rota='/compras/requisicoes',
            resumo='O ponto de partida de toda compra. Aqui estão as suas '
                   'requisições e em que pé cada uma está.',
            campos=[
                Campo(1, 'a[href*="/compras/requisicoes/nova"]', 'Nova requisição'),
                Campo(2, 'a[href*="estado="]', 'Filtros por estado',
                      nota='Cada botão traz a CONTAGEM do estado. É por aqui que '
                           'se acha o que parou: o que está em RASCUNHO é seu, o '
                           'que está AGUARDANDO está com quem aprova.'),
                Campo(3, 'thead th:nth-child(5)', 'Valor estimado',
                      nota='Estimado, não fechado — quem fecha é o comprador ao '
                           'emitir o pedido.'),
                Campo(4, 'thead th:nth-child(6)', 'Estado'),
                Campo(5, 'tbody .badge', 'O selo do estado da linha',
                      nota='Um selo amarelo "acumulado" pode aparecer ao lado do '
                           'número: é o anti-fracionamento avisando que o somado '
                           'da janela subiu a faixa daquela requisição. Ele só '
                           'existe com as alçadas avançadas ligadas, e este '
                           'manual foi feito com elas desligadas.'),
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
                           'marcar o campo 4. Ver a tela seguinte.'),
                Campo(4, 'input[name="emergencial"]', 'Rito de emergência',
                      nota='Marque só quando for. Ao marcar, a tela muda na hora '
                           '— é o que a tela 4 mostra.'),
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
                           'de grandeza. Vírgula ou ponto, os dois servem.'),
                Campo(10, 'select[name="item_almoxarifado_id[]"]', 'Catálogo',
                      nota='Ligando ao catálogo, a entrada no estoque sai automática '
                           'quando o material chegar. Item fora do catálogo '
                           'atravessa o ciclo inteiro SEM movimentar estoque.'),
                Campo(11, '#btnAddItem', 'Adicionar item',
                      nota='Uma requisição pode ter quantas linhas precisar — e '
                           'pedir tudo de uma vez é o que evita o fracionamento.'),
                Campo(12, '.btn-remover', 'Remover a linha'),
                Campo(13, 'button[type="submit"]', 'Salvar rascunho'),
            ],
            depois='A requisição nasce em RASCUNHO. Ela ainda é sua: ninguém '
                   'foi avisado e nada foi comprado.',
            atencao='A obra é exigida pelo próprio navegador: sem ela o botão não '
                    'envia. O servidor confere de novo (📖 compras_views.py:1987), '
                    'e é essa segunda guarda que vale contra um envio forjado.'),

        Tela(
            slug='04_emergencia_exige', titulo='A emergência muda o formulário',
            papel='solicitante', rota='/compras/requisicoes/nova',
            resumo='Marcar o rito de emergência não é só um selo: a tela muda na '
                   'hora, e a justificativa deixa de ser opcional.',
            # 🔬 19/08 — medido: marcar o campo torna VISÍVEIS o aviso e o
            # asterisco, e põe `required` no textarea. Por isso esta tela existe
            # no lugar da recusa do servidor: o navegador barra antes, e a
            # recusa de `compras_views.py:2049` é inalcançável pela tela.
            acoes=[Acao('marcar', 'input[name="emergencial"]')],
            campos=[
                Campo(1, '#emergencialAviso', 'O aviso do rito',
                      nota='Ele diz o que a emergência custa: a compra anda sem '
                           'aprovação prévia, mas fica devendo ratificação em 48 h.'),
                Campo(2, '#justificativaObrigatoria', 'O asterisco que apareceu'),
                Campo(3, '#justificativaCampo', 'Justificativa — agora obrigatória',
                      True,
                      'É o preço da dispensa de aprovação, e é o que os '
                      'ratificadores vão ler nas próximas 48 horas.'),
            ],
            atencao='Sem justificativa o botão não envia. Não é implicância da '
                    'tela: requisição emergencial sem texto ficaria no banco '
                    'marcada como emergência e ninguém conseguiria ratificá-la.'),

        Tela(
            slug='05_recusa_sem_item', titulo='O que acontece se faltar item',
            papel='solicitante', rota='/compras/requisicoes/nova',
            resumo='A recusa mais comum de todas, e a que mais confunde: a '
                   'requisição precisa de pelo menos UMA linha de item.',
            acoes=[
                Acao('escolher', 'select[name="obra_id"]', '{obra_limpa}'),
                Acao('submeter', 'button[type="submit"]'),
            ],
            campos=[
                Campo(1, '.alert-danger', 'A recusa',
                      nota='Linha em branco não conta como item. Se você digitou a '
                           'descrição mas deixou quantidade ou preço vazios, a '
                           'linha é descartada e cai aqui.'),
            ],
            atencao='Nada foi gravado. A requisição não chegou a existir — volte, '
                    'preencha a linha e salve de novo.'),

        Tela(
            slug='06_alcada_no_sucesso', titulo='Quantas aprovações vai precisar',
            papel='solicitante', rota='/compras/requisicoes/nova',
            resumo='Ao salvar, o sistema já diz quantas assinaturas aquele valor '
                   'exige. O número sai da faixa de alçada da empresa, não do acaso.',
            acoes=[
                Acao('escolher', 'select[name="obra_id"]', '{obra_limpa}'),
                Acao('preencher', 'input[name="item_descricao[]"]', ITEM[0]),
                Acao('preencher', 'input[name="item_quantidade[]"]', ITEM[1]),
                Acao('preencher', 'input[name="item_preco[]"]', ITEM[2]),
                Acao('submeter', 'button[type="submit"]'),
            ],
            campos=[
                Campo(1, '.alert', 'O aviso da alçada'),
                Campo(2, '.badge.fs-6', 'O estado: RASCUNHO'),
            ],
            depois='A requisição existe, em RASCUNHO. O número de aprovações '
                   'sai da FAIXA em que o valor cai — trocar os valores das '
                   'faixas é configuração, não é código.',
            atencao='Com as alçadas avançadas ligadas este mesmo aviso ganha uma '
                    'segunda linha quando o somado da janela sobe a faixa (o '
                    'anti-fracionamento). 📌 Este manual foi capturado com elas '
                    'DESLIGADAS, que é como o tenant está — ver a decisão D2 do '
                    'plano de 18/08.'),

        Tela(
            slug='07_rascunho_itens', titulo='Conferir e ajustar os itens',
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
            slug='08_enviar', titulo='Enviar para aprovação',
            papel='solicitante', rota='/compras/requisicoes/{rc_rascunho}',
            resumo='O ato que tira a requisição das suas mãos.',
            campos=[
                Campo(1, 'form[action*="/enviar"] button', 'Enviar para aprovação'),
            ],
            depois='A requisição vai para AGUARDANDO APROVAÇÃO e aparece na fila '
                   'de quem aprova. A partir daqui você só acompanha.'),

        Tela(
            slug='09_aguardando', titulo='Depois de enviar, o que sobra para você',
            papel='solicitante', rota='/compras/requisicoes/{rc_aguardando}',
            resumo='A mesma requisição, agora fora do seu alcance. Esta tela existe '
                   'para você reconhecer o estado — e não procurar um botão que '
                   'deixou de existir.',
            campos=[
                Campo(1, '.badge.fs-6', 'O estado: AGUARDANDO APROVAÇÃO'),
            ],
            atencao='O bloco de itens não é mais editável e o botão de enviar '
                    'sumiu. Não é falha: enviar é o ato que passa a requisição '
                    'para outra pessoa. Se estiver errada, peça a quem aprova que '
                    'REJEITE — a rejeição devolve a requisição para conserto.'),

        Tela(
            slug='10_emergencia', titulo='O rito de emergência, do início ao fim',
            papel='solicitante', rota='/compras/requisicoes/nova',
            resumo='Bomba quebrou, concretagem para. A emergência aprova na hora '
                   '— e cria uma dívida: a ratificação em 48 horas.',
            acoes=[
                Acao('escolher', 'select[name="obra_id"]', '{obra_limpa}'),
                Acao('marcar', 'input[name="emergencial"]'),
                Acao('preencher', 'textarea[name="justificativa"]',
                     'Bomba de recalque queimou; a concretagem da laje para '
                     'amanhã cedo sem a bomba reserva.'),
                Acao('preencher', 'input[name="item_descricao[]"]', ITEM[0]),
                Acao('preencher', 'input[name="item_quantidade[]"]', ITEM[1]),
                Acao('preencher', 'input[name="item_preco[]"]', ITEM[2]),
                Acao('submeter', 'button[type="submit"]'),
            ],
            campos=[
                Campo(1, '.alert', 'O que o sistema respondeu'),
                Campo(2, '.badge.fs-6', 'O estado: APROVADA, sem passar pela fila'),
            ],
            depois='A requisição já pode virar pedido. Mas ela nasce DEVENDO: '
                   'enquanto ninguém ratificar, a conta a pagar desta compra não '
                   'é liberada.',
            atencao='Quem ratifica é um gestor da obra ou um administrador — e a '
                    'ratificação usa a mesma tela de aprovar. O prazo aparece no '
                    'painel da própria requisição.'),

        # ---------------- ATO 2 — o gestor decide ----------------
        Tela(
            slug='11_fila_aprovacao', titulo='A fila de aprovação',
            ato='Ato 2 — Quem responde pela obra, decide',
            ato_resumo='A gerência aprova, rejeita ou devolve para conserto.',
            papel='gestor', rota='/compras/aprovacao',
            resumo='Tudo que está esperando a sua decisão, em um lugar só.',
            campos=[]),

        Tela(
            slug='12_aprovar', titulo='Aprovar',
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
            slug='13_rejeitar', titulo='Rejeitar',
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
            slug='14_corrigir', titulo='Corrigir e reenviar',
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

        Tela(
            slug='15_aprovada_emitir', titulo='Aprovada — e agora?',
            papel='solicitante', rota='/compras/requisicoes/{rc_aprovada}',
            resumo='A requisição voltou aprovada. Este é o ponto em que se '
                   'descobre quem pode transformá-la em compra.',
            campos=[
                Campo(1, '.badge.fs-6', 'O estado: APROVADA'),
                Campo(2, 'form[action*="emitir-pedido"]', 'O bloco de emitir pedido'),
            ],
            atencao='Se este bloco NÃO aparece para você, não é falha do sistema: '
                    'é o seu papel NESTA obra. 📖 Emitir pedido é do COMPRADOR; '
                    'quem é só Gestor aprova e não emite, e quem não tem vínculo '
                    'nenhum com a obra não vê nem a requisição. Foi essa a '
                    'confusão mais cara da implantação — a tela some inteira e '
                    'parece defeito.'),

        # ---------------- ATO 3 — o comprador emite ----------------
        Tela(
            slug='16_emitir_pedido', titulo='Emitir o pedido de compra',
            ato='Ato 3 — Quem compra, negocia',
            ato_resumo='A requisição aprovada vira pedido, com fornecedor e '
                       'valor real.',
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
            slug='17_pedido_triade', titulo='O painel das três pernas',
            ato='Ato 4 — Quem paga, confere',
            ato_resumo='A conta só é paga quando pedido, atesto e nota fecham.',
            papel='admin', rota='/compras/{ped_a}',
            resumo='A conta nasceu BLOQUEADA. Ela só pode ser paga quando as três '
                   'pernas fecham: o pedido, o recebimento com atesto e a nota '
                   'fiscal. O painel diz qual falta.',
            campos=[],
            atencao='Se você tentar pagar agora, o sistema recusa e diz o que está '
                    'faltando. Não é travamento: é o controle funcionando.'),

        Tela(
            slug='18_recebimento', titulo='Receber e atestar',
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
            slug='19_nota', titulo='Lançar a nota fiscal',
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
            slug='20_liberar', titulo='Liberar para pagamento',
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
            slug='21_pagar', titulo='Dar baixa na conta',
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
            slug='22_lote', titulo='Montar o lote de pagamento',
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
        # O valor da ação passa pelo MESMO `format`: é assim que
        # `Acao('escolher', 'select[name="obra_id"]', '{obra_limpa}')` vira o id
        # desta rodada. Id fixo no roteiro é o que aposentou a captura de 22/07.
        for a in t.acoes:
            a.valor = str(a.valor).format(**ids)
    return montadas


if __name__ == '__main__':
    for t in telas():
        marcas = ', '.join(str(c.numero) for c in t.campos) or '—'
        print(f'{t.slug:24s} {t.papel:12s} {t.rota:52s} campos: {marcas}')
