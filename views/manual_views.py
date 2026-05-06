"""Blueprint do Manual do Usuário (Task #16).

Renderiza o conteúdo de ``manual/*.md`` como página única dentro do sistema,
com sumário lateral, oferece um endpoint de download (HTML imprimível, pronto
para "Salvar como PDF" pelo navegador) e serve as imagens em
``manual/imagens/`` via ``send_from_directory``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List

import markdown as md
from flask import Blueprint, abort, render_template, send_from_directory
from flask_login import login_required

manual_bp = Blueprint("manual", __name__, url_prefix="/manual")

MANUAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manual")
IMAGENS_DIR = os.path.join(MANUAL_DIR, "imagens")

PLACEHOLDER_RE = re.compile(r"capítulo em constru[cç][aã]o", re.IGNORECASE)


@dataclass
class Capitulo:
    slug: str          # "20_dashboard"
    anchor: str        # "cap-20-dashboard"
    titulo: str        # "Dashboard"
    html: str          # corpo HTML renderizado (sem o H1)
    em_construcao: bool


def _md_renderer() -> "md.Markdown":
    return md.Markdown(
        extensions=["extra", "tables", "sane_lists", "toc"],
        output_format="html5",
    )


def _carregar_capitulos() -> List[Capitulo]:
    if not os.path.isdir(MANUAL_DIR):
        return []
    arquivos = sorted(
        f for f in os.listdir(MANUAL_DIR)
        if f.endswith(".md") and not f.startswith(".")
    )
    capitulos: List[Capitulo] = []
    for nome in arquivos:
        caminho = os.path.join(MANUAL_DIR, nome)
        try:
            with open(caminho, "r", encoding="utf-8") as fh:
                texto = fh.read()
        except OSError:
            continue
        slug = nome[:-3]
        # extrai o primeiro H1 como título do capítulo
        titulo = slug
        corpo = texto
        m = re.match(r"\s*#\s+(.+?)\s*\n", texto)
        if m:
            titulo = m.group(1).strip()
            corpo = texto[m.end():]
        renderer = _md_renderer()
        html = renderer.convert(corpo)
        anchor = "cap-" + re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        capitulos.append(Capitulo(
            slug=slug,
            anchor=anchor,
            titulo=titulo,
            html=html,
            em_construcao=bool(PLACEHOLDER_RE.search(texto)),
        ))
    return capitulos


@manual_bp.route("/")
@login_required
def index():
    capitulos = _carregar_capitulos()
    return render_template("manual/index.html", capitulos=capitulos)


@manual_bp.route("/download")
@login_required
def download():
    """HTML imprimível — o usuário usa "Salvar como PDF" do próprio navegador."""
    capitulos = _carregar_capitulos()
    return render_template("manual/print.html", capitulos=capitulos)


@manual_bp.route("/imagens/<path:filename>")
@login_required
def imagens(filename):
    if not os.path.isdir(IMAGENS_DIR):
        abort(404)
    return send_from_directory(IMAGENS_DIR, filename)
