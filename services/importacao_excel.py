"""
Serviço de Importação Excel para o SIGE v9.0
Suporta 5 módulos:
  1. Funcionários (formato SIGE + formato REGISTRO_COLABORADORES)
  2. Diárias (ponto eletrônico / registros manuais)
  3. Alimentação
  4. Transporte
  5. Custos / Gestão de Custos V2
"""
import logging
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalizar_texto(v):
    if v is None:
        return ''
    return str(v).strip()

def _parse_data(v):
    """Converte string DD/MM/AAAA, AAAA-MM-DD ou objeto date/datetime → date."""
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    s = _normalizar_texto(v)
    if not s:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _parse_float(v, default=0.0):
    s = _normalizar_texto(v).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return default

def _normalizar_cpf(cpf_raw):
    """Remove pontuação, retorna string limpa de 11 dígitos."""
    import re
    cpf = re.sub(r'\D', '', _normalizar_texto(cpf_raw))
    return cpf[:11] if cpf else ''

def _mapear_headers(row):
    """Converte lista de headers para dict {header_normalizado: col_index}."""
    import unicodedata
    def normalizar(s):
        s = _normalizar_texto(s).lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = s.replace(' ', '_').replace('-', '_').replace('/', '_')
        return s
    return {normalizar(str(cell)): idx for idx, cell in enumerate(row)}

# ── Detecção de formato ────────────────────────────────────────────────────────

def detectar_formato_funcionarios(headers_map):
    """
    Retorna 'sige' ou 'colaboradores' conforme os cabeçalhos encontrados.
    Formato SIGE:          nome, cpf, tipo_remuneracao ...
    Formato COLABORADORES: nome, remuneracao, valor (header na linha 3, dado na 4+)
    """
    if 'tipo_remuneracao' in headers_map or 'data_admissao' in headers_map:
        return 'sige'
    # Formato REGISTRO_COLABORADORES: tem "remuneracao" e "valor" mas não "tipo_remuneracao"
    if 'remuneracao' in headers_map and 'valor' in headers_map:
        return 'colaboradores'
    return 'sige'

# ── MÓDULO 1: Funcionários ─────────────────────────────────────────────────────

def importar_funcionarios(ws, admin_id, inicio_linha=4):
    """
    Importa funcionários de planilha.
    Tenta detectar automaticamente o formato pelo cabeçalho.
    Retorna dict: {importados, atualizados, erros, detalhes}
    """
    from models import db, Funcionario, Departamento, Funcao

    resultado = {'importados': 0, 'atualizados': 0, 'erros': 0, 'detalhes': []}

    # ── Ler cabeçalho ──────────────────────────────────────────────────────────
    # Tentar linha 3 primeiro (formato padrão), senão linha 1
    header_row = None
    for tentativa in [3, 1, 2]:
        row_vals = [ws.cell(row=tentativa, column=c).value for c in range(1, ws.max_column + 1)]
        if any(v for v in row_vals):
            # Verifica se tem pelo menos "nome" ou "nome *"
            import unicodedata
            def norm(s):
                s = _normalizar_texto(s).lower()
                s = unicodedata.normalize('NFD', s)
                s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
                s = s.replace(' ', '_').replace('-', '_').replace('*', '').strip()
                return s
            normalized = [norm(str(v)) for v in row_vals]
            if 'nome' in normalized:
                header_row = tentativa
                inicio_linha = tentativa + 1
                break

    if header_row is None:
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'N/A', 'status': 'erro', 'mensagem': 'Cabeçalho não encontrado'})
        return resultado

    raw_headers = [ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)]
    hm = _mapear_headers(raw_headers)

    # Remover asteriscos dos nomes de chave
    hm_clean = {}
    for k, v in hm.items():
        clean_k = k.replace('*', '').strip('_').strip()
        hm_clean[clean_k] = v
    hm = hm_clean

    formato = detectar_formato_funcionarios(hm)
    logger.info(f"[IMPORT] Formato detectado: {formato}, início linha {inicio_linha}")

    # ── Processar linhas de dados ──────────────────────────────────────────────
    for row_num in range(inicio_linha, ws.max_row + 1):
        def cel(key, aliases=None):
            """Pega valor de célula pela chave do header_map com suporte a aliases."""
            keys_to_try = [key] + (aliases or [])
            for k in keys_to_try:
                if k in hm:
                    v = ws.cell(row=row_num, column=hm[k] + 1).value
                    return v
            return None

        nome = _normalizar_texto(cel('nome'))
        if not nome or nome.upper() in ('NOME', 'NOME *', '-', '#N/A'):
            continue

        cpf_raw = cel('cpf')
        if not cpf_raw:
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'nome': nome, 'status': 'erro', 'mensagem': 'CPF não informado'})
            continue
        cpf = _normalizar_cpf(cpf_raw)
        if len(cpf) < 11:
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'nome': nome, 'status': 'erro', 'mensagem': f'CPF inválido: {cpf_raw}'})
            continue

        try:
            # ── Campos comuns ──────────────────────────────────────────────────
            rg = _normalizar_texto(cel('rg'))
            telefone = _normalizar_texto(cel('telefone', ['tel', 'telefone_whatsapp']))
            endereco = _normalizar_texto(cel('endereco', ['endereco_completo']))
            chave_pix = _normalizar_texto(cel('chave_pix', ['pix', 'chavepix']))
            data_nasc_raw = cel('data_nascimento', ['data_nasc', 'data_nasc_', 'datanascimento'])
            data_nasc = _parse_data(data_nasc_raw)

            status_raw = _normalizar_texto(cel('status')).upper()
            ativo = status_raw != 'INATIVO'

            # ── Campos de remuneração (adaptar conforme formato) ────────────────
            if formato == 'colaboradores':
                remuneracao_raw = _normalizar_texto(cel('remuneracao')).upper()
                if 'DIARIA' in remuneracao_raw or 'DIÁRIA' in remuneracao_raw:
                    tipo_remuneracao = 'diaria'
                else:
                    tipo_remuneracao = 'salario'
                valor_raw = cel('valor')
                valor = _parse_float(valor_raw)
                # No formato COLABORADORES, não há data_admissao — usar hoje
                data_admissao_raw = cel('data_admissao', ['data_admissao', 'admissao'])
                data_admissao = _parse_data(data_admissao_raw) or date.today()
            else:  # sige
                tipo_remuneracao_raw = _normalizar_texto(cel('tipo_remuneracao', ['tipo_remuneracao_'])).lower()
                if 'diaria' in tipo_remuneracao_raw or 'diária' in tipo_remuneracao_raw:
                    tipo_remuneracao = 'diaria'
                else:
                    tipo_remuneracao = 'salario'
                valor_raw = cel('valor', ['valor_diaria', 'salario', 'remuneracao'])
                valor = _parse_float(valor_raw)
                data_admissao_raw = cel('data_admissao', ['admissao', 'data_de_admissao'])
                data_admissao = _parse_data(data_admissao_raw) or date.today()

            valor_va = _parse_float(cel('valor_va', ['va', 'vale_alimentacao']))
            valor_vt = _parse_float(cel('valor_vt', ['vt', 'vale_transporte']))

            # ── Upsert ────────────────────────────────────────────────────────
            existente = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
            if existente:
                existente.nome = nome
                existente.rg = rg or existente.rg
                existente.telefone = telefone or existente.telefone
                existente.endereco = endereco or existente.endereco
                if chave_pix:
                    existente.chave_pix = chave_pix
                if data_nasc:
                    existente.data_nascimento = data_nasc
                existente.ativo = ativo
                existente.tipo_remuneracao = tipo_remuneracao
                if tipo_remuneracao == 'diaria' and valor > 0:
                    existente.valor_diaria = valor
                elif tipo_remuneracao == 'salario' and valor > 0:
                    existente.salario = valor
                if valor_va > 0:
                    existente.valor_va = valor_va
                if valor_vt > 0:
                    existente.valor_vt = valor_vt
                resultado['atualizados'] += 1
                resultado['detalhes'].append({'linha': row_num, 'nome': nome, 'cpf': cpf, 'status': 'atualizado'})
            else:
                # Código automático VV###
                ultimo = Funcionario.query.filter(
                    Funcionario.codigo.like('VV%'),
                    Funcionario.admin_id == admin_id
                ).order_by(Funcionario.codigo.desc()).first()
                try:
                    proximo_num = int(ultimo.codigo[2:]) + 1 if ultimo else 1
                except Exception:
                    proximo_num = 1
                codigo = f"VV{proximo_num:03d}"

                kwargs = dict(
                    nome=nome, cpf=cpf, rg=rg or None, telefone=telefone or None,
                    endereco=endereco or None, chave_pix=chave_pix or None,
                    data_nascimento=data_nasc, ativo=ativo, admin_id=admin_id,
                    codigo=codigo, tipo_remuneracao=tipo_remuneracao,
                    data_admissao=data_admissao, valor_va=valor_va, valor_vt=valor_vt,
                )
                if tipo_remuneracao == 'diaria':
                    kwargs['valor_diaria'] = valor
                    kwargs['salario'] = 0
                else:
                    kwargs['salario'] = valor
                    kwargs['valor_diaria'] = 0

                func = Funcionario(**kwargs)
                db.session.add(func)
                resultado['importados'] += 1
                resultado['detalhes'].append({'linha': row_num, 'nome': nome, 'cpf': cpf, 'status': 'importado', 'codigo': codigo})

            db.session.flush()

        except Exception as e:
            logger.error(f"[IMPORT] Erro na linha {row_num}: {e}", exc_info=True)
            db.session.rollback()
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'nome': nome, 'status': 'erro', 'mensagem': str(e)})

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"[IMPORT] Erro ao commitar funcionários: {e}")
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'COMMIT', 'status': 'erro', 'mensagem': str(e)})

    return resultado


# ── MÓDULO 2: Diárias ──────────────────────────────────────────────────────────

def importar_diarias(ws, admin_id, inicio_linha=4):
    """
    Importa registros de ponto (diárias) para diaristas V2.
    Colunas esperadas: cpf_funcionario, data, obra_id/obra_codigo, tipo_ponto, horas_trabalhadas
    """
    from models import db, Funcionario, Obra, RegistroPonto
    from event_manager import fire_event

    resultado = {'importados': 0, 'erros': 0, 'detalhes': []}

    # Detectar cabeçalho
    header_row = None
    for tentativa in [3, 1, 2]:
        row_vals = [ws.cell(row=tentativa, column=c).value for c in range(1, ws.max_column + 1)]
        import unicodedata
        def norm(s):
            s = _normalizar_texto(s).lower()
            s = unicodedata.normalize('NFD', s)
            s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
            s = s.replace(' ', '_').replace('*', '').strip()
            return s
        normalized = [norm(str(v)) for v in row_vals]
        if any(x in normalized for x in ['cpf', 'cpf_funcionario', 'funcionario']):
            header_row = tentativa
            inicio_linha = tentativa + 1
            break

    if header_row is None:
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'N/A', 'status': 'erro', 'mensagem': 'Cabeçalho não encontrado'})
        return resultado

    raw_headers = [ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)]
    hm_raw = _mapear_headers(raw_headers)
    hm = {k.replace('*', '').strip('_'): v for k, v in hm_raw.items()}

    for row_num in range(inicio_linha, ws.max_row + 1):
        def cel(key, aliases=None):
            for k in [key] + (aliases or []):
                if k in hm:
                    return ws.cell(row=row_num, column=hm[k] + 1).value
            return None

        cpf_raw = cel('cpf', ['cpf_funcionario'])
        data_raw = cel('data', ['data_ponto', 'data_diaria'])
        if not cpf_raw or not data_raw:
            continue

        cpf = _normalizar_cpf(cpf_raw)
        data_ponto = _parse_data(data_raw)
        if not data_ponto:
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': f'Data inválida: {data_raw}'})
            continue

        try:
            funcionario = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
            if not funcionario:
                resultado['erros'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': f'Funcionário CPF {cpf} não encontrado'})
                continue

            # Obra
            obra_id = None
            obra_raw = cel('obra_id', ['obra', 'obra_codigo', 'codigo_obra'])
            if obra_raw:
                try:
                    obra_id = int(obra_raw)
                except (ValueError, TypeError):
                    obra = Obra.query.filter_by(codigo=str(obra_raw).strip(), admin_id=admin_id).first()
                    if obra:
                        obra_id = obra.id

            # Idempotência
            ja_existe = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_ponto,
                tipo_ponto='entrada',
                admin_id=admin_id
            ).first()
            if ja_existe:
                resultado['detalhes'].append({'linha': row_num, 'status': 'skip', 'mensagem': f'Registro de {funcionario.nome} em {data_ponto} já existe'})
                continue

            tipo_ponto = _normalizar_texto(cel('tipo_ponto')).lower() or 'entrada'
            horas = _parse_float(cel('horas_trabalhadas', ['horas']), 8.0)

            reg = RegistroPonto(
                funcionario_id=funcionario.id,
                data=data_ponto,
                tipo_ponto=tipo_ponto,
                horas_trabalhadas=horas,
                obra_id=obra_id,
                admin_id=admin_id,
            )
            db.session.add(reg)
            db.session.flush()

            # Disparar evento para criar custo automático
            fire_event('ponto_registrado', {'registro_id': reg.id, 'tipo_ponto': tipo_ponto}, admin_id)

            resultado['importados'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'importado', 'nome': funcionario.nome, 'data': str(data_ponto)})

        except Exception as e:
            logger.error(f"[IMPORT DIARIA] Linha {row_num}: {e}", exc_info=True)
            db.session.rollback()
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': str(e)})

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'COMMIT', 'status': 'erro', 'mensagem': str(e)})

    return resultado


# ── MÓDULO 3: Alimentação ──────────────────────────────────────────────────────

def importar_alimentacao(ws, admin_id, inicio_linha=4):
    """
    Colunas: cpf_funcionario|nome_funcionario, data, descricao, valor, obra_id
    """
    from models import db, Funcionario, Obra, AlimentacaoLancamento
    from utils.financeiro_integration import registrar_custo_automatico

    resultado = {'importados': 0, 'erros': 0, 'detalhes': []}

    header_row = _detectar_linha_header(ws, ['cpf', 'nome', 'funcionario', 'descricao'])
    if header_row is None:
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'N/A', 'status': 'erro', 'mensagem': 'Cabeçalho não encontrado'})
        return resultado

    raw_headers = [ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)]
    hm = {k.replace('*', '').strip('_'): v for k, v in _mapear_headers(raw_headers).items()}

    for row_num in range(header_row + 1, ws.max_row + 1):
        def cel(key, aliases=None):
            for k in [key] + (aliases or []):
                if k in hm:
                    return ws.cell(row=row_num, column=hm[k] + 1).value
            return None

        data_raw = cel('data', ['data_lancamento'])
        valor_raw = cel('valor')
        if not data_raw or not valor_raw:
            continue

        data_ref = _parse_data(data_raw)
        valor = _parse_float(valor_raw)
        if not data_ref or valor <= 0:
            continue

        descricao = _normalizar_texto(cel('descricao', ['item', 'refeicao'])) or 'Alimentação importada'

        # Buscar funcionário por CPF ou nome
        funcionario = None
        cpf_raw = cel('cpf', ['cpf_funcionario'])
        nome_raw = cel('nome', ['nome_funcionario', 'funcionario'])
        if cpf_raw:
            cpf = _normalizar_cpf(cpf_raw)
            funcionario = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
        if not funcionario and nome_raw:
            nome_busca = _normalizar_texto(nome_raw)
            funcionario = Funcionario.query.filter(
                Funcionario.nome.ilike(f'%{nome_busca}%'),
                Funcionario.admin_id == admin_id
            ).first()

        obra_id = None
        obra_raw = cel('obra_id', ['obra', 'codigo_obra'])
        if obra_raw:
            try:
                obra_id = int(obra_raw)
            except (ValueError, TypeError):
                obra = Obra.query.filter_by(codigo=str(obra_raw).strip(), admin_id=admin_id).first()
                if obra:
                    obra_id = obra.id

        try:
            filho = registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='ALIMENTACAO',
                entidade_nome=funcionario.nome if funcionario else 'Importação Excel',
                entidade_id=funcionario.id if funcionario else None,
                data=data_ref,
                descricao=descricao,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='importacao_alimentacao',
                origem_id=row_num,
            )
            if filho:
                db.session.commit()
                resultado['importados'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'importado', 'valor': valor, 'data': str(data_ref)})
            else:
                resultado['erros'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': 'registrar_custo_automatico retornou None'})
        except Exception as e:
            logger.error(f"[IMPORT ALIMENTACAO] Linha {row_num}: {e}", exc_info=True)
            db.session.rollback()
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': str(e)})

    return resultado


# ── MÓDULO 4: Transporte ───────────────────────────────────────────────────────

def importar_transporte(ws, admin_id, inicio_linha=4):
    """
    Colunas: cpf_funcionario|nome_funcionario, data, descricao, valor, obra_id, categoria
    """
    from models import db, Funcionario, Obra
    from utils.financeiro_integration import registrar_custo_automatico

    resultado = {'importados': 0, 'erros': 0, 'detalhes': []}

    header_row = _detectar_linha_header(ws, ['cpf', 'nome', 'funcionario', 'valor'])
    if header_row is None:
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'N/A', 'status': 'erro', 'mensagem': 'Cabeçalho não encontrado'})
        return resultado

    raw_headers = [ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)]
    hm = {k.replace('*', '').strip('_'): v for k, v in _mapear_headers(raw_headers).items()}

    for row_num in range(header_row + 1, ws.max_row + 1):
        def cel(key, aliases=None):
            for k in [key] + (aliases or []):
                if k in hm:
                    return ws.cell(row=row_num, column=hm[k] + 1).value
            return None

        data_raw = cel('data', ['data_lancamento'])
        valor_raw = cel('valor')
        if not data_raw or not valor_raw:
            continue

        data_ref = _parse_data(data_raw)
        valor = _parse_float(valor_raw)
        if not data_ref or valor <= 0:
            continue

        descricao = _normalizar_texto(cel('descricao', ['tipo', 'categoria'])) or 'Transporte importado'

        funcionario = None
        cpf_raw = cel('cpf', ['cpf_funcionario'])
        nome_raw = cel('nome', ['nome_funcionario', 'funcionario'])
        if cpf_raw:
            cpf = _normalizar_cpf(cpf_raw)
            funcionario = Funcionario.query.filter_by(cpf=cpf, admin_id=admin_id).first()
        if not funcionario and nome_raw:
            nome_busca = _normalizar_texto(nome_raw)
            funcionario = Funcionario.query.filter(
                Funcionario.nome.ilike(f'%{nome_busca}%'),
                Funcionario.admin_id == admin_id
            ).first()

        obra_id = None
        obra_raw = cel('obra_id', ['obra', 'codigo_obra'])
        if obra_raw:
            try:
                obra_id = int(obra_raw)
            except (ValueError, TypeError):
                obra = Obra.query.filter_by(codigo=str(obra_raw).strip(), admin_id=admin_id).first()
                if obra:
                    obra_id = obra.id

        try:
            filho = registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='TRANSPORTE',
                entidade_nome=funcionario.nome if funcionario else 'Importação Excel',
                entidade_id=funcionario.id if funcionario else None,
                data=data_ref,
                descricao=descricao,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='importacao_transporte',
                origem_id=row_num,
            )
            if filho:
                db.session.commit()
                resultado['importados'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'importado', 'valor': valor, 'data': str(data_ref)})
            else:
                resultado['erros'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': 'registrar_custo_automatico retornou None'})
        except Exception as e:
            logger.error(f"[IMPORT TRANSPORTE] Linha {row_num}: {e}", exc_info=True)
            db.session.rollback()
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': str(e)})

    return resultado


# ── MÓDULO 5: Custos Gerais ────────────────────────────────────────────────────

def importar_custos(ws, admin_id, inicio_linha=4):
    """
    Colunas: data, descricao, categoria, valor, obra_id, fornecedor
    """
    from models import db, Obra
    from utils.financeiro_integration import registrar_custo_automatico

    resultado = {'importados': 0, 'erros': 0, 'detalhes': []}

    header_row = _detectar_linha_header(ws, ['descricao', 'valor', 'categoria'])
    if header_row is None:
        resultado['erros'] += 1
        resultado['detalhes'].append({'linha': 'N/A', 'status': 'erro', 'mensagem': 'Cabeçalho não encontrado'})
        return resultado

    raw_headers = [ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)]
    hm = {k.replace('*', '').strip('_'): v for k, v in _mapear_headers(raw_headers).items()}

    CATEGORIAS_VALIDAS = {'SALARIO', 'ALIMENTACAO', 'TRANSPORTE', 'MATERIAL', 'COMPRA', 'DESPESA_GERAL', 'REEMBOLSO'}

    for row_num in range(header_row + 1, ws.max_row + 1):
        def cel(key, aliases=None):
            for k in [key] + (aliases or []):
                if k in hm:
                    return ws.cell(row=row_num, column=hm[k] + 1).value
            return None

        descricao = _normalizar_texto(cel('descricao', ['item', 'historico']))
        valor_raw = cel('valor', ['valor_total'])
        if not descricao or not valor_raw:
            continue

        valor = _parse_float(valor_raw)
        if valor <= 0:
            continue

        data_raw = cel('data', ['data_lancamento', 'data_custo', 'data_vencimento'])
        data_ref = _parse_data(data_raw) or date.today()

        categoria_raw = _normalizar_texto(cel('categoria', ['tipo', 'tipo_categoria'])).upper()
        if categoria_raw not in CATEGORIAS_VALIDAS:
            categoria_raw = 'DESPESA_GERAL'

        entidade_nome = _normalizar_texto(cel('fornecedor', ['nome', 'empresa'])) or 'Importação Excel'

        obra_id = None
        obra_raw = cel('obra_id', ['obra', 'codigo_obra'])
        if obra_raw:
            try:
                obra_id = int(obra_raw)
            except (ValueError, TypeError):
                obra = Obra.query.filter_by(codigo=str(obra_raw).strip(), admin_id=admin_id).first()
                if obra:
                    obra_id = obra.id

        try:
            filho = registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria=categoria_raw,
                entidade_nome=entidade_nome,
                entidade_id=None,
                data=data_ref,
                descricao=descricao,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='importacao_custo',
                origem_id=row_num,
            )
            if filho:
                db.session.commit()
                resultado['importados'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'importado', 'descricao': descricao, 'valor': valor})
            else:
                resultado['erros'] += 1
                resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': 'registrar_custo_automatico retornou None'})
        except Exception as e:
            logger.error(f"[IMPORT CUSTOS] Linha {row_num}: {e}", exc_info=True)
            db.session.rollback()
            resultado['erros'] += 1
            resultado['detalhes'].append({'linha': row_num, 'status': 'erro', 'mensagem': str(e)})

    return resultado


# ── Utilitário interno ─────────────────────────────────────────────────────────

def _detectar_linha_header(ws, chaves_esperadas):
    """Detecta automaticamente qual linha contém o cabeçalho."""
    import unicodedata
    def norm(s):
        s = _normalizar_texto(s).lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        s = s.replace(' ', '_').replace('*', '').strip()
        return s

    for tentativa in range(1, min(6, ws.max_row + 1)):
        row_vals = [ws.cell(row=tentativa, column=c).value for c in range(1, ws.max_column + 1)]
        normalized = [norm(str(v)) for v in row_vals]
        if any(ch in normalized for ch in chaves_esperadas):
            return tentativa
    return None
