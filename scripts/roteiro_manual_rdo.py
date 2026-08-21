#!/usr/bin/env python3
"""As telas do manual do RDO — a ÚNICA lista de onde saem caixas e legendas.

Ordem: de onde o RDO vem (o cronograma) → preencher (efetivo, terceiro, avanço,
ocorrência, fotos) → salvar → submeter → reabrir → submeter → assinar → aprovar
→ retificar. Segue a norma do capítulo 23a do manual do sistema.

`{obra_id}`, `{t_*}`, `{f_*}`, `{sub_id}`, `{hoje}` vêm de `resolver_ids()`
(seed). `{rdo_id}` e `{rdo_retif_id}` só existem depois de salvar/retificar:
a captura os lê da URL (`Tela.guarda_id`) e resolve em runtime. `{foto1..3}`
são os PNGs que a captura gera.

Plano: docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anotar_captura import Acao, Campo, Tela

FOTOS = '{foto1};{foto2};{foto3}'
MOTIVO_REABERTURA = 'Faltou a hora da chuva na ocorrência'
MOTIVO_RETIFICACAO = 'Quantidade de estacas do dia era 5, não 6'
CLIMA = 'Ensolarado'
BOTAO_OCORRENCIA = "button[onclick=\"adicionarLinhaRepetivel('ocorr-rows','ocorr')\"]"


def resolver_ids():
    from datetime import date
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    from seed_manual_rdo import MARCA, resumo
    with app.app_context():
        admin = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
        if admin is None:
            raise SystemExit('tenant manualrdo não existe — rode scripts/seed_manual_rdo.py')
        ids = resumo(admin)
    ids['hoje'] = date.today().isoformat()
    return ids


def montar(ids):
    i = ids
    horas_davi = f'input[name="func_{i["t_blocos"]}_{i["f_davi"]}_horas"]'
    horas_pedro = f'input[name="func_{i["t_blocos"]}_{i["f_pedro"]}_horas"]'
    return [
        # ---------------- ANTES — de onde o RDO vem ----------------
        Tela(slug='01_login', titulo='Entrar no sistema', papel='anon',
             ato='Antes de tudo', ato_resumo='Entrar, e entender de onde o RDO vem.',
             rota='/login',
             resumo='Quem lança RDO entra com o próprio usuário. O que aparece depois '
                    'depende do papel na obra: apontador lança e assina; gestor '
                    'reabre e aprova.',
             campos=[Campo(1, 'input[name="username"]', 'Usuário ou e-mail', True),
                     Campo(2, 'input[name="password"]', 'Senha', True),
                     Campo(3, 'button[type="submit"]', 'Entrar')],
             recorte='form'),
        Tela(slug='02_cronograma', titulo='O RDO é alimentado pelo cronograma',
             papel='encarregado', rota=f"/cronograma/obra/{i['obra_id']}",
             resumo='As atividades que você vai apontar no RDO são ESTAS. O RDO não '
                    'tem lista própria: ele lê o cronograma da obra, e cada apontamento '
                    'volta para cá como avanço.',
             campos=[Campo(1, 'thead.cronograma-thead th.th-nome', 'As atividades',
                           nota='Só as folhas (sem filhas) recebem apontamento. As fases '
                                'somam as filhas.'),
                     Campo(2, 'thead.cronograma-thead th[title^="Quantidade prevista"]',
                           'Qtd / Un.',
                           nota='Atividade com quantidade e unidade é apontada por '
                                'QUANTIDADE executada no dia. Sem quantidade, por '
                                'percentual acumulado.'),
                     Campo(3, 'thead.cronograma-thead th[title^="Responsável"]',
                           'Responsável',
                           nota='"terceiros" é equipe de terceiro — mas o botão de '
                                'terceiro existe em qualquer atividade.'),
                     Campo(4, 'thead.cronograma-thead th[title^="Progresso realizado"]',
                           '% Realizado',
                           nota='Calculado automaticamente pelos apontamentos do RDO. '
                                'Ninguém digita aqui.')],
             recorte='#leftPane',
             atencao='RDO em rascunho NÃO mexe nesta coluna. Só o RDO submetido.'),
        Tela(slug='03_rdos_da_obra', titulo='Os RDOs da obra', papel='encarregado',
             rota='/rdos',
             resumo='Um RDO por obra, por dia trabalhado. Aqui você vê o que já foi '
                    'lançado e cria o de hoje.',
             campos=[Campo(1, f'a[href*="/rdos?obra_id={i["obra_id"]}"]', 'A obra'),
                     Campo(2, 'a[href*="/rdo/novo"]', 'Novo RDO')]),
        # ---------------- ATO 1 — preencher ----------------
        Tela(slug='04_cabecalho', titulo='Obra, data e clima', papel='encarregado',
             ato='Ato 1 — Preencher o dia',
             ato_resumo='Do cabeçalho às fotos, na ordem em que a tela pede.',
             rota=f"/rdo/novo?obra_id={i['obra_id']}",
             resumo='O cabeçalho do dia: qual obra, que dia, como estava o tempo. '
                    'A data é a do dia trabalhado — e o RDO é lançado no mesmo dia.',
             acoes=[Acao('escolher', '#obra_id', str(i['obra_id'])),
                    Acao('preencher', '#data_relatorio', i['hoje']),
                    Acao('escolher', '#clima_geral', CLIMA),
                    Acao('preencher', '#temperatura_media', '29°C')],
             campos=[Campo(1, '#obra_id', 'Obra', True),
                     Campo(2, '#data_relatorio', 'Data do RDO', True,
                           nota='A data do dia trabalhado — lançado NO MESMO DIA. Dois '
                                'dias de atraso é motivo de devolução.'),
                     Campo(3, '#clima_geral', 'Clima',
                           nota='É o que sustenta a ocorrência de chuva quando ela vira '
                                'discussão de prazo.'),
                     Campo(4, '#temperatura_media', 'Temperatura')],
             depois='Ao escolher a obra, as atividades do cronograma aparecem abaixo.'),
        Tela(slug='05_atividades', titulo='As atividades, dentro do RDO', papel='encarregado',
             rota='', permanece=True,
             resumo='São as mesmas atividades do cronograma. Em cada linha: onde apontar '
                    'o avanço, e os dois botões — equipe própria e terceiro.',
             campos=[Campo(1, '#cronogramaTarefasRDO', 'As atividades do cronograma'),
                     Campo(2, f'#qty_tarefa_{i["t_blocos"]}', 'Quantidade de HOJE',
                           nota='Atividade por quantidade: o que foi executado hoje, não '
                                'o acumulado. O sistema soma.'),
                     Campo(3, f'#pct_tarefa_{i["t_pilares"]}', 'Percentual ACUMULADO',
                           nota='Atividade por percentual: o acumulado da atividade, não '
                                'o do dia.'),
                     Campo(4, f'#chk_marco_{i["t_marco"]}', 'Marco',
                           nota='Marque só no dia em que ele de fato ocorreu.'),
                     Campo(5, f'#btn-equipe-{i["t_blocos"]}', 'Equipe própria'),
                     Campo(6, f'#btn-terceiro-{i["t_estacas"]}', 'Terceiro',
                           nota='Existe em qualquer atividade, inclusive nas nossas.')],
             recorte='#cronogramaTarefasRDO'),
        Tela(slug='06_equipe_lista', titulo='Equipe própria — só quem é operacional',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', f'#btn-equipe-{i["t_blocos"]}')],
             resumo='A lista traz só o pessoal OPERACIONAL. A Ana, do escritório, não '
                    'aparece — a função dela está marcada como administrativa.',
             campos=[Campo(1, '#modalFuncFiltro', 'Buscar pelo nome'),
                     Campo(2, '#modalFuncLista', 'Quem pode ser alocado',
                           nota='Quem trabalhou e não aparece aqui está com a função '
                                'marcada como administrativa no cadastro — avise o '
                                'escritório, não deixe de fora.')],
             recorte='#modalEquipeTarefa .modal-content'),
        Tela(slug='07_equipe_horas', titulo='Quem esteve, e quantas horas',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', '#modalFuncLista button:has-text("Davi Montador")'),
                    Acao('clicar', '#modalFuncLista button:has-text("Pedro Ajudante")'),
                    Acao('preencher', horas_davi, '8'),
                    Acao('preencher', horas_pedro, '8')],
             resumo='Cada pessoa com as horas NESTA atividade. Quem trabalhou em duas '
                    'atividades aparece nas duas, com as horas divididas — a soma bate '
                    'com a jornada.',
             campos=[Campo(1, '#modalEquipeSelecionada', 'Alocados nesta atividade'),
                     Campo(2, horas_davi, 'Horas de cada um', True),
                     Campo(3, '#modalEquipeTarefa button.btn-primary', 'Confirmar')],
             recorte='#modalEquipeTarefa .modal-content',
             atencao='Não é aceito: escrever o efetivo em observação, ou só o número de '
                     'pessoas sem dizer quem.'),
        Tela(slug='08_terceiro', titulo='Equipe de terceiro', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('clicar', '#modalEquipeTarefa button.btn-primary'),
                    Acao('clicar', f'#btn-terceiro-{i["t_estacas"]}'),
                    Acao('escolher', '#sub_subempreiteiro_id', str(i['sub_id'])),
                    Acao('preencher', '#sub_qtd_pessoas', '11'),
                    Acao('preencher', '#sub_horas', '9'),
                    Acao('preencher', '#sub_qtd_prod', '6')],
             resumo='"Abraão, 11 pessoas" deixa de ser anotação no papel: nome do '
                    'cadastro, quantidade de pessoas, horas e — se houver medida física '
                    'do dia — a produção.',
             campos=[Campo(1, '#sub_subempreiteiro_id', 'Terceiro (do cadastro)', True,
                           nota='Não está cadastrado? Peça o cadastro ao escritório.'),
                     Campo(2, '#sub_qtd_pessoas', 'Quantidade de pessoas', True,
                           nota='É este número que responde depois "em quantos dias, '
                                'com quantos homens".'),
                     Campo(3, '#sub_horas', 'Horas da equipe'),
                     Campo(4, '#sub_qtd_prod', 'Produção do dia',
                           nota='Só quando houver medida física (un, m², m³). Sem medida, '
                                'zero — registrar efetivo NÃO move o avanço.'),
                     Campo(5, '#modalSubempreitada button.btn-primary', 'Salvar')],
             recorte='#modalSubempreitada .modal-content',
             atencao='Não é aceito: anotar "11 pessoas" em observação, ou pular o terceiro '
                     'porque a atividade é nossa.'),
        Tela(slug='09_avanco', titulo='O avanço de quem andou hoje', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('clicar', '#modalSubempreitada button.btn-primary'),
                    Acao('preencher', f'#qty_tarefa_{i["t_blocos"]}', '2'),
                    Acao('preencher', f'#pct_tarefa_{i["t_pilares"]}', '15')],
             resumo='Aponte só as atividades que andaram. Quantidade é a de HOJE; '
                    'percentual é o ACUMULADO; marco só no dia em que ocorreu.',
             campos=[Campo(1, f'#qty_tarefa_{i["t_blocos"]}', 'Blocos: 2 hoje'),
                     Campo(2, f'#pct_tarefa_{i["t_pilares"]}', 'Pilares: 15 % acumulado'),
                     Campo(3, f'#chk_marco_{i["t_marco"]}', 'Marco: em branco',
                           nota='A liberação ainda não aconteceu. Em branco.')],
             recorte='#cronogramaTarefasRDO',
             atencao='Não é aceito: repetir o número da véspera para "não deixar vazio", '
                     'nem apontar 100 % "porque está quase acabando".'),
        Tela(slug='10_ocorrencias', titulo='O que aconteceu, quando e qual o efeito',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', BOTAO_OCORRENCIA),
                    Acao('escolher', '[name="ocorr_tipo[]"]', 'Clima'),
                    Acao('escolher', '[name="ocorr_severidade[]"]', 'Média'),
                    Acao('preencher', '[name="ocorr_descricao[]"]',
                         'Chuva das 10h às 14h — concretagem do bloco B3 adiada para amanhã')],
             resumo='"Choveu" não é ocorrência. "Chuva das 10h às 14h, concretagem do '
                    'bloco B3 adiada" é: diz o que, quando e o efeito.',
             campos=[Campo(1, '[name="ocorr_tipo[]"]', 'Tipo', True),
                     Campo(2, '[name="ocorr_severidade[]"]', 'Severidade'),
                     Campo(3, '[name="ocorr_descricao[]"]', 'O que, quando, efeito', True)],
             recorte='#ocorr-rows',
             atencao='Não é aceito: dia em que a produção caiu sem ocorrência que explique.'),
        Tela(slug='11_fotos', titulo='Três fotos, no mínimo', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('anexar', '#fileInputNovoGal', FOTOS),
                    Acao('preencher', '#observacoes_finais',
                         'Frente de serviço liberada às 7h. Chuva das 10h às 14h.')],
             resumo='Uma da frente de serviço no início, uma do que foi executado, uma de '
                    'cada ocorrência física. A foto tem de deixar ver ONDE é.',
             campos=[Campo(1, '#previewContainerNovo', 'As fotos anexadas'),
                     Campo(2, '#observacoes_finais', 'Observações finais')],
             atencao='Ocorrência física (dano, interdição, material errado, alagamento) '
                     'sem foto é motivo de devolução.'),
        Tela(slug='12_salvar_rascunho', titulo='Salvo — mas ainda é rascunho',
             papel='encarregado', rota='', permanece=True, guarda_id='rdo_id',
             acoes=[Acao('submeter', '#btnFinalizarRDO')],
             resumo='O RDO nasce em RASCUNHO. Pode editar à vontade durante o dia — mas '
                    'rascunho não lança custo nem alimenta o cronograma. Para o resto do '
                    'sistema, é um dia que ainda não existiu.',
             campos=[Campo(1, '.estado-badge', 'O estado: rascunho')],
             atencao='RDO esquecido em rascunho não é devolvido: ele simplesmente não '
                     'conta. É o sexto motivo da lista do escritório.'),
        # ---------------- ATO 2 — fechar ----------------
        Tela(slug='13_submeter', titulo='Submeter: o fecho do dia', papel='encarregado',
             ato='Ato 2 — Fechar o dia',
             ato_resumo='Submeter, corrigir se preciso, assinar. Depois disso o documento '
                        'não se mexe — se retifica.',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/finalizar"] button[type="submit"]')],
             resumo='É aqui que os custos de mão de obra são lançados, a medição é '
                    'recalculada e o cliente passa a enxergar o dia. No fim do DIA, não '
                    'no fim da semana.',
             campos=[Campo(1, '.estado-badge', 'O estado: preenchido')],
             depois='O % Realizado do cronograma (tela 2) acabou de mudar.'),
        Tela(slug='14_reabrir', titulo='Errou? O gestor reabre', papel='gestor',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/reabrir"] button[type="submit"]')],
             resumo='Enquanto está PREENCHIDO, o RDO ainda é corrigível: o gestor reabre '
                    '(com motivo), ele volta a rascunho, você corrige e submete de novo.',
             campos=[Campo(1, '.estado-badge', 'Voltou a rascunho')],
             atencao=f'O motivo é obrigatório e fica registrado. Aqui: "{MOTIVO_REABERTURA}".'),
        Tela(slug='15_submeter_de_novo', titulo='Corrigiu, submete de novo',
             papel='encarregado', rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/finalizar"] button[type="submit"]')],
             resumo='O mesmo botão. O histórico guarda a reabertura e a nova submissão.',
             campos=[Campo(1, '.estado-badge', 'Preenchido outra vez')]),
        Tela(slug='16_assinar', titulo='Assinar: vira documento', papel='encarregado',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/assinar"] button[type="submit"]')],
             resumo='A assinatura é o que dá ao RDO valor de documento. Depois dela, '
                    'nada mais é editado — de propósito.',
             campos=[Campo(1, '.estado-badge', 'Assinado — imutável')],
             atencao='Nunca crie um segundo RDO do mesmo dia "por fora" para consertar. '
                     'Ou se reabre antes de assinar, ou se retifica depois.'),
        Tela(slug='17_aprovar', titulo='Aprovar: o aceite do gestor', papel='gestor',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/aprovar"] button[type="submit"]')],
             resumo='O gestor da obra aceita o dia. Estado final.',
             campos=[Campo(1, '.estado-badge', 'Aprovado')]),
        Tela(slug='18_retificar', titulo='Achou erro depois? Retifica', papel='gestor',
             rota='/rdo/{rdo_id}', guarda_id='rdo_retif_id',
             acoes=[Acao('submeter', 'form[action$="/retificar"] button[type="submit"]')],
             resumo='Um documento de data não se apaga — se retifica. O sistema emite um '
                    'NOVO RDO da mesma data, e marca o original como retificado. Os dois '
                    'ficam, e a correção é rastreável.',
             campos=[Campo(1, '.estado-badge', 'O retificador nasce em rascunho')],
             depois=f'Motivo registrado: "{MOTIVO_RETIFICACAO}". Preencha o retificador '
                    'como o original, dizendo o que o primeiro deveria ter dito, e feche '
                    'pelo mesmo caminho.'),
    ]


def telas(ids=None):
    return montar(ids or resolver_ids())
