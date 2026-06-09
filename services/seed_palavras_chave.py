"""
Seed das Regras de Classificação do sistema (origem='sistema').

REGRAS_SISTEMA reproduz, de forma declarativa, o classificador hardcoded
`_classificar_categoria_nomeada` de services/importacao_excel.py. A ORDEM da
cascata vira PRIORIDADE (menor decide primeiro). Cada bloco `if` da função vira
uma ou mais entradas:
  - hb(...)  → campo_alvo='qualquer' (blob desc+plano+fornecedor)
  - hd(...)  → campo_alvo='descricao'
  - `and not hd(x)` → excecoes=[x]
  - ternário `... if tem_obra else ...` → duas entradas (com_obra / sem_obra)

Regras com AND entre DOIS campos distintos (ex.: 'beneficio' no plano E 'aliment'
na descrição) não são expressáveis no modelo de uma regra; ficam documentadas em
RESIDUOS_NAO_MIGRAVEIS e são medidas pelo teste de regressão.

Ver ADR-0002 e spec 2026-06-09 §6.
"""
from services.classificador_cadastro import Regra, _norm


# Cada item: (categoria_nome, palavras, campo_alvo, excecoes, condicao_obra)
# A prioridade é atribuída automaticamente pela ordem (passo de 10).

_ENTRADA = [
    ('Rendimentos Financeiros', ['aplicacao financ', 'rendimento', 'receita financeira', 'juros recebido'], 'qualquer', [], 'indiferente'),
    ('Reembolso de Cliente', ['reembolso', 'repasse', 'ressarcimento'], 'descricao', [], 'indiferente'),
    ('Aporte de Sócios', ['aporte', 'capital social', 'integralizacao'], 'qualquer', [], 'indiferente'),
    ('Empréstimos Recebidos', ['emprestimo', 'financiamento captado'], 'qualquer', [], 'indiferente'),
    ('Venda de Ativos', ['venda de ativo', 'alienacao', 'venda de bem', 'venda de equipamento'], 'qualquer', [], 'indiferente'),
    ('Adiantamento de Clientes', ['adiantamento', 'sinal', 'antecipa', 'entrada (', 'entrada -'], 'descricao', [], 'indiferente'),
    ('Receita de Obras', ['obra', 'medicao', 'contrato', 'administracao de obra', 'taxa administracao', 'taxa de administracao', 'faturamento', 'receita obra'], 'qualquer', [], 'indiferente'),
    ('Receita de Serviços', ['servico', 'projeto', 'honorario', ' nf ', 'nf ', 'receita servic'], 'qualquer', [], 'indiferente'),
]

_SAIDA = [
    # Pessoal — Mão de Obra Direta: hd('diaria') OR hb(lista) → duas entradas
    ('Mão de Obra Direta', ['diaria'], 'descricao', [], 'indiferente'),
    ('Mão de Obra Direta', ['trabalho noturno', 'hora extra', 'adicional noturno', 'extra trabalho', 'extra noturno', 'extra diurno', 'ajudante', 'servente', 'encarregado', 'ajuda de custo', 'mao-de-obra', 'mao de obra', 'periodo de trabalho', 'vale (', 'plaqueamento'], 'qualquer', [], 'indiferente'),
    # Salários (exceto diária)
    ('Salários e Encargos', ['salario', 'folha de pagamento', 'rescisao', 'ferias', '13o salario', 'decimo terceiro', 'bonus', 'captacao', 'recrutamento', 'selecao de pessoal'], 'qualquer', ['diaria'], 'indiferente'),
    ('Pró-labore e Retirada de Sócios', ['retirada', 'pro-labore', 'pro labore', 'prolabore', 'distribuicao de lucro', 'distribuicao de resultado'], 'qualquer', [], 'indiferente'),
    # Vale transporte (ternário obra)
    ('Transporte de Obra', ['vale transporte', 'vale-transporte', 'vale trans', 'vale-trans', 'vt mes', ' vt '], 'qualquer', [], 'com_obra'),
    ('Benefício Transporte', ['vale transporte', 'vale-transporte', 'vale trans', 'vale-trans', 'vt mes', ' vt '], 'qualquer', [], 'sem_obra'),
    # Vale alimentação (ternário obra) + clausula 'beneficio' no plano E 'aliment' na desc
    ('Alimentação de Obra', ['vale alimentacao', 'vale-alimentacao', 'vale refeicao', 'vale alim'], 'qualquer', [], 'com_obra'),
    ('Benefício Alimentação', ['vale alimentacao', 'vale-alimentacao', 'vale refeicao', 'vale alim'], 'qualquer', [], 'sem_obra'),
    ('Alimentação de Obra', ['aliment'], 'descricao', [], 'com_obra', ['beneficio'], 'plano'),
    ('Benefício Alimentação', ['aliment'], 'descricao', [], 'sem_obra', ['beneficio'], 'plano'),
    # Reembolsos a Funcionários: reembolso na desc E funcionario/colaborador no blob
    ('Reembolsos a Funcionários', ['reembolso'], 'descricao', [], 'indiferente', ['funcionario', 'colaborador'], 'qualquer'),
    # Tributos
    ('Impostos e Taxas', ['simples nacional', 'darf', ' inss', 'inss ', 'fgts', 'imposto', 'tributo', 'irpj', 'csll', 'icms', ' das ', 'das ', 'parcelamento das', 'guia de recolhimento', 'iptu parcela', 'iptu -', 'prefeitura', 'licenca funcionamento', 'licenca de funcionamento', 'ipva'], 'qualquer', [], 'indiferente'),
    # Financeiro
    ('Empréstimos e Financiamentos', ['emprestimo', 'financiamento', 'renegociacao', 'divida', 'parcela do emprestimo'], 'qualquer', [], 'indiferente'),
    ('Despesas Bancárias', ['iof', 'tarifa', 'tar ', 'taxa bancaria', 'anuidade', 'cesta de servic', 'manutencao de conta', 'despesa bancaria'], 'qualquer', [], 'indiferente'),
    ('Despesa Financeira', ['juros', 'multa', 'mora', 'encargo financeiro', 'despesa financeira'], 'qualquer', [], 'indiferente'),
    # Utilities / administrativo — Água: hb(...) OR (hd('agua') and not hd('maquina'))
    ('Água', ['sabesp', 'conta de agua', 'saneamento'], 'qualquer', [], 'indiferente'),
    ('Água', ['agua'], 'descricao', ['maquina'], 'indiferente'),
    ('Luz / Energia Elétrica', ['energia eletrica', 'enel', 'cpfl', 'elektro', 'eletropaulo', 'edp', 'conta de luz', 'energia'], 'qualquer', [], 'indiferente'),
    ('Internet', ['internet', 'fibra', 'banda larga', 'vivo fixo', 'vivo empresas - fixo'], 'qualquer', [], 'indiferente'),
    ('Telefone', ['vivo movel', 'telefone', 'celular', 'plano movel', 'claro ', ' tim ', 'vivo empresas - movel', 'vivo empresas', 'telefonica'], 'qualquer', [], 'indiferente'),
    ('Sistemas e Assinaturas', ['workspace', 'google', 'microsoft', 'office 365', 'software', 'assinatura', 'sistema', 'saas', 'dropbox', 'licenca de software', 'app ', 'aplicativo', 'plataforma', 'diario de obra', 'configuracao servidor'], 'qualquer', [], 'indiferente'),
    ('Contabilidade e Jurídico', ['contabil', 'contador', 'advogad', 'juridico', 'assessoria contabil', 'tabeliao', 'cartorio', 'protesto', 'advocaticio', 'honorario advocaticio'], 'qualquer', [], 'indiferente'),
    ('Marketing e Vendas', ['marketing', 'publicidade', 'anuncio', 'trafego', 'google ads', 'instagram', 'facebook', 'comercial externo', 'representante comercial', 'comissao de venda', 'comissao venda', 'comissao sobre venda', 'comissao comercial', 'comissao (', 'mkt', 'markenting', 'marketing digital', 'brinde', 'presente cliente', 'brinde cliente'], 'qualquer', [], 'indiferente'),
    ('Material de Escritório', ['plotagem', 'copias', 'impressao', 'impressoes', 'papelaria', 'cartucho', 'toner', 'material de escritorio', 'post it', 'post-it', 'caneta', 'pasta ', 'calculadora', 'grampeador', 'clips', 'notebook', 'monitor lg', 'computador', 'desktop', 'impressora', 'mouse', 'teclado', 'suporte cpu'], 'qualquer', [], 'indiferente'),
    ('Treinamentos e Capacitações', ['treinamento', 'capacitacao', 'curso ', 'certificacao', 'workshop', 'pos graduacao', 'pos-graduacao', 'graduacao', 'faculdade', 'mba'], 'qualquer', [], 'indiferente'),
    # Aluguel administrativo — 2a clausula (imoveis/imobiliaria AND aluguel...) é resíduo
    ('Aluguel e Locação Administrativa', ['aluguel administrat', 'locacao administrat', 'sala comercial', 'aluguel escritorio', 'alguel escritorio', 'condominio escritorio', 'condominio escrtitorio', 'iptu escritorio', 'aluguel de sala', 'locacao de sala', 'locker', 'arquivamento'], 'qualquer', [], 'indiferente'),
    # 2a clausula do Aluguel: fornecedor imoveis/imobiliaria E aluguel/iptu/condominio/locacao no blob
    ('Aluguel e Locação Administrativa', ['aluguel', 'alguel', 'iptu', 'condominio', 'locacao'], 'qualquer', [], 'indiferente', ['imoveis', 'imobiliaria'], 'fornecedor'),
    ('Manutenção Predial e Escritório', ['manutencao predial', 'reforma escritorio', 'reparo escritorio'], 'qualquer', [], 'indiferente'),
    # Custo direto de obra
    ('Manutenção de Frota e Equipamentos', ['conserto', 'concerto', 'revisao', 'mecanica', 'oficina', 'pneu', 'funilaria', 'manutencao de veiculo', 'manutencao carro', 'lavagem carro', 'lava jato', 'lava-jato', 'lava rapido', 'limpeza carro', 'solda escapamento', 'escapamento', 'centro automotivo', 'bateria', 'amortecedor', 'parabrisa', 'para-brisa', 'filtro de ar', 'jogo de velas', 'porta mala', 'litro de oleo', 'oleo carro', 'auto vitrais', 'troca lanterna', 'kit amortecedor', 'filtro de oleo', 'guincho', 'peca gol', 'peca carro', 'autopecas', 'auto pecas', 'oleo gol', 'porta - gol'], 'qualquer', [], 'indiferente'),
    ('Combustível e Frota', ['aluguel de carro', 'aluguel carro', 'aluguel de carros', 'aluguel de veiculo', 'rent car', 'rent a car', 'localiza', 'movida locacao', 'unidas locacao', 'combustivel', 'gasolina', 'diesel', 'etanol', 'posto ', 'abastec', 'pedagio', 'sem parar'], 'qualquer', [], 'indiferente'),
    ('Fretes e Entregas', ['frete', 'entrega', 'transportadora', 'transportes', 'carreto', 'viagem', 'caminhao'], 'qualquer', [], 'indiferente'),
    ('Locação de Equipamentos', ['locacao de', 'aluguel de equip', 'martelete', 'esmerilhadeira', 'betoneira', 'andaime', 'compressor', 'gerador', 'cacamba', 'locacao '], 'qualquer', [], 'indiferente'),
    ('EPIs e Segurança do Trabalho', ['epi', 'capacete', 'bota ', 'botina', 'luva', 'oculos de protecao', 'cinto de seguranca', 'protetor', 'mascara', 'exame admissional', 'exame demissional', 'exame periodico', 'exame ocupacional', 'exames admissionais', 'medicina do trabalho', 'aso ', 'admissional', 'demissional', 'uniforme', 'fardamento', 'nr 18', 'nr 35', 'nr-18', 'nr-35'], 'qualquer', [], 'indiferente'),
    ('Ferramentas e Consumíveis', ['ferramenta', 'parafusadeira', 'broca', 'disco', 'furadeira', 'serra ', 'serrote', 'consumivel', 'trena', 'alicate', 'martelo', 'chave de fenda', 'enxada', 'picareta', ' bit ', 'estilete', 'soquete', 'pilha', 'brocha', 'marreta', 'talhadeira', 'makita', 'pa quadrada', 'aspirador', 'lixadeira', 'pistola aplicacao', 'pistola pu', 'bits', 'parcela laser'], 'qualquer', [], 'indiferente'),
    ('Taxas de Obra / ART / Licenças', ['art ', 'anotacao de responsabilidade', 'licenca', 'alvara', 'taxa de obra', 'crea '], 'qualquer', [], 'indiferente'),
    ('Hospedagem de Obra', ['hospedagem', 'hotel', 'pousada'], 'qualquer', [], 'indiferente'),
    ('Alimentação de Obra', ['almoc', 'refeic', 'cafe', 'ifood', 'marmit', 'lanche', 'restaurante', 'jantar', 'janta', 'cambuca', 'padaria', 'supermercado', 'cesta basica', 'alimentacao', 'gas de cozinha', 'gas cozinha', 'botijao'], 'qualquer', [], 'indiferente'),
    # Transporte de Obra: hb(...) OR hd(...) OR ('km'+digito ~ 'km' na desc)
    ('Transporte de Obra', ['vale transporte', 'estacionamento', 'conducao', 'linhas aereas', 'passagem aerea', 'blablacar', 'bla bla car'], 'qualquer', [], 'indiferente'),
    ('Transporte de Obra', ['transporte', 'passagem', 'onibus', 'uber', ' km'], 'descricao', [], 'indiferente'),
    # km + dígito na descrição (ex.: '1083km'): 'km' na desc E algum dígito na desc
    ('Transporte de Obra', ['km'], 'descricao', [], 'indiferente', list('0123456789'), 'descricao'),
    ('Subempreitada', ['subempreit', 'empreita', 'subcontrat'], 'qualquer', [], 'indiferente'),
    ('Serviços Terceirizados de Obra', ['instalacao', 'assentamento', 'montagem', 'montador'], 'qualquer', [], 'indiferente'),
    ('Materiais de Obra', ['cimento', 'concreto', 'argamassa', 'ferro', ' aco', 'tijolo', 'areia', 'brita', 'tinta', 'madeira', 'vidro', 'tubo', 'porcelanato', 'telha', 'material', 'materiai', 'leroy', 'cimento&tudo', 'concrelagos', 'dividros', 'bomba', 'eletrico', 'hidraulico', 'parabolt', 'selante', 'vergalhao', 'mola aerea', 'parafus', 'luminaria', 'ralo', 'cabo', 'abracadeira', 'cantoneira', 'forro', 'divisoria', 'aluminio', 'porta de', 'rodape', 'piso ', 'lona', 'deposito', 'gesso', 'arame', 'pedido', ' oc ', 'saco de', 'entulho', 'produto de limpeza', 'interfone', 'fechadura', 'mezanino', 'fita crepe', 'adaptador', 'osb', 'montante', 'bloco', 'impermeabilizante', 'vedacao', 'galvanizado', 'casa do lojista', 'tapume', 'cal para', 'baguete', 'painel', 'conduite', 'gaivota', 'fercorte', 'la de rocha', 'la de vidro', 'leds', ' led ', 'produto limpeza'], 'qualquer', [], 'indiferente'),
    ('Serviços Terceirizados de Obra', ['servico', 'terceiro', 'mao de obra', 'pedreiro', 'eletricista', 'encanador', 'pintor', 'pintura', 'gesseiro', 'projeto', 'projetista', 'medicao', 'topografia', 'sondagem', 'engenharia', 'fachada', 'reparo do', 'reparo de', 'eletrica', 'eletria', 'hidraulica', 'diarista', 'faxina', 'soldador', 'azulejista', 'pagamento semana'], 'qualquer', [], 'indiferente'),
]

# Categorias de fallback (quando nada casa) — o classificador devolve eh_pendente.
FALLBACK_ENTRADA = 'Outros Recebimentos'
FALLBACK_SAIDA = 'Outras Saídas'

# Regras com AND entre dois campos distintos — migradas via gatilho_extra/campo_extra
# (condição extra do modelo). Nada residual: a regressão prova paridade total.
RESIDUOS_NAO_MIGRAVEIS = []


def _build(linhas, tipo, prio_inicial=10):
    regras = []
    prio = prio_inicial
    for ln in linhas:
        cat_nome, palavras, campo, excecoes, cond_obra = ln[0], ln[1], ln[2], ln[3], ln[4]
        gatilho_extra = ln[5] if len(ln) > 5 else []
        campo_extra = ln[6] if len(ln) > 6 else 'qualquer'
        regras.append(Regra(
            palavras=list(palavras), categoria_id=0, categoria_nome=cat_nome,
            campo_alvo=campo, excecoes=list(excecoes), condicao_obra=cond_obra,
            prioridade=prio, origem='sistema', tipo=tipo,
            gatilho_extra=list(gatilho_extra), campo_extra=campo_extra,
        ))
        prio += 10
    return regras


def regras_sistema():
    """Lista de Regra (objetos do classificador) reproduzindo o hardcode.
    categoria_id=0 (placeholder); o seed por tenant resolve o id real."""
    return _build(_ENTRADA, 'ENTRADA') + _build(_SAIDA, 'SAIDA')


# ── Persistência por tenant ──────────────────────────────────────────────────

def _join(lista):
    return ','.join(lista) if lista else None


def _split(texto):
    return texto.split(',') if texto else []


def seed_para_admin(admin_id, commit=False):
    """Persiste REGRAS_SISTEMA como PalavraChaveCategoria (origem='sistema') para
    o tenant, resolvendo categoria_nome → categoria_fluxo_caixa_id. Idempotente:
    re-rodar não duplica (chave: prioridade+tipo+palavras+campo_alvo). Regras cuja
    categoria não existe no tenant são ignoradas. Retorna o nº de regras criadas."""
    from models import db, CategoriaFluxoCaixa, PalavraChaveCategoria

    cat_id_por_nome = {
        _norm(c.nome): c.id
        for c in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id, ativo=True).all()
    }
    existentes = {
        (r.prioridade, r.tipo, r.palavras, r.campo_alvo)
        for r in PalavraChaveCategoria.query.filter_by(
            admin_id=admin_id, origem='sistema').all()
    }

    criadas = 0
    for regra in regras_sistema():
        cid = cat_id_por_nome.get(_norm(regra.categoria_nome))
        if not cid:
            continue
        palavras_str = ','.join(regra.palavras)
        chave = (regra.prioridade, regra.tipo, palavras_str, regra.campo_alvo)
        if chave in existentes:
            continue
        db.session.add(PalavraChaveCategoria(
            admin_id=admin_id, categoria_fluxo_caixa_id=cid,
            palavras=palavras_str, campo_alvo=regra.campo_alvo,
            excecoes=_join(regra.excecoes),
            gatilho_extra=_join(regra.gatilho_extra), campo_extra=regra.campo_extra,
            condicao_obra=regra.condicao_obra, prioridade=regra.prioridade,
            tipo=regra.tipo, origem='sistema', ativo=True,
        ))
        existentes.add(chave)
        criadas += 1

    db.session.flush()
    if commit:
        db.session.commit()
    return criadas


def regras_do_tenant(admin_id):
    """Carrega as Regras de Classificação ativas do tenant como objetos Regra
    (consumível pelo classificador)."""
    from models import CategoriaFluxoCaixa, PalavraChaveCategoria

    nome_por_id = {
        c.id: c.nome
        for c in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id).all()
    }
    regras = []
    for r in PalavraChaveCategoria.query.filter_by(admin_id=admin_id, ativo=True).all():
        regras.append(Regra(
            palavras=_split(r.palavras),
            categoria_id=r.categoria_fluxo_caixa_id,
            categoria_nome=nome_por_id.get(r.categoria_fluxo_caixa_id, ''),
            campo_alvo=r.campo_alvo, excecoes=_split(r.excecoes),
            condicao_obra=r.condicao_obra, prioridade=r.prioridade,
            origem=r.origem, tipo=r.tipo,
            gatilho_extra=_split(r.gatilho_extra), campo_extra=r.campo_extra,
        ))
    return regras
