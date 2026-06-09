"""
Classificador profundo de Fluxo de Caixa (cadastro por tenant).

Módulo PURO — sem DB, sem Flask. Recebe as Regras de Classificação e a Memória
Exata já carregadas (value objects) e devolve um Veredito por Lançamento.

A ordem de resolução (Regra → Memória Exata → Pendente), o desempate por
prioridade e a decisão auto/Pendente vivem AQUI dentro (locality) — quem chama
(`processar()`, endpoints do loop ao vivo) só consome o Veredito.

Linguagem: CONTEXT.md (Regra de Classificação, Gatilho, Prioridade, Pendente de
Classificação, Memória Exata). Ver ADR-0002 e spec 2026-06-09 §5.
"""
import unicodedata as _ud
from dataclasses import dataclass, field
from typing import Optional


# ── Value objects ───────────────────────────────────────────────────────────

@dataclass
class Regra:
    """Regra de Classificação carregada (gatilho → categoria)."""
    palavras: list          # gatilho — casa se QUALQUER uma aparecer
    categoria_id: int
    categoria_nome: str
    campo_alvo: str = "qualquer"        # qualquer | descricao | fornecedor | plano
    excecoes: list = field(default_factory=list)
    condicao_obra: str = "indiferente"  # indiferente | com_obra | sem_obra
    prioridade: int = 50
    origem: str = "usuario"             # sistema | usuario
    tipo: str = "SAIDA"
    # Condição extra (AND): se preenchida, alguma palavra de gatilho_extra também
    # precisa aparecer em campo_extra. Expressa regras "A num campo E B em outro".
    gatilho_extra: list = field(default_factory=list)
    campo_extra: str = "qualquer"


@dataclass
class Lancamento:
    """Lançamento a classificar (entrada ou saída)."""
    descricao: str = ""
    fornecedor: str = ""
    plano: str = ""
    tem_obra: bool = False
    tipo: str = "SAIDA"
    valor: float = 0.0   # usado pela fila de sugestões (soma_valor); ignorado no matching


@dataclass
class Contexto:
    """Tudo que o classificador precisa, já carregado em memória."""
    regras: list = field(default_factory=list)
    memoria_exata: dict = field(default_factory=dict)  # texto_norm → (cat_id, cat_nome)


@dataclass
class Veredito:
    """Resultado da classificação de um Lançamento."""
    categoria_id: Optional[int]
    categoria_nome: Optional[str]
    origem_decisao: str   # regra | memoria_exata | fallback
    eh_pendente: bool


# ── Normalização (local — evita acoplar à importacao_excel) ─────────────────

def _norm(texto) -> str:
    s = str(texto or "").lower()
    s = _ud.normalize("NFD", s)
    s = "".join(c for c in s if _ud.category(c) != "Mn")
    return s.strip()


def _norm_kw(palavra) -> str:
    """Normaliza um gatilho/exceção PRESERVANDO espaços de fronteira — gatilhos
    como ' inss', 'art ', ' vt ' dependem do espaço para não casar dentro de
    palavras (ex.: 'art ' não pode casar em 'martins'). Paridade com o legado,
    que compara o keyword literal contra o blob normalizado."""
    s = str(palavra or "").lower()
    s = _ud.normalize("NFD", s)
    return "".join(c for c in s if _ud.category(c) != "Mn")


# ── Núcleo ──────────────────────────────────────────────────────────────────

# ── Macro derivado da categoria nomeada (substitui o cadastro de macro) ─────
# Mapeia cada CategoriaFluxoCaixa nomeada → tipo_categoria macro (GestaoCustoPai).
_MACRO_POR_CATEGORIA = {
    # Custo direto de obra
    "Mão de Obra Direta": "MAO_OBRA_DIRETA",
    "Subempreitada": "MAO_OBRA_DIRETA",
    "Serviços Terceirizados de Obra": "MAO_OBRA_DIRETA",
    "Materiais de Obra": "MATERIAL",
    "Ferramentas e Consumíveis": "MATERIAL",
    "EPIs e Segurança do Trabalho": "MATERIAL",
    "Locação de Equipamentos": "OUTROS",
    "Fretes e Entregas": "TRANSPORTE",
    "Combustível e Frota": "TRANSPORTE",
    "Manutenção de Frota e Equipamentos": "TRANSPORTE",
    "Transporte de Obra": "TRANSPORTE",
    "Alimentação de Obra": "ALIMENTACAO",
    "Hospedagem de Obra": "OUTROS",
    "Taxas de Obra / ART / Licenças": "TRIBUTOS",
    # Benefícios
    "Benefício Alimentação": "ALIMENTACAO",
    "Benefício Transporte": "TRANSPORTE",
    # Pessoal
    "Salários e Encargos": "SALARIO",
    "Pró-labore e Retirada de Sócios": "PRO_LABORE",
    "Reembolsos a Funcionários": "OUTROS",
    # Tributos / financeiro
    "Impostos e Taxas": "TRIBUTOS",
    "Despesas Bancárias": "OUTROS",
    "Despesa Financeira": "OUTROS",
    "Empréstimos e Financiamentos": "OUTROS",
    # Administrativo / utilities
    "Água": "ALUGUEL_UTILITIES",
    "Luz / Energia Elétrica": "ALUGUEL_UTILITIES",
    "Internet": "ALUGUEL_UTILITIES",
    "Telefone": "ALUGUEL_UTILITIES",
    "Sistemas e Assinaturas": "ALUGUEL_UTILITIES",
    "Aluguel e Locação Administrativa": "ALUGUEL_UTILITIES",
    "Contabilidade e Jurídico": "OUTROS",
    "Marketing e Vendas": "OUTROS",
    "Material de Escritório": "OUTROS",
    "Treinamentos e Capacitações": "OUTROS",
    "Manutenção Predial e Escritório": "OUTROS",
    "Outras Saídas": "OUTROS",
    # Entradas
    "Receita de Obras": "RECEITA_SERVICO",
    "Receita de Serviços": "RECEITA_SERVICO",
    "Adiantamento de Clientes": "RECEITA_SERVICO",
    "Reembolso de Cliente": "OUTROS",
    "Aporte de Sócios": "OUTROS",
    "Empréstimos Recebidos": "OUTROS",
    "Rendimentos Financeiros": "OUTROS",
    "Venda de Ativos": "OUTROS",
    "Outros Recebimentos": "OUTROS",
}
# Índice normalizado (tolerante a acento/caixa), construído no load do módulo
_MACRO_NORM = {_norm(k): v for k, v in _MACRO_POR_CATEGORIA.items()}


def derivar_macro(categoria_nome) -> str:
    """Deriva o tipo_categoria macro a partir da categoria nomeada.
    Categorias não mapeadas → 'OUTROS'."""
    return _MACRO_NORM.get(_norm(categoria_nome), "OUTROS")


def texto_norm(lanc: Lancamento) -> str:
    """Chave da Memória Exata: descrição + fornecedor normalizados.
    Usada tanto na classificação quanto ao registrar uma Correção."""
    return _norm(f"{lanc.descricao} {lanc.fornecedor}")


def _campos_busca(lanc: Lancamento) -> dict:
    return {
        "descricao": _norm(lanc.descricao),
        "fornecedor": _norm(lanc.fornecedor),
        "plano": _norm(lanc.plano),
    }


def _condicao_obra_ok(regra: Regra, tem_obra: bool) -> bool:
    if regra.condicao_obra == "com_obra":
        return tem_obra
    if regra.condicao_obra == "sem_obra":
        return not tem_obra
    return True  # indiferente


def _alvo(campo: str, campos: dict) -> str:
    if campo == "qualquer":
        # Blob com espaços nas bordas e entre campos (gatilhos como ' inss', ' vt '
        # dependem do espaço de fronteira — paridade com o classificador legado).
        return f" {campos['descricao']} {campos['plano']} {campos['fornecedor']} "
    return campos.get(campo, "")


def _alvo_da_regra(regra: Regra, campos: dict) -> str:
    return _alvo(regra.campo_alvo, campos)


def _regra_casa(regra: Regra, campos: dict, tem_obra: bool) -> bool:
    """A regra casa se: a condição de obra é satisfeita E alguma palavra do
    gatilho aparece no(s) campo(s) alvo E nenhuma exceção está presente."""
    if not _condicao_obra_ok(regra, tem_obra):
        return False
    alvo = _alvo_da_regra(regra, campos)
    if any(_norm_kw(e) in alvo for e in regra.excecoes):
        return False
    if not any(_norm_kw(p) in alvo for p in regra.palavras):
        return False
    # Condição extra (AND) em outro campo
    if regra.gatilho_extra:
        alvo_extra = _alvo(regra.campo_extra, campos)
        if not any(_norm_kw(p) in alvo_extra for p in regra.gatilho_extra):
            return False
    return True


def _maior_match(regra: Regra, campos: dict) -> int:
    """Tamanho da palavra do gatilho mais longa que casou (especificidade)."""
    alvo = _alvo_da_regra(regra, campos)
    return max((len(_norm_kw(p)) for p in regra.palavras if _norm_kw(p) in alvo), default=0)


def _chave_desempate(regra: Regra, campos: dict) -> tuple:
    """Ordena candidatas — menor tupla vence. Em ordem de critério:
    1. menor prioridade; 2. usuário antes de sistema; 3. campo específico antes
    de 'qualquer'; 4. match mais longo (especificidade)."""
    origem_rank = 0 if regra.origem == "usuario" else 1
    campo_rank = 1 if regra.campo_alvo == "qualquer" else 0
    return (regra.prioridade, origem_rank, campo_rank, -_maior_match(regra, campos))


def classificar(lanc: Lancamento, ctx: Contexto) -> Veredito:
    """Devolve o Veredito do Lançamento.

    Resolução: dentre as Regras que casam, vence a de MENOR prioridade.
    """
    campos = _campos_busca(lanc)
    candidatas = [r for r in ctx.regras
                  if r.tipo == lanc.tipo and _regra_casa(r, campos, lanc.tem_obra)]
    if candidatas:
        vencedora = min(candidatas, key=lambda r: _chave_desempate(r, campos))
        return Veredito(
            categoria_id=vencedora.categoria_id,
            categoria_nome=vencedora.categoria_nome,
            origem_decisao="regra",
            eh_pendente=False,
        )

    # Sem Regra → Memória Exata (texto idêntico já corrigido antes)
    mem = ctx.memoria_exata.get(texto_norm(lanc))
    if mem:
        cat_id, cat_nome = mem
        return Veredito(categoria_id=cat_id, categoria_nome=cat_nome,
                        origem_decisao="memoria_exata", eh_pendente=False)

    # Sem Regra e sem Memória → Pendente de Classificação
    return Veredito(categoria_id=None, categoria_nome=None,
                    origem_decisao="fallback", eh_pendente=True)


# ── Resolução para o preview de importação (Fase D) ─────────────────────────

# Categoria genérica quando nenhuma Regra casa (Pendente). É o sinal de revisão
# manual do §3: o cadastro não soube classificar.
FALLBACK_NOME = {"ENTRADA": "Outros Recebimentos", "SAIDA": "Outras Saídas"}


@dataclass
class Resolucao:
    """Veredito já enriquecido para o preview: categoria nomeada + id do tenant,
    macro derivado e a decisão auto (cadastro classificou) vs manual (fallback)."""
    categoria_id: Optional[int]
    categoria_nome: Optional[str]
    tipo_categoria: str          # macro derivado da categoria nomeada
    eh_manual: bool
    origem_decisao: str


def resolver(lanc: Lancamento, ctx: Contexto, cat_id_por_nome=None) -> Resolucao:
    """Classifica o Lançamento e resolve tudo que o preview precisa num passo:
    categoria nomeada, id da categoria no tenant, macro e auto/manual."""
    v = classificar(lanc, ctx)
    if v.eh_pendente:
        nome = FALLBACK_NOME.get(lanc.tipo, "Outras Saídas")
        cat_id_por_nome = cat_id_por_nome or {}
        return Resolucao(
            categoria_id=cat_id_por_nome.get(_norm(nome)),
            categoria_nome=nome,
            tipo_categoria=derivar_macro(nome),
            eh_manual=True,
            origem_decisao=v.origem_decisao,
        )
    return Resolucao(
        categoria_id=v.categoria_id,
        categoria_nome=v.categoria_nome,
        tipo_categoria=derivar_macro(v.categoria_nome),
        eh_manual=v.categoria_nome in FALLBACK_NOME.values(),
        origem_decisao=v.origem_decisao,
    )


# ── Fila por Termo: Sugestões sobre os Pendentes (Fase E) ───────────────────

@dataclass
class Sugestao:
    """Termo recorrente entre os Pendentes, agregado por impacto. O usuário pode
    transformá-lo numa Regra (origem='usuario')."""
    termo: str
    ocorrencias: int
    soma_valor: float
    exemplo: str = ""
    tipo: str = "SAIDA"


def _ngramas(texto, n_max=3):
    """N-gramas de 1 a n_max palavras do texto normalizado (preserva ordem)."""
    palavras = [p for p in _norm(texto).split() if p]
    grams = []
    for n in range(1, n_max + 1):
        for i in range(len(palavras) - n + 1):
            grams.append(" ".join(palavras[i:i + n]))
    return grams


def gerar_sugestoes(pendentes, regras_existentes=()):
    """Fila por Termo (função pura, §7.1): tokeniza o fornecedor dos Pendentes em
    n-gramas (1–3 palavras), agrega por termo (ocorrencias, soma_valor, exemplo) e
    ordena por impacto (ocorrencias × soma_valor)."""
    # Gatilhos já cadastrados: um termo candidato que contenha um gatilho existente
    # já é coberto pelo cadastro e não vira sugestão.
    cobertos = {_norm(p) for r in regras_existentes for p in r.palavras if _norm(p)}

    def _coberto(termo):
        return any(kw in termo for kw in cobertos)

    agg = {}
    for lanc in pendentes:
        for termo in set(_ngramas(lanc.fornecedor)):
            if _coberto(termo):
                continue
            d = agg.setdefault(termo, {"ocorrencias": 0, "soma_valor": 0.0,
                                       "exemplo": "", "tipo": lanc.tipo})
            d["ocorrencias"] += 1
            d["soma_valor"] += lanc.valor or 0.0
            if not d["exemplo"]:
                d["exemplo"] = lanc.descricao or lanc.fornecedor

    sugestoes = [Sugestao(termo=t, ocorrencias=d["ocorrencias"],
                          soma_valor=d["soma_valor"], exemplo=d["exemplo"],
                          tipo=d["tipo"])
                 for t, d in agg.items()]
    sugestoes.sort(key=lambda s: -(s.ocorrencias * s.soma_valor))
    return sugestoes
