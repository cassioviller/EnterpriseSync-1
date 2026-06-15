"""Teste REAL ponta a ponta: importa o arquivo IMPORTACAO_Baia_REV10_completa.xlsx
(o mesmo que será usado na produção/EasyPanel) e verifica que a cadeia inteira é
criada sem configuração manual: catálogo → orçamento → templates → obra
multi-atividade, e que o read-model funciona após um apontamento."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, OrcamentoItem, Proposta, Obra,
    TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
    RDO, RDOMaoObra, RDOCustoDiario,
)
from werkzeug.security import generate_password_hash

XLSX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'obra_kabod', 'IMPORTACAO_Baia_REV10_completa.xlsx',
)


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


@pytest.mark.skipif(not os.path.exists(XLSX), reason='arquivo de importação ausente')
def test_importar_baia_do_xlsx_cria_obra_multi_atividade():
    with app.app_context():
        s = _sfx()
        admin = Usuario(username=f'baia_{s}', email=f'baia_{s}@sige.test', nome='Baia',
                        tipo_usuario=TipoUsuario.ADMIN,
                        password_hash=generate_password_hash('Test@1234'),
                        versao_sistema='v2', ativo=True)
        db.session.add(admin); db.session.commit()

        from scripts.importar_baia_easypanel import importar_baia_completa
        res = importar_baia_completa(admin.id, xlsx_path=XLSX)

        # cadeia criada
        assert res['obra_id'] is not None
        obra_id = res['obra_id']

        # orçamento: 21 itens (1.1..1.16 + 1.17a..e)
        orc_itens = OrcamentoItem.query.filter_by(orcamento_id=res['orcamento_id']).count()
        assert orc_itens == 21, orc_itens

        # Proposta de importação (fora do funil) ligada ao orçamento
        prop = Proposta.query.filter_by(orcamento_id=res['orcamento_id']).first()
        assert prop is not None and prop.origem == 'importacao_obra'

        # IMC 1:1 por serviço
        assert ItemMedicaoComercial.query.filter_by(obra_id=obra_id).count() == 21

        # cronograma MULTI-ATIVIDADE: 28 atividades produtivas
        tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id).all()
        assert len(tarefas) == 28, len(tarefas)

        # serviços com >1 atividade têm pesos somando 100%
        from collections import defaultdict
        por_serv = defaultdict(list)
        for t in tarefas:
            link = ItemMedicaoCronogramaTarefa.query.filter_by(cronograma_tarefa_id=t.id).first()
            assert link is not None
            por_serv[t.servico_id].append(Decimal(str(link.peso)))
        multi = {k: v for k, v in por_serv.items() if len(v) > 1}
        assert len(multi) >= 5
        for pesos in multi.values():
            assert sum(pesos) == Decimal('100')


@pytest.mark.skipif(not os.path.exists(XLSX), reason='arquivo de importação ausente')
def test_baia_importada_resultado_apos_apontamento():
    """Depois do import, apontar 1 RDO numa atividade faz o read-model devolver
    valores reais (Valor agregado / Custo / Resultado / orçado)."""
    with app.app_context():
        s = _sfx()
        admin = Usuario(username=f'baia2_{s}', email=f'baia2_{s}@sige.test', nome='Baia2',
                        tipo_usuario=TipoUsuario.ADMIN,
                        password_hash=generate_password_hash('Test@1234'),
                        versao_sistema='v2', ativo=True)
        db.session.add(admin); db.session.commit()

        from scripts.importar_baia_easypanel import importar_baia_completa
        from services.resultado_atividade_service import (
            valor_agregado_atividade, custo_mo_atividade, custo_mo_orcado_atividade,
        )
        res = importar_baia_completa(admin.id, xlsx_path=XLSX)
        obra_id = res['obra_id']

        t = (TarefaCronograma.query.filter_by(obra_id=obra_id)
             .filter(TarefaCronograma.nome_tarefa.like('Paineliza%')).first())
        assert t is not None
        t.percentual_concluido = 50.0
        f = Funcionario(nome=f'F {_sfx()}', cpf=f'4{_sfx()}'.ljust(14, '0')[:14],
                        codigo=f'F{_sfx()[-8:]}', data_admissao=date(2025, 1, 1),
                        admin_id=admin.id, tipo_remuneracao='salario', salario=3000.0, ativo=True)
        db.session.add(f); db.session.flush()
        r = RDO(numero_rdo=f'RDO-B-{_sfx()}', obra_id=obra_id, data_relatorio=date(2026, 6, 1),
                admin_id=admin.id, status='Finalizado', criado_por_id=admin.id)
        db.session.add(r); db.session.flush()
        db.session.add(RDOMaoObra(rdo_id=r.id, funcionario_id=f.id, funcao_exercida='Op',
                                  horas_trabalhadas=8.0, admin_id=admin.id,
                                  subatividade_id=None, tarefa_cronograma_id=t.id))
        db.session.add(RDOCustoDiario(rdo_id=r.id, funcionario_id=f.id, admin_id=admin.id,
                                      data=r.data_relatorio, tipo_remuneracao_snapshot='salario',
                                      custo_total_dia=Decimal('400'), tipo_lancamento='rdo'))
        db.session.commit()

        # com dados reais do orçamento, todos > 0
        assert valor_agregado_atividade(t) > 0          # avanço × peso × venda
        assert custo_mo_atividade(t) == Decimal('400.00')
        assert custo_mo_orcado_atividade(t) > 0         # MO orçada do snapshot real
