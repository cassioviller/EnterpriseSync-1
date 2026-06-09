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
    classificar, texto_norm, derivar_macro, resolver, gerar_sugestoes,
    sugerir_regra_refinada, regra_vencedora, Regra, Lancamento, Contexto,
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


def test_gatilho_extra_exige_segundo_campo_and():
    """Uma Regra com gatilho_extra só casa se o gatilho principal aparece no
    campo-alvo E o gatilho extra aparece no campo extra (ex.: 'aliment' na
    descrição E 'beneficio' no plano)."""
    regra = Regra(
        palavras=["aliment"], categoria_id=5, categoria_nome="Benefício Alimentação",
        campo_alvo="descricao", gatilho_extra=["beneficio"], campo_extra="plano",
        tipo="SAIDA",
    )
    ctx = Contexto(regras=[regra], memoria_exata={})

    # principal + extra presentes → casa
    com = _lanc(descricao="alimentação da equipe", plano="Benefícios")
    assert classificar(com, ctx).categoria_nome == "Benefício Alimentação"

    # principal presente, extra ausente → não casa (Pendente)
    sem = _lanc(descricao="alimentação da equipe", plano="Despesa Operacional")
    assert classificar(sem, ctx).eh_pendente is True


def test_regra_so_casa_lancamento_do_mesmo_tipo():
    """Uma Regra de ENTRADA não classifica um Lançamento de SAÍDA e vice-versa."""
    regra_entrada = _regra(["medicao"], 1, "Receita de Obras", tipo="ENTRADA")
    lanc_saida = _lanc(descricao="medicao da obra", tipo="SAIDA")
    ctx = Contexto(regras=[regra_entrada], memoria_exata={})

    v = classificar(lanc_saida, ctx)

    assert v.eh_pendente is True  # a regra de ENTRADA não vale para a SAÍDA


def test_derivar_macro_da_categoria_nomeada():
    """O macro tipo_categoria é derivado da categoria nomeada (não há cadastro
    de macro separado). Categorias não mapeadas caem em OUTROS."""
    assert derivar_macro("Mão de Obra Direta") == "MAO_OBRA_DIRETA"
    assert derivar_macro("Materiais de Obra") == "MATERIAL"
    assert derivar_macro("Salários e Encargos") == "SALARIO"
    assert derivar_macro("Impostos e Taxas") == "TRIBUTOS"
    assert derivar_macro("Pró-labore e Retirada de Sócios") == "PRO_LABORE"
    assert derivar_macro("Categoria Inexistente") == "OUTROS"


# ── resolver(): classificação + macro + auto/manual num só passo (Fase D) ────

def test_resolver_regra_que_casa_produz_categoria_especifica_e_auto():
    """resolver() classifica o Lançamento e devolve a Resolução pronta para o
    preview: categoria nomeada específica, id da regra, macro derivado e
    eh_manual=False (o cadastro decidiu — vai para a fila automática)."""
    regra = _regra(["maranhao"], 10, "Subempreitada", campo_alvo="fornecedor",
                   prioridade=40)
    lanc = _lanc(descricao="empreita bloco B", fornecedor="Maranhão Construções",
                 tem_obra=True)
    ctx = Contexto(regras=[regra], memoria_exata={})

    r = resolver(lanc, ctx, cat_id_por_nome={})

    assert r.categoria_id == 10
    assert r.categoria_nome == "Subempreitada"
    assert r.tipo_categoria == "MAO_OBRA_DIRETA"   # derivado da categoria nomeada
    assert r.eh_manual is False


def test_resolver_pendente_cai_no_fallback_generico_e_e_manual():
    """Quando nenhuma Regra casa, a SAÍDA cai no fallback genérico 'Outras
    Saídas' (id resolvido do mapa do tenant), macro OUTROS e eh_manual=True —
    vai para a fila de revisão manual (§3 do spec)."""
    ctx = Contexto(regras=[], memoria_exata={})
    lanc = _lanc(descricao="algo que nenhuma regra reconhece", tipo="SAIDA")

    r = resolver(lanc, ctx, cat_id_por_nome={"outras saidas": 99})

    assert r.categoria_nome == "Outras Saídas"
    assert r.categoria_id == 99
    assert r.tipo_categoria == "OUTROS"
    assert r.eh_manual is True


def test_resolver_entrada_pendente_usa_fallback_de_entrada():
    """O fallback genérico respeita o tipo: uma ENTRADA sem Regra cai em
    'Outros Recebimentos', não em 'Outras Saídas'."""
    ctx = Contexto(regras=[], memoria_exata={})
    lanc = _lanc(descricao="deposito nao identificado", tipo="ENTRADA")

    r = resolver(lanc, ctx, cat_id_por_nome={})

    assert r.categoria_nome == "Outros Recebimentos"
    assert r.eh_manual is True


def test_resolver_regra_que_aponta_para_fallback_ainda_e_manual():
    """§3 define manual pelo RESULTADO: se a categoria resolvida é o fallback
    genérico, é revisão manual — mesmo que uma Regra (não a pendência) a tenha
    produzido. O usuário precisa olhar."""
    regra = _regra(["pix"], 99, "Outras Saídas", prioridade=50)
    lanc = _lanc(descricao="pix avulso")
    ctx = Contexto(regras=[regra], memoria_exata={})

    r = resolver(lanc, ctx, cat_id_por_nome={})

    assert r.categoria_nome == "Outras Saídas"
    assert r.eh_manual is True


# ── gerar_sugestoes(): fila por Termo sobre os Pendentes (Fase E) ────────────

def _pend(fornecedor="", descricao="", valor=0.0, tipo="SAIDA"):
    return Lancamento(descricao=descricao, fornecedor=fornecedor, valor=valor, tipo=tipo)


def test_sugestoes_agrega_pendentes_por_termo_do_fornecedor():
    """Dois Pendentes do mesmo fornecedor geram uma Sugestão para o termo,
    com ocorrencias=2 e soma_valor somando os dois lançamentos."""
    pendentes = [
        _pend(fornecedor="Maranhão Construções", valor=1000.0),
        _pend(fornecedor="Maranhão Construções", valor=500.0),
    ]
    sugestoes = gerar_sugestoes(pendentes, regras_existentes=[])

    por_termo = {s.termo: s for s in sugestoes}
    assert "maranhao" in por_termo
    s = por_termo["maranhao"]
    assert s.ocorrencias == 2
    assert s.soma_valor == 1500.0


def test_sugestoes_descartam_stopwords_e_termos_curtos():
    """A fila não deve sugerir ruído: preposições (de, da) e fragmentos de 1–2
    letras não viram Termo. Palavras de conteúdo do fornecedor, sim."""
    pendentes = [_pend(fornecedor="Loja de Tintas", valor=100.0) for _ in range(3)]
    termos = {s.termo for s in gerar_sugestoes(pendentes, regras_existentes=[])}

    assert "de" not in termos            # preposição (stopword)
    assert "tintas" in termos            # conteúdo
    assert "loja" in termos


def test_sugestoes_descarta_termo_ja_coberto_por_regra():
    """Um termo que já é gatilho de uma Regra existente não vira Sugestão (não
    re-sugere o que o cadastro já sabe). Termos vizinhos ainda aparecem."""
    regra = _regra(["leroy"], 50, "Materiais de Obra", campo_alvo="descricao")
    pendentes = [_pend(fornecedor="Leroy Merlin", descricao="compra", valor=300.0)]

    sugestoes = gerar_sugestoes(pendentes, regras_existentes=[regra])
    termos = {s.termo for s in sugestoes}

    assert "leroy" not in termos          # já coberto pela regra
    assert "merlin" in termos             # termo vizinho continua sugerível


def test_sugestoes_ordenadas_por_impacto():
    """A fila prioriza o que mais pesa: ordena por ocorrencias × soma_valor. Um
    termo raro mas caro vence muitos termos baratos."""
    pendentes = (
        [_pend(fornecedor="Alpha", valor=100.0) for _ in range(3)]    # 3 × 100 = 900
        + [_pend(fornecedor="Beta", valor=5000.0)]                    # 1 × 5000 = 5000
    )
    sugestoes = gerar_sugestoes(pendentes, regras_existentes=[])

    assert sugestoes[0].termo == "beta"   # maior impacto vem primeiro
    termos_ordem = [s.termo for s in sugestoes]
    assert termos_ordem.index("beta") < termos_ordem.index("alpha")


# ── Memória Exata + regra refinada: aprendizado (Fase E, Passo 11) ───────────

def test_memoria_exata_reaplica_categoria_em_texto_identico():
    """Texto idêntico (descrição+fornecedor) já corrigido antes reaparece já
    classificado pela Memória Exata, sem Regra e sem ação do usuário (§7.3)."""
    lanc = _lanc(descricao="servico avulso xyz", fornecedor="ACME")
    ctx = Contexto(regras=[], memoria_exata={texto_norm(lanc): (77, "Materiais de Obra")})

    v = classificar(lanc, ctx)

    assert v.categoria_id == 77
    assert v.categoria_nome == "Materiais de Obra"
    assert v.origem_decisao == "memoria_exata"
    assert v.eh_pendente is False


def test_sugerir_regra_refinada_vence_a_regra_do_termo_pelo_contexto():
    """Quando o usuário corrige uma linha cujo contexto contraria a regra do
    Termo (ex.: 'maranhão' em geral é Subempreitada, mas ESTA é compra de
    material), o sistema propõe uma Regra refinada 'maranhão + material →
    Materiais' com prioridade MENOR (vence o conflito). Não persiste nada (§7.3)."""
    conflitante = _regra(["maranhao"], 10, "Subempreitada",
                         campo_alvo="fornecedor", prioridade=40)
    lanc = _lanc(descricao="compra de material hidraulico",
                 fornecedor="Maranhão Construções")

    refinada = sugerir_regra_refinada(
        lanc, categoria_id=20, categoria_nome="Materiais de Obra",
        regra_conflitante=conflitante)

    assert refinada.categoria_id == 20
    assert refinada.categoria_nome == "Materiais de Obra"
    assert refinada.prioridade < conflitante.prioridade   # vence a regra do termo
    assert "maranhao" in refinada.palavras                # mantém o gatilho do termo
    assert "material" in refinada.gatilho_extra           # contexto distintivo
    assert refinada.origem == "usuario"


def test_regra_vencedora_expoe_a_regra_que_classificou():
    """regra_vencedora devolve a Regra que o classificador escolheria (a de menor
    desempate) — usada para detectar o conflito numa Correção. None se nenhuma casa."""
    generica = _regra(["cabo"], 20, "Materiais de Obra", prioridade=90)
    especifica = _regra(["instalacao"], 30, "Serviços Terceirizados", prioridade=10)
    ctx = Contexto(regras=[generica, especifica], memoria_exata={})

    venc = regra_vencedora(_lanc(descricao="instalacao dos cabos"), ctx)
    assert venc is especifica   # menor prioridade vence

    assert regra_vencedora(_lanc(descricao="nada casa aqui"), ctx) is None
