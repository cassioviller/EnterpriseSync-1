"""
Task #191 — Tema do Sistema (refresh visual SaaS).

Define os presets disponíveis e ajuda a calcular as 4 cores do tema
(primária, secundária, header, fundo) que são injetadas como CSS
variables no template base.

Cada preset é uma tupla: (id, label, primaria, secundaria, header, fundo).
"""

from __future__ import annotations

import re
from typing import Dict, Optional


# ----------------------------------------------------------------------
# Presets disponíveis
# ----------------------------------------------------------------------

PRESETS: Dict[str, Dict[str, str]] = {
    # Preset padrão — visual SaaS corporativo (azul profundo)
    "azul_profundo": {
        "label": "Azul Profundo SaaS (Padrão)",
        "descricao": "Visual SaaS corporativo limpo, header escuro elegante.",
        "cor_primaria": "#2563eb",
        "cor_secundaria": "#64748b",
        "cor_header_nav": "#1e293b",
        "cor_fundo_app": "#f8fafc",
    },
    # Preset alternativo — verde construção (mantém identidade SIGE legado)
    "verde_construcao": {
        "label": "Verde Construção",
        "descricao": "Identidade clássica SIGE — verde institucional.",
        "cor_primaria": "#198754",
        "cor_secundaria": "#6c757d",
        "cor_header_nav": "#157347",
        "cor_fundo_app": "#f6f8f7",
    },
    # Preset alternativo — grafite premium (header preto, primária roxa)
    "grafite_premium": {
        "label": "Grafite Premium",
        "descricao": "Tom escuro sofisticado com toque roxo de destaque.",
        "cor_primaria": "#7c3aed",
        "cor_secundaria": "#475569",
        "cor_header_nav": "#0f172a",
        "cor_fundo_app": "#f5f6fa",
    },
}

PRESET_PADRAO = "azul_profundo"

# Cores de fallback quando não há configuração nenhuma (mesmo do preset padrão)
TEMA_FALLBACK = {
    "cor_primaria": PRESETS[PRESET_PADRAO]["cor_primaria"],
    "cor_secundaria": PRESETS[PRESET_PADRAO]["cor_secundaria"],
    "cor_header_nav": PRESETS[PRESET_PADRAO]["cor_header_nav"],
    "cor_fundo_app": PRESETS[PRESET_PADRAO]["cor_fundo_app"],
    "tema_preset": PRESET_PADRAO,
}


# ----------------------------------------------------------------------
# Validações e helpers de cor
# ----------------------------------------------------------------------

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_hex_color(valor: Optional[str]) -> bool:
    """Aceita apenas cores hex no formato '#RRGGBB'."""
    if not valor or not isinstance(valor, str):
        return False
    return bool(_HEX_RE.match(valor.strip()))


def normaliza_hex(valor: Optional[str], fallback: str) -> str:
    """Retorna a cor em lowercase ou o fallback se inválida."""
    if is_hex_color(valor):
        return valor.strip().lower()
    return fallback


def _luminancia(hex_color: str) -> float:
    """Luminância relativa (0..1) — usada para escolher texto preto/branco."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def cor_contraste(hex_color: str) -> str:
    """Retorna '#ffffff' ou '#0f172a' conforme contraste sobre o fundo."""
    try:
        return "#ffffff" if _luminancia(hex_color) < 0.5 else "#0f172a"
    except Exception:
        return "#ffffff"


# ----------------------------------------------------------------------
# API pública
# ----------------------------------------------------------------------

def listar_presets() -> Dict[str, Dict[str, str]]:
    """Retorna o dicionário completo de presets para uso na UI."""
    return PRESETS


def get_tema_da_empresa(config_empresa) -> Dict[str, str]:
    """
    Resolve o tema efetivo a partir do `ConfiguracaoEmpresa` do tenant.

    Sempre retorna 4 cores válidas + 2 cores de contraste pré-calculadas.
    Se a empresa não tem config, cai no preset padrão.
    """
    if config_empresa is None:
        base = dict(TEMA_FALLBACK)
    else:
        base = {
            "cor_primaria": normaliza_hex(
                getattr(config_empresa, "cor_primaria", None),
                TEMA_FALLBACK["cor_primaria"],
            ),
            "cor_secundaria": normaliza_hex(
                getattr(config_empresa, "cor_secundaria", None),
                TEMA_FALLBACK["cor_secundaria"],
            ),
            "cor_header_nav": normaliza_hex(
                getattr(config_empresa, "cor_header_nav", None),
                TEMA_FALLBACK["cor_header_nav"],
            ),
            "cor_fundo_app": normaliza_hex(
                getattr(config_empresa, "cor_fundo_app", None),
                TEMA_FALLBACK["cor_fundo_app"],
            ),
            "tema_preset": (getattr(config_empresa, "tema_preset", None)
                            or PRESET_PADRAO),
        }

    base["cor_texto_header"] = cor_contraste(base["cor_header_nav"])
    base["cor_texto_primaria"] = cor_contraste(base["cor_primaria"])
    return base


def aplicar_preset(config_empresa, preset_id: str) -> bool:
    """Sobrescreve as 4 cores e o `tema_preset` no objeto `config_empresa`.

    Retorna True se aplicou, False se preset inválido. Não faz commit:
    cabe ao chamador persistir.
    """
    preset = PRESETS.get(preset_id)
    if not preset:
        return False

    config_empresa.cor_primaria = preset["cor_primaria"]
    config_empresa.cor_secundaria = preset["cor_secundaria"]
    config_empresa.cor_header_nav = preset["cor_header_nav"]
    config_empresa.cor_fundo_app = preset["cor_fundo_app"]
    config_empresa.tema_preset = preset_id
    return True
