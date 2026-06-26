"""Anexa fotos (sintéticas) aos RDOs da obra Baias Kabod.

Gera imagens de canteiro estilizadas com PIL — céu, terreno, elementos de obra
que variam por etapa (fundação, estrutura, telhado, fechamento...) e uma barra
de legenda com obra • etapa • data. Salva em base64 WebP (otimizada 1200px +
thumbnail 300px) nos campos que o portal lê (imagem_otimizada_base64 /
thumbnail_base64). Idempotente: zera as fotos dos RDOs da obra antes.

Uso:
    PYTHONPATH=/home/runner/workspace python3 scripts/seed_fotos_rdos_baias.py [admin_id] [obra_codigo]
"""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from app import app, db
from models import (Obra, RDO, RDOFoto, RDOApontamentoCronograma, TarefaCronograma)

W, H = 1200, 800


def _font_path():
    """Resolve um TTF com cobertura latina completa (acentos, travessão)."""
    import glob
    cands = []
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data/fonts/ttf')
        cands += [os.path.join(d, 'DejaVuSans-Bold.ttf'), os.path.join(d, 'DejaVuSans.ttf')]
    except Exception:
        pass
    try:
        import cv2
        d = os.path.join(os.path.dirname(cv2.__file__), 'qt/fonts')
        cands += [os.path.join(d, 'DejaVuSans-Bold.ttf'), os.path.join(d, 'DejaVuSans.ttf')]
    except Exception:
        pass
    cands += glob.glob('/home/runner/workspace/.cache/**/DejaVuSans-Bold.ttf', recursive=True)
    cands += ['DejaVuSans-Bold.ttf', 'DejaVuSans.ttf']
    for c in cands:
        if c and (os.path.isabs(c) is False or os.path.exists(c)):
            try:
                ImageFont.truetype(c, 20)
                return c
            except Exception:
                continue
    return None


_FONT_PATH = None


def _font(size):
    global _FONT_PATH
    if _FONT_PATH is None:
        _FONT_PATH = _font_path() or ''
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# paleta por palavra-chave da etapa
def _tema(etapa):
    e = (etapa or '').lower()
    if 'funda' in e:
        return ('fundacao', (150, 140, 120))
    if 'metál' in e or 'lsf' in e or 'estrutura' in e:
        return ('estrutura', (120, 130, 145))
    if 'telh' in e or 'cobert' in e or 'shingle' in e:
        return ('telhado', (110, 95, 80))
    if 'fecha' in e or 'plaque' in e:
        return ('fechamento', (170, 150, 130))
    if 'pint' in e or 'stain' in e:
        return ('pintura', (160, 120, 95))
    if 'elétr' in e or 'hidrá' in e:
        return ('instalacoes', (130, 130, 130))
    return ('geral', (140, 135, 120))


def _cena(etapa, dia_str, idx):
    """Desenha uma cena de canteiro e devolve a Image RGB."""
    tipo, terra = _tema(etapa)
    img = Image.new('RGB', (W, H), (208, 226, 242))
    d = ImageDraw.Draw(img, 'RGBA')

    # céu em faixas (gradiente simples)
    for i in range(0, 520, 8):
        c = 200 + int(40 * (i / 520))
        d.rectangle([0, i, W, i + 8], fill=(c - 20, c, 240))

    # terreno
    d.rectangle([0, 500, W, H], fill=terra)
    d.rectangle([0, 500, W, 512], fill=(min(255, terra[0] + 25), min(255, terra[1] + 25), min(255, terra[2] + 20)))

    base_x = 120 + (idx * 90) % 300

    if tipo == 'fundacao':
        # valas/radier: retângulos de concreto no chão
        for k in range(4):
            x = 120 + k * 250
            d.rectangle([x, 520, x + 190, 560], fill=(190, 190, 188), outline=(120, 120, 118), width=3)
            d.rectangle([x + 10, 560, x + 25, 640], fill=(110, 110, 112))  # arranque de pilar
            d.rectangle([x + 165, 560, x + 180, 640], fill=(110, 110, 112))
    elif tipo == 'estrutura':
        # pórticos metálicos
        for k in range(5):
            x = 100 + k * 230
            d.rectangle([x, 250, x + 16, 560], fill=(90, 100, 115))       # pilar esq
            d.rectangle([x + 180, 250, x + 196, 560], fill=(90, 100, 115))  # pilar dir
            d.polygon([(x - 8, 255), (x + 104, 195), (x + 204, 255)], outline=(70, 80, 95), width=8)  # tesoura
    elif tipo == 'telhado':
        # águas de telhado shingle
        for k in range(3):
            x = 110 + k * 360
            d.polygon([(x, 320), (x + 160, 240), (x + 320, 320)], fill=(80, 70, 62), outline=(50, 44, 40))
            for s in range(6):
                d.line([(x + s * 26, 320 - s * 4), (x + 160, 240)], fill=(60, 52, 46), width=2)
    elif tipo == 'fechamento':
        # painéis de placa cimentícia/régua
        for k in range(6):
            x = 90 + k * 180
            d.rectangle([x, 300, x + 150, 560], fill=(205, 198, 188), outline=(150, 142, 132), width=3)
            for s in range(1, 4):
                d.line([(x, 300 + s * 65), (x + 150, 300 + s * 65)], fill=(170, 162, 150), width=2)
    elif tipo == 'pintura':
        for k in range(5):
            x = 100 + k * 210
            tom = 150 + (k * 12) % 60
            d.rectangle([x, 300, x + 170, 560], fill=(tom, tom - 20, tom - 45), outline=(120, 90, 60), width=3)
    else:
        for k in range(5):
            x = 100 + k * 220
            d.rectangle([x, 320, x + 18, 560], fill=(100, 100, 105))
            d.rectangle([x + 160, 320, x + 178, 560], fill=(100, 100, 105))

    # guindaste/silhueta de canteiro ao fundo (constante)
    d.line([(base_x, 540), (base_x, 150)], fill=(70, 70, 70), width=8)
    d.line([(base_x, 160), (base_x + 260, 160)], fill=(70, 70, 70), width=6)
    d.line([(base_x, 180), (base_x - 90, 160)], fill=(70, 70, 70), width=5)
    d.line([(base_x + 230, 160), (base_x + 230, 240)], fill=(120, 120, 120), width=3)

    # sol
    d.ellipse([1010, 60, 1090, 140], fill=(255, 236, 170))

    # barra de legenda
    d.rectangle([0, H - 96, W, H], fill=(17, 24, 39, 220))
    d.rectangle([0, H - 96, 10, H], fill=(245, 158, 11, 255))
    d.text((34, H - 80), 'Baias Kabod — Fazenda Santa Mônica', font=_font(34), fill=(255, 255, 255))
    d.text((34, H - 38), f'{etapa}', font=_font(26), fill=(203, 213, 225))
    data_f = _font(28)
    tw = d.textlength(dia_str, font=data_f)
    d.text((W - tw - 30, H - 58), dia_str, font=data_f, fill=(245, 158, 11))
    return img


def _b64(img, size, quality):
    im = img if size == (W, H) else img.resize(size)
    buf = io.BytesIO()
    im.save(buf, format='WEBP', quality=quality)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def _etapas_do_dia(rdo, admin_id):
    """Nomes das etapas-raiz ativas no dia (via apontamentos do RDO)."""
    aps = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()
    nomes, vistos = [], set()
    cache = {}
    for ap in aps:
        t = TarefaCronograma.query.get(ap.tarefa_cronograma_id)
        while t and t.tarefa_pai_id:
            t = cache.setdefault(t.tarefa_pai_id, TarefaCronograma.query.get(t.tarefa_pai_id))
        if t and t.nome_tarefa not in vistos:
            vistos.add(t.nome_tarefa)
            nomes.append(t.nome_tarefa)
    return nomes or ['Serviços gerais']


def seed(admin_id=1, codigo='10'):
    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if not obra:
        raise SystemExit(f'Obra codigo={codigo} admin={admin_id} não encontrada')
    rdos = RDO.query.filter_by(obra_id=obra.id, admin_id=admin_id).order_by(RDO.data_relatorio).all()
    if not rdos:
        raise SystemExit('Sem RDOs — rode scripts/seed_rdos_baias.py primeiro')

    rdo_ids = [r.id for r in rdos]
    RDOFoto.query.filter(RDOFoto.rdo_id.in_(rdo_ids), RDOFoto.admin_id == admin_id)\
        .delete(synchronize_session=False)
    db.session.flush()

    n_fotos = 0
    for r in rdos:
        dia_str = r.data_relatorio.strftime('%d/%m/%Y')
        etapas = _etapas_do_dia(r, admin_id)[:2] or ['Serviços gerais']
        for i, etapa in enumerate(etapas):
            img = _cena(etapa, dia_str, i)
            otim = _b64(img, (W, H), 80)
            thumb = _b64(img, (360, 240), 70)
            nome = f'rdo_{r.id}_{i+1}.webp'
            db.session.add(RDOFoto(
                admin_id=admin_id, rdo_id=r.id,
                nome_arquivo=nome, caminho_arquivo=f'uploads/rdo/{nome}',
                nome_original=nome, legenda=f'{etapa} — {dia_str}',
                descricao=f'Registro de campo: {etapa.lower()} em {dia_str}.',
                imagem_otimizada_base64=otim, thumbnail_base64=thumb,
                ordem=i, tamanho_bytes=len(otim)))
            n_fotos += 1

    db.session.commit()
    return {'obra_id': obra.id, 'rdos': len(rdos), 'fotos': n_fotos}


if __name__ == '__main__':
    aid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cod = sys.argv[2] if len(sys.argv) > 2 else '10'
    with app.app_context():
        r = seed(aid, cod)
    print(f"[seed_fotos_rdos_baias] obra_id={r['obra_id']}  RDOs={r['rdos']}  fotos={r['fotos']}")
