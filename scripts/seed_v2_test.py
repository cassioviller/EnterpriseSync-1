"""
Script de seed para dados de teste V2 - admin_id=63
Cria: 5 funcionários diaristas, 2 obras, cronogramas, RDOs (1-10/mar),
diárias, transporte, alimentação, materiais e valida gestão de custo + fluxo de caixa.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_APP', 'main')

from app import app, db
from datetime import date, timedelta
from decimal import Decimal
import random

ADMIN_ID = 63
USUARIO_ID = 63  # admin.v2@sige.com

def log(msg): print(f"  [OK] {msg}")
def section(msg): print(f"\n{'='*50}\n{msg}\n{'='*50}")

with app.app_context():

    # ─────────────────────────────────────────────────────
    # IMPORTS DE MODELOS
    # ─────────────────────────────────────────────────────
    from models import (
        db, Funcionario, Funcao, Departamento, Obra, TarefaCronograma,
        CalendarioEmpresa, RDO, RDOMaoObra, RDOApontamentoCronograma,
        GestaoCustoPai, GestaoCustoFilho, FluxoCaixa,
        LancamentoTransporte, CategoriaTransporte,
        AlimentacaoLancamento, AlimentacaoItem, Restaurante,
        AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
        CustoObra, Fornecedor
    )
    from sqlalchemy import text

    # ─────────────────────────────────────────────────────
    # 1. FUNCAO E DEPARTAMENTO BASE
    # ─────────────────────────────────────────────────────
    section("1. FUNÇÕES E DEPARTAMENTOS")

    dept = Departamento.query.filter_by(admin_id=ADMIN_ID).first()
    if not dept:
        dept = Departamento(nome='Obras', admin_id=ADMIN_ID)
        db.session.add(dept)
        db.session.flush()
        log(f"Departamento criado: {dept.nome}")
    else:
        log(f"Departamento existente: {dept.nome}")

    funcao = Funcao.query.filter_by(admin_id=ADMIN_ID).first()
    if not funcao:
        funcao = Funcao(nome='Pedreiro', descricao='Pedreiro de obras', admin_id=ADMIN_ID)
        db.session.add(funcao)
        db.session.flush()
        log(f"Função criada: {funcao.nome}")
    else:
        log(f"Função existente: {funcao.nome}")

    db.session.commit()

    # ─────────────────────────────────────────────────────
    # 2. FUNCIONÁRIOS DIARISTAS (5 total)
    # ─────────────────────────────────────────────────────
    section("2. FUNCIONÁRIOS DIARISTAS")

    # Atualizar existentes para diaristas
    funcs_existentes = Funcionario.query.filter_by(admin_id=ADMIN_ID, ativo=True).all()
    diarias_config = {
        'Ana Silva V2': 200.0,
        'Carlos Souza V2': 220.0,
        'Maria Oliveira V2': 180.0,
    }
    for f in funcs_existentes:
        if f.nome in diarias_config:
            f.tipo_remuneracao = 'diaria'
            f.valor_diaria = diarias_config[f.nome]
            f.departamento_id = dept.id
            f.funcao_id = funcao.id
            log(f"Atualizado: {f.nome} → diarista R${f.valor_diaria}/dia")

    db.session.commit()

    # Criar 2 novos funcionários
    novos_nomes = [
        ('Pedro Costa V2', 'pedro.costa.v2@empresa.com', 230.0),
        ('Joana Lima V2', 'joana.lima.v2@empresa.com', 190.0),
    ]
    funcionarios_ids = [f.id for f in funcs_existentes]
    for nome, email, diaria in novos_nomes:
        existente = Funcionario.query.filter_by(email=email, admin_id=ADMIN_ID).first()
        if not existente:
            f = Funcionario(
                nome=nome,
                email=email,
                cpf=f"{''.join([str(random.randint(0,9)) for _ in range(11)])}",
                salario=0.0,
                data_admissao=date(2026, 3, 1),
                tipo_remuneracao='diaria',
                valor_diaria=diaria,
                ativo=True,
                admin_id=ADMIN_ID,
                departamento_id=dept.id,
                funcao_id=funcao.id,
            )
            db.session.add(f)
            db.session.flush()
            funcionarios_ids.append(f.id)
            log(f"Criado: {nome} → diarista R${diaria}/dia (id={f.id})")
        else:
            existente.tipo_remuneracao = 'diaria'
            existente.valor_diaria = diaria
            funcionarios_ids.append(existente.id)
            log(f"Existente: {nome}")

    db.session.commit()

    # Buscar todos os 5 funcionários V2
    todos_funcs = Funcionario.query.filter_by(admin_id=ADMIN_ID, ativo=True).all()
    log(f"Total funcionários V2: {len(todos_funcs)}")

    # ─────────────────────────────────────────────────────
    # 3. 2 OBRAS COM CRONOGRAMA 01/03 - 31/03/2026
    # ─────────────────────────────────────────────────────
    section("3. OBRAS")

    obras_data = [
        ('Obra Residencial V2', 'R001'),
        ('Obra Comercial V2',   'C001'),
    ]
    obras_criadas = []
    for nome_obra, codigo in obras_data:
        o = Obra.query.filter_by(nome=nome_obra, admin_id=ADMIN_ID).first()
        if not o:
            o = Obra(
                nome=nome_obra,
                codigo=codigo,
                status='em_andamento',
                ativo=True,
                data_inicio=date(2026, 3, 1),
                admin_id=ADMIN_ID,
            )
            db.session.add(o)
            db.session.flush()
            log(f"Obra criada: {nome_obra} (id={o.id})")
        else:
            log(f"Obra existente: {nome_obra} (id={o.id})")
        obras_criadas.append(o)

    db.session.commit()

    # ─────────────────────────────────────────────────────
    # 4. CRONOGRAMA PARA CADA OBRA (tarefas mar/2026)
    # ─────────────────────────────────────────────────────
    section("4. CRONOGRAMA V2")

    cal = CalendarioEmpresa.query.filter_by(admin_id=ADMIN_ID).first()
    if not cal:
        cal = CalendarioEmpresa(
            admin_id=ADMIN_ID,
            considerar_sabado=True,
            considerar_domingo=False,
        )
        db.session.add(cal)
        db.session.flush()
        log(f"CalendarioEmpresa criado")

    tarefas_template = [
        ('Fundação',             date(2026,3,1),  date(2026,3,12), 8,  500.0, 'm³'),
        ('Alvenaria',            date(2026,3,6),  date(2026,3,19), 10, 1200.0,'m²'),
        ('Instalação Elétrica',  date(2026,3,13), date(2026,3,25), 9,  800.0, 'm'),
        ('Reboco Final',         date(2026,3,18), date(2026,3,31), 10, 900.0, 'm²'),
    ]

    for obra in obras_criadas:
        existentes = TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=ADMIN_ID).count()
        if existentes >= 4:
            log(f"Tarefas já existem para {obra.nome}")
            continue
        for i, (nome_t, di, df, dur, qtd, un) in enumerate(tarefas_template):
            t = TarefaCronograma(
                obra_id=obra.id,
                nome_tarefa=nome_t,
                data_inicio=di,
                data_fim=df,
                duracao_dias=dur,
                quantidade_total=qtd,
                unidade_medida=un,
                percentual_concluido=0.0,
                ordem=i+1,
                admin_id=ADMIN_ID,
            )
            db.session.add(t)
        db.session.flush()
        log(f"4 tarefas criadas para: {obra.nome}")

    db.session.commit()

    # ─────────────────────────────────────────────────────
    # 5. RDOs 01/03 a 10/03/2026 POR OBRA
    # ─────────────────────────────────────────────────────
    section("5. RDOs (01/03 - 10/03/2026)")

    dias_rdo = [date(2026, 3, d) for d in range(1, 11)]
    tempos = ['Bom', 'Nublado', 'Ensolarado', 'Bom', 'Bom', 'Chuvoso', 'Bom', 'Nublado', 'Bom', 'Ensolarado']
    rdos_criados = {}  # (obra_id, data) → rdo

    for obra in obras_criadas:
        tarefas_obra = TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=ADMIN_ID).order_by(TarefaCronograma.ordem).all()
        rdos_criados[obra.id] = {}

        for idx, dia in enumerate(dias_rdo):
            existente = RDO.query.filter_by(obra_id=obra.id, data_relatorio=dia, admin_id=ADMIN_ID).first()
            if existente:
                rdos_criados[obra.id][dia] = existente
                continue

            num = f"RDO-{ADMIN_ID}-2026-{obra.id:04d}{idx+1:02d}"
            rdo = RDO(
                numero_rdo=num,
                obra_id=obra.id,
                criado_por_id=USUARIO_ID,
                data_relatorio=dia,
                local='Campo',
                status='Finalizado',
                clima_geral=tempos[idx],
                condicoes_trabalho='Normais',
                observacoes_climaticas='Condições normais de trabalho.',
                comentario_geral=f'RDO {dia.strftime("%d/%m/%Y")} - {obra.nome}',
                admin_id=ADMIN_ID,
            )
            db.session.add(rdo)
            db.session.flush()

            # Mão de obra — todos os 5 funcionários
            for func in todos_funcs:
                mo = RDOMaoObra(
                    rdo_id=rdo.id,
                    funcionario_id=func.id,
                    funcao_exercida=funcao.nome,
                    horas_trabalhadas=8.0,
                    admin_id=ADMIN_ID,
                )
                db.session.add(mo)

            # Apontamentos do cronograma (tarefas ativas nesse dia)
            for tarefa in tarefas_obra:
                if tarefa.data_inicio and tarefa.data_inicio <= dia:
                    qty_dia = round(tarefa.quantidade_total * 0.07, 2)  # ~7% por dia
                    ap = RDOApontamentoCronograma(
                        rdo_id=rdo.id,
                        tarefa_cronograma_id=tarefa.id,
                        quantidade_executada_dia=qty_dia,
                        quantidade_acumulada=qty_dia * (idx + 1),
                        percentual_realizado=min(100.0, round(qty_dia * (idx+1) / tarefa.quantidade_total * 100, 2)),
                        percentual_planejado=min(100.0, round((idx+1) / tarefa.duracao_dias * 100, 2)),
                        admin_id=ADMIN_ID,
                    )
                    db.session.add(ap)

            rdos_criados[obra.id][dia] = rdo
            db.session.flush()

        log(f"10 RDOs criados/encontrados para: {obra.nome}")

    db.session.commit()
    log("RDOs commitados")

    # ─────────────────────────────────────────────────────
    # 6. DIÁRIAS — GestaoCustoPai por funcionário por dia
    # ─────────────────────────────────────────────────────
    section("6. LANÇAMENTOS DE DIÁRIA (GestaoCusto SALARIO)")

    for dia in dias_rdo:
        for func in todos_funcs:
            valor_dia = getattr(func, 'valor_diaria', 0) or 200.0
            # Verificar se já existe para este func/dia
            existe = GestaoCustoPai.query.filter_by(
                admin_id=ADMIN_ID, entidade_id=func.id, tipo_categoria='MAO_OBRA_DIRETA'
            ).filter(GestaoCustoPai.data_criacao != None).first()
            # Filtro melhor: verificar por data nos filhos
            existe_filho = GestaoCustoFilho.query.filter_by(
                admin_id=ADMIN_ID, data_referencia=dia,
                descricao=f'Diária - {func.nome}'
            ).first()
            if existe_filho:
                continue

            # Dias 1-5 = PAGO, dias 6-10 = SOLICITADO
            status = 'PAGO' if dia.day <= 5 else 'SOLICITADO'
            dt_pag = dia if status == 'PAGO' else None

            pai = GestaoCustoPai(
                tipo_categoria='MAO_OBRA_DIRETA',
                entidade_nome=func.nome,
                entidade_id=func.id,
                valor_total=valor_dia,
                valor_solicitado=valor_dia,
                status=status,
                data_pagamento=dt_pag,
                observacoes=f'Diária {dia.strftime("%d/%m/%Y")} - {func.nome}',
                admin_id=ADMIN_ID,
            )
            db.session.add(pai)
            db.session.flush()

            filho = GestaoCustoFilho(
                pai_id=pai.id,
                data_referencia=dia,
                descricao=f'Diária - {func.nome}',
                valor=valor_dia,
                obra_id=obras_criadas[0].id,
                origem_tabela='diaria_manual',
                origem_id=func.id,
                admin_id=ADMIN_ID,
            )
            db.session.add(filho)

            # FluxoCaixa para PAGO
            if status == 'PAGO':
                fc = FluxoCaixa(
                    admin_id=ADMIN_ID,
                    data_movimento=dia,
                    tipo_movimento='SAIDA',
                    categoria='MAO_OBRA_DIRETA',
                    valor=valor_dia,
                    descricao=f'Diária paga - {func.nome} ({dia.strftime("%d/%m")})',
                    obra_id=obras_criadas[0].id,
                    referencia_id=pai.id,
                    referencia_tabela='gestao_custo_pai',
                )
                db.session.add(fc)

    db.session.commit()
    total_diarias = GestaoCustoPai.query.filter_by(admin_id=ADMIN_ID, tipo_categoria='MAO_OBRA_DIRETA').count()
    log(f"Diárias criadas: {total_diarias} registros")

    # ─────────────────────────────────────────────────────
    # 7. TRANSPORTE
    # ─────────────────────────────────────────────────────
    section("7. TRANSPORTE")

    cat_vt = CategoriaTransporte.query.filter_by(admin_id=ADMIN_ID, nome='Vale Transporte').first()
    if not cat_vt:
        cat_vt = CategoriaTransporte.query.filter(CategoriaTransporte.admin_id.in_([ADMIN_ID, None])).first()

    for dia in dias_rdo:
        for func in todos_funcs:
            existe = LancamentoTransporte.query.filter_by(
                admin_id=ADMIN_ID, funcionario_id=func.id, data_lancamento=dia
            ).first()
            if existe:
                continue

            valor_tp = round(random.uniform(8.0, 15.0), 2)
            status = 'PAGO' if dia.day <= 5 else 'SOLICITADO'
            dt_pag = dia if status == 'PAGO' else None

            lt = LancamentoTransporte(
                categoria_id=cat_vt.id if cat_vt else 1,
                funcionario_id=func.id,
                obra_id=obras_criadas[0].id,
                data_lancamento=dia,
                valor=valor_tp,
                descricao=f'Vale transporte {dia.strftime("%d/%m/%Y")} - {func.nome}',
                admin_id=ADMIN_ID,
            )
            db.session.add(lt)
            db.session.flush()

            # GestaoCusto para transporte
            pai_t = GestaoCustoPai(
                tipo_categoria='TRANSPORTE',
                entidade_nome=func.nome,
                entidade_id=func.id,
                valor_total=valor_tp,
                valor_solicitado=valor_tp,
                status=status,
                data_pagamento=dt_pag,
                observacoes=f'Transporte {dia.strftime("%d/%m/%Y")} - {func.nome}',
                admin_id=ADMIN_ID,
            )
            db.session.add(pai_t)
            db.session.flush()

            filho_t = GestaoCustoFilho(
                pai_id=pai_t.id,
                data_referencia=dia,
                descricao=f'Vale transporte - {func.nome}',
                valor=valor_tp,
                obra_id=obras_criadas[0].id,
                origem_tabela='lancamento_transporte',
                origem_id=lt.id,
                admin_id=ADMIN_ID,
            )
            db.session.add(filho_t)

            if status == 'PAGO':
                fc_t = FluxoCaixa(
                    admin_id=ADMIN_ID,
                    data_movimento=dia,
                    tipo_movimento='SAIDA',
                    categoria='TRANSPORTE',
                    valor=valor_tp,
                    descricao=f'Transporte pago - {func.nome} ({dia.strftime("%d/%m")})',
                    obra_id=obras_criadas[0].id,
                    referencia_id=pai_t.id,
                    referencia_tabela='gestao_custo_pai',
                )
                db.session.add(fc_t)

    db.session.commit()
    total_transp = LancamentoTransporte.query.filter_by(admin_id=ADMIN_ID).count()
    log(f"Lançamentos de transporte: {total_transp}")

    # ─────────────────────────────────────────────────────
    # 8. ALIMENTAÇÃO
    # ─────────────────────────────────────────────────────
    section("8. ALIMENTAÇÃO")

    restaurantes = Restaurante.query.filter_by(admin_id=ADMIN_ID).all()
    if not restaurantes:
        r = Restaurante(nome='Cantina da Obra', admin_id=ADMIN_ID)
        db.session.add(r)
        db.session.flush()
        restaurantes = [r]

    for idx, dia in enumerate(dias_rdo):
        for obra in obras_criadas:
            existe = AlimentacaoLancamento.query.filter_by(
                admin_id=ADMIN_ID, obra_id=obra.id, data=dia
            ).first()
            if existe:
                continue

            rest = restaurantes[idx % len(restaurantes)]
            n_pessoas = len(todos_funcs)
            vr_pp = round(random.uniform(18.0, 32.0), 2)
            total_al = round(vr_pp * n_pessoas, 2)

            al = AlimentacaoLancamento(
                data=dia,
                valor_total=total_al,
                descricao=f'Refeição {dia.strftime("%d/%m/%Y")} - {obra.nome} ({n_pessoas} pessoas)',
                restaurante_id=rest.id,
                obra_id=obra.id,
                admin_id=ADMIN_ID,
            )
            db.session.add(al)
            db.session.flush()

            status_al = 'PAGO' if dia.day <= 5 else 'SOLICITADO'
            dt_pag_al = dia if status_al == 'PAGO' else None

            pai_al = GestaoCustoPai(
                tipo_categoria='ALIMENTACAO',
                entidade_nome=rest.nome,
                entidade_id=rest.id,
                valor_total=total_al,
                valor_solicitado=total_al,
                status=status_al,
                data_pagamento=dt_pag_al,
                observacoes=f'Alimentação {dia.strftime("%d/%m/%Y")} - {obra.nome}',
                admin_id=ADMIN_ID,
            )
            db.session.add(pai_al)
            db.session.flush()

            filho_al = GestaoCustoFilho(
                pai_id=pai_al.id,
                data_referencia=dia,
                descricao=f'Refeição - {rest.nome}',
                valor=total_al,
                obra_id=obra.id,
                origem_tabela='lancamento_alimentacao',
                origem_id=al.id,
                admin_id=ADMIN_ID,
            )
            db.session.add(filho_al)

            if status_al == 'PAGO':
                fc_al = FluxoCaixa(
                    admin_id=ADMIN_ID,
                    data_movimento=dia,
                    tipo_movimento='SAIDA',
                    categoria='ALIMENTACAO',
                    valor=total_al,
                    descricao=f'Alimentação paga - {obra.nome} ({dia.strftime("%d/%m")})',
                    obra_id=obra.id,
                    referencia_id=pai_al.id,
                    referencia_tabela='gestao_custo_pai',
                )
                db.session.add(fc_al)

    db.session.commit()
    total_alim = AlimentacaoLancamento.query.filter_by(admin_id=ADMIN_ID).count()
    log(f"Lançamentos de alimentação: {total_alim}")

    # ─────────────────────────────────────────────────────
    # 9. MATERIAIS (Almoxarifado)
    # ─────────────────────────────────────────────────────
    section("9. MATERIAIS (ALMOXARIFADO)")

    from models import AlmoxarifadoCategoria

    # Categorias
    cats_data = [
        ('Materiais de Construção', 'quantidade', False),
        ('Ferramentas',             'individual',  True),
        ('EPI',                     'quantidade', False),
    ]
    cats_map = {}
    for nome_c, tipo_c, devolucao in cats_data:
        cat = AlmoxarifadoCategoria.query.filter_by(nome=nome_c, admin_id=ADMIN_ID).first()
        if not cat:
            cat = AlmoxarifadoCategoria(
                nome=nome_c,
                tipo_controle_padrao=tipo_c,
                permite_devolucao_padrao=devolucao,
                admin_id=ADMIN_ID,
            )
            db.session.add(cat)
            db.session.flush()
            log(f"Categoria criada: {nome_c}")
        cats_map[nome_c] = cat

    db.session.commit()

    # Itens
    itens_data = [
        ('Cimento',      'CIMENTO-50KG', 'Materiais de Construção', 'quantidade', False, 'sc',  45.0),
        ('Areia Grossa', 'AREIA-GRO',    'Materiais de Construção', 'quantidade', False, 'm³',  120.0),
        ('Brita 1',      'BRITA-1',      'Materiais de Construção', 'quantidade', False, 'm³',  110.0),
        ('Tijolo Furado','TIJOLO-F',     'Materiais de Construção', 'quantidade', False, 'mil', 380.0),
        ('Vergalhão 10mm','VERG-10',     'Materiais de Construção', 'quantidade', False, 'kg',  8.5),
        ('Capacete Seg.','CAP-SEG',      'EPI',                     'individual',  True, 'un',  35.0),
        ('Luvas Raspa',  'LUV-RASPA',   'EPI',                     'quantidade', False, 'par', 12.0),
        ('Martelo 500g', 'MART-500',    'Ferramentas',             'individual',  True, 'un',  85.0),
        ('Nível 60cm',   'NIV-60',      'Ferramentas',             'individual',  True, 'un',  48.0),
    ]

    itens_map = {}
    for nome_i, cod, cat_nome, tipo_ctrl, devolucao, un, vr_un in itens_data:
        item = AlmoxarifadoItem.query.filter_by(codigo=cod, admin_id=ADMIN_ID).first()
        if not item:
            item = AlmoxarifadoItem(
                codigo=cod,
                nome=nome_i,
                categoria_id=cats_map[cat_nome].id,
                tipo_controle=tipo_ctrl,
                permite_devolucao=devolucao,
                estoque_minimo=5.0 if tipo_ctrl == 'quantidade' else 1.0,
                unidade=un,
                admin_id=ADMIN_ID,
            )
            db.session.add(item)
            db.session.flush()
            log(f"Item criado: {nome_i} ({un})")
        itens_map[nome_i] = (item, vr_un)

    db.session.commit()

    # Fornecedor para materiais
    forn = Fornecedor.query.filter_by(admin_id=ADMIN_ID).first()

    # Entradas de material (do fornecedor para o almoxarifado)
    entradas_data = [
        ('Cimento',       100, date(2026, 3, 1)),
        ('Areia Grossa',   50, date(2026, 3, 1)),
        ('Brita 1',        30, date(2026, 3, 2)),
        ('Tijolo Furado',   5, date(2026, 3, 2)),
        ('Vergalhão 10mm', 200, date(2026, 3, 3)),
        ('Capacete Seg.',  10, date(2026, 3, 1)),
        ('Luvas Raspa',    20, date(2026, 3, 1)),
        ('Martelo 500g',    5, date(2026, 3, 1)),
        ('Nível 60cm',      3, date(2026, 3, 1)),
    ]

    estoques_map = {}
    for nome_i, qtd, dt_ent in entradas_data:
        item, vr_un = itens_map[nome_i]

        # Criar estoque
        est = AlmoxarifadoEstoque.query.filter_by(item_id=item.id, admin_id=ADMIN_ID).first()
        if not est:
            est = AlmoxarifadoEstoque(
                item_id=item.id,
                quantidade=qtd,
                quantidade_inicial=qtd,
                quantidade_disponivel=qtd,
                status='disponivel',
                valor_unitario=vr_un,
                lote=f'L{dt_ent.strftime("%Y%m%d")}',
                admin_id=ADMIN_ID,
            )
            db.session.add(est)
            db.session.flush()

        # Movimento de entrada
        mov_ent = AlmoxarifadoMovimento.query.filter_by(
            item_id=item.id, tipo_movimento='entrada', admin_id=ADMIN_ID
        ).first()
        if not mov_ent:
            mov_ent = AlmoxarifadoMovimento(
                tipo_movimento='entrada',
                item_id=item.id,
                estoque_id=est.id,
                quantidade=qtd,
                valor_unitario=vr_un,
                fornecedor_id=forn.id if forn else None,
                nota_fiscal=f'NF-{random.randint(1000,9999)}',
                observacao=f'Entrada inicial - {nome_i}',
                data_movimento=dt_ent,
                usuario_id=USUARIO_ID,
                admin_id=ADMIN_ID,
                impacta_estoque=True,
            )
            db.session.add(mov_ent)
            est.entrada_movimento_id = mov_ent.id

        estoques_map[nome_i] = (item, est, vr_un)
        log(f"Entrada: {qtd} {item.unidade} de {nome_i}")

    db.session.commit()

    # Saídas de material para as obras
    saidas_data = [
        ('Cimento',       20, obras_criadas[0], date(2026,3,3)),
        ('Cimento',       15, obras_criadas[1], date(2026,3,4)),
        ('Areia Grossa',  10, obras_criadas[0], date(2026,3,3)),
        ('Brita 1',        8, obras_criadas[0], date(2026,3,4)),
        ('Tijolo Furado',  2, obras_criadas[1], date(2026,3,5)),
        ('Vergalhão 10mm',50, obras_criadas[0], date(2026,3,5)),
        ('Capacete Seg.',  5, obras_criadas[0], date(2026,3,1)),
        ('Luvas Raspa',   10, obras_criadas[0], date(2026,3,1)),
    ]

    for nome_i, qtd_s, obra_s, dt_s in saidas_data:
        if nome_i not in estoques_map:
            continue
        item, est, vr_un = estoques_map[nome_i]

        existe_saida = AlmoxarifadoMovimento.query.filter_by(
            item_id=item.id, tipo_movimento='saida', obra_id=obra_s.id, admin_id=ADMIN_ID
        ).first()
        if existe_saida:
            continue

        mov_s = AlmoxarifadoMovimento(
            tipo_movimento='saida',
            item_id=item.id,
            estoque_id=est.id,
            obra_id=obra_s.id,
            quantidade=qtd_s,
            valor_unitario=vr_un,
            observacao=f'Saída para {obra_s.nome}',
            data_movimento=dt_s,
            usuario_id=USUARIO_ID,
            admin_id=ADMIN_ID,
            impacta_estoque=True,
        )
        db.session.add(mov_s)
        db.session.flush()

        # Atualizar estoque disponível
        est.quantidade_disponivel = max(0, (est.quantidade_disponivel or est.quantidade) - qtd_s)

        # CustoObra para material
        valor_total_mat = round(qtd_s * vr_un, 2)
        custo = CustoObra(
            obra_id=obra_s.id,
            tipo='material',
            descricao=f'{nome_i} - saída almoxarifado',
            valor=valor_total_mat,
            data=dt_s,
            item_almoxarifado_id=item.id,
            quantidade=qtd_s,
            valor_unitario=vr_un,
            admin_id=ADMIN_ID,
            categoria='MATERIAL',
        )
        db.session.add(custo)

        # GestaoCusto para material
        pai_mat = GestaoCustoPai(
            tipo_categoria='DESPESA_GERAL',
            entidade_nome=f'Material - {nome_i}',
            entidade_id=item.id,
            valor_total=valor_total_mat,
            valor_solicitado=valor_total_mat,
            status='PAGO',
            data_pagamento=dt_s,
            observacoes=f'{nome_i} → {obra_s.nome} ({qtd_s} {item.unidade})',
            admin_id=ADMIN_ID,
        )
        db.session.add(pai_mat)
        db.session.flush()

        filho_mat = GestaoCustoFilho(
            pai_id=pai_mat.id,
            data_referencia=dt_s,
            descricao=f'{nome_i} para {obra_s.nome}',
            valor=valor_total_mat,
            obra_id=obra_s.id,
            origem_tabela='almoxarifado_movimento',
            origem_id=mov_s.id,
            admin_id=ADMIN_ID,
        )
        db.session.add(filho_mat)

        fc_mat = FluxoCaixa(
            admin_id=ADMIN_ID,
            data_movimento=dt_s,
            tipo_movimento='SAIDA',
            categoria='MATERIAL',
            valor=valor_total_mat,
            descricao=f'Material: {nome_i} → {obra_s.nome}',
            obra_id=obra_s.id,
            referencia_id=pai_mat.id,
            referencia_tabela='gestao_custo_pai',
        )
        db.session.add(fc_mat)
        log(f"Saída: {qtd_s} {item.unidade} de {nome_i} → {obra_s.nome} (R${valor_total_mat})")

    db.session.commit()

    # ─────────────────────────────────────────────────────
    # 10. RELATÓRIO FINAL
    # ─────────────────────────────────────────────────────
    section("10. RELATÓRIO FINAL")

    n_funcs = Funcionario.query.filter_by(admin_id=ADMIN_ID, ativo=True).count()
    n_obras = Obra.query.filter_by(admin_id=ADMIN_ID).count()
    n_rdos = RDO.query.filter_by(admin_id=ADMIN_ID).count()
    n_tarefas = TarefaCronograma.query.filter_by(admin_id=ADMIN_ID).count()
    n_diarias = GestaoCustoPai.query.filter_by(admin_id=ADMIN_ID, tipo_categoria='MAO_OBRA_DIRETA').count()
    n_transp = LancamentoTransporte.query.filter_by(admin_id=ADMIN_ID).count()
    n_alim = AlimentacaoLancamento.query.filter_by(admin_id=ADMIN_ID).count()
    n_itens = AlmoxarifadoItem.query.filter_by(admin_id=ADMIN_ID).count()
    n_mov = AlmoxarifadoMovimento.query.filter_by(admin_id=ADMIN_ID).count()
    n_custo = GestaoCustoPai.query.filter_by(admin_id=ADMIN_ID).count()
    n_fc = FluxoCaixa.query.filter_by(admin_id=ADMIN_ID).count()

    # Totais financeiros
    from sqlalchemy import func as sqlfunc
    total_pago = db.session.query(sqlfunc.sum(GestaoCustoPai.valor_total)).filter_by(
        admin_id=ADMIN_ID, status='PAGO').scalar() or 0
    total_previsto = db.session.query(sqlfunc.sum(GestaoCustoPai.valor_total)).filter(
        GestaoCustoPai.admin_id == ADMIN_ID,
        GestaoCustoPai.status.in_(['SOLICITADO','AUTORIZADO','PENDENTE'])
    ).scalar() or 0
    total_fc_saidas = db.session.query(sqlfunc.sum(FluxoCaixa.valor)).filter_by(
        admin_id=ADMIN_ID, tipo_movimento='SAIDA').scalar() or 0

    print(f"""
  Funcionários V2:        {n_funcs}
  Obras:                  {n_obras}
  Tarefas cronograma:     {n_tarefas}
  RDOs criados:           {n_rdos}
  Diárias (GestaoCusto):  {n_diarias}
  Transportes:            {n_transp}
  Alimentações:           {n_alim}
  Itens almoxarifado:     {n_itens}
  Movimentos almox:       {n_mov}
  Total GestaoCusto:      {n_custo}
  Entradas FluxoCaixa:    {n_fc}

  FINANCEIRO:
  ├─ Total Pago (PAGO):   R$ {total_pago:,.2f}
  ├─ Previsto (SOLICIT.): R$ {total_previsto:,.2f}
  └─ FluxoCaixa saídas:   R$ {total_fc_saidas:,.2f}
""")

    print("  SEED COMPLETO COM SUCESSO!")
