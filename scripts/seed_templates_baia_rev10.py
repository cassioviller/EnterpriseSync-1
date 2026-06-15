"""Seed dos CronogramaTemplate da Baia REV10 a partir do cronograma refinado.

Cria 1 CronogramaTemplate por serviço do orçamento ORC-BAIA-REV10 (id 98), com
um item por Atividade do cronograma refinado
(`docs/superpowers/specs/2026-06-14-cronograma-refinado-pareto-baia-rev10.md`),
gravando o peso explícito em `peso_medicao` (soma 100%/serviço). Liga o serviço
ao template via `Servico.template_padrao_id`. Idempotente: pula serviço que já
tem template_padrao_id.

Depois disso, importar/re-materializar a obra cria a estrutura MULTI-ATIVIDADE
(não 1:1). Telhado viga I (subempreitada) fica de fora (Fatia 2); gates (peso 0)
não entram no aspecto financeiro.
"""
from decimal import Decimal

from app import app, db
from models import Orcamento, OrcamentoItem, Servico, CronogramaTemplate, CronogramaTemplateItem

# prefixo "1.X"/"1.17a" do serviço  ->  [(nome da atividade, peso no serviço %), ...]
BREAKDOWN = {
    '1.1':  [('Painelização LSF (bancada)', 50), ('Montagem LSF (verticalização+fixação+contravent.)', 50)],
    '1.2':  [('Pintura do aço estrutural', 100)],
    '1.3':  [('Stain dos portões', 100)],
    '1.4':  [('Portões — fabricação (oficina)', 60), ('Portões — instalação (campo)', 40)],
    '1.5':  [('Fixação da placa cimentícia', 55), ('Tratamento de junta + basecoat', 45)],
    '1.6':  [('Fechamento em régua de pinus', 100)],
    '1.7':  [('Pintura interna dos fechamentos', 100)],
    '1.8':  [('Stain das paredes externas', 100)],
    '1.9':  [('Verticalização dos pilares roliços', 100)],
    '1.10': [('Corredores — preparo e formas', 47), ('Corredores — concretagem', 53)],
    '1.11': [('Revestimento pedra moledo', 100)],
    '1.12': [('Elétrica final (fiação+pontos+luminárias)', 100)],
    '1.13': [('Base OSB do telhado', 25), ('Telhamento shingle (manta+telhas+cumeeira)', 75)],
    '1.14': [('Cercado das baias', 100)],
    '1.15': [('Stain do cercado', 100)],
    '1.16': [('Ponto hidráulico terminal por baia', 100)],
    '1.17a': [('Preparo do terreno + lastro', 33), ('Armação e formas', 38), ('Concretagem do radier', 29)],
    '1.17b': [('Infra elétrica embutida', 100)],
    '1.17c': [('Infra hidráulica/dreno embutida', 100)],
    '1.17d': [('Lã de rocha (isolamento)', 100)],
    '1.17e': [('Forro de PVC', 100)],
}


def seed_templates_baia(admin_id, orcamento_id=98):
    orc = Orcamento.query.filter_by(id=orcamento_id, admin_id=admin_id).first()
    if not orc:
        raise ValueError(f"Orçamento {orcamento_id} não encontrado para admin {admin_id}")

    criados, pulados = 0, 0
    itens = OrcamentoItem.query.filter_by(orcamento_id=orcamento_id).order_by(OrcamentoItem.ordem).all()
    for it in itens:
        prefixo = (it.descricao or '').split()[0] if it.descricao else ''
        atividades = BREAKDOWN.get(prefixo)
        if not atividades or not it.servico_id:
            pulados += 1
            continue
        serv = db.session.get(Servico, it.servico_id)
        if not serv:
            pulados += 1
            continue
        if serv.template_padrao_id:
            pulados += 1   # idempotente: já tem template
            continue

        tmpl = CronogramaTemplate(
            nome=f'Template {prefixo} — {(it.descricao or "")[:60]}',
            descricao='Gerado do cronograma refinado Baia REV10',
            ativo=True, admin_id=admin_id,
        )
        db.session.add(tmpl)
        db.session.flush()
        for i, (nome, peso) in enumerate(atividades, start=1):
            db.session.add(CronogramaTemplateItem(
                template_id=tmpl.id, nome_tarefa=nome, ordem=i, duracao_dias=1,
                admin_id=admin_id, peso_medicao=Decimal(str(peso)),
            ))
        serv.template_padrao_id = tmpl.id
        criados += 1

    db.session.commit()
    return {'templates_criados': criados, 'servicos_pulados': pulados}


if __name__ == '__main__':
    with app.app_context():
        print(seed_templates_baia(admin_id=1, orcamento_id=98))
