"""
Fase B (TDD) — Classificador profundo de Fluxo de Caixa.

Spec §5: o classificador devolve um VEREDITO (não "categoria ou None"). A ordem
de resolução (Regra de Classificação → Memória Exata → Pendente), o desempate por
prioridade e a decisão auto/Pendente vivem DENTRO do módulo.

Módulo PURO — sem DB, sem Flask. Testa o veredito (comportamento observável),
não as funções internas de matching.

Linguagem: CONTEXT.md (Regra de Classificação, Gatilho, Prioridade, Pendente,
Memória Exata, Veredito).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.classificador_cadastro import (
    classificar, texto_norm, derivar_macro, Regra, Lancamento, Contexto,
)


def _regra(palavras, cat_id, cat_nome, campo_alvo="qualquer", excecoes=(),
           condicao_obra="indiferente", prioridade=50, origem="usuario", tipo="SAIDA"):
    return Regra(
        palavras=list(palavras), categoria_id=cat_id, categoria_nome=cat_nome,
        campo_alvo=campo_alvo, excecoes=list(excecoes), condicao_obra=condicao_obra,
        prioridade=prioridade, origem=origem, tipo=tipo,
    )


def _lanc(descricao="", fornecedor="", plano="", tem_obra=False, tipo="SAIDA"):
    return Lancamento(descricao=descricao, fornecedor=fornecedor, plano=plano,
                      tem_obra=tem_obra, tipo=tipo)


def test_regra_que_casa_o_gatilho_produz_veredito_com_categoria():
    """Uma Regra cujo gatilho casa o fornecedor classifica o Lançamento: o
    Veredito traz a categoria, origem 'regra' e não é Pendente."""
    regra = _regra(["maranhao"], 10, "Subempreitada", campo_alvo="fornecedor",
                   prioridade=40)
    lanc = _lanc(descricao="empreita bloco B", fornecedor="Maranhão Construções",
                 tem_obra=True)
    ctx = Contexto(regras=[regra], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.categoria_id == 10
    assert v.categoria_nome == "Subempreitada"
    assert v.origem_decisao == "regra"
    assert v.eh_pendente is False


def test_menor_prioridade_vence_mesmo_vindo_depois_na_lista():
    """Quando duas Regras casam o mesmo Lançamento, a de menor prioridade
    (mais específica) vence — independente da ordem na lista."""
    generica = _regra(["cabo"], 20, "Materiais de Obra", prioridade=90)
    especifica = _regra(["instalacao"], 30, "Serviços Terceirizados", prioridade=10)
    lanc = _lanc(descricao="instalacao dos cabos do quadro")
    # genérica primeiro na lista, mas a específica (prioridade menor) deve vencer
    ctx = Contexto(regras=[generica, especifica], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.categoria_id == 30
    assert v.categoria_nome == "Serviços Terceirizados"


def test_excecao_anula_a_regra():
    """Se uma palavra de exceção aparece no texto, a Regra não casa.
    Ex.: 'salário' classifica Salários, EXCETO quando há 'diária'."""
    regra = _regra(["salario"], 40, "Salários e Encargos", excecoes=["diaria"])
    lanc = _lanc(descricao="salario referente a 10 dias de diaria")
    ctx = Contexto(regras=[regra], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.eh_pendente is True
    assert v.origem_decisao == "fallback"


def test_condicao_de_obra_decide_entre_duas_regras_do_mesmo_gatilho():
    """O mesmo gatilho leva a categorias diferentes conforme a obra:
    com obra → custo direto; sem obra → benefício administrativo."""
    sem_obra = _regra(["vale transporte"], 50, "Benefício Transporte",
                      condicao_obra="sem_obra")
    com_obra = _regra(["vale transporte"], 60, "Transporte de Obra",
                      condicao_obra="com_obra")
    lanc = _lanc(descricao="vale transporte equipe", tem_obra=True)
    # sem_obra primeiro na lista — não pode vencer porque o Lançamento TEM obra
    ctx = Contexto(regras=[sem_obra, com_obra], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.categoria_nome == "Transporte de Obra"


def test_memoria_exata_classifica_quando_nenhuma_regra_casa():
    """Sem Regra que case, um texto idêntico já corrigido antes (Memória Exata)
    classifica o Lançamento — origem 'memoria_exata', não Pendente."""
    lanc = _lanc(descricao="compra material", fornecedor="Loja Maranhão")
    chave = texto_norm(lanc)
    ctx = Contexto(regras=[], memoria_exata={chave: (70, "Materiais de Obra")})

    v = classificar(lanc, ctx)

    assert v.categoria_id == 70
    assert v.categoria_nome == "Materiais de Obra"
    assert v.origem_decisao == "memoria_exata"
    assert v.eh_pendente is False


def test_lancamento_sem_regra_nem_memoria_e_pendente():
    """Sem Regra e sem Memória Exata, o Lançamento é Pendente de Classificação."""
    lanc = _lanc(descricao="algo totalmente novo", fornecedor="Fornecedor X")
    ctx = Contexto(regras=[], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.eh_pendente is True
    assert v.categoria_id is None
    assert v.origem_decisao == "fallback"


def test_empate_de_prioridade_regra_do_usuario_vence_a_do_sistema():
    """Com prioridade igual, a Regra criada pelo usuário vence a do sistema."""
    do_sistema = _regra(["pix"], 80, "Outras Saídas", prioridade=50, origem="sistema")
    do_usuario = _regra(["pix"], 81, "Subempreitada", prioridade=50, origem="usuario")
    lanc = _lanc(descricao="pix para fornecedor")
    ctx = Contexto(regras=[do_sistema, do_usuario], memoria_exata={})

    v = classificar(lanc, ctx)

    assert v.categoria_nome == "Subempreitada"


def test_derivar_macro_da_categoria_nomeada():
    """O macro tipo_categoria é derivado da categoria nomeada (não há cadastro
    de macro separado). Categorias não mapeadas caem em OUTROS."""
    assert derivar_macro("Mão de Obra Direta") == "MAO_OBRA_DIRETA"
    assert derivar_macro("Materiais de Obra") == "MATERIAL"
    assert derivar_macro("Salários e Encargos") == "SALARIO"
    assert derivar_macro("Impostos e Taxas") == "TRIBUTOS"
    assert derivar_macro("Pró-labore e Retirada de Sócios") == "PRO_LABORE"
    assert derivar_macro("Categoria Inexistente") == "OUTROS"
