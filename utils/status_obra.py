"""Fase 0.6 / D5 — vocabulário canônico do status da Obra.

`Obra.status` é `db.String(20)` sem constraint (`models.py:257`). Até 21/07/2026
duas grafias do mesmo estado circulavam: `'Em andamento'` (default do modelo,
contador e filtro da listagem) e `'Em Andamento'` (o `<select>` do formulário,
vindo de `_SLUG_DEFAULTS['obra_status']`). Como `views/obras.py:83` filtra por
igualdade exata, as 53 obras gravadas com a segunda grafia sumiam da tela.

Este módulo é a única fonte da verdade do vocabulário. A convergência acontece
na **escrita** — `@validates('status')` em `models.Obra` — para que todo caminho
de gravação passe por aqui: formulário, `event_manager.py`, seeds, importadores
de `.mpp` e de planilha.

A grafia canônica é a do default do modelo, não a do formulário: 7.926 das
7.979 obras já a usavam quando a divergência foi medida.
"""
import unicodedata

# Ordem = ordem de exibição nos `<select>`.
#
# Fase 2: 'Planejamento' entrou aqui porque a máquina de estados passa a fazer
# a obra NASCER nele (`EstadoObra.PLANEJAMENTO`), e o write-through grava o
# rótulo neste campo. Deixá-lo fora faria o estado inicial de toda obra nova
# ser considerado não-canônico pelo módulo que governa o vocabulário.
#
# Não entrou em `services.dropdown_service._SLUG_DEFAULTS['obra_status']` de
# propósito: aquele é o `<select>` do formulário de obra, e a Fase 2 tira do
# formulário a capacidade de mudar estado — quem transiciona é
# `services.obra_estado.transitar()`. O filtro da listagem
# (`templates/obras_moderno.html:619`) já oferecia 'Planejamento'.
STATUS_OBRA_CANONICOS: tuple[str, ...] = (
    'Planejamento',
    'Em andamento',
    'Pausada',
    'Concluída',
    'Cancelada',
)


def _chave(valor: str) -> str:
    """Reduz a variação ortográfica a uma chave comparável.

    Mesma técnica do `_norm` local de `views/obras.py:971`, que existia só
    para decidir o disparo de `obra.concluida`.
    """
    valor = (valor or '').strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFKD', valor)
        if not unicodedata.combining(c)
    )


def chave_status(valor: str | None) -> str:
    """Chave comparável de um texto de status — sem acento, sem caixa.

    Exposta para `services/obra_estado.py` (Fase 2), que precisa da MESMA
    normalização para traduzir texto legado em `EstadoObra`. Este módulo já era
    a segunda implementação da técnica — a primeira foi o `_norm` local de
    `views/obras.py:971`, que ele substituiu. Uma terceira cópia dentro de
    `obra_estado` tornaria possível as duas divergirem justamente no vocabulário
    que este arquivo existe para manter único.
    """
    return _chave(valor)


_POR_CHAVE = {_chave(s): s for s in STATUS_OBRA_CANONICOS}


def normalizar_status_obra(valor: str | None) -> str | None:
    """Devolve a grafia canônica de `valor`, ou o próprio `valor` sem espaços.

    Valor desconhecido **não** é descartado nem substituído por um default: ele
    volta preservado. Engolir o desconhecido em silêncio é exatamente o defeito
    de `services/cronograma_proposta.py:532`, e aqui produziria uma obra com
    status diferente do que o usuário escolheu, sem aviso.

    `None` volta `None` — deixar o default da coluna agir é responsabilidade do
    SQLAlchemy, não desta função.
    """
    if valor is None:
        return None
    return _POR_CHAVE.get(_chave(valor), valor.strip())


def eh_status_canonico(valor: str | None) -> bool:
    return valor in STATUS_OBRA_CANONICOS
