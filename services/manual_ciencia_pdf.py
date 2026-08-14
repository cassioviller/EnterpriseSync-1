#!/usr/bin/env python3
"""Manual da CIÊNCIA no portal do cliente, em PDF.

O documento que a construtora baixa e manda junto com o convite (link +
senha temporária) que nasce na tela da obra. Cobre só o que o responsável do
cliente precisa fazer: criar a senha, dar ciência num RDO, o que fica
registrado, o que fazer quando algo trava e as dúvidas que aparecem sempre.

DELIBERADAMENTE SEM A MARCA DA CONSTRUTORA — nem logo, nem nome — pela mesma
razão do portal e do recibo de ciência: é material que vive do lado do
cliente. Quem envia já se identifica na mensagem do convite.

Também deliberadamente SEM DADOS DA OBRA: um único PDF serve todas as obras
e todos os responsáveis, e não vence quando o link muda. O link e a senha
vão na mensagem do convite, que é onde eles já estão.

Os números aqui (72 h, 8 caracteres, 5 tentativas / 15 min, 10 erros) são os
do código e precisam andar junto com ele:
  * `ObraSignatarioCliente.HORAS_SENHA_TEMPORARIA` e `MAX_FALHAS` (models);
  * `services.portal_signatario_auth.SENHA_MIN`;
  * o `limiter.limit` de `portal_obras_views.ciencia_confirmar`.
`tests/test_manual_ciencia_pdf.py` prende os quatro ao texto: mexeu na
regra, o teste cobra a frase.
"""
from __future__ import annotations

import logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from models import ObraSignatarioCliente
from services.portal_signatario_auth import SENHA_MIN
from services.rdo_pdf_service import BORDER, _build_styles, _Footer

logger = logging.getLogger(__name__)

_FUNDO = colors.HexColor('#f8fafc')
_AVISO = colors.HexColor('#fff8e6')
_AVISO_BORDA = colors.HexColor('#f0d4b0')

# Quantas tentativas o rate-limit de `ciencia_confirmar` aceita, e em que
# janela. Está aqui como texto porque o decorador do Flask-Limiter é uma
# string ('5 per 15 minutes') e não expõe os números.
_TENTATIVAS = 5
_JANELA_MIN = 15

TITULO = 'Portal da Obra — assinatura dos relatórios diários'


def _p(texto, styles, estilo='body'):
    return Paragraph(texto, styles[estilo])


def _secao(titulo, styles):
    """Título de seção, com a régua fina por baixo."""
    t = Table([[Paragraph(titulo.upper(), styles['section'])]],
              colWidths=[None])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -1), 0.6, BORDER),
    ]))
    return t


def _aviso(titulo, corpo, styles):
    """Caixa de destaque — usada com parcimônia, só onde perder a informação
    custa caro ao cliente (o recibo que só existe naquele instante)."""
    interno = [
        Paragraph(titulo.upper(), styles['kpi_label']),
        Spacer(1, 2),
        Paragraph(corpo, styles['body']),
    ]
    t = Table([[interno]], colWidths=[None])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _AVISO),
        ('BOX', (0, 0), (-1, -1), 0.7, _AVISO_BORDA),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def _passos(itens, styles):
    """Os passos da ciência, numerados.

    A numeração é informação, não enfeite: aqui existe ordem real — não dá
    para confirmar a senha antes de marcar o nome, nem baixar o recibo antes
    de confirmar.
    """
    linhas = []
    for n, (titulo, corpo) in enumerate(itens, start=1):
        num = Paragraph(f'<b>{n}</b>', styles['kpi_value_primary'])
        texto = [Paragraph(f'<b>{titulo}</b>', styles['cell_b']),
                 Spacer(1, 2),
                 Paragraph(corpo, styles['body'])]
        linhas.append([num, texto])
    t = Table(linhas, colWidths=[12 * mm, None])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, BORDER),
    ]))
    return t


def _tabela_situacoes(linhas, styles):
    dados = [[Paragraph('SITUAÇÃO', styles['kpi_label']),
              Paragraph('O QUE FAZER', styles['kpi_label'])]]
    for situacao, acao in linhas:
        dados.append([Paragraph(f'<b>{situacao}</b>', styles['cell_b']),
                      Paragraph(acao, styles['cell'])])
    t = Table(dados, colWidths=[45 * mm, None], repeatRows=1)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, 0), 0.6, BORDER),
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, colors.HexColor('#eef2f6')),
    ]))
    return t


def _registro(itens, styles):
    """O quadro do que fica gravado — rótulo curto à esquerda, explicação à
    direita. É a parte que sustenta o valor probatório, então ganha fundo."""
    dados = [[Paragraph(rot.upper(), styles['kpi_label']),
              Paragraph(txt, styles['cell'])] for rot, txt in itens]
    t = Table(dados, colWidths=[28 * mm, None])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), _FUNDO),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return t


def _perguntas(itens, styles):
    saida = []
    for pergunta, resposta in itens:
        saida.append(KeepTogether([
            Paragraph(f'<b>{pergunta}</b>', styles['cell_b']),
            Spacer(1, 2),
            Paragraph(resposta, styles['body']),
            Spacer(1, 5),
        ]))
    return saida


def gerar_manual_ciencia() -> bytes:
    """PDF do manual. Sem argumentos: o conteúdo não depende de obra nem
    de tenant."""
    horas = ObraSignatarioCliente.HORAS_SENHA_TEMPORARIA
    max_falhas = ObraSignatarioCliente.MAX_FALHAS

    styles = _build_styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=TITULO,
    )

    el = []

    # ── Abertura ──
    el.append(Paragraph('GUIA DO RESPONSÁVEL', styles['title']))
    el.append(Spacer(1, 4))
    el.append(Paragraph('Assinatura dos relatórios diários', styles['h1']))
    el.append(Spacer(1, 6))
    el.append(_p(
        'Como criar a sua senha e dar ciência nos relatórios diários da obra '
        '(RDO) pelo portal do cliente — o que é pedido, o que fica registrado '
        'e o que fazer quando algo não sai como esperado. O endereço do portal '
        'e a sua senha temporária vão na mensagem que acompanha este guia.',
        styles, 'body_muted'))
    el.append(Spacer(1, 10))

    # ── 1. Primeiro acesso ──
    el.append(_secao('Primeiro acesso: criando a sua senha', styles))
    el.append(Spacer(1, 5))
    el.append(_p(
        'A senha temporária foi gerada e entregue pela construtora — o que '
        'significa que <b>ela conhece essa senha</b>. Por isso a temporária '
        'autentica você, mas não assina nada: na primeira vez que você tentar '
        'dar ciência, o portal desvia para a tela de definir senha.',
        styles))
    el.append(Spacer(1, 5))
    el.append(_p(
        f'Escolha ali uma senha de <b>no mínimo {SENHA_MIN} caracteres</b>, '
        'que só você conheça. A construtora não vê essa senha nova — é isso '
        'que faz a sua ciência valer como sua. Feito isso, o portal volta para '
        'o relatório e você conclui a ciência.',
        styles))
    el.append(Spacer(1, 5))
    el.append(_p(
        'Sua senha definitiva <b>não expira</b>. Você pode trocá-la quando '
        'quiser, pelo link de trocar senha na própria tela.',
        styles))
    el.append(Spacer(1, 4))

    # ── 2. Dando ciência ──
    el.append(_secao('Dando ciência num relatório', styles))
    el.append(Spacer(1, 5))
    el.append(_p(
        'A ciência é feita <b>um relatório por vez</b>, e cada responsável '
        'assina em seu próprio nome.', styles))
    el.append(Spacer(1, 6))
    el.append(_passos([
        ('Abra o relatório do dia',
         'Na seção “Relatórios diários (RDOs)”, toque no dia que quer ler. '
         'Cada linha mostra um contador — por exemplo 1/3 — com quantos '
         'responsáveis já deram ciência naquele relatório.'),
        ('Leia até o fim',
         'Percorra o efetivo, as atividades executadas, as observações e as '
         'fotos. No fim da página está a seção <b>“Ciência dos '
         'responsáveis”</b>, com a lista de todos os responsáveis pela obra e '
         'a situação de cada um.'),
        ('Marque a caixa ao lado do seu nome',
         'A identidade é a linha: você marca a caixa no <i>seu</i> nome, e a '
         'confirmação se abre logo abaixo dela. Quem já assinou aparece com a '
         'caixa marcada e a data e hora ao lado.'),
        ('Digite sua senha e confirme',
         'Há também um campo de <b>observação, opcional</b>, se você quiser '
         'deixar algo registrado junto da sua ciência — uma ressalva, um '
         'pedido, um apontamento sobre o dia. Ele fica gravado junto e '
         'aparece para a construtora.'),
        ('Baixe o seu recibo',
         'Confirmada a ciência, abre o comprovante com tudo o que ficou '
         'registrado, e um botão para baixar o <b>recibo em PDF</b>.'),
    ], styles))
    el.append(Spacer(1, 8))
    el.append(_aviso(
        'Baixe o recibo na hora',
        'A tela de comprovante é mostrada logo depois de assinar, para o '
        'navegador que acabou de assinar. Se você sair sem baixar, a ciência '
        'continua registrada e visível no próprio relatório — mas o recibo em '
        'PDF é gerado naquele momento. Guarde-o junto dos seus documentos da '
        'obra.', styles))
    el.append(Spacer(1, 4))

    # ── 3. O que fica registrado ──
    el.append(_secao('O que fica registrado quando você confirma', styles))
    el.append(Spacer(1, 5))
    # O quadro inteiro numa página só: partido ao meio, o leitor vê metade da
    # prova numa folha e metade na outra.
    el.append(KeepTogether([
        _p('A confirmação grava um conjunto de dados feito para servir de '
           'prova depois:', styles),
        Spacer(1, 6),
        _registro([
            ('Quem', 'Seu nome, como cadastrado nesta obra, e o seu cargo.'),
            ('Quando',
             'Data e hora do <i>servidor</i> — não do seu celular, que poderia '
             'estar com o relógio errado ou ajustado.'),
            ('De onde', 'O endereço de rede (IP) de onde o acesso partiu.'),
            ('Sobre o quê',
             'Uma impressão digital do conteúdo do relatório naquele instante. '
             'É ela que permite demonstrar depois que o documento que você '
             'assinou é exatamente aquele — e detectar se ele mudou.'),
        ], styles),
    ]))
    el.append(Spacer(1, 7))
    el.append(_p(
        'O objetivo desse registro é comprovar <b>autoria e integridade</b>, '
        'no amparo da MP 2.200-2/2001, art. 10, § 2º. Não é certificado '
        'digital ICP-Brasil, e não substitui um: é o registro de que uma '
        'pessoa nomeada por você viu aquele documento, naquela data, com '
        'aquele conteúdo.', styles))
    el.append(Spacer(1, 5))
    el.append(_p(
        'Dar ciência <b>não é aprovar nem concordar</b> com o que está no '
        'relatório. É registrar que você tomou conhecimento. Se tiver '
        'divergência, use o campo de observação e fale com a construtora.',
        styles))
    el.append(Spacer(1, 4))

    # ── 4. Se algo não sair como esperado ──
    el.append(_secao('Se algo não sair como esperado', styles))
    el.append(Spacer(1, 6))
    el.append(_tabela_situacoes([
        ('Esqueci minha senha',
         'Use “esqueci minha senha” na tela do relatório. O pedido vai para a '
         'construtora, que entra em contato com uma nova senha temporária. O '
         'portal não envia e-mail.'),
        ('Errei a senha várias vezes',
         f'O portal aceita {_TENTATIVAS} tentativas a cada {_JANELA_MIN} '
         f'minutos. Espere alguns minutos e tente de novo. Depois de '
         f'{max_falhas} erros seguidos o acesso é bloqueado por segurança, e '
         f'só a construtora destrava.'),
        ('A senha temporária venceu',
         f'Ela vale {horas} horas. Passado esse prazo, peça uma nova à '
         f'construtora.'),
        ('Diz que já dei ciência',
         'Cada pessoa assina uma vez por relatório. O portal leva você ao '
         'comprovante da ciência que já existe.'),
        ('Aparece o aviso “alterado”',
         'O relatório mudou depois de alguém assinar. A ciência dada continua '
         'registrada e válida, mas não corresponde mais ao texto atual — peça '
         'um relatório retificador à construtora.'),
        ('Não consigo marcar a caixa',
         'O relatório foi retificado: existe uma versão mais recente, e é '
         'nela que a ciência deve ser dada. O aviso na tela indica o caminho.'),
        ('O portal diz que está inativo',
         'O acompanhamento on-line foi pausado pela construtora. Entre em '
         'contato para retomar o acesso.'),
    ], styles))
    el.append(Spacer(1, 6))

    # ── 5. Perguntas rápidas ──
    el.append(_secao('Perguntas rápidas', styles))
    el.append(Spacer(1, 6))
    el.extend(_perguntas([
        ('Preciso instalar alguma coisa?',
         'Não. Funciona no navegador do celular, do tablet ou do computador.'),
        ('A construtora vê a minha senha?',
         'A temporária sim — foi ela quem gerou e entregou. A que você define '
         'depois, não. É exatamente por isso que o portal insiste que você '
         'troque antes da primeira ciência.'),
        ('Posso dar ciência em vários dias de uma vez?',
         'Não. Cada relatório é um documento, e cada ciência é registrada '
         'individualmente, com a data e hora em que foi dada.'),
        ('Outra pessoa pode assinar por mim?',
         'Não deveria. A senha é pessoal e é ela que sustenta o registro como '
         'sendo seu. Se outro responsável precisa assinar, ele deve estar '
         'cadastrado com o nome dele e a senha dele.'),
        ('O que acontece se eu não der ciência?',
         'O relatório continua existindo e válido como documento da obra. O '
         'que fica em aberto é o registro de que você tomou conhecimento — e '
         'é isso que o contador de cada dia mostra.'),
    ], styles))

    # Rodapé sem o nome da construtora — ver a nota do módulo.
    doc.build(el,
              onFirstPage=_Footer('', TITULO),
              onLaterPages=_Footer('', TITULO))
    pdf = buf.getvalue()
    buf.close()
    logger.info('[manual-ciencia] gerado — %s bytes', len(pdf))
    return pdf
