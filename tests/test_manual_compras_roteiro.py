"""O roteiro do manual de compras e o guarda da anotação — 2026-08-18.

Plano: docs/superpowers/plans/2026-08-18-plano-manual-requisicao-compras.md

Dois riscos, e um teste para cada:

  1. **A numeração divergir da imagem.** O manual só é confiável porque a caixa
     desenhada e a legenda numerada saem da MESMA lista. Se um número repetir
     ou pular dentro de uma tela, a legenda deixa de casar com a figura e o
     leitor é mandado para o campo errado.

  2. **O guarda falhar em silêncio.** 📖 `scripts/capturar_manual_ciclo.py:76-79`
     engole a exceção e segue, e o PDF sai montado com a foto velha. O motor
     novo existe para PARAR nesse caso; se ele voltar a engolir, o manual
     volta a envelhecer sem avisar. Este teste é o que segura isso.

Nenhum dos dois precisa de browser nem de banco: exercitam a lista e o guarda.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from anotar_captura import Campo, MarcacaoQuebrada, marcar


class _PaginaFalsa:
    """O mínimo de `page` que `marcar` usa: um `evaluate` que devolve o veredito."""

    def __init__(self, faltando=(), invisiveis=()):
        self.resultado = {'faltando': list(faltando), 'invisiveis': list(invisiveis)}
        self.chamadas = 0

    def evaluate(self, _js, _dados=None):
        self.chamadas += 1
        return self.resultado


def test_seletor_que_nao_casa_levanta_excecao():
    """O guarda. Se este teste passar a falhar, o manual voltou a poder mentir."""
    pagina = _PaginaFalsa(faltando=['[name="campo_que_sumiu"]'])

    with pytest.raises(MarcacaoQuebrada) as erro:
        marcar(pagina, [Campo(1, '[name="campo_que_sumiu"]', 'Qualquer')])

    assert 'campo_que_sumiu' in str(erro.value), 'o erro tem de dizer QUAL seletor'


def test_campo_invisivel_tambem_e_falha():
    """Existir no HTML não basta: caixa de 0x0 desenha um retângulo degenerado
    num canto da imagem, que é pior que caixa nenhuma porque parece de propósito."""
    pagina = _PaginaFalsa(invisiveis=['[name="escondido"]'])

    with pytest.raises(MarcacaoQuebrada) as erro:
        marcar(pagina, [Campo(1, '[name="escondido"]', 'Qualquer')])

    assert 'invisí' in str(erro.value) or 'invis' in str(erro.value)


def test_tela_sem_campos_nao_chama_o_navegador():
    pagina = _PaginaFalsa()
    marcar(pagina, [])
    assert pagina.chamadas == 0


def test_tudo_casou_nao_levanta():
    pagina = _PaginaFalsa()
    marcar(pagina, [Campo(1, 'input', 'Um'), Campo(2, 'select', 'Dois')])
    assert pagina.chamadas == 1


def _roteiro():
    from roteiro_manual_compras import montar
    # ids fictícios: `montar` não toca no banco, só formata a rota.
    return montar({'rc_rascunho': 1, 'rc_aguardando': 2, 'rc_rejeitada': 3,
                   'rc_aprovada': 4, 'ped_a': 5, 'ped_b': 6, 'ped_c': 7,
                   'conta_c': 8})


def test_numeracao_e_unica_e_contigua_em_cada_tela():
    for tela in _roteiro():
        numeros = [c.numero for c in tela.campos]
        assert len(numeros) == len(set(numeros)), \
            f'{tela.slug}: número repetido — a legenda deixaria de casar com a figura'
        assert numeros == list(range(1, len(numeros) + 1)), \
            f'{tela.slug}: numeração com buraco ou fora de ordem: {numeros}'


def test_os_slugs_sao_unicos_e_ordenados():
    """O slug é o nome do arquivo E a ordem do PDF. Repetido, uma captura
    sobrescreveria a outra em silêncio."""
    slugs = [t.slug for t in _roteiro()]
    assert len(slugs) == len(set(slugs))
    assert slugs == sorted(slugs), 'a ordem do roteiro é a ordem do manual'


def test_toda_tela_tem_papel_conhecido():
    from seed_manual_compras import PESSOAS
    validos = {chave for chave, *_ in PESSOAS} | {'anon'}
    for tela in _roteiro():
        assert tela.papel in validos, \
            f'{tela.slug}: papel "{tela.papel}" não existe no cenário semeado'


def test_toda_tela_diz_o_que_a_pessoa_esta_fazendo():
    for tela in _roteiro():
        assert tela.titulo and tela.resumo, f'{tela.slug} sem título ou resumo'
        assert tela.rota.startswith('/'), f'{tela.slug}: rota estranha {tela.rota!r}'


def test_campo_obrigatorio_sem_nota_ainda_diz_algo_na_legenda():
    """A legenda nunca sai vazia: sem nota, o obrigatório vira 'Obrigatório.'."""
    for tela in _roteiro():
        for campo in tela.campos:
            assert campo.rotulo, f'{tela.slug}/{campo.numero} sem rótulo'
