#!/usr/bin/env python3
"""Motor de captura anotada — desenha as caixas numeradas ANTES do screenshot.

A decisão que este arquivo implementa está no plano
`docs/superpowers/plans/2026-08-18-plano-manual-requisicao-compras.md`:

    As caixas são desenhadas no DOM, pelo Playwright, e não por cima do PNG
    depois.

Cada marcação declara um SELETOR (`[name="obra_id"]`), não um par de
coordenadas. O motor mede o elemento e injeta um contorno com um badge numerado
ancorado nele. Três consequências:

  * sobrevive a mudança de CSS — o contorno é medido do campo, todo vez;
  * é independente de resolução — a anotação é CSS, não pixel colado;
  * o número da caixa e o número da legenda são O MESMO DADO, porque os dois
    saem da mesma lista no roteiro. Não existem duas listas para divergir.

E o guarda que justifica o resto: **seletor que não casa levanta exceção**.
📖 `scripts/capturar_manual_ciclo.py:76-79` (a captura de 22/07) faz o oposto —
engole a exceção, imprime "ERRO em ..." e segue. Como o gerador do PDF lê a
pasta por nome de arquivo, uma captura que falha deixa o PNG velho no disco e o
manual sai montado com a tela errada, sem um aviso. Um manual que aponta a seta
para o campo errado é pior que manual nenhum.
"""
from dataclasses import dataclass, field as _field


# Paleta: laranja de alto contraste sobre a interface azul/cinza do SIGE, e
# legível também impresso em preto e branco (é manual de obra; vai ser impresso).
COR = '#e8590c'
COR_TEXTO = '#ffffff'


@dataclass
class Campo:
    """Um campo marcado na tela.

    numero      — o da caixa E o da legenda. Fonte única.
    seletor     — CSS. Se não casar, a captura PARA.
    rotulo      — o nome que aparece na legenda do manual.
    obrigatorio — vira o asterisco e a coluna "obrigatório?" da legenda.
    nota        — a frase que evita o erro comum. Opcional, mas é onde mora
                  metade do valor do manual.
    """
    numero: int
    seletor: str
    rotulo: str
    obrigatorio: bool = False
    nota: str = ''


@dataclass
class Tela:
    slug: str
    titulo: str
    papel: str            # qual pessoa loga para ver esta tela
    rota: str             # já com os ids resolvidos
    resumo: str           # o que a pessoa está tentando fazer aqui
    campos: list = _field(default_factory=list)
    depois: str = ''      # o que acontece ao confirmar
    atencao: str = ''     # o erro comum / a pegadinha
    # Seletor do pedaço a fotografar. Sem ele, a página inteira. Serve para
    # tela que é um cartão no meio de uma área vazia (o login): fotografada
    # inteira, ela vira um retângulo escuro com as caixas ilegíveis no PDF.
    recorte: str = ''


_JS_MARCAR = """
(marcacoes) => {
  const COR = '%COR%', COR_TEXTO = '%COR_TEXTO%';
  document.querySelectorAll('.sige-marcacao').forEach(e => e.remove());
  const faltando = [], invisiveis = [];
  for (const m of marcacoes) {
    const el = document.querySelector(m.seletor);
    if (!el) { faltando.push(m.seletor); continue; }
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) { invisiveis.push(m.seletor); continue; }
    const topo = r.top + window.scrollY, esq = r.left + window.scrollX;

    const caixa = document.createElement('div');
    caixa.className = 'sige-marcacao';
    Object.assign(caixa.style, {
      position: 'absolute', left: (esq - 4) + 'px', top: (topo - 4) + 'px',
      width: (r.width + 8) + 'px', height: (r.height + 8) + 'px',
      border: '3px solid ' + COR, borderRadius: '6px',
      pointerEvents: 'none', zIndex: 2147483000,
      boxShadow: '0 0 0 2px rgba(255,255,255,.9)',
    });
    document.body.appendChild(caixa);

    const badge = document.createElement('div');
    badge.className = 'sige-marcacao';
    badge.textContent = m.numero;
    Object.assign(badge.style, {
      position: 'absolute', left: (esq - 20) + 'px', top: (topo - 16) + 'px',
      width: '28px', height: '28px', lineHeight: '28px', textAlign: 'center',
      background: COR, color: COR_TEXTO, borderRadius: '50%',
      font: '700 15px/28px system-ui, sans-serif',
      border: '2px solid #fff', boxShadow: '0 1px 4px rgba(0,0,0,.4)',
      pointerEvents: 'none', zIndex: 2147483001,
    });
    document.body.appendChild(badge);
  }
  return {faltando, invisiveis};
}
""".replace('%COR%', COR).replace('%COR_TEXTO%', COR_TEXTO)


class MarcacaoQuebrada(RuntimeError):
    """Um seletor do roteiro não casa mais com a tela."""


def marcar(page, campos):
    """Desenha as caixas. Levanta MarcacaoQuebrada se algum seletor falhar."""
    if not campos:
        return
    dados = [{'seletor': c.seletor, 'numero': c.numero} for c in campos]
    r = page.evaluate(_JS_MARCAR, dados)
    problemas = []
    if r['faltando']:
        problemas.append('não existem na página: ' + ', '.join(r['faltando']))
    if r['invisiveis']:
        problemas.append('existem mas estão invisíveis (0x0): '
                         + ', '.join(r['invisiveis']))
    if problemas:
        raise MarcacaoQuebrada('; '.join(problemas))


def limpar(page):
    page.evaluate("() => document.querySelectorAll('.sige-marcacao').forEach(e => e.remove())")
