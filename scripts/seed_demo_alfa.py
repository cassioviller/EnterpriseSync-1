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
        # ---- Task #20 — CRM (filhos primeiro). Lead tem FKs para
        # cliente/proposta/obra/listas-mestras CRM e bloqueia a deleção
        # delas se ficar para a passagem dinâmica. lead_historico tem
        # ondelete='CASCADE' mas explicitar evita surpresas.
        "DELETE FROM lead_historico WHERE admin_id=:a",
        "DELETE FROM lead WHERE admin_id=:a",
        "DELETE FROM crm_responsavel WHERE admin_id=:a",
        "DELETE FROM crm_origem WHERE admin_id=:a",
        "DELETE FROM crm_cadencia WHERE admin_id=:a",
        "DELETE FROM crm_situacao WHERE admin_id=:a",
        "DELETE FROM crm_tipo_material WHERE admin_id=:a",
        "DELETE FROM crm_tipo_obra WHERE admin_id=:a",
        "DELETE FROM crm_motivo_perda WHERE admin_id=:a",
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
        "DELETE FROM rdo_custo_diario WHERE admin_id=:a",
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
        "DELETE FROM subatividade_mao_obra WHERE admin_id=:a",
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
        "DELETE FROM funcao WHERE admin_id=:a",
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
        Usuario, TipoUsuario, Funcao, Funcionario, Cliente, ConfiguracaoEmpresa,
        Insumo, PrecoBaseInsumo, SubatividadeMestre, SubatividadeMaoObra,
        CronogramaTemplate,
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
        # Task #20 — CRM Demo
        Lead, LeadHistorico, CrmResponsavel, LeadStatus,
        CrmOrigem, CrmCadencia, CrmSituacao, CrmTipoMaterial,
        CrmTipoObra, CrmMotivoPerda,
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
        # Insumos do 3º serviço (Pintura) usado na obra Pinheiros — Task #20.
        ("Tinta acrílica 18L",       "MATERIAL",    "gl", 320.00),
        ("Massa corrida 25kg",       "MATERIAL",    "sc",  68.00),
        ("Hora pintor",              "MAO_OBRA",    "h",   30.00),
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
    #
    # Task #11 — METAS DE PRODUTIVIDADE CALIBRADAS
    # ─────────────────────────────────────────────
    # A meta_produtividade é interpretada pelo handler como
    #   indice = (qty_produzida ÷ Σ horas_equipe) ÷ meta
    # ou seja, é uma produtividade por *homem-hora* (cada hora-pessoa
    # registrada em RDOMaoObra conta no denominador). Isso muda
    # bastante o número que faz sentido cadastrar — uma "meta de equipe"
    # acaba dividida pelo nº de pessoas alocadas.
    #
    # Os valores abaixo foram calibrados de propósito para que o
    # dashboard `/cronograma/produtividade` da obra Residencial Bela Vista
    # mostre uma mistura realista de cores (verde / amarelo / vermelho),
    # contando uma história de "obra com pontos fortes e atenção".
    # Bela Vista usa 3 RDOs × 4 funcionários × 8h = 96 hh por
    # subatividade, com qty_total vinda do template de cronograma.
    # Faixas-alvo por sub (BV):
    #   Marcação        → 0,833 ÷ 0,7 = 1,19× (verde)
    #   Elevação        → 2,604 ÷ 2,0 = 1,30× (verde)
    #   Chapisco        → 2,604 ÷ 3,0 = 0,87× (amarelo)
    #   Prep contrapiso → 2,604 ÷ 3,5 = 0,74× (vermelho — investigar)
    #   Lançamento      → 2,604 ÷ 2,7 = 0,96× (amarelo)
    # Massa e Tinta (só Pin): calibrados contra a taxa do Pinheiros
    # (~0,785 m²/hh) para amarelo/verde respectivamente.
    # Referência: TCPO/PINI — faixas típicas de produtividade por
    # homem-hora em obras residenciais populares (com pedreiro+servente).
    def _sub(nome, horas, unidade, meta, complex_=2):
        sm = SubatividadeMestre(
            tipo="subatividade", nome=nome, descricao=nome,
            duracao_estimada_horas=horas, unidade_medida=unidade,
            meta_produtividade=meta, obrigatoria=True, complexidade=complex_,
            admin_id=aid, ativo=True,
        )
        db.session.add(sm); return sm

    sub_marcacao   = _sub("Marcação de paredes",      8.0, "m linear", 0.7)
    sub_elevacao   = _sub("Elevação de alvenaria",   32.0, "m²",       2.0)
    sub_chapisco   = _sub("Chapisco",                12.0, "m²",       3.0)
    sub_prep_piso  = _sub("Preparação do contrapiso", 8.0, "m²",       3.5)
    sub_lancamento = _sub("Lançamento e desempeno",  20.0, "m²",       2.7)
    # Subatividades do 3º serviço (Pintura) — Task #20.
    sub_massa      = _sub("Massa corrida + lixamento", 16.0, "m²",     1.0)
    sub_pintura    = _sub("Aplicação de tinta acrílica (2 demãos)",
                          24.0, "m²",                                 0.7)
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

    # Template Pintura (3º serviço com folhas — alimenta Métricas
    # "Empresa por Serviço" com ≥3 serviços com dados — Task #20).
    tmpl_pin = CronogramaTemplate(
        nome="Pintura interna — padrão",
        descricao="Massa corrida → Aplicação de tinta (2 demãos)",
        categoria="Acabamento", ativo=True, admin_id=aid,
    )
    db.session.add(tmpl_pin); db.session.flush()
    g_pin = CronogramaTemplateItem(
        template_id=tmpl_pin.id, nome_tarefa="Pintura",
        ordem=30, duracao_dias=1, admin_id=aid,
    )
    db.session.add(g_pin); db.session.flush()
    db.session.add_all([
        CronogramaTemplateItem(
            template_id=tmpl_pin.id, parent_item_id=g_pin.id,
            subatividade_mestre_id=sub_massa.id,
            nome_tarefa="Massa corrida + lixamento",
            ordem=31, duracao_dias=3, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
        CronogramaTemplateItem(
            template_id=tmpl_pin.id, parent_item_id=g_pin.id,
            subatividade_mestre_id=sub_pintura.id,
            nome_tarefa="Aplicação de tinta (2 demãos)",
            ordem=32, duracao_dias=4, quantidade_prevista=250.0,
            responsavel="empresa", admin_id=aid,
        ),
    ]); db.session.flush()

    # 7) Serviços de catálogo (3 com template + 1 verba) -------------------
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
    serv_pin = Servico(
        nome="Pintura interna acrílica",
        descricao="Massa corrida + 2 demãos de tinta acrílica em parede",
        categoria="Acabamento", unidade_medida="m2", unidade_simbolo="m²",
        custo_unitario=20.00, complexidade=2, ativo=True,
        imposto_pct=Decimal("8.0"), margem_lucro_pct=Decimal("25.0"),
        preco_venda_unitario=Decimal("35.00"),
        template_padrao_id=tmpl_pin.id, admin_id=aid,
    )
    db.session.add_all([serv_alv, serv_pis, serv_mob, serv_pin])
    db.session.flush()

    # Task #4 — back-link SubatividadeMestre → Servico. Cada subatividade
    # mestre pertence ao serviço cujo CronogramaTemplate a referencia. Sem
    # esse vínculo o auto-vínculo Função→ComposicaoServico (Task #62) não
    # consegue casar a mão-de-obra à composição correta e a UI que filtra
    # por serviço (cronograma, custos por serviço) fica vazia.
    sub_marcacao.servico_id   = serv_alv.id
    sub_elevacao.servico_id   = serv_alv.id
    sub_chapisco.servico_id   = serv_alv.id
    sub_prep_piso.servico_id  = serv_pis.id
    sub_lancamento.servico_id = serv_pis.id
    sub_massa.servico_id      = serv_pin.id
    sub_pintura.servico_id    = serv_pin.id
    db.session.flush()

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
    # Composição mínima da pintura (Task #20).
    for nome_ins, coef in [
        ("Tinta acrílica 18L",   "0.020"),  # ~1 galão p/ 50 m² (2 demãos)
        ("Massa corrida 25kg",   "0.040"),  # ~1 sc p/ 25 m²
        ("Hora pintor",          "0.350"),
        ("Hora servente",        "0.150"),
    ]:
        db.session.add(ComposicaoServico(
            admin_id=aid, servico_id=serv_pin.id,
            insumo_id=insumos_obj[nome_ins].id,
            coeficiente=Decimal(coef),
        ))
    db.session.flush()

    # 7.5) Funções (Task #62 — vínculo Função→Composição) ------------------
    # Cada Função aponta para o Insumo MAO_OBRA equivalente. O listener
    # services.vinculo_mao_obra.before_flush usa esse vínculo para
    # preencher RDOMaoObra.composicao_servico_id automaticamente quando
    # o RDO é salvo, alimentando as métricas de produtividade (Task #3).
    funcao_pedreiro = Funcao(
        nome="Pedreiro", admin_id=aid,
        insumo_id=insumos_obj["Hora pedreiro"].id,
        salario_base=2800.0,
    )
    funcao_servente = Funcao(
        nome="Servente", admin_id=aid,
        insumo_id=insumos_obj["Hora servente"].id,
        salario_base=180.0,
    )
    funcao_encarregado = Funcao(
        nome="Encarregado", admin_id=aid,
        insumo_id=insumos_obj["Diária encarregado"].id,
        salario_base=200.0,
    )
    db.session.add_all([funcao_pedreiro, funcao_servente, funcao_encarregado])
    db.session.flush()

    # Vincular Funcionários às suas Funções
    carlos.funcao_id = funcao_pedreiro.id
    pedro.funcao_id  = funcao_encarregado.id
    joao.funcao_id   = funcao_servente.id
    marcos.funcao_id = funcao_servente.id
    db.session.flush()

    # 7.6) SubatividadeMaoObra (Task #62 — N:N sub_mestre↔composicao) -----
    # O resolver de vínculo exige links explícitos quando RDOMaoObra
    # aponta para um RDOServicoSubatividade com subatividade_mestre_id
    # definido. Mapeia cada subatividade às composições MAO_OBRA do
    # serviço correspondente.
    comps_alv_mo = ComposicaoServico.query.filter(
        ComposicaoServico.servico_id == serv_alv.id,
        ComposicaoServico.insumo_id.in_([
            insumos_obj["Hora pedreiro"].id,
            insumos_obj["Hora servente"].id,
        ]),
    ).all()
    comps_pis_mo = ComposicaoServico.query.filter(
        ComposicaoServico.servico_id == serv_pis.id,
        ComposicaoServico.insumo_id.in_([
            insumos_obj["Hora pedreiro"].id,
            insumos_obj["Hora servente"].id,
        ]),
    ).all()
    comps_pin_mo = ComposicaoServico.query.filter(
        ComposicaoServico.servico_id == serv_pin.id,
        ComposicaoServico.insumo_id.in_([
            insumos_obj["Hora pintor"].id,
            insumos_obj["Hora servente"].id,
        ]),
    ).all()
    _smo_map = [
        (sub_marcacao,   comps_alv_mo),
        (sub_elevacao,   comps_alv_mo),
        (sub_chapisco,   comps_alv_mo),
        (sub_prep_piso,  comps_pis_mo),
        (sub_lancamento, comps_pis_mo),
        (sub_massa,      comps_pin_mo),
        (sub_pintura,    comps_pin_mo),
    ]
    for _sm, _comps in _smo_map:
        for _comp in _comps:
            db.session.add(SubatividadeMaoObra(
                admin_id=aid,
                subatividade_mestre_id=_sm.id,
                composicao_servico_id=_comp.id,
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
        # Task #6 — cria como Rascunho e finaliza via mesmo caminho da rota
        # (views.rdo.finalizar_rdo): status='Finalizado' + commit + emit
        # 'rdo_finalizado'. O handler `event_manager.lancar_custos_rdo`
        # gera GestaoCustoPai/Filho (SALARIO/VA/VT) — sem INSERT direto.
        rdo = RDO(
            numero_rdo=f"RDO-2026-{idx:03d}",
            data_relatorio=dt, obra_id=obra.id,
            criado_por_id=aid, admin_id=aid,
            clima_geral="Ensolarado", temperatura_media="26°C",
            condicoes_trabalho="Ideais", local="Campo",
            comentario_geral=f"Avanço da semana — meta atingida ({perc_destino:.0f}%).",
            status="Rascunho",
        )
        db.session.add(rdo); db.session.flush()

        for folha in folhas:
            # Mensalista (Carlos) + 3 diaristas (Pedro, João, Marcos).
            # Cada diarista alocado em RDO finalizado dispara, em
            # services.rdo_custos.gerar_custos_mao_obra_rdo, 1 GCF
            # SALARIO (diária) + 1 GCF ALIMENTACAO (VA) + 1 GCF
            # TRANSPORTE (VT). Mensalista: nada (folha mensal cobre).
            perc_anterior = _perc_anteriores.get(idx, 0.0)
            _qty_total = float(folha.quantidade_total or 0.0)
            _qty_dia_rss = max(
                0.0,
                _qty_total * (perc_destino - perc_anterior) / 100.0,
            )
            rss = RDOServicoSubatividade(
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
                quantidade_produzida=_qty_dia_rss,
                ordem_execucao=folha.ordem, ativo=True,
                admin_id=aid,
                subatividade_mestre_id=folha.subatividade_mestre_id,
            )
            db.session.add(rss); db.session.flush()
            db.session.add(RDOMaoObra(
                admin_id=aid, rdo_id=rdo.id,
                funcionario_id=carlos.id, funcao_exercida="Pedreiro (mensalista)",
                horas_trabalhadas=horas,
                tarefa_cronograma_id=folha.id,
                subatividade_id=rss.id,
            ))
            for _diar, _func in (
                (pedro,  "Encarregado (diária)"),
                (joao,   "Servente (diária)"),
                (marcos, "Servente (diária)"),
            ):
                db.session.add(RDOMaoObra(
                    admin_id=aid, rdo_id=rdo.id,
                    funcionario_id=_diar.id, funcao_exercida=_func,
                    horas_trabalhadas=horas,
                    tarefa_cronograma_id=folha.id,
                    subatividade_id=rss.id,
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

        # Task #3 — recalcula produtividade snapshot (RDOMaoObra.produtividade_real
        # / indice_produtividade) para alimentar /cronograma/api/produtividade.
        # Sem isto, o dashboard de produtividade fica vazio para o demo.
        from services.rdo_custos import recalcular_produtividade_rdo as _recalc_prod
        _recalc_prod(rdo)

        # Task #6 — finaliza pelo mesmo caminho da rota: muda status,
        # commita, e emite 'rdo_finalizado'. O handler oficial
        # `event_manager.lancar_custos_rdo` cria os GestaoCustoPai/Filho
        # (SALARIO/VA/VT) — nada de INSERT direto em gestao_custo_*.
        rdo.status = "Finalizado"
        db.session.commit()
        from event_manager import EventManager as _EM
        _EM.emit('rdo_finalizado', {
            'rdo_id': rdo.id,
            'obra_id': rdo.obra_id,
            'data_relatorio': str(rdo.data_relatorio),
        }, aid)

        log.info(f"RDO #{idx} ({dt.isoformat()}) finalizado — folhas a {perc_destino:.0f}%")

    # Task #3 — sincroniza percentuais bottom-up: tarefas-pai do cronograma
    # passam a refletir a média ponderada dos filhos (que os RDOs avançaram).
    from utils.cronograma_engine import sincronizar_percentuais_obra as _sinc_perc
    _sinc_perc(obra.id, aid)

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

    # IMPORTANTE: numero explícito para evitar colisão com a proposta "002.26"
    # do Pinheiros (criada mais adiante). Sem isso, Proposta.__init__ chama
    # gerar_numero_proposta() → conta 1 proposta no ano (001.26 Bela Vista) →
    # gera "002.26", que colide com o numero explícito do Pinheiros.
    proposta_t118 = Proposta(numero="E2E118.26", data_proposta=date(2026, 1, 15))
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

    # 13) Task #20 — CRM Demo: 4 responsáveis + listas mestras + 12 leads -
    # Popula listas mestras genéricas (origem/cadência/situação/tipo
    # material/tipo obra/motivo perda) — necessário porque o seed cria o
    # admin direto via SQL e não passa pelo fluxo de criação que dispara
    # `seed_listas_mestras_crm`. Em seguida cria 4 responsáveis e 12
    # leads cobrindo as 8 colunas do Kanban (incl. 1 Aprovado linkado à
    # proposta+obra Bela Vista, 2 Perdidos com motivo). Aging variado
    # (status_changed_at espalhado entre hoje e 25 dias atrás) para que
    # o badge "parado há X dias" apareça em verde/amarelo/vermelho.
    from datetime import timedelta as _timedelta
    from crm_seeds import seed_listas_mestras_crm

    _crm_inseridos = seed_listas_mestras_crm(aid, commit=False)
    log.info(f"Task #20 CRM: listas mestras semeadas {_crm_inseridos}")

    resp_ana = CrmResponsavel(admin_id=aid, nome="Ana Paula Costa", ativo=True)
    resp_bruno = CrmResponsavel(admin_id=aid, nome="Bruno Mendes", ativo=True)
    resp_carla = CrmResponsavel(admin_id=aid, nome="Carla Tavares", ativo=True)
    resp_diego = CrmResponsavel(admin_id=aid, nome="Diego Santos", ativo=True)
    db.session.add_all([resp_ana, resp_bruno, resp_carla, resp_diego])
    db.session.flush()

    # Mapas de FKs CRM (lookup por nome)
    _origens = {o.nome: o for o in CrmOrigem.query.filter_by(admin_id=aid).all()}
    _cadencias = {c.nome: c for c in CrmCadencia.query.filter_by(admin_id=aid).all()}
    _situacoes = {s.nome: s for s in CrmSituacao.query.filter_by(admin_id=aid).all()}
    _tipos_mat = {m.nome: m for m in CrmTipoMaterial.query.filter_by(admin_id=aid).all()}
    _tipos_obra = {t.nome: t for t in CrmTipoObra.query.filter_by(admin_id=aid).all()}
    _motivos = {p.nome: p for p in CrmMotivoPerda.query.filter_by(admin_id=aid).all()}

    _agora = datetime.utcnow()
    _hoje = date.today()

    # Trajetória padrão por status final — garante 2 a 4 entradas em
    # LeadHistorico por lead (criação + 1-3 transições), em datas
    # crescentes igualmente espaçadas entre data_chegada e
    # status_changed_at. Cobre o requisito do spec da Task #20.
    # Cada item: (campo, valor_antes, valor_depois, descricao_curta).
    _TRAJ = {
        LeadStatus.EM_FILA: [
            # Lead permanece em EM_FILA: o evento real após a criação é
            # a distribuição/atribuição do responsável durante a triagem
            # (campo tipado responsavel_id), não uma transição de status.
            ("responsavel_id", None, None,
             "Lead distribuído ao responsável após triagem inicial."),
        ],
        LeadStatus.EM_ANDAMENTO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
        ],
        LeadStatus.ENVIADO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.ENVIADO.value,
             "Proposta enviada ao cliente."),
        ],
        LeadStatus.VALIDACAO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.ENVIADO.value,
             "Proposta enviada ao cliente."),
            ("status", LeadStatus.ENVIADO.value, LeadStatus.VALIDACAO.value,
             "Cliente em análise técnica da proposta."),
        ],
        LeadStatus.APROVADO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.ENVIADO.value,
             "Proposta enviada ao cliente."),
            ("status", LeadStatus.ENVIADO.value, LeadStatus.APROVADO.value,
             "Proposta APROVADA — obra aberta no sistema."),
        ],
        LeadStatus.FEEDBACK: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.ENVIADO.value,
             "Proposta enviada ao cliente."),
            ("status", LeadStatus.ENVIADO.value, LeadStatus.FEEDBACK.value,
             "Cliente solicitou ajustes — aguardando devolutiva."),
        ],
        LeadStatus.CONGELADO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.CONGELADO.value,
             "Cliente solicitou pausa — lead congelado."),
        ],
        LeadStatus.PERDIDO: [
            ("status", LeadStatus.EM_FILA.value, LeadStatus.EM_ANDAMENTO.value,
             "Qualificação iniciada — primeiro contato realizado."),
            ("status", LeadStatus.EM_ANDAMENTO.value, LeadStatus.ENVIADO.value,
             "Proposta enviada ao cliente."),
            ("status", LeadStatus.ENVIADO.value, LeadStatus.PERDIDO.value,
             "Lead perdido — registrado motivo."),
        ],
    }

    def _criar_lead(
        *, nome, contato, email, responsavel, status, dias_parado,
        origem=None, cadencia=None, situacao=None, tipo_material=None,
        tipo_obra=None, motivo_perda=None, localizacao=None, demanda=None,
        valor_proposta=None, observacao=None, data_envio=None,
        data_retomada=None, cliente_id=None, proposta_id=None, obra_id=None,
        historico_extra=None,
    ):
        sc_at = _agora - _timedelta(days=int(dias_parado))
        # data_chegada: 0-3 dias antes do status_changed_at, para que a
        # trajetória de transições caiba dentro do intervalo.
        chegada_dt = sc_at - _timedelta(days=max(2, min(int(dias_parado / 2), 7)))
        lead = Lead(
            admin_id=aid,
            data_chegada=chegada_dt.date(),
            data_envio=data_envio,
            nome=nome, contato=contato, email=email,
            responsavel_id=responsavel.id if responsavel else None,
            origem_id=(_origens.get(origem).id if origem and _origens.get(origem) else None),
            cadencia_id=(_cadencias.get(cadencia).id if cadencia and _cadencias.get(cadencia) else None),
            situacao_id=(_situacoes.get(situacao).id if situacao and _situacoes.get(situacao) else None),
            tipo_material_id=(_tipos_mat.get(tipo_material).id if tipo_material and _tipos_mat.get(tipo_material) else None),
            tipo_obra_id=(_tipos_obra.get(tipo_obra).id if tipo_obra and _tipos_obra.get(tipo_obra) else None),
            motivo_perda_id=(_motivos.get(motivo_perda).id if motivo_perda and _motivos.get(motivo_perda) else None),
            localizacao=localizacao, demanda=demanda,
            valor_proposta=(Decimal(str(valor_proposta)) if valor_proposta else None),
            status=status.value, observacao=observacao,
            data_retomada=data_retomada,
            cliente_id=cliente_id, proposta_id=proposta_id, obra_id=obra_id,
            criado_por_id=aid, status_changed_at=sc_at,
            created_at=chegada_dt, updated_at=sc_at,
        )
        db.session.add(lead); db.session.flush()
        # 1) Entrada de criação (sempre, datada na chegada).
        db.session.add(LeadHistorico(
            lead_id=lead.id, admin_id=aid, campo="sistema",
            valor_antes=None, valor_depois=LeadStatus.EM_FILA.value,
            descricao=f"Lead criado pelo sistema (origem: {origem or 'manual'}).",
            usuario_id=None,
            created_at=chegada_dt,
        ))
        # 2) Trajetória automática (1 a 3 entradas) — espaçada
        # uniformemente entre chegada_dt+1d e sc_at.
        trajetoria = _TRAJ.get(status, [])
        n = len(trajetoria)
        if n > 0:
            intervalo = (sc_at - chegada_dt) - _timedelta(days=1)
            if intervalo.total_seconds() <= 0:
                intervalo = _timedelta(days=1)
            passo = intervalo / n
            base = chegada_dt + _timedelta(days=1)
            for i, (campo, antes, depois, desc) in enumerate(trajetoria, start=1):
                ts = (sc_at if i == n else base + (passo * (i - 1)))
                # Para o evento responsavel_id (EM_FILA), o valor_depois
                # é resolvido em runtime para o id real do responsável.
                if campo == "responsavel_id" and depois is None:
                    depois = (str(responsavel.id) if responsavel else None)
                db.session.add(LeadHistorico(
                    lead_id=lead.id, admin_id=aid,
                    campo=campo, valor_antes=antes, valor_depois=depois,
                    descricao=desc, usuario_id=aid,
                    created_at=ts,
                ))
        # 3) Eventos extras opcionais (sobre a trajetória, datados no
        # final). Usados para detalhes pontuais como "primeira ligação OK".
        for ev in (historico_extra or []):
            db.session.add(LeadHistorico(
                lead_id=lead.id, admin_id=aid,
                campo=ev.get("campo", "observacao"),
                valor_antes=ev.get("antes"),
                valor_depois=ev.get("depois"),
                descricao=ev.get("descricao"),
                usuario_id=aid,
                created_at=ev.get("when") or sc_at,
            ))
        return lead

    leads_criados = []

    # ---- Em fila (2) — recém-chegados, ainda não trabalhados.
    leads_criados.append(_criar_lead(
        nome="Marina Oliveira", contato="(11) 98765-1100",
        email="marina.oliveira@example.com", responsavel=resp_ana,
        status=LeadStatus.EM_FILA, dias_parado=1,
        origem="Site", cadencia="Contato Dia 1",
        situacao="Levantar Necessidade", tipo_material="Drywall",
        tipo_obra="Residencial",
        localizacao="Vila Mariana — São Paulo / SP",
        demanda="Reforma de sala e cozinha integradas em apartamento.",
        valor_proposta=18500.00,
    ))
    leads_criados.append(_criar_lead(
        nome="Construtora Horizonte SA", contato="(11) 3300-1100",
        email="compras@horizonte.com.br", responsavel=resp_bruno,
        status=LeadStatus.EM_FILA, dias_parado=2,
        origem="Indicação", cadencia="Contato Dia 1",
        situacao="Levantar Necessidade", tipo_material="Steel Frame",
        tipo_obra="Empresarial",
        localizacao="Itaim Bibi — São Paulo / SP",
        demanda="Forros removíveis para escritório novo (450 m²).",
        valor_proposta=72000.00,
    ))

    # ---- Em andamento (2) — qualificados, em diálogo ativo.
    leads_criados.append(_criar_lead(
        nome="Patricia Almeida", contato="(11) 99100-2200",
        email="patricia.almeida@example.com", responsavel=resp_carla,
        status=LeadStatus.EM_ANDAMENTO, dias_parado=4,
        origem="Anúncio Meta Ads", cadencia="Contato Dia 3",
        situacao="Em Negociação", tipo_material="Material",
        tipo_obra="Residencial",
        localizacao="Tatuapé — São Paulo / SP",
        demanda="Cotação de cimento e blocos para alvenaria.",
        valor_proposta=8400.00,
        historico_extra=[{
            "campo": "observacao", "depois": "Primeira ligação OK",
            "descricao": "Cliente aceitou receber visita técnica na quinta.",
        }],
    ))
    leads_criados.append(_criar_lead(
        nome="Empresa Skyline Ltda", contato="(11) 4040-3300",
        email="projetos@skyline.com.br", responsavel=resp_diego,
        status=LeadStatus.EM_ANDAMENTO, dias_parado=6,
        origem="Google", cadencia="Contato Dia 3",
        situacao="Em Negociação", tipo_material="Projeto",
        tipo_obra="Empresarial",
        localizacao="Faria Lima — São Paulo / SP",
        demanda="Projeto executivo para retrofit de andar corporativo.",
        valor_proposta=42000.00,
    ))

    # ---- Enviado (2) — proposta despachada, aguardando.
    leads_criados.append(_criar_lead(
        nome="Roberto Carvalho", contato="(11) 99220-4400",
        email="roberto.c@example.com", responsavel=resp_ana,
        status=LeadStatus.ENVIADO, dias_parado=8,
        origem="Site", cadencia="Contato Dia 7",
        situacao="Orçamento Enviado", tipo_material="Obra Completa",
        tipo_obra="Residencial",
        localizacao="Moema — São Paulo / SP",
        demanda="Reforma completa de cobertura duplex.",
        valor_proposta=185000.00,
        data_envio=_hoje - _timedelta(days=8),
    ))
    leads_criados.append(_criar_lead(
        nome="Edifício Aurora — síndico", contato="(11) 4050-5500",
        email="sindico.aurora@example.com", responsavel=resp_bruno,
        status=LeadStatus.ENVIADO, dias_parado=10,
        origem="Indicação", cadencia="Contato Dia 7",
        situacao="Orçamento Enviado", tipo_material="Serviço",
        tipo_obra="Empreendimento",
        localizacao="Pinheiros — São Paulo / SP",
        demanda="Manutenção predial trimestral (fachada e hidráulica).",
        valor_proposta=22500.00,
        data_envio=_hoje - _timedelta(days=10),
    ))

    # ---- Validação (1) — proposta em análise técnica do cliente.
    leads_criados.append(_criar_lead(
        nome="Felipe Nogueira", contato="(11) 99330-6600",
        email="felipe.n@example.com", responsavel=resp_carla,
        status=LeadStatus.VALIDACAO, dias_parado=12,
        origem="Prospecção Ativa", cadencia="Contato Dia 15",
        situacao="Fechamento", tipo_material="Material",
        tipo_obra="Residencial",
        localizacao="Perdizes — São Paulo / SP",
        demanda="Aprovação técnica de proposta de drywall para 2 dormitórios.",
        valor_proposta=12800.00,
        data_envio=_hoje - _timedelta(days=14),
    ))

    # ---- Aprovado (1) — convertido em proposta+obra (Bela Vista).
    leads_criados.append(_criar_lead(
        nome=CLIENTE_NOME, contato=CLIENTE_TELEFONE,
        email=CLIENTE_EMAIL, responsavel=resp_diego,
        status=LeadStatus.APROVADO, dias_parado=18,
        origem="Indicação", cadencia="Contato Dia 15",
        situacao="Fechamento", tipo_material="Obra Completa",
        tipo_obra="Residencial",
        localizacao="São Paulo / SP",
        demanda="Execução civil — Residencial Bela Vista (250 m²).",
        valor_proposta=float(valor_total),
        observacao="Lead originário da proposta 001.26 — APROVADO e em execução.",
        data_envio=_hoje - _timedelta(days=22),
        cliente_id=cliente.id, proposta_id=proposta.id, obra_id=obra.id,
    ))

    # ---- Feedback (1) — aguardando resposta a ajustes solicitados.
    leads_criados.append(_criar_lead(
        nome="Juliana Tavares", contato="(11) 99440-7700",
        email="juliana.t@example.com", responsavel=resp_ana,
        status=LeadStatus.FEEDBACK, dias_parado=11,
        origem="Site", cadencia="Contato Dia 7",
        situacao="Em Negociação", tipo_material="Forros Removíveis",
        tipo_obra="Empresarial",
        localizacao="Vila Olímpia — São Paulo / SP",
        demanda="Ajuste de escopo solicitado — esperando devolutiva.",
        valor_proposta=15600.00,
        data_envio=_hoje - _timedelta(days=15),
    ))

    # ---- Congelado (1) — pausado, com data sugerida de retomada.
    leads_criados.append(_criar_lead(
        nome="Henrique Lopes", contato="(11) 99550-8800",
        email="henrique.l@example.com", responsavel=resp_bruno,
        status=LeadStatus.CONGELADO, dias_parado=20,
        origem="Anúncio Meta Ads", cadencia="Contato Dia 15",
        situacao="Sem Retorno", tipo_material="Material",
        tipo_obra="Residencial",
        localizacao="Saúde — São Paulo / SP",
        demanda="Cliente pediu para retomar após viagem.",
        valor_proposta=9800.00,
        data_retomada=_hoje + _timedelta(days=30),
    ))

    # ---- Perdido (2) — com motivo registrado.
    leads_criados.append(_criar_lead(
        nome="Camila Ribeiro", contato="(11) 99660-9900",
        email="camila.r@example.com", responsavel=resp_carla,
        status=LeadStatus.PERDIDO, dias_parado=15,
        origem="Google", cadencia="Contato Dia 7",
        situacao="Sem Retorno", tipo_material="Material",
        tipo_obra="Residencial", motivo_perda="Preço do Produto",
        localizacao="Mooca — São Paulo / SP",
        demanda="Cotação de cimento — fechou com concorrente.",
        valor_proposta=6200.00,
        data_envio=_hoje - _timedelta(days=20),
    ))
    leads_criados.append(_criar_lead(
        nome="Fernando Brito", contato="(11) 99770-1010",
        email="fernando.b@example.com", responsavel=resp_diego,
        status=LeadStatus.PERDIDO, dias_parado=25,
        origem="Prospecção Ativa", cadencia="Contato Dia 15",
        situacao="Sem Retorno", tipo_material="Obra Completa",
        tipo_obra="Residencial", motivo_perda="Desistência de Compra",
        localizacao="Butantã — São Paulo / SP",
        demanda="Cliente desistiu da reforma após mudança de planos.",
        valor_proposta=48000.00,
        data_envio=_hoje - _timedelta(days=30),
    ))

    db.session.commit()
    log.info(
        f"Task #20 CRM: {len(leads_criados)} leads criados em 8 estágios "
        f"do Kanban; 4 responsáveis cadastrados"
    )

    # 14) Task #20 — 2ª obra "Comercial Pinheiros" + 10 RDOs Finalizados ----
    # Dá volume real a Métricas (Carlos+3 diaristas em outra obra) e mostra
    # o gestor com mais de uma obra em andamento simultaneamente.
    # Reusa os Serviços de Alvenaria + Contrapiso (com cronograma 3 níveis).
    cliente_pin = Cliente(
        nome="Pinheiros Empreendimentos Ltda",
        email="contato@pinheirosempreend.com.br",
        telefone="(11) 3300-2200",
        endereco="Av. Pedroso de Morais, 1000 — Pinheiros, São Paulo / SP",
        cnpj="22.333.444/0001-55",
        admin_id=aid,
    )
    db.session.add(cliente_pin); db.session.flush()

    proposta_pin = Proposta(
        numero="002.26",
        data_proposta=date(2026, 1, 20),
        cliente_id=cliente_pin.id,
        cliente_nome=cliente_pin.nome,
        cliente_telefone=cliente_pin.telefone,
        cliente_email=cliente_pin.email,
        cliente_endereco=cliente_pin.endereco,
        titulo="Comercial Pinheiros — execução civil",
        descricao=(
            "Execução de alvenaria de vedação, contrapiso e mobilização "
            "de canteiro para o Comercial Pinheiros (1.500 m² úteis)."
        ),
        prazo_entrega_dias=180, validade_dias=15,
        status="rascunho",
        valor_total=Decimal("0.00"),
        criado_por=aid, admin_id=aid,
        data_envio=datetime(2026, 1, 21, 9, 30),
    )
    db.session.add(proposta_pin); db.session.flush()

    # Itens dimensionados para que a obra Pinheiros caia na faixa
    # ~R$ 350-500k (spec da Task #20). Total = 1500*165 + 1500*95 +
    # 1500*35 + 20.000 = R$ 462.500. Três serviços (Alvenaria, Contrapiso,
    # Pintura) com TEMPLATE — alimentam Métricas "Empresa por Serviço"
    # com ≥3 serviços com dados, conforme spec. O item 4 (mobilização)
    # usa serv_mob (sem template) — verba financeira pura, não entra
    # no cronograma materializado.
    itens_pin_def = [
        ("Alvenaria de bloco cerâmico — Pinheiros",
         Decimal("1500.000"), "m2", Decimal("165.00"), serv_alv, 1),
        ("Contrapiso desempenado — Pinheiros",
         Decimal("1500.000"), "m2", Decimal("95.00"), serv_pis, 2),
        ("Pintura interna acrílica — Pinheiros",
         Decimal("1500.000"), "m2", Decimal("35.00"), serv_pin, 3),
        ("Mobilização e canteiro — Pinheiros",
         Decimal("1.000"), "vb", Decimal("20000.00"), serv_mob, 4),
    ]
    valor_pin = Decimal("0.00")
    propostaitem_pin_objs = []
    for idx, (desc, qtd, un, preco, serv, ordem) in enumerate(itens_pin_def, start=1):
        sub = (qtd * preco).quantize(Decimal("0.01"))
        valor_pin += sub
        pi = PropostaItem(
            admin_id=aid, proposta_id=proposta_pin.id,
            item_numero=idx, descricao=desc,
            quantidade=qtd, unidade=un,
            preco_unitario=preco, ordem=ordem,
            servico_id=serv.id,
            quantidade_medida=qtd,
            custo_unitario=Decimal(str(serv.custo_unitario)),
            lucro_unitario=preco - Decimal(str(serv.custo_unitario)),
            subtotal=sub,
        )
        db.session.add(pi); propostaitem_pin_objs.append(pi)
    db.session.flush()
    proposta_pin.valor_total = valor_pin

    obra_pin = Obra(
        nome="Comercial Pinheiros", codigo="OBR-2026-002",
        endereco=cliente_pin.endereco,
        data_inicio=date(2026, 2, 1),
        data_previsao_fim=date(2026, 7, 31),
        orcamento=float(valor_pin),
        valor_contrato=float(valor_pin),
        area_total_m2=1500.0,
        status="Em andamento",
        cliente_id=cliente_pin.id,
        proposta_origem_id=proposta_pin.id, portal_ativo=True,
        responsavel_id=carlos.id, ativo=True, admin_id=aid,
        data_inicio_medicao=date(2026, 2, 1),
        valor_entrada=Decimal("0.00"), data_entrada=None,
    )
    db.session.add(obra_pin); db.session.flush()
    proposta_pin.obra_id = obra_pin.id
    proposta_pin.convertida_em_obra = True
    proposta_pin.status = "aprovada"
    proposta_pin.data_resposta_cliente = datetime(2026, 1, 28, 11, 0)

    arvore_pin = montar_arvore_preview(proposta_pin, aid)
    proposta_pin.cronograma_default_json = arvore_pin

    for pi in propostaitem_pin_objs:
        db.session.add(ItemMedicaoComercial(
            admin_id=aid, obra_id=obra_pin.id,
            nome=pi.descricao[:200],
            valor_comercial=pi.subtotal,
            servico_id=pi.servico_id,
            quantidade=pi.quantidade,
            proposta_item_id=pi.id,
            status="PENDENTE",
        ))
    db.session.flush()

    n_tarefas_pin = materializar_cronograma(
        proposta_pin, aid, obra_pin.id, arvore_pin,
    )
    log.info(
        f"Task #20 Pinheiros: cronograma materializado — {n_tarefas_pin} "
        f"tarefas, valor R$ {float(valor_pin):.2f}"
    )
    db.session.flush()

    # 10 RDOs Finalizados, semanais, terça-feira (03/02 → 07/04/2026).
    # Progresso monotônico 10→100% com VARIAÇÃO intencional de
    # incrementos: a maioria dos RDOs avança +10%/semana, mas idx 3
    # avança apenas +5% (produtividade ABAIXO do orçado, gera divergência
    # em "Empresa por Serviço" → coluna Índice abaixo de 100%) e idx 7
    # avança +15% (compensação que recupera o atraso). 2 RDOs ficam com
    # 1 diarista omitido (idx 4 sem Marcos; idx 7 sem João) — demonstra
    # ausências em Métricas.
    folhas_pin = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_pin.id, admin_id=aid, is_cliente=False)
        .filter(TarefaCronograma.subatividade_mestre_id.isnot(None))
        .order_by(TarefaCronograma.ordem.asc())
        .all()
    )
    log.info(f"Task #20 Pinheiros: folhas do cronograma {len(folhas_pin)}")

    # Mix de horas (6h-10h) e horas extras (0h-2h) por RDO — gera
    # variação realista em Métricas (custo MO, produtividade,
    # detalhe do funcionário). Mantém o mesmo valor para todos os
    # funcionários daquele RDO (jornada do dia).
    #
    # `perc_planejado` é o cronograma orçado (10/20/30/.../100% linear
    # em incrementos de 10%/semana). `perc_destino` é o REALIZADO,
    # que diverge do planejado nos RDOs 3-6 (atraso por produtividade
    # abaixo na 3ª semana → permanece -5% até a recuperação no idx 7).
    # Essa divergência alimenta /metricas/servico (Empresa por Serviço,
    # índice < 100 em alguns RDOs) e /metricas/divergencia/servico/<id>.
    # Task #5 — hora extra removida do RDO. Tuplas mantidas como
    # (data, perc_realizado, horas, perc_anterior, perc_planejado).
    rdos_pin_dados = [
        # (data, perc_realizado, horas, perc_anterior, perc_planejado)
        (date(2026, 2, 3),  10.0, 8.0,   0.0,  10.0),
        (date(2026, 2, 10), 20.0, 9.0,  10.0,  20.0),
        (date(2026, 2, 17), 25.0, 6.0,  20.0,  30.0),  # ABAIXO do orçado
        (date(2026, 2, 24), 35.0, 8.0,  25.0,  40.0),  # ausência Marcos
        (date(2026, 3, 3),  45.0, 10.0, 35.0,  50.0),  # turno estendido
        (date(2026, 3, 10), 55.0, 8.0,  45.0,  60.0),
        (date(2026, 3, 17), 70.0, 9.5,  55.0,  70.0),  # COMPENSAÇÃO
        (date(2026, 3, 24), 80.0, 8.0,  70.0,  80.0),
        (date(2026, 3, 31), 90.0, 7.0,  80.0,  90.0),  # dia chuvoso
        (date(2026, 4, 7), 100.0, 8.5,  90.0, 100.0),  # entrega final
    ]
    omitir_diarista_no_idx = {4: marcos.id, 7: joao.id}
    # Tipo + severidade da ocorrência por RDO — garante mix Baixa/Média
    # conforme spec da Task #20.
    ocorrencia_por_idx = {
        1:  ("Observação", "Baixa",  "Início da obra — equipe nivelada."),
        2:  ("Hora Extra", "Baixa",  "Extra leve para concluir a fundação do trecho A."),
        3:  ("Atraso",     "Média",  "Produtividade abaixo do orçado (clima úmido na 3ª semana)."),
        4:  ("Ausência",   "Média",  "Marcos faltou — ajustada distribuição de tarefas."),
        5:  ("Hora Extra", "Média",  "Turno estendido para liberar trecho crítico antes do feriado."),
        6:  ("Observação", "Baixa",  "Avanço dentro do planejado."),
        7:  ("Ausência",   "Média",  "João ausente — equipe compensou com hora extra."),
        8:  ("Observação", "Baixa",  "Avanço dentro do planejado."),
        9:  ("Clima",      "Baixa",  "Chuva forte — jornada reduzida."),
        10: ("Observação", "Baixa",  "Entrega final — checklist concluído."),
    }

    from models import RDOApontamentoCronograma as _RAC_pin
    _v2_acum_pin = {}
    for idx, (dt, perc_destino, horas, perc_anterior,
              perc_planejado) in enumerate(rdos_pin_dados, start=1):
        omitir_id = omitir_diarista_no_idx.get(idx)
        rdo = RDO(
            numero_rdo=f"RDO-PIN-2026-{idx:03d}",
            data_relatorio=dt, obra_id=obra_pin.id,
            criado_por_id=aid, admin_id=aid,
            clima_geral=("Chuvoso" if idx == 9 else "Ensolarado"),
            temperatura_media=("19°C" if idx == 9 else "25°C"),
            condicoes_trabalho=("Adversas" if idx in (3, 9) else "Ideais"),
            local="Campo",
            comentario_geral=(
                f"Avanço semanal — meta {perc_destino:.0f}% "
                f"(incremento de {perc_destino - perc_anterior:.0f}%, "
                f"jornada {horas:.1f}h)."
            ),
            # Task #6 — Rascunho; finalizado abaixo via emit do evento.
            status="Rascunho",
        )
        db.session.add(rdo); db.session.flush()

        for folha in folhas_pin:
            _nome_low = folha.nome_tarefa.lower()
            if ("pintura" in _nome_low or "tinta" in _nome_low
                    or "massa" in _nome_low):
                _serv_id = serv_pin.id
            elif ("alvenaria" in _nome_low or "marcação" in _nome_low
                    or "chapisco" in _nome_low):
                _serv_id = serv_alv.id
            else:
                _serv_id = serv_pis.id
            _qty_total = float(folha.quantidade_total or 0.0)
            _qty_dia_rss = max(
                0.0,
                _qty_total * (perc_destino - perc_anterior) / 100.0,
            )
            rss = RDOServicoSubatividade(
                rdo_id=rdo.id,
                servico_id=_serv_id,
                nome_subatividade=folha.nome_tarefa,
                descricao_subatividade=folha.nome_tarefa,
                percentual_conclusao=perc_destino,
                percentual_anterior=perc_anterior,
                incremento_dia=perc_destino - perc_anterior,
                quantidade_produzida=_qty_dia_rss,
                ordem_execucao=folha.ordem, ativo=True,
                admin_id=aid,
                subatividade_mestre_id=folha.subatividade_mestre_id,
            )
            db.session.add(rss); db.session.flush()
            db.session.add(RDOMaoObra(
                admin_id=aid, rdo_id=rdo.id,
                funcionario_id=carlos.id,
                funcao_exercida="Pedreiro (mensalista)",
                horas_trabalhadas=horas,
                tarefa_cronograma_id=folha.id,
                subatividade_id=rss.id,
            ))
            for _diar, _func in (
                (pedro,  "Encarregado (diária)"),
                (joao,   "Servente (diária)"),
                (marcos, "Servente (diária)"),
            ):
                if omitir_id and _diar.id == omitir_id:
                    continue
                db.session.add(RDOMaoObra(
                    admin_id=aid, rdo_id=rdo.id,
                    funcionario_id=_diar.id, funcao_exercida=_func,
                    horas_trabalhadas=horas,
                    tarefa_cronograma_id=folha.id,
                    subatividade_id=rss.id,
                ))
            folha.percentual_concluido = perc_destino

            if folha.quantidade_total and folha.quantidade_total > 0:
                qty_destino_acum = float(folha.quantidade_total) * (perc_destino / 100.0)
                qty_anterior_acum = _v2_acum_pin.get(folha.id, 0.0)
                qty_dia = max(0.0, qty_destino_acum - qty_anterior_acum)
                _v2_acum_pin[folha.id] = qty_destino_acum
                db.session.add(_RAC_pin(
                    rdo_id=rdo.id, tarefa_cronograma_id=folha.id,
                    admin_id=aid,
                    quantidade_executada_dia=qty_dia,
                    quantidade_acumulada=qty_destino_acum,
                    percentual_realizado=perc_destino,
                    percentual_planejado=perc_planejado,
                ))

        # Equipamento varia (≥3 RDOs com equipamento, conforme spec).
        if idx in (1, 4, 6, 9):
            db.session.add(RDOEquipamento(
                admin_id=aid, rdo_id=rdo.id,
                nome_equipamento="Betoneira 400L", quantidade=1,
                horas_uso=max(2.0, horas - 2.0), estado_conservacao="Bom",
            ))
        if idx in (2, 5, 8):
            db.session.add(RDOEquipamento(
                admin_id=aid, rdo_id=rdo.id,
                nome_equipamento="Andaime tubular (10m²)", quantidade=2,
                horas_uso=horas, estado_conservacao="Bom",
            ))
        # Ocorrência por RDO com mix de severidade Baixa/Média.
        _tipo_oc, _sev_oc, _desc_oc = ocorrencia_por_idx.get(
            idx, ("Observação", "Baixa", "Avanço dentro do planejado.")
        )
        db.session.add(RDOOcorrencia(
            admin_id=aid, rdo_id=rdo.id,
            tipo_ocorrencia=_tipo_oc, severidade=_sev_oc,
            descricao_ocorrencia=_desc_oc,
            status_resolucao="Resolvido",
        ))

        db.session.flush()

        # Task #3 — recalcula produtividade snapshot por RDO (mesma rotina
        # disparada pelo finalize handler em views/rdo.py).
        from services.rdo_custos import recalcular_produtividade_rdo as _recalc_prod_pin
        _recalc_prod_pin(rdo)

        # Task #6 — finaliza pelo mesmo caminho da rota: status='Finalizado',
        # commit, emit 'rdo_finalizado'. O handler oficial cria os custos.
        rdo.status = "Finalizado"
        db.session.commit()
        from event_manager import EventManager as _EM_pin
        _EM_pin.emit('rdo_finalizado', {
            'rdo_id': rdo.id,
            'obra_id': rdo.obra_id,
            'data_relatorio': str(rdo.data_relatorio),
        }, aid)

        log.info(
            f"Task #20 Pinheiros: RDO {idx}/{len(rdos_pin_dados)} "
            f"({dt.isoformat()}) finalizado — {perc_destino:.0f}%"
        )

    # Task #3 — rolla as tarefas-pai do cronograma do Pinheiros para refletir
    # o avanço dos filhos finalizados.
    from utils.cronograma_engine import sincronizar_percentuais_obra as _sinc_perc_pin
    _sinc_perc_pin(obra_pin.id, aid)

    db.session.commit()

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
        "servico_pintura_id": serv_pin.id,
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
        # Task #20
        "n_leads": len(leads_criados),
        "n_responsaveis_crm": 4,
        "obra_pinheiros_id": obra_pin.id,
        "obra_pinheiros_codigo": obra_pin.codigo,
        "n_rdos_pinheiros": len(rdos_pin_dados),
        "valor_obra_pinheiros": float(valor_pin),
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
    # Task #20 — CRM + 2ª obra
    log.info(f"    crm_responsaveis   = {info.get('n_responsaveis_crm', 0)}  "
             f"(Ana Paula, Bruno, Carla, Diego)")
    log.info(f"    crm_leads          = {info.get('n_leads', 0)}  "
             f"(distribuídos nas 8 colunas do Kanban)")
    log.info(f"    obra_pinheiros_id  = {info.get('obra_pinheiros_id')}  "
             f"({info.get('obra_pinheiros_codigo')} — Comercial Pinheiros, "
             f"R$ {info.get('valor_obra_pinheiros', 0):.2f})")
    log.info(f"    rdos_pinheiros     = {info.get('n_rdos_pinheiros', 0)}  "
             f"(Finalizados — progresso monotônico 10→100% com variação "
             f"semanal: 1 RDO em produtividade abaixo do orçado + 1 RDO "
             f"de compensação)")
    log.info("")
    log.info("  Roteiro sugerido (12 telas, na ordem):")
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
    log.info(f"  11) CRM (Kanban)      → {base_url}/crm/")
    log.info(f"      CRM (Lista)       → {base_url}/crm/lista")
    log.info(f"  12) Métricas          → {base_url}/metricas")
    log.info(f"      Métricas/Serviço  → {base_url}/metricas/servico")
    log.info(f"      Métricas/Função   → {base_url}/metricas/funcionarios")
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# Task #18 — lançamentos demo para o mês corrente (Realizado no Período)
# ---------------------------------------------------------------------------
def _seed_custos_mes_atual(admin_id):
    """Cria lançamentos GestaoCustoPai/Filho no mês corrente para que o
    gráfico 'Realizado no Período' mostre dados ao filtrar por Mês Atual.

    Idempotente via origem_tabela='demo_mes_atual'. Executa tanto no
    caminho fresh quanto no idempotente (reseed automático por deploy).
    """
    try:
        from app import db
        from models import GestaoCustoPai, GestaoCustoFilho, Obra
        from sqlalchemy import text
        from datetime import date

        hoje = date.today()
        dia_ref = hoje.replace(day=10)  # dia 10 do mês corrente

        obras = (
            Obra.query
            .filter_by(admin_id=admin_id, ativo=True)
            .filter(Obra.codigo.in_(["OBR-2026-001", "OBR-2026-002"]))
            .all()
        )
        if not obras:
            log.warning("Task #18 seed: obras demo não encontradas — pulando")
            return

        # Entradas diferenciadas por tipo de obra:
        #   OBR-2026-001 Residencial Bela Vista  → mais Mão de Obra (250 m²)
        #   OBR-2026-002 Comercial Pinheiros      → mais Material + Subempreitada (1 500 m²)
        _ENTRADAS_POR_OBRA = {
            "OBR-2026-001": [
                # (entidade_nome, tipo_cat, valor, descricao_especifica)
                ("Mão de Obra Direta",
                 "MAO_OBRA_DIRETA", 4_200.00,
                 "Pedreiros e serventes — semana 1 e 2, Bela Vista"),
                ("Material de Construção",
                 "MATERIAL",        1_850.00,
                 "Argamassa, bloco cerâmico e tela soldada — Bela Vista"),
                ("Equipamentos",
                 "EQUIPAMENTO",       620.00,
                 "Aluguel betoneira e andaime tubular — Bela Vista"),
            ],
            "OBR-2026-002": [
                ("Material de Construção",
                 "MATERIAL",        9_400.00,
                 "Aço CA-50, forma metálica e concreto usinado — Pinheiros"),
                ("Mão de Obra Direta",
                 "MAO_OBRA_DIRETA", 5_800.00,
                 "Equipe de estrutura e acabamento — semana 1 e 2, Pinheiros"),
                ("Subempreitada Elétrica",
                 "SUBEMPREITADA",   3_200.00,
                 "Subempreitada instalações elétricas prediais — Pinheiros"),
                ("Equipamentos Pesados",
                 "EQUIPAMENTO",     1_150.00,
                 "Locação grua torre e bomba de concreto — Pinheiros"),
            ],
        }

        # ------------------------------------------------------------------ #
        # Limpeza antes da inserção: garante que reseeds (inclusive com      #
        # valores antigos do Task #18 original) resultem em dados atuais.    #
        # Apaga GCFs demo_mes_atual do mês corrente para estas obras,        #
        # depois remove os GCPs órfãos correspondentes.                      #
        # ------------------------------------------------------------------ #
        obra_ids = [o.id for o in obras]

        gcfs_antigos = (
            GestaoCustoFilho.query
            .filter(
                GestaoCustoFilho.obra_id.in_(obra_ids),
                GestaoCustoFilho.admin_id == admin_id,
                GestaoCustoFilho.origem_tabela == 'demo_mes_atual',
                db.extract('year',  GestaoCustoFilho.data_referencia) == hoje.year,
                db.extract('month', GestaoCustoFilho.data_referencia) == hoje.month,
            )
            .all()
        )
        pai_ids_antigos = list({gcf.pai_id for gcf in gcfs_antigos})
        for gcf in gcfs_antigos:
            db.session.delete(gcf)
        db.session.flush()

        # Remove GCPs que ficaram sem filhos após a limpeza
        for pai_id in pai_ids_antigos:
            pai = db.session.get(GestaoCustoPai, pai_id)
            if pai and not pai.filhos:
                db.session.delete(pai)
        db.session.flush()

        # ------------------------------------------------------------------ #
        # Inserção dos novos lançamentos realistas                            #
        # ------------------------------------------------------------------ #
        criados = 0
        for obra in obras:
            entradas = _ENTRADAS_POR_OBRA.get(obra.codigo, [])
            for entidade_nome, tipo_cat, valor, descricao in entradas:
                gcp = GestaoCustoPai(
                    admin_id=admin_id,
                    tipo_categoria=tipo_cat,
                    entidade_nome=entidade_nome,
                    valor_total=valor,
                    valor_solicitado=valor,
                    status='PENDENTE',
                    data_vencimento=dia_ref,
                )
                db.session.add(gcp)
                db.session.flush()

                gcf = GestaoCustoFilho(
                    pai_id=gcp.id,
                    admin_id=admin_id,
                    obra_id=obra.id,
                    data_referencia=dia_ref,
                    descricao=descricao,
                    valor=valor,
                    origem_tabela='demo_mes_atual',
                )
                db.session.add(gcf)
                criados += 1

        db.session.commit()
        removidos = len(gcfs_antigos)
        log.info(
            f"Task #18 seed: {removidos} entrada(s) antigas removidas, "
            f"{criados} lançamento(s) demo criados "
            f"para {hoje.strftime('%m/%Y')} em {len(obras)} obra(s)"
        )
    except Exception as exc:
        from app import db as _db
        _db.session.rollback()
        log.warning(f"Task #18 seed custos mês atual falhou (não crítico): {exc}")


# ---------------------------------------------------------------------------
# Entry point com guarda de produção
# ---------------------------------------------------------------------------
def _backfill_custos_rdo_demo(admin_id):
    """Roda gerar_custos_mao_obra_rdo() em todos os RDOs finalizados de
    TODAS as obras do admin Alfa (Bela Vista + Pinheiros + qualquer outra
    futura). Idempotente — só insere o que falta. Também promove o admin
    Alfa para versao_sistema='v2' (a demo usa diaristas + Gestão de Custos
    V2, recursos exclusivos do v2).
    """
    try:
        from app import db
        from models import Usuario, Obra, RDO
        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        from event_manager import EventManager

        admin = Usuario.query.get(admin_id)
        if admin and getattr(admin, 'versao_sistema', None) != 'v2':
            log.info(
                f"backfill: promovendo admin Alfa (id={admin_id}) "
                f"de {admin.versao_sistema!r} para 'v2'"
            )
            admin.versao_sistema = 'v2'
            db.session.commit()

        obras = Obra.query.filter_by(admin_id=admin_id).all()
        if not obras:
            log.info("backfill custos RDO: nenhuma obra encontrada")
            return

        rdos_geral = 0
        custo_diario_total = 0
        for obra in obras:
            rdos = (
                RDO.query
                .filter_by(obra_id=obra.id, status="Finalizado")
                .all()
            )
            rdos_geral += len(rdos)
            for rdo in rdos:
                # 1) RDOCustoDiario (Task #2) — alimenta métricas de
                #    produtividade/lucratividade (Task #3).
                try:
                    custo_diario_total += gravar_custo_funcionario_rdo(
                        rdo, admin_id
                    ) or 0
                except Exception as e:
                    log.warning(
                        f"backfill RDOCustoDiario {rdo.numero_rdo} "
                        f"falhou: {e}"
                    )
                # 2) GestaoCustoFilho — Task #6: emite o MESMO evento da
                #    rota oficial (`views.rdo.finalizar_rdo`). O handler
                #    `event_manager.lancar_custos_rdo` cria os GCP/GCF
                #    (SALARIO/VA/VT) e é idempotente por
                #    (entidade_id, data, categoria) — re-emit é seguro.
                try:
                    EventManager.emit('rdo_finalizado', {
                        'rdo_id': rdo.id,
                        'obra_id': rdo.obra_id,
                        'data_relatorio': str(rdo.data_relatorio),
                    }, admin_id)
                except Exception as e:
                    log.warning(f"backfill RDO {rdo.numero_rdo} falhou: {e}")
        if custo_diario_total:
            log.info(
                f"backfill RDOCustoDiario: {custo_diario_total} "
                f"linha(s) gravada(s) em {rdos_geral} RDO(s)."
            )
        log.info(
            f"backfill custos RDO: evento 'rdo_finalizado' re-emitido para "
            f"{rdos_geral} RDO(s) em {len(obras)} obra(s) — handler "
            f"`lancar_custos_rdo` é idempotente."
        )
    except Exception:
        log.exception("backfill custos RDO falhou")


def _verificar_custos_demo(admin_id, obra_id, obra_label="Bela Vista",
                           check_material=True):
    """Task #6 / Task #7 — verificação automática end-of-seed.

    Garante que o tenant Alfa terminou o seed com:
      • SALARIO/MAO_OBRA_DIRETA originados de RDO (`origem_tabela`
        IN ('rdo_mao_obra','rdo_custo_diario'))  ← via emit
        'rdo_finalizado' → `lancar_custos_rdo`
      • MATERIAL originados de PedidoCompra (`origem_tabela`
        ='pedido_compra')                         ← via
        `processar_compra_normal` (só na obra principal — Pinheiros
        não tem PedidoCompra na demo)

    Task #7: também valida a obra Pinheiros (passar
    ``check_material=False``), que historicamente perdia o lançamento
    de mão-de-obra por causa do truncamento de descrição em
    ``custo_obra.descricao`` (StringDataRightTruncation silenciado pelo
    EventManager). Sem essa cobertura, regressões no handler
    ``lancar_custos_rdo`` ficavam invisíveis.

    Se faltar qualquer uma das fontes esperadas, levanta RuntimeError
    com mensagem clara — falha o seed alto e visível, em vez de
    produzir um demo silenciosamente quebrado.
    """
    from app import db
    from sqlalchemy import text

    # Filtra por origem_tabela: garante que MAO_OBRA veio do fluxo do RDO
    # (handler `lancar_custos_rdo`) e MATERIAL veio de uma compra
    # (`processar_compra_normal`). Sem esse filtro a verificação aceitaria
    # custos das mesmas categorias vindos de outras origens (ex.: ponto
    # eletrônico, conta a pagar manual) — o que mascararia regressão no
    # fluxo automático que esta task está protegendo.
    rows = db.session.execute(text("""
        SELECT
            CASE
              WHEN gcp.tipo_categoria IN ('MATERIAL','COMPRA')
                   AND gcf.origem_tabela = 'pedido_compra'             THEN 'MATERIAL'
              WHEN gcp.tipo_categoria IN ('SALARIO','MAO_OBRA_DIRETA')
                   AND gcf.origem_tabela IN ('rdo_mao_obra',
                                             'rdo_custo_diario')      THEN 'MAO_OBRA'
              ELSE 'OUTRO'
            END                                       AS bucket,
            COUNT(*)                                  AS n,
            COALESCE(SUM(gcf.valor), 0)               AS total
        FROM gestao_custo_filho gcf
        JOIN gestao_custo_pai   gcp ON gcp.id = gcf.pai_id
        WHERE gcf.obra_id  = :o
          AND gcf.admin_id = :a
        GROUP BY 1
    """), {"o": obra_id, "a": admin_id}).fetchall()

    por_bucket = {r[0]: (int(r[1]), float(r[2] or 0)) for r in rows}
    n_mo, v_mo  = por_bucket.get('MAO_OBRA', (0, 0.0))
    n_mat, v_mat = por_bucket.get('MATERIAL', (0, 0.0))

    log.info(
        f"[VERIFY] obra={obra_id} ({obra_label}) → "
        f"MAO_OBRA: {n_mo} GCF (R$ {v_mo:.2f}) | "
        f"MATERIAL: {n_mat} GCF (R$ {v_mat:.2f})"
    )

    faltando = []
    if n_mo == 0:
        faltando.append(
            f"MAO_OBRA (esperado via emit 'rdo_finalizado' → "
            f"`lancar_custos_rdo` nos RDOs de {obra_label})"
        )
    if check_material and n_mat == 0:
        faltando.append(
            "MATERIAL (esperado via `processar_compra_normal` "
            "no PedidoCompra NF-2026-0001)"
        )
    if faltando:
        raise RuntimeError(
            f"Verificação falhou: obra {obra_id} ({obra_label}) ficou "
            f"sem GestaoCustoFilho de {' E '.join(faltando)}. "
            f"Buckets atuais: {por_bucket!r}"
        )


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
                _seed_custos_mes_atual(existente.id)
                # Task #6 — verificação também no caminho idempotente, para
                # detectar regressão em demos legados a cada re-execução.
                from models import Obra
                obra_principal = (
                    Obra.query
                    .filter_by(admin_id=existente.id, codigo="OBR-2026-001")
                    .first()
                )
                if obra_principal:
                    _verificar_custos_demo(
                        existente.id, obra_principal.id,
                        obra_label="Bela Vista",
                        check_material=True,
                    )
                else:
                    log.warning(
                        "verificação pulada: obra principal "
                        "(OBR-2026-001) não encontrada no tenant Alfa"
                    )
                # Task #7: Pinheiros tem 7 subatividades por funcionário
                # — historicamente perdia o lançamento de custos por
                # truncamento da descrição. Agora vai junto na verificação.
                obra_pinheiros = (
                    Obra.query
                    .filter_by(admin_id=existente.id, codigo="OBR-2026-002")
                    .first()
                )
                if obra_pinheiros:
                    _verificar_custos_demo(
                        existente.id, obra_pinheiros.id,
                        obra_label="Comercial Pinheiros",
                        check_material=False,
                    )
                else:
                    log.warning(
                        "verificação pulada: obra Pinheiros "
                        "(OBR-2026-002) não encontrada no tenant Alfa"
                    )
                return 0

            log.info(
                f"plantando dataset Alfa (ambiente={args.ambiente})…"
            )
            info = _seed()
            # Após plantar (caminho fresh ou --reset), grava RDOCustoDiario
            # e re-emite 'rdo_finalizado' (idempotente) — fecha custos de
            # mão-de-obra também para demos antigos.
            _backfill_custos_rdo_demo(info["admin_id"])
            _seed_custos_mes_atual(info["admin_id"])
            # Task #6 — verificação obrigatória: MAO_OBRA via evento RDO +
            # MATERIAL via processar_compra_normal precisam existir.
            _verificar_custos_demo(
                info["admin_id"], info["obra_id"],
                obra_label="Bela Vista",
                check_material=True,
            )
            # Task #7 — Pinheiros (7 subatividades por funcionário) também
            # precisa terminar com lançamento completo de mão-de-obra.
            obra_pinheiros_id = info.get("obra_pinheiros_id")
            if obra_pinheiros_id:
                _verificar_custos_demo(
                    info["admin_id"], obra_pinheiros_id,
                    obra_label="Comercial Pinheiros",
                    check_material=False,
                )
            _imprimir_demo_pronta(info, args.ambiente)
            return 0

        except Exception as e:
            from app import db
            db.session.rollback()
            log.exception(f"erro durante seed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
