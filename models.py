# MODELS CONSOLIDADOS - SIGE v8.0
# Arquivo único para eliminar dependências circulares

from flask_login import UserMixin
from datetime import datetime, date, time
from sqlalchemy import func, JSON, Column, Integer, String, Text, DateTime, Numeric, ForeignKey
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, relationship, validates
from functools import lru_cache
import logging
import secrets

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class TipoUsuario(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    GESTOR_EQUIPES = "gestor_equipes"
    ALMOXARIFE = "almoxarife"  # MÓDULO 4: Almoxarifado
    FUNCIONARIO = "funcionario"


class EstadoObra(Enum):
    """Estados da Obra — Fase 2.

    Antes desta fase o estado da obra era `Obra.status`, um
    `db.Column(db.String(20), default='Em andamento')` de texto livre
    alimentado por um dropdown editável pelo tenant
    (`services/dropdown_service.py:94`). Três grafias convivem para os
    mesmos dois conceitos — `'Em andamento'` gravado por `models.py:297`,
    `'Em Andamento'` oferecido por `forms.py:42` e pelo dropdown — e o
    filtro de `views/obras.py:82-83` compara igualdade exata, então nunca
    casa com metade delas. Há ainda um segundo eixo paralelo, `Obra.ativo`,
    que a UI chama de "Concluída / Inativa"
    (`templates/obras_moderno.html:803`) sem nunca sincronizar com `status`.

    Os cinco valores abaixo são exatamente os que o código já produz ou já
    oferece ao usuário — nenhum foi inventado. O rótulo humano de cada um
    vive em `services.obra_estado.ROTULOS` e é o texto gravado no campo
    legado `Obra.status`, que passa a ser derivado por write-through.

    Gravado como VARCHAR(20) + CHECK, não como ENUM nativo do Postgres:
    acrescentar valor a um tipo ENUM exige ALTER TYPE, que não roda dentro
    do bloco transacional em que as migrações deste repo executam.
    """
    PLANEJAMENTO = "planejamento"   # obra existe, sem GP, cronograma não aceito
    EM_EXECUCAO = "em_execucao"     # handoff feito; é o 'Em andamento' de hoje
    PAUSADA = "pausada"             # paralisada, com motivo registrado
    CONCLUIDA = "concluida"         # entregue; equivale ao ativo=False de hoje
    CANCELADA = "cancelada"         # terminal: distrato/desistência


class PapelObra(Enum):
    """Papel de um usuário DENTRO de uma obra específica — Fase 1.

    Ortogonal a `TipoUsuario`, que é o papel no TENANT. Um usuário pode
    ser FUNCIONARIO na empresa e GESTOR de uma obra; outro pode ser
    FUNCIONARIO na empresa e APONTADOR de três obras. ADMIN e
    SUPER_ADMIN não precisam de vínculo: enxergam todas as obras do
    tenant por definição (ver utils/autorizacao.obras_visiveis).

    COMPRADOR entrou na Fase 3, quando passaram a existir verbos para
    ele: criar requisição de compra e emitir pedido a partir de
    requisição aprovada (compras_views.py). Ele NÃO aprova — quem aprova
    é GESTOR ou ADMIN, e a separação de funções é checada em
    services/alcada_compras.pode_aprovar.
    """
    GESTOR = "gestor"        # responde pela obra: edita, aprova, faz handoff
    APONTADOR = "apontador"  # lança RDO e apontamento; não edita a obra
    LEITOR = "leitor"        # só leitura
    COMPRADOR = "comprador"  # requisita e emite pedido; NÃO aprova e NÃO edita a obra


class EstadoRequisicao(Enum):
    """Ciclo de vida da RequisicaoCompra — Fase 3.

    Mesma forma da máquina de estados da Obra (Fase 2) e da
    CronogramaImportacao (models.py:5037): enum de estado + tabela de
    transição auditada + um único chokepoint que valida. Não há
    `transicionar` no modelo de propósito — ele vive em
    services/requisicao_compra.py, para que exista UM caminho de escrita.

    Terminais: REJEITADA, CONVERTIDA e CANCELADA. De CONVERTIDA não se
    volta: o PedidoCompra já existe e já gerou GestaoCustoPai e
    ContaPagar (compras_views.py:193-254).
    """
    RASCUNHO = "rascunho"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    CONVERTIDA = "convertida"
    CANCELADA = "cancelada"


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    tipo_usuario = db.Column(db.Enum(TipoUsuario), default=TipoUsuario.FUNCIONARIO, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para funcionários, referencia seu admin
    # Fase 1 — identidade estável da pessoa. Até 2026-07-21 não existia
    # nenhuma FK ligando o login à linha de RH: `views/employees.py:686`
    # casava por substring do username, `crud_rdo_completo.py:30` tinha um
    # e-mail chumbado, e o último fallback pegava o primeiro funcionário
    # ativo do banco INTEIRO. Nullable porque nem todo usuário é
    # funcionário (o admin da construtora não é) e nem todo funcionário
    # tem login. UNIQUE porque uma pessoa de RH tem no máximo um login —
    # no Postgres UNIQUE admite múltiplos NULL, que é o que queremos.
    # INVARIANTE DE TENANT: o Funcionario apontado tem que ser do mesmo
    # tenant do Usuario. Não dá para expressar como CHECK entre tabelas;
    # é garantido por `utils.identidade.vincular_funcionario` e travado
    # por `tests/test_fase1_identidade.py::test_vinculo_cross_tenant_e_recusado`.
    funcionario_id = db.Column(
        db.Integer,
        db.ForeignKey('funcionario.id', ondelete='SET NULL'),
        unique=True, nullable=True, index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    versao_sistema = db.Column(db.String(10), default='v1', nullable=False)  # 'v1' ou 'v2' - Feature Flag V2

    # Relacionamentos
    funcionarios = db.relationship('Usuario', backref=db.backref('admin', remote_side=[id]), lazy='dynamic')
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id],
                                  backref=db.backref('usuario', uselist=False))

class Departamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionarios = db.relationship('Funcionario', backref='departamento_ref', lazy=True)

class Funcao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    salario_base = db.Column(db.Float, default=0.0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    # Task #62 — Insumo (tipo MAO_OBRA) equivalente desta função.
    # Usado pelo auto-vínculo Função→ComposicaoServico no salvamento de RDO.
    insumo_id = db.Column(
        db.Integer,
        db.ForeignKey('insumo.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    funcionarios = db.relationship('Funcionario', backref='funcao_ref', lazy=True)
    insumo = db.relationship('Insumo', foreign_keys=[insumo_id])

class HorarioTrabalho(db.Model):
    """
    Modelo "molde" de horário de trabalho.
    Define um padrão de horário que pode ser associado a funcionários.
    Os detalhes por dia da semana são armazenados em HorarioDia.
    """
    __tablename__ = 'horario_trabalho'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # CAMPOS LEGADOS - mantidos temporariamente para compatibilidade
    # Serão removidos após migração completa
    entrada = db.Column(db.Time, nullable=True)
    saida_almoco = db.Column(db.Time, nullable=True)
    retorno_almoco = db.Column(db.Time, nullable=True)
    saida = db.Column(db.Time, nullable=True)
    dias_semana = db.Column(db.String(20), nullable=True)
    horas_diarias = db.Column(db.Float, default=8.0)
    valor_hora = db.Column(db.Float, default=12.0)
    
    # Relacionamento com HorarioDia (detalhes por dia da semana)
    dias = db.relationship('HorarioDia', backref='horario', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<HorarioTrabalho {self.nome}>'
    
    def get_horario_dia(self, dia_semana: int):
        """
        Retorna o HorarioDia para um dia específico da semana.
        dia_semana: 0=Segunda, 1=Terça, ..., 6=Domingo
        """
        return HorarioDia.query.filter_by(
            horario_id=self.id, 
            dia_semana=dia_semana
        ).first()
    
    def calcular_horas_contratuais_dia(self, dia_semana: int):
        """
        Calcula as horas contratuais para um dia específico.
        Retorna 0 se o dia não for dia de trabalho.
        """
        from decimal import Decimal
        horario_dia = self.get_horario_dia(dia_semana)
        
        if not horario_dia or not horario_dia.trabalha:
            return Decimal('0')
        
        if horario_dia.entrada and horario_dia.saida:
            from datetime import datetime, timedelta
            entrada_dt = datetime.combine(datetime.today(), horario_dia.entrada)
            saida_dt = datetime.combine(datetime.today(), horario_dia.saida)
            
            if saida_dt < entrada_dt:
                saida_dt += timedelta(days=1)
            
            diferenca = saida_dt - entrada_dt
            horas_brutas = Decimal(str(diferenca.total_seconds() / 3600))
            pausa = Decimal(str(horario_dia.pausa_horas or 1))
            
            return max(horas_brutas - pausa, Decimal('0'))
        
        return Decimal('0')


class HorarioDia(db.Model):
    """
    Detalha o horário de trabalho para cada dia da semana.
    Permite configurar horários diferentes para cada dia (ex: sexta mais curta).
    """
    __tablename__ = 'horario_dia'
    
    id = db.Column(db.Integer, primary_key=True)
    horario_id = db.Column(db.Integer, db.ForeignKey('horario_trabalho.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=Segunda, 1=Terça, ..., 6=Domingo
    entrada = db.Column(db.Time, nullable=True)
    saida = db.Column(db.Time, nullable=True)
    pausa_horas = db.Column(db.Numeric(4, 2), default=1.0)  # Tempo de almoço/pausa em horas
    trabalha = db.Column(db.Boolean, default=True)  # Se é dia de trabalho
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # Multi-tenant
    
    # Constraint única para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('horario_id', 'dia_semana', name='uk_horario_dia'),
    )
    
    def __repr__(self):
        dias_nomes = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        nome_dia = dias_nomes[self.dia_semana] if 0 <= self.dia_semana <= 6 else 'Inválido'
        return f'<HorarioDia {nome_dia} {self.entrada}-{self.saida}>'
    
    def calcular_horas(self):
        """Calcula as horas de trabalho deste dia."""
        from decimal import Decimal
        from datetime import datetime, timedelta
        
        if not self.trabalha or not self.entrada or not self.saida:
            return Decimal('0')
        
        entrada_dt = datetime.combine(datetime.today(), self.entrada)
        saida_dt = datetime.combine(datetime.today(), self.saida)
        
        if saida_dt < entrada_dt:
            saida_dt += timedelta(days=1)
        
        diferenca = saida_dt - entrada_dt
        horas_brutas = Decimal(str(diferenca.total_seconds() / 3600))
        pausa = Decimal(str(self.pausa_horas or 1))
        
        return max(horas_brutas - pausa, Decimal('0'))

class Funcionario(db.Model):
    __table_args__ = (
        db.UniqueConstraint('codigo', 'admin_id', name='uq_funcionario_codigo_admin_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), nullable=False)  # VV001, VV002, etc. — único por tenant
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    rg = db.Column(db.String(20))
    data_nascimento = db.Column(db.Date)
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    data_admissao = db.Column(db.Date, nullable=False)
    salario = db.Column(db.Float, default=0.0)
    jornada_semanal = db.Column(db.Integer, default=44)
    ativo = db.Column(db.Boolean, default=True)
    foto = db.Column(db.String(255))  # Caminho para o arquivo de foto
    foto_base64 = db.Column(db.Text)  # Foto em base64 para persistência completa (mantido por compatibilidade)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))
    funcao_id = db.Column(db.Integer, db.ForeignKey('funcao.id'))
    horario_trabalho_id = db.Column(db.Integer, db.ForeignKey('horario_trabalho.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # V2: Tipo de remuneração — 'salario' (padrão V1) ou 'diaria' (V2)
    tipo_remuneracao = db.Column(db.String(20), default='salario', nullable=False)
    valor_diaria = db.Column(db.Float, default=0.0)
    # V2: Dados de pagamento e benefícios
    chave_pix = db.Column(db.String(150))       # Chave PIX: CPF, e-mail, telefone ou aleatória
    valor_va  = db.Column(db.Float, default=0.0)  # Vale Alimentação por dia trabalhado (R$)
    valor_vt  = db.Column(db.Float, default=0.0)  # Vale Transporte por dia trabalhado (R$)
    
    # Relacionamentos
    horario_trabalho = db.relationship('HorarioTrabalho', backref=db.backref('funcionarios', overlaps="horario_trabalho"), overlaps="funcionarios")
    registros_ponto = db.relationship('RegistroPonto', backref='funcionario_ref', lazy=True, overlaps="funcionario_ref")
    fotos_faciais = db.relationship('FotoFacialFuncionario', backref='funcionario', lazy=True, cascade='all, delete-orphan')


class FotoFacialFuncionario(db.Model):
    """
    Modelo para armazenar múltiplas fotos faciais de cada funcionário.
    Permite cadastrar fotos com/sem óculos, diferentes ângulos, etc.
    Melhora significativamente a precisão do reconhecimento facial.
    """
    __tablename__ = 'foto_facial_funcionario'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id', ondelete='CASCADE'), nullable=False)
    foto_base64 = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(100))  # Ex: "Com óculos", "Sem óculos", "Perfil esquerdo"
    ordem = db.Column(db.Integer, default=1)  # Ordem de prioridade (menor = principal)
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    def __repr__(self):
        return f'<FotoFacial {self.funcionario_id} - {self.descricao}>'

class Obra(db.Model):
    __table_args__ = (
        db.UniqueConstraint('codigo', 'admin_id', name='uq_obra_codigo_admin_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20))  # Código único da obra (único por tenant)
    endereco = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_previsao_fim = db.Column(db.Date)
    orcamento = db.Column(db.Float, default=0.0)
    valor_contrato = db.Column(db.Float, default=0.0)  # Valor do contrato para cálculo de margem
    fluxo_caixa_planilha = db.Column(db.JSON)  # snapshot verbatim da Planilha1 (fluxo_caixa_mensal)
    area_total_m2 = db.Column(db.Float, default=0.0)  # Área total da obra
    # Fase 0.6 / D5 — texto livre, mas com vocabulário canônico convergido na
    # escrita pelo @validates abaixo. Ver utils/status_obra.py.
    status = db.Column(db.String(20), default='Em andamento')

    # Fase 2 — estado canônico da obra. `status` (acima) e `ativo` (abaixo)
    # passam a ser DERIVADOS deste campo por write-through em
    # services/obra_estado. Quase nenhuma leitura de `status` precisou mudar:
    # ela continua recebendo os mesmos textos ('Em andamento', 'Concluída').
    # A exceção são os filtros do dashboard, que não reconheciam
    # 'Planejamento' — corrigidos junto com a Task 9, que introduz o valor.
    #
    # VARCHAR + CHECK em vez de ENUM nativo: ver docstring de EstadoObra.
    # O CHECK é criado pela migration 231, não pelo declarativo — o
    # SQLAlchemy criaria uma constraint sem nome estável, impossível de
    # dropar num rollback.
    estado = db.Column(
        db.String(20), nullable=False,
        default='planejamento', server_default='planejamento',
        index=True,
    )
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    
    # MÓDULO 2: Portal do Cliente - Campos Completos
    token_cliente = db.Column(db.String(255), unique=True)
    # Fase 3 — expiração do token do portal. Até 2026-07-21 o token não
    # expirava NUNCA: quem tivesse a URL mantinha acesso (e poder de POST)
    # para sempre, inclusive ex-cliente e link vazado em grupo de
    # mensagem. NULLABLE de propósito: token já emitido sem data continua
    # valendo até ser rotacionado, para que o deploy não derrube portal de
    # obra em andamento. O carimbo entra no `toggle_portal`.
    token_cliente_expira_em = db.Column(db.DateTime, nullable=True)
    # Task #176 — Cliente é vínculo único e obrigatório (FK NOT NULL). Os
    # antigos campos texto cliente_nome/email/telefone/cliente foram
    # removidos: a única fonte de verdade é o cadastro de Cliente.
    cliente_id = db.Column(
        db.Integer, db.ForeignKey('cliente.id'),
        nullable=False, index=True,
    )
    proposta_origem_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'))
    
    # Configurações do Portal
    portal_ativo = db.Column(db.Boolean, default=True)
    ultima_visualizacao_cliente = db.Column(db.DateTime)
    
    ativo = db.Column(db.Boolean, default=True)  # Campo para controle de obras ativas
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Medição Quinzenal
    data_inicio_medicao = db.Column(db.Date, nullable=True)
    valor_entrada = db.Column(db.Numeric(15, 2), default=0)
    data_entrada = db.Column(db.Date, nullable=True)

    # Task #70 — Percentual de administração para cálculo de custo fixo da obra
    percentual_administracao = db.Column(db.Numeric(5, 2), default=0, nullable=False)

    # Regime de medição/faturamento da obra:
    #   'fixa'       → fatura por marcos contratuais (MedicaoContrato, datas/% fixos).
    #   'percentual' → fatura pelo % físico das etapas apurado via RDO (MedicaoObra).
    #
    # O que esta coluna governa DE FATO (conferido em 2026-07-21): o modo de
    # apontamento padrão das tarefas criadas na obra. Com 'percentual',
    # `cronograma_views.criar_tarefa` grava `modo_apontamento='percentual'`
    # na tarefa nova quando o usuário não escolheu — faz sentido: se a obra
    # fatura pelo % físico, exigir quantitativo por tarefa é contraditório.
    # Escolha explícita do usuário sempre vence.
    #
    # O que esta coluna NÃO governa (o comentário anterior afirmava que sim,
    # e era falso): o vínculo custo↔tarefa. Nenhum código lia esta coluna
    # antes do plano `2026-07-21-cronograma-editavel-rdo-percentual.md`;
    # a única leitura era o teste de existência em
    # tests/test_importacao_fisico_financeiro.py:41. Tornar o vínculo
    # custo↔tarefa obrigatório em regime percentual é escopo da Fase 4
    # (centro de custo obrigatório).
    #
    # Ver spec 2026-06-27-custo-cronograma-fieis-regime-medicao e a
    # migration 201, que backfilla 'percentual' para obras com medição
    # física preexistente.
    regime_medicao = db.Column(db.String(20), default='fixa', nullable=False)

    # Task #200 — Revisão de cronograma na primeira entrada da obra.
    # NULL = obra ainda não passou pelo gate de revisão inicial; uma vez
    # preenchido, a obra abre direto nos detalhes (sem redirect para a
    # tela de revisão). Obras criadas com cronograma materializado a
    # partir de `propostas.cronograma_default_json` na hora da aprovação
    # já nascem com este campo setado.
    cronograma_revisado_em = db.Column(db.DateTime, nullable=True)

    # Campos de Geofencing (Cerca Virtual)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    raio_geofence_metros = db.Column(db.Integer, default=100)
    
    registros_ponto = db.relationship('RegistroPonto', backref='obra_ref', lazy=True, overlaps="obra_ref")
    custos = db.relationship('CustoObra', backref='obra_ref', lazy=True, overlaps="obra_ref")
    servicos_obra = db.relationship('ServicoObra', backref='obra', cascade='all, delete-orphan', lazy=True)
    servicos_reais = db.relationship('ServicoObraReal', backref='obra_real', cascade='all, delete-orphan', lazy=True)

    # Task #172 — relacionamento com Cliente cadastrado.
    # backref 'obras' permite Cliente.obras para listar todas as obras do cliente.
    cliente_ref = db.relationship('Cliente', foreign_keys=[cliente_id], backref='obras')

    # Fase 1 — `responsavel_id` existe desde sempre (models.py:258) mas
    # NUNCA teve relationship: `obra.responsavel` resolvia para Undefined
    # em templates/obras.html:266 e obra_form.html:449 (sempre "Sem
    # responsável") e estourava AttributeError na f-string de
    # relatorios_funcionais.py:217.
    responsavel = db.relationship('Funcionario', foreign_keys=[responsavel_id])

    # Fase 0.6 / D5 — convergência do vocabulário de status na ESCRITA.
    # O formulário oferecia 'Em Andamento' e a listagem filtrava por
    # 'Em andamento' com igualdade exata (views/obras.py:83): 53 obras
    # existiam e sumiam da tela. Normalizar aqui, e não em cada view, cobre
    # também event_manager.py, os seeds e os importadores.
    @validates('status')
    def _normalizar_status(self, _key, valor):
        from utils.status_obra import normalizar_status_obra
        return normalizar_status_obra(valor)

    # ── Task #176: properties simplificadas — apenas a FK Cliente é fonte de
    # verdade. Os antigos campos texto cliente_nome/email/telefone foram
    # removidos do schema; nada de fallback legado.

    @property
    def cliente_nome_efetivo(self):
        return (self.cliente_ref.nome or '') if self.cliente_ref is not None else ''

    @property
    def cliente_email_efetivo(self):
        return (self.cliente_ref.email or '') if self.cliente_ref is not None else ''

    @property
    def cliente_telefone_efetivo(self):
        return (self.cliente_ref.telefone or '') if self.cliente_ref is not None else ''


class ObraTransicaoEstado(db.Model):
    """Histórico de transições de estado da Obra — Fase 2.

    Molde: `CronogramaImportacaoEvento`, a única trilha de auditoria de
    máquina de estados que já existia no sistema. Mesma forma: FK para o
    agregado, tenant desnormalizado, `detalhes` em JSON livre, `usuario_id`
    nullable (transição feita por migração ou por automação não tem usuário).

    `estado_de` é NULL apenas na linha de backfill escrita pela migration
    231, que registra o NASCIMENTO do estado derivado do texto legado — não
    é transição, é origem. Essa linha carrega, no `motivo`, o valor VERBATIM
    de `Obra.status` e de `Obra.ativo` antes da migração; é o que torna a
    migration 232 reversível a partir do próprio banco.
    """
    __tablename__ = 'obra_transicao_estado'
    __table_args__ = (
        db.Index('ix_obra_transicao_obra_criado', 'obra_id', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(
        db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    admin_id = db.Column(
        db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True,
    )
    # Guardamos o `.value` do EstadoObra, não o Enum: a coluna precisa ser
    # legível por SQL cru nas migrações e nos relatórios de censo.
    estado_de = db.Column(db.String(20), nullable=True)
    estado_para = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.Text, nullable=True)
    detalhes = db.Column(db.JSON, nullable=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey('usuario.id'), nullable=True,
    )
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    obra = db.relationship(
        'Obra', foreign_keys=[obra_id],
        backref=db.backref('transicoes', lazy='select',
                           order_by='ObraTransicaoEstado.criado_em',
                           cascade='all, delete-orphan'),
    )

    def __repr__(self):
        return (f'<ObraTransicaoEstado obra={self.obra_id} '
                f'{self.estado_de}→{self.estado_para}>')


class UsuarioObra(db.Model):
    """Vínculo usuário ↔ obra — o segundo eixo de autorização (Fase 1).

    Antes desta tabela o sistema tinha um eixo só: `admin_id`. Qualquer
    usuário autenticado de um tenant alcançava todas as obras dele. As
    tabelas que pareciam vínculo não eram: `FuncionarioObrasPonto`
    (models.py:605) governa um DROPDOWN de ponto e falha ABERTA — sem
    configuração, `ponto_views.py:674` devolve todas as obras do tenant;
    `AlocacaoEquipe` (models.py:1522) é planejamento diário.

    Chaveada por `usuario_id` (não `funcionario_id`) porque autorização
    é sobre quem loga. Quem é a pessoa por trás do login é a FK
    `Usuario.funcionario_id`, resolvida em utils/identidade.py.
    """
    __tablename__ = 'usuario_obra'
    __table_args__ = (
        db.UniqueConstraint('usuario_id', 'obra_id', name='uq_usuario_obra'),
        db.Index('ix_usuario_obra_usuario_ativo', 'usuario_id', 'ativo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    # `native_enum=False` — DESVIO DELIBERADO do plano da Fase 1, que
    # declarava `db.Enum(PapelObra)` enquanto a migration 215 cria
    # `papel VARCHAR(20)`. Este schema usa enums NATIVOS do Postgres
    # (`usuario.tipo_usuario` é do tipo `tipousuario`), então o padrão
    # `native_enum=True` faria o `create_all()` do startup tentar criar
    # um tipo `papelobra` que a migration não cria — modelo e migration
    # descrevendo coisas diferentes. VARCHAR também é o que permite
    # acrescentar COMPRADOR na Fase 3 sem ALTER TYPE.
    papel = db.Column(db.Enum(PapelObra, native_enum=False, length=20),
                      nullable=False, default=PapelObra.LEITOR)
    # admin_id redundante com obra.admin_id, mas presente por consistência
    # com o resto do schema e para permitir filtro de tenant sem join.
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id],
                              backref=db.backref('obras_vinculadas', lazy='dynamic'))
    obra = db.relationship('Obra', foreign_keys=[obra_id],
                           backref=db.backref('usuarios_vinculados', lazy='dynamic'))

    def __repr__(self):
        return f'<UsuarioObra u={self.usuario_id} o={self.obra_id} {self.papel.value}>'


class ServicoObra(db.Model):
    """Relacionamento ORIGINAL - Serviços das Propostas vinculados às Obras (MANTIDO PARA COMPATIBILIDADE)"""
    __tablename__ = 'servico_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    quantidade_planejada = db.Column(db.Numeric(10, 4), nullable=False)  # Quantidade total planejada
    quantidade_executada = db.Column(db.Numeric(10, 4), default=0.0)  # Quantidade já executada
    observacoes = db.Column(db.Text)  # Observações específicas para este serviço na obra
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('obra_id', 'servico_id', name='_obra_servico_uc'),)

class ServicoObraReal(db.Model):
    """NOVA TABELA - Gestão completa dos serviços reais executados na obra com controle avançado"""
    __tablename__ = 'servico_obra_real'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    
    # Planejamento detalhado
    quantidade_planejada = db.Column(db.Numeric(12, 4), nullable=False, default=0.0)
    quantidade_executada = db.Column(db.Numeric(12, 4), default=0.0)
    percentual_concluido = db.Column(db.Numeric(5, 2), default=0.0)  # 0.00 a 100.00%
    
    # Controle de prazo
    data_inicio_planejada = db.Column(db.Date)
    data_fim_planejada = db.Column(db.Date)
    data_inicio_real = db.Column(db.Date)
    data_fim_real = db.Column(db.Date)
    
    # Controle de custos
    valor_unitario = db.Column(db.Numeric(10, 2), default=0.0)
    valor_total_planejado = db.Column(db.Numeric(12, 2), default=0.0)
    valor_total_executado = db.Column(db.Numeric(12, 2), default=0.0)
    
    # Status e controle
    status = db.Column(db.String(30), default='Não Iniciado')  # Não Iniciado, Em Andamento, Concluído, Pausado
    prioridade = db.Column(db.Integer, default=3)  # 1=Alta, 2=Média, 3=Baixa
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))  # Funcionário responsável
    
    # Observações e notas
    observacoes = db.Column(db.Text)
    notas_tecnicas = db.Column(db.Text)  # Para detalhes técnicos específicos
    
    # Controle de qualidade
    aprovado = db.Column(db.Boolean, default=False)
    data_aprovacao = db.Column(db.DateTime)
    aprovado_por_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    
    # Multi-tenant e controle
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', foreign_keys=[servico_id], backref='servicos_obra_real', lazy=True)
    responsavel = db.relationship('Funcionario', foreign_keys=[responsavel_id], backref='servicos_responsavel_real', lazy=True)
    aprovado_por = db.relationship('Funcionario', foreign_keys=[aprovado_por_id], backref='servicos_aprovados_real', lazy=True)
    admin = db.relationship('Usuario', backref='servicos_obra_real_criados', lazy=True)
    
    # Unique constraint para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('obra_id', 'servico_id', name='_servico_obra_real_uc'),)




class CategoriaServico(db.Model):
    """Categorias para classificação de serviços"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    cor = db.Column(db.String(7), default='#6c757d')  # Cor hex para identificação visual
    icone = db.Column(db.String(50), default='fas fa-wrench')  # Ícone FontAwesome
    ordem = db.Column(db.Integer, default=0)  # Para ordenação
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Multi-tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos removidos - usar campo categoria string no Servico

class Servico(db.Model):
    """Serviços para coleta de dados reais via RDO - SIGE v6.3"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(50), nullable=False)  # Campo string principal
    unidade_medida = db.Column(db.String(10), nullable=False)  # m2, m3, kg, ton, un, m, h
    unidade_simbolo = db.Column(db.String(10))  # Símbolo da unidade para exibição
    custo_unitario = db.Column(db.Float, default=0.0)  # Custo unitário do serviço
    complexidade = db.Column(db.Integer, default=3)  # 1-5 para análise futura
    requer_especializacao = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    # Task #82 — Orçamento paramétrico
    imposto_pct = db.Column(db.Numeric(5, 2), nullable=True)
    margem_lucro_pct = db.Column(db.Numeric(5, 2), nullable=True)
    preco_venda_unitario = db.Column(db.Numeric(15, 2), default=0)
    # Task #102 — Template padrão de cronograma (usado na aprovação da proposta)
    template_padrao_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_template.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    template_padrao = db.relationship('CronogramaTemplate', foreign_keys=[template_padrao_id])
    # Task #36 — tipo de medição do serviço (nullable = derivar dos insumos da composição)
    tipo_medicao = db.Column(db.String(30), nullable=True)
    # Multi-tenant obrigatório
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    # Removido: subatividades obsoletas - agora usamos SubatividadeMestre
    historico_produtividade = db.relationship('HistoricoProdutividadeServico', backref='servico', lazy=True)
    composicoes = db.relationship('ComposicaoServico', backref='servico', cascade='all, delete-orphan', lazy=True)

    @property
    def tipo_medicao_efetivo(self):
        """Task #36: retorna tipo_medicao próprio ou deriva do mais frequente entre os insumos."""
        if self.tipo_medicao:
            return self.tipo_medicao
        try:
            from collections import Counter
            tipos = [
                c.insumo.tipo_medicao
                for c in (self.composicoes or [])
                if c.insumo and getattr(c.insumo, 'tipo_medicao', None)
            ]
            if tipos:
                return Counter(tipos).most_common(1)[0][0]
        except Exception:
            pass
        return 'UNITARIO'

    servicos_obra = db.relationship('ServicoObra', backref='servico', lazy=True)
    servicos_reais = db.relationship('ServicoObraReal', backref='servico_real', lazy=True)
    admin = db.relationship('Usuario', backref='servicos_criados')

# Removido: SubAtividade - substituído por SubatividadeMestre

class HistoricoProdutividadeServico(db.Model):
    """Histórico de produtividade coletado via RDO"""
    __tablename__ = 'historico_produtividade_servico'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    # Removido: referência à tabela obsoleta sub_atividade
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    data_execucao = db.Column(db.Date, nullable=False)
    quantidade_executada = db.Column(db.Numeric(10, 4), nullable=False)
    tempo_execucao_horas = db.Column(db.Numeric(8, 2), nullable=False)
    custo_mao_obra_real = db.Column(db.Numeric(10, 2), nullable=False)  # calculado automaticamente
    produtividade_hora = db.Column(db.Numeric(8, 4), nullable=False)  # quantidade/hora
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='historico_produtividade', lazy=True)
    funcionario = db.relationship('Funcionario', backref='historico_produtividade', lazy=True)

class RegistroPonto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))  # MÓDULO 3: Campo para obras
    data = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time)
    hora_saida = db.Column(db.Time)
    hora_almoco_saida = db.Column(db.Time)
    hora_almoco_retorno = db.Column(db.Time)
    
    # MÓDULO 3: Campo tipo_local para integração com gestão de equipes
    tipo_local = db.Column(db.String(20), default='oficina')  # 'oficina', 'campo'
    
    # Cálculos automáticos conforme especificação
    horas_trabalhadas = db.Column(db.Float, default=0.0)
    horas_extras = db.Column(db.Float, default=0.0)
    minutos_atraso_entrada = db.Column(db.Integer, default=0)  # entrada após horário
    minutos_atraso_saida = db.Column(db.Integer, default=0)    # saída antes do horário
    total_atraso_minutos = db.Column(db.Integer, default=0)    # soma dos atrasos
    total_atraso_horas = db.Column(db.Float, default=0.0)      # atrasos em horas
    
    # Campos adicionais
    meio_periodo = db.Column(db.Boolean, default=False)
    saida_antecipada = db.Column(db.Boolean, default=False)
    tipo_registro = db.Column(db.String(30), default='trabalhado')  # trabalhado, falta, falta_justificada, feriado, feriado_trabalhado, sabado_horas_extras, domingo_horas_extras
    percentual_extras = db.Column(db.Float, default=0.0)  # percentual de horas extras configurável
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Campos para reconhecimento facial
    foto_registro_base64 = db.Column(db.Text)  # Foto em base64 capturada no momento do registro
    reconhecimento_facial_sucesso = db.Column(db.Boolean, default=False)  # True se reconhecimento foi bem-sucedido
    confianca_reconhecimento = db.Column(db.Float)  # Distância facial (quanto menor, mais confiável)
    modelo_utilizado = db.Column(db.String(50), default='VGG-Face')  # Modelo DeepFace utilizado
    
    # Campos de Geolocalização (Geofencing)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    distancia_obra_metros = db.Column(db.Float, nullable=True)
    
    # Relacionamentos são definidos via backref nos modelos principais
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_registro_ponto_funcionario_data', 'funcionario_id', 'data'),
        db.Index('idx_registro_ponto_obra_data', 'obra_id', 'data'),
        db.Index('idx_registro_ponto_admin_data', 'admin_id', 'data'),
    )

class ConfiguracaoHorario(db.Model):
    """Configuração de horários padrão por obra"""
    __tablename__ = 'configuracao_horario'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))  # Opcional: configuração específica por funcionário
    
    # Horários padrão
    entrada_padrao = db.Column(db.Time, default=time(8, 0))      # 08:00
    saida_padrao = db.Column(db.Time, default=time(17, 0))       # 17:00
    almoco_inicio = db.Column(db.Time, default=time(12, 0))      # 12:00
    almoco_fim = db.Column(db.Time, default=time(13, 0))         # 13:00
    
    # Configurações
    tolerancia_atraso = db.Column(db.Integer, default=15)        # 15 minutos
    carga_horaria_diaria = db.Column(db.Integer, default=480)    # 8 horas em minutos
    
    # Controle multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='configuracoes_horario')
    funcionario = db.relationship('Funcionario', backref='configuracao_horario_individual')

class DispositivoObra(db.Model):
    """Registro de dispositivos autorizados por obra para ponto eletrônico compartilhado"""
    __tablename__ = 'dispositivo_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    nome_dispositivo = db.Column(db.String(100), nullable=False)  # "Tablet Obra A"
    identificador = db.Column(db.String(200))  # User-agent ou fingerprint
    ultimo_acesso = db.Column(db.DateTime)
    ativo = db.Column(db.Boolean, default=True)
    
    # Localização GPS do dispositivo
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Controle multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento
    obra = db.relationship('Obra', backref='dispositivos_autorizados')

class FuncionarioObrasPonto(db.Model):
    """Configuração de quais obras aparecem no dropdown para cada funcionário bater ponto"""
    __tablename__ = 'funcionario_obras_ponto'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='obras_ponto_disponiveis')
    obra = db.relationship('Obra', backref='funcionarios_autorizados')
    
    # Constraint única para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('funcionario_id', 'obra_id', 'admin_id', name='uq_funcionario_obra_admin'),
    )

# Novos modelos conforme especificação v3.0
class TipoOcorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(50), unique=True, nullable=False)  # Atestado Médico, Atraso Justificado, etc.
    descricao = db.Column(db.Text)
    requer_documento = db.Column(db.Boolean, default=False)
    afeta_custo = db.Column(db.Boolean, default=False)  # se deve ser incluído no custo mensal
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ocorrencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo_ocorrencia_id = db.Column(db.Integer, db.ForeignKey('tipo_ocorrencia.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pendente')  # Pendente, Aprovado, Rejeitado
    descricao = db.Column(db.Text)
    documento_anexo = db.Column(db.String(500))  # caminho para arquivo anexo
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_aprovacao = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='ocorrencias', lazy=True, overlaps="ocorrencias")
    tipo_ocorrencia = db.relationship('TipoOcorrencia', backref='ocorrencias', lazy=True, overlaps="ocorrencias")
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por], backref='ocorrencias_aprovadas', lazy=True, overlaps="ocorrencias_aprovadas")

# ===== MÓDULO 3: GESTÃO DE EQUIPES - SISTEMAS KANBAN/CALENDÁRIO =====

class CalendarioUtil(db.Model):
    data = db.Column(db.Date, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    dia_semana = db.Column(db.Integer)  # 1=Segunda, 7=Domingo
    eh_util = db.Column(db.Boolean, default=True)
    eh_feriado = db.Column(db.Boolean, default=False)
    descricao_feriado = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustoObra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    tipo = db.Column(db.String(20), nullable=False)  # 'mao_obra', 'material', 'servico', 'veiculo', 'alimentacao'
    # Task #7: ampliado de 200 para 500 chars — RDOs com muitas
    # subatividades por funcionário ultrapassavam 200 e disparavam
    # StringDataRightTruncation, perdendo o lançamento de custo.
    descricao = db.Column(db.String(500), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Campos adicionados pela Migração 43 para integração completa
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    item_almoxarifado_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'))
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    quantidade = db.Column(db.Numeric(10, 2), default=1)
    valor_unitario = db.Column(db.Numeric(10, 2), default=0)
    horas_trabalhadas = db.Column(db.Numeric(5, 2))
    horas_extras = db.Column(db.Numeric(5, 2))
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    categoria = db.Column(db.String(50))
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="custos,obra_ref")
    centro_custo_ref = db.relationship('CentroCusto', backref='custos')
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id])
    veiculo = db.relationship('Vehicle', foreign_keys=[veiculo_id])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # [OK] OTIMIZAÇÃO: Índices compostos para queries frequentes
    __table_args__ = (
        db.Index('idx_custo_admin_data', 'admin_id', 'data'),  # Filtros por período
        db.Index('idx_custo_obra_tipo', 'obra_id', 'tipo'),     # Filtros por obra e tipo
    )

# Novos modelos para Gestão Financeira Avançada

class CentroCusto(db.Model):
    """Centros de custo para classificação financeira"""
    __tablename__ = 'centro_custo'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)  # CC001, CC002, etc.
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String(20), nullable=False)  # 'obra', 'departamento', 'projeto', 'atividade'
    ativo = db.Column(db.Boolean, default=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))  # Associação opcional com obra
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'))  # Associação opcional com departamento
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="centros_custo_lista")
    departamento = db.relationship('Departamento', overlaps="centros_custo_lista")

class Receita(db.Model):
    """Registro de receitas da empresa"""
    __tablename__ = 'receita'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    numero_receita = db.Column(db.String(20), unique=True, nullable=False)  # REC001, REC002, etc.
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    origem = db.Column(db.String(50), nullable=False)  # 'obra', 'servico', 'venda', 'outros'
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_receita = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)  # Data real do recebimento
    status = db.Column(db.String(20), default='Pendente')  # 'Pendente', 'Recebido', 'Cancelado'
    forma_recebimento = db.Column(db.String(30))  # 'Dinheiro', 'Transferência', 'Cartão', 'Cheque'
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="receitas_lista")
    centro_custo = db.relationship('CentroCusto', overlaps="receitas_lista")

class OrcamentoObra(db.Model):
    """Orçamento planejado vs. realizado por obra"""
    __tablename__ = 'orcamento_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    categoria = db.Column(db.String(30), nullable=False)  # 'mao_obra', 'material', 'equipamento', 'outros'
    orcamento_planejado = db.Column(db.Float, nullable=False, default=0.0)
    custo_realizado = db.Column(db.Float, default=0.0)
    receita_planejada = db.Column(db.Float, default=0.0)
    receita_realizada = db.Column(db.Float, default=0.0)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', overlaps="orcamentos_lista")
    
    @property
    def desvio_custo(self):
        """Calcula o desvio percentual do custo"""
        if self.orcamento_planejado > 0:
            return ((self.custo_realizado - self.orcamento_planejado) / self.orcamento_planejado) * 100
        return 0.0
    
    @property
    def desvio_receita(self):
        """Calcula o desvio percentual da receita"""
        if self.receita_planejada > 0:
            return ((self.receita_realizada - self.receita_planejada) / self.receita_planejada) * 100
        return 0.0

class FluxoCaixa(db.Model):
    """Movimentações de fluxo de caixa consolidadas"""
    __tablename__ = 'fluxo_caixa'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_movimento = db.Column(db.Date, nullable=False)
    tipo_movimento = db.Column(db.String(10), nullable=False)  # 'ENTRADA', 'SAIDA'
    categoria = db.Column(db.String(30), nullable=False)  # 'receita', 'custo_obra', 'custo_veiculo', 'alimentacao', 'salario'
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'))
    referencia_id = db.Column(db.Integer)  # ID da tabela de origem (receita, custo_obra, etc.)
    referencia_tabela = db.Column(db.String(30))  # Nome da tabela de origem
    observacoes = db.Column(db.Text)
    import_batch_id = db.Column(db.String(50), nullable=True)
    banco_id = db.Column(db.Integer, db.ForeignKey('banco_empresa.id'), nullable=True)
    categoria_fluxo_caixa_id = db.Column(db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Task #57 — destinatário da saída (fornecedor ou funcionário vinculado na importação)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)

    # Relacionamentos
    obra = db.relationship('Obra', overlaps="movimentos_caixa_lista")
    centro_custo = db.relationship('CentroCusto', overlaps="movimentos_caixa_lista")
    banco = db.relationship('BancoEmpresa', foreign_keys=[banco_id], overlaps="fluxos_caixa")
    categoria_fluxo_caixa = db.relationship('CategoriaFluxoCaixa', foreign_keys=[categoria_fluxo_caixa_id])
    fornecedor_ref = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
    funcionario_ref = db.relationship('Funcionario', foreign_keys=[funcionario_id])

class RegistroAlimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'))
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'cafe', 'almoco', 'jantar', 'lanche'
    valor = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario_ref = db.relationship('Funcionario', overlaps="registros_alimentacao")
    obra_ref = db.relationship('Obra', overlaps="registros_alimentacao") 
    restaurante_ref = db.relationship('Restaurante', overlaps="registros_alimentacao")

# Modelo removido - duplicata


class RDO(db.Model):
    __tablename__ = 'rdo'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_rdo = db.Column(db.String(20), unique=True, nullable=False)  # Auto-gerado
    data_relatorio = db.Column(db.Date, nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para isolamento multi-tenant
    
    # Condições climáticas padronizadas
    clima_geral = db.Column(db.String(50))  # Ensolarado, Nublado, Chuvoso, etc.
    temperatura_media = db.Column(db.String(10))  # "25°C"
    umidade_relativa = db.Column(db.Integer)  # 0-100%
    vento_velocidade = db.Column(db.String(20))  # "Fraco", "Moderado", "Forte"
    precipitacao = db.Column(db.String(20))  # "Sem chuva", "Garoa", "Chuva forte"
    condicoes_trabalho = db.Column(db.String(50))  # "Ideais", "Adequadas", "Limitadas", "Inadequadas"
    observacoes_climaticas = db.Column(db.Text)
    
    # Local de trabalho
    local = db.Column(db.String(20), default='Campo')  # "Campo" ou "Oficina"
    
    # Comentários gerais
    comentario_geral = db.Column(db.Text)
    
    # Status e controle
    status = db.Column(db.String(20), default='Finalizado')  # Task #12: RDO sempre Finalizado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref=db.backref('rdos', cascade='all, delete-orphan', passive_deletes=True), overlaps="rdos")
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id], backref='rdos_criados', overlaps="rdos_criados")
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='rdos_admin', overlaps="rdos_admin")
    mao_obra = db.relationship('RDOMaoObra', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    equipamentos = db.relationship('RDOEquipamento', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    # Removido: atividades obsoletas - agora usamos servico_subatividades
    ocorrencias_rdo = db.relationship('RDOOcorrencia', backref='rdo_ref', cascade='all, delete-orphan', overlaps="rdo_ref")
    # fotos - definido em RDOFoto com backref (linha ~743)
    
    def __repr__(self):
        return f'<RDO {self.numero_rdo}>'
    
    @property
    def progresso_geral(self):
        """Calcula progresso geral baseado nas atividades"""
        if not self.atividades:
            return 0
        return round(sum(a.percentual_conclusao for a in self.atividades) / len(self.atividades), 2)
    
    @property
    def total_horas_trabalhadas(self):
        """Calcula total de horas trabalhadas no RDO"""
        return sum(m.horas_trabalhadas for m in self.mao_obra)
    
    @property
    def total_funcionarios(self):
        """Conta funcionários únicos no RDO"""
        return len(set(m.funcionario_id for m in self.mao_obra))
    
    def validar_rdo_unico_por_dia(self):
        """Valida se já existe outro RDO para a mesma obra/data"""
        rdo_existente = RDO.query.filter(
            RDO.obra_id == self.obra_id,
            RDO.data_relatorio == self.data_relatorio,
            RDO.id != self.id if self.id else True
        ).first()
        return rdo_existente is None, rdo_existente
    
    def gerar_numero_rdo(self):
        """Gera número único para RDO"""
        if not self.numero_rdo:
            ano = self.data_relatorio.year
            count = db.session.query(func.count(RDO.id)).filter(
                func.extract('year', RDO.data_relatorio) == ano,
                RDO.obra_id == self.obra_id
            ).scalar() or 0
            self.numero_rdo = f"RDO-{ano}-{count + 1:03d}"
    
    def __repr__(self):
        return f'<RDO {self.numero_rdo}>'


class RDOMaoObra(db.Model):
    __tablename__ = 'rdo_mao_obra'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    funcao_exercida = db.Column(db.String(100), nullable=False)
    horas_trabalhadas = db.Column(db.Float, nullable=False)
    # Task #5 — coluna horas_extras removida do RDO. Hora extra continua
    # apenas no Ponto Eletrônico/Folha de Pagamento.
    subatividade_id = db.Column(db.Integer, db.ForeignKey('rdo_servico_subatividade.id', ondelete='CASCADE'), nullable=True)
    tarefa_cronograma_id = db.Column(db.Integer, db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'), nullable=True)

    # Task #62 — vínculo automático Funcao→ComposicaoServico (preenchido
    # no salvamento do RDO via services.vinculo_mao_obra).
    composicao_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('composicao_servico.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    # Status do auto-vínculo: 'auto', 'manual', 'ambiguo', 'sem_funcao',
    # 'funcao_fora_composicao', 'subatividade_sem_composicoes'.
    vinculo_status = db.Column(db.String(40), nullable=True, index=True)

    # Produtividade V2 (migration #97)
    produtividade_real = db.Column(db.Float, nullable=True)
    indice_produtividade = db.Column(db.Float, nullable=True)

    # Task #38 — peso da tarefa principal do funcionário (pontos
    # percentuais 0..100). Quando definido em ao menos uma linha do
    # mesmo funcionário/dia, o helper utils.rdo_horas distribui as
    # horas de jornada-base proporcionalmente em vez da divisão igual.
    peso_distribuicao = db.Column(db.Integer, nullable=True)

    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='rdos_mao_obra', overlaps="rdos_mao_obra")
    subatividade = db.relationship('RDOServicoSubatividade', backref='mao_obra_registros', foreign_keys=[subatividade_id])
    tarefa_cronograma = db.relationship('TarefaCronograma', backref='mao_obra_registros', foreign_keys=[tarefa_cronograma_id])
    
    # Compatibilidade com código legado
    @property
    def funcao(self):
        return self.funcao_exercida
    
    @funcao.setter
    def funcao(self, value):
        self.funcao_exercida = value


class RDOCustoDiario(db.Model):
    """Custo diário de mão-de-obra por funcionário, persistido no salvamento do RDO.

    Garante imutabilidade histórica (mudança de salário não afeta registros
    antigos), elimina dupla contagem quando o funcionário aparece em vários
    RDOs no mesmo dia e fornece dados rápidos para as métricas de
    produtividade (Task #3).

    tipo_lancamento:
      'rdo'           — gerado a partir de um RDO salvo/editado
      'ocioso_mensal' — criado pelo job de cobertura para dias úteis sem RDO
                        de mensalistas
    """
    __tablename__ = 'rdo_custo_diario'

    id                         = db.Column(db.Integer, primary_key=True)
    rdo_id                     = db.Column(
        db.Integer, db.ForeignKey('rdo.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    funcionario_id             = db.Column(
        db.Integer, db.ForeignKey('funcionario.id', ondelete='CASCADE'),
        nullable=False,
    )
    admin_id                   = db.Column(
        db.Integer, db.ForeignKey('usuario.id'), nullable=False,
    )
    data                       = db.Column(db.Date, nullable=False)
    tipo_remuneracao_snapshot  = db.Column(db.String(20), nullable=False)
    componente_folha           = db.Column(db.Numeric(12, 2), default=0)
    componente_va              = db.Column(db.Numeric(12, 2), default=0)
    componente_vt              = db.Column(db.Numeric(12, 2), default=0)
    componente_extra           = db.Column(db.Numeric(12, 2), default=0)
    custo_total_dia            = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    horas_normais              = db.Column(db.Float, default=0.0)
    horas_extras               = db.Column(db.Float, default=0.0)
    custo_hora_normal          = db.Column(db.Numeric(12, 4), nullable=True)
    dias_uteis_mes_referencia  = db.Column(db.Integer, nullable=True)
    tipo_lancamento            = db.Column(db.String(20), nullable=False, default='rdo')
    retroativo                 = db.Column(db.Boolean, default=False)
    created_at                 = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at                 = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    rdo         = db.relationship('RDO', backref=db.backref('custos_diarios', lazy='dynamic'))
    funcionario = db.relationship('Funcionario', backref=db.backref('custos_diarios', lazy='dynamic'))

    __table_args__ = (
        db.Index(
            'uq_rdo_custo_rdo_func',
            'rdo_id', 'funcionario_id', 'data',
            unique=True,
            postgresql_where=db.text("rdo_id IS NOT NULL"),
        ),
        db.Index(
            'uq_rdo_custo_ocioso_func_data',
            'funcionario_id', 'data',
            unique=True,
            postgresql_where=db.text("tipo_lancamento = 'ocioso_mensal'"),
        ),
        db.Index('idx_rdo_custo_func_data', 'funcionario_id', 'data'),
        db.Index('idx_rdo_custo_admin_data', 'admin_id', 'data'),
    )

    def __repr__(self):
        return (
            f'<RDOCustoDiario func={self.funcionario_id} '
            f'data={self.data} total={self.custo_total_dia} '
            f'tipo={self.tipo_lancamento}>'
        )


class RDOEquipamento(db.Model):
    __tablename__ = 'rdo_equipamento'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False)
    nome_equipamento = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    horas_uso = db.Column(db.Float, nullable=False)
    estado_conservacao = db.Column(db.String(50), nullable=False)


# Removido: RDOAtividade - substituído por RDOServicoSubatividade


class RDOOcorrencia(db.Model):
    __tablename__ = 'rdo_ocorrencia'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False)
    tipo_ocorrencia = db.Column(db.String(50), nullable=False)  # "Problema", "Observação", "Melhoria", "Segurança"
    severidade = db.Column(db.String(20), default='Baixa')  # "Baixa", "Média", "Alta", "Crítica"
    descricao_ocorrencia = db.Column(db.Text, nullable=False)
    problemas_identificados = db.Column(db.Text)
    acoes_corretivas = db.Column(db.Text)
    responsavel_acao = db.Column(db.String(100))  # Quem deve resolver
    prazo_resolucao = db.Column(db.Date)  # Prazo para resolver
    status_resolucao = db.Column(db.String(20), default='Pendente')  # "Pendente", "Em Andamento", "Resolvido"
    observacoes_resolucao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class RDOFoto(db.Model):
    __tablename__ = 'rdo_foto'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # [OK] CORREÇÃO CRÍTICA: Campos legados são NOT NULL no banco de dados
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    legenda = db.Column(db.Text)
    
    # Novos campos (v9.0)
    descricao = db.Column(db.Text)
    arquivo_original = db.Column(db.String(500))
    arquivo_otimizado = db.Column(db.String(500))
    thumbnail = db.Column(db.String(500))
    nome_original = db.Column(db.String(255))
    tamanho_bytes = db.Column(db.BigInteger)
    ordem = db.Column(db.Integer, default=0)
    
    # [READY] ARMAZENAMENTO PERSISTENTE (v9.0.4) - Fotos em Base64 no banco de dados
    # Solução: Igual aos funcionários - fotos NUNCA são perdidas em deploy/restart
    imagem_original_base64 = db.Column(db.Text)  # Backup completo da imagem original
    imagem_otimizada_base64 = db.Column(db.Text)  # Versão otimizada (1200px) para visualização
    thumbnail_base64 = db.Column(db.Text)  # Miniatura (300px) para listagem rápida
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com RDO
    rdo = db.relationship('RDO', backref=db.backref('fotos', lazy='selectin', order_by='RDOFoto.ordem', cascade='all, delete-orphan', passive_deletes=True))


# ===== MÓDULO ALIMENTAÇÃO - Gestão de Refeições =====

class Restaurante(db.Model):
    """Modelo para restaurantes/fornecedores de alimentação"""
    __tablename__ = 'restaurante'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    razao_social = db.Column(db.String(200))
    cnpj = db.Column(db.String(18))
    pix = db.Column(db.String(100))
    nome_conta = db.Column(db.String(100))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    lancamentos = db.relationship('AlimentacaoLancamento', back_populates='restaurante', lazy='dynamic')
    registros_alimentacao = db.relationship('RegistroAlimentacao', lazy=True, overlaps="restaurante_ref")
    
    def __repr__(self):
        return f'<Restaurante {self.nome}>'


# Tabela de associação para relacionamento Many-to-Many entre AlimentacaoLancamento e Funcionario
# Inclui admin_id para multi-tenant (já existe no banco)
alimentacao_funcionarios_assoc = db.Table('alimentacao_funcionarios_assoc',
    db.Column('lancamento_id', db.Integer, db.ForeignKey('alimentacao_lancamento.id'), primary_key=True),
    db.Column('funcionario_id', db.Integer, db.ForeignKey('funcionario.id'), primary_key=True),
    db.Column('admin_id', db.Integer, db.ForeignKey('usuario.id'), nullable=False)
)


class AlimentacaoLancamento(db.Model):
    """Lançamentos de alimentação para controle de custos com refeições"""
    __tablename__ = 'alimentacao_lancamento'
    
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, index=True)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.Text)
    
    # Chaves Estrangeiras - padrão multi-tenant com admin_id NOT NULL
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Relacionamentos
    restaurante = db.relationship('Restaurante', back_populates='lancamentos')
    obra = db.relationship('Obra', backref='lancamentos_alimentacao')
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])
    
    # Many-to-Many com Funcionários
    funcionarios = db.relationship('Funcionario',
                                 secondary=alimentacao_funcionarios_assoc,
                                 backref=db.backref('lancamentos_alimentacao', lazy='dynamic'),
                                 lazy='selectin')
    
    @property
    def valor_por_funcionario(self):
        """Calcula o valor rateado por funcionário"""
        num_funcionarios = len(self.funcionarios)
        if not num_funcionarios or self.valor_total is None:
            return 0
        return self.valor_total / num_funcionarios


class AlimentacaoItem(db.Model):
    """Itens pré-cadastrados de alimentação (Marmita, Refrigerante, etc.)"""
    __tablename__ = 'alimentacao_item'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco_padrao = db.Column(db.Numeric(10, 2), default=0.0)
    descricao = db.Column(db.Text)
    icone = db.Column(db.String(50), default='fas fa-utensils')
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlimentacaoLancamentoItem(db.Model):
    """Itens de um lançamento de alimentação com quantidade e preço"""
    __tablename__ = 'alimentacao_lancamento_item'
    
    id = db.Column(db.Integer, primary_key=True)
    lancamento_id = db.Column(db.Integer, db.ForeignKey('alimentacao_lancamento.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('alimentacao_item.id'), nullable=True)
    
    nome_item = db.Column(db.String(100), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    # V2: detalhamento por funcionário e centro de custo
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'), nullable=True)

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lancamento = db.relationship('AlimentacaoLancamento', backref=db.backref('itens', lazy='selectin', cascade='all, delete-orphan'))
    item = db.relationship('AlimentacaoItem', backref='lancamento_itens')
    funcionario = db.relationship('Funcionario', backref='refeicoes_consumidas', foreign_keys=[funcionario_id])
    centro_custo = db.relationship('CentroCusto', backref='despesas_alimentacao', foreign_keys=[centro_custo_id])


class ManutencaoVeiculo(db.Model):
    """Registro de manutenções realizadas em veículos"""
    __tablename__ = 'manutencao_veiculo'

    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)

    data_manutencao = db.Column(db.Date, nullable=False)
    tipo_manutencao = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text)
    fornecedor = db.Column(db.String(200))
    valor = db.Column(db.Numeric(10, 2), default=0.0)
    km_veiculo = db.Column(db.Integer)
    proxima_manutencao_km = db.Column(db.Integer)
    proxima_manutencao_data = db.Column(db.Date)
    numero_nota_fiscal = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Concluída')
    observacoes = db.Column(db.Text)

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    veiculo = db.relationship('Veiculo', backref='manutencoes')
    admin = db.relationship('Usuario', backref='manutencoes_veiculo_admin')

    def __repr__(self):
        return f'<ManutencaoVeiculo {self.tipo_manutencao} - {self.data_manutencao}>'


class DocumentoFiscal(db.Model):
    """Controle de documentos fiscais relacionados a veículos"""
    __tablename__ = 'documento_fiscal'
    
    id = db.Column(db.Integer, primary_key=True)
    custo_veiculo_id = db.Column(db.Integer, db.ForeignKey('custo_veiculo.id'), nullable=True)
    manutencao_id = db.Column(db.Integer, db.ForeignKey('manutencao_veiculo.id'), nullable=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    
    # Dados do documento
    tipo_documento = db.Column(db.String(20), nullable=False)  # nf, nfce, recibo, cupom, outros
    numero_documento = db.Column(db.String(50), nullable=False)
    serie = db.Column(db.String(10))
    data_emissao = db.Column(db.Date, nullable=False)
    valor_documento = db.Column(db.Float, nullable=False)
    
    # Dados do emissor
    cnpj_emissor = db.Column(db.String(18))
    nome_emissor = db.Column(db.String(200), nullable=False)
    endereco_emissor = db.Column(db.Text)
    
    # Dados fiscais
    valor_icms = db.Column(db.Float, default=0.0)
    valor_pis = db.Column(db.Float, default=0.0)
    valor_cofins = db.Column(db.Float, default=0.0)
    valor_iss = db.Column(db.Float, default=0.0)
    valor_desconto = db.Column(db.Float, default=0.0)
    
    # Arquivo digitalizado
    arquivo_digitalizado = db.Column(db.String(500))  # Caminho para o arquivo
    arquivo_nome_original = db.Column(db.String(200))  # Nome original do arquivo
    arquivo_tamanho = db.Column(db.Integer)  # Tamanho em bytes
    
    # Controle e validação
    validado = db.Column(db.Boolean, default=False)
    validado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_validacao = db.Column(db.DateTime)
    observacoes_validacao = db.Column(db.Text)
    
    # Status contábil
    lancado_contabilidade = db.Column(db.Boolean, default=False)
    data_lancamento = db.Column(db.DateTime)
    numero_lancamento = db.Column(db.String(50))
    
    # Multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    custo_veiculo = db.relationship('CustoVeiculo', backref='documentos_fiscais', overlaps="documentos_fiscais")
    veiculo = db.relationship('Veiculo', backref='documentos_fiscais', overlaps="documentos_fiscais")
    validado_por = db.relationship('Usuario', foreign_keys=[validado_por_id], backref='documentos_validados')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='documentos_criados')
    
    @property
    def valor_impostos_total(self):
        """Calcula total de impostos"""
        return (self.valor_icms or 0) + (self.valor_pis or 0) + (self.valor_cofins or 0) + (self.valor_iss or 0)
    
    @property
    def valor_liquido(self):
        """Calcula valor líquido (valor total - descontos)"""
        return self.valor_documento - (self.valor_desconto or 0)
    
    @property
    def percentual_impostos(self):
        """Calcula percentual de impostos sobre o valor total"""
        if self.valor_documento > 0:
            return round((self.valor_impostos_total / self.valor_documento) * 100, 2)
        return 0
    
    def __repr__(self):
        return f'<DocumentoFiscal {self.tipo_documento} - {self.numero_documento} - R${self.valor_documento}>'


class OutroCusto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # 'vale_transporte', 'vale_alimentacao', 'desconto_vt', 'desconto_outras'
    categoria = db.Column(db.String(20), nullable=False)  # 'adicional' ou 'desconto'
    valor = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    percentual = db.Column(db.Float)  # Para descontos percentuais (ex: 6% do salário)
    
    # FUNCIONALIDADE MULTI-TENANT: admin_id para isolamento de dados
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Para compatibilidade, permitir NULL inicialmente
    
    # NOVA FUNCIONALIDADE: Associação com KPIs específicos
    kpi_associado = db.Column(db.String(30), default='outros_custos')  # 'custo_alimentacao', 'custo_transporte', 'outros_custos'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    funcionario = db.relationship('Funcionario', backref='outros_custos')
    obra = db.relationship('Obra', backref='outros_custos')
    admin = db.relationship('Usuario', backref='outros_custos_criados')
    
    def __repr__(self):
        return f'<OutroCusto {self.funcionario.nome} - {self.tipo} R$ {self.valor}>'

# ================================
# MÓDULO DE PROPOSTAS COMERCIAIS (MOVIDO PARA models_propostas.py)
# ================================
# As definições das classes Proposta e ServicoPropostaComercialSIGE
# foram movidas para models_propostas.py para evitar conflitos de importação

# ================================
# ENHANCED RDO SYSTEM - SUBATIVIDADES
# ================================

class RDOServicoSubatividade(db.Model):
    """
    Modelo compatível com a estrutura real do database
    """
    __tablename__ = 'rdo_servico_subatividade'
    
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=True)
    
    # Campos conforme estrutura real do database
    nome_subatividade = db.Column(db.String(255), nullable=False)
    descricao_subatividade = db.Column(db.Text)
    percentual_conclusao = db.Column(db.Float, default=0.0)
    percentual_anterior = db.Column(db.Float, default=0.0)
    incremento_dia = db.Column(db.Float, default=0.0)
    observacoes_tecnicas = db.Column(db.Text)
    ordem_execucao = db.Column(db.Integer)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, nullable=False)

    # Produtividade V2 (migration #96)
    subatividade_mestre_id = db.Column(db.Integer, db.ForeignKey('subatividade_mestre.id', ondelete='SET NULL'), nullable=True)
    quantidade_produzida = db.Column(db.Float, nullable=True)
    meta_produtividade_snapshot = db.Column(db.Float, nullable=True)
    unidade_medida_snapshot = db.Column(db.String(50), nullable=True)

    subatividade_mestre = db.relationship('SubatividadeMestre', backref='rdo_subatividades', foreign_keys=[subatividade_mestre_id])
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    rdo = db.relationship('RDO', backref=db.backref('servico_subatividades', cascade='all, delete-orphan', passive_deletes=True))
    servico = db.relationship('Servico', backref='rdo_subatividades')
    
    # Propriedades de compatibilidade
    @property
    def percentual(self):
        return self.percentual_conclusao
    
    @percentual.setter
    def percentual(self, value):
        self.percentual_conclusao = value
    
    @property
    def observacoes(self):
        return self.observacoes_tecnicas
    
    @observacoes.setter
    def observacoes(self, value):
        self.observacoes_tecnicas = value
    
    def __repr__(self):
        return f'<RDOServicoSubatividade RDO:{self.rdo_id} Servico:{self.servico_id} - {self.percentual_conclusao}%>'


from sqlalchemy import event as _sa_event

@_sa_event.listens_for(RDOServicoSubatividade, 'before_insert')
@_sa_event.listens_for(RDOServicoSubatividade, 'before_update')
def _auto_fill_produtividade_snapshot(mapper, connection, target):
    """Garante que os campos de snapshot são copiados do catálogo sempre que subatividade_mestre_id é definido."""
    if target.subatividade_mestre_id is None:
        return
    if target.meta_produtividade_snapshot is not None and target.unidade_medida_snapshot is not None:
        return
    try:
        from sqlalchemy import text
        result = connection.execute(
            text('SELECT meta_produtividade, unidade_medida FROM subatividade_mestre WHERE id = :id'),
            {'id': target.subatividade_mestre_id}
        ).fetchone()
        if result:
            if target.meta_produtividade_snapshot is None:
                target.meta_produtividade_snapshot = result[0]
            if target.unidade_medida_snapshot is None:
                target.unidade_medida_snapshot = result[1]
    except Exception as _snap_err:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            f"[WARN] Falha ao preencher snapshot de produtividade para subatividade_mestre_id={target.subatividade_mestre_id}: {_snap_err}"
        )


class SubatividadeMestre(db.Model):
    """
    Modelo mestre de subatividades para cada serviço
    Define as subatividades padrão que podem ser aplicadas aos serviços
    """
    __tablename__ = 'subatividade_mestre'
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=True)
    tipo = db.Column(db.String(20), nullable=False, default='subatividade')  # 'grupo' ou 'subatividade'
    
    # Dados da subatividade
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    ordem_padrao = db.Column(db.Integer, default=0)
    
    # Configurações
    obrigatoria = db.Column(db.Boolean, default=True)  # Sempre aparece nos RDOs
    duracao_estimada_horas = db.Column(db.Float)  # Para planejamento
    complexidade = db.Column(db.Integer, default=1)  # 1-5

    # Catálogo de produtividade (Migration #94)
    unidade_medida = db.Column(db.String(30))        # ex: m², m linear, un, m³
    meta_produtividade = db.Column(db.Float)          # ex: 5.0 → 5 m²/h por funcionário
    
    # Multi-tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Task #62 — flag de origem e revisão pendente.
    # Quando uma tarefa de cronograma é criada com nome de subatividade que
    # NÃO corresponde a nenhuma SubatividadeMestre existente, criamos uma
    # nova marcando criada_via_cronograma=True e precisa_revisao=True para
    # que o gestor revise composições/unidade/meta no Catálogo depois.
    criada_via_cronograma = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    precisa_revisao = db.Column(db.Boolean, nullable=False, default=False, server_default='false')

    # Controle
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', backref='subatividades_mestre')
    admin = db.relationship('Usuario', backref='subatividades_mestre_administradas')
    
    # Índices
    __table_args__ = (
        db.Index('idx_subativ_mestre_servico', 'servico_id'),
        db.Index('idx_subativ_mestre_admin', 'admin_id'),
    )
    
    def __repr__(self):
        return f'<SubatividadeMestre {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ordem_padrao': self.ordem_padrao,
            'obrigatoria': self.obrigatoria,
            'duracao_estimada_horas': self.duracao_estimada_horas,
            'complexidade': self.complexidade,
            'unidade_medida': self.unidade_medida or '',
            'meta_produtividade': self.meta_produtividade,
            'servico_id': self.servico_id,
            'servico_nome': self.servico.nome if self.servico else None
        }


# ================================
# MÓDULO 3: GESTÃO DE EQUIPES
# ================================

class AlocacaoEquipe(db.Model):
    """Sistema completo de alocação de equipes - MÓDULO 3 v8.0"""
    __tablename__ = 'alocacao_equipe'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    
    # Dados da alocação
    data_alocacao = db.Column(db.Date, nullable=False)
    tipo_local = db.Column(db.String(20), nullable=False)  # 'oficina', 'campo'
    turno = db.Column(db.String(20), default='matutino')  # 'matutino', 'vespertino', 'noturno'
    
    # Controle e auditoria avançado (conforme reunião técnica)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    rdo_gerado_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))  # NULL se for oficina
    rdo_gerado = db.Column(db.Boolean, default=False)  # Flag para compatibilidade
    
    # Status da alocação
    status = db.Column(db.String(20), default='Planejado')  # 'Planejado', 'Executado', 'Cancelado'
    prioridade = db.Column(db.String(20), default='Normal')  # 'Alta', 'Normal', 'Baixa'
    
    # Validações e controle de conflitos
    validacao_conflito = db.Column(db.Boolean, default=False)  # Se foi validado contra conflitos
    motivo_cancelamento = db.Column(db.Text)  # Motivo se cancelado
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='alocacoes_equipe')
    obra = db.relationship('Obra', backref='alocacoes_equipe')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id], backref='alocacoes_criadas')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='alocacoes_administradas')
    rdo_gerado_rel = db.relationship('RDO', backref='alocacao_origem')
    
    # Índices para performance e unicidade
    __table_args__ = (
        db.UniqueConstraint('funcionario_id', 'data_alocacao', name='uk_funcionario_data_alocacao'),
        db.Index('idx_alocacao_data_admin', 'data_alocacao', 'admin_id'),
        db.Index('idx_alocacao_obra_data', 'obra_id', 'data_alocacao'),
        db.Index('idx_alocacao_funcionario_status', 'funcionario_id', 'status'),
    )
    
    def __repr__(self):
        func_nome = self.funcionario.nome if self.funcionario else f"ID:{self.funcionario_id}"
        obra_nome = self.obra.nome if self.obra else f"ID:{self.obra_id}"
        return f'<AlocacaoEquipe {func_nome} -> {obra_nome} ({self.data_alocacao})>'
    
    def to_dict(self):
        """Converter para dicionário para APIs do sistema Kanban/Calendário"""
        return {
            'id': self.id,
            'funcionario_id': self.funcionario_id,
            'funcionario_nome': self.funcionario.nome if self.funcionario else None,
            'funcionario_cargo': self.funcionario.cargo if self.funcionario else None,
            'obra_id': self.obra_id,
            'obra_nome': self.obra.nome if self.obra else None,
            'obra_codigo': self.obra.codigo if self.obra else None,
            'data_alocacao': self.data_alocacao.isoformat(),
            'tipo_local': self.tipo_local,
            'turno': self.turno,
            'status': self.status,
            'prioridade': self.prioridade,
            'rdo_gerado': self.rdo_gerado,
            'rdo_gerado_id': self.rdo_gerado_id,
            'rdo_numero': self.rdo_gerado_rel.numero_rdo if self.rdo_gerado_rel else None,
            'validacao_conflito': self.validacao_conflito,
            'observacoes': self.observacoes,
            'motivo_cancelamento': self.motivo_cancelamento,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def pode_ser_cancelada(self):
        """Verifica se a alocação pode ser cancelada"""
        return self.status == 'Planejado' and self.data_alocacao >= date.today()
    
    def gerar_numero_rdo_automatico(self):
        """Gera número de RDO conforme especificação da reunião técnica"""
        if not self.obra:
            return None
        
        data_str = self.data_alocacao.strftime('%Y%m%d')
        codigo_obra = self.obra.codigo or f'OBR{self.obra.id:03d}'
        
        # Buscar último RDO do dia para esta obra
        ultimo_rdo = RDO.query.filter(
            RDO.obra_id == self.obra_id,
            RDO.numero_rdo.like(f'RDO-{codigo_obra}-{data_str}%')
        ).order_by(RDO.numero_rdo.desc()).first()
        
        if ultimo_rdo:
            try:
                ultimo_numero = int(ultimo_rdo.numero_rdo.split('-')[-1])
                novo_numero = ultimo_numero + 1
            except:
                novo_numero = 1
        else:
            novo_numero = 1
        
        return f"RDO-{codigo_obra}-{data_str}-{novo_numero:03d}"


# ================================
# MÓDULO 4: ALMOXARIFADO INTELIGENTE
# ================================


class CategoriaProduto(db.Model):
    """Categorias de produtos para organização do almoxarifado"""
    __tablename__ = 'categoria_produto'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    codigo = db.Column(db.String(10), nullable=False)  # CIM, ELE, HID, etc.
    cor_hex = db.Column(db.String(7), default='#007bff')  # Para interface visual
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    produtos = db.relationship('Produto', backref='categoria_produto', lazy='dynamic')
    admin = db.relationship('Usuario', backref='categorias_administradas')
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('codigo', 'admin_id', name='uk_categoria_codigo_admin'),
        db.Index('idx_categoria_admin_codigo', 'admin_id', 'codigo'),
    )
    
    def __repr__(self):
        return f'<CategoriaProduto {self.nome}>'

fornecedor_categorias = db.Table(
    'fornecedor_categorias',
    db.Column('fornecedor_id', db.Integer, db.ForeignKey('fornecedor.id', ondelete='CASCADE'), primary_key=True),
    db.Column('categoria_fornecedor_id', db.Integer, db.ForeignKey('categoria_fornecedor.id', ondelete='CASCADE'), primary_key=True),
)


class Fornecedor(db.Model):
    """Fornecedores para controle de compras e notas fiscais"""
    __tablename__ = 'fornecedor'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)  # Campo legado obrigatório
    razao_social = db.Column(db.String(200))
    nome_fantasia = db.Column(db.String(200))
    cnpj = db.Column(db.String(18), nullable=False)
    inscricao_estadual = db.Column(db.String(20))
    
    # Endereço
    endereco = db.Column(db.Text)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    cep = db.Column(db.String(10))
    
    # Contato
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    contato_responsavel = db.Column(db.String(100))
    
    # Tipo: MATERIAL | PRESTADOR_SERVICO | OUTRO
    tipo_fornecedor = db.Column(db.String(20), nullable=True, default='OUTRO')

    # Dados bancários / PIX
    chave_pix = db.Column(db.String(255))

    # Status
    ativo = db.Column(db.Boolean, default=True)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    notas_fiscais = db.relationship('NotaFiscal', backref='fornecedor', lazy='dynamic')
    admin = db.relationship('Usuario', backref='fornecedores_administrados')
    categorias = db.relationship(
        'CategoriaFornecedor',
        secondary='fornecedor_categorias',
        lazy='subquery',
        backref=db.backref('fornecedores', lazy=True),
    )
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('cnpj', 'admin_id', name='uk_fornecedor_cnpj_admin'),
        db.Index('idx_fornecedor_admin_ativo', 'admin_id', 'ativo'),
    )
    
    def __repr__(self):
        return f'<Fornecedor {self.razao_social}>'
    
    @property
    def cnpj_formatado(self):
        """Retorna CNPJ formatado"""
        if len(self.cnpj) == 14:
            return f"{self.cnpj[:2]}.{self.cnpj[2:5]}.{self.cnpj[5:8]}/{self.cnpj[8:12]}-{self.cnpj[12:]}"
        return self.cnpj

class ContaPagar(db.Model):
    """Contas a Pagar - Gestão de pagamentos a fornecedores"""
    __tablename__ = 'conta_pagar'
    
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    numero_documento = db.Column(db.String(50))
    descricao = db.Column(db.Text, nullable=False)
    valor_original = db.Column(db.Numeric(15, 2), nullable=False)
    valor_pago = db.Column(db.Numeric(15, 2), default=0)
    saldo = db.Column(db.Numeric(15, 2))
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDENTE')
    conta_contabil_codigo = db.Column(db.String(20))
    forma_pagamento = db.Column(db.String(50))
    observacoes = db.Column(db.Text)
    origem_tipo = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    import_batch_id = db.Column(db.String(50), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Task #11 — Compras Parceladas e Calendário de Pagamentos
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    parcela_numero = db.Column(db.Integer, nullable=True)
    parcela_total = db.Column(db.Integer, nullable=True)
    pedido_compra_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id', use_alter=True, name='fk_cp_pedido_compra'), nullable=True)
    fechamento_id = db.Column(db.Integer, db.ForeignKey('fechamento_pagamento.id', use_alter=True, name='fk_cp_fechamento'), nullable=True)
    
    fornecedor = db.relationship('Fornecedor', backref='contas_pagar')
    obra = db.relationship('Obra', backref='contas_pagar')
    conta_contabil = db.relationship('PlanoContas', backref='contas_pagar_rel')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='contas_pagar_admin')
    responsavel = db.relationship('Usuario', foreign_keys=[responsavel_id], backref='contas_pagar_responsavel')
    
    __table_args__ = (
        db.Index('idx_conta_pagar_vencimento', 'data_vencimento'),
        db.Index('idx_conta_pagar_status', 'status'),
        db.Index('idx_conta_pagar_fornecedor', 'fornecedor_id'),
        db.Index('idx_conta_pagar_obra', 'obra_id'),
        # Fase 0.6 / D4 — a conta contábil pertence ao tenant: FK composta
        # contra a PK (admin_id, codigo) de plano_contas. Ver migration 218.
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_contabil_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
        db.Index('idx_conta_pagar_admin', 'admin_id'),
    )

class ContaReceber(db.Model):
    """Contas a Receber - Gestão de recebimentos de clientes"""
    __tablename__ = 'conta_receber'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(200), nullable=False)
    cliente_cpf_cnpj = db.Column(db.String(18))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    numero_documento = db.Column(db.String(50))
    descricao = db.Column(db.Text, nullable=False)
    valor_original = db.Column(db.Numeric(15, 2), nullable=False)
    valor_recebido = db.Column(db.Numeric(15, 2), default=0)
    saldo = db.Column(db.Numeric(15, 2))
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDENTE')
    conta_contabil_codigo = db.Column(db.String(20))
    forma_recebimento = db.Column(db.String(50))
    observacoes = db.Column(db.Text)
    origem_tipo = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    import_batch_id = db.Column(db.String(50), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    obra = db.relationship('Obra', backref='contas_receber')
    conta_contabil = db.relationship('PlanoContas', backref='contas_receber_rel')
    admin = db.relationship('Usuario', backref='contas_receber_admin')
    
    __table_args__ = (
        db.Index('idx_conta_receber_vencimento', 'data_vencimento'),
        db.Index('idx_conta_receber_status', 'status'),
        db.Index('idx_conta_receber_cliente', 'cliente_cpf_cnpj'),
        db.Index('idx_conta_receber_obra', 'obra_id'),
        # Fase 0.6 / D4 — a conta contábil pertence ao tenant: FK composta
        # contra a PK (admin_id, codigo) de plano_contas. Ver migration 218.
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_contabil_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
        db.Index('idx_conta_receber_admin', 'admin_id'),
    )

class BancoEmpresa(db.Model):
    """Contas Bancárias da Empresa"""
    __tablename__ = 'banco_empresa'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_banco = db.Column(db.String(100), nullable=False)
    agencia = db.Column(db.String(10), nullable=False)
    conta = db.Column(db.String(20), nullable=False)
    tipo_conta = db.Column(db.String(20))
    saldo_inicial = db.Column(db.Numeric(15, 2), default=0)
    saldo_atual = db.Column(db.Numeric(15, 2), default=0)
    data_saldo_inicial = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('Usuario', backref='bancos_empresa')
    
    __table_args__ = (
        db.Index('idx_banco_admin', 'admin_id'),
    )

class Produto(db.Model):
    """Produtos/materiais do almoxarifado com controle completo"""
    __tablename__ = 'produto'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo_interno = db.Column(db.String(20), nullable=False)
    codigo_barras = db.Column(db.String(50))
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    
    # Classificação
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_produto.id'), nullable=False)
    
    # Unidades e medidas
    unidade_medida = db.Column(db.String(10), nullable=False)  # UN, KG, M, L, M2, M3, etc.
    peso_unitario = db.Column(db.Numeric(10,3))  # Para cálculos de frete
    dimensoes = db.Column(db.String(50))  # Ex: "10x20x30 cm"
    
    # Controle de estoque
    estoque_minimo = db.Column(db.Numeric(10,3), default=0)
    estoque_maximo = db.Column(db.Numeric(10,3))
    estoque_atual = db.Column(db.Numeric(10,3), default=0)
    estoque_reservado = db.Column(db.Numeric(10,3), default=0)  # Para futuras funcionalidades
    
    # Valores
    valor_medio = db.Column(db.Numeric(10,2), default=0)  # Calculado automaticamente
    ultimo_valor_compra = db.Column(db.Numeric(10,2))
    
    # Status e controle
    ativo = db.Column(db.Boolean, default=True)
    critico = db.Column(db.Boolean, default=False)  # Material crítico para obras
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    categoria = db.relationship('CategoriaProduto', foreign_keys=[categoria_id], overlaps="categoria_produto,produtos")
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='produtos_administrados')
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('codigo_interno', 'admin_id', name='uk_produto_codigo_admin'),
        db.Index('idx_produto_codigo_barras', 'codigo_barras'),
        db.Index('idx_produto_admin_ativo', 'admin_id', 'ativo'),
        db.Index('idx_produto_categoria', 'categoria_id'),
        db.Index('idx_produto_estoque_baixo', 'admin_id', 'estoque_atual', 'estoque_minimo'),
    )
    
    def __repr__(self):
        return f'<Produto {self.nome}>'
    
    @property
    def estoque_disponivel(self):
        """Estoque disponível (atual - reservado)"""
        return self.estoque_atual - self.estoque_reservado
    
    @property
    def status_estoque(self):
        """Status do estoque: OK, BAIXO, CRITICO, ZERADO"""
        if self.estoque_atual <= 0:
            return 'ZERADO'
        elif self.estoque_atual <= (self.estoque_minimo * 0.5):
            return 'CRITICO'
        elif self.estoque_atual <= self.estoque_minimo:
            return 'BAIXO'
        else:
            return 'OK'
    
    @property
    def valor_estoque_atual(self):
        """Valor total do estoque atual"""
        return self.estoque_atual * self.valor_medio
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'codigo_interno': self.codigo_interno,
            'codigo_barras': self.codigo_barras,
            'nome': self.nome,
            'descricao': self.descricao,
            'categoria': self.categoria.nome if self.categoria else None,
            'unidade_medida': self.unidade_medida,
            'estoque_atual': float(self.estoque_atual),
            'estoque_minimo': float(self.estoque_minimo),
            'valor_medio': float(self.valor_medio),
            'status_estoque': self.status_estoque,
            'ativo': self.ativo
        }

class NotaFiscal(db.Model):
    """Notas fiscais para controle de entrada de materiais"""
    __tablename__ = 'nota_fiscal'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False)
    serie = db.Column(db.String(5), nullable=False)
    chave_acesso = db.Column(db.String(44), unique=True, nullable=False)
    
    # Fornecedor
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    
    # Datas
    data_emissao = db.Column(db.Date, nullable=False)
    data_entrada = db.Column(db.Date)  # Data de entrada no estoque
    
    # Valores
    valor_produtos = db.Column(db.Numeric(10,2), nullable=False)
    valor_frete = db.Column(db.Numeric(10,2), default=0)
    valor_desconto = db.Column(db.Numeric(10,2), default=0)
    valor_total = db.Column(db.Numeric(10,2), nullable=False)
    
    # XML e processamento
    xml_content = db.Column(db.Text)  # Armazenar XML completo
    xml_hash = db.Column(db.String(64))  # Hash para detectar duplicatas
    
    # Status
    status = db.Column(db.String(20), default='Pendente')  # Pendente, Processada, Erro
    observacoes = db.Column(db.Text)
    
    # Controle
    processada_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data_processamento = db.Column(db.DateTime)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='nota_fiscal', lazy='dynamic')
    processada_por = db.relationship('Usuario', foreign_keys=[processada_por_id])
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='notas_fiscais_administradas')
    
    # Índices
    __table_args__ = (
        db.Index('idx_nf_admin_status', 'admin_id', 'status'),
        db.Index('idx_nf_fornecedor_data', 'fornecedor_id', 'data_emissao'),
        db.Index('idx_nf_chave_acesso', 'chave_acesso'),
    )
    
    def __repr__(self):
        return f'<NotaFiscal {self.numero}/{self.serie}>'
    
    @property
    def numero_formatado(self):
        """Número da NF formatado"""
        return f"{self.numero}/{self.serie}"

class MovimentacaoEstoque(db.Model):
    """Movimentações de estoque com rastreabilidade completa"""
    __tablename__ = 'movimentacao_estoque'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Produto
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    
    # Tipo de movimentação
    tipo_movimentacao = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA, DEVOLUCAO, AJUSTE
    
    # Quantidades
    quantidade = db.Column(db.Numeric(10,3), nullable=False)
    quantidade_anterior = db.Column(db.Numeric(10,3))  # Para auditoria
    quantidade_posterior = db.Column(db.Numeric(10,3))  # Para auditoria
    
    # Valores
    valor_unitario = db.Column(db.Numeric(10,2))
    valor_total = db.Column(db.Numeric(10,2))
    
    # Data e hora
    data_movimentacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Origem da movimentação (relacionamentos opcionais)
    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('nota_fiscal.id'))
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    
    # Controle e auditoria
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    observacoes = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='movimentacoes_estoque')
    funcionario = db.relationship('Funcionario', backref='movimentacoes_materiais_funcionario')
    obra = db.relationship('Obra', backref='movimentacoes_materiais_obra')
    rdo = db.relationship('RDO', backref='movimentacoes_materiais_rdo')
    
    # Índices
    __table_args__ = (
        db.Index('idx_mov_produto_data', 'produto_id', 'data_movimentacao'),
        db.Index('idx_mov_admin_tipo', 'admin_id', 'tipo_movimentacao'),
        db.Index('idx_mov_obra_data', 'obra_id', 'data_movimentacao'),
        db.Index('idx_mov_funcionario_data', 'funcionario_id', 'data_movimentacao'),
        db.Index('idx_mov_rdo', 'rdo_id'),
        db.Index('idx_mov_nf', 'nota_fiscal_id'),
    )
    
    def __repr__(self):
        return f'<MovimentacaoEstoque {self.tipo_movimentacao} - Produto:{self.produto_id}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'produto_nome': self.produto_rel.nome if hasattr(self, 'produto_rel') and self.produto_rel else None,
            'tipo_movimentacao': self.tipo_movimentacao,
            'quantidade': float(self.quantidade),
            'valor_unitario': float(self.valor_unitario) if self.valor_unitario else None,
            'valor_total': float(self.valor_total) if self.valor_total else None,
            'data_movimentacao': self.data_movimentacao.isoformat(),
            'funcionario_nome': self.funcionario.nome if self.funcionario else None,
            'obra_nome': self.obra.nome if self.obra else None,
            'rdo_numero': self.rdo.numero_rdo if self.rdo else None,
            'usuario_nome': self.usuario.nome if self.usuario else None,
            'observacoes': self.observacoes
        }
    
    # Relacionamentos
    produto_rel = db.relationship('Produto', foreign_keys=[produto_id], overlaps="movimentacoes")


# ================================
# MÓDULO 6: FOLHA DE PAGAMENTO AUTOMÁTICA
# ================================

class ConfiguracaoSalarial(db.Model):
    """Configuração salarial por funcionário"""
    __tablename__ = 'configuracao_salarial'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    salario_base = db.Column(db.Numeric(10, 2), nullable=False)  # Salário base
    tipo_salario = db.Column(db.String(20), nullable=False)  # MENSAL, HORISTA, COMISSIONADO
    valor_hora = db.Column(db.Numeric(10, 2))  # Para horistas
    percentual_comissao = db.Column(db.Numeric(5, 2))  # Para comissionados
    carga_horaria_mensal = db.Column(db.Integer, default=220)  # Horas/mês padrão
    dependentes = db.Column(db.Integer, default=0)  # Para IRRF
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = vigente
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='configuracoes_salariais')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_config_salarial_funcionario_ativo', 'funcionario_id', 'ativo'),
        db.Index('idx_config_salarial_admin_id', 'admin_id'),
        db.Index('idx_config_salarial_vigencia', 'data_inicio', 'data_fim'),
    )

class BeneficioFuncionario(db.Model):
    """Benefícios por funcionário"""
    __tablename__ = 'beneficio_funcionario'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo_beneficio = db.Column(db.String(50), nullable=False)  # VR, VT, PLANO_SAUDE, SEGURO_VIDA, etc.
    valor = db.Column(db.Numeric(10, 2), nullable=False)  # Valor do benefício
    percentual_desconto = db.Column(db.Numeric(5, 2), default=0)  # % descontado do funcionário
    dias_por_mes = db.Column(db.Integer, default=22)  # Para VR/VT
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = vigente
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='beneficios')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_beneficio_funcionario_tipo', 'funcionario_id', 'tipo_beneficio', 'ativo'),
        db.Index('idx_beneficio_admin_id', 'admin_id'),
    )

class CalculoHorasMensal(db.Model):
    """Cálculo de horas mensal baseado nos pontos"""
    __tablename__ = 'calculo_horas_mensal'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    
    # Horas trabalhadas
    horas_normais = db.Column(db.Numeric(8, 2), default=0)
    horas_extras_50 = db.Column(db.Numeric(8, 2), default=0)  # Extras 50%
    horas_extras_100 = db.Column(db.Numeric(8, 2), default=0)  # Extras 100%
    horas_noturnas = db.Column(db.Numeric(8, 2), default=0)  # Adicional noturno
    horas_dsr = db.Column(db.Numeric(8, 2), default=0)  # Descanso semanal
    
    # Faltas e atrasos
    faltas_horas = db.Column(db.Numeric(8, 2), default=0)
    atrasos_horas = db.Column(db.Numeric(8, 2), default=0)
    
    # Controle de dias
    dias_trabalhados = db.Column(db.Integer, default=0)
    dias_faltas = db.Column(db.Integer, default=0)
    dias_uteis_mes = db.Column(db.Integer, default=22)
    
    # Controle de processamento
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)
    reprocessado = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='calculos_horas')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_calculo_horas_funcionario_mes', 'funcionario_id', 'mes_referencia'),
        db.Index('idx_calculo_horas_admin_id', 'admin_id'),
        db.UniqueConstraint('funcionario_id', 'mes_referencia', name='uk_calculo_horas_funcionario_mes'),
    )

class FolhaPagamento(db.Model):
    """Folha de pagamento mensal por funcionário"""
    __tablename__ = 'folha_pagamento'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    
    # PROVENTOS
    salario_base = db.Column(db.Numeric(10, 2), default=0)
    horas_extras = db.Column(db.Numeric(10, 2), default=0)
    adicional_noturno = db.Column(db.Numeric(10, 2), default=0)
    dsr = db.Column(db.Numeric(10, 2), default=0)  # Descanso semanal remunerado
    comissoes = db.Column(db.Numeric(10, 2), default=0)
    bonus = db.Column(db.Numeric(10, 2), default=0)
    outros_proventos = db.Column(db.Numeric(10, 2), default=0)
    total_proventos = db.Column(db.Numeric(10, 2), default=0)
    
    # DESCONTOS OBRIGATÓRIOS
    inss = db.Column(db.Numeric(10, 2), default=0)
    irrf = db.Column(db.Numeric(10, 2), default=0)
    fgts = db.Column(db.Numeric(10, 2), default=0)  # Não é desconto, mas é calculado
    
    # DESCONTOS DE BENEFÍCIOS
    vale_refeicao = db.Column(db.Numeric(10, 2), default=0)
    vale_transporte = db.Column(db.Numeric(10, 2), default=0)
    plano_saude = db.Column(db.Numeric(10, 2), default=0)
    seguro_vida = db.Column(db.Numeric(10, 2), default=0)
    
    # DESCONTOS POR FALTAS/ATRASOS
    faltas = db.Column(db.Numeric(10, 2), default=0)
    atrasos = db.Column(db.Numeric(10, 2), default=0)
    
    # OUTROS DESCONTOS
    adiantamentos = db.Column(db.Numeric(10, 2), default=0)
    emprestimos = db.Column(db.Numeric(10, 2), default=0)
    outros_descontos = db.Column(db.Numeric(10, 2), default=0)
    total_descontos = db.Column(db.Numeric(10, 2), default=0)
    
    # LÍQUIDO
    salario_liquido = db.Column(db.Numeric(10, 2), default=0)
    
    # CONTROLE
    status = db.Column(db.String(20), default='CALCULADO')  # CALCULADO, APROVADO, PAGO
    calculado_em = db.Column(db.DateTime, default=datetime.utcnow)
    aprovado_em = db.Column(db.DateTime)
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    pago_em = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='folhas_pagamento')
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_folha_funcionario_mes', 'funcionario_id', 'mes_referencia'),
        db.Index('idx_folha_admin_status', 'admin_id', 'status'),
        db.Index('idx_folha_mes_referencia', 'mes_referencia'),
        db.Index('idx_folha_admin_mes_status', 'admin_id', 'mes_referencia', 'status'),  # [OK] OTIMIZAÇÃO: Índice composto para filtros combinados
        db.UniqueConstraint('funcionario_id', 'mes_referencia', name='uk_folha_funcionario_mes'),
    )

class LancamentoRecorrente(db.Model):
    """Lançamentos recorrentes mensais"""
    __tablename__ = 'lancamento_recorrente'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # PROVENTO, DESCONTO
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Numeric(10, 2))  # Valor fixo
    percentual = db.Column(db.Numeric(5, 2))  # Percentual do salário
    dia_vencimento = db.Column(db.Integer, default=1)  # Dia do mês para processar
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)  # NULL = sem fim
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='lancamentos_recorrentes')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_lancamento_funcionario_ativo', 'funcionario_id', 'ativo'),
        db.Index('idx_lancamento_admin_id', 'admin_id'),
    )

class Adiantamento(db.Model):
    """Adiantamentos salariais"""
    __tablename__ = 'adiantamento'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_solicitacao = db.Column(db.Date, nullable=False)
    data_aprovacao = db.Column(db.Date)
    aprovado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    # Parcelamento
    parcelas = db.Column(db.Integer, default=1)
    valor_parcela = db.Column(db.Numeric(10, 2))
    parcelas_pagas = db.Column(db.Integer, default=0)
    
    # Controle
    status = db.Column(db.String(20), default='SOLICITADO')  # SOLICITADO, APROVADO, QUITADO, CANCELADO
    motivo = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='adiantamentos')
    aprovador = db.relationship('Usuario', foreign_keys=[aprovado_por])
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_adiantamento_funcionario_status', 'funcionario_id', 'status'),
        db.Index('idx_adiantamento_admin_id', 'admin_id'),
    )

class FeriasDecimo(db.Model):
    """Controle de férias e 13º salário"""
    __tablename__ = 'ferias_decimo'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # FERIAS, DECIMO_TERCEIRO
    ano_referencia = db.Column(db.Integer, nullable=False)
    
    # Período
    periodo_inicio = db.Column(db.Date, nullable=False)
    periodo_fim = db.Column(db.Date, nullable=False)
    
    # Cálculos
    dias_direito = db.Column(db.Integer, default=30)  # Dias de férias ou meses de 13º
    dias_gozados = db.Column(db.Integer, default=0)
    valor_calculado = db.Column(db.Numeric(10, 2), default=0)
    terco_constitucional = db.Column(db.Numeric(10, 2), default=0)  # 1/3 das férias
    
    # Controle
    status = db.Column(db.String(20), default='CALCULADO')  # CALCULADO, PAGO
    data_pagamento = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='ferias_decimos')
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_ferias_decimo_funcionario_tipo_ano', 'funcionario_id', 'tipo', 'ano_referencia'),
        db.Index('idx_ferias_decimo_admin_id', 'admin_id'),
    )

class ParametrosLegais(db.Model):
    """Parâmetros legais por ano (INSS, IRRF, etc.)"""
    __tablename__ = 'parametros_legais'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ano_vigencia = db.Column(db.Integer, nullable=False)
    
    # INSS - Tabela progressiva
    inss_faixa1_limite = db.Column(db.Numeric(10, 2), default=1320.00)  # 2024
    inss_faixa1_percentual = db.Column(db.Numeric(5, 2), default=7.5)
    inss_faixa2_limite = db.Column(db.Numeric(10, 2), default=2571.29)
    inss_faixa2_percentual = db.Column(db.Numeric(5, 2), default=9.0)
    inss_faixa3_limite = db.Column(db.Numeric(10, 2), default=3856.94)
    inss_faixa3_percentual = db.Column(db.Numeric(5, 2), default=12.0)
    inss_faixa4_limite = db.Column(db.Numeric(10, 2), default=7507.49)
    inss_faixa4_percentual = db.Column(db.Numeric(5, 2), default=14.0)
    inss_teto = db.Column(db.Numeric(10, 2), default=877.24)  # Valor máximo
    
    # IRRF - Tabela progressiva
    irrf_isencao = db.Column(db.Numeric(10, 2), default=2112.00)
    irrf_faixa1_limite = db.Column(db.Numeric(10, 2), default=2826.65)
    irrf_faixa1_percentual = db.Column(db.Numeric(5, 2), default=7.5)
    irrf_faixa1_deducao = db.Column(db.Numeric(10, 2), default=158.40)
    irrf_faixa2_limite = db.Column(db.Numeric(10, 2), default=3751.05)
    irrf_faixa2_percentual = db.Column(db.Numeric(5, 2), default=15.0)
    irrf_faixa2_deducao = db.Column(db.Numeric(10, 2), default=370.40)
    irrf_faixa3_limite = db.Column(db.Numeric(10, 2), default=4664.68)
    irrf_faixa3_percentual = db.Column(db.Numeric(5, 2), default=22.5)
    irrf_faixa3_deducao = db.Column(db.Numeric(10, 2), default=651.73)
    irrf_faixa4_percentual = db.Column(db.Numeric(5, 2), default=27.5)
    irrf_faixa4_deducao = db.Column(db.Numeric(10, 2), default=884.96)
    irrf_dependente_valor = db.Column(db.Numeric(10, 2), default=189.59)
    
    # OUTROS PARÂMETROS
    fgts_percentual = db.Column(db.Numeric(5, 2), default=8.0)
    salario_minimo = db.Column(db.Numeric(10, 2), default=1412.00)  # 2024
    vale_transporte_percentual = db.Column(db.Numeric(5, 2), default=6.0)
    adicional_noturno_percentual = db.Column(db.Numeric(5, 2), default=20.0)
    hora_extra_50_percentual = db.Column(db.Numeric(5, 2), default=50.0)
    hora_extra_100_percentual = db.Column(db.Numeric(5, 2), default=100.0)
    
    # TOLERÂNCIA PARA HORAS EXTRAS E ATRASOS (Dez/2025)
    # Variações em minutos dentro dessa tolerância não são computadas como extras ou atrasos
    tolerancia_minutos = db.Column(db.Integer, default=10)  # Padrão: 10 minutos de tolerância
    
    # Controle
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', foreign_keys=[admin_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_parametros_admin_ano', 'admin_id', 'ano_vigencia'),
        db.UniqueConstraint('admin_id', 'ano_vigencia', name='uk_parametros_admin_ano'),
    )
    
    @staticmethod
    @lru_cache(maxsize=128)
    def get_parametros_cached(admin_id: int, ano: int):
        """
        Busca parâmetros legais com cache em memória
        
        Cache de 128 entradas (admin_id + ano)
        Parâmetros legais mudam raramente (uma vez por ano no máximo)
        
        Args:
            admin_id: ID do administrador/tenant
            ano: Ano de vigência dos parâmetros
            
        Returns:
            ParametrosLegais ou None
        """
        return ParametrosLegais.query.filter_by(
            admin_id=admin_id,
            ano_vigencia=ano
        ).first()
    
    @staticmethod
    def invalidar_cache():
        """Limpa cache de parâmetros legais (usar ao criar/editar)"""
        ParametrosLegais.get_parametros_cached.cache_clear()
        logger.info("[SYNC] Cache de ParametrosLegais invalidado")


# ================================
# RDO ATIVIDADE - MODELO LEGADO (mantido para compatibilidade de FK)
# ================================

class RdoAtividade(db.Model):
    """Modelo legado de atividades de RDO - mantido apenas para compatibilidade de chave estrangeira"""
    __tablename__ = 'rdo_atividade'

    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=True)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20), default='Em andamento')
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RdoAtividade {self.id}>'


# ================================
# NOTIFICAÇÕES CLIENTE - MÓDULO 2
# ================================

class NotificacaoCliente(db.Model):
    """Notificações automáticas para clientes via portal"""
    __tablename__ = 'notificacao_cliente'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    
    # Tipo e conteúdo
    tipo = db.Column(db.String(30), nullable=False)  # 'novo_rdo', 'marco_atingido', 'atraso', 'conclusao_atividade'
    titulo = db.Column(db.String(100), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    
    # Dados relacionados
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    atividade_id = db.Column(db.Integer, db.ForeignKey('rdo_atividade.id'))
    
    # Status
    visualizada = db.Column(db.Boolean, default=False)
    data_visualizacao = db.Column(db.DateTime)
    
    # Prioridade
    prioridade = db.Column(db.String(10), default='normal')  # 'baixa', 'normal', 'alta', 'urgente'
    
    # Controle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='notificacoes_obra')
    rdo = db.relationship('RDO', backref='notificacoes')
    # Removido: relacionamento com RDOAtividade obsoleto
    
    def __repr__(self):
        return f'<NotificacaoCliente {self.titulo}>'

# ===============================================================
# == MÓDULO 7: SISTEMA CONTÁBIL COMPLETO
# ===============================================================

class PlanoContas(db.Model):
    """Plano de Contas brasileiro completo e hierárquico.

    Fase 0.6 / D4 — a PK é `(admin_id, codigo)`. Era só `codigo`, global,
    apesar de a tabela sempre ter tido `admin_id`: a primeira empresa a
    semear ficava dona de '1.1.01.001' e as demais não conseguiam criar a
    própria (o seed usava `ON CONFLICT (codigo) DO NOTHING`). Em 21/07 havia
    315 tenants com lançamentos contábeis e 2 com plano de contas.
    Ver migration 218.
    """
    __tablename__ = 'plano_contas'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_pai_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
    )
    # A ordem das colunas da PK segue a do índice criado pela migration 218.
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         primary_key=True, nullable=False)
    codigo = db.Column(db.String(20), primary_key=True)  # Ex: 1.1.01.001
    nome = db.Column(db.String(200), nullable=False)
    tipo_conta = db.Column(db.String(20), nullable=False)  # ATIVO, PASSIVO, PATRIMONIO, RECEITA, DESPESA
    natureza = db.Column(db.String(10), nullable=False)  # DEVEDORA, CREDORA
    nivel = db.Column(db.Integer, nullable=False)
    conta_pai_codigo = db.Column(db.String(20))
    aceita_lancamento = db.Column(db.Boolean, default=True)  # True para contas analíticas
    ativo = db.Column(db.Boolean, default=True)

    conta_pai = db.relationship('PlanoContas', remote_side=[admin_id, codigo])
    
    @staticmethod
    @lru_cache(maxsize=256)
    def get_conta_cached(admin_id: int, codigo: str):
        """
        Busca conta contábil com cache em memória
        
        Cache de 256 entradas (admin_id + codigo)
        Plano de contas muda raramente (setup inicial + ajustes ocasionais)
        
        Args:
            admin_id: ID do administrador/tenant
            codigo: Código da conta (ex: '1.1.01.001')
            
        Returns:
            PlanoContas ou None
        """
        return PlanoContas.query.filter_by(
            admin_id=admin_id,
            codigo=codigo,
            ativo=True
        ).first()
    
    @staticmethod
    def invalidar_cache():
        """Limpa cache do plano de contas (usar ao criar/editar)"""
        PlanoContas.get_conta_cached.cache_clear()
        logger.info("[SYNC] Cache de PlanoContas invalidado")

class CentroCustoContabil(db.Model):
    """Centros de Custo para rateio contábil (Obras, Departamentos)."""
    __tablename__ = 'centro_custo_contabil'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # OBRA, DEPARTAMENTO, PROJETO
    descricao = db.Column(db.Text)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra')
    partidas = db.relationship('PartidaContabil', foreign_keys='PartidaContabil.centro_custo_id', back_populates='centro_custo')
    __table_args__ = (db.UniqueConstraint('codigo', 'admin_id', name='uq_centro_custo_contabil_codigo_admin'),)

class LancamentoContabil(db.Model):
    """Cabeçalho dos Lançamentos Contábeis (partidas dobradas)."""
    __tablename__ = 'lancamento_contabil'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False) # Sequencial por admin
    data_lancamento = db.Column(db.Date, nullable=False, index=True)
    historico = db.Column(db.String(500), nullable=False)
    valor_total = db.Column(db.Numeric(15, 2), nullable=False)
    origem = db.Column(db.String(50))  # MANUAL, MODULO_1, MODULO_4, MODULO_6
    origem_id = db.Column(db.Integer) # ID do registro de origem (Proposta, NotaFiscal, etc)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partidas = db.relationship('PartidaContabil', backref='lancamento', cascade="all, delete-orphan")
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    
    # [OK] OTIMIZAÇÃO: Índices compostos para queries frequentes
    __table_args__ = (
        db.Index('idx_lancamento_admin_data_origem', 'admin_id', 'data_lancamento', 'origem'),  # Relatórios contábeis
    )

class PartidaContabil(db.Model):
    """Itens do Lançamento Contábil (Débito e Crédito)."""
    __tablename__ = 'partida_contabil'
    id = db.Column(db.Integer, primary_key=True)
    lancamento_id = db.Column(db.Integer, db.ForeignKey('lancamento_contabil.id'), nullable=False)
    sequencia = db.Column(db.Integer, nullable=False)
    conta_codigo = db.Column(db.String(20), nullable=False, index=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo_contabil.id'))
    tipo_partida = db.Column(db.String(10), nullable=False)  # DEBITO, CREDITO
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    historico_complementar = db.Column(db.String(200))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    conta = db.relationship('PlanoContas')
    centro_custo = db.relationship('CentroCustoContabil', back_populates='partidas')

    __table_args__ = (
        # Fase 0.6 / D4 — a conta contábil pertence ao tenant: FK composta
        # contra a PK (admin_id, codigo) de plano_contas. Ver migration 218.
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
    )

class BalanceteMensal(db.Model):
    """Armazena os saldos mensais para geração rápida de relatórios."""
    __tablename__ = 'balancete_mensal'
    id = db.Column(db.Integer, primary_key=True)
    conta_codigo = db.Column(db.String(20), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)  # Primeiro dia do mês
    saldo_anterior = db.Column(db.Numeric(15, 2), default=0)
    debitos_mes = db.Column(db.Numeric(15, 2), default=0)
    creditos_mes = db.Column(db.Numeric(15, 2), default=0)
    saldo_atual = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('conta_codigo', 'mes_referencia', 'admin_id',
                            name='uq_balancete_conta_mes_admin'),
        # Fase 0.6 / D4 — a conta contábil pertence ao tenant: FK composta
        # contra a PK (admin_id, codigo) de plano_contas. Ver migration 218.
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
    )

class DREMensal(db.Model):
    """Demonstração do Resultado do Exercício (DRE) mensal."""
    __tablename__ = 'dre_mensal'
    id = db.Column(db.Integer, primary_key=True)
    mes_referencia = db.Column(db.Date, nullable=False)
    receita_bruta = db.Column(db.Numeric(15, 2), default=0)
    impostos_sobre_vendas = db.Column(db.Numeric(15, 2), default=0)
    receita_liquida = db.Column(db.Numeric(15, 2), default=0)
    custo_total = db.Column(db.Numeric(15, 2), default=0)
    lucro_bruto = db.Column(db.Numeric(15, 2), default=0)
    total_despesas = db.Column(db.Numeric(15, 2), default=0)
    lucro_operacional = db.Column(db.Numeric(15, 2), default=0)
    lucro_liquido = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('mes_referencia', 'admin_id', name='uq_dre_mes_admin'),)

class BalancoPatrimonial(db.Model):
    """Balanço Patrimonial em uma data específica."""
    __tablename__ = 'balanco_patrimonial'
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, nullable=False)
    total_ativo = db.Column(db.Numeric(15, 2), default=0)
    total_passivo_patrimonio = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('data_referencia', 'admin_id', name='uq_balanco_data_admin'),)

class FluxoCaixaContabil(db.Model):
    """Registro de todas as entradas e saídas de caixa."""
    __tablename__ = 'fluxo_caixa_contabil'
    id = db.Column(db.Integer, primary_key=True)
    data_movimento = db.Column(db.Date, nullable=False)
    tipo_movimento = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA
    categoria = db.Column(db.String(50), nullable=False)  # OPERACIONAL, INVESTIMENTO, FINANCIAMENTO
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    conta_codigo = db.Column(db.String(20))
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo_contabil.id'))
    origem = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    __table_args__ = (
        # Fase 0.6 / D4 — a conta contábil pertence ao tenant: FK composta
        # contra a PK (admin_id, codigo) de plano_contas. Ver migration 218.
        db.ForeignKeyConstraint(
            ['admin_id', 'conta_codigo'],
            ['plano_contas.admin_id', 'plano_contas.codigo'],
        ),
    )

class ConciliacaoBancaria(db.Model):
    """Registros para conciliação bancária."""
    __tablename__ = 'conciliacao_bancaria'
    id = db.Column(db.Integer, primary_key=True)
    conta_banco = db.Column(db.String(50), nullable=False)
    data_movimento = db.Column(db.Date, nullable=False)
    historico = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # DEBITO, CREDITO
    conciliado = db.Column(db.Boolean, default=False)
    lancamento_id = db.Column(db.Integer, db.ForeignKey('lancamento_contabil.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class ProvisaoMensal(db.Model):
    """Controle de provisões automáticas (Férias, 13º)."""
    __tablename__ = 'provisao_mensal'
    id = db.Column(db.Integer, primary_key=True)
    mes_referencia = db.Column(db.Date, nullable=False)
    tipo_provisao = db.Column(db.String(50), nullable=False)  # FERIAS, DECIMO_TERCEIRO, INSS_EMPRESA
    valor_provisionado = db.Column(db.Numeric(15, 2), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class SpedContabil(db.Model):
    """Registro dos arquivos SPED Contábil gerados."""
    __tablename__ = 'sped_contabil'
    id = db.Column(db.Integer, primary_key=True)
    periodo_inicial = db.Column(db.Date, nullable=False)
    periodo_final = db.Column(db.Date, nullable=False)
    arquivo_gerado = db.Column(db.String(200), nullable=False)
    hash_arquivo = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), default='GERADO') # GERADO, TRANSMITIDO, ACEITO
    data_geracao = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class AuditoriaContabil(db.Model):
    """Logs da auditoria automática do sistema."""
    __tablename__ = 'auditoria_contabil'
    id = db.Column(db.Integer, primary_key=True)
    data_auditoria = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_verificacao = db.Column(db.String(100), nullable=False)
    resultado = db.Column(db.String(20), nullable=False)  # CONFORME, NAO_CONFORME, ALERTA
    observacoes = db.Column(db.Text)
    valor_divergencia = db.Column(db.Numeric(15, 2))
    corrigido = db.Column(db.Boolean, default=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# MÓDULO 1 - SISTEMA DE PROPOSTAS
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.Text)
    cnpj = db.Column(db.String(18))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('Usuario', backref='clientes_administrados')
    observacoes = db.relationship(
        'ClienteObservacao', backref='cliente',
        cascade='all, delete-orphan',
        order_by='ClienteObservacao.created_at.desc()',
        foreign_keys='ClienteObservacao.cliente_id',
    )


class ClienteObservacao(db.Model):
    """Histórico de anotações livres sobre um Cliente."""
    __tablename__ = 'cliente_observacao'
    __table_args__ = (
        db.Index('ix_cliente_obs_cliente', 'cliente_id'),
        db.Index('ix_cliente_obs_admin', 'admin_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('cliente.id', ondelete='CASCADE'),
        nullable=False,
    )
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    texto = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


# Atualização de timestamp para verificar se o modelo é alterado
# Essa linha força o gunicorn a recarregar quando há mudanças
# Última modificação: 2025-08-11 21:05:00 - Módulo 1 Propostas adicionado



# MODELS DE SERVIÇOS
class StatusServico(Enum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    DESCONTINUADO = "descontinuado"

class TipoUnidade(Enum):
    M2 = "m2"
    M3 = "m3"
    ML = "ml"
    UN = "un"
    KG = "kg"
    H = "h"
    VERBA = "verba"

class ServicoMestre(db.Model):
    """Serviços principais que podem ser utilizados nas propostas"""
    __tablename__ = 'servico_mestre'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    codigo = Column(String(20), nullable=False)  # Ex: SRV001
    nome = Column(String(100), nullable=False)   # Ex: "Estrutura Metálica Industrial"
    descricao = Column(Text)
    
    # Dados comerciais
    unidade = Column(String(10), nullable=False, default='m2')  # m2, m3, ml, un, kg, h, verba
    preco_base = Column(Numeric(10, 2), nullable=False, default=0.00)
    margem_lucro = Column(Numeric(5, 2), nullable=False, default=30.00)  # %
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativo')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    subservicos = relationship('SubServico', back_populates='servico_mestre', cascade='all, delete-orphan')
    
    # Administrador
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ServicoMestre {self.codigo}: {self.nome}>'
    
    @property
    def preco_final(self):
        """Calcula preço final com margem de lucro"""
        if self.preco_base:
            return float(self.preco_base) * (1 + float(self.margem_lucro) / 100)
        return 0.0
    
    @property
    def total_subservicos(self):
        """Conta quantos subserviços este serviço possui"""
        return len(self.subservicos)

class SubServico(db.Model):
    """Subserviços que compõem um serviço mestre"""
    __tablename__ = 'sub_servico'
    
    id = Column(Integer, primary_key=True)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    codigo = Column(String(20), nullable=False)  # Ex: SRV001.001
    nome = Column(String(100), nullable=False)   # Ex: "Soldagem de Viga Principal"
    descricao = Column(Text)
    
    # Dados técnicos
    unidade = Column(String(10), nullable=False, default='m2')
    quantidade_base = Column(Numeric(10, 2), nullable=False, default=1.00)  # Quantidade por unidade do serviço mestre
    preco_unitario = Column(Numeric(10, 2), nullable=False, default=0.00)
    
    # Dados de execução
    tempo_execucao = Column(Numeric(5, 2), default=0.00)  # Horas
    nivel_dificuldade = Column(String(20), default='medio')  # facil, medio, dificil
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativo')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    servico_mestre = relationship('ServicoMestre', back_populates='subservicos')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<SubServico {self.codigo}: {self.nome}>'
    
    @property
    def valor_total_base(self):
        """Calcula valor total baseado na quantidade base"""
        return float(self.quantidade_base) * float(self.preco_unitario)

class TabelaComposicao(db.Model):
    """Tabelas de composição de custos por tipo de estrutura"""
    __tablename__ = 'tabela_composicao'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados básicos
    nome = Column(String(100), nullable=False)  # Ex: "Galpão Industrial Padrão"
    descricao = Column(Text)
    tipo_estrutura = Column(String(50), nullable=False)  # galpao, edificio, ponte, etc.
    
    # Parâmetros técnicos
    area_minima = Column(Numeric(10, 2), default=0.00)  # m²
    area_maxima = Column(Numeric(10, 2), default=999999.99)  # m²
    altura_minima = Column(Numeric(5, 2), default=0.00)  # metros
    altura_maxima = Column(Numeric(5, 2), default=999.99)  # metros
    
    # Status e controle
    status = Column(String(20), nullable=False, default='ativa')
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    itens_composicao = relationship('ItemTabelaComposicao', back_populates='tabela', cascade='all, delete-orphan')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<TabelaComposicao {self.nome}>'
    
    @property
    def custo_total_m2(self):
        """Calcula custo total por m²"""
        return sum(item.valor_total for item in self.itens_composicao)

class ItemTabelaComposicao(db.Model):
    """Itens que compõem uma tabela de composição"""
    __tablename__ = 'item_tabela_composicao'
    
    id = Column(Integer, primary_key=True)
    tabela_composicao_id = Column(Integer, ForeignKey('tabela_composicao.id'), nullable=False)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    
    # Dados de composição
    quantidade = Column(Numeric(10, 2), nullable=False, default=1.00)  # Quantidade por m²
    percentual_aplicacao = Column(Numeric(5, 2), default=100.00)  # % do serviço aplicado
    
    # Ajustes específicos
    fator_multiplicador = Column(Numeric(5, 2), default=1.00)  # Multiplicador de preço
    observacoes = Column(Text)
    
    # Relacionamentos
    tabela = relationship('TabelaComposicao', back_populates='itens_composicao')
    servico_mestre = relationship('ServicoMestre')
    admin = relationship('Usuario', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ItemTabelaComposicao {self.servico_mestre.nome} - {self.quantidade}>'
    
    @property
    def valor_unitario_ajustado(self):
        """Preço unitário com fator multiplicador"""
        return self.servico_mestre.preco_final * float(self.fator_multiplicador)
    
    @property
    def valor_total(self):
        """Valor total do item na composição"""
        return float(self.quantidade) * self.valor_unitario_ajustado * (float(self.percentual_aplicacao) / 100)

# MODELS DE PROPOSTAS
class Proposta(db.Model):
    __tablename__ = 'propostas_comerciais'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column('numero_proposta', db.String(50), nullable=False)  # Mapeado para coluna numero_proposta no banco
    data_proposta = db.Column(db.Date, nullable=False, default=date.today)
    
    # Dados do Cliente
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)  # FK adicionada pela Migração 43
    cliente_nome = db.Column(db.String(255), nullable=False)
    cliente_telefone = db.Column(db.String(20))
    cliente_email = db.Column(db.String(255))
    cliente_endereco = db.Column(db.Text)
    
    # Dados da Proposta
    titulo = db.Column('assunto', db.String(255), nullable=True)  # Mapeado para coluna assunto no banco
    descricao = db.Column('objeto', db.Text, nullable=True)  # Mapeado para coluna objeto no banco
    documentos_referencia = db.Column(db.Text)
    
    # Condições
    prazo_entrega_dias = db.Column(db.Integer, default=90)
    observacoes_entrega = db.Column(db.Text)
    validade_dias = db.Column(db.Integer, default=7)
    percentual_nota_fiscal = db.Column(db.Numeric(5,2), default=13.5)

    # Bloco 3 — override opcional do BDI da empresa nesta proposta.
    # NULL = herda ConfiguracaoEmpresa (cascata proposta → empresa → 0).
    bdi_ac_pct = db.Column(db.Numeric(5, 2), nullable=True)
    bdi_seguro_pct = db.Column(db.Numeric(5, 2), nullable=True)
    bdi_risco_pct = db.Column(db.Numeric(5, 2), nullable=True)
    bdi_garantia_pct = db.Column(db.Numeric(5, 2), nullable=True)
    bdi_desp_financeiras_pct = db.Column(db.Numeric(5, 2), nullable=True)

    # Condições de Pagamento
    condicoes_pagamento = db.Column(db.Text, default="""10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem""")
    
    # Garantias e Considerações
    garantias = db.Column(db.Text, default="""A empresa garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.""")
    consideracoes_gerais = db.Column(db.Text, default="""Modificações nesta proposta somente serão válidas por escrito e com aceite mútuo. Em caso de cancelamento do contrato pela contratante, será cobrada multa de 30% sobre o valor total.""")
    
    # Itens Inclusos/Exclusos (JSON)
    itens_inclusos = db.Column(JSON, default=[
        "Mão de obra para execução dos serviços",
        "Todos os equipamentos de segurança necessários",
        "Transporte e alimentação da equipe",
        "Container para guarda de ferramentas",
        "Movimentação de carga (Munck)",
        "Transporte dos materiais"
    ])
    
    itens_exclusos = db.Column(JSON, default=[
        "Projeto e execução de qualquer obra civil, fundações, alvenarias, elétrica, automação, tubulações etc.",
        "Execução de ensaios destrutivos e radiográficos",
        "Fornecimento de local para armazenagem das peças",
        "Fornecimento e/ou serviços não especificados claramente nesta proposta",
        "Fornecimento de escoramento (escoras)",
        "Fornecimento de andaimes e plataformas",
        "Técnico de segurança",
        "Pintura final de acabamento",
        "Calhas, rufos, condutores e pingadeiras"
    ])
    
    # Status
    status = db.Column(db.String(50), default='rascunho')  # rascunho, enviada, aprovada, rejeitada
    token_cliente = db.Column(db.String(100), unique=True)
    data_envio = db.Column(db.DateTime)
    data_resposta_cliente = db.Column(db.DateTime)
    observacoes_cliente = db.Column(db.Text)
    
    # Valores
    valor_total = db.Column(db.Numeric(15,2), default=0)
    
    # Metadados
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Integração com Obras
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    convertida_em_obra = db.Column(db.Boolean, default=False)

    # Task #115 — origem (Orçamento interno que gerou esta proposta), 1→N
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id', ondelete='SET NULL'),
                             nullable=True, index=True)

    # Task #173 — engenheiro responsável (override do padrão da empresa por proposta)
    engenheiro_id = db.Column(db.Integer, db.ForeignKey('engenheiro_responsavel.id', ondelete='SET NULL'),
                              nullable=True, index=True)

    # Task #102 — snapshot do cronograma revisado pelo admin antes de aprovar.
    # Estrutura: lista de Serviços, cada um com filhos (grupos/subatividades),
    # com flag `marcado` por nó. Usado pelo portal do cliente como fonte da verdade.
    cronograma_default_json = db.Column(JSON, nullable=True)

    # Task #31 — versionamento de propostas: cada vez que uma proposta já
    # enviada é "editada", criamos uma nova Proposta (v2, v3...) ligada via
    # proposta_origem_id, e marcamos a anterior como substituída. v1 = original.
    versao = db.Column(db.Integer, nullable=False, default=1)
    proposta_origem_id = db.Column(
        db.Integer, db.ForeignKey('propostas_comerciais.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    substituida_por_id = db.Column(
        db.Integer, db.ForeignKey('propostas_comerciais.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    substituida_em = db.Column(db.DateTime, nullable=True)

    # Task #23 — nota de validação escrita pelo supervisor (sem mudar o fluxo
    # de aprovação — apenas campo de texto livre para comunicação interna).
    observacao_validacao = db.Column(db.Text, nullable=True)

    # Task #31 — template aplicado na geração (informativo + base de comparação
    # na revisão). NULL = proposta sem template (editada manualmente).
    proposta_template_id = db.Column(
        db.Integer, db.ForeignKey('proposta_templates.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    # Task #31 — lista de chaves de campos vindos do template que ainda
    # precisam de revisão pelo admin antes do envio. Strings tipo
    # 'prazo_entrega_dias', 'validade_dias', 'itens_inclusos',
    # 'itens_exclusos', 'texto_apresentacao'. Cláusulas têm seu próprio
    # marker (PropostaClausula.revisado_em). Quando vazia AND todas as
    # cláusulas têm revisado_em != NULL, a proposta pode ser enviada.
    campos_pendentes_revisao = db.Column(JSON, nullable=True, default=list)

    # Relacionamentos
    cliente = db.relationship('Cliente', backref='propostas')
    itens = db.relationship('PropostaItem', backref='proposta', lazy=True, cascade='all, delete-orphan')
    arquivos = db.relationship('PropostaArquivo', backref='proposta', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Proposta, self).__init__(**kwargs)
        if not self.numero:
            self.numero = self.gerar_numero_proposta()
        if not self.token_cliente:
            self.token_cliente = secrets.token_urlsafe(32)
    
    def gerar_numero_proposta(self):
        """Gera número sequencial da proposta"""
        ano_atual = date.today().year
        # Contar propostas do ano atual
        count = db.session.query(func.count(Proposta.id)).filter(
            func.extract('year', Proposta.data_proposta) == ano_atual
        ).scalar() or 0
        
        proximo_numero = count + 1
        return f"{proximo_numero:03d}.{str(ano_atual)[-2:]}"
    
    def calcular_valor_total(self):
        """Calcula o valor total da proposta"""
        total = sum(float(item.subtotal) for item in self.itens)
        self.valor_total = total
        return total
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'data_proposta': self.data_proposta.isoformat() if self.data_proposta else None,
            'cliente_nome': self.cliente_nome,
            'cliente_telefone': self.cliente_telefone,
            'cliente_email': self.cliente_email,
            'titulo': self.titulo,
            'status': self.status,
            'valor_total': float(self.valor_total) if self.valor_total else 0,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

    # ────────── Task #31 — versionamento e revisão ──────────
    def cadeia_versoes(self):
        """Retorna lista ordenada de todas as Propostas dessa cadeia de versões.

        v1 → v2 → v3 ...; segue ``proposta_origem_id`` para trás até a raiz e
        ``substituida_por_id`` para frente até a versão mais recente.
        Inclui a própria proposta atual. Em caso de ciclo (defensivo) ou
        chains profundas, limita a 50 nós.
        """
        # Raiz (v1)
        raiz = self
        seen = {self.id}
        while raiz.proposta_origem_id and len(seen) < 50:
            anterior = Proposta.query.get(raiz.proposta_origem_id)
            if not anterior or anterior.id in seen:
                break
            seen.add(anterior.id)
            raiz = anterior
        # Caminhar para frente
        chain = [raiz]
        cur = raiz
        seen = {raiz.id}
        while cur.substituida_por_id and len(seen) < 50:
            prox = Proposta.query.get(cur.substituida_por_id)
            if not prox or prox.id in seen:
                break
            seen.add(prox.id)
            chain.append(prox)
            cur = prox
        return chain

    def clausulas_pendentes_revisao(self):
        """Lista PropostaClausulas que ainda têm ``revisado_em`` NULL."""
        return [c for c in (self.clausulas or []) if c.revisado_em is None]

    def pode_enviar(self):
        """Task #31 — True se a proposta pode ser enviada (status rascunho e
        nenhum item de revisão pendente)."""
        if (self.status or '').lower() != 'rascunho':
            return False
        if self.campos_pendentes_revisao:
            return False
        if self.clausulas_pendentes_revisao():
            return False
        return True


class PropostaHistorico(db.Model):
    __tablename__ = 'proposta_historico'
    
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Ação realizada: 'criada', 'editada', 'enviada', 'aprovada', 'rejeitada', 'excluida'
    acao = db.Column(db.String(50), nullable=False)
    observacao = db.Column(db.Text, nullable=True)  # Alias para descricao (mantido para compatibilidade)
    
    # Campos adicionados pela Migração 43 para auditoria detalhada
    campo_alterado = db.Column(db.String(100))  # Nome do campo que foi alterado
    valor_anterior = db.Column(db.Text)  # Valor antes da alteração
    valor_novo = db.Column(db.Text)  # Valor após a alteração
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))  # Multi-tenant
    
    # Timestamps
    data_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    proposta = db.relationship('Proposta', backref='historico')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='acoes_em_propostas')

class PropostaItem(db.Model):
    __tablename__ = 'proposta_itens'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    item_numero = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(db.Numeric(10,3), nullable=False)
    unidade = db.Column(db.String(10), nullable=False)
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    
    # Novos campos para organização avançada
    categoria_titulo = db.Column(db.String(100))  # Título personalizado da categoria (ex: "PROJETO", "ESTRUTURA METÁLICA")
    template_origem_id = db.Column(db.Integer, db.ForeignKey('proposta_templates.id'))  # Template de origem
    template_origem_nome = db.Column(db.String(100))  # Nome do template quando foi carregado
    grupo_ordem = db.Column(db.Integer, default=1)  # Ordem do grupo/categoria
    item_ordem_no_grupo = db.Column(db.Integer, default=1)  # Ordem do item dentro do grupo

    # Task #82 — vínculo com catálogo de serviços (opcional, snapshot fica em preco_unitario)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=True, index=True)

    # Fase 0.6 / D1 — linhagem entre versões da proposta.
    # Criar uma revisão CLONA os itens com ids novos. Sem este vínculo, a
    # propagação proposta→obra não tinha como saber que o item da v2 é o
    # MESMO item da v1, e criava um segundo ItemMedicaoComercial em vez de
    # atualizar o existente: um aditivo de +20% virava +100% de itens.
    # NULL no item original (v1) e nos itens acrescentados pela revisão.
    proposta_item_origem_id = db.Column(
        db.Integer, db.ForeignKey('proposta_itens.id'), nullable=True,
        index=True)

    # Task #89 — snapshot do cálculo paramétrico (explosão de insumos)
    quantidade_medida = db.Column(db.Numeric(15, 4), nullable=True)
    custo_unitario = db.Column(db.Numeric(15, 4), nullable=True)
    lucro_unitario = db.Column(db.Numeric(15, 4), nullable=True)
    subtotal = db.Column(db.Numeric(15, 2), nullable=True)

    # Task #118 — override de cronograma e snapshot da composição efetiva
    # propagados a partir do OrcamentoItem que originou esta linha. NULL no
    # override significa "usar o template padrão do serviço (Servico.template_padrao_id)".
    cronograma_template_override_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_template.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    composicao_snapshot = db.Column(JSON, nullable=True)

    # Task #18 — inclusos/exclusos POR ITEM (texto livre, uma linha por item)
    # propagados a partir do OrcamentoItem em gerar_proposta. Diferentes do
    # campo Proposta.itens_inclusos/itens_exclusos (que é por proposta inteira).
    itens_inclusos = db.Column(db.Text)
    itens_exclusos = db.Column(db.Text)

    # Task #36 — medição dimensional propagada do OrcamentoItem
    tipo_medicao_override = db.Column(db.String(30), nullable=True)
    dim_largura      = db.Column(db.Numeric(15, 4), nullable=True)
    dim_comprimento  = db.Column(db.Numeric(15, 4), nullable=True)
    dim_perimetro    = db.Column(db.Numeric(15, 4), nullable=True)
    dim_pe_direito   = db.Column(db.Numeric(15, 4), nullable=True)
    dim_area_manual  = db.Column(db.Numeric(15, 4), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento com template (opcional)
    template_origem = db.relationship('PropostaTemplate', backref='itens_utilizados')
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    cronograma_template_override = db.relationship(
        'CronogramaTemplate', foreign_keys=[cronograma_template_override_id]
    )

    @property
    def subtotal_calculado(self):
        """Subtotal efetivo: persistido (snapshot) ou fallback qty×preço."""
        if self.subtotal is not None:
            return self.subtotal
        try:
            return (self.quantidade or 0) * (self.preco_unitario or 0)
        except Exception:
            return 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'item_numero': self.item_numero,
            'descricao': self.descricao,
            'quantidade': float(self.quantidade),
            'unidade': self.unidade,
            'preco_unitario': float(self.preco_unitario),
            'subtotal': float(self.subtotal),
            'ordem': self.ordem,
            'categoria_titulo': self.categoria_titulo,
            'template_origem_id': self.template_origem_id,
            'template_origem_nome': self.template_origem_nome,
            'grupo_ordem': self.grupo_ordem,
            'item_ordem_no_grupo': self.item_ordem_no_grupo
        }

class PropostaClausula(db.Model):
    """Task #174 — cláusula textual configurável de uma Proposta.

    Cada Proposta carrega uma lista ordenada de cláusulas (título + texto +
    ordem). Cláusula com ``texto`` vazio é considerada removida e não
    aparece no PDF nem no portal do cliente. Substitui os campos fixos
    ``condicoes_pagamento``, ``garantias`` e ``consideracoes_gerais`` no
    nível de renderização — esses campos são mantidos inertes em
    ``Proposta`` para rollback seguro.
    """
    __tablename__ = 'proposta_clausula'

    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(
        db.Integer,
        db.ForeignKey('propostas_comerciais.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    titulo = db.Column(db.String(200), nullable=False, default='')
    texto = db.Column(db.Text, nullable=False, default='')
    ordem = db.Column(db.Integer, nullable=False, default=1)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow,
                              onupdate=datetime.utcnow)

    # Task #31 — marcador de revisão. NULL = vinda de template e ainda não
    # revisada pelo admin (precisa marcar antes de enviar). Quando o admin
    # marca como "revisada" (checkbox no editor) ou edita o texto via UI,
    # registramos o timestamp aqui.
    revisado_em = db.Column(db.DateTime, nullable=True)

    proposta = db.relationship(
        'Proposta',
        backref=db.backref(
            'clausulas',
            order_by='PropostaClausula.ordem',
            cascade='all, delete-orphan',
            lazy='select',
        ),
    )


class PropostaTemplateClausula(db.Model):
    """Task #174 — cláusula textual configurável de um PropostaTemplate.

    Estrutura espelha :class:`PropostaClausula`. Quando uma nova proposta
    é gerada a partir do template, a lista de cláusulas é copiada
    integralmente (preservando ordem e título).
    """
    __tablename__ = 'proposta_template_clausula'

    id = db.Column(db.Integer, primary_key=True)
    proposta_template_id = db.Column(
        db.Integer,
        db.ForeignKey('proposta_templates.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    titulo = db.Column(db.String(200), nullable=False, default='')
    texto = db.Column(db.Text, nullable=False, default='')
    ordem = db.Column(db.Integer, nullable=False, default=1)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow,
                              onupdate=datetime.utcnow)

    template = db.relationship(
        'PropostaTemplate',
        backref=db.backref(
            'clausulas',
            order_by='PropostaTemplateClausula.ordem',
            cascade='all, delete-orphan',
            lazy='select',
        ),
    )


class PropostaArquivo(db.Model):
    __tablename__ = 'proposta_arquivos'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas_comerciais.id'), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    tipo_arquivo = db.Column(db.String(100))
    tamanho_bytes = db.Column(db.BigInteger)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    categoria = db.Column(db.String(50))  # 'dwg', 'pdf', 'imagem', 'documento', 'outros'
    
    # [READY] ARMAZENAMENTO PERSISTENTE (v9.4.0) - Base64 no banco de dados
    # Solução: Arquivos persistem mesmo após deploys/restarts do container
    # - Imagens: 3 versões otimizadas (original, 1200px, 300px thumbnail)
    # - Outros arquivos (<5MB): base64 direto
    arquivo_base64 = db.Column(db.Text)  # Para PDFs/DWG/DOC pequenos (<5MB)
    imagem_original_base64 = db.Column(db.Text)  # Imagem original completa
    imagem_otimizada_base64 = db.Column(db.Text)  # Imagem otimizada 1200px WebP
    thumbnail_base64 = db.Column(db.Text)  # Thumbnail 300px para preview
    
    enviado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_original': self.nome_original,
            'tipo_arquivo': self.tipo_arquivo,
            'tamanho_bytes': self.tamanho_bytes,
            'categoria': 'operacional',  # Default value since categoria was removed
            'enviado_em': self.enviado_em.isoformat() if self.enviado_em else None
        }

class PropostaTemplate(db.Model):
    """Templates reutilizáveis para propostas com itens padrão pré-configurados"""
    __tablename__ = 'proposta_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(50), nullable=False)  # Ex: "Estrutura Metálica", "Mezanino", "Cobertura"
    
    # Itens padrão do template (JSON)
    itens_padrao = db.Column(JSON, default=[])  # Array de itens padrão para este template
    
    # Configurações padrão do template
    prazo_entrega_dias = db.Column(db.Integer, default=90)
    validade_dias = db.Column(db.Integer, default=7)
    percentual_nota_fiscal = db.Column(db.Numeric(5,2), default=13.5)
    
    # CAMPOS COMPLETOS DO TEMPLATE - PRIMEIRA PÁGINA ATÉ PONTO 9
    # Dados do cliente (primeira página)
    # Task #162 — sem default hard-coded de cidade. O template renderiza
    # apenas o que estiver configurado pelo tenant.
    cidade_data = db.Column(db.String(200), default='')
    destinatario = db.Column(db.String(200))  # "À [Nome do Cliente]"
    atencao_de = db.Column(db.String(200))    # "A/c.: [Responsável]"
    telefone_cliente = db.Column(db.String(50)) # "12 98111-0980"
    assunto = db.Column(db.Text)              # "Ass.: Fabricação e montagem de estrutura metálica."
    numero_referencia = db.Column(db.String(100)) # "N. Ref.: Proposta Comercial 333-25 – Estrutura Metálica"
    
    # Texto de apresentação
    texto_apresentacao = db.Column(db.Text, default="""Prezados,

Atendendo a solicitação de V.sas., apresentamos nossas "Condições Comerciais" para o fornecimento em referência.

Na expectativa de ter atendido às condições especificadas, aproveitamos para expressar os nossos votos de estima e consideração.

Atenciosamente,
""")
    
    # Dados do engenheiro responsável (rodapé/cabeçalho)
    # Task #162 — defaults zerados; nada de "Lucas Barbosa" hard-coded.
    # Para a fonte real do engenheiro use EngenheiroResponsavel
    # (Task #173) via services.engenheiro_service.obter_engenheiro_dados.
    engenheiro_nome = db.Column(db.String(200), default='')
    engenheiro_crea = db.Column(db.String(50), default='')
    engenheiro_email = db.Column(db.String(120), default='')
    engenheiro_telefone = db.Column(db.String(50), default='')
    engenheiro_endereco = db.Column(db.Text, default='')
    engenheiro_website = db.Column(db.String(200), default='')
    
    # Itens inclusos e exclusos
    itens_inclusos = db.Column(db.Text)
    itens_exclusos = db.Column(db.Text)
    condicoes = db.Column(db.Text)
    
    # Condições padrão
    condicoes_pagamento = db.Column(db.Text, default="""10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem""")
    
    # Garantias padrão
    garantias = db.Column(db.Text, default="""A empresa garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.""")
    
    # SEÇÕES COMPLETAS DA PROPOSTA (1-9)
    secao_objeto = db.Column(db.Text, default="""Esta proposta descreve as condições comerciais a serem atendidas para o fornecimento de mão de obra especializada para fabricação e montagem de estruturas conforme segue.""")
    condicoes_entrega = db.Column(db.Text, default="""Prazo de entrega de 90 dias corridos após aprovação do projeto executivo e recebimento da primeira parcela.

O prazo poderá ser alterado em função de condições climáticas adversas.""")
    consideracoes_gerais = db.Column(db.Text, default="""8.1 Modificações e Cancelamentos
Qualquer alteração no escopo do projeto deverá ser previamente aprovada por escrito, podendo resultar em ajustes nos prazos e valores.

8.2 Obrigações do Contratante
O contratante deverá fornecer energia elétrica, água potável e local adequado para estoque temporário dos materiais.

8.3 Água e Energia
Por conta do contratante o fornecimento de água e energia elétrica durante o período de execução da obra.""")
    secao_validade = db.Column(db.Text, default="""Esta proposta tem validade de 7 (sete) dias corridos a partir da data de emissão.""")
    
    # Status e controle
    ativo = db.Column(db.Boolean, default=True)
    publico = db.Column(db.Boolean, default=False)  # Se pode ser usado por outros usuários
    uso_contador = db.Column(db.Integer, default=0)  # Quantas vezes foi usado

    # Task #47 — flag de "template padrão" do tenant. Apenas UM template por
    # admin pode estar marcado como padrão (índice parcial único na tabela).
    # Quando o admin clica em "Novo Template", o formulário abre pré-preenchido
    # com todos os campos ricos copiados deste template padrão.
    padrao = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relacionamentos
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PropostaTemplate {self.nome}>'
    
    def incrementar_uso(self):
        """Incrementa o contador de uso do template"""
        self.uso_contador += 1
        db.session.commit()
    
    def duplicar(self, nome_novo, admin_id, criado_por):
        """Cria uma cópia do template"""
        novo_template = PropostaTemplate(
            nome=nome_novo,
            descricao=f"Cópia de: {self.descricao}" if self.descricao else None,
            categoria=self.categoria,
            itens_padrao=self.itens_padrao.copy() if self.itens_padrao else [],
            prazo_entrega_dias=self.prazo_entrega_dias,
            validade_dias=self.validade_dias,
            percentual_nota_fiscal=self.percentual_nota_fiscal,
            condicoes_pagamento=self.condicoes_pagamento,
            garantias=self.garantias,
            admin_id=admin_id,
            criado_por=criado_por
        )
        
        db.session.add(novo_template)
        return novo_template
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'categoria': 'operacional',  # Default value since categoria was removed
            'itens_padrao': self.itens_padrao or [],
            'prazo_entrega_dias': self.prazo_entrega_dias,
            'validade_dias': self.validade_dias,
            'percentual_nota_fiscal': float(self.percentual_nota_fiscal) if self.percentual_nota_fiscal else 0,
            'itens_inclusos': self.itens_inclusos,
            'itens_exclusos': self.itens_exclusos,
            'condicoes': self.condicoes,
            'condicoes_pagamento': self.condicoes_pagamento,
            'garantias': self.garantias,
            'ativo': self.ativo,
            'publico': self.publico,
            'uso_contador': self.uso_contador,
            'total_itens': len(self.itens_padrao) if self.itens_padrao else 0,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

# Catálogo de Serviços para Templates
class ServicoTemplate(db.Model):
    """Catálogo de serviços/atividades para usar em templates"""
    __tablename__ = 'servico_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Ex: EST-001, MEZ-002
    nome = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    subcategoria = db.Column(db.String(50))
    
    # Especificações padrão
    unidade_padrao = db.Column(db.String(10), nullable=False)  # m², kg, ton, m, un
    preco_referencia = db.Column(db.Numeric(10,2))
    
    # Descrição técnica
    descricao_tecnica = db.Column(db.Text)
    especificacoes = db.Column(db.Text)
    
    # Tags para busca
    tags = db.Column(db.String(500))  # palavras-chave separadas por vírgula
    
    # Status
    ativo = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Task #173 — Cadastro próprio de Engenheiros Responsáveis
class EngenheiroResponsavel(db.Model):
    """Engenheiro responsável que assina propostas (rodapé/PDF).

    Substitui o conjunto de campos engenheiro_* em ConfiguracaoEmpresa,
    que permanecem como fallback. Cada admin pode cadastrar múltiplos
    engenheiros e definir um padrão na ConfiguracaoEmpresa; cada Proposta
    pode opcionalmente sobrescrever o padrão.
    """
    __tablename__ = 'engenheiro_responsavel'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)

    nome = db.Column(db.String(200), nullable=False)
    crea = db.Column(db.String(50), default='')
    email = db.Column(db.String(120), default='')
    telefone = db.Column(db.String(50), default='')
    endereco = db.Column(db.Text, default='')
    website = db.Column(db.String(200), default='')

    # Imagem de assinatura opcional (data URI base64)
    assinatura_base64 = db.Column(db.Text, default='')

    ativo = db.Column(db.Boolean, default=True, nullable=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<EngenheiroResponsavel {self.nome} (CREA {self.crea})>'

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'crea': self.crea or '',
            'email': self.email or '',
            'telefone': self.telefone or '',
            'endereco': self.endereco or '',
            'website': self.website or '',
            'assinatura_base64': self.assinatura_base64 or '',
            'ativo': bool(self.ativo),
        }


# Configurações da Empresa
class ConfiguracaoEmpresa(db.Model):
    """Configurações centrais da empresa para reutilização em propostas"""
    __tablename__ = 'configuracao_empresa'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, nullable=False)  # Removido foreign key para evitar problemas em produção
    
    # Dados da empresa
    nome_empresa = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20))
    endereco = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    logo_url = db.Column(db.String(500))
    logo_base64 = db.Column(db.Text)  # Logo em base64 para upload direto
    logo_pdf_base64 = db.Column(db.Text)  # Logo específica para PDFs
    header_pdf_base64 = db.Column(db.Text)  # Header completo para PDFs (substitui logo no cabeçalho)
    
    # Personalização visual
    cor_primaria = db.Column(db.String(7), default='#007bff')  # Cor primária em hexadecimal (legado p/ PDF)
    cor_secundaria = db.Column(db.String(7), default='#6c757d')  # Cor secundária (legado p/ PDF)
    cor_fundo_proposta = db.Column(db.String(7), default='#f8f9fa')  # Cor de fundo das propostas
    logo_tamanho_portal = db.Column(db.String(20), default='medio')  # Tamanho da logo no portal: pequeno, medio, grande

    # Task #191 — Tema do Sistema (refresh visual SaaS)
    cor_header_nav = db.Column(db.String(7), default='#1e293b')  # Cor de fundo do header/navbar
    cor_fundo_app = db.Column(db.String(7), default='#f8fafc')   # Cor de fundo da aplicação
    tema_preset = db.Column(db.String(40), default='azul_profundo')  # Identificador do preset ativo

    # Cronograma-mpp M10 — flag de rollout da importação de cronograma por
    # tenant. Default FALSE: liga-se por fase (scripts/flag_cronograma_mpp.py).
    cronograma_mpp_ativo = db.Column(db.Boolean, nullable=False, default=False,
                                     server_default='false')

    # Fase 1 — rollout do escopo por obra, por tenant. Desligada por
    # padrão: com FALSE o comportamento é idêntico ao de antes da Fase 1
    # (não-admin enxerga todas as obras do tenant). Ligar só depois de
    # popular usuario_obra para o tenant, senão o pessoal de campo perde
    # acesso. Mesmo padrão de cronograma_mpp_ativo (migration 211).
    escopo_obra_ativo = db.Column(db.Boolean, nullable=False, default=False,
                                  server_default='false')

    # Fase 3 — flag de rollout da governança de compras, por tenant.
    # Default FALSE: com ela desligada, `compras.nova_post` registra compra
    # exatamente como antes (compras_views.py:709-711) e as telas de
    # requisição existem como caminho OPCIONAL. Ligada, pedido sem
    # requisição aprovada é recusado. Liga-se por
    # scripts/flag_compras_governanca.py. Irmã de cronograma_mpp_ativo
    # (acima) e de escopo_obra_ativo (Fase 1).
    compras_governanca_ativa = db.Column(db.Boolean, nullable=False,
                                         default=False, server_default='false')

    # REMOVIDO: Campos transferidos para PropostaTemplate para evitar conflitos
    # itens_inclusos_padrao, itens_exclusos_padrao, condicoes_padrao, 
    # condicoes_pagamento_padrao, garantias_padrao, observacoes_gerais_padrao
    
    # Bloco de assinatura padrão da proposta
    assinatura_nome = db.Column(db.String(200), default='')
    assinatura_cargo = db.Column(db.String(200), default='')

    # Task #178 — Engenheiro responsável: a única fonte de verdade é
    # EngenheiroResponsavel (cadastro próprio, Task #173). Os antigos
    # campos engenheiro_nome/crea/email/telefone/endereco/website foram
    # removidos do schema.
    engenheiro_padrao_id = db.Column(db.Integer,
                                     db.ForeignKey('engenheiro_responsavel.id', ondelete='SET NULL'),
                                     nullable=True)

    # Configurações padrão
    prazo_entrega_padrao = db.Column(db.Integer, default=90)
    validade_padrao = db.Column(db.Integer, default=7)
    percentual_nota_fiscal_padrao = db.Column(db.Numeric(5,2), default=13.5)
    # Task #82 — defaults de orçamento
    imposto_pct_padrao = db.Column(db.Numeric(5, 2), default=8.0)
    lucro_pct_padrao = db.Column(db.Numeric(5, 2), default=10.0)

    # Bloco 3 — BDI completo (padrão TCU). Componentes de custo indireto (% por dentro).
    # Default 0 → preço de catálogo não muda até a empresa preencher (não-disrupção).
    bdi_ac_pct = db.Column(db.Numeric(5, 2), default=0)               # Administração Central
    bdi_seguro_pct = db.Column(db.Numeric(5, 2), default=0)           # Seguro
    bdi_risco_pct = db.Column(db.Numeric(5, 2), default=0)            # Risco
    bdi_garantia_pct = db.Column(db.Numeric(5, 2), default=0)         # Garantia
    bdi_desp_financeiras_pct = db.Column(db.Numeric(5, 2), default=0)  # Despesas Financeiras
    # Guarda-corpo (D3): limiares de T+L para aviso e bloqueio.
    bdi_tl_aviso_pct = db.Column(db.Numeric(5, 2), default=60)
    bdi_tl_bloqueio_pct = db.Column(db.Numeric(5, 2), default=90)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConfiguracaoEmpresa {self.nome_empresa}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_empresa': self.nome_empresa,
            'cnpj': self.cnpj,
            'endereco': self.endereco,
            'telefone': self.telefone,
            'email': self.email,
            'website': self.website,
            'logo_url': self.logo_url,
            'logo_base64': self.logo_base64,
            'cor_primaria': self.cor_primaria,
            'cor_secundaria': self.cor_secundaria,
            'cor_fundo_proposta': self.cor_fundo_proposta,
            # Campos removidos - agora no template
            'prazo_entrega_padrao': self.prazo_entrega_padrao,
            'validade_padrao': self.validade_padrao,
            'percentual_nota_fiscal_padrao': float(self.percentual_nota_fiscal_padrao) if self.percentual_nota_fiscal_padrao else 13.5,
            'assinatura_nome': self.assinatura_nome or '',
            'assinatura_cargo': self.assinatura_cargo or '',
            # Task #178 — campos engenheiro_* removidos. Use
            # services.engenheiro_service.obter_engenheiro_dados.
            'engenheiro_padrao_id': self.engenheiro_padrao_id,
        }
    
    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'nome': self.nome,
            'categoria': 'operacional',  # Default value since categoria was removed
            'subcategoria': self.subcategoria,
            'unidade_padrao': self.unidade_padrao,
            'preco_referencia': float(self.preco_referencia) if self.preco_referencia else 0,
            'descricao_tecnica': self.descricao_tecnica,
            'especificacoes': self.especificacoes,
            'tags': self.tags.split(',') if self.tags else [],
            'ativo': self.ativo
        }
    
    @classmethod
    def buscar_por_texto(cls, texto, admin_id):
        """Busca serviços por texto em nome, descrição e tags"""
        return cls.query.filter(
            cls.admin_id == admin_id,
            cls.ativo == True,
            db.or_(
                cls.nome.ilike(f'%{texto}%'),
                cls.descricao_tecnica.ilike(f'%{texto}%'),
                cls.tags.ilike(f'%{texto}%')
            )
        ).all()
    
    @classmethod
    def por_categoria(cls, categoria, admin_id):
        """Retorna serviços por categoria"""
        return cls.query.filter(
            cls.admin_id == admin_id,
            cls.categoria == categoria,
            cls.ativo == True
        ).order_by(cls.nome).all()

# ================================
# MÓDULO DE GESTÃO DE EQUIPE - LEAN & EFICIENTE
# ================================

class Allocation(db.Model):
    """Alocação de obra por dia - Tela A (Obras→Dias)
    
    Cada registro representa UMA OBRA alocada em UM DIA específico.
    Ex: UNO PTO na Segunda-feira das 08:00 às 17:00
    """
    __tablename__ = 'allocation'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    data_alocacao = db.Column(db.Date, nullable=False)
    turno_inicio = db.Column(db.Time, default=time(8, 0))  # 08:00
    turno_fim = db.Column(db.Time, default=time(17, 0))    # 17:00
    local_trabalho = db.Column(db.String(20), default='campo')  # 'campo' ou 'oficina'
    nota = db.Column(db.String(100))  # Observação curta
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='allocations')
    admin = db.relationship('Usuario', backref='allocations')
    funcionarios = db.relationship('AllocationEmployee', backref='allocation', cascade='all, delete-orphan')
    
    # Constraint de integridade: uma obra não pode ser alocada duas vezes no mesmo dia/local
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'obra_id', 'data_alocacao', 'local_trabalho', name='uk_allocation_admin_obra_data_local'),
        db.Index('idx_allocation_admin_data', 'admin_id', 'data_alocacao'),
        db.Index('idx_allocation_obra_data', 'obra_id', 'data_alocacao'),
        db.Index('idx_allocation_local', 'local_trabalho'),
    )
    
    def __repr__(self):
        return f'<Allocation {self.obra.nome} - {self.data_alocacao}>'
    
    @property
    def funcionarios_count(self):
        """Quantos funcionários estão alocados nesta obra/dia"""
        return len(self.funcionarios)

class AllocationEmployee(db.Model):
    """Funcionários alocados em obra/dia - Tela B (Pessoas→Obra)
    
    Cada registro é UM FUNCIONÁRIO trabalhando em uma alocação específica.
    Ex: João Silva trabalhando no UNO PTO na Segunda das 08:00-12:00 como soldador
    """
    __tablename__ = 'allocation_employee'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    allocation_id = db.Column(db.Integer, db.ForeignKey('allocation.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    turno_inicio = db.Column(db.Time, default=time(8, 0))
    turno_fim = db.Column(db.Time, default=time(17, 0))
    papel = db.Column(db.String(50))  # Ex: "soldador", "ajudante", "líder"
    observacao = db.Column(db.String(100))  # Obs específica do funcionário
    
    # Campos de horário de almoço
    hora_almoco_saida = db.Column(db.Time, default=time(12, 0))     # 12:00
    hora_almoco_retorno = db.Column(db.Time, default=time(13, 0))   # 13:00
    
    # Campo de percentual de extras
    percentual_extras = db.Column(db.Float, default=0.0)  # 0% por padrão
    
    # Campos para integração com ponto
    tipo_lancamento = db.Column(db.String(30), default='trabalho_normal')  # trabalho_normal, sabado_trabalhado, domingo_trabalhado, falta, sabado_folga, domingo_folga, feriado_folga
    sincronizado_ponto = db.Column(db.Boolean, default=False)  # Se já foi sincronizado com RegistroPonto
    data_sincronizacao = db.Column(db.DateTime)  # Quando foi sincronizado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='allocations')
    
    # CONSTRAINT ÚNICO CRÍTICO PARA SEGURANÇA - EVITA DUPLICAÇÃO
    __table_args__ = (db.UniqueConstraint('allocation_id', 'funcionario_id', name='_allocation_employee_uc'),)
    
    def __repr__(self):
        return f'<AllocationEmployee {self.funcionario.nome} - {self.allocation.obra.nome}>'
    
    def has_conflict_with_date(self, target_date):
        """Verifica se funcionário tem conflito em outra obra na mesma data"""
        from sqlalchemy import and_
        conflicts = AllocationEmployee.query.join(Allocation).filter(
            and_(
                AllocationEmployee.funcionario_id == self.funcionario_id,
                Allocation.data_alocacao == target_date,
                AllocationEmployee.id != self.id
            )
        ).count()
        return conflicts > 0
    
    @property
    def deve_gerar_ponto(self):
        """Verifica se deve gerar registro de ponto automaticamente"""
        return not self.sincronizado_ponto

    def get_tipo_lancamento_automatico(self, data_alocacao=None):
        """Determina tipo de lançamento baseado no dia da semana
        
        Args:
            data_alocacao (date, optional): Data da alocação. Se não fornecida, usa self.allocation.data_alocacao
        """
        from app import db
        
        # Usar parâmetro se fornecido, senão tentar usar relacionamento
        if data_alocacao:
            target_date = data_alocacao
        elif self.allocation:
            target_date = self.allocation.data_alocacao
        else:
            # Fallback: tentar carregar allocation manualmente
            try:
                allocation = db.session.query(Allocation).filter_by(id=self.allocation_id).first()
                if allocation:
                    target_date = allocation.data_alocacao
                else:
                    # Se não conseguir carregar, assumir dia útil como padrão
                    return 'trabalho_normal'
            except:
                return 'trabalho_normal'
        
        dia_semana = target_date.weekday()  # 0=Monday, 6=Sunday
        
        if dia_semana < 5:  # Segunda a Sexta (0-4)
            return 'trabalho_normal'
        elif dia_semana == 5:  # Sábado
            return 'sabado_trabalhado'
        else:  # Domingo
            return 'domingo_trabalhado'

    def sincronizar_com_ponto(self):
        """Cria registro de ponto baseado na alocação"""
        from app import db
        from datetime import datetime
        
        # Verificar se já existe registro
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=self.funcionario_id,
            data=self.allocation.data_alocacao
        ).first()
        
        if registro_existente:
            # Atualizar registro existente
            registro_existente.obra_id = self.allocation.obra_id
            registro_existente.tipo_local = self.allocation.local_trabalho
            registro_existente.hora_entrada = self.turno_inicio
            registro_existente.hora_saida = self.turno_fim
            # Sincronizar novos campos de almoço e percentual
            if hasattr(registro_existente, 'hora_almoco_saida'):
                registro_existente.hora_almoco_saida = self.hora_almoco_saida
            if hasattr(registro_existente, 'hora_almoco_retorno'):
                registro_existente.hora_almoco_retorno = self.hora_almoco_retorno
            if hasattr(registro_existente, 'percentual_extras'):
                registro_existente.percentual_extras = self.percentual_extras
            if hasattr(registro_existente, 'tipo_registro'):
                registro_existente.tipo_registro = self.tipo_lancamento
            # Recalcular horas trabalhadas com os novos campos
            registro_existente.horas_trabalhadas = self._calcular_horas_trabalhadas()
        else:
            # Criar novo registro
            registro = RegistroPonto(
                funcionario_id=self.funcionario_id,
                obra_id=self.allocation.obra_id,
                data=self.allocation.data_alocacao,
                hora_entrada=self.turno_inicio,
                hora_saida=self.turno_fim,
                tipo_local=self.allocation.local_trabalho,
                horas_trabalhadas=self._calcular_horas_trabalhadas()
            )
            # Adicionar novos campos se disponíveis no modelo RegistroPonto
            if hasattr(registro, 'hora_almoco_saida'):
                registro.hora_almoco_saida = self.hora_almoco_saida
            if hasattr(registro, 'hora_almoco_retorno'):
                registro.hora_almoco_retorno = self.hora_almoco_retorno
            if hasattr(registro, 'percentual_extras'):
                registro.percentual_extras = self.percentual_extras
            if hasattr(registro, 'tipo_registro'):
                registro.tipo_registro = self.tipo_lancamento
            db.session.add(registro)
        
        # Marcar como sincronizado
        self.sincronizado_ponto = True
        self.data_sincronizacao = datetime.utcnow()
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao sincronizar ponto: {e}")
            return False

    def _calcular_horas_trabalhadas(self):
        """Calcula horas trabalhadas baseado no turno, considerando intervalo de almoço"""
        from datetime import datetime, date
        
        if not (self.turno_inicio and self.turno_fim):
            return 8.0  # Padrão
        
        # Converter para datetime para cálculos
        hoje = date.today()
        inicio = datetime.combine(hoje, self.turno_inicio)
        fim = datetime.combine(hoje, self.turno_fim)
        
        # Calcular total de horas brutas
        delta_total = fim - inicio
        horas_brutas = delta_total.total_seconds() / 3600
        
        # Descontar intervalo de almoço se os horários estiverem definidos
        horas_almoco = 0.0
        if self.hora_almoco_saida and self.hora_almoco_retorno:
            saida_almoco = datetime.combine(hoje, self.hora_almoco_saida)
            retorno_almoco = datetime.combine(hoje, self.hora_almoco_retorno)
            
            # Verificar se o intervalo de almoço está dentro do horário de trabalho
            if saida_almoco >= inicio and retorno_almoco <= fim:
                delta_almoco = retorno_almoco - saida_almoco
                horas_almoco = delta_almoco.total_seconds() / 3600
        else:
            # Se não tiver horários de almoço definidos, usar padrão de 1 hora
            # apenas se o turno for maior que 6 horas (indicando jornada completa)
            if horas_brutas > 6.0:
                horas_almoco = 1.0
        
        # Calcular horas efetivamente trabalhadas
        horas_trabalhadas = horas_brutas - horas_almoco
        
        # Garantir que não seja negativo
        return max(0.0, horas_trabalhadas)

class WeeklyPlan(db.Model):
    """Planejamento semanal por obra - Tela C (opcional)
    
    Container para organizar atividades de uma obra durante uma semana.
    Ex: Semana 09/09 - Obra UNO PTO
    """
    __tablename__ = 'weekly_plan'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)  # Segunda-feira da semana
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    obra = db.relationship('Obra', backref='weekly_plans')
    admin = db.relationship('Usuario', backref='weekly_plans')
    items = db.relationship('WeeklyPlanItem', backref='weekly_plan', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<WeeklyPlan {self.obra.nome} - {self.week_start}>'

class WeeklyPlanItem(db.Model):
    """Atividades do planejamento semanal - Drag & drop de serviços
    
    Cada item é UMA ATIVIDADE planejada para um dia específico.
    Ex: Soldagem de vigas na Terça-feira das 14:00-18:00 com João como responsável
    """
    __tablename__ = 'weekly_plan_item'
    
    id = db.Column(db.Integer, primary_key=True)
    weekly_plan_id = db.Column(db.Integer, db.ForeignKey('weekly_plan.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Segunda, 1=Terça...4=Sexta
    responsavel_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    turno_inicio = db.Column(db.Time, default=time(8, 0))
    turno_fim = db.Column(db.Time, default=time(17, 0))
    nota_curta = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    servico = db.relationship('Servico', backref='weekly_plan_items')
    responsavel = db.relationship('Funcionario', backref='weekly_plan_items')
    
    def __repr__(self):
        return f'<WeeklyPlanItem {self.servico.nome} - Dia {self.day_of_week}>'

# ================================
# FUNÇÕES PARA LANÇAMENTO AUTOMÁTICO DE PONTO
# ================================

def processar_lancamentos_automaticos(data_processamento=None, admin_id=None):
    """
    Processa lançamentos automáticos de ponto para funcionários não alocados
    Deve ser executada via cron job à meia-noite
    IMPORTANTE: admin_id é obrigatório para isolamento multi-tenant
    """
    from app import db
    from datetime import date, timedelta
    
    if admin_id is None:
        raise ValueError("admin_id é obrigatório para isolamento multi-tenant")
    
    if data_processamento is None:
        data_processamento = date.today() - timedelta(days=1)  # Dia anterior
    
    # Buscar todos os funcionários ativos do admin específico
    funcionarios_ativos = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    for funcionario in funcionarios_ativos:
        # Verificar se funcionário foi alocado nesta data
        alocacao = db.session.query(AllocationEmployee).join(Allocation).filter(
            AllocationEmployee.funcionario_id == funcionario.id,
            Allocation.data_alocacao == data_processamento,
            Allocation.admin_id == admin_id  # CRÍTICO: Isolamento multi-tenant
        ).first()
        
        if alocacao:
            # Funcionário foi alocado - sincronizar se necessário
            if not alocacao.sincronizado_ponto:
                alocacao.sincronizar_com_ponto()
        else:
            # Funcionário NÃO foi alocado - gerar falta/folga
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_processamento
            ).first()
            
            if not registro_existente:
                tipo_registro = _determinar_tipo_falta(data_processamento)
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_processamento,
                    horas_trabalhadas=0.0
                )
                if hasattr(registro, 'tipo_registro'):
                    registro.tipo_registro = tipo_registro
                if hasattr(registro, 'observacoes'):
                    registro.observacoes = f'Lançamento automático - {tipo_registro}'
                db.session.add(registro)
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao processar lançamentos automáticos: {e}")
        return False

def _determinar_tipo_falta(data):
    """Determina tipo de falta baseado no dia da semana"""
    dia_semana = data.weekday()  # 0=Monday, 6=Sunday
    
    # Verificar se é feriado (implementar lógica de feriados)
    if _eh_feriado(data):
        return 'feriado_folga'
    
    if dia_semana < 5:  # Segunda a Sexta
        return 'falta'
    elif dia_semana == 5:  # Sábado
        return 'sabado_folga'
    else:  # Domingo
        return 'domingo_folga'

def _eh_feriado(data):
    """Verifica se a data é feriado nacional"""
    # Implementar lógica de feriados nacionais
    # Por enquanto, retorna False
    return False

def sincronizar_alocacao_com_horario_funcionario(allocation_employee_id, admin_id=None):
    """Aplica horário do funcionário na alocação se disponível
    IMPORTANTE: admin_id é obrigatório para isolamento multi-tenant
    """
    from app import db
    
    if admin_id is None:
        raise ValueError("admin_id é obrigatório para isolamento multi-tenant")
    
    # Buscar com validação de admin_id
    allocation_emp = db.session.query(AllocationEmployee).join(Allocation).filter(
        AllocationEmployee.id == allocation_employee_id,
        Allocation.admin_id == admin_id
    ).first()
    
    if not allocation_emp:
        return False
    
    funcionario = allocation_emp.funcionario
    if funcionario and funcionario.horario_trabalho:
        horario = funcionario.horario_trabalho
        allocation_emp.turno_inicio = horario.entrada
        allocation_emp.turno_fim = horario.saida
        
        # Definir tipo de lançamento baseado no dia
        # Usar data da alocação como parâmetro para garantir que funcione sempre
        allocation_emp.tipo_lancamento = allocation_emp.get_tipo_lancamento_automatico(allocation_emp.allocation.data_alocacao)
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao sincronizar horário: {e}")
            return False
    
    return False

# ================================
# MÓDULO DE VEÍCULOS V2.0 - REDESIGN COMPLETO  
# ================================
# Schema moderno com tipos INTEGER corretos e formulários unificados
# Design visual idêntico aos módulos RDO/Obras

class Veiculo(db.Model):
    """Modelo principal de veículos com design moderno e tipos corretos"""
    __tablename__ = 'veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados básicos do veículo
    placa = db.Column(db.String(10), nullable=False)  # ABC-1234 ou ABC1D234
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), default='Utilitário')  # Utilitário, Caminhão, Van, Carro
    
    # Controle de quilometragem
    km_atual = db.Column(db.Integer, default=0)  # Quilometragem atual
    
    # Dados opcionais
    cor = db.Column(db.String(30))
    chassi = db.Column(db.String(50))
    renavam = db.Column(db.String(20))
    combustivel = db.Column(db.String(20), default='Gasolina')  # Gasolina, Álcool, Diesel, Flex
    
    # Controle
    ativo = db.Column(db.Boolean, default=True)
    
    # Manutenção
    data_ultima_manutencao = db.Column(db.Date)
    data_proxima_manutencao = db.Column(db.Date)
    km_proxima_manutencao = db.Column(db.Integer)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='veiculos_administrados')
    usos = db.relationship('UsoVeiculo', backref='veiculo', cascade='all, delete-orphan', lazy='dynamic')
    custos = db.relationship('CustoVeiculo', backref='veiculo', cascade='all, delete-orphan', lazy='dynamic')
    
    # Índices e constraints para performance
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'placa', name='uk_veiculo_admin_placa'),
        db.Index('idx_veiculo_admin_tipo', 'admin_id', 'tipo'),
        db.Index('idx_veiculo_placa_admin', 'placa', 'admin_id'),
    )
    
    def __repr__(self):
        return f'<Veiculo {self.placa} - {self.marca} {self.modelo}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'placa': self.placa,
            'marca': self.marca,
            'modelo': self.modelo,
            'ano': self.ano,
            'tipo': self.tipo,
            'km_atual': self.km_atual,
            'cor': self.cor,
            'combustivel': self.combustivel,
            'ativo': self.ativo,
            'data_ultima_manutencao': self.data_ultima_manutencao.isoformat() if self.data_ultima_manutencao else None,
            'data_proxima_manutencao': self.data_proxima_manutencao.isoformat() if self.data_proxima_manutencao else None,
            'km_proxima_manutencao': self.km_proxima_manutencao,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def marca_modelo(self):
        """Propriedade para exibição combinada"""
        return f"{self.marca} {self.modelo}"
    
    @property
    def descricao_completa(self):
        """Descrição completa do veículo"""
        return f"{self.placa} - {self.marca} {self.modelo} ({self.ano})"


class UsoVeiculo(db.Model):
    """Registro de uso de veículo com formulário unificado para uso e custos"""
    __tablename__ = 'uso_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)  # Agora opcional
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)  # Pode ser uso pessoal/administrativo
    
    # Dados do uso
    data_uso = db.Column(db.Date, nullable=False)
    hora_saida = db.Column(db.Time, nullable=True)  # Nome correto da tabela
    hora_retorno = db.Column(db.Time, nullable=True)  # Nome correto da tabela
    
    # Quilometragem
    km_inicial = db.Column(db.Integer, nullable=True)  # Opcional agora
    km_final = db.Column(db.Integer)
    km_percorrido = db.Column(db.Integer)  # Calculado automaticamente
    
    # Passageiros modernos (novos campos)
    passageiros_frente = db.Column(db.Text)  # IDs separados por vírgula
    passageiros_tras = db.Column(db.Text)    # IDs separados por vírgula
    
    
    
    # Controle
    responsavel_veiculo = db.Column(db.String(100))  # Funcionário responsável pelo veículo
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO) 
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id], backref='usos_veiculo')
    obra = db.relationship('Obra', backref='usos_veiculo')
    admin = db.relationship('Usuario', backref='usos_veiculo_administrados')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_uso_veiculo_data_admin', 'data_uso', 'admin_id'),
        db.Index('idx_uso_veiculo_funcionario', 'funcionario_id'),
        db.Index('idx_uso_veiculo_obra', 'obra_id'),
    )
    
    def __repr__(self):
        func_nome = self.funcionario.nome if self.funcionario else f"ID:{self.funcionario_id}"
        veiculo_placa = self.veiculo.placa if self.veiculo else f"ID:{self.veiculo_id}"
        return f'<UsoVeiculo {veiculo_placa} - {func_nome} ({self.data_uso})>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'veiculo_id': self.veiculo_id,
            'veiculo_placa': self.veiculo.placa if self.veiculo else None,
            'funcionario_id': self.funcionario_id,
            'motorista_nome': self.funcionario.nome if self.funcionario else None,
            'obra_id': self.obra_id,
            'obra_nome': self.obra.nome if self.obra else None,
            'data_uso': self.data_uso.isoformat(),
            'hora_saida': self.hora_saida.isoformat() if self.hora_saida else None,
            'hora_retorno': self.hora_retorno.isoformat() if self.hora_retorno else None,
            'km_inicial': self.km_inicial,
            'km_final': self.km_final,
            'km_percorrido': self.km_percorrido,
            'observacoes': self.observacoes,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    
    def calcular_km_percorrido(self):
        """Calcula automaticamente KM percorrido se possível"""
        if self.km_inicial and self.km_final and self.km_final > self.km_inicial:
            self.km_percorrido = self.km_final - self.km_inicial
            return self.km_percorrido
        return 0


class CustoVeiculo(db.Model):
    """Custos do veículo não relacionados a uso específico (manutenção, seguro, etc.)"""
    __tablename__ = 'custo_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamento principal
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    
    # Dados do custo
    data_custo = db.Column(db.Date, nullable=False)
    tipo_custo = db.Column(db.String(30), nullable=False)  # manutencao, seguro, ipva, dpvat, multa, outros
    
    # Valores
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Detalhes
    descricao = db.Column(db.String(200), nullable=False)
    fornecedor = db.Column(db.String(100))  # Oficina, Seguradora, etc.
    numero_nota_fiscal = db.Column(db.String(20))
    data_vencimento = db.Column(db.Date)  # Para custos recorrentes
    
    # Status
    status_pagamento = db.Column(db.String(20), default='Pendente')  # Pendente, Pago, Vencido, Cancelado
    forma_pagamento = db.Column(db.String(30))  # Dinheiro, PIX, Cartão, Boleto
    
    # Controle de quilometragem (para manutenções)
    km_veiculo = db.Column(db.Integer)  # KM do veículo no momento do custo
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Multi-tenant (OBRIGATÓRIO)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Controle de tempo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    admin = db.relationship('Usuario', backref='custos_veiculo_administrados')
    
    # Índices para performance
    __table_args__ = (
        db.Index('idx_custo_veiculo_data_admin', 'data_custo', 'admin_id'),
        db.Index('idx_custo_veiculo_tipo', 'tipo_custo', 'admin_id'),
        db.Index('idx_custo_veiculo_status', 'status_pagamento', 'admin_id'),
    )
    
    def __repr__(self):
        veiculo_placa = self.veiculo.placa if self.veiculo else f"ID:{self.veiculo_id}"
        return f'<CustoVeiculo {veiculo_placa} - {self.tipo_custo} R$ {self.valor}>'
    
    def to_dict(self):
        """Converter para dicionário para APIs"""
        return {
            'id': self.id,
            'veiculo_id': self.veiculo_id,
            'veiculo_placa': self.veiculo.placa if self.veiculo else None,
            'data_custo': self.data_custo.isoformat(),
            'tipo_custo': self.tipo_custo,
            'categoria': 'operacional',  # Default value since categoria was removed
            'valor': float(self.valor),
            'descricao': self.descricao,
            'fornecedor': self.fornecedor,
            'numero_nota_fiscal': self.numero_nota_fiscal,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'status_pagamento': self.status_pagamento,
            'forma_pagamento': self.forma_pagamento,
            'km_veiculo': self.km_veiculo,
            'observacoes': self.observacoes,
            'admin_id': self.admin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ================================
# MÓDULO DE VEÍCULOS - SISTEMA LIMPO
# ================================

class Vehicle(db.Model):
    """Modelo de veículos - Sistema limpo"""
    __tablename__ = 'frota_veiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(30), default='Utilitário')
    km_atual = db.Column(db.Integer, default=0)
    cor = db.Column(db.String(30))
    chassi = db.Column(db.String(50))
    renavam = db.Column(db.String(20))
    combustivel = db.Column(db.String(20), default='Gasolina')
    ativo = db.Column(db.Boolean, default=True)
    
    # Campos de manutenção
    data_ultima_manutencao = db.Column(db.Date)
    data_proxima_manutencao = db.Column(db.Date)
    km_proxima_manutencao = db.Column(db.Integer)
    
    # Campos de alertas/vencimentos ([OK] TAREFA 6)
    data_vencimento_ipva = db.Column(db.Date)
    data_vencimento_seguro = db.Column(db.Date)
    
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships (mantém nomes antigos para compatibilidade)
    admin = db.relationship('Usuario', backref='vehicles')
    usos = db.relationship('VehicleUsage', backref='vehicle', cascade='all, delete-orphan')
    custos = db.relationship('VehicleExpense', backref='vehicle', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'placa', name='uk_vehicle_admin_placa'),
        db.Index('idx_vehicle_admin', 'admin_id'),
    )

class VehicleUsage(db.Model):
    """Registro de uso de veículos"""
    __tablename__ = 'frota_utilizacao'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data_uso = db.Column(db.Date, nullable=False)
    hora_saida = db.Column(db.Time)
    hora_retorno = db.Column(db.Time)
    km_inicial = db.Column(db.Integer)
    km_final = db.Column(db.Integer)
    km_percorrido = db.Column(db.Integer)
    passageiros_frente = db.Column(db.Text)
    passageiros_tras = db.Column(db.Text)
    responsavel_veiculo = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    funcionario = db.relationship('Funcionario', backref='vehicle_usages')
    obra = db.relationship('Obra', backref='vehicle_usages')
    admin = db.relationship('Usuario', backref='vehicle_usages')
    
    __table_args__ = (
        db.Index('idx_vehicle_usage_data_admin', 'data_uso', 'admin_id'),
    )

class VehicleExpense(db.Model):
    """Despesas de veículos"""
    __tablename__ = 'frota_despesa'
    
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    data_custo = db.Column(db.Date, nullable=False)
    tipo_custo = db.Column(db.String(30), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    fornecedor = db.Column(db.String(100))
    numero_nota_fiscal = db.Column(db.String(20))
    data_vencimento = db.Column(db.Date)
    status_pagamento = db.Column(db.String(20), default='Pendente')
    forma_pagamento = db.Column(db.String(30))
    km_veiculo = db.Column(db.Integer)
    observacoes = db.Column(db.Text)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    obra = db.relationship('Obra', backref='vehicle_expenses')
    admin = db.relationship('Usuario', backref='vehicle_expenses')
    
    __table_args__ = (
        db.Index('idx_vehicle_expense_data_admin', 'data_custo', 'admin_id'),
    )

# ================================
# ALMOXARIFADO V3.0 - GESTÃO DE MATERIAIS, FERRAMENTAS E EPIs
# ================================

class AlmoxarifadoCategoria(db.Model):
    """Categorias de materiais do almoxarifado"""
    __tablename__ = 'almoxarifado_categoria'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo_controle_padrao = db.Column(db.String(20), nullable=False)  # SERIALIZADO ou CONSUMIVEL
    permite_devolucao_padrao = db.Column(db.Boolean, default=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    admin = db.relationship('Usuario', backref='almoxarifado_categorias')
    
    __table_args__ = (
        db.Index('idx_almox_categoria_admin', 'admin_id'),
    )

class AlmoxarifadoItem(db.Model):
    """Catálogo de itens do almoxarifado"""
    __tablename__ = 'almoxarifado_item'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_categoria.id'), nullable=False)
    tipo_controle = db.Column(db.String(20), nullable=False)  # SERIALIZADO ou CONSUMIVEL
    permite_devolucao = db.Column(db.Boolean, default=True)
    estoque_minimo = db.Column(db.Integer, default=0)
    unidade = db.Column(db.String(20))  # un, kg, m, litros, etc
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    categoria = db.relationship('AlmoxarifadoCategoria', backref='itens')
    admin = db.relationship('Usuario', backref='almoxarifado_itens')
    
    __table_args__ = (
        db.Index('idx_almox_item_codigo_admin', 'codigo', 'admin_id'),
        db.Index('idx_almox_item_categoria', 'categoria_id'),
        db.Index('idx_almox_item_nome', 'nome'),
    )

class AlmoxarifadoEstoque(db.Model):
    """Controle de estoque (serializado e consumível) com rastreamento de lotes FIFO"""
    __tablename__ = 'almoxarifado_estoque'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=False)
    numero_serie = db.Column(db.String(100))  # Para SERIALIZADO
    quantidade = db.Column(db.Numeric(10, 2), default=0)  # Para CONSUMIVEL (quantidade atual)
    
    # NOVOS CAMPOS PARA RASTREAMENTO DE LOTES FIFO
    quantidade_inicial = db.Column(db.Numeric(10, 2))  # Quantidade original da entrada deste lote
    quantidade_disponivel = db.Column(db.Numeric(10, 2))  # Quantidade ainda disponível para saída
    entrada_movimento_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_movimento.id'))  # Vincula ao movimento de entrada
    
    status = db.Column(db.String(20), default='DISPONIVEL')  # DISPONIVEL, EM_USO, MANUTENCAO, DESCARTADO, CONSUMIDO
    funcionario_atual_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    valor_unitario = db.Column(db.Numeric(10, 2))
    lote = db.Column(db.String(50))
    data_validade = db.Column(db.Date)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    item = db.relationship('AlmoxarifadoItem', backref='estoque')
    funcionario_atual = db.relationship('Funcionario', backref='itens_almoxarifado_posse')
    obra = db.relationship('Obra', backref='itens_almoxarifado_obra')
    admin = db.relationship('Usuario', backref='almoxarifado_estoque')
    entrada_movimento = db.relationship('AlmoxarifadoMovimento', foreign_keys=[entrada_movimento_id], backref='lotes_criados')
    
    __table_args__ = (
        db.Index('idx_almox_estoque_item_status', 'item_id', 'status'),
        db.Index('idx_almox_estoque_funcionario', 'funcionario_atual_id'),
        db.Index('idx_almox_estoque_admin', 'admin_id'),
        db.Index('idx_almox_estoque_numero_serie', 'numero_serie'),
        db.Index('idx_almox_estoque_entrada_mov', 'entrada_movimento_id'),
        db.Index('idx_almox_estoque_fifo', 'item_id', 'status', 'created_at'),  # Índice composto para queries FIFO
    )

class AlmoxarifadoMovimento(db.Model):
    """Histórico de movimentações (ENTRADA, SAIDA, DEVOLUCAO)"""
    __tablename__ = 'almoxarifado_movimento'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo_movimento = db.Column(db.String(20), nullable=False)  # ENTRADA, SAIDA, DEVOLUCAO
    item_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_estoque.id'))
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)  # NULL permitido para ENTRADAs
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'))  # Integração com Financeiro
    quantidade = db.Column(db.Numeric(10, 2))
    valor_unitario = db.Column(db.Numeric(10, 2))
    nota_fiscal = db.Column(db.String(50))
    lote = db.Column(db.String(50))
    numero_serie = db.Column(db.String(100))  # Para movimentos de serializados
    condicao_item = db.Column(db.String(20))  # Para devoluções: BOM, DANIFICADO, PERDIDO
    observacao = db.Column(db.Text)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    origem_manual = db.Column(db.Boolean, default=False)
    impacta_estoque = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Vínculo com PedidoCompra: quando preenchido, indica que este movimento
    # foi gerado a partir de um pedido de compra (evita duplicação de custo).
    pedido_compra_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    item = db.relationship('AlmoxarifadoItem', backref='movimentos')
    estoque = db.relationship('AlmoxarifadoEstoque', foreign_keys=[estoque_id], backref='movimentos')
    funcionario = db.relationship('Funcionario', backref='movimentos_almoxarifado')
    obra = db.relationship('Obra', backref='movimentos_almoxarifado')
    fornecedor = db.relationship('Fornecedor', backref='movimentos_almoxarifado')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='movimentos_almoxarifado_criados')
    admin = db.relationship('Usuario', foreign_keys=[admin_id], backref='movimentos_almoxarifado_admin')
    pedido_compra = db.relationship('PedidoCompra', backref='movimentos_almoxarifado', foreign_keys=[pedido_compra_id])
    
    __table_args__ = (
        db.Index('idx_almox_movimento_data', 'data_movimento'),
        db.Index('idx_almox_movimento_tipo', 'tipo_movimento'),
        db.Index('idx_almox_movimento_funcionario', 'funcionario_id'),
        db.Index('idx_almox_movimento_obra', 'obra_id'),
        db.Index('idx_almox_movimento_fornecedor', 'fornecedor_id'),
        db.Index('idx_almox_movimento_admin', 'admin_id'),
    )

# ================================
# RASTREAMENTO DE MIGRAÇÕES
# ================================
class MigrationHistory(db.Model):
    """Rastreamento de migrações executadas para garantir idempotência"""
    __tablename__ = 'migration_history'
    
    id = db.Column(db.Integer, primary_key=True)
    migration_number = db.Column(db.Integer, unique=True, nullable=False)
    migration_name = db.Column(db.String(200), nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    execution_time_ms = db.Column(db.Integer)
    status = db.Column(db.String(20), default='success')  # success, failed, skipped
    error_message = db.Column(db.Text)
    
    __table_args__ = (
        db.Index('idx_migration_number', 'migration_number'),
        db.Index('idx_migration_executed', 'executed_at'),
    )
    
    def __repr__(self):
        return f'<Migration #{self.migration_number}: {self.migration_name}>'

# ================================
# FOLHA PROCESSADA (DASHBOARD CUSTOS)
# ================================
class FolhaProcessada(db.Model):
    """
    Armazena resultados consolidados do processamento de folha.
    Usado para dashboards de custos de mão de obra por obra.
    Cada registro representa um funcionário/mês/obra processado.
    """
    __tablename__ = 'folha_processada'
    
    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    
    # Dados do salário
    salario_base = db.Column(db.Numeric(10, 2), default=0)
    salario_bruto = db.Column(db.Numeric(10, 2), default=0)
    total_proventos = db.Column(db.Numeric(10, 2), default=0)
    total_descontos = db.Column(db.Numeric(10, 2), default=0)
    salario_liquido = db.Column(db.Numeric(10, 2), default=0)
    
    # Componentes de horas extras e DSR
    valor_he_50 = db.Column(db.Numeric(10, 2), default=0)
    valor_he_100 = db.Column(db.Numeric(10, 2), default=0)
    valor_dsr = db.Column(db.Numeric(10, 2), default=0)
    
    # Encargos
    encargos_fgts = db.Column(db.Numeric(10, 2), default=0)
    encargos_inss_patronal = db.Column(db.Numeric(10, 2), default=0)
    custo_total_empresa = db.Column(db.Numeric(10, 2), default=0)
    
    # Descontos do funcionário
    inss_funcionario = db.Column(db.Numeric(10, 2), default=0)
    irrf = db.Column(db.Numeric(10, 2), default=0)
    desconto_faltas = db.Column(db.Numeric(10, 2), default=0)
    desconto_atrasos = db.Column(db.Numeric(10, 2), default=0)
    
    # Horas
    horas_contratuais = db.Column(db.Numeric(10, 2), default=0)
    horas_trabalhadas = db.Column(db.Numeric(10, 2), default=0)
    horas_extras_50 = db.Column(db.Numeric(10, 2), default=0)
    horas_extras_100 = db.Column(db.Numeric(10, 2), default=0)
    horas_falta = db.Column(db.Numeric(10, 2), default=0)
    
    # Metadados
    processado_em = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    funcionario = db.relationship('Funcionario', backref='folhas_processadas')
    obra = db.relationship('Obra', backref='folhas_processadas')
    admin = db.relationship('Usuario', backref='folhas_processadas_admin')
    
    __table_args__ = (
        db.UniqueConstraint('funcionario_id', 'obra_id', 'ano', 'mes', name='uq_folha_func_obra_periodo'),
        db.Index('idx_folha_processada_obra', 'obra_id'),
        db.Index('idx_folha_processada_periodo', 'ano', 'mes'),
        db.Index('idx_folha_processada_admin', 'admin_id'),
        db.Index('idx_folha_processada_funcionario', 'funcionario_id'),
    )
    
    def __repr__(self):
        return f'<FolhaProcessada func={self.funcionario_id} obra={self.obra_id} {self.mes:02d}/{self.ano}>'


# ================================
# ALIASES PARA COMPATIBILIDADE
# ================================
# Manter compatibilidade com código legado que importa Frota*
FrotaVeiculo = Vehicle
FrotaUtilizacao = VehicleUsage
FrotaDespesa = VehicleExpense


# ================================
# MÓDULO V2: COMPRAS DE MATERIAIS
# ================================

class PedidoCompra(db.Model):
    """Pedido / recibo de compra V2 — vinculado a fornecedor e obra (obra é o centro de custo)"""
    __tablename__ = 'pedido_compra'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50))                        # Número da NF/recibo (livre)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    data_compra = db.Column(db.Date, nullable=False)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'), nullable=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    # Etapa (centro de custo) à qual a compra se amarra — opcional. Quando definida,
    # os GestaoCustoFilho gerados entram no Realizado dessa etapa
    # (spec 2026-06-29-compras-campo-etapa-design).
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)
    condicao_pagamento = db.Column(db.String(50), default='a_vista')  # a_vista, 30d, 60d, 90d, parcelado
    parcelas = db.Column(db.Integer, default=1)
    valor_total = db.Column(db.Numeric(12, 2), nullable=False)
    observacoes = db.Column(db.Text)
    anexo_url = db.Column(db.String(500))

    # Portal do Cliente — aprovação e comprovante
    status_aprovacao_cliente = db.Column(db.String(40), default=None)
    comprovante_pagamento_url = db.Column(db.String(500))

    # Tipo de compra:
    #   'normal'             → cria GestaoCustoPai MATERIAL + entrada no almoxarifado (fluxo interno)
    #   'aprovacao_cliente'  → fica pendente até cliente aprovar no portal; ao aprovar,
    #                          cria GestaoCustoPai FATURAMENTO_DIRETO (sem FluxoCaixa) + entrada + saída
    tipo_compra = db.Column(db.String(30), nullable=False, default='normal')
    # Flag de idempotência: True depois que processar_compra_aprovada_cliente rodou.
    processada_apos_aprovacao = db.Column(db.Boolean, nullable=False, default=False)

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Task #11 — Compras Parceladas, Responsável e Calendário de Pagamentos
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_vencimento_primeira_parcela = db.Column(db.Date, nullable=True)
    intervalo_parcelas_dias = db.Column(db.Integer, nullable=True)
    # Fase 3 — origem do pedido. NULL = pedido avulso, registrado direto
    # pelo formulário (compras_views.py:532), que é como TODOS os pedidos
    # nasceram até 2026-07-21. Preenchido = pedido emitido a partir de
    # requisição aprovada, com alçada registrada em requisicao_transicao.
    # A coluna é o que permite a Task 9 recusar pedido sem requisição
    # quando `compras_governanca_ativa` está ligada, sem invalidar
    # nenhum registro histórico.
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='SET NULL'),
        nullable=True, index=True)

    # Relacionamentos
    fornecedor = db.relationship('Fornecedor', backref='pedidos_compra', foreign_keys=[fornecedor_id])
    centro_custo = db.relationship('CentroCusto', backref='pedidos_compra', foreign_keys=[centro_custo_id])
    obra = db.relationship('Obra', backref='pedidos_compra', foreign_keys=[obra_id])
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])
    itens = db.relationship('PedidoCompraItem', backref='pedido', lazy='dynamic', cascade='all, delete-orphan')
    responsavel = db.relationship('Usuario', foreign_keys=[responsavel_id], backref='pedidos_compra_responsavel')
    requisicao = db.relationship(
        'RequisicaoCompra', foreign_keys=[requisicao_id],
        backref=db.backref('pedidos', lazy='dynamic'))


class PedidoCompraItem(db.Model):
    """Itens de um pedido de compra V2"""
    __tablename__ = 'pedido_compra_item'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido_compra.id'), nullable=False)
    almoxarifado_item_id = db.Column(db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=True)
    descricao = db.Column(db.String(200), nullable=False)   # free-text caso item não esteja no catálogo
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    preco_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    # Relacionamentos
    almoxarifado_item = db.relationship('AlmoxarifadoItem', backref='pedido_itens', foreign_keys=[almoxarifado_item_id])


class RequisicaoCompra(db.Model):
    """Documento de DEMANDA de compra — Fase 3.

    O que existia até 2026-07-21 era só o `PedidoCompra`, que é registro a
    posteriori de NF/recibo: `compras_views.py:709-711` cria o pedido, os
    GestaoCustoPai, os ContaPagar e os movimentos de almoxarifado no MESMO
    request do formulário. Não havia lugar onde alguém pedisse antes de
    comprar, nem onde alguém aprovasse.

    Diferenças deliberadas em relação a PedidoCompra:
      * `obra_id` é NOT NULL aqui (lá é nullable — models.py:4736). Tabela
        nova, sem órfão para migrar; a Fase 4 encontra o terreno pronto.
      * `valor_estimado` é ESTIMATIVA. O valor real é o do pedido emitido.
        A alçada decide pela estimativa, e a Task 8 recusa emitir pedido
        acima da faixa aprovada.
    """
    __tablename__ = 'requisicao_compra'
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'numero', name='uq_requisicao_admin_numero'),
        db.Index('ix_requisicao_obra_estado', 'obra_id', 'estado'),
        db.Index('ix_requisicao_admin_estado', 'admin_id', 'estado'),
    )

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), nullable=False)  # RC-2026-0001, por tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)

    # Vínculo obrigatório com obra. É a regra central da fase: requisição
    # sem obra não existe, porque custo sem obra não é rastreável
    # (DEVOLUTIVA R4 / services/resumo_custos_obra.py:190, que hoje rateia
    # órfão por estimativa).
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    # Etapa/centro de custo — opcional, exatamente como em
    # pedido_compra.obra_servico_custo_id (models.py:4740, migration 205).
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id', ondelete='SET NULL'),
        nullable=True)

    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                               nullable=False, index=True)
    estado = db.Column(db.Enum(EstadoRequisicao), nullable=False,
                       default=EstadoRequisicao.RASCUNHO)

    justificativa = db.Column(db.Text)
    data_necessidade = db.Column(db.Date, nullable=True)
    valor_estimado = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Mapa de concorrência opcional. FK, NÃO reparentagem: os mapas
    # existentes continuam pendurados na obra (models.py:5604) e continuam
    # funcionando. Faixas de alçada altas podem exigir que esta FK esteja
    # preenchida e o mapa concluído (FaixaAlcada.exige_mapa_concorrencia).
    mapa_v2_id = db.Column(
        db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='SET NULL'),
        nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    obra = db.relationship('Obra', foreign_keys=[obra_id],
                           backref=db.backref('requisicoes', lazy='dynamic'))
    obra_servico_custo = db.relationship('ObraServicoCusto',
                                         foreign_keys=[obra_servico_custo_id])
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    mapa_v2 = db.relationship('MapaConcorrenciaV2', foreign_keys=[mapa_v2_id])
    # order_by fixo: a emissão do pedido casa item ↔ preço pela ORDEM
    # (compras_views.requisicao_emitir_pedido lê item_preco_real[] por índice).
    # Sem ordenação determinística, `requisicao.itens.all()` no template e o
    # `.order_by(id)` na rota poderiam divergir no Postgres e trocar o preço
    # de um item pelo de outro. Fixar aqui garante a mesma ordem nos dois.
    itens = db.relationship('RequisicaoCompraItem', backref='requisicao',
                            lazy='dynamic', cascade='all, delete-orphan',
                            order_by='RequisicaoCompraItem.id')

    def __repr__(self):
        return f'<RequisicaoCompra {self.numero} obra={self.obra_id} {self.estado.value}>'


class RequisicaoCompraItem(db.Model):
    """Linha de uma RequisicaoCompra.

    Espelha PedidoCompraItem (models.py:4778) de propósito: a conversão em
    pedido é uma cópia campo a campo, sem tradução. A diferença é que aqui
    o preço é ESTIMADO (o solicitante de campo raramente sabe o preço
    fechado) e existe `unidade`, que PedidoCompraItem não tem.
    """
    __tablename__ = 'requisicao_compra_item'
    __table_args__ = (
        db.Index('ix_requisicao_item_requisicao', 'requisicao_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='CASCADE'),
        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    # Opcional: item do catálogo do almoxarifado (models.py:4508). Quando
    # preenchido, a conversão em pedido leva o vínculo junto e a entrada de
    # estoque é gerada por _gerar_entrada_almoxarifado (compras_views.py:80).
    almoxarifado_item_id = db.Column(
        db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=True)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), default='un')
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    preco_estimado = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    almoxarifado_item = db.relationship('AlmoxarifadoItem',
                                        foreign_keys=[almoxarifado_item_id])

    @property
    def subtotal(self):
        """Derivado, não persistido: não existe caminho em que subtotal e
        quantidade*preco divirjam, e persistir os dois cria a chance de
        divergirem (é o que acontece em PedidoCompraItem.subtotal)."""
        from decimal import Decimal as _D
        return (_D(str(self.quantidade or 0)) * _D(str(self.preco_estimado or 0))
                ).quantize(_D('0.01'))

    def __repr__(self):
        return f'<RequisicaoCompraItem req={self.requisicao_id} {self.descricao[:30]}>'


class RequisicaoTransicao(db.Model):
    """Trilha de auditoria da RequisicaoCompra — quem, quando, de onde para
    onde, e por QUANTO.

    Mesma forma de CronogramaImportacaoEvento (models.py:5178) e de
    PropostaHistorico (models.py:3140), que são as duas trilhas que já
    funcionam neste repositório. A diferença é `valor_no_momento`: numa
    aprovação por alçada, o valor da decisão é parte da decisão. Sem ele,
    editar a requisição depois de aprovada reescreveria a história — que é
    exatamente o buraco que uma alçada tem que fechar.

    `papel_aplicado` guarda com que chapéu a pessoa agiu ('ADMIN',
    'GESTOR', 'COMPRADOR'), porque o vínculo em usuario_obra pode mudar
    depois e o histórico não pode mudar junto.
    """
    __tablename__ = 'requisicao_transicao'
    __table_args__ = (
        db.Index('ix_requisicao_transicao_req', 'requisicao_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='CASCADE'),
        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    de_estado = db.Column(db.Enum(EstadoRequisicao), nullable=True)
    para_estado = db.Column(db.Enum(EstadoRequisicao), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    papel_aplicado = db.Column(db.String(20), nullable=True)
    valor_no_momento = db.Column(db.Numeric(15, 2), nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    requisicao = db.relationship(
        'RequisicaoCompra',
        backref=db.backref('transicoes', lazy='dynamic',
                           order_by='RequisicaoTransicao.id',
                           cascade='all, delete-orphan'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

    def __repr__(self):
        de = self.de_estado.value if self.de_estado else '-'
        return f'<RequisicaoTransicao req={self.requisicao_id} {de}→{self.para_estado.value}>'


class FaixaAlcada(db.Model):
    """Faixa de alçada de aprovação de compra, POR TENANT — Fase 3.

    Alçada é dado, não código. A pergunta 3 da DEVOLUTIVA ("qual o valor
    de X?") continua sem resposta do negócio, e a resposta não pode virar
    um `if valor > 5000` no meio de uma view. Os valores semeados pela
    migration 243 são a RECOMENDAÇÃO do plano da Fase 3 e podem ser
    trocados sem deploy.

    Leitura de uma linha: "compra de até `valor_ate` precisa de
    `aprovacoes_necessarias` aprovações distintas; se `exige_admin`, uma
    delas tem que ser de ADMIN/SUPER_ADMIN; se `exige_mapa_concorrencia`,
    a requisição precisa apontar para um MapaConcorrenciaV2 concluído com
    pelo menos dois fornecedores".

    `valor_ate = NULL` é o teto aberto — tem que existir exatamente uma
    faixa assim por tenant, e ela é sempre a de maior `ordem`.
    """
    __tablename__ = 'faixa_alcada'
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'ordem', name='uq_faixa_alcada_admin_ordem'),
        db.Index('ix_faixa_alcada_admin_ativo', 'admin_id', 'ativo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    # NULL = sem teto. Comparação é `valor <= valor_ate` (inclusivo): a
    # compra de exatamente R$ 5.000,00 fica na faixa de R$ 5.000,00.
    valor_ate = db.Column(db.Numeric(15, 2), nullable=True)
    aprovacoes_necessarias = db.Column(db.Integer, nullable=False, default=1)
    exige_admin = db.Column(db.Boolean, nullable=False, default=False)
    exige_mapa_concorrencia = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        teto = f'<= {self.valor_ate}' if self.valor_ate is not None else 'sem teto'
        return (f'<FaixaAlcada #{self.ordem} {teto} '
                f'{self.aprovacoes_necessarias} aprov>')


class PortalAcessoEvento(db.Model):
    """Trilha dos acessos que MUTAM estado pelo portal por token — Fase 3.

    O portal é anônimo por construção (portal_obras_views.py:3). Isso
    significa que, até esta tabela existir, uma aprovação de compra pelo
    portal produzia um GestaoCustoPai atribuído ao ADMIN do tenant
    (portal_obras_views.py:360-361, `usuario_id=compra.admin_id`) — a
    trilha do almoxarifado registrava como autor alguém que não fez a
    ação.

    Não identifica pessoa (não há como, sem login — isso é a Fase 9a).
    Identifica ORIGEM: IP, user-agent e momento. É o suficiente para
    responder "de onde veio essa aprovação?" numa auditoria, e para
    detectar um token vazado sendo usado de vários lugares.
    """
    __tablename__ = 'portal_acesso_evento'
    __table_args__ = (
        db.Index('ix_portal_acesso_obra_criado', 'obra_id', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    acao = db.Column(db.String(50), nullable=False)
    alvo_tipo = db.Column(db.String(40), nullable=True)   # 'pedido_compra', 'mapa_v2'…
    alvo_id = db.Column(db.Integer, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    detalhes = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    obra = db.relationship('Obra', foreign_keys=[obra_id])

    def __repr__(self):
        return f'<PortalAcessoEvento {self.acao} obra={self.obra_id} ip={self.ip}>'


# ================================
# MÓDULO V2: TRANSPORTE
# ================================

class CategoriaTransporte(db.Model):
    """Categorias de despesas de transporte (por tenant)"""
    __tablename__ = 'categoria_transporte'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    icone = db.Column(db.String(50), default='fas fa-bus')
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lancamentos = db.relationship('LancamentoTransporte', backref='categoria', lazy='dynamic')


class LancamentoTransporte(db.Model):
    """Lançamentos de despesas de transporte: VT, combustível, aplicativo, passagem"""
    __tablename__ = 'lancamento_transporte'

    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_transporte.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('frota_veiculo.id'), nullable=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id'), nullable=True)

    data_lancamento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200))
    comprovante_url = db.Column(db.String(500))

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    funcionario = db.relationship('Funcionario', backref='lancamentos_transporte', foreign_keys=[funcionario_id])
    veiculo = db.relationship('Vehicle', backref='lancamentos_transporte', foreign_keys=[veiculo_id])
    centro_custo = db.relationship('CentroCusto', backref='lancamentos_transporte', foreign_keys=[centro_custo_id])
    obra = db.relationship('Obra', backref='lancamentos_transporte', foreign_keys=[obra_id])
    obra_servico_custo = db.relationship(
        'ObraServicoCusto', foreign_keys=[obra_servico_custo_id])


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO V2: CRONOGRAMA DE OBRAS (MS PROJECT STYLE) — Migration 75
# ─────────────────────────────────────────────────────────────────────────────

class CalendarioEmpresa(db.Model):
    """Configuração do calendário de dias úteis da empresa para o cronograma."""
    __tablename__ = 'calendario_empresa'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    considerar_sabado = db.Column(db.Boolean, default=False, nullable=False)
    considerar_domingo = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TarefaCronograma(db.Model):
    """
    Tarefa do cronograma de obra.
    Suporta hierarquia (tarefa_pai_id) e predecessoras (predecessora_id).
    """
    __tablename__ = 'tarefa_cronograma'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(
        db.Integer,
        db.ForeignKey('obra.id', ondelete='CASCADE'),
        nullable=False,
    )
    # Hierarquia: tarefa macro contém subtarefas
    tarefa_pai_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
    )
    # Dependência de cronograma: esta tarefa começa após o término da predecessora
    predecessora_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
    )
    ordem = db.Column(db.Integer, nullable=False, default=0)
    nome_tarefa = db.Column(db.String(200), nullable=False)
    duracao_dias = db.Column(db.Integer, default=1, nullable=False)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    quantidade_total = db.Column(db.Float, nullable=True)
    unidade_medida = db.Column(db.String(20), nullable=True)
    # Modo de apontamento ESCOLHIDO para esta tarefa: 'quantidade' (o RDO
    # pede quantidade do dia na unidade da tarefa) ou 'percentual' (o RDO
    # pede o % acumulado). Até 2026-07-21 isso não era escolha: era
    # deduzido em `services/cronograma_apontamento_service.modo_da_tarefa`
    # a partir de `quantidade_total > 0 AND unidade_medida != ''`, ou seja,
    # preencher "Quantidade" no modal do Gantt mudava o modo do RDO como
    # efeito colateral. A queixa do dono em 21/07/2026 — "RDO em
    # porcentagem" — é exatamente isso.
    #
    # NULL significa "ninguém escolheu" e mantém a dedução antiga
    # (`_modo_deduzido`). É o default de propósito: o importador .mpp
    # (services/cronograma_versao_service.py:534) e qualquer construção
    # direta do modelo continuam se comportando como sempre.
    #
    # Vocabulário: mesmo de `modo_da_tarefa()` e do JSON `tipo_modo` que a
    # UI do RDO já consome (templates/rdo/novo.html:1118). NÃO confundir
    # com `RDOApontamentoCronograma.tipo_apontamento` (models.py:5139),
    # que usa 'quantitativo'/'percentual' e descreve a LINHA de
    # apontamento, não a tarefa.
    #
    # Marco (`is_marco`) ignora esta coluna e é sempre percentual binário —
    # o guard vem antes da leitura, em `modo_da_tarefa`.
    modo_apontamento = db.Column(db.String(12), nullable=True)
    subatividade_mestre_id = db.Column(
        db.Integer,
        db.ForeignKey('subatividade_mestre.id', ondelete='SET NULL'),
        nullable=True,
    )
    subatividade_mestre = db.relationship('SubatividadeMestre', backref='tarefas_cronograma')
    # Task #62 — Serviço obrigatório das novas tarefas (nullable no DB
    # para tolerar dados legados; a UI/POST exige o campo a partir de v9).
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey('servico.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    # Atualizado automaticamente pelo RDO
    percentual_concluido = db.Column(db.Float, default=0.0, nullable=False)
    # 'empresa' = conta na produtividade; 'terceiros' = só check de conclusão
    responsavel = db.Column(db.String(20), default='empresa', nullable=False)
    # Para entregas/terceiros: data efetiva da entrega/conclusao (Migration 113)
    data_entrega_real = db.Column(db.Date, nullable=True)
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=False,
    )
    # Migration 117: separa cronograma INTERNO (False) do cronograma do CLIENTE (True)
    is_cliente = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # Task #102 (Migration 125) — rastreia tarefas geradas pela aprovação de proposta
    gerada_por_proposta_item_id = db.Column(
        db.Integer,
        db.ForeignKey('proposta_itens.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    # Relação somente-leitura para navegar até o item de proposta de origem
    # (e, por ele, ao serviço de catálogo). Usada na UI do cronograma para
    # expor o vínculo tarefa↔serviço. viewonly + sem backref = aditivo, sem
    # conflito de mapeamento.
    gerada_por_proposta_item = db.relationship(
        'PropostaItem',
        foreign_keys=[gerada_por_proposta_item_id],
        viewonly=True,
    )
    # ── Módulo 02 (cronograma-mpp), Migration 208: identidade estável ──
    # UID do MS Project (getUniqueID / <UID> do MSPDI) — chave de reconciliação
    mpp_uid = db.Column(db.BigInteger, nullable=True)
    wbs_codigo = db.Column(db.String(50), nullable=True)
    # Fingerprint determinístico do conteúdo (Módulo 4)
    fingerprint = db.Column(db.String(64), nullable=True)
    is_marco = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # Arquivamento lógico: tarefa removida em versão nova NUNCA é deletada
    ativa = db.Column(db.Boolean, nullable=False, default=True, server_default='true')
    arquivada_em = db.Column(db.DateTime, nullable=True)
    versao_criacao_id = db.Column(db.Integer,
                                  db.ForeignKey('cronograma_versao.id', ondelete='SET NULL'),
                                  nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO V2: APONTAMENTO DE PRODUÇÃO RDO ↔ CRONOGRAMA — Migration 76
# ─────────────────────────────────────────────────────────────────────────────

class RDOApontamentoCronograma(db.Model):
    """
    Registra a produção diária de uma tarefa do cronograma, vinculada a um RDO.
    Cada linha = quantidade executada em 1 dia por 1 tarefa.
    """
    __tablename__ = 'rdo_apontamento_cronograma'

    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(
        db.Integer,
        db.ForeignKey('rdo.id', ondelete='CASCADE'),
        nullable=False,
    )
    tarefa_cronograma_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='CASCADE'),
        nullable=False,
    )
    quantidade_executada_dia = db.Column(db.Float, default=0.0, nullable=False)
    quantidade_acumulada = db.Column(db.Float, default=0.0, nullable=False)
    percentual_realizado = db.Column(db.Float, default=0.0, nullable=False)
    # Task #142 — nullable: a coluna passa a aceitar NULL para sinalizar
    # "tarefa sem plano calculável" (sem data_inicio/duração) em vez de
    # confundir 0% real com 0% sem plano. A rota `apontar_producao` grava
    # `None` direto quando `calcular_progresso_rdo` devolve `None`.
    percentual_planejado = db.Column(db.Float, nullable=True)
    admin_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    # ── Módulo 02 (cronograma-mpp), Migration 209: semântica explícita ──
    # 'quantitativo' (valor do dia em unidades) | 'percentual' (acumulado %).
    # Hoje o modo é implícito por quantidade_total>0; os campos antigos NÃO
    # mudam de significado (leitura legada intacta) — ver spec §13.2.
    tipo_apontamento = db.Column(db.String(15), nullable=True)
    percentual_acumulado = db.Column(db.Float, nullable=True)
    percentual_incremento_dia = db.Column(db.Float, nullable=True)
    quantidade_total_snapshot = db.Column(db.Float, nullable=True)
    unidade_snapshot = db.Column(db.String(20), nullable=True)

    rdo = db.relationship(
        'RDO',
        backref=db.backref('apontamentos_cronograma', cascade='all, delete-orphan'),
    )
    tarefa = db.relationship('TarefaCronograma', backref='apontamentos')

    def __repr__(self):
        return (
            f'<RDOApontamentoCronograma rdo={self.rdo_id} '
            f'tarefa={self.tarefa_cronograma_id} qty={self.quantidade_executada_dia}>'
        )


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 02 (plano cronograma-mpp): importação e versionamento de cronograma
# Migrations 207-210. Modelos PASSIVOS (regra §9 da spec: nenhuma lógica em
# event listeners; snapshots são preenchidos explicitamente pelos serviços M5).
# ─────────────────────────────────────────────────────────────────────────────
class CronogramaImportacao(db.Model):
    """Um upload de cronograma (.xml MSPDI ou .mpp) e seu pipeline de estados:
    recebido → parseado → normalizado → reconciliado → aguardando_revisao →
    aplicado | falhou | cancelado."""
    __tablename__ = 'cronograma_importacao'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    arquivo_nome = db.Column(db.String(255))
    arquivo_tamanho = db.Column(db.Integer)
    arquivo_sha256 = db.Column(db.String(64), index=True)
    arquivo_path = db.Column(db.String(512), nullable=True)
    origem = db.Column(db.String(20))          # 'upload_mpp' | 'upload_mspdi' | 'json_cli'
    parser_nome = db.Column(db.String(50))     # 'mspdi_stdlib' | 'mpxj'
    parser_versao = db.Column(db.String(20))
    normalizador_versao = db.Column(db.String(20))
    status = db.Column(db.String(30), nullable=False, default='recebido')
    json_bruto = db.Column(db.JSON, nullable=True)
    json_normalizado = db.Column(db.JSON, nullable=True)
    relatorio_diff = db.Column(db.JSON, nullable=True)
    erro = db.Column(db.Text, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    aplicado_em = db.Column(db.DateTime, nullable=True)


class CronogramaVersao(db.Model):
    """Versão do cronograma de uma obra (nº sequencial por obra).
    Uma e somente uma versão 'ativa' por obra — o unique parcial
    (WHERE status='ativa') vive SÓ no DDL (migration 207), pois o
    declarativo do SQLAlchemy não expressa índice parcial de forma portável."""
    __tablename__ = 'cronograma_versao'
    __table_args__ = (
        db.UniqueConstraint('obra_id', 'numero', name='uq_cronograma_versao_obra_numero'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(
        db.Integer,
        db.ForeignKey('obra.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=False,
        index=True,
    )
    # Sequencial por obra (unique composto obra_id+numero)
    numero = db.Column(db.Integer, nullable=False)
    # 'ativa' | 'arquivada'
    status = db.Column(db.String(20), nullable=False, default='ativa')
    # NULL para a versão nº1 criada pelo backfill (migration 210)
    importacao_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_importacao.id'),
        nullable=True,
    )
    aplicada_em = db.Column(db.DateTime, default=datetime.utcnow)
    aplicada_por_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=True,
    )
    # Ex.: "backfill inicial", "rollback da v3"
    observacao = db.Column(db.Text, nullable=True)


class CronogramaTarefaSnapshot(db.Model):
    """Fotografia integral de cada tarefa em cada versão (diff, rollback e
    auditoria). Imutável após criado (spec §12)."""
    __tablename__ = 'cronograma_tarefa_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_versao.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=False,
    )
    # Tarefa viva correspondente; SET NULL — pode ter sido arquivada/removida
    tarefa_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
    )
    mpp_uid = db.Column(db.BigInteger, nullable=True)
    wbs_codigo = db.Column(db.String(50), nullable=True)
    nome_tarefa = db.Column(db.String(200), nullable=True)
    tarefa_pai_snapshot_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_tarefa_snapshot.id'),
        nullable=True,
    )
    # Lista de {uid, tipo, lag} — predecessoras múltiplas ficam só aqui (spec §4)
    predecessoras_json = db.Column(db.JSON, nullable=True)
    ordem = db.Column(db.Integer, nullable=True)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    duracao_dias = db.Column(db.Integer, nullable=True)
    quantidade_total = db.Column(db.Float, nullable=True)
    unidade_medida = db.Column(db.String(20), nullable=True)
    is_marco = db.Column(db.Boolean, default=False)
    is_resumo = db.Column(db.Boolean, default=False)
    percentual_concluido_no_momento = db.Column(db.Float, nullable=True)
    payload_extra = db.Column(db.JSON, nullable=True)


class CronogramaTarefaMapeamento(db.Model):
    """Resultado da reconciliação, por importação. Um par pode ter vários
    registros de tipo (ex.: correspondencia_exata + datas_alteradas) —
    uma linha por classificação simplifica filtros na UI (spec §4)."""
    __tablename__ = 'cronograma_tarefa_mapeamento'

    id = db.Column(db.Integer, primary_key=True)
    importacao_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_importacao.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=False,
    )
    # NULL para tarefa nova (sem correspondente atual)
    tarefa_atual_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
    )
    # uid/wbs/fingerprint da tarefa no arquivo novo; NULL para removida
    chave_nova = db.Column(db.String(120), nullable=True)
    # correspondencia_exata | correspondencia_provavel | nova | removida |
    # renomeada | movida_hierarquia | datas_alteradas | duracao_alterada |
    # predecessoras_alteradas | quantidade_alterada | unidade_alterada |
    # ambigua | revisao_manual | dividida | fundida
    tipo = db.Column(db.String(40), nullable=False)
    # Confiança da correspondência (0-1)
    score = db.Column(db.Float, nullable=True)
    # 'auto' | 'manual'
    origem_decisao = db.Column(db.String(20), nullable=True)
    decidido_por_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=True,
    )
    detalhes = db.Column(db.JSON, nullable=True)


class CronogramaImportacaoEvento(db.Model):
    """Trilha de auditoria da importação. Eventos mínimos: upload,
    parse_ok/parse_erro, normalizado, reconciliado, revisao_alterada,
    aplicado, rollback, cancelado."""
    __tablename__ = 'cronograma_importacao_evento'

    id = db.Column(db.Integer, primary_key=True)
    importacao_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_importacao.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=False,
    )
    evento = db.Column(db.String(50), nullable=False)
    detalhes = db.Column(db.JSON, nullable=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=True,
    )
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
# GESTÃO DE CUSTOS V2 (Migration 77)
# ═══════════════════════════════════════════════════════════

class GestaoCustoPai(db.Model):
    """Agrupador de custos: único módulo de saídas financeiras V2.
    
    Categorias (nova hierarquia contábil construção civil SINAPI/NBC TG):
      Custo Direto de Obra:    MATERIAL, MAO_OBRA_DIRETA, EQUIPAMENTO, SUBEMPREITADA
      Custo Indireto de Obra:  ALIMENTACAO, TRANSPORTE, CANTEIRO, TAXAS_LICENCAS
      Despesa Administrativa:  SALARIO_ADMIN, ALUGUEL_UTILITIES, TRIBUTOS, DESPESA_FINANCEIRA, OUTROS
    
    Categorias legadas (mapeadas automaticamente para as novas):
      COMPRA → MATERIAL, VEICULO → EQUIPAMENTO, SALARIO → MAO_OBRA_DIRETA,
      REEMBOLSO → OUTROS, DESPESA_GERAL → OUTROS
    """
    __tablename__ = 'gestao_custo_pai'

    id = db.Column(db.Integer, primary_key=True)
    tipo_categoria = db.Column(db.String(50), nullable=False)
    entidade_nome = db.Column(db.String(150), nullable=False)
    entidade_id = db.Column(db.Integer, nullable=True)
    valor_total = db.Column(db.Numeric(15, 2), default=0.0)
    valor_solicitado = db.Column(db.Numeric(15, 2), nullable=True)
    status = db.Column(db.String(20), default='PENDENTE')
    # PENDENTE, SOLICITADO, AUTORIZADO, PAGO, RECUSADO
    data_pagamento = db.Column(db.Date, nullable=True)
    data_vencimento = db.Column(db.Date, nullable=True)
    numero_documento = db.Column(db.String(50), nullable=True)
    conta_bancaria = db.Column(db.String(100), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fluxo_caixa_id = db.Column(db.Integer, db.ForeignKey('fluxo_caixa.id'), nullable=True)
    # Categoria de fluxo de caixa (catálogo curável) — categoriza o custo no relatório
    # de Fluxo de Caixa e no lançamento por etapa (spec 2026-06-29-lancamento-categoria-fluxo-caixa).
    categoria_fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=True)

    # Novos campos para absorver ContaPagar
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=True)
    # Favorecido alternativo quando categoria=SUBEMPREITADA
    subempreiteiro_id = db.Column(db.Integer, db.ForeignKey('subempreiteiro.id'), nullable=True)
    forma_pagamento = db.Column(db.String(30), nullable=True)
    # Boleto, PIX, Transferencia, Dinheiro, Cheque
    valor_pago = db.Column(db.Numeric(15, 2), nullable=True)
    saldo = db.Column(db.Numeric(15, 2), nullable=True)
    conta_contabil_codigo = db.Column(db.String(20), nullable=True)
    # Nota: FK DB-level para plano_contas.codigo não é possível porque o banco foi
    # criado com PK em 'id' (integer) e 'codigo' só é único composto com admin_id.
    # Vínculo lógico gerenciado pela aplicação via conta_contabil_codigo.
    data_emissao = db.Column(db.Date, nullable=True)
    numero_parcela = db.Column(db.Integer, nullable=True)
    total_parcelas = db.Column(db.Integer, nullable=True)
    import_batch_id = db.Column(db.String(50), nullable=True)
    # Task #11 — Responsável pela Compra e Fechamento de Pagamentos
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    fechamento_id = db.Column(db.Integer, db.ForeignKey('fechamento_pagamento.id', use_alter=True, name='fk_gcp_fechamento'), nullable=True)

    itens = db.relationship('GestaoCustoFilho', backref='pai', lazy=True,
                            cascade='all, delete-orphan')
    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
    categoria_fluxo_caixa = db.relationship(
        'CategoriaFluxoCaixa', foreign_keys=[categoria_fluxo_caixa_id])
    subempreiteiro = db.relationship('Subempreiteiro', foreign_keys=[subempreiteiro_id], backref='custos_lancados')
    responsavel = db.relationship('Usuario', foreign_keys=[responsavel_id], backref='gestao_custo_responsavel')
    # conta_contabil: sem relationship ORM pois não há FK DB-level (veja nota acima).
    # Consultar PlanoContas.query.filter_by(codigo=self.conta_contabil_codigo) quando necessário.

    # Mapeamento de categorias legadas para novas
    _CATEGORIA_LEGADA_MAP = {
        'COMPRA':       'MATERIAL',
        'VEICULO':      'EQUIPAMENTO',
        'SALARIO':      'MAO_OBRA_DIRETA',
        'REEMBOLSO':    'OUTROS',
        'DESPESA_GERAL': 'OUTROS',
    }

    @property
    def tipo_categoria_normalizado(self):
        """Retorna a categoria nova correspondente, mesmo para categorias legadas."""
        return self._CATEGORIA_LEGADA_MAP.get(self.tipo_categoria, self.tipo_categoria)

    def __repr__(self):
        return f'<GestaoCustoPai {self.tipo_categoria} {self.entidade_nome} R${self.valor_total}>'


class GestaoCustoFilho(db.Model):
    """Lançamento individual: diária 01/04 em Obra X, marmita 02/04, etc."""
    __tablename__ = 'gestao_custo_filho'

    id = db.Column(db.Integer, primary_key=True)
    pai_id = db.Column(db.Integer, db.ForeignKey('gestao_custo_pai.id'), nullable=False)
    data_referencia = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'), nullable=True)
    obra_servico_custo_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_custo.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    origem_tabela = db.Column(db.String(80), nullable=True)
    origem_id = db.Column(db.Integer, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra', foreign_keys=[obra_id])
    obra_servico_custo = db.relationship('ObraServicoCusto', foreign_keys=[obra_servico_custo_id])

    def __repr__(self):
        return f'<GestaoCustoFilho pai={self.pai_id} R${self.valor} {self.descricao[:30]}>'


# ================================
# MÓDULO V2: REEMBOLSO A FUNCIONÁRIOS
# ================================

class ReembolsoFuncionario(db.Model):
    """Registra valores que a empresa deve devolver ao funcionário por despesas pagas do próprio bolso"""
    __tablename__ = 'reembolso_funcionario'

    id = db.Column(db.Integer, primary_key=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    data_despesa = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), default='outros')
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    centro_custo_id = db.Column(db.Integer, db.ForeignKey('centro_custo.id'), nullable=True)
    comprovante_url = db.Column(db.String(500), nullable=True)
    gestao_custo_pai_id = db.Column(db.Integer, db.ForeignKey('gestao_custo_pai.id', ondelete='SET NULL'), nullable=True)
    origem_tabela = db.Column(db.String(50))
    origem_id = db.Column(db.Integer)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    funcionario = db.relationship('Funcionario', backref='reembolsos', foreign_keys=[funcionario_id])
    obra = db.relationship('Obra', foreign_keys=[obra_id])

    def __repr__(self):
        return f'<ReembolsoFuncionario func={self.funcionario_id} R${self.valor}>'


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO V2: TEMPLATES DE CRONOGRAMA — Migration #95
# ─────────────────────────────────────────────────────────────────────────────

class CronogramaTemplate(db.Model):
    """
    Template reutilizável de cronograma.
    O gestor define um conjunto de tarefas/subatividades padrão (ex: "Fachada",
    "Fundação") que pode ser aplicado a qualquer obra, criando TarefaCronograma
    automaticamente.
    """
    __tablename__ = 'cronograma_template'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    categoria = db.Column(db.String(100))   # ex: Fachada, Fundação, Cobertura
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admin = db.relationship('Usuario', backref='cronograma_templates')
    itens = db.relationship(
        'CronogramaTemplateItem',
        backref='template',
        cascade='all, delete-orphan',
        order_by='CronogramaTemplateItem.ordem',
    )

    def __repr__(self):
        return f'<CronogramaTemplate {self.nome}>'


class CronogramaTemplateItem(db.Model):
    """
    Item de um template de cronograma.
    Cada item corresponde a uma SubatividadeMestre (catálogo) e define
    duração estimada e quantidade prevista para a tarefa que será criada.
    """
    __tablename__ = 'cronograma_template_item'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_template.id', ondelete='CASCADE'),
        nullable=False,
    )
    subatividade_mestre_id = db.Column(
        db.Integer,
        db.ForeignKey('subatividade_mestre.id', ondelete='SET NULL'),
        nullable=True,
    )
    parent_item_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_template_item.id', ondelete='SET NULL'),
        nullable=True,
    )
    # Nome snapshot — para templates sem subatividade do catálogo
    nome_tarefa = db.Column(db.String(200), nullable=False)
    ordem = db.Column(db.Integer, default=0, nullable=False)
    duracao_dias = db.Column(db.Integer, default=1, nullable=False)
    quantidade_prevista = db.Column(db.Float)          # unidade vem da SubatividadeMestre
    responsavel = db.Column(db.String(20), default='empresa')  # empresa | terceiros

    admin_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subatividade = db.relationship('SubatividadeMestre', backref='template_itens')
    filhos = db.relationship(
        'CronogramaTemplateItem',
        backref=db.backref('parent', remote_side='CronogramaTemplateItem.id'),
        foreign_keys='CronogramaTemplateItem.parent_item_id',
        lazy='dynamic',
    )

    def __repr__(self):
        return f'<CronogramaTemplateItem {self.nome_tarefa}>'


class ItemMedicaoComercial(db.Model):
    __tablename__ = 'item_medicao_comercial'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    valor_comercial = db.Column(db.Numeric(15, 2), nullable=False)
    percentual_executado_acumulado = db.Column(db.Numeric(5, 2), default=0)
    valor_executado_acumulado = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default='PENDENTE')
    # Task #82 — vínculo opcional com catálogo
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=True, index=True)
    quantidade = db.Column(db.Numeric(15, 4), nullable=True)
    # Task #82 — origem determinística para dedupe na propagação de proposta
    proposta_item_id = db.Column(db.Integer, db.ForeignKey('proposta_itens.id', ondelete='SET NULL'), nullable=True, index=True, unique=True)
    # Task #89 — snapshot do cálculo paramétrico (explosão de insumos)
    quantidade_medida = db.Column(db.Numeric(15, 4), nullable=True)
    custo_unitario = db.Column(db.Numeric(15, 4), nullable=True)
    preco_unitario = db.Column(db.Numeric(15, 4), nullable=True)
    lucro_unitario = db.Column(db.Numeric(15, 4), nullable=True)
    subtotal = db.Column(db.Numeric(15, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra', backref='itens_medicao_comercial')
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    proposta_item = db.relationship('PropostaItem', foreign_keys=[proposta_item_id])
    tarefas_vinculadas = db.relationship('ItemMedicaoCronogramaTarefa', backref='item_medicao', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ItemMedicaoComercial {self.nome} obra_id={self.obra_id}>'


class ItemMedicaoCronogramaTarefa(db.Model):
    __tablename__ = 'item_medicao_cronograma_tarefa'

    id = db.Column(db.Integer, primary_key=True)
    item_medicao_id = db.Column(db.Integer, db.ForeignKey('item_medicao_comercial.id', ondelete='CASCADE'), nullable=False)
    cronograma_tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefa_cronograma.id', ondelete='CASCADE'), nullable=False)
    peso = db.Column(db.Numeric(5, 2), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    tarefa = db.relationship('TarefaCronograma')

    __table_args__ = (
        db.UniqueConstraint('item_medicao_id', 'cronograma_tarefa_id', name='uq_item_tarefa'),
    )


class MedicaoObra(db.Model):
    __tablename__ = 'medicao_obra'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    data_medicao = db.Column(db.DateTime, default=datetime.utcnow)
    periodo_inicio = db.Column(db.Date, nullable=False)
    periodo_fim = db.Column(db.Date, nullable=False)
    data_inicio = db.Column(db.Date)
    data_fim = db.Column(db.Date)
    percentual_executado = db.Column(db.Float, default=0.0)
    valor_medido = db.Column(db.Numeric(14, 2), default=0)
    valor_total_medido_periodo = db.Column(db.Numeric(15, 2), default=0)
    valor_entrada_abatido_periodo = db.Column(db.Numeric(15, 2), default=0)
    valor_a_faturar_periodo = db.Column(db.Numeric(15, 2), default=0)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDENTE')
    conta_receber_id = db.Column(db.Integer, db.ForeignKey('conta_receber.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra', backref='medicoes')
    itens = db.relationship('MedicaoObraItem', backref='medicao', cascade='all, delete-orphan')
    conta_receber = db.relationship('ContaReceber')

    def __repr__(self):
        return f'<MedicaoObra #{self.numero} obra_id={self.obra_id}>'


class MapaConcorrencia(db.Model):
    """Mapa de concorrência — tabela comparativa de fornecedores para aprovação do cliente"""
    __tablename__ = 'mapa_concorrencia'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    descricao_item = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='pendente', nullable=False)  # pendente / concluido
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obra = db.relationship('Obra', backref='mapas_concorrencia')
    opcoes = db.relationship('OpcaoConcorrencia', backref='mapa', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='OpcaoConcorrencia.id')

    def __repr__(self):
        return f'<MapaConcorrencia #{self.id} obra={self.obra_id}>'


class OpcaoConcorrencia(db.Model):
    """Opção de fornecedor dentro de um Mapa de Concorrência"""
    __tablename__ = 'opcao_concorrencia'

    id = db.Column(db.Integer, primary_key=True)
    mapa_id = db.Column(db.Integer, db.ForeignKey('mapa_concorrencia.id', ondelete='CASCADE'), nullable=False)
    fornecedor_nome = db.Column(db.String(200), nullable=False)
    valor_unitario = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    prazo_entrega = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    selecionada = db.Column(db.Boolean, default=False, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    def __repr__(self):
        return f'<OpcaoConcorrencia #{self.id} mapa={self.mapa_id}>'


class MedicaoObraItem(db.Model):
    __tablename__ = 'medicao_obra_item'

    id = db.Column(db.Integer, primary_key=True)
    medicao_obra_id = db.Column(db.Integer, db.ForeignKey('medicao_obra.id', ondelete='CASCADE'), nullable=False)
    item_medicao_comercial_id = db.Column(db.Integer, db.ForeignKey('item_medicao_comercial.id'), nullable=False)
    percentual_anterior = db.Column(db.Numeric(5, 2), default=0)
    percentual_atual = db.Column(db.Numeric(5, 2), default=0)
    percentual_executado_periodo = db.Column(db.Numeric(5, 2), default=0)
    valor_medido_periodo = db.Column(db.Numeric(15, 2), default=0)
    percentual_executado_acumulado = db.Column(db.Numeric(5, 2), default=0)
    valor_executado_acumulado = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    item_comercial = db.relationship('ItemMedicaoComercial')

    def __repr__(self):
        return f'<MedicaoObraItem medicao={self.medicao_obra_id} item={self.item_medicao_comercial_id}>'


class MedicaoContrato(db.Model):
    """Medição de contrato (cronograma de faturamento FIXO pelo contrato).
    Distinta de MedicaoObra (medição por execução). valor = pct × valor_contrato."""
    __tablename__ = 'medicao_contrato'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    data = db.Column(db.Date)
    pct = db.Column(db.Numeric(7, 5), nullable=False, default=0)
    recebido_no_mes = db.Column(db.String(8))
    obs = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)

    # Fase 0.6 / D1c — base contratual congelada no momento da emissão.
    # `valor` sempre foi property calculada sobre `obra.valor_contrato`, e
    # aprovar um aditivo reprecificava RETROATIVAMENTE toda medição já
    # emitida — inclusive as que o cliente já pagou. NULL = ainda segue o
    # contrato vigente, que é o comportamento correto para medição futura.
    valor_base = db.Column(db.Numeric(15, 2), nullable=True)

    obra = db.relationship('Obra', backref='medicoes_contrato')

    @property
    def valor(self):
        from decimal import Decimal as _D
        base = (self.valor_base if self.valor_base is not None
                else (self.obra.valor_contrato or 0))
        return (_D(str(base)) * _D(str(self.pct or 0)))

    __table_args__ = (
        db.Index('ix_medicao_contrato_obra', 'obra_id'),
        db.Index('ix_medicao_contrato_admin', 'admin_id'),
    )

    def __repr__(self):
        return f'<MedicaoContrato {self.nome} obra={self.obra_id}>'


class MapaConcorrenciaV2(db.Model):
    """Mapa de Concorrência V2 — tabela multi-fornecedor comparativa (N itens × N fornecedores)"""
    __tablename__ = 'mapa_concorrencia_v2'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='aberto', nullable=False)  # aberto / concluido
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    obra = db.relationship('Obra', backref=db.backref('mapas_v2', lazy='dynamic', cascade='all,delete-orphan'))
    fornecedores = db.relationship('MapaFornecedor', backref='mapa', cascade='all, delete-orphan',
                                   order_by='MapaFornecedor.ordem')
    itens = db.relationship('MapaItemCotacao', backref='mapa', cascade='all, delete-orphan',
                            order_by='MapaItemCotacao.ordem')
    cotacoes = db.relationship('MapaCotacao', backref='mapa', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<MapaConcorrenciaV2 #{self.id} "{self.nome}" obra={self.obra_id}>'


class MapaFornecedor(db.Model):
    """Fornecedor (coluna) de um MapaConcorrenciaV2"""
    __tablename__ = 'mapa_fornecedor'

    id = db.Column(db.Integer, primary_key=True)
    mapa_id = db.Column(db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    ordem = db.Column(db.Integer, default=0)
    # Task #21 — atributos comerciais por fornecedor (não mais por célula item×forn)
    prazo_entrega = db.Column(db.String(100))
    observacao = db.Column(db.Text)
    condicoes_pagamento = db.Column(db.String(255))

    cotacoes = db.relationship('MapaCotacao', backref='fornecedor', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<MapaFornecedor #{self.id} "{self.nome}">'


class MapaItemCotacao(db.Model):
    """Item (linha) de um MapaConcorrenciaV2"""
    __tablename__ = 'mapa_item_cotacao'

    id = db.Column(db.Integer, primary_key=True)
    mapa_id = db.Column(db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    unidade = db.Column(db.String(50), default='un')
    quantidade = db.Column(db.Numeric(12, 3), default=1)
    ordem = db.Column(db.Integer, default=0)
    # Task #21 — fornecedor escolhido para compra deste item (admin define;
    # também espelhado a partir da seleção do cliente no portal)
    fornecedor_escolhido_id = db.Column(
        db.Integer,
        db.ForeignKey('mapa_fornecedor.id', ondelete='SET NULL'),
        nullable=True,
    )

    cotacoes = db.relationship('MapaCotacao', backref='item', cascade='all, delete-orphan')
    fornecedor_escolhido = db.relationship('MapaFornecedor', foreign_keys=[fornecedor_escolhido_id])

    def __repr__(self):
        return f'<MapaItemCotacao #{self.id} "{self.descricao}">'


class MapaCotacao(db.Model):
    """Cotação (célula) de um item × fornecedor no MapaConcorrenciaV2"""
    __tablename__ = 'mapa_cotacao'

    id = db.Column(db.Integer, primary_key=True)
    mapa_id = db.Column(db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('mapa_item_cotacao.id', ondelete='CASCADE'), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('mapa_fornecedor.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    valor_unitario = db.Column(db.Numeric(14, 2), default=0)
    # DEPRECATED Task #21 — prazo agora vive em MapaFornecedor.prazo_entrega.
    # Mantido por compatibilidade de dados históricos / rollback seguro.
    prazo = db.Column(db.String(100))
    selecionado = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<MapaCotacao item={self.item_id} forn={self.fornecedor_id} val={self.valor_unitario}>'


class RelatorioCompraMapa(db.Model):
    """Relatório de Compra (PDF) gerado a partir de um MapaConcorrenciaV2.

    Cada vez que o admin clica em "Gerar Relatório de Compra" um PDF é
    materializado em static/uploads/relatorios_mapa/<obra_id>/ e um
    registro é criado aqui — permitindo histórico de versões e download
    via portal do cliente.
    """
    __tablename__ = 'relatorio_compra_mapa'

    id = db.Column(db.Integer, primary_key=True)
    mapa_id = db.Column(db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='CASCADE'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    gerado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    versao = db.Column(db.Integer, default=1, nullable=False)
    arquivo_path = db.Column(db.String(500), nullable=False)  # caminho relativo dentro de static/
    arquivo_nome = db.Column(db.String(255), nullable=False)
    total_geral = db.Column(db.Numeric(14, 2), default=0)
    gerado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    mapa = db.relationship('MapaConcorrenciaV2', backref=db.backref(
        'relatorios_compra', lazy='dynamic',
        order_by='RelatorioCompraMapa.versao.desc()',
        cascade='all, delete-orphan'
    ))
    obra = db.relationship('Obra', backref=db.backref(
        'relatorios_compra_mapa', lazy='dynamic',
        order_by='RelatorioCompraMapa.gerado_em.desc()',
    ))
    gerado_por = db.relationship('Usuario', foreign_keys=[gerado_por_id])

    def __repr__(self):
        return f'<RelatorioCompraMapa #{self.id} mapa={self.mapa_id} v{self.versao}>'


class CronogramaCliente(db.Model):
    """
    Cronograma editável exclusivo para apresentação ao cliente no Portal.
    Gerado a partir de TarefaCronograma mas editável independentemente,
    sem impactar métricas internas.
    """
    __tablename__ = 'cronograma_cliente'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome_tarefa = db.Column(db.String(200), nullable=False)
    data_inicio_apresentacao = db.Column(db.Date, nullable=True)
    data_fim_apresentacao = db.Column(db.Date, nullable=True)
    percentual_apresentacao = db.Column(db.Float, default=0.0, nullable=False)
    ordem = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    obra = db.relationship('Obra', backref=db.backref('cronograma_cliente_items', lazy='dynamic', cascade='all,delete-orphan'))

    def __repr__(self):
        return f'<CronogramaCliente #{self.id} obra={self.obra_id} "{self.nome_tarefa}">'


# ─────────────────────────────────────────────────────────────────────────────
# SUBEMPREITEIRO — Cadastro, alocação no RDO e custos vinculados (Migration 113)
# ─────────────────────────────────────────────────────────────────────────────

class Subempreiteiro(db.Model):
    """Equipe terceirizada gerida pela própria empresa, com produtividade mensurável."""
    __tablename__ = 'subempreiteiro'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    especialidade = db.Column(db.String(150), nullable=True)
    contato_responsavel = db.Column(db.String(150), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    chave_pix = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('cnpj', 'admin_id', name='uk_subempreiteiro_cnpj_admin'),
        db.Index('idx_subempreiteiro_admin_ativo', 'admin_id', 'ativo'),
    )

    def __repr__(self):
        return f'<Subempreiteiro {self.nome}>'


class RDOSubempreitadaApontamento(db.Model):
    """
    Apontamento diário de uma equipe de subempreitada em uma tarefa do cronograma.
    Permite múltiplos subempreiteiros por tarefa em um mesmo RDO (várias equipes em paralelo).
    """
    __tablename__ = 'rdo_subempreitada_apontamento'

    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'), nullable=False)
    tarefa_cronograma_id = db.Column(
        db.Integer, db.ForeignKey('tarefa_cronograma.id', ondelete='CASCADE'), nullable=False
    )
    subempreiteiro_id = db.Column(
        db.Integer, db.ForeignKey('subempreiteiro.id', ondelete='RESTRICT'), nullable=False
    )
    qtd_pessoas = db.Column(db.Integer, nullable=False, default=0)
    horas_trabalhadas = db.Column(db.Float, nullable=False, default=0.0)
    quantidade_produzida = db.Column(db.Float, nullable=False, default=0.0)
    homem_hora = db.Column(db.Float, nullable=True)  # qtd / (pessoas * horas)
    observacoes = db.Column(db.Text, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship(
        'RDO', backref=db.backref('subempreitada_apontamentos', cascade='all, delete-orphan')
    )
    tarefa = db.relationship('TarefaCronograma', backref='subempreitada_apontamentos')
    subempreiteiro = db.relationship('Subempreiteiro', backref='apontamentos_rdo')

    __table_args__ = (
        db.Index('idx_rdo_sub_apontamento_rdo', 'rdo_id'),
        db.Index('idx_rdo_sub_apontamento_tarefa', 'tarefa_cronograma_id'),
        db.Index('idx_rdo_sub_apontamento_sub', 'subempreiteiro_id'),
    )

    def calcular_homem_hora(self):
        try:
            denom = (self.qtd_pessoas or 0) * (self.horas_trabalhadas or 0)
            if denom > 0:
                self.homem_hora = round(float(self.quantidade_produzida or 0) / denom, 4)
            else:
                self.homem_hora = None
        except Exception:
            self.homem_hora = None
        return self.homem_hora

    def __repr__(self):
        return (
            f'<RDOSubempreitadaApontamento rdo={self.rdo_id} '
            f'tarefa={self.tarefa_cronograma_id} sub={self.subempreiteiro_id}>'
        )


@_sa_event.listens_for(RDOSubempreitadaApontamento, 'before_insert')
@_sa_event.listens_for(RDOSubempreitadaApontamento, 'before_update')
def _auto_calc_homem_hora(mapper, connection, target):
    target.calcular_homem_hora()


# ═══════════════════════════════════════════════════════════════════════
# TASK #70 — RESUMO DE CUSTOS DA OBRA (Migration 118)
# ═══════════════════════════════════════════════════════════════════════

class ObraServicoCusto(db.Model):
    """Planejamento de custo por serviço da obra.

    Cada linha representa a visão INTERNA (custo) da mesma linha de serviço
    tratada comercialmente por ItemMedicaoComercial. A FK
    item_medicao_comercial_id é opcional e UNIQUE (1-pra-1) quando preenchida.
    """
    __tablename__ = 'obra_servico_custo'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False, index=True)

    item_medicao_comercial_id = db.Column(
        db.Integer,
        db.ForeignKey('item_medicao_comercial.id', ondelete='SET NULL'),
        nullable=True,
        unique=True,
    )
    servico_obra_real_id = db.Column(
        db.Integer,
        db.ForeignKey('servico_obra_real.id', ondelete='SET NULL'),
        nullable=True,
    )
    # Task #82 — vínculo com catálogo (analítico cross-obra)
    servico_catalogo_id = db.Column(
        db.Integer,
        db.ForeignKey('servico.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(200), nullable=False)

    # Orçado — digitado manualmente pelo gestor
    valor_orcado = db.Column(db.Numeric(15, 2), default=0, nullable=False)

    # Realizado — snapshot agregado de GestaoCustoFilho por categoria;
    # pode ser sobrescrito manualmente via override_realizado_manual.
    realizado_material = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    realizado_mao_obra = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    realizado_outros = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    override_realizado_manual = db.Column(db.Boolean, default=False, nullable=False)

    # A Realizar — material (manual ou vindo de cotação selecionada) + mão de obra
    # planejada (soma das linhas de equipe) + outros.
    material_a_realizar = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    cotacao_selecionada_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_cotacao_interna.id', ondelete='SET NULL'),
        nullable=True,
    )
    mao_obra_a_realizar = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    outros_a_realizar = db.Column(db.Numeric(15, 2), default=0, nullable=False)

    # Físico-financeiro: quem paga cada categoria — 'veks' (empresa) ou 'fat_direto'
    # (cliente paga o fornecedor direto). Default 'veks'.
    fonte_material = db.Column(db.String(20), default='veks', nullable=False)
    fonte_mao_obra = db.Column(db.String(20), default='veks', nullable=False)
    fonte_outros = db.Column(db.String(20), default='veks', nullable=False)

    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    obra = db.relationship('Obra', backref=db.backref('servicos_custo', cascade='all, delete-orphan'))
    item_medicao = db.relationship('ItemMedicaoComercial', foreign_keys=[item_medicao_comercial_id])
    servico_real = db.relationship('ServicoObraReal', foreign_keys=[servico_obra_real_id])
    servico_catalogo = db.relationship('Servico', foreign_keys=[servico_catalogo_id])
    equipe_planejada = db.relationship(
        'ObraServicoEquipePlanejada',
        backref='servico_custo',
        cascade='all, delete-orphan',
        foreign_keys='ObraServicoEquipePlanejada.obra_servico_custo_id',
    )
    cotacoes = db.relationship(
        'ObraServicoCotacaoInterna',
        backref='servico_custo',
        cascade='all, delete-orphan',
        foreign_keys='ObraServicoCotacaoInterna.obra_servico_custo_id',
    )

    @property
    def realizado_total(self):
        return float(self.realizado_material or 0) + float(self.realizado_mao_obra or 0) + float(self.realizado_outros or 0)

    @property
    def a_realizar_total(self):
        return float(self.material_a_realizar or 0) + float(self.mao_obra_a_realizar or 0) + float(self.outros_a_realizar or 0)

    @property
    def saldo(self):
        return float(self.valor_orcado or 0) - (self.realizado_total + self.a_realizar_total)

    def __repr__(self):
        return f'<ObraServicoCusto #{self.id} obra={self.obra_id} {self.nome}>'


class ObraServicoCustoItem(db.Model):
    """Linha de custo (insumo) de uma etapa, por obra. Fonte da verdade do custo
    previsto: ObraServicoCusto.mao_obra_a_realizar/material_a_realizar = soma destas
    linhas por `fonte` (veks/fat_direto). Ver design 2026-06-24."""
    __tablename__ = 'obra_servico_custo_item'

    id = db.Column(db.Integer, primary_key=True)
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id', ondelete='CASCADE'),
        nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # previsto por período
    fonte = db.Column(db.String(20), nullable=False, default='veks')  # 'veks' | 'fat_direto'
    ordem = db.Column(db.Integer, default=0)
    # Janela de desembolso previsto (caixa): o valor é faseado entre estas datas.
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)

    osc = db.relationship('ObraServicoCusto', backref=db.backref(
        'itens_custo', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<ObraServicoCustoItem osc={self.obra_servico_custo_id} {self.descricao!r}>'


class ObraServicoEquipePlanejada(db.Model):
    """Linha de equipe planejada por serviço: funcionário + quantidade dias +
    custos diários snapshot (diária, alimentação, transporte)."""
    __tablename__ = 'obra_servico_equipe_planejada'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    obra_servico_custo_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_custo.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)
    funcionario_nome = db.Column(db.String(120), nullable=False)
    quantidade_dias = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    diaria = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    almoco_e_cafe = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    transporte = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    funcionario = db.relationship('Funcionario', foreign_keys=[funcionario_id])

    @property
    def custo_dia(self):
        return float(self.diaria or 0) + float(self.almoco_e_cafe or 0) + float(self.transporte or 0)

    @property
    def subtotal(self):
        return self.custo_dia * float(self.quantidade_dias or 0)

    def __repr__(self):
        return f'<EquipePlanejada func={self.funcionario_nome} dias={self.quantidade_dias}>'


class ObraServicoCotacaoInterna(db.Model):
    """Cotação interna de material por serviço (isolado do Mapa de Concorrência
    do cliente). Apenas 1 cotação SELECIONADA por serviço."""
    __tablename__ = 'obra_servico_cotacao_interna'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    obra_servico_custo_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_custo.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    fornecedor_nome = db.Column(db.String(200), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=True)
    prazo_entrega = db.Column(db.String(100))
    condicao_pagamento = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    selecionada = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    linhas = db.relationship(
        'ObraServicoCotacaoInternaLinha',
        backref='cotacao',
        cascade='all, delete-orphan',
    )

    @property
    def valor_total(self):
        return sum(float(l.subtotal) for l in self.linhas)

    def __repr__(self):
        return f'<CotacaoInterna #{self.id} {self.fornecedor_nome} sel={self.selecionada}>'


class ObraServicoCotacaoInternaLinha(db.Model):
    """Linha de material dentro de uma cotação interna."""
    __tablename__ = 'obra_servico_cotacao_interna_linha'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    cotacao_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_cotacao_interna.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    descricao = db.Column(db.String(300), nullable=False)
    unidade = db.Column(db.String(20))
    quantidade = db.Column(db.Numeric(15, 4), default=0, nullable=False)
    valor_unitario = db.Column(db.Numeric(15, 2), default=0, nullable=False)

    @property
    def subtotal(self):
        return float(self.quantidade or 0) * float(self.valor_unitario or 0)


# ─────────────────────────────────────────────────────────────────────────
# Task #70 — Listeners de recálculo automático
# ─────────────────────────────────────────────────────────────────────────

_RESUMO_PENDING_KEY = '_resumo_custos_pending'
_RESUMO_REENTRANT_KEY = '_resumo_custos_recalc_running'


def _resumo_pending_bag(session):
    """Retorna/inicializa o bag de trabalho pendente na session.info.
    Nenhum acesso a DB é feito aqui — apenas coleta em memória."""
    bag = session.info.get(_RESUMO_PENDING_KEY)
    if bag is None:
        bag = {'servicos': set(), 'obras': {}}
        session.info[_RESUMO_PENDING_KEY] = bag
    return bag


def _agendar_via_target(target, obra=False):
    """Registra o target para recálculo posterior (no before_commit),
    sem emitir queries ou flush dentro do ciclo de flush atual."""
    try:
        from sqlalchemy.orm import object_session
        sess = object_session(target) or db.session()
        bag = _resumo_pending_bag(sess)
        if obra and getattr(target, 'obra_id', None):
            bag['obras'][target.obra_id] = getattr(target, 'admin_id', None)
        else:
            svc_id = getattr(target, 'obra_servico_custo_id', None)
            if svc_id is not None:
                bag['servicos'].add(svc_id)
    except Exception:
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "resumo_custos: falha ao agendar recálculo (target=%r)", target,
            exc_info=True,
        )


@_sa_event.listens_for(ObraServicoEquipePlanejada, 'after_insert')
@_sa_event.listens_for(ObraServicoEquipePlanejada, 'after_update')
@_sa_event.listens_for(ObraServicoEquipePlanejada, 'after_delete')
def _equipe_planejada_changed(mapper, connection, target):
    _agendar_via_target(target, obra=False)


@_sa_event.listens_for(ObraServicoCotacaoInterna, 'after_insert')
@_sa_event.listens_for(ObraServicoCotacaoInterna, 'after_update')
def _cotacao_interna_changed(mapper, connection, target):
    if target.selecionada:
        _agendar_via_target(target, obra=False)


@_sa_event.listens_for(GestaoCustoFilho, 'after_insert')
@_sa_event.listens_for(GestaoCustoFilho, 'after_update')
@_sa_event.listens_for(GestaoCustoFilho, 'after_delete')
def _gestao_custo_filho_changed(mapper, connection, target):
    if target.obra_id:
        _agendar_via_target(target, obra=True)


@_sa_event.listens_for(db.session, 'after_flush_postexec')
def _resumo_custos_after_flush(session, flush_context):
    """Processa o recálculo agendado logo após o término do flush atual.

    after_flush_postexec executa depois que todas as operações de INSERT/
    UPDATE do flush já foram emitidas, fora do ciclo crítico de unit-of-work.
    As mutações feitas aqui são incluídas no próximo flush (que acontece como
    parte do commit em curso), garantindo que o snapshot de realizado/a_realizar
    persista junto com a transação original. Erros são logados em WARNING
    (nunca silenciados).
    """
    bag = session.info.pop(_RESUMO_PENDING_KEY, None)
    if not bag:
        return
    servicos = list(bag.get('servicos') or [])
    obras = dict(bag.get('obras') or {})
    if not servicos and not obras:
        return
    if session.info.get(_RESUMO_REENTRANT_KEY):
        return
    session.info[_RESUMO_REENTRANT_KEY] = True
    try:
        from services.resumo_custos_obra import (
            recalcular_servico,
            recalcular_obra,
        )
        for svc_id in servicos:
            ok = recalcular_servico(svc_id)
            if not ok:
                import logging as _lg
                _lg.getLogger(__name__).warning(
                    "resumo_custos: recalcular_servico(%s) retornou False", svc_id,
                )
        for obra_id, admin_id in obras.items():
            ok = recalcular_obra(obra_id, admin_id=admin_id)
            if not ok:
                import logging as _lg
                _lg.getLogger(__name__).warning(
                    "resumo_custos: recalcular_obra(%s) retornou False", obra_id,
                )
    except Exception:
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "resumo_custos: falha no recálculo pré-commit "
            "(svcs=%s obras=%s)",
            servicos, list(obras.keys()),
            exc_info=True,
        )
    finally:
        session.info.pop(_RESUMO_REENTRANT_KEY, None)


class NotificacaoOrcamento(db.Model):
    """Task #76 — Notificação persistente de estouro de orçamento por serviço.

    Há 1 registro por (admin_id, obra_id, obra_servico_custo_id). Quando o
    serviço estoura novamente após resolução, a mesma linha é reativada
    (ativa=True, resolvida_em=NULL). Quando o serviço volta para dentro do
    orçado, a linha é marcada como resolvida.
    """
    __tablename__ = 'notificacao_orcamento'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False, index=True)
    obra_servico_custo_id = db.Column(
        db.Integer,
        db.ForeignKey('obra_servico_custo.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    percentual = db.Column(db.Numeric(7, 2), nullable=False, default=0)
    valor_excesso = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    valor_orcado = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    valor_projetado = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    mensagem = db.Column(db.Text, nullable=False, default='')

    ativa = db.Column(db.Boolean, nullable=False, default=True, index=True)
    resolvida_em = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    obra = db.relationship('Obra', backref=db.backref('notificacoes_orcamento', cascade='all, delete-orphan'))
    servico = db.relationship('ObraServicoCusto', backref=db.backref('notificacoes_orcamento', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint(
            'admin_id', 'obra_id', 'obra_servico_custo_id',
            name='uq_notif_orcamento_servico',
        ),
    )

    def __repr__(self):
        return f'<NotificacaoOrcamento svc={self.obra_servico_custo_id} ativa={self.ativa}>'


def _calc_proposta_item_snapshot(target):
    """Task #89: garante snapshot mínimo (subtotal=qtd×preço) em PropostaItem."""
    try:
        if target.subtotal is None:
            q = target.quantidade or 0
            p = target.preco_unitario or 0
            target.subtotal = (q * p)
    except Exception:
        pass


def _calc_item_medicao_snapshot(target):
    """Task #89: garante snapshot mínimo em ItemMedicaoComercial.

    - Se preco_unitario faltar mas houver quantidade>0 e valor_comercial,
      deriva preco_unitario = valor_comercial / quantidade.
    - subtotal = valor_comercial (sempre).
    """
    try:
        if (target.preco_unitario is None
                and target.quantidade and target.valor_comercial):
            try:
                q = float(target.quantidade)
                if q > 0:
                    target.preco_unitario = float(target.valor_comercial) / q
            except Exception:
                pass
        if target.subtotal is None and target.valor_comercial is not None:
            target.subtotal = target.valor_comercial
    except Exception:
        pass


@_sa_event.listens_for(PropostaItem, 'before_insert')
@_sa_event.listens_for(PropostaItem, 'before_update')
def _proposta_item_before_save(mapper, connection, target):
    _calc_proposta_item_snapshot(target)


@_sa_event.listens_for(ItemMedicaoComercial, 'before_insert')
@_sa_event.listens_for(ItemMedicaoComercial, 'before_update')
def _item_medicao_before_save(mapper, connection, target):
    _calc_item_medicao_snapshot(target)


@_sa_event.listens_for(ItemMedicaoComercial, 'after_insert')
def _item_medicao_auto_cria_custo(mapper, connection, target):
    """Ao criar um ItemMedicaoComercial, cria automaticamente o par
    ObraServicoCusto vinculado (se ainda não existir).

    Task #82: herda valor_comercial → valor_orcado e servico_id →
    servico_catalogo_id quando presentes, fechando o ciclo
    catálogo → proposta → medição comercial → planejamento de custo.
    """
    try:
        tbl = ObraServicoCusto.__table__
        existing = connection.execute(
            tbl.select().where(tbl.c.item_medicao_comercial_id == target.id)
        ).first()
        if existing:
            return
        valor_orcado = target.valor_comercial or 0
        servico_catalogo_id = getattr(target, 'servico_id', None)
        connection.execute(
            tbl.insert().values(
                admin_id=target.admin_id,
                obra_id=target.obra_id,
                item_medicao_comercial_id=target.id,
                servico_catalogo_id=servico_catalogo_id,
                nome=target.nome,
                valor_orcado=valor_orcado,
                realizado_material=0,
                realizado_mao_obra=0,
                realizado_outros=0,
                override_realizado_manual=False,
                material_a_realizar=0,
                mao_obra_a_realizar=0,
                outros_a_realizar=0,
            )
        )
    except Exception:
        import logging as _lg
        _lg.getLogger(__name__).exception("Erro ao auto-criar ObraServicoCusto para ItemMedicaoComercial")


# ─────────────────────────────────────────────────────────────────────────
# Task #82 — Catálogo de Insumos + Composição de Serviços
# ─────────────────────────────────────────────────────────────────────────
class Insumo(db.Model):
    """Item base reutilizável usado na composição de serviços.

    Tipo: MATERIAL | MAO_OBRA | EQUIPAMENTO. O preço base é versionado em
    PrecoBaseInsumo (vigência por data); o cálculo do serviço usa o vigente
    na data de referência.
    """
    __tablename__ = 'insumo'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='MATERIAL')
    unidade = db.Column(db.String(20), nullable=False, default='un')
    descricao = db.Column(db.Text)
    # Task #166: coeficiente padrão de consumo do insumo (sugestão automática
    # ao adicionar este insumo na composição de um serviço). NÃO é usado no
    # cálculo das composições já existentes; só pré-preenche o picker.
    coeficiente_padrao = db.Column(db.Numeric(15, 6), nullable=False, default=1)
    # Task #19 — Quantidade Comercial: embalagem/múltiplo de fornecimento.
    # fator_comercial = tamanho do pacote do fornecedor (ex: 100 parafusos, 6 m barra).
    # 1.0 = compra unitária.
    # qtd_compra = ceil(qtd_técnica / fator_comercial) × fator_comercial.
    fator_comercial = db.Column(db.Numeric(15, 4), nullable=False, default=1)
    # Unidade comercial (ex: "pacote", "barra") — opcional; se vazio usa `unidade`.
    unidade_comercial = db.Column(db.String(30), nullable=True)
    # Task #75 — fracionavel: True = pode comprar fração (kg, m, m², h…).
    # False = unidade inteira obrigatória (peça, barra, chapa, un…) —
    # força ceil mesmo quando fator_comercial = 1.
    # Default True para retrocompatibilidade com dados existentes.
    fracionavel = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    # Task #36 — tipo de medição dimensional (UNITARIO|AREA|PERIMETRO|PERIMETRO_PE_DIREITO|AREA_PE_DIREITO|LINEAR)
    tipo_medicao = db.Column(db.String(30), nullable=False, default='UNITARIO')
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    precos = db.relationship(
        'PrecoBaseInsumo',
        backref='insumo',
        cascade='all, delete-orphan',
        order_by='PrecoBaseInsumo.vigencia_inicio.desc()',
    )
    composicoes = db.relationship(
        'ComposicaoServico',
        backref='insumo',
        cascade='all, delete-orphan',
    )

    def preco_vigente(self, data_ref=None):
        """Retorna o preço unitário vigente em data_ref (ou hoje), ou 0."""
        from datetime import date as _date
        d = data_ref or _date.today()
        for p in sorted(self.precos, key=lambda x: x.vigencia_inicio, reverse=True):
            if p.vigencia_inicio and p.vigencia_inicio > d:
                continue
            if p.vigencia_fim and p.vigencia_fim < d:
                continue
            return float(p.valor or 0)
        return 0.0

    def __repr__(self):
        return f'<Insumo #{self.id} {self.nome}>'


class PrecoBaseInsumo(db.Model):
    """Histórico de preço base de um insumo, com vigência."""
    __tablename__ = 'preco_base_insumo'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    insumo_id = db.Column(
        db.Integer,
        db.ForeignKey('insumo.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    valor = db.Column(db.Numeric(15, 4), nullable=False, default=0)
    vigencia_inicio = db.Column(db.Date, nullable=False, default=date.today)
    vigencia_fim = db.Column(db.Date, nullable=True)
    observacao = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PrecoBaseInsumo #{self.id} insumo={self.insumo_id} R$ {self.valor}>'


class ComposicaoServico(db.Model):
    """Linha de composição: serviço × insumo × coeficiente de consumo
    (quanto de insumo por unidade do serviço)."""
    __tablename__ = 'composicao_servico'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey('servico.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    insumo_id = db.Column(
        db.Integer,
        db.ForeignKey('insumo.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    coeficiente = db.Column(db.Numeric(15, 6), nullable=False, default=0)
    unidade = db.Column(db.String(20), nullable=True)  # snapshot opcional da unidade do insumo (ex: "h", "kg", "un")
    observacao = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('servico_id', 'insumo_id', name='uq_composicao_servico_insumo'),
    )

    def __repr__(self):
        return f'<ComposicaoServico svc={self.servico_id} ins={self.insumo_id} coef={self.coeficiente}>'


class SubatividadeMaoObra(db.Model):
    """Task #62 — junção N:N entre SubatividadeMestre e ComposicaoServico
    (linhas de mão-de-obra do serviço). Permite que uma subatividade aponte
    para várias composições de mão-de-obra (várias funções/insumos), e que
    uma composição apareça em várias subatividades do mesmo serviço.
    """
    __tablename__ = 'subatividade_mao_obra'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    subatividade_mestre_id = db.Column(
        db.Integer,
        db.ForeignKey('subatividade_mestre.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    composicao_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('composicao_servico.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subatividade = db.relationship(
        'SubatividadeMestre',
        backref=db.backref('composicoes_mao_obra', cascade='all, delete-orphan'),
    )
    composicao = db.relationship(
        'ComposicaoServico',
        backref=db.backref('subatividades_vinculadas', cascade='all, delete-orphan'),
    )

    __table_args__ = (
        db.UniqueConstraint(
            'subatividade_mestre_id', 'composicao_servico_id',
            name='uq_subatividade_composicao',
        ),
    )

    def __repr__(self):
        return (
            f'<SubatividadeMaoObra sub={self.subatividade_mestre_id} '
            f'comp={self.composicao_servico_id}>'
        )


class ComposicaoServicoHistorico(db.Model):
    """Histórico de alterações no coeficiente de uma linha de ComposicaoServico.

    Criado quando o usuário aplica a produtividade real como referência no catálogo
    (botão "Aplicar como referência" nas Métricas — Task #3).
    Permite rastrear quando e por quem cada coeficiente foi alterado.
    """
    __tablename__ = 'composicao_servico_historico'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    composicao_servico_id = db.Column(
        db.Integer,
        db.ForeignKey('composicao_servico.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id', ondelete='CASCADE'), nullable=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumo.id', ondelete='CASCADE'), nullable=True)
    coeficiente_anterior = db.Column(db.Numeric(15, 6), nullable=False)
    coeficiente_novo = db.Column(db.Numeric(15, 6), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    data_referencia_inicio = db.Column(db.Date, nullable=True)
    data_referencia_fim = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    composicao = db.relationship('ComposicaoServico',
                                  backref=db.backref('historico', cascade='all, delete-orphan'))
    autor = db.relationship('Usuario', foreign_keys=[autor_id])

    def __repr__(self):
        return (
            f'<ComposicaoServicoHistorico comp={self.composicao_servico_id} '
            f'{self.coeficiente_anterior}→{self.coeficiente_novo}>'
        )


# ===================================================================
# Task #115 — Orçamento (camada interna) → Proposta (camada cliente)
# ===================================================================

class Orcamento(db.Model):
    """Orçamento interno (camada de custo/preço). Gera Proposta para o cliente."""
    __tablename__ = 'orcamento'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    numero = db.Column(db.String(50), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    cliente_nome = db.Column(db.String(255))

    # Globais (sobrescrevem o serviço quando definidos)
    imposto_pct_global = db.Column(db.Numeric(5, 2), nullable=True)
    margem_pct_global = db.Column(db.Numeric(5, 2), nullable=True)

    # Totais snapshot
    custo_total = db.Column(db.Numeric(15, 2), default=0)
    venda_total = db.Column(db.Numeric(15, 2), default=0)
    lucro_total = db.Column(db.Numeric(15, 2), default=0)

    status = db.Column(db.String(30), default='rascunho', index=True)  # rascunho, fechado, convertido
    # DEPRECATED (Task #115 v2): mantido apenas para compatibilidade com dados existentes.
    # Use a relação 1→N via Proposta.orcamento_id (`propostas_geradas` abaixo).
    ultima_proposta_id = db.Column('proposta_id', db.Integer,
                                   db.ForeignKey('propostas_comerciais.id', ondelete='SET NULL'),
                                   nullable=True, index=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship('Cliente')
    ultima_proposta = db.relationship('Proposta', foreign_keys=[ultima_proposta_id])
    propostas_geradas = db.relationship('Proposta', foreign_keys='Proposta.orcamento_id',
                                        backref='orcamento_origem',
                                        order_by='Proposta.criado_em.desc()')
    itens = db.relationship('OrcamentoItem', backref='orcamento', cascade='all, delete-orphan',
                            order_by='OrcamentoItem.ordem')

    __table_args__ = (
        db.UniqueConstraint('admin_id', 'numero', name='uq_orcamento_numero_tenant'),
    )

    def __repr__(self):
        return f'<Orcamento {self.numero}>'


class OrcamentoItem(db.Model):
    """Item do orçamento — snapshot da composição do serviço com overrides editáveis."""
    __tablename__ = 'orcamento_item'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id', ondelete='CASCADE'),
                             nullable=False, index=True)
    ordem = db.Column(db.Integer, nullable=False, default=1)

    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id', ondelete='SET NULL'), nullable=True, index=True)
    descricao = db.Column(db.String(500), nullable=False)
    unidade = db.Column(db.String(20), nullable=False, default='un')
    quantidade = db.Column(db.Numeric(15, 4), nullable=False, default=0)

    # Overrides per-item (sobrescrevem global e serviço)
    imposto_pct = db.Column(db.Numeric(5, 2), nullable=True)
    margem_pct = db.Column(db.Numeric(5, 2), nullable=True)

    # Snapshot da composição editado: lista de
    # {tipo, insumo_id, nome, unidade, coeficiente, preco_unitario, subtotal_unitario}
    composicao_snapshot = db.Column(JSON, default=list)

    # Task #118 — override do template de cronograma SÓ para esta linha do
    # orçamento (não altera Servico.template_padrao_id no Catálogo).
    # NULL = "usar template padrão do serviço".
    cronograma_template_override_id = db.Column(
        db.Integer,
        db.ForeignKey('cronograma_template.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    custo_unitario = db.Column(db.Numeric(15, 4), default=0)
    preco_venda_unitario = db.Column(db.Numeric(15, 4), default=0)
    custo_total = db.Column(db.Numeric(15, 2), default=0)
    venda_total = db.Column(db.Numeric(15, 2), default=0)
    lucro_total = db.Column(db.Numeric(15, 2), default=0)

    observacao = db.Column(db.Text)
    # Task #18 — itens inclusos / exclusos por SERVIÇO (texto livre, uma linha
    # por item; renderizados como bullets no card expansível). Campos próprios
    # da linha do orçamento — propagados para PropostaItem em gerar_proposta.
    itens_inclusos = db.Column(db.Text)
    itens_exclusos = db.Column(db.Text)
    # Task #36 — medição dimensional: tipo efetivo do item + dimensões usadas no cálculo
    tipo_medicao_override = db.Column(db.String(30), nullable=True)
    dim_largura = db.Column(db.Numeric(15, 4), nullable=True)
    dim_comprimento = db.Column(db.Numeric(15, 4), nullable=True)
    dim_perimetro = db.Column(db.Numeric(15, 4), nullable=True)
    dim_pe_direito = db.Column(db.Numeric(15, 4), nullable=True)
    dim_area_manual = db.Column(db.Numeric(15, 4), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    servico = db.relationship('Servico', foreign_keys=[servico_id])
    cronograma_template_override = db.relationship(
        'CronogramaTemplate', foreign_keys=[cronograma_template_override_id]
    )

    def __repr__(self):
        return f'<OrcamentoItem {self.id} svc={self.servico_id}>'


# ============================================================================
# Task #42 — CRM de Leads com Kanban e criação automática de Cliente
# ============================================================================

class LeadStatus(Enum):
    """Status do lead = colunas do Kanban (rótulos fixos do sistema).
    A ordem aqui é a ordem em que aparecem no quadro.
    """
    EM_FILA = "Em fila"
    EM_ANDAMENTO = "Em andamento"
    VALIDACAO = "Validação"
    ENVIADO = "Enviado"
    APROVADO = "Aprovado"
    FEEDBACK = "Feedback"
    CONGELADO = "Congelado"
    PERDIDO = "Perdido"


def _crm_lista_table_args(table_name):
    return (
        db.UniqueConstraint('admin_id', 'nome', name=f'uq_{table_name}_admin_nome'),
        db.Index(f'ix_{table_name}_admin', 'admin_id'),
    )


class CrmResponsavel(db.Model):
    __tablename__ = 'crm_responsavel'
    __table_args__ = _crm_lista_table_args('crm_responsavel')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmOrigem(db.Model):
    __tablename__ = 'crm_origem'
    __table_args__ = _crm_lista_table_args('crm_origem')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmCadencia(db.Model):
    __tablename__ = 'crm_cadencia'
    __table_args__ = _crm_lista_table_args('crm_cadencia')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmSituacao(db.Model):
    __tablename__ = 'crm_situacao'
    __table_args__ = _crm_lista_table_args('crm_situacao')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmTipoMaterial(db.Model):
    __tablename__ = 'crm_tipo_material'
    __table_args__ = _crm_lista_table_args('crm_tipo_material')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmTipoObra(db.Model):
    __tablename__ = 'crm_tipo_obra'
    __table_args__ = _crm_lista_table_args('crm_tipo_obra')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrmMotivoPerda(db.Model):
    __tablename__ = 'crm_motivo_perda'
    __table_args__ = _crm_lista_table_args('crm_motivo_perda')

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lead(db.Model):
    """Lead do CRM. Estágio do Kanban = `status` (LeadStatus enum)."""
    __tablename__ = 'lead'
    __table_args__ = (
        db.Index('ix_lead_admin_status', 'admin_id', 'status'),
        db.Index('ix_lead_admin_responsavel', 'admin_id', 'responsavel_id'),
        db.Index('ix_lead_admin_vendedor', 'admin_id', 'vendedor_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Datas
    data_chegada = db.Column(db.Date, nullable=False, default=date.today)
    data_envio = db.Column(db.Date, nullable=True)

    # Identificação
    nome = db.Column(db.String(200), nullable=False)
    contato = db.Column(db.String(50), nullable=True)  # telefone
    email = db.Column(db.String(200), nullable=True)

    # FKs para listas mestras (todas opcionais — admin pode ainda não ter cadastrado)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('crm_responsavel.id'), nullable=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('crm_responsavel.id'), nullable=True)
    orcamentista_id = db.Column(db.Integer, db.ForeignKey('crm_responsavel.id'), nullable=True)
    origem_id = db.Column(db.Integer, db.ForeignKey('crm_origem.id'), nullable=True)
    cadencia_id = db.Column(db.Integer, db.ForeignKey('crm_cadencia.id'), nullable=True)
    situacao_id = db.Column(db.Integer, db.ForeignKey('crm_situacao.id'), nullable=True)
    tipo_material_id = db.Column(db.Integer, db.ForeignKey('crm_tipo_material.id'), nullable=True)
    tipo_obra_id = db.Column(db.Integer, db.ForeignKey('crm_tipo_obra.id'), nullable=True)
    motivo_perda_id = db.Column(db.Integer, db.ForeignKey('crm_motivo_perda.id'), nullable=True)

    # Localização e demanda
    localizacao = db.Column(db.String(200), nullable=True)
    detalhes_localizacao = db.Column(db.Text, nullable=True)
    demanda = db.Column(db.Text, nullable=True)
    pasta = db.Column(db.String(500), nullable=True)

    # Comercial
    valor_proposta = db.Column(db.Numeric(15, 2), nullable=True)
    status = db.Column(db.String(40), nullable=False, default=LeadStatus.EM_FILA.value)
    observacao = db.Column(db.Text, nullable=True)

    # Prioridade — aparece no topo da coluna Kanban com tag visual
    prioridade = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    # Congelado: data sugerida de retomada
    data_retomada = db.Column(db.Date, nullable=True)

    # Task #113 — Prazo do lead (data alvo de fechamento)
    prazo = db.Column(db.Date, nullable=True)

    # Vínculos automáticos
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True, index=True)
    proposta_id = db.Column(
        db.Integer, db.ForeignKey('propostas_comerciais.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    obra_id = db.Column(
        db.Integer, db.ForeignKey('obra.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    # Auditoria
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Marcador para badge "parado há X dias" — atualizado a cada mudança de status
    status_changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Task #110 — Fluxo de aprovação do supervisor na coluna Validação
    validacao_aprovada = db.Column(db.Boolean, default=False, nullable=False, server_default='false')
    validado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    validado_em = db.Column(db.DateTime, nullable=True)
    # Comentário deixado pelo supervisor ao pedir revisão
    comentario_revisao = db.Column(db.Text, nullable=True)

    # Relacionamentos
    validado_por = db.relationship('Usuario', foreign_keys=[validado_por_id])

    responsavel = db.relationship('CrmResponsavel', foreign_keys=[responsavel_id])
    vendedor = db.relationship('CrmResponsavel', foreign_keys=[vendedor_id])
    orcamentista = db.relationship('CrmResponsavel', foreign_keys=[orcamentista_id])
    origem = db.relationship('CrmOrigem', foreign_keys=[origem_id])
    cadencia = db.relationship('CrmCadencia', foreign_keys=[cadencia_id])
    situacao = db.relationship('CrmSituacao', foreign_keys=[situacao_id])
    tipo_material = db.relationship('CrmTipoMaterial', foreign_keys=[tipo_material_id])
    tipo_obra = db.relationship('CrmTipoObra', foreign_keys=[tipo_obra_id])
    motivo_perda = db.relationship('CrmMotivoPerda', foreign_keys=[motivo_perda_id])
    cliente = db.relationship('Cliente', foreign_keys=[cliente_id], backref='leads')
    proposta = db.relationship('Proposta', foreign_keys=[proposta_id], backref='leads')
    obra = db.relationship('Obra', foreign_keys=[obra_id], backref='leads')
    historico = db.relationship('LeadHistorico', backref='lead',
                                cascade='all, delete-orphan',
                                order_by='LeadHistorico.created_at.desc()')

    @property
    def prazo_cor(self):
        """Retorna a classe CSS de cor para o indicador de prazo.
        Calculado com base no percentual de dias decorridos entre
        data_chegada e prazo (dias corridos).

        Verde  < 50%   → prazo-verde
        Amarelo 50–75% → prazo-amarelo
        Laranja 75–90% → prazo-laranja
        Vermelho ≥ 90% ou vencido → prazo-vermelho
        None se prazo não preenchido.
        """
        if not self.prazo:
            return None
        hoje = date.today()
        if hoje >= self.prazo:
            return 'prazo-vermelho'
        if not self.data_chegada:
            return 'prazo-verde'
        total = (self.prazo - self.data_chegada).days
        if total <= 0:
            return 'prazo-vermelho'
        decorrido = (hoje - self.data_chegada).days
        if decorrido < 0:
            decorrido = 0
        pct = decorrido / total * 100
        if pct >= 90:
            return 'prazo-vermelho'
        if pct >= 75:
            return 'prazo-laranja'
        if pct >= 50:
            return 'prazo-amarelo'
        return 'prazo-verde'

    @property
    def dias_parado(self):
        if not self.status_changed_at:
            return 0
        from datetime import timedelta
        hoje = datetime.utcnow().date()
        inicio = self.status_changed_at.date()
        if hoje <= inicio:
            return 0
        dias = 0
        d = inicio + timedelta(days=1)
        while d <= hoje:
            if d.weekday() < 5:
                dias += 1
            d += timedelta(days=1)
        return dias


class LeadHistorico(db.Model):
    """Timeline de alterações do lead.

    Cada linha registra UMA mudança: o campo alterado, o valor antes/depois
    (renderizado como string p/ exibição), e quem fez quando. Eventos
    "sistema" (ex.: criação automática de cliente) usam usuario_id NULL.
    """
    __tablename__ = 'lead_historico'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer, db.ForeignKey('lead.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    campo = db.Column(db.String(60), nullable=False)  # ex.: "status", "responsavel", "sistema"
    valor_antes = db.Column(db.String(255), nullable=True)
    valor_depois = db.Column(db.String(255), nullable=True)
    descricao = db.Column(db.Text, nullable=True)  # mensagem livre extra
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


# ──────────────────────────────────────────────────────────────────────────────
# Task #43 — Webhook para n8n (notificações externas)
# ──────────────────────────────────────────────────────────────────────────────
class WebhookEntrega(db.Model):
    """Task #43 — log/fila de entregas de webhook para n8n.

    Cada linha representa uma tentativa de notificar o n8n sobre um evento
    do sistema. Quando o POST falha (timeout, conexão, 5xx), a linha fica
    em ``status='pendente'`` para o job de retry. Após 3 tentativas sem
    sucesso, vira ``status='falha'`` (falha permanente).
    """

    __tablename__ = 'webhook_entrega'

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(80), nullable=False, index=True)
    payload = db.Column(JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pendente', index=True)
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    ultimo_erro = db.Column(db.Text, nullable=True)
    proxima_tentativa_em = db.Column(db.DateTime, nullable=True, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<WebhookEntrega {self.id} {self.event} {self.status}>'


# ════════════════════════════════════════════════════════════════════════
# Task #63 — Orçamento Operacional da Obra
# ════════════════════════════════════════════════════════════════════════

class ObraOrcamentoOperacional(db.Model):
    """Orçamento operacional 1:1 da obra (cópia editável separada do contrato).

    Métricas e RDOs sempre leem daqui (pela versão vigente na data do RDO).
    Edições no Orcamento original NÃO afetam o operacional.
    """
    __tablename__ = 'obra_orcamento_operacional'
    __table_args__ = (
        db.UniqueConstraint('obra_id', name='uq_op_obra'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    orcamento_origem_id = db.Column(db.Integer, db.ForeignKey('orcamento.id', ondelete='SET NULL'),
                                    nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    obra = db.relationship('Obra', backref=db.backref('orcamento_operacional', uselist=False,
                                                       cascade='all, delete-orphan',
                                                       passive_deletes=True))
    orcamento_origem = db.relationship('Orcamento', foreign_keys=[orcamento_origem_id])
    itens = db.relationship('ObraOrcamentoOperacionalItem',
                            backref='operacional',
                            cascade='all, delete-orphan',
                            order_by='ObraOrcamentoOperacionalItem.id')


class ObraOrcamentoOperacionalItem(db.Model):
    """Item do orçamento operacional. 1..N versões temporais."""
    __tablename__ = 'obra_orcamento_operacional_item'

    id = db.Column(db.Integer, primary_key=True)
    operacional_id = db.Column(db.Integer,
                               db.ForeignKey('obra_orcamento_operacional.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    orcamento_item_origem_id = db.Column(db.Integer,
                                         db.ForeignKey('orcamento_item.id', ondelete='SET NULL'),
                                         nullable=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'), nullable=True)
    descricao = db.Column(db.String(500), nullable=False)
    unidade = db.Column(db.String(20), default='un')
    quantidade = db.Column(db.Numeric(15, 4), default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    versoes = db.relationship('ObraOrcamentoOperacionalItemVersao',
                              backref='item',
                              cascade='all, delete-orphan',
                              order_by='ObraOrcamentoOperacionalItemVersao.vigente_de.desc()')


class ObraOrcamentoOperacionalItemVersao(db.Model):
    """Versão temporal de um item operacional.

    Janela [vigente_de, vigente_ate). vigente_ate=NULL → versão atualmente ativa.
    Para modo='retroativo', a versão atual é atualizada in-place E uma cópia
    é gravada com vigente_ate=now() apenas para auditoria.
    """
    __tablename__ = 'obra_orcamento_operacional_item_versao'
    __table_args__ = (
        db.Index('idx_op_item_versao_lookup', 'item_id', 'vigente_de', 'vigente_ate'),
    )

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer,
                        db.ForeignKey('obra_orcamento_operacional_item.id', ondelete='CASCADE'),
                        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True, index=True)
    composicao_snapshot = db.Column(db.JSON, default=list)
    margem_pct = db.Column(db.Numeric(5, 2), nullable=True)
    imposto_pct = db.Column(db.Numeric(5, 2), nullable=True)
    vigente_de = db.Column(db.DateTime, nullable=False, index=True)
    vigente_ate = db.Column(db.DateTime, nullable=True, index=True)
    modo_aplicacao = db.Column(db.String(30), default='clonagem_inicial')
    motivo = db.Column(db.Text, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# Hook SQLAlchemy: auto-clona o orçamento operacional na 1ª criação de RDO
# da obra. Idempotente (garantir_operacional verifica se já existe).
from sqlalchemy import event as _sa_event


@_sa_event.listens_for(RDO, 'after_insert')
def _rdo_after_insert_autoclone_operacional(mapper, connection, target):
    """Ao inserir um RDO, agenda criação do operacional (se ainda não existir)
    para depois do commit, num after_commit listener one-shot. A sessão pode
    estar em estado 'committed' quando o callback dispara — então abrimos uma
    transação nova explicitamente."""
    obra_id = target.obra_id
    if not obra_id:
        return
    sess = db.session

    @_sa_event.listens_for(sess, 'after_commit', once=True)
    def _do_clone(_session):
        import logging as _logging
        _log = _logging.getLogger(__name__)
        # Defer com Timer para sair do callback after_commit (que mantém a
        # session em estado 'committed' e impede SQL novo). 0s = próximo tick.
        from threading import Timer
        from flask import current_app
        try:
            app_obj = current_app._get_current_object()
        except Exception:
            return
        def _run_in_app_ctx():
            try:
                with app_obj.app_context():
                    from services.orcamento_operacional import garantir_operacional
                    garantir_operacional(obra_id)
            except Exception as _e:
                _log.warning(
                    "[orcamento_operacional] auto-clone falhou obra=%s: %s",
                    obra_id, _e,
                )
        Timer(0, _run_in_app_ctx).start()


# ============================================================
# MÓDULO CUSTOS DO ESCRITÓRIO (Task #6)
# ============================================================

class CategoriaEscritorio(db.Model):
    """Categorias de custo do escritório (aluguel, água, luz, etc.)"""
    __tablename__ = 'categoria_escritorio'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cor = db.Column(db.String(7), default='#6c757d')
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    despesas = db.relationship('DespesaEscritorio', backref='categoria', lazy=True)

    __table_args__ = (
        db.Index('idx_categoria_escritorio_admin', 'admin_id'),
    )

    @classmethod
    def seed_defaults(cls, admin_id):
        """Cria as 10 categorias padrão para o tenant se ainda não existirem."""
        defaults = [
            ('Aluguel',    '#e74c3c'),
            ('Água',       '#3498db'),
            ('Luz',        '#f39c12'),
            ('Internet',   '#9b59b6'),
            ('Telefone',   '#1abc9c'),
            ('Salário PJ', '#2ecc71'),
            ('Contador',   '#34495e'),
            ('Limpeza',    '#e67e22'),
            ('Segurança',  '#c0392b'),
            ('Outros',     '#95a5a6'),
        ]
        for nome, cor in defaults:
            existe = cls.query.filter_by(admin_id=admin_id, nome=nome).first()
            if not existe:
                db.session.add(cls(nome=nome, cor=cor, ativo=True, admin_id=admin_id))
        db.session.commit()


class DespesaEscritorio(db.Model):
    """Despesas do escritório (recorrentes ou avulsas)"""
    __tablename__ = 'despesa_escritorio'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_escritorio.id'), nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    dia_vencimento = db.Column(db.Integer, nullable=False)  # 1–28
    recorrente = db.Column(db.Boolean, default=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ocorrencias = db.relationship(
        'DespesaEscritorioOcorrencia', backref='despesa', lazy=True,
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        db.Index('idx_despesa_escritorio_admin', 'admin_id'),
    )


class DespesaEscritorioOcorrencia(db.Model):
    """Ocorrência mensal ou avulsa de uma despesa do escritório"""
    __tablename__ = 'despesa_escritorio_ocorrencia'

    id = db.Column(db.Integer, primary_key=True)
    despesa_id = db.Column(db.Integer, db.ForeignKey('despesa_escritorio.id'), nullable=False)
    competencia_ano = db.Column(db.Integer, nullable=False)
    competencia_mes = db.Column(db.Integer, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    conta_pagar_id = db.Column(db.Integer, db.ForeignKey('conta_pagar.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conta_pagar = db.relationship('ContaPagar', backref='ocorrencia_escritorio', lazy=True)

    __table_args__ = (
        db.UniqueConstraint(
            'despesa_id', 'competencia_ano', 'competencia_mes',
            name='uq_despesa_ocorrencia_mes'
        ),
        db.Index('idx_despesa_ocorrencia_admin', 'admin_id'),
    )


# ============================================================
# CATÁLOGOS AUXILIARES (Task #10)
# ============================================================

class GrupoFinanceiro(db.Model):
    """Grupos financeiros para agrupamento de categorias de fluxo de caixa."""
    __tablename__ = 'grupo_financeiro'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # ENTRADA | SAIDA
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('nome', 'tipo', 'admin_id', name='uq_grupo_financeiro_nome_tipo_admin'),
        db.Index('idx_grupo_financeiro_admin', 'admin_id'),
    )

    categorias = db.relationship('CategoriaFluxoCaixa', backref='grupo_financeiro_rel',
                                 lazy='dynamic', foreign_keys='CategoriaFluxoCaixa.grupo_financeiro_id')

    def __repr__(self):
        return f'<GrupoFinanceiro {self.tipo}:{self.nome}>'


class CategoriaFluxoCaixa(db.Model):
    """Categorias de fluxo de caixa gerenciadas pelo administrador."""
    __tablename__ = 'categoria_fluxo_caixa'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default='SAIDA')  # ENTRADA | SAIDA
    grupo_financeiro = db.Column(db.String(100))
    grupo_financeiro_id = db.Column(db.Integer, db.ForeignKey('grupo_financeiro.id'), nullable=True)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_cat_fluxo_caixa_admin', 'admin_id'),
    )

    _DEFAULTS = [
        # (tipo, nome, grupo_financeiro, descricao)
        # --- ENTRADAS ---
        ('ENTRADA', 'Receita de Obras',                   'Receitas Operacionais',       'Medições e faturamento de obras'),
        ('ENTRADA', 'Receita de Serviços',                'Receitas Operacionais',       'Faturamento por prestação de serviços'),
        ('ENTRADA', 'Adiantamento de Clientes',           'Receitas Operacionais',       'Valores recebidos antecipadamente de clientes'),
        ('ENTRADA', 'Reembolso de Cliente',               'Reembolsos e Repasses',       'Ressarcimentos e reembolsos recebidos de clientes'),
        ('ENTRADA', 'Aporte de Sócios',                   'Capital e Financiamentos',    'Aporte de capital pelos sócios'),
        ('ENTRADA', 'Empréstimos Recebidos',              'Capital e Financiamentos',    'Empréstimos e financiamentos captados'),
        ('ENTRADA', 'Rendimentos Financeiros',            'Receitas Financeiras',        'Rendimentos de aplicações e contas bancárias'),
        ('ENTRADA', 'Venda de Ativos',                    'Receitas Não Operacionais',   'Receita proveniente da venda de bens e equipamentos'),
        ('ENTRADA', 'Outros Recebimentos',                'Outros',                      'Entradas diversas não categorizadas'),
        # --- SAÍDAS: Custo Direto de Obra ---
        ('SAIDA',   'Mão de Obra Direta',                 'Custo Direto de Obra',        'Diárias e mão de obra que atua diretamente na execução da obra'),
        ('SAIDA',   'Materiais de Obra',                  'Custo Direto de Obra',        'Aquisição de materiais e insumos para obras'),
        ('SAIDA',   'Subempreitada',                      'Custo Direto de Obra',        'Pagamento a subempreiteiros por serviços de obra'),
        ('SAIDA',   'Serviços Terceirizados de Obra',     'Custo Direto de Obra',        'Prestadores de serviços especializados em obra'),
        ('SAIDA',   'Locação de Equipamentos',            'Custo Direto de Obra',        'Aluguel de equipamentos e máquinas para obra'),
        ('SAIDA',   'Fretes e Entregas',                  'Custo Direto de Obra',        'Transporte e entrega de materiais para obra'),
        ('SAIDA',   'Combustível e Frota',                'Custo Direto de Obra',        'Abastecimento e manutenção de veículos da frota'),
        ('SAIDA',   'Manutenção de Frota e Equipamentos', 'Custo Direto de Obra',        'Reparos e revisões em veículos e equipamentos'),
        ('SAIDA',   'Ferramentas e Consumíveis',          'Custo Direto de Obra',        'Ferramentas, peças de desgaste e materiais consumíveis'),
        ('SAIDA',   'EPIs e Segurança do Trabalho',       'Custo Direto de Obra',        'Equipamentos de proteção individual e coletiva'),
        ('SAIDA',   'Taxas de Obra / ART / Licenças',     'Custo Direto de Obra',        'ART, licenças, alvarás e taxas legais de obra'),
        ('SAIDA',   'Transporte de Obra',                 'Custo Direto de Obra',        'Transporte de equipes e pessoal para o canteiro'),
        ('SAIDA',   'Alimentação de Obra',                'Custo Direto de Obra',        'Refeições e alimentação dos trabalhadores em obra'),
        ('SAIDA',   'Hospedagem de Obra',                 'Custo Direto de Obra',        'Hospedagem de equipes em obras fora da sede'),
        ('SAIDA',   'Outros Custos de Obra',              'Custo Direto de Obra',        'Custos diretos de obra não enquadrados nas demais categorias'),
        # --- SAÍDAS: Benefícios e Pessoal ---
        ('SAIDA',   'Salários e Encargos',                'Benefícios e Pessoal',        'Folha de pagamento, FGTS, INSS e encargos trabalhistas'),
        ('SAIDA',   'Benefício Transporte',               'Benefícios e Pessoal',        'Vale-transporte e auxílio-deslocamento'),
        ('SAIDA',   'Benefício Alimentação',              'Benefícios e Pessoal',        'Vale-refeição e vale-alimentação'),
        ('SAIDA',   'Reembolsos a Funcionários',          'Benefícios e Pessoal',        'Ressarcimento de despesas pagas pelos colaboradores'),
        # --- SAÍDAS: Sócios e Capital ---
        ('SAIDA',   'Pró-labore e Retirada de Sócios',   'Sócios e Capital',            'Remuneração e retiradas dos sócios'),
        # --- SAÍDAS: Despesas Administrativas ---
        ('SAIDA',   'Aluguel e Locação Administrativa',   'Despesas Administrativas',    'Aluguel de imóvel e locação de espaços administrativos'),
        ('SAIDA',   'Água',                               'Despesas Administrativas',    'Consumo de água e saneamento'),
        ('SAIDA',   'Luz / Energia Elétrica',             'Despesas Administrativas',    'Conta de energia elétrica'),
        ('SAIDA',   'Internet',                           'Despesas Administrativas',    'Planos de internet fixa e corporativa'),
        ('SAIDA',   'Telefone',                           'Despesas Administrativas',    'Planos de telefonia fixa e móvel'),
        ('SAIDA',   'Contabilidade e Jurídico',           'Despesas Administrativas',    'Honorários contábeis, advocatícios e assessoria jurídica'),
        ('SAIDA',   'Sistemas e Assinaturas',             'Despesas Administrativas',    'Softwares, licenças e assinaturas de ferramentas digitais'),
        ('SAIDA',   'Material de Escritório',             'Despesas Administrativas',    'Suprimentos e materiais de uso administrativo'),
        ('SAIDA',   'Manutenção Predial e Escritório',    'Despesas Administrativas',    'Reparos e conservação do imóvel e espaço de trabalho'),
        ('SAIDA',   'Treinamentos e Capacitações',        'Despesas Administrativas',    'Cursos, treinamentos e desenvolvimento de equipe'),
        # --- SAÍDAS: Despesas Comerciais ---
        ('SAIDA',   'Marketing e Vendas',                 'Despesas Comerciais',         'Publicidade, marketing digital e ações comerciais'),
        # --- SAÍDAS: Despesas Financeiras ---
        ('SAIDA',   'Despesas Bancárias',                 'Despesas Financeiras',        'Tarifas, IOF e custos bancários'),
        ('SAIDA',   'Despesa Financeira',                 'Despesas Financeiras',        'Juros, multas e encargos financeiros'),
        # --- SAÍDAS: Capital e Financiamentos ---
        ('SAIDA',   'Empréstimos e Financiamentos',       'Capital e Financiamentos',    'Amortização e pagamento de parcelas de empréstimos'),
        # --- SAÍDAS: Tributos ---
        ('SAIDA',   'Impostos e Taxas',                   'Tributos',                    'DAS, ISS, tributos municipais, estaduais e federais'),
        # --- SAÍDAS: Outros ---
        ('SAIDA',   'Outras Saídas',                      'Outros',                      'Saídas diversas não categorizadas'),
    ]

    @classmethod
    def seed_defaults(cls, admin_id: int) -> None:
        """Insere categorias padrão para o tenant se ainda não tiver nenhuma."""
        existing = db.session.execute(
            db.text('SELECT COUNT(*) FROM categoria_fluxo_caixa WHERE admin_id = :aid'),
            {'aid': admin_id}
        ).scalar() or 0
        if existing:
            return
        for tipo, nome, grupo_financeiro, descricao in cls._DEFAULTS:
            db.session.execute(db.text("""
                INSERT INTO categoria_fluxo_caixa (nome, tipo, grupo_financeiro, descricao, ativo, admin_id)
                VALUES (:nome, :tipo, :grupo, :desc, true, :aid)
            """), {'nome': nome, 'tipo': tipo, 'grupo': grupo_financeiro, 'desc': descricao, 'aid': admin_id})
        db.session.flush()


class PalavraChaveCategoria(db.Model):
    """Regra de Classificação: associação por tenant entre um Gatilho (palavras) e
    uma Categoria de destino, com Prioridade e condições. Ensina o sistema a
    categorizar Lançamentos da importação de Fluxo de Caixa automaticamente.
    Ver CONTEXT.md (seção Importação / Classificação) e ADR-0002."""
    __tablename__ = 'palavra_chave_categoria'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    categoria_fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=False)
    # Gatilho: uma ou mais palavras separadas por vírgula (semântica "qualquer uma")
    palavras = db.Column(db.Text, nullable=False)
    # Onde buscar: qualquer | descricao | fornecedor | plano (aceita múltiplos por vírgula)
    campo_alvo = db.Column(db.String(40), nullable=False, default='qualquer')
    # Exceções: palavras que, se presentes, anulam a regra (OU)
    excecoes = db.Column(db.Text, nullable=True)
    # Condição extra (AND): gatilho que também precisa aparecer em campo_extra
    gatilho_extra = db.Column(db.Text, nullable=True)
    campo_extra = db.Column(db.String(40), nullable=False, default='qualquer')
    # Condição de obra: indiferente | com_obra | sem_obra
    condicao_obra = db.Column(db.String(20), nullable=False, default='indiferente')
    # Prioridade: menor decide primeiro (mais específica)
    prioridade = db.Column(db.Integer, nullable=False, default=50)
    tipo = db.Column(db.String(10), nullable=False, default='SAIDA')  # ENTRADA | SAIDA
    origem = db.Column(db.String(10), nullable=False, default='usuario')  # sistema | usuario
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_pck_admin_ativo_tipo_prio', 'admin_id', 'ativo', 'tipo', 'prioridade'),
    )


class PalavraChaveSugestao(db.Model):
    """Sugestão: termo recorrente entre os Pendentes de Classificação de uma
    importação, agregado por impacto, que o usuário pode transformar em Regra.
    Refeita a cada importação para o tenant. Ver CONTEXT.md."""
    __tablename__ = 'palavra_chave_sugestao'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    termo = db.Column(db.String(120), nullable=False)
    ocorrencias = db.Column(db.Integer, nullable=False, default=0)
    soma_valor = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    exemplo = db.Column(db.String(300))
    tipo = db.Column(db.String(10), nullable=False, default='SAIDA')  # ENTRADA | SAIDA
    dismissed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_pcs_admin_tipo', 'admin_id', 'tipo'),
    )


class CorrecaoClassificacao(db.Model):
    """Correção + Memória Exata: decisão de categoria que o usuário fez em um
    Lançamento individual (no drill-down de um Termo). Reaplicada automaticamente
    quando um Lançamento de texto idêntico reaparece. Chaveada por
    (admin_id, texto_norm). Ver CONTEXT.md (Correção, Memória Exata) e spec §4."""
    __tablename__ = 'correcao_classificacao'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    # descrição+fornecedor normalizados — chave da Memória Exata
    texto_norm = db.Column(db.String(500), nullable=False)
    categoria_fluxo_caixa_id = db.Column(
        db.Integer, db.ForeignKey('categoria_fluxo_caixa.id'), nullable=False)
    termo_origem = db.Column(db.String(120), nullable=True)
    tipo = db.Column(db.String(10), nullable=False, default='SAIDA')  # ENTRADA | SAIDA
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('uq_correcao_admin_texto', 'admin_id', 'texto_norm', unique=True),
    )


class CategoriaFornecedor(db.Model):
    """Categorias de fornecedor (M2M com Fornecedor)."""
    __tablename__ = 'categoria_fornecedor'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_cat_fornecedor_admin', 'admin_id'),
    )

    # Lista completa especializada em construção civil (Task #58)
    _DEFAULTS = [
        # Material de Construção Geral
        'Material de Construção Geral',
        'Areia, Pedra e Agregados',
        'Cimento, Argamassa e Rejunte',
        'Blocos, Tijolos e Alvenaria',
        'Concreto Usinado',
        'Ferragens para Construção',
        'Aço, Vergalhão e Malha Pop',
        'Madeiras e Compensados',
        'Telhas e Coberturas',
        'Calhas e Rufos',
        'Impermeabilizantes',
        'Mantas e Produtos de Vedação',
        # Acabamentos
        'Acabamentos',
        'Pisos e Revestimentos',
        'Porcelanato e Cerâmica',
        'Pedras, Granitos e Mármores',
        'Rodapés e Soleiras',
        'Tintas e Texturas',
        'Gesso e Drywall',
        'Forros e Divisórias',
        'Portas e Janelas',
        'Vidros e Esquadrias',
        'Louças e Metais',
        'Bancadas e Cubas',
        # Materiais Elétricos
        'Material Elétrico',
        'Fios e Cabos',
        'Disjuntores e Quadros Elétricos',
        'Tomadas, Interruptores e Placas',
        'Iluminação e Luminárias',
        'Postes, Eletrodutos e Canaletas',
        'Materiais de Aterramento',
        'Automação e Segurança Eletrônica',
        # Materiais Hidráulicos
        'Material Hidráulico',
        'Tubos e Conexões',
        'Registros e Válvulas',
        "Caixas d'água e Reservatórios",
        'Bombas e Pressurizadores',
        'Esgoto e Drenagem',
        'Ralos, Grelhas e Caixas de Inspeção',
        'Aquecedores e Sistemas de Água Quente',
        # Estrutura Metálica e Serralheria
        'Perfis Metálicos',
        'Chapas e Bobinas',
        'Parafusos, Porcas e Arruelas',
        'Solda, Eletrodos e Consumíveis',
        'Telas, Gradis e Alambrados',
        'Portões e Estruturas Metálicas',
        'Galvanização e Tratamento Superficial',
        # Apoio de Obra
        'EPIs',
        'Ferramentas Manuais',
        'Ferramentas Elétricas',
        'Máquinas e Equipamentos',
        'Material de Limpeza de Obra',
        'Material de Sinalização',
        'Lonas, Plásticos e Proteções',
        'Andaimes, Escoras e Formas',
        'Fixadores, Buchas e Chumbadores',
        'Colas, Selantes e Silicones',
        # Administrativo / Escritório
        'Contabilidade',
        'Jurídico',
        'Marketing e Publicidade',
        'Tecnologia / Sistemas',
        'Telefonia e Internet',
        'Energia Elétrica',
        'Água e Saneamento',
        'Aluguel',
        'Material de Escritório',
        'Limpeza e Conservação',
        'Alimentação / Refeitório',
        'Combustível',
        'Bancos e Tarifas',
        'Seguros',
        'Impostos e Taxas',
    ]

    @classmethod
    def seed_defaults(cls, admin_id: int) -> None:
        """Insere categorias padrão para o tenant, usando get-or-create por nome.
        Admins que já têm categorias recebem apenas as que ainda não existem.
        """
        existing_names = set(
            row[0] for row in db.session.execute(
                db.text('SELECT nome FROM categoria_fornecedor WHERE admin_id = :aid'),
                {'aid': admin_id}
            ).fetchall()
        )
        inserted = 0
        for nome in cls._DEFAULTS:
            if nome not in existing_names:
                db.session.execute(db.text("""
                    INSERT INTO categoria_fornecedor (nome, ativo, admin_id)
                    VALUES (:nome, true, :aid)
                """), {'nome': nome, 'aid': admin_id})
                inserted += 1
        if inserted:
            db.session.flush()


# ================================
# Task #11 — Calendário de Pagamentos
# ================================

class DiaPagamentoConfig(db.Model):
    """Dias do mês configurados para fechamento de pagamentos (ex: dia 5, dia 20)."""
    __tablename__ = 'dia_pagamento_config'

    id = db.Column(db.Integer, primary_key=True)
    dia_do_mes = db.Column(db.Integer, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('dia_do_mes', 'admin_id', name='uq_dia_pagamento_admin'),
        db.Index('idx_dia_pagamento_admin', 'admin_id'),
    )

    def __repr__(self):
        return f'<DiaPagamentoConfig dia={self.dia_do_mes}>'


class FechamentoPagamento(db.Model):
    """Registro de um fechamento de pagamentos (batch de contas a pagar)."""
    __tablename__ = 'fechamento_pagamento'

    id = db.Column(db.Integer, primary_key=True)
    data_fechamento = db.Column(db.Date, nullable=False)
    descricao = db.Column(db.String(200))
    status = db.Column(db.String(20), default='ABERTO')
    total_selecionado = db.Column(db.Numeric(15, 2), default=0)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contas = db.relationship('ContaPagar', foreign_keys='ContaPagar.fechamento_id',
                             backref='fechamento', lazy='dynamic')
    gestao_custos = db.relationship('GestaoCustoPai', foreign_keys='GestaoCustoPai.fechamento_id',
                                    backref='fechamento', lazy='dynamic')

    __table_args__ = (
        db.Index('idx_fechamento_admin', 'admin_id'),
    )

    def __repr__(self):
        return f'<FechamentoPagamento {self.data_fechamento} {self.status}>'


class DropdownGrupo(db.Model):
    """Motor universal de dropdowns — grupo / lista mestra genérica."""
    __tablename__ = 'dropdown_grupo'
    __table_args__ = (
        db.UniqueConstraint('slug', 'admin_id', name='uq_dropdown_grupo_slug_admin'),
        db.Index('ix_dropdown_grupo_admin', 'admin_id'),
    )

    id         = db.Column(db.Integer, primary_key=True)
    admin_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    slug       = db.Column(db.String(80), nullable=False)
    label      = db.Column(db.String(120), nullable=False)
    modulo     = db.Column(db.String(40), nullable=False, default='geral')
    descricao  = db.Column(db.Text, nullable=True)
    editavel   = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    opcoes = db.relationship(
        'DropdownOpcao', backref='grupo', lazy='dynamic',
        order_by='DropdownOpcao.ordem.asc()',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<DropdownGrupo {self.slug}>'


class DropdownOpcao(db.Model):
    """Motor universal de dropdowns — opção de um grupo."""
    __tablename__ = 'dropdown_opcao'
    __table_args__ = (
        db.UniqueConstraint('grupo_id', 'valor', 'admin_id',
                            name='uq_dropdown_opcao_grupo_valor_admin'),
        db.Index('ix_dropdown_opcao_grupo', 'grupo_id'),
        db.Index('ix_dropdown_opcao_admin', 'admin_id'),
    )

    id         = db.Column(db.Integer, primary_key=True)
    admin_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    grupo_id   = db.Column(db.Integer, db.ForeignKey('dropdown_grupo.id', ondelete='CASCADE'), nullable=False)
    valor      = db.Column(db.String(200), nullable=False)
    ordem      = db.Column(db.Integer, default=0, nullable=False)
    cor        = db.Column(db.String(7), nullable=True)
    ativo      = db.Column(db.Boolean, default=True, nullable=False)
    protegido  = db.Column(db.Boolean, default=False, nullable=False)
    ext_id     = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def nome(self):
        return self.valor

    def __repr__(self):
        return f'<DropdownOpcao {self.grupo_id}:{self.valor}>'


class CategoriaReembolso(db.Model):
    """Categorias de reembolso a funcionários."""
    __tablename__ = 'categoria_reembolso'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_cat_reembolso_admin', 'admin_id'),
    )

    _DEFAULTS = [
        ('Alimentação',         'Refeições e lanches em viagem ou serviço externo'),
        ('Transporte Público',  'Ônibus, metrô, taxi e aplicativos de transporte'),
        ('Combustível',         'Abastecimento de veículo próprio a serviço'),
        ('Hospedagem',          'Hotel ou pousada em deslocamentos a trabalho'),
        ('Estacionamento',      'Estacionamentos pagos durante atividade profissional'),
        ('Material de Trabalho','Compra de insumos ou ferramentas necessários à atividade'),
        ('Pedágio',             'Tarifas de pedágio em deslocamentos a serviço'),
        ('Outros',              'Despesas diversas não cobertas pelas demais categorias'),
    ]

    @classmethod
    def seed_defaults(cls, admin_id: int) -> None:
        """Insere categorias padrão para o tenant se ainda não tiver nenhuma."""
        existing = db.session.execute(
            db.text('SELECT COUNT(*) FROM categoria_reembolso WHERE admin_id = :aid'),
            {'aid': admin_id}
        ).scalar() or 0
        if existing:
            return
        for nome, descricao in cls._DEFAULTS:
            db.session.execute(db.text("""
                INSERT INTO categoria_reembolso (nome, descricao, ativo, admin_id)
                VALUES (:nome, :desc, true, :aid)
            """), {'nome': nome, 'desc': descricao, 'aid': admin_id})
        db.session.flush()
