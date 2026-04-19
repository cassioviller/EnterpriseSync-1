"""
Task #108 — Seed Demo "Construtora Alfa" (idempotente, dev-only por padrão).

Planta o cenário canônico do `docs/manual-ciclo-completo.md` num único
tenant isolado:

  • Admin Construtora Alfa + ConfiguracaoEmpresa
  • Cliente: João da Silva (PF)
  • Funcionários:
      - Carlos Pereira  → mensalista (tipo_remuneracao='salario',
                          salario R$ 2.800, VA 22, VT 12, PIX)
      - Pedro Souza     → diarista  (tipo_remuneracao='diaria',
                          valor_diaria R$ 180, VA 22, VT 12, PIX)
  • Catálogo: Insumos com preço base + 3 Serviços
      - "Alvenaria de bloco cerâmico"  → COM Template padrão (cronograma)
      - "Contrapiso desempenado"       → COM Template padrão (cronograma)
      - "Mobilização de obra"          → SEM template (avulso)
  • Proposta `001.26` para João da Silva, com 4 itens:
       1) Alvenaria 250 m²
       2) Contrapiso 250 m²
       3) Mobilização avulsa
       4) Honorário de projeto livre R$ 5.000
  • APROVAÇÃO da proposta → cria obra "Residencial Bela Vista",
    snapshot do cronograma, materializa cronograma 3 níveis com pesos,
    abre ItemMedicaoComercial e a única `ContaReceber` cumulativa.
  • 2 RDOs FINALIZADOS (Carlos + Pedro alocados, progresso 30 → 60 %).
  • 1 medição quinzenal #001 APROVADA → atualiza ContaReceber OBR-MED.

GUARDA DE PRODUÇÃO
------------------
Por padrão o script roda em modo `dev`. Para rodar em prod:
    SIGE_ALLOW_PROD_SEED=1 python3 scripts/seed_demo_alfa.py --ambiente prod
Se em prod o admin Alfa já existir e `--reset` não for passado, o script
ABORTA com exit 2 (não faz no-op silencioso) — exigindo decisão explícita.

USO
---
    # Dev (padrão)
    python3 scripts/seed_demo_alfa.py
    python3 scripts/seed_demo_alfa.py --reset    # apaga e replanta dataset Alfa

    # Produção (acionamento manual e consciente)
    SIGE_ALLOW_PROD_SEED=1 \\
      python3 scripts/seed_demo_alfa.py --ambiente prod
    SIGE_ALLOW_PROD_SEED=1 \\
      python3 scripts/seed_demo_alfa.py --ambiente prod --reset
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="[seed-demo-alfa] %(levelname)s %(message)s",
)
log = logging.getLogger("seed_demo_alfa")

# ---- Identidade canônica do tenant Alfa ------------------------------------
ADMIN_EMAIL = "admin@construtoraalfa.com.br"
ADMIN_USERNAME = "admin_alfa"
ADMIN_PASSWORD = "Alfa@2026"

CLIENTE_NOME = "João da Silva"
CLIENTE_EMAIL = "joao.silva@example.com"
CLIENTE_TELEFONE = "(11) 99000-1234"
CLIENTE_DOC = "123.456.789-09"  # CPF (PF). Vai no campo `cnpj` do modelo.

OBRA_NOME = "Residencial Bela Vista"
OBRA_CODIGO = "OBR-2026-001"

PROPOSTA_NUMERO = "001.26"

CARLOS_CPF = "900.901.001-01"
PEDRO_CPF = "900.901.002-02"


def _admin_existente():
    from models import Usuario
    return Usuario.query.filter_by(email=ADMIN_EMAIL).first()


# ---------------------------------------------------------------------------
# RESET (apaga TUDO do tenant Alfa, em ordem segura para FKs)
# ---------------------------------------------------------------------------
def _reset_dataset():
    from app import db
    from sqlalchemy import text

    admin = _admin_existente()
    if not admin:
        log.info("nada a resetar (admin Alfa inexistente)")
        return
    aid = admin.id
    log.info(f"resetando dataset do admin Alfa (id={aid})")

    # Etapa 1: NULL nas FKs cruzadas que impedem deleção em cadeia
    db.session.execute(text(
        "UPDATE medicao_obra SET conta_receber_id=NULL "
        "WHERE conta_receber_id IN "
        "(SELECT id FROM conta_receber WHERE admin_id=:a)"
    ), {"a": aid})
    db.session.execute(text(
        "UPDATE conta_receber SET obra_id=NULL WHERE admin_id=:a"
    ), {"a": aid})
    db.session.execute(text(
        "UPDATE obra SET responsavel_id=NULL "
        "WHERE responsavel_id IN (SELECT id FROM funcionario WHERE admin_id=:a)"
    ), {"a": aid})

    # Etapa 2: deleção em cascata manual (filhos antes dos pais)
    deletes = [
        # Medição
        "DELETE FROM medicao_obra_item WHERE admin_id=:a",
        "DELETE FROM medicao_obra WHERE admin_id=:a",
        "DELETE FROM item_medicao_cronograma_tarefa WHERE admin_id=:a",
        "DELETE FROM item_medicao_comercial WHERE admin_id=:a",
        # RDO
        "DELETE FROM rdo_servico_subatividade WHERE admin_id=:a",
        "DELETE FROM rdo_mao_obra WHERE admin_id=:a",
        "DELETE FROM rdo_mao_obra WHERE funcionario_id IN "
        "(SELECT id FROM funcionario WHERE admin_id=:a)",
        "DELETE FROM rdo WHERE admin_id=:a",
        # Cronograma da obra
        "DELETE FROM tarefa_cronograma WHERE admin_id=:a",
        # Custos / propostas / obras
        "DELETE FROM obra_servico_custo WHERE admin_id=:a",
        "DELETE FROM proposta_itens WHERE admin_id=:a",
        "DELETE FROM proposta_historico WHERE admin_id=:a",
        "DELETE FROM propostas_comerciais WHERE admin_id=:a OR criado_por=:a",
        "DELETE FROM obra WHERE admin_id=:a",
        # Catálogo
        "DELETE FROM composicao_servico WHERE admin_id=:a",
        "DELETE FROM cronograma_template_item WHERE admin_id=:a",
        "DELETE FROM cronograma_template WHERE admin_id=:a",
        "DELETE FROM servico WHERE admin_id=:a",
        "DELETE FROM subatividade_mestre WHERE admin_id=:a",
        "DELETE FROM preco_base_insumo WHERE admin_id=:a",
        "DELETE FROM insumo WHERE admin_id=:a",
        # Pessoas / config
        "DELETE FROM funcionario WHERE admin_id=:a",
        "DELETE FROM cliente WHERE admin_id=:a",
        "DELETE FROM conta_receber WHERE admin_id=:a",
        "DELETE FROM configuracao_empresa WHERE admin_id=:a",
        "DELETE FROM calendario_empresa WHERE admin_id=:a",
        "DELETE FROM usuario WHERE admin_id=:a",
        "DELETE FROM usuario WHERE id=:a",
    ]
    for sql in deletes:
        db.session.execute(text(sql), {"a": aid})
    db.session.commit()
    log.info("reset concluído")


# ---------------------------------------------------------------------------
# SEED — populador idempotente (chamado quando admin Alfa não existe)
# ---------------------------------------------------------------------------
def _seed():
    from app import db
    from werkzeug.security import generate_password_hash
    from models import (
        Usuario, TipoUsuario, Funcionario, Cliente, ConfiguracaoEmpresa,
        Insumo, PrecoBaseInsumo, SubatividadeMestre, CronogramaTemplate,
        CronogramaTemplateItem, Servico, ComposicaoServico,
        Proposta, PropostaItem, Obra, ItemMedicaoComercial,
        TarefaCronograma, RDO, RDOMaoObra, RDOServicoSubatividade,
        ContaReceber,
    )
    from services.cronograma_proposta import (
        montar_arvore_preview, materializar_cronograma,
    )
    from services.medicao_service import gerar_medicao_quinzenal, fechar_medicao

    # 1) Admin --------------------------------------------------------------
    admin = Usuario(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        nome="Construtora Alfa",
        password_hash=generate_password_hash(ADMIN_PASSWORD),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema="v1",
    )
    db.session.add(admin); db.session.flush()
    aid = admin.id
    log.info(f"admin criado id={aid}  email={ADMIN_EMAIL}")

    # 2) Configuração da empresa -------------------------------------------
    db.session.add(ConfiguracaoEmpresa(
        admin_id=aid,
        nome_empresa="Construtora Alfa Ltda",
        cnpj="12.345.678/0001-90",
        endereco="Rua das Pedras, 100 — Centro",
        telefone="(11) 4000-0000",
        email="contato@construtoraalfa.com.br",
        cor_primaria="#1976d2",
        cor_secundaria="#455a64",
        prazo_entrega_padrao=120,
        validade_padrao=15,
    ))

    # 3) Cliente João da Silva (PF) ----------------------------------------
    cliente = Cliente(
        nome=CLIENTE_NOME,
        email=CLIENTE_EMAIL,
        telefone=CLIENTE_TELEFONE,
        endereco="Rua das Acácias, 250 — São Paulo / SP",
        cnpj=CLIENTE_DOC,  # campo aceita CPF também
        admin_id=aid,
    )
    db.session.add(cliente); db.session.flush()

    # 4) Funcionários — Carlos mensalista, Pedro diarista ------------------
    carlos = Funcionario(
        codigo="ALF001",
        nome="Carlos Pereira",
        cpf=CARLOS_CPF,
        data_admissao=date(2024, 1, 15),
        salario=2800.00,
        valor_diaria=0.0,
        tipo_remuneracao="salario",
        jornada_semanal=44,
        ativo=True, admin_id=aid,
        valor_va=22.00, valor_vt=12.00,
        chave_pix=CARLOS_CPF,
        email="carlos@construtoraalfa.com.br",
        telefone="(11) 90000-0001",
    )
    pedro = Funcionario(
        codigo="ALF002",
        nome="Pedro Souza",
        cpf=PEDRO_CPF,
        data_admissao=date(2025, 6, 1),
        salario=0.0,
        valor_diaria=180.00,
        tipo_remuneracao="diaria",
        jornada_semanal=44,
        ativo=True, admin_id=aid,
        valor_va=22.00, valor_vt=12.00,
        chave_pix=PEDRO_CPF,
        email="pedro@construtoraalfa.com.br",
        telefone="(11) 90000-0002",
    )
    db.session.add_all([carlos, pedro]); db.session.flush()

    # 5) Insumos básicos com preço base ------------------------------------
    insumos_def = [
        ("Cimento CP II 50kg",       "MATERIAL",    "sc", 38.50),
        ("Bloco cerâmico 9x19x19",   "MATERIAL",    "un",  1.20),
        ("Areia média m³",           "MATERIAL",    "m3", 95.00),
        ("Hora pedreiro",            "MAO_OBRA",    "h",  28.00),
        ("Hora servente",            "MAO_OBRA",    "h",  18.00),
        ("Diária encarregado",       "MAO_OBRA",    "dia", 200.00),
        ("Betoneira hora",           "EQUIPAMENTO", "h",  25.00),
    ]
    insumos_obj = {}
    for nome, tipo, un, preco in insumos_def:
        ins = Insumo(admin_id=aid, nome=nome, tipo=tipo, unidade=un, ativo=True)
        db.session.add(ins); db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=aid, insumo_id=ins.id,
            valor=Decimal(str(preco)),
            vigencia_inicio=date(2025, 1, 1),
        ))
        insumos_obj[nome] = ins

    # 6) Catálogo de subatividades + 2 templates de cronograma -------------
    def _sub(nome, horas, unidade, meta, complex_=2):
        sm = SubatividadeMestre(
            tipo="subatividade", nome=nome, descricao=nome,
            duracao_estimada_horas=horas, unidade_medida=unidade,
            meta_produtividade=meta, obrigatoria=True, complexidade=complex_,
            admin_id=aid, ativo=True,
        )
        db.session.add(sm); return sm

    sub_marcacao   = _sub("Marcação de paredes",      8.0, "m linear", 5.0)
    sub_elevacao   = _sub("Elevação de alvenaria",   32.0, "m²",       1.5)
    sub_chapisco   = _sub("Chapisco",                12.0, "m²",       3.0)
    sub_prep_piso  = _sub("Preparação do contrapiso", 8.0, "m²",       4.0)
    sub_lancamento = _sub("Lançamento e desempeno",  20.0, "m²",       2.5)
    db.session.flush()

    # Template Alvenaria
    tmpl_alv = CronogramaTemplate(
        nome="Alvenaria de bloco cerâmico — padrão",
        descricao="Marcação → Elevação → Chapisco",
        categoria="Vedação", ativo=True, admin_id=aid,
    )
    db.session.add(tmpl_alv); db.session.flush()
    g_alv = CronogramaTemplateItem(
        template_id=tmpl_alv.id, nome_tarefa="Alvenaria",
        ordem=10, duracao_dias=1, admin_id=aid,
    )
    db.session.add(g_alv); db.session.flush()
    db.session.add_all([
        CronogramaTemplateItem(
            template_id=tmpl_alv.id, parent_item_id=g_alv.id,
            subatividade_mestre_id=sub_marcacao.id,
            nome_tarefa="Marcação de paredes",
            ordem=11, duracao_dias=2, quantidade_prevista=80.0,
            responsavel="empresa", admin_id=aid,
        ),
        CronogramaTemplateItem(
            template_id=tmpl_alv.id, parent_item_id=g_alv.id,
            subatividade_mestre_id=sub_elevacao.id,
            nome_tarefa="Elevação de alvenaria",
            ordem=12, duracao_dias=8, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
        CronogramaTemplateItem(
            template_id=tmpl_alv.id, parent_item_id=g_alv.id,
            subatividade_mestre_id=sub_chapisco.id,
            nome_tarefa="Chapisco",
            ordem=13, duracao_dias=3, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
    ]); db.session.flush()

    # Template Contrapiso
    tmpl_pis = CronogramaTemplate(
        nome="Contrapiso desempenado — padrão",
        descricao="Preparação → Lançamento e desempeno",
        categoria="Piso", ativo=True, admin_id=aid,
    )
    db.session.add(tmpl_pis); db.session.flush()
    g_pis = CronogramaTemplateItem(
        template_id=tmpl_pis.id, nome_tarefa="Contrapiso",
        ordem=20, duracao_dias=1, admin_id=aid,
    )
    db.session.add(g_pis); db.session.flush()
    db.session.add_all([
        CronogramaTemplateItem(
            template_id=tmpl_pis.id, parent_item_id=g_pis.id,
            subatividade_mestre_id=sub_prep_piso.id,
            nome_tarefa="Preparação do contrapiso",
            ordem=21, duracao_dias=2, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
        CronogramaTemplateItem(
            template_id=tmpl_pis.id, parent_item_id=g_pis.id,
            subatividade_mestre_id=sub_lancamento.id,
            nome_tarefa="Lançamento e desempeno",
            ordem=22, duracao_dias=4, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
    ]); db.session.flush()

    # 7) 3 Serviços de catálogo --------------------------------------------
    serv_alv = Servico(
        nome="Alvenaria de bloco cerâmico",
        descricao="Alvenaria de vedação 9x19x19 com chapisco",
        categoria="Vedação", unidade_medida="m2", unidade_simbolo="m²",
        custo_unitario=85.00, complexidade=3, ativo=True,
        imposto_pct=Decimal("8.0"), margem_lucro_pct=Decimal("25.0"),
        preco_venda_unitario=Decimal("145.00"),
        template_padrao_id=tmpl_alv.id, admin_id=aid,
    )
    serv_pis = Servico(
        nome="Contrapiso desempenado",
        descricao="Contrapiso desempenado e=4cm",
        categoria="Piso", unidade_medida="m2", unidade_simbolo="m²",
        custo_unitario=42.00, complexidade=2, ativo=True,
        imposto_pct=Decimal("8.0"), margem_lucro_pct=Decimal("25.0"),
        preco_venda_unitario=Decimal("70.00"),
        template_padrao_id=tmpl_pis.id, admin_id=aid,
    )
    serv_mob = Servico(
        nome="Mobilização de obra",
        descricao="Container, alojamento e transporte inicial (sem template)",
        categoria="Serviços gerais", unidade_medida="verba", unidade_simbolo="vb",
        custo_unitario=2500.00, complexidade=1, ativo=True,
        imposto_pct=Decimal("8.0"), margem_lucro_pct=Decimal("20.0"),
        preco_venda_unitario=Decimal("3500.00"),
        template_padrao_id=None, admin_id=aid,
    )
    db.session.add_all([serv_alv, serv_pis, serv_mob]); db.session.flush()

    # Composição mínima do serviço de alvenaria (paramétrica)
    for nome_ins, coef in [
        ("Cimento CP II 50kg",     "0.04"),
        ("Bloco cerâmico 9x19x19", "28.0"),
        ("Areia média m³",         "0.02"),
        ("Hora pedreiro",          "0.60"),
        ("Hora servente",          "0.40"),
    ]:
        db.session.add(ComposicaoServico(
            admin_id=aid, servico_id=serv_alv.id,
            insumo_id=insumos_obj[nome_ins].id,
            coeficiente=Decimal(coef),
        ))
    # Composição mínima do contrapiso
    for nome_ins, coef in [
        ("Cimento CP II 50kg", "0.10"),
        ("Areia média m³",     "0.04"),
        ("Hora pedreiro",      "0.30"),
        ("Hora servente",      "0.20"),
    ]:
        db.session.add(ComposicaoServico(
            admin_id=aid, servico_id=serv_pis.id,
            insumo_id=insumos_obj[nome_ins].id,
            coeficiente=Decimal(coef),
        ))
    db.session.flush()

    # 8) Proposta 001.26 com 4 itens ---------------------------------------
    proposta = Proposta(
        numero=PROPOSTA_NUMERO,
        data_proposta=date(2026, 1, 10),
        cliente_id=cliente.id,
        cliente_nome=CLIENTE_NOME,
        cliente_telefone=CLIENTE_TELEFONE,
        cliente_email=CLIENTE_EMAIL,
        cliente_endereco="Rua das Acácias, 250 — São Paulo / SP",
        titulo="Residencial Bela Vista — execução civil",
        descricao=(
            "Execução de alvenaria de vedação, contrapiso e mobilização "
            "para o Residencial Bela Vista (lote único)."
        ),
        prazo_entrega_dias=120, validade_dias=15,
        status="rascunho",  # virá APROVADA após snapshot+materialização
        valor_total=Decimal("0.00"),
        criado_por=aid, admin_id=aid,
        data_envio=datetime(2026, 1, 11, 10, 0),
    )
    db.session.add(proposta); db.session.flush()

    itens_def = [
        # (descricao, qtd, unidade, preco_unit, servico, ordem)
        ("Alvenaria de bloco cerâmico — Bloco A",
         Decimal("250.000"), "m2", Decimal("145.00"), serv_alv, 1),
        ("Contrapiso desempenado — Bloco A",
         Decimal("250.000"), "m2", Decimal("70.00"),  serv_pis, 2),
        ("Mobilização de obra (avulsa)",
         Decimal("1.000"),   "vb", Decimal("3500.00"), serv_mob, 3),
        ("Honorário de projeto e acompanhamento",
         Decimal("1.000"),   "vb", Decimal("5000.00"), None,     4),
    ]
    valor_total = Decimal("0.00")
    propostaitem_objs = []
    for idx, (desc, qtd, un, preco, serv, ordem) in enumerate(itens_def, start=1):
        sub = (qtd * preco).quantize(Decimal("0.01"))
        valor_total += sub
        pi = PropostaItem(
            admin_id=aid, proposta_id=proposta.id,
            item_numero=idx, descricao=desc,
            quantidade=qtd, unidade=un,
            preco_unitario=preco, ordem=ordem,
            servico_id=(serv.id if serv else None),
            quantidade_medida=qtd,
            custo_unitario=(Decimal(str(serv.custo_unitario)) if serv else preco),
            lucro_unitario=(
                (preco - Decimal(str(serv.custo_unitario))) if serv else Decimal("0")
            ),
            subtotal=sub,
        )
        db.session.add(pi)
        propostaitem_objs.append(pi)
    db.session.flush()
    proposta.valor_total = valor_total

    # 9) Obra "Residencial Bela Vista" (criada pela aprovação) -------------
    obra = Obra(
        nome=OBRA_NOME, codigo=OBRA_CODIGO,
        endereco="Rua das Acácias, 250 — São Paulo / SP",
        data_inicio=date(2026, 2, 2),
        data_previsao_fim=date(2026, 6, 2),
        orcamento=float(valor_total),
        valor_contrato=float(valor_total),
        area_total_m2=250.0,
        status="Em andamento",
        cliente=CLIENTE_NOME, cliente_nome=CLIENTE_NOME,
        cliente_email=CLIENTE_EMAIL, cliente_telefone=CLIENTE_TELEFONE,
        proposta_origem_id=proposta.id, portal_ativo=True,
        responsavel_id=pedro.id, ativo=True, admin_id=aid,
        data_inicio_medicao=date(2026, 2, 1),
        valor_entrada=Decimal("0.00"), data_entrada=None,
    )
    db.session.add(obra); db.session.flush()
    proposta.obra_id = obra.id
    proposta.convertida_em_obra = True
    proposta.status = "aprovada"
    proposta.data_resposta_cliente = datetime(2026, 1, 18, 14, 30)

    # 10) Snapshot + propagação proposta→obra (1:1 PropostaItem→IMC) ------
    arvore = montar_arvore_preview(proposta, aid)
    proposta.cronograma_default_json = arvore

    for pi in propostaitem_objs:
        db.session.add(ItemMedicaoComercial(
            admin_id=aid, obra_id=obra.id,
            nome=pi.descricao[:200],
            valor_comercial=pi.subtotal,
            servico_id=pi.servico_id,
            quantidade=pi.quantidade,
            proposta_item_id=pi.id,
            status="PENDENTE",
        ))
    db.session.flush()

    n_tarefas = materializar_cronograma(proposta, aid, obra.id, arvore)
    log.info(f"cronograma materializado: {n_tarefas} tarefas (com pesos)")
    db.session.flush()

    # 11) 2 RDOs FINALIZADOS — Carlos + Pedro alocados ---------------------
    folhas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra.id, admin_id=aid, is_cliente=False)
        .filter(TarefaCronograma.subatividade_mestre_id.isnot(None))
        .order_by(TarefaCronograma.ordem.asc())
        .all()
    )
    log.info(f"folhas do cronograma: {len(folhas)}")

    rdos_dados = [
        (date(2026, 2, 5),  30.0, 8.0),
        (date(2026, 2, 12), 60.0, 8.0),
    ]
    for idx, (dt, perc_destino, horas) in enumerate(rdos_dados, start=1):
        rdo = RDO(
            numero_rdo=f"RDO-2026-{idx:03d}",
            data_relatorio=dt, obra_id=obra.id,
            criado_por_id=aid, admin_id=aid,
            clima_geral="Ensolarado", temperatura_media="26°C",
            condicoes_trabalho="Ideais", local="Campo",
            comentario_geral=f"Avanço da semana — meta atingida ({perc_destino:.0f}%).",
            status="Finalizado",
        )
        db.session.add(rdo); db.session.flush()

        for folha in folhas:
            db.session.add(RDOMaoObra(
                admin_id=aid, rdo_id=rdo.id,
                funcionario_id=carlos.id, funcao_exercida="Pedreiro",
                horas_trabalhadas=horas, horas_extras=0.0,
                tarefa_cronograma_id=folha.id,
            ))
            db.session.add(RDOMaoObra(
                admin_id=aid, rdo_id=rdo.id,
                funcionario_id=pedro.id, funcao_exercida="Encarregado (diária)",
                horas_trabalhadas=horas, horas_extras=0.0,
                tarefa_cronograma_id=folha.id,
            ))
            perc_anterior = 0.0 if idx == 1 else 30.0
            db.session.add(RDOServicoSubatividade(
                rdo_id=rdo.id,
                servico_id=(serv_alv.id if "alvenaria" in folha.nome_tarefa.lower()
                            or "marcação" in folha.nome_tarefa.lower()
                            or "chapisco" in folha.nome_tarefa.lower()
                            else serv_pis.id),
                nome_subatividade=folha.nome_tarefa,
                descricao_subatividade=folha.nome_tarefa,
                percentual_conclusao=perc_destino,
                percentual_anterior=perc_anterior,
                incremento_dia=perc_destino - perc_anterior,
                ordem_execucao=folha.ordem, ativo=True,
                admin_id=aid,
                subatividade_mestre_id=folha.subatividade_mestre_id,
            ))
            folha.percentual_concluido = perc_destino
        db.session.flush()
        log.info(f"RDO #{idx} ({dt.isoformat()}) finalizado — folhas a {perc_destino:.0f}%")

    db.session.commit()

    # 12) Medição quinzenal #001 + APROVAÇÃO → ContaReceber OBR-MED -------
    medicao, err = gerar_medicao_quinzenal(
        obra_id=obra.id, admin_id=aid,
        periodo_inicio=date(2026, 2, 1),
        periodo_fim=date(2026, 2, 15),
        observacoes="Primeira medição — alvenaria/contrapiso a 60%.",
    )
    if err:
        raise RuntimeError(f"falha ao gerar medição: {err}")
    log.info(f"medição #{medicao.numero:03d} gerada — R$ "
             f"{float(medicao.valor_total_medido_periodo or 0):.2f}")

    medicao_aprovada, err2 = fechar_medicao(medicao.id, aid)
    if err2:
        raise RuntimeError(f"falha ao fechar medição: {err2}")
    log.info(f"medição #{medicao_aprovada.numero:03d} APROVADA")

    cr = ContaReceber.query.filter_by(
        admin_id=aid, origem_tipo="OBRA_MEDICAO", origem_id=obra.id,
    ).first()

    return {
        "admin_id": aid,
        "cliente_id": cliente.id,
        "carlos_id": carlos.id,
        "pedro_id": pedro.id,
        "servico_alvenaria_id": serv_alv.id,
        "servico_contrapiso_id": serv_pis.id,
        "servico_mobilizacao_id": serv_mob.id,
        "template_alvenaria_id": tmpl_alv.id,
        "template_contrapiso_id": tmpl_pis.id,
        "proposta_id": proposta.id,
        "proposta_numero": proposta.numero,
        "obra_id": obra.id,
        "obra_codigo": obra.codigo,
        "n_tarefas": n_tarefas,
        "n_rdos": len(rdos_dados),
        "medicao_id": medicao_aprovada.id,
        "medicao_numero": medicao_aprovada.numero,
        "conta_receber_id": cr.id if cr else None,
        "conta_receber_numero": cr.numero_documento if cr else None,
        "conta_receber_valor": float(cr.valor_original or 0) if cr else 0.0,
        "valor_total_proposta": float(valor_total),
    }


# ---------------------------------------------------------------------------
# Bloco final "Demo pronta"
# ---------------------------------------------------------------------------
def _imprimir_demo_pronta(info: dict, ambiente: str):
    base_url = (
        "https://construtoraalfa.estruturasdoval.com.br"
        if ambiente == "prod"
        else "http://localhost:5000"
    )
    log.info("")
    log.info("=" * 72)
    log.info(" DEMO CONSTRUTORA ALFA — Credenciais e estado pronto")
    log.info("=" * 72)
    log.info(f"  URL de login : {base_url}/login")
    log.info(f"  E-mail       : {ADMIN_EMAIL}")
    log.info(f"  Senha        : {ADMIN_PASSWORD}")
    log.info("")
    log.info("  IDs principais:")
    log.info(f"    admin_id           = {info['admin_id']}")
    log.info(f"    cliente_id         = {info['cliente_id']}  ({CLIENTE_NOME})")
    log.info(f"    carlos_id          = {info['carlos_id']}  (mensalista R$ 2.800)")
    log.info(f"    pedro_id           = {info['pedro_id']}  (diarista R$ 180/dia)")
    log.info(f"    servico_alvenaria  = {info['servico_alvenaria_id']}  "
             f"(template {info['template_alvenaria_id']})")
    log.info(f"    servico_contrapiso = {info['servico_contrapiso_id']}  "
             f"(template {info['template_contrapiso_id']})")
    log.info(f"    servico_mobilizacao= {info['servico_mobilizacao_id']}  "
             f"(SEM template)")
    log.info(f"    proposta_id        = {info['proposta_id']}  "
             f"(nº {info['proposta_numero']}, R$ "
             f"{info['valor_total_proposta']:.2f})")
    log.info(f"    obra_id            = {info['obra_id']}  "
             f"({info['obra_codigo']} — {OBRA_NOME})")
    log.info(f"    cronograma         = {info['n_tarefas']} tarefas "
             f"materializadas (3 níveis)")
    log.info(f"    rdos finalizados   = {info['n_rdos']}")
    log.info(f"    medicao_id         = {info['medicao_id']}  "
             f"(#{info['medicao_numero']:03d} APROVADA)")
    log.info(f"    conta_receber_id   = {info['conta_receber_id']}  "
             f"({info['conta_receber_numero']} — R$ "
             f"{info['conta_receber_valor']:.2f})")
    log.info("")
    log.info("  Roteiro sugerido (10 telas, na ordem):")
    log.info(f"   1) Dashboard         → {base_url}/dashboard")
    log.info(f"   2) Funcionários      → {base_url}/funcionarios")
    log.info(f"   3) Catálogo serviços → {base_url}/catalogo/servicos")
    log.info(f"   4) Propostas         → {base_url}/propostas/")
    log.info(f"   5) Proposta detalhe  → {base_url}/propostas/{info['proposta_id']}")
    log.info(f"   6) Obra detalhe      → {base_url}/obras/{info['obra_id']}")
    log.info(f"   7) Cronograma        → {base_url}/cronograma/obra/{info['obra_id']}")
    log.info(f"   8) RDOs              → {base_url}/rdo")
    log.info(f"   9) Medição           → {base_url}/obras/{info['obra_id']}/medicao")
    log.info(f"  10) Contas a Receber  → {base_url}/financeiro/contas-receber")
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# Entry point com guarda de produção
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed demo Construtora Alfa (idempotente)."
    )
    parser.add_argument(
        "--ambiente", choices=["dev", "prod"], default="dev",
        help="Ambiente alvo (default: dev). Em prod exige "
             "SIGE_ALLOW_PROD_SEED=1.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Apaga o tenant Alfa por inteiro antes de replantar.",
    )
    args = parser.parse_args(argv)

    # Guarda de produção
    if args.ambiente == "prod":
        if os.environ.get("SIGE_ALLOW_PROD_SEED") != "1":
            log.error(
                "execução em produção bloqueada — defina "
                "SIGE_ALLOW_PROD_SEED=1 e re-execute"
            )
            return 2

    try:
        from app import app, db  # noqa: F401
    except Exception as e:
        log.error(f"falha ao importar app: {e}")
        return 1

    with app.app_context():
        try:
            if args.reset:
                _reset_dataset()

            existente = _admin_existente()
            if existente and not args.reset:
                if args.ambiente == "prod":
                    log.error(
                        f"admin Alfa já existe em produção (id={existente.id}) "
                        "— passe --reset para wipe+replantar (ato consciente) "
                        "ou remova essa execução"
                    )
                    return 2
                log.info(
                    f"admin Alfa já populado (id={existente.id}) — no-op "
                    "idempotente em dev. Use --reset para replantar."
                )
                return 0

            log.info(
                f"plantando dataset Alfa (ambiente={args.ambiente})…"
            )
            info = _seed()
            _imprimir_demo_pronta(info, args.ambiente)
            return 0

        except Exception as e:
            from app import db
            db.session.rollback()
            log.exception(f"erro durante seed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
