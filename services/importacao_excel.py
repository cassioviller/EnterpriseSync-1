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
    - SIGE: cabeçalho com headers minúsculos: nome, cpf, tipo_remuneracao, data_admissao, ...
    - REGISTRO_COLABORADORES: cabeçalho com headers maiúsculos: NOME, RG, CPF, DATA NASC, ...

    Detecção: raw header[0] == 'nome' (lowercase) → SIGE
              raw header[0] == 'NOME' (uppercase) → REGISTRO_COLABORADORES
    """

    def _detectar_formato(self, raw_headers):
        """
        Detecta formato pelo primeiro header não-vazio, após remover sufixos de marcação (*, !).

        Regra:
          • Primeiro char minúsculo → SIGE (ex: 'nome', 'nome *', 'nome*')
          • Primeiro char maiúsculo → REGISTRO_COLABORADORES (ex: 'NOME', 'NOME *')
          • Não inicia com 'nome'/variante → 'desconhecido'
        """
        import unicodedata

        def sem_acento(s):
            s = unicodedata.normalize('NFD', s)
            return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

        if not raw_headers:
            return 'desconhecido'

        # Pega o primeiro header real (ignora None/vazio)
        primeiro_raw = None
        for h in raw_headers:
            v = str(h).strip() if h is not None else ''
            if v:
                primeiro_raw = v
                break
        if primeiro_raw is None:
            return 'desconhecido'

        # Remove sufixos de marcação (*, !, espaços) para comparar a raiz
        primeiro_clean = sem_acento(
            primeiro_raw.replace('*', '').replace('!', '').strip().lower()
        )
        if primeiro_clean != 'nome':
            return 'desconhecido'

        # Diferencia SIGE (minúsculo) de REGISTRO_COLABORADORES (maiúsculo)
        # usa o primeiro caractere alfabético do header original
        primeiro_alfa = next((c for c in primeiro_raw if c.isalpha()), '')
        if primeiro_alfa.islower():
            return 'sige'
        return 'colaboradores'

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
        formato = self._detectar_formato(raw_headers)
        if formato == 'desconhecido':
            return [], [{'linha': 3, 'nome': '—',
                         'motivo': 'Formato não reconhecido. Use o template SIGE ou o modelo "Registro de Colaboradores".'}]

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

            # CPF já cadastrado neste tenant → rejeitado (importação cria novos, não atualiza)
            existe = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
            if existe:
                erros.append({'linha': rn, 'nome': nome,
                              'motivo': f'CPF {cpf} já cadastrado (funcionário: {existe.nome}). '
                                        f'Use a edição individual para atualizar.'})
                continue

            if formato == 'colaboradores':
                # Tenta ler da planilha; se ausente, usa defaults do formulário
                rem_raw = _norm(c('remuneracao', 'tipo_remuneracao')).upper()
                if rem_raw:
                    tipo_rem = 'diaria' if ('DIARIA' in rem_raw or 'DIÁRIA' in rem_raw) else 'salario'
                else:
                    tipo_rem = _norm(defaults.get('tipo_remuneracao') or 'salario').lower()
                    tipo_rem = 'diaria' if 'diaria' in tipo_rem else 'salario'

                valor = _parse_float(c('valor', 'salario', 'valor_diaria'))
                if valor == 0:
                    valor = _parse_float(defaults.get('valor', '0'))
                # Para Registro de Colaboradores, o valor padrão é obrigatório
                if valor == 0:
                    erros.append({'linha': rn, 'nome': nome,
                                  'motivo': 'Valor não informado. Defina o valor padrão '
                                            'de salário/diária no formulário de importação.'})
                    continue

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

            # Resolução de funcao_id por nome
            funcao_raw = _norm(c('funcao', 'cargo', 'funcao_id'))
            funcao_id = None
            funcao_nome = None
            if funcao_raw:
                from models import Funcao
                funcao_obj = Funcao.query.filter(
                    Funcao.admin_id == admin_id,
                    Funcao.nome.ilike(funcao_raw)
                ).first()
                if funcao_obj:
                    funcao_id = funcao_obj.id
                    funcao_nome = funcao_obj.nome
                else:
                    funcao_nome = f'{funcao_raw} (não encontrada)'

            row = {
                'linha': rn,
                'nome': nome,
                'cpf': cpf,
                'email': _norm(c('email')) or None,
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
                'funcao_id': funcao_id,
                'funcao_nome': funcao_nome,
                'operacao': 'criar',  # Importação cria novos; CPFs existentes são rejeitados em preview
            }
            validos.append(row)

        return validos, erros

    def importar(self, rows, admin_id):
        """
        Apenas CRIA novos funcionários. CPFs já existentes devem ter sido rejeitados em processar().
        Se por alguma razão um CPF duplicado chegar aqui, é registrado como erro sem alteração.
        """
        from models import db, Funcionario
        criados, erros = 0, []

        # Busca o max código VV do tenant uma única vez, antes do loop.
        # O filtro admin_id está correto: cada tenant tem sua própria sequência independente.
        # Re-consultar dentro do loop não funcionaria porque os INSERTs estão em savepoint
        # (não commitados para a sessão principal) e a query retornaria sempre o mesmo valor.
        ultimo_tenant = (Funcionario.query
                         .filter(Funcionario.codigo.like('VV%'), Funcionario.admin_id == admin_id)
                         .order_by(Funcionario.codigo.desc()).first())
        try:
            proximo_num = int(ultimo_tenant.codigo[2:]) + 1 if ultimo_tenant else 1
        except Exception:
            proximo_num = 1

        for row in rows:
            sp = db.session.begin_nested()
            try:
                cpf = row['cpf']
                data_adm = _parse_data(row.get('data_admissao')) or date.today()

                # Dupla verificação: rejeita se CPF já existe (não atualiza)
                if Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first():
                    erros.append({'linha': row.get('linha'), 'nome': row.get('nome'),
                                  'motivo': f'CPF {cpf} já cadastrado — ignorado na importação'})
                    continue

                codigo = f"VV{proximo_num:03d}"
                proximo_num += 1  # incrementa o contador local para o próximo do lote

                v = _parse_float(row.get('valor', 0))
                kwargs = dict(
                    nome=row['nome'], cpf=cpf, rg=row.get('rg'),
                    email=row.get('email'),
                    telefone=row.get('telefone'), endereco=row.get('endereco'),
                    chave_pix=row.get('chave_pix'),
                    data_nascimento=_parse_data(row.get('data_nascimento')),
                    ativo=row.get('ativo', True), admin_id=admin_id, codigo=codigo,
                    tipo_remuneracao=row['tipo_remuneracao'], data_admissao=data_adm,
                    valor_va=_parse_float(row.get('valor_va', 0)),
                    valor_vt=_parse_float(row.get('valor_vt', 0)),
                )
                if row.get('funcao_id'):
                    kwargs['funcao_id'] = row['funcao_id']
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

        return {'criados': criados, 'atualizados': 0, 'erros': erros}


# ── MÓDULO 2: Diárias ──────────────────────────────────────────────────────────


# ── Tipos especiais de lançamento no campo "obra / centro de custo" ────────────
# A palavra-chave é detectada no campo obra da planilha.
# Qualquer valor não reconhecido como tipo especial é tratado como nome de obra.
_TIPOS_ESPECIAIS_DIARIA = {
    'FERIADO':    'sem_lancamento',   # registro apenas, sem custo
    'FALTOU':     'sem_lancamento',
    'DESCANSO':   'sem_lancamento',
    'FOLGA':      'sem_lancamento',
    'FALTA':      'diaria_completa',  # falta sem desconto → lança diária + VA + VT
    'ATESTADO':   'somente_diaria',   # atestado → lança só diária, sem VA e VT
}

_TIPO_LABELS = {
    'sem_lancamento': '🚫 Sem lançamento',
    'diaria_completa': '✅ Diária + VA + VT',
    'somente_diaria': '📋 Só diária (atestado)',
}

def _detectar_tipo_lancamento(obra_raw):
    """Retorna tipo especial ou None quando for obra normal."""
    if not obra_raw:
        return None
    return _TIPOS_ESPECIAIS_DIARIA.get(obra_raw.strip().upper())


class ImportacaoDiarias:
    """
    Suporta dois formatos de planilha:

    FORMATO SIGE (colunas: nome_funcionario, data, obra, status)
    - Valor da diária, VA e VT vêm do cadastro do funcionário

    FORMATO COLABORADORES (detectado pela palavra COLABORADOR na linha 1)
    - Nome do funcionário em: linha 1, col C (ou col A com rótulo COLABORADOR na mesma linha)
    - Cabeçalho: DATA | DIA DA SEMANA | CENTRO DE CUSTO | $ DIÁRIA | $ VT | $ VA
    - Valores lidos diretamente da planilha por linha
    - Múltiplos funcionários por arquivo (cada seção começa com COLABORADOR)

    Regras de lançamento por tipo de centro de custo:
    - Obra normal               → diária + VA + VT
    - FALTA                     → diária + VA + VT (sem desconto)
    - FERIADO / FALTOU / DESCANSO / FOLGA → registro apenas (sem lançamento financeiro)
    - ATESTADO                  → somente diária

    Se a obra não existir → é criada automaticamente com o nome (para editar depois).
    Se o funcionário não existir → é criado com o nome e os valores da planilha (CPF temporário).
    """

    # ── Detecção de formato ────────────────────────────────────────────────────
    def _is_formato_colaboradores(self, ws):
        """Retorna True se a planilha usa o formato multi-colaborador."""
        cell_a1 = _norm(ws.cell(1, 1).value).upper()
        return 'COLABORADOR' in cell_a1

    # ── Busca ou prepara funcionário (usado nos dois formatos) ─────────────────
    def _resolver_funcionario(self, nome, admin_id, valor_diaria=0, valor_va=0, valor_vt=0):
        """
        Busca funcionário por nome. Se não encontrado, prepara dict de criação.
        Retorna (func_id_ou_None, nome_normalizado, func_criar, aviso)
        """
        from models import Funcionario
        func = (Funcionario.query
                .filter(Funcionario.nome.ilike(nome), Funcionario.admin_id == admin_id)
                .first())
        if func:
            return func.id, func.nome, False, None
        # Não encontrado → será criado no importar()
        aviso = f'Funcionário "{nome}" não encontrado — será criado automaticamente'
        return None, nome.title(), True, aviso

    # ── Busca ou prepara obra (usado nos dois formatos) ────────────────────────
    def _resolver_obra(self, obra_raw, admin_id):
        """
        Busca obra por nome/código. Se não encontrada, prepara criação automática.
        Retorna (obra_id_ou_None, obra_nome, obra_criar)
        """
        from models import Obra
        if not obra_raw:
            return None, '(sem obra)', False
        obra = (Obra.query
                .filter(Obra.admin_id == admin_id)
                .filter((Obra.nome.ilike(obra_raw)) | (Obra.codigo == obra_raw))
                .first())
        if obra:
            return obra.id, obra.nome, False
        # Não encontrada → será criada automaticamente
        return None, obra_raw.title(), True

    # ── FORMATO COLABORADORES ──────────────────────────────────────────────────
    def _processar_colaboradores(self, ws, admin_id):
        """
        Formato: linha com COLABORADOR define o funcionário atual.
        A seguir, cabeçalho DATA | DIA DA SEMANA | CENTRO DE CUSTO | $ DIÁRIA | $ VT | $ VA
        Depois, linhas de dados.
        """
        validos, erros, avisos = [], [], []
        funcionario_nome = None
        em_dados = False
        col_data = col_cc = col_diaria = col_vt = col_va = None

        for rn in range(1, ws.max_row + 1):
            row = [ws.cell(rn, c).value for c in range(1, ws.max_column + 1)]

            # ── Detecta linha COLABORADOR ──────────────────────────────────────
            primeira = _norm(row[0]).upper()
            if 'COLABORADOR' in primeira:
                # Nome pode estar na coluna A, B ou C dependendo do layout
                for ci in range(len(row) - 1, -1, -1):
                    v = _norm(row[ci])
                    if v and v.upper() not in ('COLABORADOR',):
                        funcionario_nome = v.strip()
                        break
                em_dados = False
                col_data = col_cc = col_diaria = col_vt = col_va = None
                continue

            # ── Detecta linha de cabeçalho ──────────────────────────────────
            normalized_row = [_norm(v).upper() for v in row]
            if 'DATA' in normalized_row and ('DIÁRIA' in ' '.join(normalized_row) or 'DIARIA' in ' '.join(normalized_row)):
                col_data = next((i for i, v in enumerate(normalized_row) if v == 'DATA'), None)
                col_cc = next((i for i, v in enumerate(normalized_row)
                               if 'CENTRO' in v or 'CUSTO' in v or 'OBRA' in v), None)
                col_diaria = next((i for i, v in enumerate(normalized_row)
                                   if 'DIÁRIA' in v or 'DIARIA' in v), None)
                col_vt = next((i for i, v in enumerate(normalized_row) if 'VT' in v), None)
                col_va = next((i for i, v in enumerate(normalized_row) if 'VA' in v), None)
                em_dados = True
                continue

            # ── Processa linha de dados ────────────────────────────────────
            if not em_dados or funcionario_nome is None:
                continue

            data_ref = _parse_data(row[col_data] if col_data is not None else None)
            if not data_ref:
                continue  # linha sem data válida → pula silenciosamente (DOMINGO vazio etc.)

            obra_raw = _norm(row[col_cc] if col_cc is not None else None)
            valor_d = _parse_float(row[col_diaria] if col_diaria is not None else 0)
            valor_vt_ = _parse_float(row[col_vt] if col_vt is not None else 0)
            valor_va_ = _parse_float(row[col_va] if col_va is not None else 0)

            # Linhas sem obra e sem valores → dia de descanso, pula
            if not obra_raw and valor_d == 0 and valor_vt_ == 0 and valor_va_ == 0:
                continue

            tipo_lancamento = _detectar_tipo_lancamento(obra_raw)

            # Validação de valor: se não for tipo especial, precisa de valor
            if tipo_lancamento is None and valor_d <= 0:
                # Sem tipo especial e sem valor → pula silenciosamente
                continue

            func_id, func_nome, func_criar, aviso = self._resolver_funcionario(
                funcionario_nome, admin_id, valor_d, valor_va_, valor_vt_)
            if aviso:
                avisos.append({'linha': rn, 'nome': func_nome, 'motivo': aviso})

            if tipo_lancamento:
                obra_id, obra_nome, obra_criar = None, obra_raw.title(), False
            else:
                obra_id, obra_nome, obra_criar = self._resolver_obra(obra_raw, admin_id)

            row_dict = {
                'linha': rn,
                'nome': func_nome,
                'funcionario_id': func_id,
                'func_criar': func_criar,
                'func_valores': {'valor_diaria': valor_d, 'valor_va': valor_va_, 'valor_vt': valor_vt_}
                                if func_criar else None,
                'data': str(data_ref),
                'valor_diaria': valor_d,
                'valor_va': valor_va_,
                'valor_vt': valor_vt_,
                'obra_id': obra_id,
                'obra_nome': obra_nome,
                'obra_criar': obra_criar,
                'obra_raw': obra_raw,
                'tipo_lancamento': tipo_lancamento or 'diaria_completa',
                'tipo_label': _TIPO_LABELS.get(tipo_lancamento or 'diaria_completa', ''),
                'status': 'PENDENTE',
            }
            validos.append(row_dict)

        # Avisos integrados como "erros" não-bloqueantes para exibição no preview
        return validos, avisos

    # ── FORMATO SIGE ──────────────────────────────────────────────────────────
    def _processar_sige(self, ws, admin_id):
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

            obra_raw = _norm(c('obra', 'obra_id', 'codigo_obra', 'centro_custo', 'centro de custo'))
            tipo_lancamento = _detectar_tipo_lancamento(obra_raw)

            func_id, func_nome, func_criar, aviso = self._resolver_funcionario(nome, admin_id)
            if aviso and not func_criar:
                erros.append({'linha': rn, 'nome': nome, 'motivo': aviso})
                continue

            # Valor: da planilha se informado, senão do cadastro
            valor_d = _parse_float(c('valor_diaria', 'valor', '$ diária', 'diaria'))
            valor_va_ = _parse_float(c('valor_va', 'va', '$ va'))
            valor_vt_ = _parse_float(c('valor_vt', 'vt', '$ vt'))

            if not func_criar:
                from models import Funcionario
                func = Funcionario.query.get(func_id)
                if func:
                    if valor_d <= 0: valor_d = float(func.valor_diaria or 0)
                    if valor_va_ <= 0: valor_va_ = float(func.valor_va or 0)
                    if valor_vt_ <= 0: valor_vt_ = float(func.valor_vt or 0)

            if tipo_lancamento is None and valor_d <= 0:
                erros.append({'linha': rn, 'nome': func_nome,
                              'motivo': 'Funcionário não tem valor de diária cadastrado no perfil'})
                continue

            if tipo_lancamento:
                obra_id, obra_nome, obra_criar = None, (obra_raw.title() if obra_raw else ''), False
            else:
                obra_id, obra_nome, obra_criar = self._resolver_obra(obra_raw, admin_id)

            validos.append({
                'linha': rn,
                'nome': func_nome,
                'funcionario_id': func_id,
                'func_criar': func_criar,
                'func_valores': {'valor_diaria': valor_d, 'valor_va': valor_va_, 'valor_vt': valor_vt_}
                                if func_criar else None,
                'data': str(data_ref),
                'valor_diaria': valor_d,
                'valor_va': valor_va_,
                'valor_vt': valor_vt_,
                'obra_id': obra_id,
                'obra_nome': obra_nome,
                'obra_criar': obra_criar,
                'obra_raw': obra_raw,
                'tipo_lancamento': tipo_lancamento or 'diaria_completa',
                'tipo_label': _TIPO_LABELS.get(tipo_lancamento or 'diaria_completa', ''),
                'status': _norm(c('status')) or 'PENDENTE',
            })

        return validos, erros

    # ── Entry point ───────────────────────────────────────────────────────────
    def processar(self, ws, admin_id):
        if self._is_formato_colaboradores(ws):
            return self._processar_colaboradores(ws, admin_id)
        return self._processar_sige(ws, admin_id)

    # ── importar ──────────────────────────────────────────────────────────────
    def importar(self, rows, admin_id):
        from models import db, Funcionario, Obra
        from utils.financeiro_integration import registrar_custo_automatico
        import random, string
        criados, erros = 0, []

        # Cache de obras e funcionários criados nesta importação para reusar IDs
        obras_criadas = {}      # obra_raw_upper → obra_id
        funcs_criados = {}      # nome_upper → func_id

        for row in rows:
            try:
                data_ref = _parse_data(row['data'])
                linha = row['linha']
                nome = row['nome']
                tipo = row.get('tipo_lancamento', 'diaria_completa')

                # ── Tipo "sem_lancamento": só registro, sem custo ──────────
                if tipo == 'sem_lancamento':
                    criados += 1
                    continue

                # ── Resolver / criar funcionário ──────────────────────────
                func_id = row.get('funcionario_id')
                if row.get('func_criar') and not func_id:
                    nome_up = nome.upper()
                    if nome_up in funcs_criados:
                        func_id = funcs_criados[nome_up]
                    else:
                        # Gera CPF temporário único (até 14 chars)
                        cpf_tmp = f"TMP{random.randint(10000000000, 99999999999)}"
                        # Garante unicidade consultando o DB
                        while Funcionario.query.filter_by(cpf=cpf_tmp).first():
                            cpf_tmp = f"TMP{random.randint(10000000000, 99999999999)}"

                        # Busca max codigo VV global (constraint global)
                        ultimo_vv = (Funcionario.query
                                     .filter(Funcionario.codigo.like('VV%'))
                                     .order_by(Funcionario.codigo.desc()).first())
                        try:
                            proximo_vv = int(ultimo_vv.codigo[2:]) + 1 if ultimo_vv else 1
                        except Exception:
                            proximo_vv = 1
                        # Garante unicidade do código
                        while Funcionario.query.filter(
                            Funcionario.codigo == f"VV{proximo_vv:03d}",
                            Funcionario.admin_id == admin_id
                        ).first():
                            proximo_vv += 1

                        vals = row.get('func_valores') or {}
                        novo_func = Funcionario(
                            codigo=f"VV{proximo_vv:03d}",
                            nome=nome,
                            cpf=cpf_tmp,
                            tipo_remuneracao='diaria',
                            valor_diaria=float(vals.get('valor_diaria', row.get('valor_diaria', 0))),
                            valor_va=float(vals.get('valor_va', row.get('valor_va', 0))),
                            valor_vt=float(vals.get('valor_vt', row.get('valor_vt', 0))),
                            data_admissao=data_ref,
                            ativo=True,
                            admin_id=admin_id,
                        )
                        db.session.add(novo_func)
                        db.session.flush()  # obtém ID sem commit
                        func_id = novo_func.id
                        funcs_criados[nome_up] = func_id

                # ── Resolver / criar obra ─────────────────────────────────
                obra_id = row.get('obra_id')
                if row.get('obra_criar') and not obra_id:
                    obra_raw = row.get('obra_raw', row.get('obra_nome', ''))
                    obra_up = obra_raw.strip().upper()
                    if obra_up in obras_criadas:
                        obra_id = obras_criadas[obra_up]
                    else:
                        nova_obra = Obra(
                            nome=obra_raw.title(),
                            codigo=None,   # sem código — editável depois
                            data_inicio=data_ref,
                            admin_id=admin_id,
                            ativo=True,
                        )
                        db.session.add(nova_obra)
                        db.session.flush()
                        obra_id = nova_obra.id
                        obras_criadas[obra_up] = obra_id

                # ── Lançamentos financeiros ───────────────────────────────
                data_fmt = data_ref.strftime('%d/%m/%Y')
                origem_sfx = f"{func_id}_{data_fmt.replace('/','')}"

                # Diária — sempre (exceto sem_lancamento já tratado acima)
                filho = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='SALARIO',
                    entidade_nome=nome,
                    entidade_id=func_id,
                    data=data_ref,
                    descricao=f'Diária - {nome} - {data_fmt}',
                    valor=row.get('valor_diaria', 0),
                    obra_id=obra_id,
                    origem_tabela='importacao_diaria',
                    origem_id=origem_sfx,
                )
                if not filho:
                    erros.append({'linha': linha, 'nome': nome,
                                  'motivo': 'Erro ao registrar custo da diária'})
                    db.session.rollback()
                    continue

                # VA e VT — somente se tipo for diaria_completa
                if tipo == 'diaria_completa':
                    if row.get('valor_va', 0) > 0:
                        registrar_custo_automatico(
                            admin_id=admin_id,
                            tipo_categoria='ALIMENTACAO',
                            entidade_nome=nome,
                            entidade_id=func_id,
                            data=data_ref,
                            descricao=f'VA - {nome} - {data_fmt}',
                            valor=row['valor_va'],
                            obra_id=obra_id,
                            origem_tabela='importacao_diaria_va',
                            origem_id=origem_sfx,
                        )
                    if row.get('valor_vt', 0) > 0:
                        registrar_custo_automatico(
                            admin_id=admin_id,
                            tipo_categoria='TRANSPORTE',
                            entidade_nome=nome,
                            entidade_id=func_id,
                            data=data_ref,
                            descricao=f'VT - {nome} - {data_fmt}',
                            valor=row['valor_vt'],
                            obra_id=obra_id,
                            origem_tabela='importacao_diaria_vt',
                            origem_id=origem_sfx,
                        )
                # tipo 'somente_diaria' (ATESTADO) → só diária, sem VA/VT

                db.session.commit()
                criados += 1

            except Exception as e:
                db.session.rollback()
                erros.append({'linha': row.get('linha'), 'nome': row.get('nome'), 'motivo': str(e)})

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
            if not obra_raw:
                erros.append({'linha': rn, 'nome': str(data_ref),
                              'motivo': 'Obra obrigatória para lançamento de alimentação'})
                continue
            obra = (Obra.query.filter(Obra.admin_id == admin_id)
                    .filter((Obra.nome.ilike(obra_raw)) | (Obra.codigo == obra_raw))
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
                         .filter(Funcionario.nome.ilike(fn), Funcionario.admin_id == admin_id)
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
        from models import Funcionario, Obra, CategoriaTransporte

        header_row, raw_headers = _detectar_header_row(ws, ['nome_funcionario', 'funcionario', 'nome'])
        if not header_row:
            return [], [{'linha': '?', 'nome': '—', 'motivo': 'Cabeçalho não encontrado'}]

        hm = _mapear_headers(raw_headers)
        validos, erros = [], []

        # Cache de categorias para evitar N queries
        categorias_cache = {
            c.nome.lower(): c
            for c in CategoriaTransporte.query.filter_by(admin_id=admin_id).all()
        }

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
                    .filter(Funcionario.nome.ilike(nome), Funcionario.admin_id == admin_id)
                    .first())
            if not func:
                erros.append({'linha': rn, 'nome': nome, 'motivo': f'Funcionário "{nome}" não encontrado'})
                continue

            obra_raw = _norm(c('obra'))
            obra = None
            if obra_raw:
                obra = (Obra.query.filter(Obra.admin_id == admin_id)
                        .filter((Obra.nome.ilike(obra_raw)) | (Obra.codigo == obra_raw))
                        .first())
                if not obra:
                    erros.append({'linha': rn, 'nome': nome,
                                  'motivo': f'Obra "{obra_raw}" não encontrada'})
                    continue

            # Busca CategoriaTransporte por nome (case-insensitive)
            categoria_raw = _norm(c('categoria')) or ''
            cat_obj = categorias_cache.get(categoria_raw.lower())
            if not cat_obj and categoria_raw:
                # Busca direta caso não esteja no cache (criado após o cache)
                cat_obj = CategoriaTransporte.query.filter(
                    CategoriaTransporte.nome.ilike(categoria_raw),
                    CategoriaTransporte.admin_id == admin_id,
                ).first()
            if not cat_obj:
                erros.append({
                    'linha': rn, 'nome': nome,
                    'motivo': (
                        f'Categoria de transporte "{categoria_raw}" não encontrada. '
                        f'Disponíveis: {", ".join(categorias_cache.keys()) or "nenhuma cadastrada"}'
                    ),
                })
                continue

            validos.append({
                'linha': rn,
                'nome': func.nome,
                'funcionario_id': func.id,
                'data': str(data_ref),
                'valor': valor,
                'categoria': cat_obj.nome,
                'categoria_id': cat_obj.id,
                'obra_id': obra.id if obra else None,
                'obra_nome': obra.nome if obra else '(sem obra)',
                'descricao': _norm(c('descricao')) or f'{cat_obj.nome} - {func.nome} - {data_ref.strftime("%d/%m/%Y")}',
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
                        .filter((Obra.nome.ilike(obra_raw)) | (Obra.codigo == obra_raw))
                        .first())
                if not obra:
                    erros.append({'linha': rn, 'nome': fornecedor or descricao,
                                  'motivo': f'Obra/centro de custo "{obra_raw}" não encontrado'})
                    continue

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
