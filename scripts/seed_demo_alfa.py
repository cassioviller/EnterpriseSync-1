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
JOAO_CPF = "900.901.003-03"
MARCOS_CPF = "900.901.004-04"


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

    # Etapa 0: limpa órfãos de runs anteriores (admin_id NULL com CPFs/códigos
    # do dataset demo). Acontece quando uma rodada falhou no meio e a passagem
    # dinâmica acabou nulificando admin_id em vez de deletar.
    try:
        db.session.execute(text("""
            DELETE FROM rdo_mao_obra
             WHERE funcionario_id IN (
                SELECT id FROM funcionario
                 WHERE admin_id IS NULL AND cpf LIKE '900.901%'
            )
        """))
        db.session.execute(text(
            "DELETE FROM funcionario WHERE admin_id IS NULL AND cpf LIKE '900.901%'"
        ))
    except Exception as _orph:
        log.debug(f"limpeza de órfãos demo: {_orph}")

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
    # NULL proposta_origem_id antes de deletar propostas (FK bidirecional)
    db.session.execute(text(
        "UPDATE obra SET proposta_origem_id=NULL WHERE admin_id=:a"
    ), {"a": aid})
    # plano_contas é auto-referente via conta_pai_codigo. Quebra o ciclo
    # antes da deleção para que a passagem dinâmica consiga remover as
    # linhas do tenant; sem isso, o DELETE FROM plano_contas WHERE
    # admin_id=:a falha por FK self-reference e bloqueia a remoção
    # final do próprio usuário (plano_contas_admin_id_fkey).
    db.session.execute(text(
        "UPDATE plano_contas SET conta_pai_codigo=NULL WHERE admin_id=:a"
    ), {"a": aid})
    # Pré-checagem multi-tenant: se OUTRO tenant tem
    # partida_contabil/lancamento_contabil referenciando códigos do plano de
    # contas DESTE admin, o reset NÃO PODE prosseguir — destruir esses
    # registros violaria isolamento de tenants. Aborta com erro claro e
    # deixa o operador limpar a inconsistência manualmente.
    xt_partida = db.session.execute(text(
        "SELECT COUNT(*) FROM partida_contabil pc "
        "WHERE pc.conta_codigo IN "
        "(SELECT codigo FROM plano_contas WHERE admin_id=:a) "
        "AND pc.admin_id != :a"
    ), {"a": aid}).scalar() or 0
    if xt_partida > 0:
        log.error(
            f"reset abortado: {xt_partida} partida_contabil de OUTRO(S) "
            f"tenant(s) referencia(m) o plano de contas do admin id={aid}. "
            "Esses registros indicam pollution cross-tenant (provavelmente "
            "de seeds/testes antigos) e devem ser removidos manualmente "
            "antes de executar --reset. Reset NÃO mexe em outros tenants."
        )
        db.session.rollback()
        raise RuntimeError(
            f"cross-tenant plano_contas FK refs ({xt_partida}) — "
            "limpe manualmente antes de re-tentar --reset"
        )

    # Etapa 2: deleção em cascata manual (filhos antes dos pais)
    deletes = [
        # ---- Pré-limpezas: quebra ciclos e zera FKs nullables que apontam
        # para tabelas que serão deletadas mais adiante (fornecedor, cliente,
        # almoxarifado_*). Sem isso o DELETE da tabela-mãe falha por FK.
        # Ciclo almoxarifado_estoque <-> almoxarifado_movimento.
        "UPDATE almoxarifado_estoque SET entrada_movimento_id=NULL WHERE admin_id=:a",
        "UPDATE almoxarifado_movimento SET fornecedor_id=NULL WHERE admin_id=:a",
        # Dependentes de fornecedor (delete antes de deletar fornecedor).
        "DELETE FROM nota_fiscal WHERE fornecedor_id IN (SELECT id FROM fornecedor WHERE admin_id=:a)",
        "DELETE FROM obra_servico_cotacao_interna WHERE fornecedor_id IN (SELECT id FROM fornecedor WHERE admin_id=:a)",
        "UPDATE conta_pagar SET fornecedor_id=NULL WHERE fornecedor_id IN (SELECT id FROM fornecedor WHERE admin_id=:a)",
        "UPDATE gestao_custo_pai SET fornecedor_id=NULL WHERE fornecedor_id IN (SELECT id FROM fornecedor WHERE admin_id=:a)",
        # Dependentes de cliente.
        "UPDATE lead SET cliente_id=NULL WHERE cliente_id IN (SELECT id FROM cliente WHERE admin_id=:a)",
        # Centro de custo aponta para obra → precisa morrer antes da obra.
        "DELETE FROM centro_custo WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM centro_custo WHERE admin_id=:a",
        # Obras órfãs (admin_id pode ter sido nulificado por uma rodada de
        # reset anterior, mas continuam apontando para clientes desse tenant).
        # Capturar tudo que esteja ligado a clientes deste admin antes de
        # tentar deletar a tabela cliente.
        "UPDATE obra SET admin_id=:a WHERE admin_id IS NULL AND cliente_id IN (SELECT id FROM cliente WHERE admin_id=:a)",
        # Medição
        "DELETE FROM medicao_obra_item WHERE admin_id=:a",
        "DELETE FROM medicao_obra WHERE admin_id=:a",
        "DELETE FROM item_medicao_cronograma_tarefa WHERE admin_id=:a",
        "DELETE FROM item_medicao_comercial WHERE admin_id=:a",
        # RDO (todos os filhos antes do pai)
        "DELETE FROM rdo_servico_subatividade WHERE admin_id=:a",
        "DELETE FROM rdo_mao_obra WHERE admin_id=:a",
        "DELETE FROM rdo_mao_obra WHERE funcionario_id IN "
        "(SELECT id FROM funcionario WHERE admin_id=:a)",
        "DELETE FROM rdo_equipamento WHERE rdo_id IN "
        "(SELECT id FROM rdo WHERE admin_id=:a)",
        "DELETE FROM rdo_ocorrencia WHERE rdo_id IN "
        "(SELECT id FROM rdo WHERE admin_id=:a)",
        "DELETE FROM rdo_apontamento_cronograma WHERE admin_id=:a",
        "DELETE FROM rdo WHERE admin_id=:a",
        # Cronograma da obra
        "DELETE FROM tarefa_cronograma WHERE admin_id=:a",
        # Custos V2 (criados pelo backfill _backfill_custos_rdo_demo)
        "DELETE FROM gestao_custo_filho WHERE pai_id IN "
        "(SELECT id FROM gestao_custo_pai WHERE admin_id=:a)",
        "DELETE FROM gestao_custo_pai WHERE admin_id=:a",
        # Todas as tabelas com FK obra_id (descobertas via information_schema)
        # ---- Alimentação ----
        "DELETE FROM alimentacao_lancamento_item WHERE lancamento_id IN "
        "(SELECT id FROM alimentacao_lancamento WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a))",
        "DELETE FROM alimentacao_funcionarios_assoc WHERE admin_id=:a",
        "DELETE FROM alimentacao_lancamento WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM alimentacao_lancamento WHERE admin_id=:a",
        # ---- Mapa de concorrência (filhos primeiro) ----
        "DELETE FROM mapa_cotacao WHERE mapa_id IN "
        "(SELECT id FROM mapa_concorrencia_v2 WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a))",
        "DELETE FROM mapa_item_cotacao WHERE mapa_id IN "
        "(SELECT id FROM mapa_concorrencia_v2 WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a))",
        "DELETE FROM mapa_fornecedor WHERE mapa_id IN "
        "(SELECT id FROM mapa_concorrencia_v2 WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a))",
        "DELETE FROM mapa_concorrencia_v2 WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM mapa_concorrencia WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Compras ----
        "DELETE FROM pedido_compra_item WHERE pedido_id IN "
        "(SELECT id FROM pedido_compra WHERE admin_id=:a)",
        "DELETE FROM pedido_compra WHERE admin_id=:a",
        # ---- Almoxarifado (movimentos/estoque/itens/categorias do tenant) ----
        "DELETE FROM almoxarifado_movimento WHERE admin_id=:a",
        "DELETE FROM almoxarifado_estoque WHERE admin_id=:a",
        "DELETE FROM almoxarifado_item WHERE admin_id=:a",
        "DELETE FROM almoxarifado_categoria WHERE admin_id=:a",
        # ---- Transporte ----
        "DELETE FROM lancamento_transporte WHERE admin_id=:a",
        "DELETE FROM categoria_transporte WHERE admin_id=:a",
        # ---- Serviços ----
        "DELETE FROM historico_produtividade_servico WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM servico_obra_real WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM servico_obra WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Ponto / Registro ----
        "DELETE FROM funcionario_obras_ponto WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM registro_ponto WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM registro_alimentacao WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Financeiro / Custos ----
        "DELETE FROM custo_obra WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM outro_custo WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM receita WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM fluxo_caixa WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM folha_processada WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM reembolso_funcionario WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM conta_pagar WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Cronograma cliente / Dispositivos ----
        "DELETE FROM cronograma_cliente WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM dispositivo_obra WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Alocação / Equipe ----
        "DELETE FROM alocacao_equipe WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        "DELETE FROM allocation WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Notificações ----
        "DELETE FROM notificacao_cliente WHERE admin_id=:a",
        "DELETE FROM notificacao_orcamento WHERE obra_id IN (SELECT id FROM obra WHERE admin_id=:a)",
        # ---- Custos / propostas / obras ----
        "DELETE FROM obra_servico_custo WHERE admin_id=:a",
        "DELETE FROM proposta_itens WHERE admin_id=:a",
        "DELETE FROM proposta_historico WHERE proposta_id IN "
        "(SELECT id FROM propostas_comerciais WHERE admin_id=:a OR criado_por=:a)",
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
        # Orçamentos (referenciam cliente)
        "DELETE FROM orcamento_item WHERE admin_id=:a",
        "DELETE FROM orcamento WHERE admin_id=:a",
        # Pessoas / config
        "DELETE FROM funcionario WHERE admin_id=:a",
        "DELETE FROM cliente WHERE admin_id=:a",
        "DELETE FROM conta_receber WHERE admin_id=:a",
        "DELETE FROM configuracao_empresa WHERE admin_id=:a",
        "DELETE FROM calendario_empresa WHERE admin_id=:a",
        "DELETE FROM restaurante WHERE admin_id=:a",
        "DELETE FROM fornecedor WHERE admin_id=:a",
        # Tabelas com admin_id FK para usuario que podem ter sobrado
        "DELETE FROM alimentacao_item WHERE admin_id=:a",
        "DELETE FROM almoxarifado_estoque WHERE admin_id=:a",
        "DELETE FROM almoxarifado_movimento WHERE admin_id=:a",
        "DELETE FROM movimentacao_estoque WHERE admin_id=:a",
        "DELETE FROM custo_veiculo WHERE admin_id=:a",
        "DELETE FROM uso_veiculo WHERE admin_id=:a",
        "DELETE FROM frota_despesa WHERE admin_id=:a",
        "DELETE FROM frota_utilizacao WHERE admin_id=:a",
        "DELETE FROM outro_custo WHERE admin_id=:a",
        "DELETE FROM receita WHERE admin_id=:a",
        "DELETE FROM fluxo_caixa WHERE admin_id=:a",
        "DELETE FROM weekly_plan WHERE admin_id=:a",
        # Contabilidade — partida_contabil e conciliacao_bancaria têm FK
        # para lancamento_contabil.id; precisam ser apagadas antes para que
        # a passagem dinâmica consiga deletar lancamento_contabil
        # (que tem admin_id NOT NULL e bloqueia o DELETE final do usuário).
        "DELETE FROM partida_contabil WHERE admin_id=:a OR lancamento_id IN "
        "(SELECT id FROM lancamento_contabil WHERE admin_id=:a)",
        "DELETE FROM conciliacao_bancaria WHERE admin_id=:a OR lancamento_id IN "
        "(SELECT id FROM lancamento_contabil WHERE admin_id=:a)",
        "DELETE FROM lancamento_contabil WHERE admin_id=:a",
        "DELETE FROM usuario WHERE admin_id=:a",
        # NÃO incluir "DELETE FROM usuario WHERE id=:a" aqui —
        # essa deleção final do próprio admin fica após o cleanup dinâmico.
    ]
    # Executa cada DELETE dentro de um SAVEPOINT individual.
    # Se uma tabela não existir ou tiver FK inesperado, o SAVEPOINT é
    # revertido e o statement é re-tentado em passes seguintes — assim
    # uma falha por dependência ainda não limpa converge depois.
    pending_sql = list(deletes)
    deleted_total = 0
    for _pass in range(5):
        next_pending = []
        progress = False
        prev_pending_count = len(pending_sql)
        for sql in pending_sql:
            try:
                db.session.execute(text("SAVEPOINT sp_reset_cleanup"))
                result = db.session.execute(text(sql), {"a": aid})
                db.session.execute(text("RELEASE SAVEPOINT sp_reset_cleanup"))
                rc = result.rowcount if result.rowcount and result.rowcount > 0 else 0
                deleted_total += rc
                # Sucesso (independente de rowcount) já é progresso porque
                # remove a tabela do conjunto pendente para a próxima passagem.
                progress = True
            except Exception as _e:
                db.session.execute(text("ROLLBACK TO SAVEPOINT sp_reset_cleanup"))
                next_pending.append(sql)
        pending_sql = next_pending
        # Convergiu se nada pendente OU se nenhum DELETE saiu da fila.
        if not pending_sql or len(pending_sql) == prev_pending_count:
            break
    skipped_persistent = pending_sql
    log.info(
        f"reset explícito: {deleted_total} registro(s) removido(s), "
        f"{len(skipped_persistent)} statement(s) pulado(s)"
    )
    if skipped_persistent:
        for sql in skipped_persistent:
            log.warning(f"reset skip persistente: {sql[:90]}")

    # Passagem dinâmica: para cada par (tabela, coluna) que tem FK apontando
    # para usuario.id onde o valor = aid, tenta DELETE ou NULL.
    # Isso garante que o usuario admin possa ser apagado independente de
    # qual coluna (admin_id, criado_por, responsavel_id, etc.) referencia aid.
    try:
        fk_cols = db.session.execute(text("""
            SELECT DISTINCT kcu.table_name, kcu.column_name,
                   col.is_nullable
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc
                ON rc.constraint_name = tc.constraint_name
            JOIN information_schema.key_column_usage ccu
                ON ccu.constraint_name = rc.unique_constraint_name
            JOIN information_schema.columns col
                ON col.table_name = kcu.table_name
                AND col.column_name = kcu.column_name
                AND col.table_schema = 'public'
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'usuario'
              AND kcu.table_schema = 'public'
            ORDER BY kcu.table_name
        """)).fetchall()
        # Loop de convergência: a ordem alfabética inicial pode falhar
        # quando uma tabela ainda tem dependentes não-limpos. Repetimos
        # até nenhum DELETE adicional acontecer (max 5 passes).
        pending = list(fk_cols)
        dyn_ok = 0
        for _pass in range(5):
            still_pending = []
            progress = False
            for (tbl, col, nullable) in pending:
                try:
                    db.session.execute(text("SAVEPOINT sp_dynclean"))
                    # Para colunas chamadas exatamente "admin_id" sempre
                    # DELETE — nulificar ali deixa registros órfãos do tenant
                    # (e quebra o reset idempotente). Para colunas nullable
                    # diferentes, NULL é seguro (autoria/responsável/etc.).
                    if nullable == "YES" and col != "admin_id":
                        db.session.execute(
                            text(f"UPDATE {tbl} SET {col}=NULL WHERE {col}=:a"),
                            {"a": aid},
                        )
                    else:
                        db.session.execute(
                            text(f"DELETE FROM {tbl} WHERE {col}=:a"),
                            {"a": aid},
                        )
                    db.session.execute(text("RELEASE SAVEPOINT sp_dynclean"))
                    dyn_ok += 1
                    progress = True
                except Exception as _de:
                    db.session.execute(text("ROLLBACK TO SAVEPOINT sp_dynclean"))
                    still_pending.append((tbl, col, nullable))
                    log.debug(f"dyn-clean retry {tbl}.{col}: {_de}")
            pending = still_pending
            if not progress or not pending:
                break
        dyn_skip = len(pending)
        log.info(f"reset dinâmico: {dyn_ok} FK(s) limpas, {dyn_skip} FK(s) puladas")
        if pending:
            for (tbl, col, _) in pending:
                log.warning(f"dyn-clean PERSISTENT skip: {tbl}.{col}")
    except Exception as _ie:
        log.warning(f"passagem dinâmica fk→usuario falhou: {_ie}")

    # Deleção final do próprio admin (após cleanup dinâmico de todas as FKs)
    # Usa SAVEPOINT para não abortar a sessão se alguma FK residual impedir.
    try:
        db.session.execute(text("SAVEPOINT sp_delete_admin"))
        db.session.execute(text("DELETE FROM usuario WHERE id=:a"), {"a": aid})
        db.session.execute(text("RELEASE SAVEPOINT sp_delete_admin"))
    except Exception as _ue:
        db.session.execute(text("ROLLBACK TO SAVEPOINT sp_delete_admin"))
        log.warning(f"reset: não foi possível deletar usuario id={aid}: {_ue}")

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
        RDOEquipamento, RDOOcorrencia,
        ContaReceber, Orcamento, OrcamentoItem,
        # Task #55 — ciclo completo: compras + alimentação + transporte
        Fornecedor, AlmoxarifadoCategoria, AlmoxarifadoItem, PedidoCompra,
        PedidoCompraItem,
        Restaurante, AlimentacaoItem, AlimentacaoLancamento,
        AlimentacaoLancamentoItem,
        CategoriaTransporte, LancamentoTransporte,
        CentroCusto,
    )
    from services.orcamento_view_service import (
        snapshot_from_servico, recalcular_item, recalcular_orcamento,
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
        versao_sistema="v2",
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
    # Task #55 — 3 diaristas no total (Pedro + João + Marcos), todos com
    # VA/VT/PIX. RDO finalizado deve gerar 1 SALARIO + 1 VA + 1 VT por
    # diarista/dia em GestaoCustoFilho.
    joao = Funcionario(
        codigo="ALF003",
        nome="João Lima",
        cpf=JOAO_CPF,
        data_admissao=date(2025, 8, 1),
        salario=0.0,
        valor_diaria=180.00,
        tipo_remuneracao="diaria",
        jornada_semanal=44,
        ativo=True, admin_id=aid,
        valor_va=22.00, valor_vt=12.00,
        chave_pix=JOAO_CPF,
        email="joao@construtoraalfa.com.br",
        telefone="(11) 90000-0003",
    )
    marcos = Funcionario(
        codigo="ALF004",
        nome="Marcos Alves",
        cpf=MARCOS_CPF,
        data_admissao=date(2025, 10, 1),
        salario=0.0,
        valor_diaria=180.00,
        tipo_remuneracao="diaria",
        jornada_semanal=44,
        ativo=True, admin_id=aid,
        valor_va=22.00, valor_vt=12.00,
        chave_pix=MARCOS_CPF,
        email="marcos@construtoraalfa.com.br",
        telefone="(11) 90000-0004",
    )
    db.session.add_all([carlos, pedro, joao, marcos]); db.session.flush()

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
    # Task #172 — resolve/cria Cliente e vincula via FK (mantém campos texto
    # como fallback de compatibilidade com leituras legadas).
    from services.cliente_resolver import obter_ou_criar_cliente
    cliente_obj = obter_ou_criar_cliente(
        admin_id=aid, nome=CLIENTE_NOME,
        email=CLIENTE_EMAIL, telefone=CLIENTE_TELEFONE,
    )
    obra = Obra(
        nome=OBRA_NOME, codigo=OBRA_CODIGO,
        endereco="Rua das Acácias, 250 — São Paulo / SP",
        data_inicio=date(2026, 2, 2),
        data_previsao_fim=date(2026, 6, 2),
        orcamento=float(valor_total),
        valor_contrato=float(valor_total),
        area_total_m2=250.0,
        status="Em andamento",
        cliente_id=cliente_obj.id,
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

    # Task #140 — 3 RDOs em datas crescentes com progresso MONOTÔNICO
    # (30% → 60% → 100%). Demonstra que "Progresso geral" da listagem
    # nunca decresce no tempo.
    rdos_dados = [
        (date(2026, 2, 5),  30.0, 8.0),
        (date(2026, 2, 12), 60.0, 8.0),
        (date(2026, 2, 19), 100.0, 8.0),
    ]
    # mapa percentual_anterior por (idx) para preencher RDOServicoSubatividade
    _perc_anteriores = {1: 0.0, 2: 30.0, 3: 60.0}
    # Acumulador V2 (RDOApontamentoCronograma) por tarefa — mantém somatório
    # entre RDOs para que a coluna `quantidade_acumulada` seja monotônica.
    from models import RDOApontamentoCronograma as _RAC_seed
    _v2_acum_qty = {}
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
            # Mensalista (Carlos) + 3 diaristas (Pedro, João, Marcos).
            # Cada diarista alocado em RDO finalizado dispara, em
            # services.rdo_custos.gerar_custos_mao_obra_rdo, 1 GCF
            # SALARIO (diária) + 1 GCF ALIMENTACAO (VA) + 1 GCF
            # TRANSPORTE (VT). Mensalista: nada (folha mensal cobre).
            db.session.add(RDOMaoObra(
                admin_id=aid, rdo_id=rdo.id,
                funcionario_id=carlos.id, funcao_exercida="Pedreiro (mensalista)",
                horas_trabalhadas=horas, horas_extras=0.0,
                tarefa_cronograma_id=folha.id,
            ))
            for _diar, _func in (
                (pedro,  "Encarregado (diária)"),
                (joao,   "Servente (diária)"),
                (marcos, "Servente (diária)"),
            ):
                db.session.add(RDOMaoObra(
                    admin_id=aid, rdo_id=rdo.id,
                    funcionario_id=_diar.id, funcao_exercida=_func,
                    horas_trabalhadas=horas, horas_extras=0.0,
                    tarefa_cronograma_id=folha.id,
                ))
            perc_anterior = _perc_anteriores.get(idx, 0.0)
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

            # Task #140 — Apontamento V2 (RDOApontamentoCronograma).
            # Necessário para que a listagem de RDO em modo V2 calcule
            # "Progresso geral" baseado no acumulado real da obra.
            if folha.quantidade_total and folha.quantidade_total > 0:
                qty_destino_acum = float(folha.quantidade_total) * (perc_destino / 100.0)
                qty_anterior_acum = _v2_acum_qty.get(folha.id, 0.0)
                qty_dia = max(0.0, qty_destino_acum - qty_anterior_acum)
                _v2_acum_qty[folha.id] = qty_destino_acum
                db.session.add(_RAC_seed(
                    rdo_id=rdo.id, tarefa_cronograma_id=folha.id,
                    admin_id=aid,
                    quantidade_executada_dia=qty_dia,
                    quantidade_acumulada=qty_destino_acum,
                    percentual_realizado=perc_destino,
                    percentual_planejado=perc_destino,  # demo: planejado = realizado
                ))
        # Equipamento (betoneira aparece no 2º e 3º RDO — obra em plena atividade)
        if idx >= 2:
            db.session.add(RDOEquipamento(
                admin_id=aid, rdo_id=rdo.id,
                nome_equipamento="Betoneira 400L",
                quantidade=1,
                horas_uso=4.0,
                estado_conservacao="Bom",
            ))

        # Ocorrência — cada RDO tem pelo menos uma
        _ocorrencia_dados = [
            ("Segurança", "Baixa",
             "Uso correto de EPIs verificado em toda a equipe."),
            ("Climático", "Baixa",
             "Chuva leve no período da tarde — trabalho suspenso 2h."),
            ("Observação", "Baixa",
             "Serviço concluído dentro do prazo previsto — equipe de parabéns."),
        ]
        _tipo_oc, _sev_oc, _desc_oc = _ocorrencia_dados[idx - 1]
        db.session.add(RDOOcorrencia(
            admin_id=aid, rdo_id=rdo.id,
            tipo_ocorrencia=_tipo_oc,
            severidade=_sev_oc,
            descricao_ocorrencia=_desc_oc,
            status_resolucao="Resolvido",
        ))

        db.session.flush()
        log.info(f"RDO #{idx} ({dt.isoformat()}) finalizado — folhas a {perc_destino:.0f}%")

    # 11.5) Task #118 — Demo: Orçamento com 4 cenários de override -----
    # (a) item com template padrão do serviço, sem override
    # (b) serviço novo (criado "como se fosse" pelo modal embedado) com
    #     template padrão escolhido na criação
    # (c) item com override de cronograma por linha (template ≠ padrão)
    # (d) item com composição customizada (1 add + 1 remove vs catálogo)
    tmpl_alv_expresso = CronogramaTemplate(
        nome="Alvenaria — execução expressa",
        descricao="Variante acelerada (3 etapas paralelas) — Task #118",
        admin_id=aid, ativo=True,
    )
    db.session.add(tmpl_alv_expresso); db.session.flush()
    g_exp = CronogramaTemplateItem(
        admin_id=aid, template_id=tmpl_alv_expresso.id, parent_item_id=None,
        nome_tarefa="Alvenaria expressa", ordem=1, duracao_dias=1,
    )
    db.session.add(g_exp); db.session.flush()
    db.session.add_all([
        CronogramaTemplateItem(
            admin_id=aid, template_id=tmpl_alv_expresso.id,
            parent_item_id=g_exp.id, nome_tarefa="Marcação + 1ª fiada",
            ordem=1, duracao_dias=2,
        ),
        CronogramaTemplateItem(
            admin_id=aid, template_id=tmpl_alv_expresso.id,
            parent_item_id=g_exp.id, nome_tarefa="Elevação até cinta",
            ordem=2, duracao_dias=3,
        ),
    ]); db.session.flush()

    # Cenário (b): "novo serviço" criado pelo fluxo do modal, com template padrão.
    serv_reboco = Servico(
        nome="Reboco interno (criado pelo modal)",
        descricao="Demonstração do modal de Novo Serviço dentro do Orçamento",
        categoria="Acabamento", unidade_medida="m2", unidade_simbolo="m²",
        custo_unitario=38.00, complexidade=2, ativo=True,
        imposto_pct=Decimal("8.0"), margem_lucro_pct=Decimal("25.0"),
        preco_venda_unitario=Decimal("65.00"),
        template_padrao_id=tmpl_pis.id,  # template escolhido no modal
        admin_id=aid,
    )
    db.session.add(serv_reboco); db.session.flush()
    db.session.add(ComposicaoServico(
        admin_id=aid, servico_id=serv_reboco.id,
        insumo_id=insumos_obj["Cimento CP II 50kg"].id,
        coeficiente=Decimal("0.08"),
    )); db.session.flush()

    orc = Orcamento(
        admin_id=aid,
        numero=f"ORC-2026-0001",
        titulo="Orçamento demo — cenários de override (Task #118)",
        descricao=(
            "Demonstra: (a) padrão herdado, (b) serviço criado no modal, "
            "(c) override de cronograma por linha, (d) composição customizada."
        ),
        cliente_id=cliente.id, cliente_nome=CLIENTE_NOME,
        imposto_pct_global=Decimal("8.0"),
        margem_pct_global=Decimal("25.0"),
        criado_por=aid, status="rascunho",
    )
    db.session.add(orc); db.session.flush()

    # (a) padrão herdado
    it_a = OrcamentoItem(
        admin_id=aid, orcamento_id=orc.id, ordem=1,
        servico_id=serv_alv.id, descricao="Alvenaria — Bloco A (cenário A: padrão)",
        unidade="m2", quantidade=Decimal("180"),
        composicao_snapshot=snapshot_from_servico(serv_alv),
        cronograma_template_override_id=None,
    )
    # (b) serviço criado no modal — usa o template do serviço (=padrão)
    it_b = OrcamentoItem(
        admin_id=aid, orcamento_id=orc.id, ordem=2,
        servico_id=serv_reboco.id,
        descricao="Reboco interno (cenário B: serviço criado no modal)",
        unidade="m2", quantidade=Decimal("120"),
        composicao_snapshot=snapshot_from_servico(serv_reboco),
        cronograma_template_override_id=None,
    )
    # (c) override por linha (template_alv_expresso ≠ tmpl_alv padrão)
    it_c = OrcamentoItem(
        admin_id=aid, orcamento_id=orc.id, ordem=3,
        servico_id=serv_alv.id,
        descricao="Alvenaria — Bloco B (cenário C: cronograma override = expresso)",
        unidade="m2", quantidade=Decimal("80"),
        composicao_snapshot=snapshot_from_servico(serv_alv),
        cronograma_template_override_id=tmpl_alv_expresso.id,
    )
    # (d) composição customizada (1 add + 1 remove)
    snap_d = list(snapshot_from_servico(serv_pis))
    if snap_d:
        snap_d.pop()  # remove o último insumo
    snap_d.append({
        "tipo": "MATERIAL",
        "insumo_id": insumos_obj["Cimento CP II 50kg"].id,
        "nome": "Cimento extra (cenário D: insumo adicionado)",
        "unidade": "kg", "coeficiente": 0.5,
        "preco_unitario": 0.85, "subtotal_unitario": 0.0,
    })
    it_d = OrcamentoItem(
        admin_id=aid, orcamento_id=orc.id, ordem=4,
        servico_id=serv_pis.id,
        descricao="Contrapiso — Bloco A (cenário D: composição customizada)",
        unidade="m2", quantidade=Decimal("180"),
        composicao_snapshot=snap_d,
        cronograma_template_override_id=None,
    )
    db.session.add_all([it_a, it_b, it_c, it_d]); db.session.flush()
    for _it in (it_a, it_b, it_c, it_d):
        recalcular_item(_it, orc)
    recalcular_orcamento(orc)
    log.info(
        "Task #118 demo: Orçamento %s criado com 4 cenários "
        "(custo R$ %.2f, venda R$ %.2f)",
        orc.numero, float(orc.custo_total or 0), float(orc.venda_total or 0),
    )

    db.session.commit()

    # 11.5) Task #118 — E2E: gerar Proposta a partir do Orçamento, aprovar e
    # validar override+snapshot na materialização do cronograma.
    from services.cronograma_proposta import (
        montar_arvore_preview as _montar_arvore_t118,
    )

    proposta_t118 = Proposta()
    proposta_t118.titulo = orc.titulo + " — Proposta E2E #118"
    proposta_t118.descricao = orc.descricao
    proposta_t118.cliente_id = orc.cliente_id
    proposta_t118.cliente_nome = orc.cliente_nome or CLIENTE_NOME
    proposta_t118.admin_id = aid
    proposta_t118.criado_por = aid
    proposta_t118.status = "rascunho"
    proposta_t118.valor_total = orc.venda_total or 0
    proposta_t118.orcamento_id = orc.id
    db.session.add(proposta_t118); db.session.flush()

    for _idx, _it in enumerate(orc.itens, start=1):
        db.session.add(PropostaItem(
            admin_id=aid,
            proposta_id=proposta_t118.id,
            item_numero=_idx, ordem=_idx,
            descricao=_it.descricao,
            quantidade=_it.quantidade,
            unidade=_it.unidade,
            preco_unitario=_it.preco_venda_unitario or 0,
            subtotal=_it.venda_total or 0,
            servico_id=_it.servico_id,
            quantidade_medida=_it.quantidade,
            cronograma_template_override_id=_it.cronograma_template_override_id,
            composicao_snapshot=_it.composicao_snapshot or [],
        ))
    db.session.flush()

    # Snapshot da árvore (precedência override→padrão) marcando todos os nós.
    _arvore = _montar_arvore_t118(proposta_t118, aid)
    def _marcar_todos(nodes):
        for n in nodes:
            n["selecionado"] = True
            for g in n.get("grupos", []):
                g["selecionado"] = True
                for s in g.get("subatividades", []):
                    s["selecionado"] = True
        return nodes
    proposta_t118.cronograma_default_json = _marcar_todos(_arvore)
    proposta_t118.status = "aprovada"
    db.session.flush()

    # Cria a Obra e dispara o handler (igual à rota de aprovação).
    obra_t118 = Obra(
        nome=f"Obra E2E #{proposta_t118.id} — Task #118",
        codigo=f"E2E118-{proposta_t118.id}",
        admin_id=aid, status="Em andamento",
        data_inicio=date.today(), responsavel_id=pedro.id,
        proposta_origem_id=proposta_t118.id, cliente_id=cliente.id,
    )
    db.session.add(obra_t118); db.session.flush()
    proposta_t118.obra_id = obra_t118.id
    db.session.flush()

    from handlers.propostas_handlers import handle_proposta_aprovada
    handle_proposta_aprovada({
        "proposta_id": proposta_t118.id,
        "cliente_nome": proposta_t118.cliente_nome,
        "valor_total": float(proposta_t118.valor_total or 0),
        "data_aprovacao": date.today().isoformat(),
    }, aid)
    db.session.commit()

    # Validação E2E: tarefas materializadas com origem 'override' para o item C.
    from models import TarefaCronograma as _TC
    _qs = (_TC.query
           .filter_by(admin_id=aid, obra_id=obra_t118.id)
           .all())
    _origens = {t.gerada_por_proposta_item_id: t for t in _qs if t.gerada_por_proposta_item_id}
    log.info(
        "Task #118 E2E: Proposta #%s aprovada → Obra #%s, %d tarefas materializadas",
        proposta_t118.id, obra_t118.id, len(_qs),
    )

    # 11.7) Task #55 — Compras: 1 Fornecedor + 1 PedidoCompra finalizada
    # à vista, vinculada à obra (gera GestaoCustoPai MATERIAL PAGO +
    # entrada/saída no almoxarifado).
    fornecedor_alf = Fornecedor(
        admin_id=aid,
        nome="Materiais São Paulo Ltda",
        razao_social="Materiais São Paulo Ltda",
        nome_fantasia="Materiais SP",
        cnpj="98.765.432/0001-10",
        endereco="Av. dos Construtores, 1000 — São Paulo / SP",
        cidade="São Paulo", estado="SP",
        telefone="(11) 4444-5555",
        email="vendas@materiaissp.com.br",
        contato_responsavel="Roberto Lima",
        tipo_fornecedor="MATERIAL",
        chave_pix="98765432000110",
        ativo=True,
    )
    db.session.add(fornecedor_alf); db.session.flush()

    cat_almox = AlmoxarifadoCategoria(
        admin_id=aid, nome="Materiais Básicos",
        tipo_controle_padrao="CONSUMIVEL",
        permite_devolucao_padrao=False,
    )
    db.session.add(cat_almox); db.session.flush()
    item_cimento = AlmoxarifadoItem(
        admin_id=aid, codigo="CIM-CPII-50",
        nome="Cimento CP II 50kg",
        categoria_id=cat_almox.id,
        tipo_controle="CONSUMIVEL",
        permite_devolucao=False, estoque_minimo=10, unidade="sc",
    )
    item_bloco = AlmoxarifadoItem(
        admin_id=aid, codigo="BLOC-9X19X19",
        nome="Bloco cerâmico 9x19x19",
        categoria_id=cat_almox.id,
        tipo_controle="CONSUMIVEL",
        permite_devolucao=False, estoque_minimo=200, unidade="un",
    )
    db.session.add_all([item_cimento, item_bloco]); db.session.flush()

    pedido = PedidoCompra(
        admin_id=aid,
        numero="NF-2026-0001",
        fornecedor_id=fornecedor_alf.id,
        data_compra=date(2026, 2, 6),
        obra_id=obra.id,
        condicao_pagamento="a_vista",
        parcelas=1,
        valor_total=Decimal("1500.00"),
        observacoes="Compra inicial de cimento e blocos para o Bloco A.",
        tipo_compra="normal",
    )
    db.session.add(pedido); db.session.flush()
    db.session.add_all([
        PedidoCompraItem(
            admin_id=aid, pedido_id=pedido.id,
            almoxarifado_item_id=item_cimento.id,
            descricao="Cimento CP II 50kg",
            quantidade=Decimal("20"),
            preco_unitario=Decimal("38.50"),
            subtotal=Decimal("770.00"),
        ),
        PedidoCompraItem(
            admin_id=aid, pedido_id=pedido.id,
            almoxarifado_item_id=item_bloco.id,
            descricao="Bloco cerâmico 9x19x19",
            quantidade=Decimal("608"),
            preco_unitario=Decimal("1.20"),
            subtotal=Decimal("729.60"),
        ),
    ])
    db.session.flush()

    # Processa via fluxo oficial — gera GCP MATERIAL PAGO + entrada/saída.
    # processar_compra_normal espera tuplas (desc, qtd, preco, almox_id,
    # subtotal), padrão da view compras.criar_compra.
    from compras_views import processar_compra_normal
    itens_validos = [
        (it.descricao, it.quantidade, it.preco_unitario,
         it.almoxarifado_item_id, it.subtotal)
        for it in pedido.itens
    ]
    processar_compra_normal(pedido, itens_validos, aid, aid)
    log.info(
        f"Task #55: pedido de compra {pedido.numero} (R$ "
        f"{float(pedido.valor_total):.2f}) finalizado → GCP MATERIAL PAGO + "
        f"entrada/saída no almoxarifado"
    )

    # 11.8) Task #55 — Alimentação V2: Restaurante + Item + Lançamento
    # vinculado à obra (com 3 diaristas como participantes).
    restaurante = Restaurante(
        admin_id=aid,
        nome="Restaurante Bom Prato",
        endereco="Rua das Acácias, 200 — São Paulo / SP",
        telefone="(11) 3333-2222",
        razao_social="Bom Prato Refeições Ltda",
        cnpj="11.222.333/0001-44",
        pix="bompato@pix.com.br",
        nome_conta="Bom Prato Refeições Ltda",
    )
    db.session.add(restaurante); db.session.flush()

    item_marmita = AlimentacaoItem(
        admin_id=aid,
        nome="Marmita executiva",
        preco_padrao=Decimal("18.00"),
        descricao="Marmita executiva — opção do dia",
        icone="fas fa-utensils", ordem=1,
        ativo=True, is_default=True,
    )
    db.session.add(item_marmita); db.session.flush()

    cc_obra = CentroCusto(
        admin_id=aid,
        codigo=f"CC-{obra.codigo}",
        nome=f"Centro de custo — {obra.nome}",
        descricao="Centro de custo automático da obra (Task #55).",
        tipo="obra", ativo=True, obra_id=obra.id,
    )
    db.session.add(cc_obra); db.session.flush()

    # 1 lançamento de alimentação na 1ª semana (3 diaristas almoçaram).
    almoco = AlimentacaoLancamento(
        admin_id=aid,
        data=date(2026, 2, 5),
        valor_total=Decimal("54.00"),  # 3 marmitas × R$ 18,00
        descricao="Almoço de campo — 3 diaristas (Pedro, João, Marcos).",
        restaurante_id=restaurante.id,
        obra_id=obra.id,
    )
    db.session.add(almoco); db.session.flush()
    # Inserção direta na tabela de associação porque ela carrega admin_id
    # NOT NULL (multi-tenant), e o backref `.funcionarios = [...]` do
    # SQLAlchemy não preenche essa coluna automaticamente.
    from models import alimentacao_funcionarios_assoc as _aa
    db.session.execute(_aa.insert(), [
        {"lancamento_id": almoco.id, "funcionario_id": diar.id, "admin_id": aid}
        for diar in (pedro, joao, marcos)
    ])
    for diar in (pedro, joao, marcos):
        db.session.add(AlimentacaoLancamentoItem(
            admin_id=aid,
            lancamento_id=almoco.id,
            item_id=item_marmita.id,
            nome_item="Marmita executiva",
            preco_unitario=Decimal("18.00"),
            quantidade=1,
            subtotal=Decimal("18.00"),
            funcionario_id=diar.id,
            centro_custo_id=cc_obra.id,
        ))
    db.session.flush()
    log.info(
        f"Task #55: AlimentacaoLancamento #{almoco.id} "
        f"(R$ {float(almoco.valor_total):.2f}) — 3 diaristas no restaurante "
        f"{restaurante.nome}"
    )

    # 11.9) Task #55 — Transporte V2: Categoria + Lançamento vinculado à
    # obra (combustível abastecido por encarregado).
    cat_transp = CategoriaTransporte(
        admin_id=aid, nome="Combustível", icone="fas fa-gas-pump",
    )
    db.session.add(cat_transp); db.session.flush()

    transp = LancamentoTransporte(
        admin_id=aid,
        categoria_id=cat_transp.id,
        funcionario_id=pedro.id,
        centro_custo_id=cc_obra.id,
        obra_id=obra.id,
        data_lancamento=date(2026, 2, 6),
        valor=Decimal("180.00"),
        descricao="Combustível para caminhonete da obra (semana 1).",
    )
    db.session.add(transp); db.session.flush()
    log.info(
        f"Task #55: LancamentoTransporte #{transp.id} "
        f"(R$ {float(transp.valor):.2f}) — combustível para a obra"
    )

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
        "joao_id": joao.id,
        "marcos_id": marcos.id,
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
        "fornecedor_id": fornecedor_alf.id,
        "pedido_compra_id": pedido.id,
        "pedido_compra_numero": pedido.numero,
        "pedido_compra_valor": float(pedido.valor_total),
        "alimentacao_lancamento_id": almoco.id,
        "alimentacao_valor": float(almoco.valor_total),
        "transporte_lancamento_id": transp.id,
        "transporte_valor": float(transp.valor),
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
        "https://construtoraalfa.example.com"
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
    log.info(f"    joao_id            = {info['joao_id']}  (diarista R$ 180/dia)")
    log.info(f"    marcos_id          = {info['marcos_id']}  (diarista R$ 180/dia)")
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
    log.info(f"    fornecedor_id      = {info['fornecedor_id']}")
    log.info(f"    pedido_compra_id   = {info['pedido_compra_id']}  "
             f"({info['pedido_compra_numero']} — R$ "
             f"{info['pedido_compra_valor']:.2f}, à vista, MATERIAL PAGO)")
    log.info(f"    alimentacao_id     = {info['alimentacao_lancamento_id']}  "
             f"(R$ {info['alimentacao_valor']:.2f} — 3 diaristas)")
    log.info(f"    transporte_id      = {info['transporte_lancamento_id']}  "
             f"(R$ {info['transporte_valor']:.2f} — combustível)")
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
def _backfill_custos_rdo_demo(admin_id):
    """Roda gerar_custos_mao_obra_rdo() em todos os RDOs finalizados da
    obra OBR-2026-001 do admin Alfa. Idempotente — só insere o que falta.
    Também promove o admin Alfa para versao_sistema='v2' (a demo usa
    diaristas + Gestão de Custos V2, recursos exclusivos do v2).
    """
    try:
        from app import db
        from models import Usuario, Obra, RDO
        from services.rdo_custos import gerar_custos_mao_obra_rdo

        admin = Usuario.query.get(admin_id)
        if admin and getattr(admin, 'versao_sistema', None) != 'v2':
            log.info(
                f"backfill: promovendo admin Alfa (id={admin_id}) "
                f"de {admin.versao_sistema!r} para 'v2'"
            )
            admin.versao_sistema = 'v2'
            db.session.commit()

        obra = (
            Obra.query
            .filter_by(admin_id=admin_id, codigo=OBRA_CODIGO)
            .first()
        )
        if not obra:
            log.info(f"backfill custos RDO: obra {OBRA_CODIGO} não encontrada")
            return

        rdos = (
            RDO.query
            .filter_by(obra_id=obra.id, status="Finalizado")
            .all()
        )
        total = 0
        for rdo in rdos:
            try:
                total += gerar_custos_mao_obra_rdo(rdo, admin_id) or 0
            except Exception as e:
                log.warning(f"backfill RDO {rdo.numero_rdo} falhou: {e}")
        if total:
            log.info(
                f"backfill custos RDO: {total} lançamento(s) inserido(s) "
                f"em {len(rdos)} RDO(s) da obra {OBRA_CODIGO}"
            )
        else:
            log.info(
                f"backfill custos RDO: nada a inserir "
                f"({len(rdos)} RDO(s) já com custos)"
            )
    except Exception:
        log.exception("backfill custos RDO falhou")


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

    # ------------------------------------------------------------------
    # Auto-detecção de produção (fail-closed)
    # ------------------------------------------------------------------
    # Mesmo que o operador rode sem `--ambiente prod`, se houver QUALQUER
    # sinal de que estamos rodando contra um ambiente produtivo, tratamos
    # como prod e exigimos o opt-in `SIGE_ALLOW_PROD_SEED=1`. Isso fecha
    # o buraco de "rodei o script no shell de prod sem o flag".
    prod_signals = []
    if (os.environ.get("FLASK_ENV") or "").lower() == "production":
        prod_signals.append("FLASK_ENV=production")
    if (os.environ.get("APP_ENV") or "").lower() in ("prod", "production"):
        prod_signals.append("APP_ENV=prod")
    if (os.environ.get("ENVIRONMENT") or "").lower() in ("prod", "production"):
        prod_signals.append("ENVIRONMENT=prod")
    if os.environ.get("REPLIT_DEPLOYMENT") == "1":
        prod_signals.append("REPLIT_DEPLOYMENT=1")
    db_url = (os.environ.get("DATABASE_URL") or "").lower()
    if any(tok in db_url for tok in (
        "easypanel", "prod", "production", "live", "rds.amazonaws", "neon.tech",
    )):
        prod_signals.append("DATABASE_URL parece produtivo")

    if prod_signals and args.ambiente != "prod":
        log.warning(
            "ambiente produtivo detectado pelos sinais "
            f"{prod_signals!r} — escalando para modo prod automaticamente"
        )
        args.ambiente = "prod"

    # Guarda de produção (vale para flag explícita OU auto-escalada)
    if args.ambiente == "prod":
        if os.environ.get("SIGE_ALLOW_PROD_SEED") != "1":
            log.error(
                "execução em produção bloqueada — defina "
                "SIGE_ALLOW_PROD_SEED=1 e re-execute. Sinais detectados: "
                f"{prod_signals or ['flag --ambiente prod']!r}"
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
                # Backfill idempotente: garante que os custos de mão-de-obra
                # dos RDOs finalizados da demo estão lançados em
                # GestaoCustoFilho. Necessário para deploys que plantaram a
                # demo ANTES da geração automática existir.
                _backfill_custos_rdo_demo(existente.id)
                return 0

            log.info(
                f"plantando dataset Alfa (ambiente={args.ambiente})…"
            )
            info = _seed()
            # Após plantar (caminho fresh ou --reset), gera GestaoCustoFilho
            # SALARIO/VA/VT para os RDOs finalizados da demo. O seed cria os
            # RDOMaoObra mas não dispara gerar_custos_mao_obra_rdo.
            _backfill_custos_rdo_demo(info["admin_id"])
            _imprimir_demo_pronta(info, args.ambiente)
            return 0

        except Exception as e:
            from app import db
            db.session.rollback()
            log.exception(f"erro durante seed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
