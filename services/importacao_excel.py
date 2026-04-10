"""
Serviço de Importação Excel para o SIGE v9.0
5 módulos: Funcionários, Diárias, Alimentação, Transporte, Custos

Fluxo por módulo:
  1. processar(ws, admin_id, defaults={}) → (validos, erros)
     - Lê planilha, valida campos, retorna preview sem salvar no DB
  2. importar(rows, admin_id) → {'criados': N, 'erros': [...]}
     - Recebe lista de dicts com dados já validados, salva no DB
"""
import logging
import re
from datetime import datetime, date

logger = logging.getLogger(__name__)

# ── Helpers compartilhados ─────────────────────────────────────────────────────

def _norm(v):
    if v is None:
        return ''
    return str(v).strip()

def _parse_data(v):
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    s = _norm(v)
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _parse_float(v, default=0.0):
    if isinstance(v, (int, float)):
        return float(v)
    s = _norm(v).replace('R$', '').replace(' ', '')
    if not s:
        return default
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return default

def _limpar_cpf(v):
    return re.sub(r'\D', '', _norm(v))[:11]

def _mapear_headers(row_vals):
    """Retorna {header_normalizado: col_index (0-based)}."""
    import unicodedata
    def n(s):
        s = _norm(s).lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = s.replace(' ', '_').replace('*', '').replace('-', '_').strip('_')
        return s
    return {n(str(cell)): idx for idx, cell in enumerate(row_vals)}

def _detectar_header_row(ws, must_contain):
    """Detecta qual linha tem o cabeçalho contendo pelo menos um dos termos."""
    import unicodedata
    def n(s):
        s = _norm(s).lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = s.replace(' ', '_').replace('*', '').strip('_')
        return s
    for r in range(1, min(6, ws.max_row + 1)):
        vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        normalized = [n(str(v)) for v in vals]
        if any(term in normalized for term in must_contain):
            return r, [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
    return None, None

def _cel(ws, row_num, hm, *keys):
    """Retorna o valor da primeira chave encontrada no header_map."""
    for k in keys:
        if k in hm:
            return ws.cell(row=row_num, column=hm[k] + 1).value
    return None


# ── MÓDULO 1: Funcionários ─────────────────────────────────────────────────────

class ImportacaoFuncionarios:
    """
    Suporta dois formatos:
    - SIGE: cabeçalho na linha 3 com: nome, cpf, tipo_remuneracao, valor, ...
    - REGISTRO_COLABORADORES: cabeçalho na linha 3 com NOME, CPF, REMUNERACAO, VALOR
    """

    def _detectar_formato(self, hm):
        if 'tipo_remuneracao' in hm or 'data_admissao' in hm:
            return 'sige'
        if 'remuneracao' in hm and 'valor' in hm:
            return 'colaboradores'
        return 'sige'

    def processar(self, ws, admin_id, defaults=None):
        """
        Retorna (validos, erros).
        validos = list[dict] prontos para importar
        erros   = list[dict] com 'linha' e 'motivo'
        """
        from models import Funcionario
        defaults = defaults or {}

        header_row, raw_headers = _detectar_header_row(ws, ['nome', 'cpf'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        formato = self._detectar_formato(hm)

        validos, erros = [], []
        cpfs_vistos = set()

        for rn in range(header_row + 1, ws.max_row + 1):
            def c(*keys):
                return _cel(ws, rn, hm, *keys)

            nome = _norm(c('nome'))
            if not nome or nome.upper() in ('NOME', '-', '#N/A', 'NONE'):
                continue

            cpf_raw = c('cpf')
            if not cpf_raw:
                erros.append({'linha': rn, 'nome': nome, 'motivo': 'CPF não informado'})
                continue
            cpf = _limpar_cpf(cpf_raw)
            if len(cpf) < 11:
                erros.append({'linha': rn, 'nome': nome, 'motivo': f'CPF inválido: {cpf_raw}'})
                continue
            if cpf in cpfs_vistos:
                erros.append({'linha': rn, 'nome': nome, 'motivo': f'CPF duplicado na planilha: {cpf}'})
                continue
            cpfs_vistos.add(cpf)

            # Verifica se já existe (será atualização, não erro)
            existe = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
            operacao = 'atualizar' if existe else 'criar'

            if formato == 'colaboradores':
                rem_raw = _norm(c('remuneracao')).upper()
                tipo_rem = 'diaria' if ('DIARIA' in rem_raw or 'DIÁRIA' in rem_raw) else 'salario'
                valor = _parse_float(c('valor'))
                data_admissao = _parse_data(c('data_admissao', 'admissao')) or (
                    _parse_data(defaults.get('data_admissao')) or date.today()
                )
            else:
                rem_raw = _norm(c('tipo_remuneracao')).lower()
                tipo_rem = 'diaria' if 'diaria' in rem_raw or 'diária' in rem_raw else 'salario'
                valor = _parse_float(c('valor', 'valor_diaria', 'salario'))
                data_admissao = _parse_data(c('data_admissao', 'admissao')) or date.today()

            status_raw = _norm(c('status')).upper()
            ativo = status_raw != 'INATIVO'

            row = {
                'linha': rn,
                'nome': nome,
                'cpf': cpf,
                'rg': _norm(c('rg')) or None,
                'telefone': _norm(c('telefone', 'tel')) or None,
                'endereco': _norm(c('endereco')) or None,
                'chave_pix': _norm(c('chave_pix', 'pix')) or None,
                'data_nascimento': _parse_data(c('data_nascimento', 'data_nasc')),
                'ativo': ativo,
                'tipo_remuneracao': tipo_rem,
                'valor': valor,
                'data_admissao': str(data_admissao),
                'valor_va': _parse_float(c('valor_va', 'va')),
                'valor_vt': _parse_float(c('valor_vt', 'vt')),
                'operacao': operacao,
            }
            validos.append(row)

        return validos, erros

    def importar(self, rows, admin_id):
        from models import db, Funcionario
        criados, atualizados, erros = 0, 0, []

        for row in rows:
            sp = db.session.begin_nested()
            try:
                cpf = row['cpf']
                data_adm = _parse_data(row.get('data_admissao')) or date.today()
                existente = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
                if existente:
                    existente.nome = row['nome']
                    if row.get('rg'):
                        existente.rg = row['rg']
                    if row.get('telefone'):
                        existente.telefone = row['telefone']
                    if row.get('endereco'):
                        existente.endereco = row['endereco']
                    if row.get('chave_pix'):
                        existente.chave_pix = row['chave_pix']
                    if row.get('data_nascimento'):
                        existente.data_nascimento = _parse_data(row['data_nascimento'])
                    existente.ativo = row.get('ativo', True)
                    existente.tipo_remuneracao = row['tipo_remuneracao']
                    v = _parse_float(row.get('valor', 0))
                    if row['tipo_remuneracao'] == 'diaria' and v > 0:
                        existente.valor_diaria = v
                    elif v > 0:
                        existente.salario = v
                    if _parse_float(row.get('valor_va', 0)) > 0:
                        existente.valor_va = _parse_float(row['valor_va'])
                    if _parse_float(row.get('valor_vt', 0)) > 0:
                        existente.valor_vt = _parse_float(row['valor_vt'])
                    sp.commit()
                    atualizados += 1
                else:
                    ultimo = (Funcionario.query
                              .filter(Funcionario.codigo.like('VV%'), Funcionario.admin_id == admin_id)
                              .order_by(Funcionario.codigo.desc()).first())
                    try:
                        proximo = int(ultimo.codigo[2:]) + 1 if ultimo else 1
                    except Exception:
                        proximo = 1
                    codigo = f"VV{proximo:03d}"
                    v = _parse_float(row.get('valor', 0))
                    kwargs = dict(
                        nome=row['nome'], cpf=cpf, rg=row.get('rg'),
                        telefone=row.get('telefone'), endereco=row.get('endereco'),
                        chave_pix=row.get('chave_pix'),
                        data_nascimento=_parse_data(row.get('data_nascimento')),
                        ativo=row.get('ativo', True), admin_id=admin_id, codigo=codigo,
                        tipo_remuneracao=row['tipo_remuneracao'], data_admissao=data_adm,
                        valor_va=_parse_float(row.get('valor_va', 0)),
                        valor_vt=_parse_float(row.get('valor_vt', 0)),
                    )
                    if row['tipo_remuneracao'] == 'diaria':
                        kwargs['valor_diaria'] = v
                        kwargs['salario'] = 0
                    else:
                        kwargs['salario'] = v
                        kwargs['valor_diaria'] = 0
                    db.session.add(Funcionario(**kwargs))
                    sp.commit()
                    criados += 1
            except Exception as e:
                sp.rollback()
                erros.append({'linha': row.get('linha'), 'nome': row.get('nome'), 'motivo': str(e)})

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            erros.append({'linha': 'COMMIT', 'motivo': str(e)})

        return {'criados': criados, 'atualizados': atualizados, 'erros': erros}


# ── MÓDULO 2: Diárias ──────────────────────────────────────────────────────────

class ImportacaoDiarias:
    """
    Colunas: nome_funcionario, data, valor, obra, status, descricao, chave_pix
    Cria GestaoCustoPai/Filho via registrar_custo_automatico(tipo='SALARIO')
    """

    def processar(self, ws, admin_id):
        from models import Funcionario, Obra

        header_row, raw_headers = _detectar_header_row(ws, ['nome_funcionario', 'nome', 'funcionario'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        validos, erros = [], []

        for rn in range(header_row + 1, ws.max_row + 1):
            def c(*keys):
                return _cel(ws, rn, hm, *keys)

            nome = _norm(c('nome_funcionario', 'nome', 'funcionario'))
            if not nome:
                continue

            data_ref = _parse_data(c('data', 'data_ponto'))
            if not data_ref:
                erros.append({'linha': rn, 'nome': nome, 'motivo': 'Data inválida'})
                continue

            valor = _parse_float(c('valor', 'valor_diaria'))
            if valor <= 0:
                erros.append({'linha': rn, 'nome': nome, 'motivo': 'Valor deve ser maior que 0'})
                continue

            # Buscar funcionário
            func = (Funcionario.query
                    .filter(Funcionario.nome.ilike(f'%{nome}%'), Funcionario.admin_id == admin_id)
                    .first())
            if not func:
                erros.append({'linha': rn, 'nome': nome, 'motivo': f'Funcionário "{nome}" não encontrado'})
                continue

            # Buscar obra
            obra_raw = _norm(c('obra', 'obra_id', 'codigo_obra'))
            obra = None
            if obra_raw:
                obra = (Obra.query
                        .filter(Obra.admin_id == admin_id)
                        .filter((Obra.nome.ilike(f'%{obra_raw}%')) | (Obra.codigo == obra_raw))
                        .first())

            validos.append({
                'linha': rn,
                'nome': func.nome,
                'funcionario_id': func.id,
                'data': str(data_ref),
                'valor': valor,
                'obra_id': obra.id if obra else None,
                'obra_nome': obra.nome if obra else '(sem obra)',
                'status': _norm(c('status')) or 'PENDENTE',
                'descricao': _norm(c('descricao')) or f'Diária - {func.nome} - {data_ref.strftime("%d/%m/%Y")}',
            })

        return validos, erros

    def importar(self, rows, admin_id):
        from models import db
        from utils.financeiro_integration import registrar_custo_automatico
        criados, erros = 0, []

        for row in rows:
            try:
                data_ref = _parse_data(row['data'])
                filho = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='SALARIO',
                    entidade_nome=row['nome'],
                    entidade_id=row['funcionario_id'],
                    data=data_ref,
                    descricao=row['descricao'],
                    valor=_parse_float(row['valor']),
                    obra_id=row.get('obra_id'),
                    origem_tabela='importacao_diaria',
                    origem_id=row['linha'],
                )
                if filho:
                    db.session.commit()
                    criados += 1
                else:
                    erros.append({'linha': row['linha'], 'nome': row['nome'], 'motivo': 'Erro ao registrar custo'})
            except Exception as e:
                db.session.rollback()
                erros.append({'linha': row['linha'], 'nome': row['nome'], 'motivo': str(e)})

        return {'criados': criados, 'erros': erros}


# ── MÓDULO 3: Alimentação ──────────────────────────────────────────────────────

class ImportacaoAlimentacao:
    """
    Colunas: data, obra, valor_total, funcionarios (sep por ;), descricao, restaurante
    Cria AlimentacaoLancamento + associa funcionários por nome
    """

    def processar(self, ws, admin_id):
        from models import Funcionario, Obra

        header_row, raw_headers = _detectar_header_row(ws, ['data', 'valor_total', 'funcionarios'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        validos, erros = [], []

        for rn in range(header_row + 1, ws.max_row + 1):
            def c(*keys):
                return _cel(ws, rn, hm, *keys)

            data_ref = _parse_data(c('data'))
            if not data_ref:
                continue

            valor = _parse_float(c('valor_total', 'valor'))
            if valor <= 0:
                erros.append({'linha': rn, 'nome': str(data_ref), 'motivo': 'Valor deve ser maior que 0'})
                continue

            obra_raw = _norm(c('obra', 'obra_id'))
            obra = None
            if obra_raw:
                obra = (Obra.query.filter(Obra.admin_id == admin_id)
                        .filter((Obra.nome.ilike(f'%{obra_raw}%')) | (Obra.codigo == obra_raw))
                        .first())
                if not obra:
                    erros.append({'linha': rn, 'nome': str(data_ref), 'motivo': f'Obra "{obra_raw}" não encontrada'})
                    continue

            # Resolver lista de funcionários
            funcs_raw = _norm(c('funcionarios', 'funcionario'))
            func_ids = []
            func_nomes_ok = []
            func_nomes_erro = []
            if funcs_raw:
                for fn in [x.strip() for x in funcs_raw.split(';') if x.strip()]:
                    f = (Funcionario.query
                         .filter(Funcionario.nome.ilike(f'%{fn}%'), Funcionario.admin_id == admin_id)
                         .first())
                    if f:
                        func_ids.append(f.id)
                        func_nomes_ok.append(f.nome)
                    else:
                        func_nomes_erro.append(fn)

            if func_nomes_erro:
                erros.append({'linha': rn, 'nome': str(data_ref),
                               'motivo': f'Funcionários não encontrados: {", ".join(func_nomes_erro)}'})
                continue

            validos.append({
                'linha': rn,
                'data': str(data_ref),
                'valor_total': valor,
                'obra_id': obra.id if obra else None,
                'obra_nome': obra.nome if obra else '(sem obra)',
                'descricao': _norm(c('descricao')) or 'Alimentação importada',
                'restaurante': _norm(c('restaurante', 'fornecedor')) or None,
                'funcionario_ids': func_ids,
                'funcionarios_nomes': '; '.join(func_nomes_ok),
            })

        return validos, erros

    def importar(self, rows, admin_id):
        from models import db, AlimentacaoLancamento, Funcionario
        from sqlalchemy import text
        criados, erros = 0, []

        for row in rows:
            sp = db.session.begin_nested()
            try:
                data_ref = _parse_data(row['data'])
                lanc = AlimentacaoLancamento(
                    data=data_ref,
                    valor_total=_parse_float(row['valor_total']),
                    descricao=row['descricao'],
                    obra_id=row.get('obra_id'),
                    admin_id=admin_id,
                )
                db.session.add(lanc)
                db.session.flush()

                # Associar funcionários (tabela M2M: alimentacao_funcionarios_assoc)
                for fid in row.get('funcionario_ids', []):
                    db.session.execute(
                        text('INSERT INTO alimentacao_funcionarios_assoc (lancamento_id, funcionario_id, admin_id) VALUES (:lid, :fid, :aid) ON CONFLICT DO NOTHING'),
                        {'lid': lanc.id, 'fid': fid, 'aid': admin_id}
                    )
                sp.commit()
                criados += 1
            except Exception as e:
                sp.rollback()
                erros.append({'linha': row['linha'], 'motivo': str(e)})

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            erros.append({'linha': 'COMMIT', 'motivo': str(e)})

        return {'criados': criados, 'erros': erros}


# ── MÓDULO 4: Transporte ───────────────────────────────────────────────────────

class ImportacaoTransporte:
    """
    Colunas: data, nome_funcionario, categoria, valor, obra, descricao
    Cria GestaoCustoPai/Filho via registrar_custo_automatico(tipo='TRANSPORTE')
    """

    def processar(self, ws, admin_id):
        from models import Funcionario, Obra

        header_row, raw_headers = _detectar_header_row(ws, ['nome_funcionario', 'funcionario', 'nome'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        validos, erros = [], []

        for rn in range(header_row + 1, ws.max_row + 1):
            def c(*keys):
                return _cel(ws, rn, hm, *keys)

            nome = _norm(c('nome_funcionario', 'nome', 'funcionario'))
            if not nome:
                continue

            data_ref = _parse_data(c('data'))
            if not data_ref:
                erros.append({'linha': rn, 'nome': nome, 'motivo': 'Data inválida'})
                continue

            valor = _parse_float(c('valor'))
            if valor <= 0:
                erros.append({'linha': rn, 'nome': nome, 'motivo': 'Valor deve ser maior que 0'})
                continue

            func = (Funcionario.query
                    .filter(Funcionario.nome.ilike(f'%{nome}%'), Funcionario.admin_id == admin_id)
                    .first())
            if not func:
                erros.append({'linha': rn, 'nome': nome, 'motivo': f'Funcionário "{nome}" não encontrado'})
                continue

            obra_raw = _norm(c('obra'))
            obra = None
            if obra_raw:
                obra = (Obra.query.filter(Obra.admin_id == admin_id)
                        .filter((Obra.nome.ilike(f'%{obra_raw}%')) | (Obra.codigo == obra_raw))
                        .first())

            categoria = _norm(c('categoria')) or 'Transporte'

            validos.append({
                'linha': rn,
                'nome': func.nome,
                'funcionario_id': func.id,
                'data': str(data_ref),
                'valor': valor,
                'categoria': categoria,
                'obra_id': obra.id if obra else None,
                'obra_nome': obra.nome if obra else '(sem obra)',
                'descricao': _norm(c('descricao')) or f'{categoria} - {func.nome} - {data_ref.strftime("%d/%m/%Y")}',
            })

        return validos, erros

    def importar(self, rows, admin_id):
        from models import db
        from utils.financeiro_integration import registrar_custo_automatico
        criados, erros = 0, []

        for row in rows:
            try:
                data_ref = _parse_data(row['data'])
                filho = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='TRANSPORTE',
                    entidade_nome=row['nome'],
                    entidade_id=row['funcionario_id'],
                    data=data_ref,
                    descricao=row['descricao'],
                    valor=_parse_float(row['valor']),
                    obra_id=row.get('obra_id'),
                    origem_tabela='importacao_transporte',
                    origem_id=row['linha'],
                )
                if filho:
                    db.session.commit()
                    criados += 1
                else:
                    erros.append({'linha': row['linha'], 'nome': row['nome'], 'motivo': 'Erro ao registrar custo'})
            except Exception as e:
                db.session.rollback()
                erros.append({'linha': row['linha'], 'nome': row['nome'], 'motivo': str(e)})

        return {'criados': criados, 'erros': erros}


# ── MÓDULO 5: Custos ───────────────────────────────────────────────────────────

class ImportacaoCustos:
    """
    Colunas: data, fornecedor, descricao, valor, obra, categoria, status,
             forma_pagamento, banco_conta, nf_numero, parcela, data_vencimento, observacoes
    Cria GestaoCustoPai diretamente
    """
    CATEGORIAS_VALIDAS = {
        'SALARIO', 'ALIMENTACAO', 'TRANSPORTE', 'MATERIAL',
        'COMPRA', 'DESPESA_GERAL', 'REEMBOLSO',
    }

    def processar(self, ws, admin_id):
        from models import Obra

        header_row, raw_headers = _detectar_header_row(ws, ['fornecedor', 'descricao', 'valor'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        validos, erros = [], []

        for rn in range(header_row + 1, ws.max_row + 1):
            def c(*keys):
                return _cel(ws, rn, hm, *keys)

            fornecedor = _norm(c('fornecedor', 'nome', 'empresa'))
            descricao = _norm(c('descricao', 'historico', 'item'))
            if not descricao and not fornecedor:
                continue

            valor = _parse_float(c('valor', 'valor_total'))
            if valor <= 0:
                erros.append({'linha': rn, 'nome': fornecedor or descricao, 'motivo': 'Valor deve ser maior que 0'})
                continue

            data_ref = _parse_data(c('data', 'data_pagamento')) or date.today()
            data_venc = _parse_data(c('data_vencimento'))

            categoria = _norm(c('categoria', 'tipo', 'tipo_categoria')).upper()
            if categoria not in self.CATEGORIAS_VALIDAS:
                categoria = 'DESPESA_GERAL'

            obra_raw = _norm(c('obra', 'centro_custo', 'obra_id'))
            obra = None
            if obra_raw:
                obra = (Obra.query.filter(Obra.admin_id == admin_id)
                        .filter((Obra.nome.ilike(f'%{obra_raw}%')) | (Obra.codigo == obra_raw))
                        .first())

            status_raw = _norm(c('status')).upper()
            status = status_raw if status_raw in ('PAGO', 'PENDENTE', 'AUTORIZADO') else 'PENDENTE'

            validos.append({
                'linha': rn,
                'fornecedor': fornecedor or 'Importação',
                'descricao': descricao or fornecedor,
                'valor': valor,
                'data': str(data_ref),
                'data_vencimento': str(data_venc) if data_venc else None,
                'categoria': categoria,
                'obra_id': obra.id if obra else None,
                'obra_nome': obra.nome if obra else '(sem obra)',
                'status': status,
                'forma_pagamento': _norm(c('forma_pagamento')) or None,
                'banco_conta': _norm(c('banco_conta')) or None,
                'nf_numero': _norm(c('nf_numero', 'nota_fiscal')) or None,
                'parcela': _norm(c('parcela')) or None,
                'observacoes': _norm(c('observacoes', 'obs')) or None,
            })

        return validos, erros

    def importar(self, rows, admin_id):
        from models import db, GestaoCustoPai, GestaoCustoFilho
        criados, erros = 0, []

        for row in rows:
            sp = db.session.begin_nested()
            try:
                data_ref = _parse_data(row['data'])
                data_venc = _parse_data(row.get('data_vencimento'))
                valor = _parse_float(row['valor'])

                pai = GestaoCustoPai(
                    admin_id=admin_id,
                    tipo_categoria=row['categoria'],
                    entidade_nome=row['fornecedor'],
                    entidade_id=None,
                    valor_total=valor,
                    status=row.get('status', 'PENDENTE'),
                    forma_pagamento=row.get('forma_pagamento') or None,
                    data_vencimento=data_venc,
                    numero_documento=row.get('nf_numero') or None,
                    observacoes=row.get('observacoes') or None,
                    data_pagamento=data_ref if row.get('status') == 'PAGO' else None,
                )
                db.session.add(pai)
                db.session.flush()

                filho = GestaoCustoFilho(
                    pai_id=pai.id,
                    data_referencia=data_ref,
                    descricao=row.get('descricao') or row['fornecedor'],
                    valor=valor,
                    obra_id=row.get('obra_id'),
                    admin_id=admin_id,
                    origem_tabela='importacao_custos',
                    origem_id=row.get('linha'),
                )
                db.session.add(filho)
                sp.commit()
                criados += 1
            except Exception as e:
                sp.rollback()
                erros.append({'linha': row.get('linha', '?'), 'motivo': str(e)})

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            erros.append({'linha': 'COMMIT', 'motivo': str(e)})

        return {'criados': criados, 'erros': erros}


# ── Fábrica ────────────────────────────────────────────────────────────────────

MODULO_MAP = {
    'funcionarios': ImportacaoFuncionarios,
    'diarias': ImportacaoDiarias,
    'alimentacao': ImportacaoAlimentacao,
    'transporte': ImportacaoTransporte,
    'custos': ImportacaoCustos,
}

def get_importador(modulo):
    cls = MODULO_MAP.get(modulo)
    if not cls:
        raise ValueError(f'Módulo desconhecido: {modulo}')
    return cls()
