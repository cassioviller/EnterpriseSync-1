#!/usr/bin/env python3
"""Rastreio de campos, funcionalidades e integração por módulo → MODULOS.md.

Regenera a seção entre `<!-- RASTREIO:INICIO -->` e `<!-- RASTREIO:FIM -->`
do MODULOS.md. Análise 100% estática (não importa o app):

1. `models.py` via AST — classes, `__tablename__`, colunas (nome + FK).
2. Arquivos de views via regex — rotas `@bp.route` (path, métodos, função).
3. Varredura de uso: quais modelos cada módulo referencia → matriz de
   integração (modelo compartilhado = ponto de conferência).

Uso:
    python scripts/rastreio_modulos.py            # reescreve a seção no MODULOS.md
    python scripts/rastreio_modulos.py --stdout   # só imprime (não toca o arquivo)

Ao adicionar/remover blueprint, atualize o dicionário MODULOS abaixo E as
tabelas manuais do MODULOS.md (este script só cuida da seção de rastreio).
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Módulo → arquivos de view (mesmo agrupamento das tabelas do MODULOS.md).
MODULOS = {
    # núcleo operacional (obra)
    'Obras/Dashboard/base (main)': [
        'views/__init__.py', 'views/auth.py', 'views/dashboard.py',
        'views/users.py', 'views/employees.py', 'views/obras.py',
        'views/vehicles.py', 'views/rdo.py', 'views/api.py', 'views/admin.py'],
    'RDO — edição': ['rdo_editar_sistema.py'],
    'RDO — CRUD completo': ['crud_rdo_completo.py'],
    'Cronograma': ['cronograma_views.py'],
    'Cronograma — importação .mpp': ['views/cronograma_importacao.py'],
    'Portal do cliente': ['portal_obras_views.py'],
    'Medição': ['medicao_views.py'],
    'Importação': ['importacao_views.py'],
    # pessoas
    'Equipe': ['equipe_views.py'],
    'Funcionários (API)': ['api_funcionarios.py'],
    'Ponto': ['ponto_views.py'],
    'Folha de pagamento': ['folha_pagamento_views.py'],
    'Alimentação': ['alimentacao_views.py'],
    'Reembolso': ['reembolso_views.py'],
    'Subempreiteiros': ['subempreiteiros_views.py'],
    # financeiro / custos
    'Financeiro': ['financeiro_views.py'],
    'Relatórios financeiros avançados': ['relatorios_financeiros_avancados.py'],
    'Contabilidade': ['contabilidade_views.py'],
    'Custos de obra': ['custos_views.py'],
    'Gestão de custos': ['gestao_custos_views.py'],
    'Custos de escritório': ['custos_escritorio_views.py'],
    'Planejamento de custos': ['views/planejamento_custos_views.py'],
    # comercial
    'CRM': ['crm_views.py'],
    'Clientes': ['clientes_views.py'],
    'Propostas': ['propostas_consolidated.py'],
    'Orçamentos': ['views/orcamentos_views.py'],
    'Orçamento operacional': ['views/orcamento_operacional_views.py'],
    'Catálogo de serviços': ['views/catalogo_views.py'],
    'Categorias de serviços': ['categoria_servicos.py'],
    'Serviço da obra (real)': ['crud_servico_obra_real.py'],
    'Serviços da obra (API)': ['api_servicos_obra_limpa.py'],
    'Cadastrar serviço na obra': ['cadastrar_servico_obra.py'],
    # suprimentos / logística
    'Almoxarifado': [
        'views/almoxarifado/__init__.py', 'views/almoxarifado/api.py',
        'views/almoxarifado/categorias.py', 'views/almoxarifado/dashboard.py',
        'views/almoxarifado/fornecedores.py', 'views/almoxarifado/itens.py',
        'views/almoxarifado/movimentos.py', 'views/almoxarifado/relatorios.py'],
    'Compras': ['compras_views.py'],
    'Frota': ['frota_views.py'],
    'Transporte': ['transporte_views.py'],
    # transversais
    'Relatórios': ['relatorios_funcionais.py'],
    'Exportação de relatórios': ['exportacao_relatorios.py'],
    'Analytics preditivos': ['analytics_preditivos.py'],
    'Dashboards específicos': ['dashboards_especificos.py'],
    'Métricas': ['views/metricas_views.py'],
    'Configurações': ['configuracoes_views.py'],
    'Hub de cadastros': ['cadastros_views.py'],
    'Quick-create': ['views/quick_create_views.py'],
    'Catálogos (views)': ['views/catalogos_views.py'],
    'API organizer': ['api_organizer.py'],
    'Auditoria de vínculos': ['vinculos_audit_views.py'],
    'Manual': ['views/manual_views.py'],
    'Landing': ['landing_views.py'],
    'Dev': ['views/dev_views.py'],
    'Produção': ['production_routes.py'],
}

# Entidades que cruzam o sistema inteiro: campos completos numa seção própria.
CENTRAIS = ['Obra', 'Funcionario', 'Usuario', 'RDO', 'CustoObra',
            'TarefaCronograma', 'Servico', 'Cliente', 'Proposta', 'RegistroPonto']

MARCA_INI = '<!-- RASTREIO:INICIO -->'
MARCA_FIM = '<!-- RASTREIO:FIM -->'


def _snake(nome):
    """Default do Flask-SQLAlchemy para classe sem __tablename__."""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', nome).lower()


def extrair_modelos():
    tree = ast.parse(open(os.path.join(ROOT, 'models.py')).read())
    modelos = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        tabela, cols = None, []
        for item in node.body:
            if not (isinstance(item, ast.Assign) and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)):
                continue
            nome = item.targets[0].id
            if nome == '__tablename__':
                try:
                    tabela = ast.literal_eval(item.value)
                except Exception:
                    pass
                continue
            call = item.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                    and call.func.attr == 'Column':
                fk = None
                for arg in call.args:
                    s = ast.unparse(arg)
                    if 'ForeignKey' in s:
                        m = re.search(r"ForeignKey\(\s*['\"]([^'\"]+)", s)
                        if m:
                            fk = m.group(1)
                cols.append({'nome': nome, 'fk': fk})
        if cols:
            modelos[node.name] = {'tabela': tabela or _snake(node.name), 'cols': cols}
    return modelos


# [^)]* limita a captura de methods= ao parêntese do PRÓPRIO decorator —
# com .*?/re.S a busca atravessava o arquivo até o methods= de outra rota,
# engolindo as rotas intermediárias e desalinhando os nomes de função.
ROUTE_RE = re.compile(
    r"@(\w+)\.route\(\s*['\"]([^'\"]+)['\"](?:[^)]*methods\s*=\s*(\[[^\]]*\]))?", re.S)
DEF_RE = re.compile(r"def\s+(\w+)\s*\(")


def extrair_rotas(path):
    try:
        src = open(path).read()
    except OSError:
        return []
    rotas = []
    for m in ROUTE_RE.finditer(src):
        met = re.findall(r"['\"](\w+)['\"]", m.group(3)) if m.group(3) else ['GET']
        d = DEF_RE.search(src, m.end())
        rotas.append({'rota': m.group(2), 'metodos': met,
                      'func': d.group(1) if d else '?'})
    return rotas


def modelos_usados(path, nomes):
    try:
        src = open(path).read()
    except OSError:
        return set()
    return {n for n in nomes if re.search(r'\b' + re.escape(n) + r'\b', src)}


def gerar_secao():
    modelos = extrair_modelos()
    nomes = list(modelos)

    dados, uso = {}, {}
    for mod, arquivos in MODULOS.items():
        rotas, usados = [], set()
        for arq in arquivos:
            p = os.path.join(ROOT, arq)
            rotas += extrair_rotas(p)
            usados |= modelos_usados(p, nomes)
        dados[mod] = {'arquivos': arquivos, 'rotas': rotas,
                      'modelos': sorted(usados)}
        for m in usados:
            uso.setdefault(m, []).append(mod)

    def campos(nome):
        info = modelos[nome]
        out = []
        for c in info['cols']:
            s = c['nome']
            if c['fk']:
                s += f"→{c['fk'].split('.')[0]}"
            out.append(s)
        return info['tabela'], out

    total_rotas = sum(len(d['rotas']) for d in dados.values())
    L = []
    w = L.append
    w('## Rastreio por módulo — campos, funcionalidades e integração')
    w('')
    w('> **Gerado por `python scripts/rastreio_modulos.py`** (análise estática:')
    w('> AST de `models.py` + regex de `@bp.route` + varredura de uso de modelos')
    w('> por arquivo de view). Não edite esta seção à mão — rode o script.')
    w(f'> Números desta geração: **{len(modelos)} modelos**, **{total_rotas} rotas**.')
    w('> "Modelos próprios" = referenciados por até 2 módulos; o resto aparece em')
    w('> "compartilhados" — onde mora a integração, e o risco na conferência.')
    w('> A marca `Conferência:` de cada módulo é manual e **sobrevive à regeração**.')
    w('')
    w('### Entidades centrais (campos completos)')
    w('')
    w('FK indicada com `→tabela`.')
    w('')
    for nome in CENTRAIS:
        if nome not in modelos:
            continue
        tabela, cs = campos(nome)
        w(f'**{nome}** (`{tabela}`, {len(cs)} colunas, usada por '
          f'{len(uso.get(nome, []))} módulos):')
        w(f'`{"`, `".join(cs)}`')
        w('')
    w('---')
    w('')
    for mod, info in dados.items():
        proprios = [m for m in info['modelos']
                    if len(uso.get(m, [])) <= 2 and m not in CENTRAIS]
        compartilhados = [m for m in info['modelos'] if m not in proprios]
        w(f'### {mod}')
        w('')
        w('Arquivos: ' + ', '.join(f'`{a}`' for a in info['arquivos']))
        w('Conferência: ☐ pendente')
        w('')
        if info['rotas']:
            w(f'**Funcionalidades ({len(info["rotas"])} rotas):**')
            w('')
            w('| Rota | Métodos | Função |')
            w('|---|---|---|')
            for r in info['rotas']:
                w(f"| `{r['rota']}` | {','.join(r['metodos'])} | `{r['func']}` |")
            w('')
        else:
            w('**Funcionalidades:** nenhuma rota própria.')
            w('')
        if proprios:
            w(f'**Modelos próprios ({len(proprios)}):**')
            w('')
            for m in proprios:
                tabela, cs = campos(m)
                outros = [x for x in uso.get(m, []) if x != mod]
                extra = f' — também usado por {outros[0]}' if outros else ''
                w(f'- **{m}** (`{tabela}`, {len(cs)} col){extra}: '
                  f'`{"`, `".join(cs)}`')
            w('')
        if compartilhados:
            w(f'**Modelos compartilhados que este módulo toca '
              f'({len(compartilhados)}):** '
              + ', '.join(f'`{m}`' for m in compartilhados))
            w('')
    w('---')
    w('')
    w('### Matriz de integração — modelos mais compartilhados')
    w('')
    w('Modelos usados por 4+ módulos: cada um é um ponto de integração a')
    w('conferir (mudança num módulo pode quebrar os outros).')
    w('')
    w('| Modelo | Módulos | Quais |')
    w('|---|---|---|')
    for m, mods in sorted(uso.items(), key=lambda kv: -len(kv[1])):
        if len(mods) >= 4:
            w(f'| `{m}` | {len(mods)} | {", ".join(mods)} |')
    w('')
    return '\n'.join(L)


def preservar_conferencias(antigo, novo):
    """Copia as marcas `Conferência:` já preenchidas da versão antiga."""
    marcas = {}
    mod_atual = None
    for ln in antigo.splitlines():
        if ln.startswith('### '):
            mod_atual = ln[4:].strip()
        elif ln.startswith('Conferência:') and mod_atual:
            marcas[mod_atual] = ln
    out, mod_atual = [], None
    for ln in novo.splitlines():
        if ln.startswith('### '):
            mod_atual = ln[4:].strip()
        elif ln.startswith('Conferência:') and mod_atual in marcas:
            ln = marcas[mod_atual]
        out.append(ln)
    return '\n'.join(out)


def main():
    secao = gerar_secao()
    if '--stdout' in sys.argv:
        print(secao)
        return
    caminho = os.path.join(ROOT, 'MODULOS.md')
    doc = open(caminho).read()
    if MARCA_INI not in doc or MARCA_FIM not in doc:
        sys.exit(f'MODULOS.md sem os marcadores {MARCA_INI} / {MARCA_FIM}')
    antes, resto = doc.split(MARCA_INI, 1)
    velho, depois = resto.split(MARCA_FIM, 1)
    secao = preservar_conferencias(velho, secao)
    open(caminho, 'w').write(
        antes + MARCA_INI + '\n' + secao + '\n' + MARCA_FIM + depois)
    print(f'MODULOS.md atualizado ({len(secao.splitlines())} linhas na seção).')


if __name__ == '__main__':
    main()
