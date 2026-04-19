"""
Task #108 — Seed Demo "Construtora Alfa" (idempotente).

Planta um dataset de demonstração completo:
  • Admin (Construtora Alfa) + 2 funcionários (Carlos pedreiro, Pedro encarregado)
  • Cliente, ConfiguracaoEmpresa
  • Catálogo: Insumos (com PrecoBaseInsumo), SubatividadeMestre,
    CronogramaTemplate (+ itens), Servico vinculado ao template + ComposicaoServico
  • Proposta 2026-001 APROVADA com 1 item paramétrico → cria Obra "Bela Vista"
    + ItemMedicaoComercial + materializa cronograma (3 níveis) com pesos
  • 2 RDOs FINALIZADOS com mão de obra e progresso 30% → 60%
  • Tarefas do cronograma sincronizadas com avanço dos RDOs
  • Medição quinzenal #001 APROVADA → ContaReceber OBR-MED-#####

Idempotência (chave natural = email do admin):
  • Se Usuario.email='admin@construtoraalfa.com.br' já existe → sai 0
    com mensagem "já populado" (não duplica, não zera).
  • Implantações repetidas no mesmo container são no-op silencioso.

Uso:
    python3 scripts/seed_demo_alfa.py            # primeira vez planta; depois é no-op
    python3 scripts/seed_demo_alfa.py --reset    # reseta (apenas em dev)
                                                 # exige SIGE_ALLOW_PROD_SEED=1
                                                 # quando FLASK_ENV=production
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

# Garante que /app (ou raiz do projeto) está no sys.path antes dos imports
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="[seed-demo-alfa] %(levelname)s %(message)s",
)
log = logging.getLogger("seed_demo_alfa")

ADMIN_EMAIL = "admin@construtoraalfa.com.br"
ADMIN_USERNAME = "admin_alfa"
ADMIN_PASSWORD = "Alfa@2026"


def _admin_existente():
    from models import Usuario
    return Usuario.query.filter_by(email=ADMIN_EMAIL).first()


def _reset_dataset():
    """Remove o dataset Alfa por completo (cascade pelas FKs).
    Apenas para dev. Em produção exige SIGE_ALLOW_PROD_SEED=1.
    """
    if os.environ.get("FLASK_ENV") == "production" and \
       os.environ.get("SIGE_ALLOW_PROD_SEED") != "1":
        log.error("--reset bloqueado em produção (defina SIGE_ALLOW_PROD_SEED=1 para forçar)")
        sys.exit(2)

    from app import db
    from models import (
        Usuario, Funcionario, Cliente, Obra, Proposta, Servico,
        SubatividadeMestre, CronogramaTemplate, Insumo, ConfiguracaoEmpresa,
        ContaReceber, LancamentoContabil, PartidaContabil,
    )
    admin = _admin_existente()
    if not admin:
        log.info("nada a resetar (admin Alfa inexistente)")
        return
    admin_id = admin.id
    log.info(f"resetando dataset do admin Alfa (id={admin_id})")

    # Ordem importa: filhos antes dos pais. O cascade do ORM cobre maioria.
    PartidaContabil.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    LancamentoContabil.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    ContaReceber.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    # Obras (cascade → RDOs, IMC, MedicaoObra, Tarefas)
    Obra.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    Proposta.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    # Catálogo
    Servico.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    SubatividadeMestre.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    CronogramaTemplate.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    Insumo.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    Funcionario.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    Cliente.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    # Funcionários do tenant (subordinados via admin_id em Usuario)
    Usuario.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
    db.session.delete(admin)
    db.session.commit()
    log.info("reset concluído")


def _seed():
    from app import app, db
    from werkzeug.security import generate_password_hash
    from models import (
        Usuario, TipoUsuario, Funcionario, Cliente, ConfiguracaoEmpresa,
        Insumo, PrecoBaseInsumo, SubatividadeMestre, CronogramaTemplate,
        CronogramaTemplateItem, Servico, ComposicaoServico,
        Proposta, PropostaItem, Obra, ItemMedicaoComercial,
        TarefaCronograma, RDO, RDOMaoObra, RDOServicoSubatividade,
    )
    from services.cronograma_proposta import (
        montar_arvore_preview, materializar_cronograma,
    )
    from services.medicao_service import gerar_medicao_quinzenal, fechar_medicao

    # 1) Admin -------------------------------------------------------------
    admin = Usuario(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        nome="Construtora Alfa",
        password_hash=generate_password_hash(ADMIN_PASSWORD),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema="v1",
    )
    db.session.add(admin)
    db.session.flush()
    admin_id = admin.id
    log.info(f"admin criado id={admin_id} email={ADMIN_EMAIL}")

    # 2) Configuração da empresa ------------------------------------------
    cfg = ConfiguracaoEmpresa(
        admin_id=admin_id,
        nome_empresa="Construtora Alfa Ltda",
        cnpj="12.345.678/0001-90",
        endereco="Rua das Pedras, 100 — Centro",
        telefone="(11) 4000-0000",
        email="contato@construtoraalfa.com.br",
        cor_primaria="#1976d2",
        cor_secundaria="#455a64",
        prazo_entrega_padrao=120,
        validade_padrao=15,
    )
    db.session.add(cfg)

    # 3) Cliente ----------------------------------------------------------
    cliente = Cliente(
        nome="Empreendimentos Bela Vista S/A",
        email="obras@belavista.com.br",
        telefone="(11) 5000-0000",
        endereco="Av. Paulista, 1000 — São Paulo",
        cnpj="98.765.432/0001-10",
        admin_id=admin_id,
    )
    db.session.add(cliente)
    db.session.flush()

    # 4) Funcionários -----------------------------------------------------
    carlos = Funcionario(
        codigo="ALF001",
        nome="Carlos Pereira",
        cpf="900.901.001-01",
        data_admissao=date(2024, 1, 15),
        salario=3200.00,
        jornada_semanal=44,
        ativo=True,
        admin_id=admin_id,
        tipo_remuneracao="salario",
        valor_va=22.00,
        valor_vt=12.00,
        chave_pix="900.901.001-01",
        email="carlos@construtoraalfa.com.br",
        telefone="(11) 90000-0001",
    )
    pedro = Funcionario(
        codigo="ALF002",
        nome="Pedro Souza",
        cpf="900.901.002-02",
        data_admissao=date(2023, 6, 1),
        salario=4800.00,
        jornada_semanal=44,
        ativo=True,
        admin_id=admin_id,
        tipo_remuneracao="salario",
        valor_va=22.00,
        valor_vt=12.00,
        chave_pix="900.901.002-02",
        email="pedro@construtoraalfa.com.br",
        telefone="(11) 90000-0002",
    )
    db.session.add_all([carlos, pedro])
    db.session.flush()

    # 5) Catálogo: Insumos + Preços --------------------------------------
    hoje = date.today()
    insumos_def = [
        ("Cimento CP II 50kg", "MATERIAL", "sc", 38.50),
        ("Tijolo cerâmico 9x19x19", "MATERIAL", "un", 1.20),
        ("Areia média m³", "MATERIAL", "m3", 95.00),
        ("Hora pedreiro", "MAO_OBRA", "h", 28.00),
        ("Hora servente", "MAO_OBRA", "h", 18.00),
        ("Betoneira diária", "EQUIPAMENTO", "h", 25.00),
    ]
    insumos_obj = {}
    for nome, tipo, un, preco in insumos_def:
        ins = Insumo(
            admin_id=admin_id, nome=nome, tipo=tipo,
            unidade=un, ativo=True,
        )
        db.session.add(ins)
        db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=admin_id, insumo_id=ins.id,
            valor=Decimal(str(preco)),
            vigencia_inicio=date(2025, 1, 1),
        ))
        insumos_obj[nome] = ins

    # 6) Catálogo: SubatividadeMestre + Template de Cronograma -----------
    # Estrutura: Grupo "Alvenaria" → 2 subatividades; Grupo "Reboco" → 1 sub.
    subs = {}
    for nome, horas, unidade, meta in [
        ("Marcação de paredes",   8.0, "m linear", 5.0),
        ("Elevação de alvenaria", 32.0, "m²", 1.5),
        ("Chapisco e reboco",     24.0, "m²", 2.0),
    ]:
        sm = SubatividadeMestre(
            tipo="subatividade", nome=nome, descricao=nome,
            duracao_estimada_horas=horas,
            unidade_medida=unidade,
            meta_produtividade=meta,
            obrigatoria=True, complexidade=2,
            admin_id=admin_id, ativo=True,
        )
        db.session.add(sm)
        subs[nome] = sm
    db.session.flush()

    template = CronogramaTemplate(
        nome="Alvenaria padrão Alfa",
        descricao="Template padrão de execução de alvenaria",
        categoria="Estrutura",
        ativo=True, admin_id=admin_id,
    )
    db.session.add(template)
    db.session.flush()

    # Itens do template — 2 grupos com filhos
    grupo_alv = CronogramaTemplateItem(
        template_id=template.id,
        nome_tarefa="Alvenaria",
        ordem=10, duracao_dias=1,
        admin_id=admin_id,
    )
    db.session.add(grupo_alv)
    db.session.flush()

    item_marcacao = CronogramaTemplateItem(
        template_id=template.id,
        parent_item_id=grupo_alv.id,
        subatividade_mestre_id=subs["Marcação de paredes"].id,
        nome_tarefa="Marcação de paredes",
        ordem=11, duracao_dias=2,
        quantidade_prevista=80.0,
        responsavel="empresa",
        admin_id=admin_id,
    )
    item_elevacao = CronogramaTemplateItem(
        template_id=template.id,
        parent_item_id=grupo_alv.id,
        subatividade_mestre_id=subs["Elevação de alvenaria"].id,
        nome_tarefa="Elevação de alvenaria",
        ordem=12, duracao_dias=8,
        quantidade_prevista=240.0,
        responsavel="empresa",
        admin_id=admin_id,
    )
    grupo_reb = CronogramaTemplateItem(
        template_id=template.id,
        nome_tarefa="Reboco",
        ordem=20, duracao_dias=1,
        admin_id=admin_id,
    )
    db.session.add_all([item_marcacao, item_elevacao, grupo_reb])
    db.session.flush()

    item_reboco = CronogramaTemplateItem(
        template_id=template.id,
        parent_item_id=grupo_reb.id,
        subatividade_mestre_id=subs["Chapisco e reboco"].id,
        nome_tarefa="Chapisco e reboco",
        ordem=21, duracao_dias=6,
        quantidade_prevista=240.0,
        responsavel="empresa",
        admin_id=admin_id,
    )
    db.session.add(item_reboco)
    db.session.flush()

    # 7) Serviço com template padrão + composição -------------------------
    servico = Servico(
        nome="Alvenaria de vedação",
        descricao="Execução completa de alvenaria de vedação com reboco",
        categoria="Estrutura",
        unidade_medida="m2",
        unidade_simbolo="m²",
        custo_unitario=85.00,
        complexidade=3,
        ativo=True,
        imposto_pct=Decimal("8.0"),
        margem_lucro_pct=Decimal("25.0"),
        preco_venda_unitario=Decimal("145.00"),
        template_padrao_id=template.id,
        admin_id=admin_id,
    )
    db.session.add(servico)
    db.session.flush()

    # Composição: 0.04 sc cimento, 28 tijolos, 0.02 m³ areia,
    #             0.6h pedreiro, 0.4h servente por m².
    for nome_ins, coef in [
        ("Cimento CP II 50kg", "0.04"),
        ("Tijolo cerâmico 9x19x19", "28.0"),
        ("Areia média m³", "0.02"),
        ("Hora pedreiro", "0.60"),
        ("Hora servente", "0.40"),
    ]:
        db.session.add(ComposicaoServico(
            admin_id=admin_id,
            servico_id=servico.id,
            insumo_id=insumos_obj[nome_ins].id,
            coeficiente=Decimal(coef),
        ))

    # 8) Proposta 2026-001 APROVADA --------------------------------------
    proposta = Proposta(
        numero="001.26",
        data_proposta=date(2026, 1, 10),
        cliente_id=cliente.id,
        cliente_nome=cliente.nome,
        cliente_telefone=cliente.telefone,
        cliente_email=cliente.email,
        cliente_endereco=cliente.endereco,
        titulo="Edifício Bela Vista — Alvenaria",
        descricao="Execução de alvenaria de vedação do bloco A",
        prazo_entrega_dias=120,
        validade_dias=15,
        status="aprovada",
        valor_total=Decimal("145000.00"),
        criado_por=admin_id,
        admin_id=admin_id,
        data_envio=datetime(2026, 1, 11, 10, 0),
        data_resposta_cliente=datetime(2026, 1, 18, 14, 30),
    )
    db.session.add(proposta)
    db.session.flush()

    item_prop = PropostaItem(
        admin_id=admin_id,
        proposta_id=proposta.id,
        item_numero=1,
        descricao="Alvenaria de vedação — bloco A",
        quantidade=Decimal("1000.000"),
        unidade="m2",
        preco_unitario=Decimal("145.00"),
        ordem=1,
        servico_id=servico.id,
        quantidade_medida=Decimal("1000.0000"),
        custo_unitario=Decimal("85.0000"),
        lucro_unitario=Decimal("60.0000"),
        subtotal=Decimal("145000.00"),
    )
    db.session.add(item_prop)
    db.session.flush()

    # 9) Obra Bela Vista --------------------------------------------------
    obra = Obra(
        nome="Edifício Bela Vista",
        codigo="OBR-2026-001",
        endereco="Rua das Acácias, 250 — São Paulo",
        data_inicio=date(2026, 2, 2),
        data_previsao_fim=date(2026, 6, 2),
        orcamento=145000.00,
        valor_contrato=145000.00,
        area_total_m2=1000.0,
        status="Em andamento",
        cliente=cliente.nome,
        cliente_nome=cliente.nome,
        cliente_email=cliente.email,
        cliente_telefone=cliente.telefone,
        proposta_origem_id=proposta.id,
        portal_ativo=True,
        responsavel_id=pedro.id,
        ativo=True,
        admin_id=admin_id,
        data_inicio_medicao=date(2026, 2, 1),
        valor_entrada=Decimal("14500.00"),
        data_entrada=date(2026, 1, 25),
    )
    db.session.add(obra)
    db.session.flush()
    proposta.obra_id = obra.id
    proposta.convertida_em_obra = True

    # 10) Snapshot de cronograma + propagação proposta→obra --------------
    arvore = montar_arvore_preview(proposta, admin_id)
    proposta.cronograma_default_json = arvore

    # Propagação 1:1 PropostaItem → ItemMedicaoComercial
    imc = ItemMedicaoComercial(
        admin_id=admin_id,
        obra_id=obra.id,
        nome=item_prop.descricao[:200],
        valor_comercial=Decimal("145000.00"),
        servico_id=servico.id,
        quantidade=item_prop.quantidade,
        proposta_item_id=item_prop.id,
        status="PENDENTE",
    )
    db.session.add(imc)
    db.session.flush()

    # Materialização do cronograma (3 níveis + pesos por horas)
    n_tarefas = materializar_cronograma(proposta, admin_id, obra.id, arvore)
    log.info(f"cronograma materializado: {n_tarefas} tarefas (com pesos)")
    db.session.flush()

    # 11) Dois RDOs FINALIZADOS com mão de obra ---------------------------
    # Avanço: RDO #1 leva subatividades a 30%; RDO #2 a 60%.
    folhas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=False)
        .filter(TarefaCronograma.subatividade_mestre_id.isnot(None))
        .order_by(TarefaCronograma.ordem.asc())
        .all()
    )
    log.info(f"folhas do cronograma encontradas: {len(folhas)}")

    rdos_dados = [
        (date(2026, 2, 5), 30.0, 8.0),
        (date(2026, 2, 12), 60.0, 8.0),
    ]
    for idx, (dt, perc_destino, horas) in enumerate(rdos_dados, start=1):
        rdo = RDO(
            numero_rdo=f"RDO-2026-{idx:03d}",
            data_relatorio=dt,
            obra_id=obra.id,
            criado_por_id=admin_id,
            admin_id=admin_id,
            clima_geral="Ensolarado",
            temperatura_media="26°C",
            condicoes_trabalho="Ideais",
            local="Campo",
            comentario_geral=f"Avanço da semana — meta atingida ({perc_destino:.0f}%).",
            status="Finalizado",
        )
        db.session.add(rdo)
        db.session.flush()

        # Mão de obra: Carlos pedreiro + Pedro encarregado em todas as folhas
        for folha in folhas:
            db.session.add(RDOMaoObra(
                admin_id=admin_id, rdo_id=rdo.id,
                funcionario_id=carlos.id, funcao_exercida="Pedreiro",
                horas_trabalhadas=horas, horas_extras=0.0,
                tarefa_cronograma_id=folha.id,
            ))
            db.session.add(RDOMaoObra(
                admin_id=admin_id, rdo_id=rdo.id,
                funcionario_id=pedro.id, funcao_exercida="Encarregado",
                horas_trabalhadas=horas, horas_extras=0.0,
                tarefa_cronograma_id=folha.id,
            ))

            # Apontamento de progresso por subatividade
            perc_anterior = 0.0 if idx == 1 else 30.0
            db.session.add(RDOServicoSubatividade(
                rdo_id=rdo.id,
                servico_id=servico.id,
                nome_subatividade=folha.nome_tarefa,
                descricao_subatividade=folha.nome_tarefa,
                percentual_conclusao=perc_destino,
                percentual_anterior=perc_anterior,
                incremento_dia=perc_destino - perc_anterior,
                ordem_execucao=folha.ordem,
                ativo=True,
                admin_id=admin_id,
                subatividade_mestre_id=folha.subatividade_mestre_id,
            ))

            # Atualiza tarefa do cronograma — fonte da verdade da medição
            folha.percentual_concluido = perc_destino
        db.session.flush()
        log.info(f"RDO #{idx} ({dt.isoformat()}) finalizado — folhas a {perc_destino:.0f}%")

    db.session.commit()

    # 12) Medição quinzenal #001 + fechamento → ContaReceber OBR-MED -----
    medicao, err = gerar_medicao_quinzenal(
        obra_id=obra.id,
        admin_id=admin_id,
        periodo_inicio=date(2026, 2, 1),
        periodo_fim=date(2026, 2, 15),
        observacoes="Primeira medição — alvenaria a 60%.",
    )
    if err:
        raise RuntimeError(f"falha ao gerar medição: {err}")
    log.info(f"medição #{medicao.numero:03d} gerada — valor R$ "
             f"{float(medicao.valor_total_medido_periodo or 0):.2f}")

    medicao_aprovada, err2 = fechar_medicao(medicao.id, admin_id)
    if err2:
        raise RuntimeError(f"falha ao fechar medição: {err2}")
    log.info(f"medição #{medicao_aprovada.numero:03d} APROVADA")

    # ContaReceber é criada/atualizada por recalcular_medicao_obra dentro
    # de gerar_medicao_quinzenal e fechar_medicao. Apenas confirma.
    from models import ContaReceber
    cr = ContaReceber.query.filter_by(
        admin_id=admin_id, origem_tipo="OBRA_MEDICAO", origem_id=obra.id,
    ).first()
    if cr:
        log.info(f"ContaReceber {cr.numero_documento} criada — "
                 f"valor R$ {float(cr.valor_original or 0):.2f} status={cr.status}")

    log.info("=" * 60)
    log.info("SEED DEMO ALFA CONCLUÍDO COM SUCESSO")
    log.info(f"  • admin: {ADMIN_EMAIL}  (senha: {ADMIN_PASSWORD})")
    log.info(f"  • obra:  {obra.codigo} — {obra.nome}")
    log.info(f"  • proposta: {proposta.numero} ({proposta.status})")
    log.info(f"  • cronograma: {n_tarefas} tarefas materializadas")
    log.info(f"  • RDOs finalizados: {len(rdos_dados)}")
    log.info(f"  • medição: #{medicao_aprovada.numero:03d} APROVADA")
    log.info("=" * 60)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    reset = "--reset" in argv

    try:
        from app import app, db
    except Exception as e:
        log.error(f"falha ao importar app: {e}")
        return 1

    with app.app_context():
        try:
            if reset:
                _reset_dataset()

            existente = _admin_existente()
            if existente:
                log.info(
                    f"dataset Alfa já populado (admin id={existente.id}) — "
                    f"no-op idempotente"
                )
                return 0

            log.info("primeira execução detectada — populando dataset Alfa…")
            _seed()
            return 0

        except Exception as e:
            from app import db
            db.session.rollback()
            log.exception(f"erro durante seed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
