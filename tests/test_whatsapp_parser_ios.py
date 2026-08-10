"""Parser do export do WhatsApp em formato iOS (scripts/whatsapp_para_rdos.py).

O export do iPhone (`_chat.txt`) difere do Android em tudo que o parser
toca: cabeçalho `[DD/MM/AAAA, HH:MM:SS]`, anexo `<anexado: X>` e marcas
bidi U+200E/U+2068 espalhadas. Estes testes travam:

  • as duas formas de cabeçalho abrem mensagem; continuação cola no corpo;
  • anexo iOS é reconhecido e a legenda é a continuação;
  • marcas bidi não vazam para o comentário;
  • `marcador_obra` como lista de APELIDOS agrupa as grafias da mesma obra.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../scripts'))

from whatsapp_para_rdos import agrupar_rdos, parse_mensagens  # noqa: E402

EXPORT_IOS = (
    '‎[08/01/2025, 18:31:13] Eng Alan: ‎<anexado: 00000009-PHOTO.jpg>\n'
    'Legenda da foto\n'
    '[15/07/2026, 09:17:48] Abel: *Obra a Angela - RDO 14/07/2026*\n'
    '\n'
    'Efetivo: 4\n'
    'Execução do forro ⁨@Cássio⁩\n'
    '[17/07/2026, 11:33:56] Abel: *15/07/2026*\n'
    '*Obra casa Angela*\n'
    'Plaqueamento\n'
)


def test_cabecalho_ios_abre_mensagem_e_continuacao_cola():
    msgs = parse_mensagens(EXPORT_IOS)
    assert len(msgs) == 3
    assert msgs[0].data.isoformat() == '2025-01-08'
    assert msgs[1].corpo.startswith('*Obra a Angela')
    assert 'Execução do forro' in msgs[1].corpo


def test_anexo_ios_com_legenda():
    msgs = parse_mensagens(EXPORT_IOS)
    assert msgs[0].anexo == '00000009-PHOTO.jpg'
    assert msgs[0].legenda == 'Legenda da foto'


def test_marcas_bidi_nao_vazam():
    msgs = parse_mensagens(EXPORT_IOS)
    assert '⁨' not in msgs[1].corpo and '⁩' not in msgs[1].corpo
    assert '@Cássio' in msgs[1].corpo


def test_apelidos_agrupam_grafias_da_mesma_obra():
    msgs = parse_mensagens(EXPORT_IOS)
    blocos, _ = agrupar_rdos(
        msgs, ['Obra a Angela', 'Obra casa Angela'], ['Obra Itu'])
    assert sorted(b.data_rdo.isoformat() for b in blocos) == \
        ['2026-07-14', '2026-07-15']
