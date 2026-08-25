"""Fase 6 / Task 13 — a porta HTTP do aditivo e o extrato de contrato da obra.

Até aqui a Fase 6 construiu o mecanismo inteiro sem nenhuma porta: o baseline
versionado (`ObraContratoVersao`), o documento (`AditivoContrato`), o lançamento
contábil do delta, o ajuste de cronograma e o diff entre versões. Tudo isso só
era alcançável por serviço — ou seja, por ninguém.

Este módulo é a porta, e ela é fina de propósito: **nenhuma regra de negócio
mora aqui**. Abrir, aprovar e cancelar continuam em `services.contrato_obra`,
que é quem sabe fechar a versão vigente, lançar o delta e recusar o que não
pode. A view resolve identidade, autoriza, chama o serviço e traduz erro em
mensagem.

**Autorização.** O plano mandava conferir o nome real do decorator antes de
importar, e a conferência mudou a decisão: em 23/07 o ruling N4 escolheu
`pode_editar_obra` na mão *porque `obra_required` não existia*. Ele existe
(`utils/autorizacao.py:302`), devolve **404 e não 403** para obra fora de
alcance — que é a escolha já travada em
`tests/test_cronograma_permissoes.py` — e trata o caso JSON. Usar a mão agora
seria reimplementar pior o que a Fase 1 publicou.

Aprovar aditivo mexe no baseline do contrato: exige `PapelObra.GESTOR`. Ver o
extrato é leitura e basta ter acesso à obra.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from models import AditivoContrato, Obra, ObraContratoVersao, PapelObra, db
from utils.autorizacao import obra_required
from utils.decimal_br import parse_decimal_br
from utils.tenant import get_tenant_admin_id

logger = logging.getLogger(__name__)

aditivos_bp = Blueprint('aditivos', __name__, url_prefix='/obras')


def _obra_do_tenant(obra_id: int) -> Obra:
    """A obra, dentro do tenant da sessão, ou 404.

    `obra_required` já barrou quem não alcança a obra; este filtro é a segunda
    camada, para o caso de a sessão trocar de tenant entre o decorator e a
    query.
    """
    admin_id = get_tenant_admin_id()
    return Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()


@aditivos_bp.route('/<int:obra_id>/aditivos')
@login_required
@obra_required()
def listar(obra_id: int):
    """Extrato do contrato: o original, cada aditivo e o valor vigente.

    É a tela que responde "por que este contrato vale isto hoje" — a pergunta
    que antes só se respondia abrindo o banco.
    """
    obra = _obra_do_tenant(obra_id)
    admin_id = obra.admin_id
    versoes = (ObraContratoVersao.query
               .filter_by(obra_id=obra_id, admin_id=admin_id)
               .order_by(ObraContratoVersao.versao.asc()).all())
    aditivos = (AditivoContrato.query
                .filter_by(obra_id=obra_id, admin_id=admin_id)
                .order_by(AditivoContrato.criado_em.asc()).all())
    vigente = next((v for v in versoes if v.vigente_ate is None), None)
    return render_template('aditivos/listar.html', obra=obra, versoes=versoes,
                           aditivos=aditivos, vigente=vigente,
                           pode_editar=True)


@aditivos_bp.route('/<int:obra_id>/aditivos/novo', methods=['GET', 'POST'])
@login_required
@obra_required(PapelObra.GESTOR)
def novo(obra_id: int):
    """Abre um aditivo em rascunho. NÃO toca no baseline — quem toca é aprovar.

    O rascunho existe justamente para que o impacto seja lido antes de valer:
    aprovar sem ver o que muda é o que esta fase existe para impedir.
    """
    from services.contrato_obra import abrir_aditivo, contrato_vigente

    obra = _obra_do_tenant(obra_id)
    vigente = contrato_vigente(obra_id, obra.admin_id)

    if request.method == 'GET':
        return render_template('aditivos/form.html', obra=obra,
                               vigente=vigente)

    try:
        prazo = (request.form.get('prazo_delta_dias') or '').strip()
        # `default=None`: aditivo de prazo puro não traz valor, e isso é
        # legítimo (D2 da Fase 6). O que não pode é ADIVINHAR um valor
        # ambíguo — `ValorAmbiguo` é `ValueError` e cai no `except` de baixo,
        # que devolve 400 com a mensagem na tela.
        valor_novo = parse_decimal_br(
            request.form.get('valor_novo'), campo='valor do aditivo',
            default=None, minimo=Decimal('0'))
        aditivo = abrir_aditivo(
            obra,
            tipo=(request.form.get('tipo') or '').strip(),
            motivo=(request.form.get('motivo') or '').strip(),
            valor_novo=valor_novo,
            prazo_delta_dias=int(prazo) if prazo else None,
            criado_por_id=getattr(current_user, 'id', None),
        )
        db.session.commit()
        flash(f'Aditivo {aditivo.numero} aberto em rascunho. '
              f'Confira o impacto antes de aprovar.', 'success')
        return redirect(url_for('aditivos.listar', obra_id=obra_id))
    except HTTPException:
        # 404/403 são RESPOSTA, não falha a recuperar — precisam escapar
        # antes do catch-all, senão viram "erro ao abrir aditivo" + 302.
        raise
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
        return render_template('aditivos/form.html', obra=obra,
                               vigente=vigente), 400
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao abrir aditivo da obra %s', obra_id)
        flash(f'Erro ao abrir aditivo: {e}', 'error')
        return redirect(url_for('aditivos.listar', obra_id=obra_id))


@aditivos_bp.route('/<int:obra_id>/aditivos/<int:aid>/aprovar',
                   methods=['POST'])
@login_required
@obra_required(PapelObra.GESTOR)
def aprovar(obra_id: int, aid: int):
    """`rascunho` → `aprovado`: o único ponto em que o aditivo vale.

    Abre a versão seguinte do baseline, lança o delta contábil e ajusta o
    cronograma — tudo dentro do serviço, numa transação só.
    """
    from services.contrato_obra import aprovar_aditivo

    obra = _obra_do_tenant(obra_id)
    aditivo = AditivoContrato.query.filter_by(
        id=aid, obra_id=obra_id, admin_id=obra.admin_id).first_or_404()
    try:
        versao = aprovar_aditivo(
            aditivo, aprovado_por_id=getattr(current_user, 'id', None))
        db.session.commit()
        flash(f'Aditivo {aditivo.numero} aprovado. O contrato passou a valer '
              f'R$ {float(versao.valor):,.2f} (versão {versao.versao}).'
              .replace(',', 'X').replace('.', ',').replace('X', '.'),
              'success')
    except HTTPException:
        raise
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao aprovar aditivo %s', aid)
        flash(f'Erro ao aprovar o aditivo: {e}', 'error')
    return redirect(url_for('aditivos.listar', obra_id=obra_id))


@aditivos_bp.route('/<int:obra_id>/aditivos/<int:aid>/cancelar',
                   methods=['POST'])
@login_required
@obra_required(PapelObra.GESTOR)
def cancelar(obra_id: int, aid: int):
    """`rascunho` → `cancelado`. Não toca no baseline.

    A linha fica na tabela como registro do que foi cogitado — o número não
    recicla. Cancelar um aprovado é recusado pelo serviço: aprovado já produziu
    efeito, e desfazer exige aditivo em sentido contrário, nunca apagar
    história.
    """
    from services.contrato_obra import cancelar_aditivo

    obra = _obra_do_tenant(obra_id)
    aditivo = AditivoContrato.query.filter_by(
        id=aid, obra_id=obra_id, admin_id=obra.admin_id).first_or_404()
    try:
        cancelar_aditivo(aditivo)
        db.session.commit()
        flash(f'Aditivo {aditivo.numero} cancelado.', 'success')
    except HTTPException:
        raise
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao cancelar aditivo %s', aid)
        flash(f'Erro ao cancelar o aditivo: {e}', 'error')
    return redirect(url_for('aditivos.listar', obra_id=obra_id))
