"""De-para das contas 5.x para o canônico (Fase 8, Task 4).

Chaveado em (ASSINATURA, codigo) — decisão D6, respondida em 01/09. Os dois
seeders aposentados TROCAM o significado de 5.1.01 e 5.1.02 entre si:

    5.1.01 = 'Materiais Diretos' (contabilidade_utils)
    5.1.01 = 'MÃO DE OBRA'       (financeiro_seeds)

Um de-para por código mandaria material para pessoal em metade do parque,
e o erro seria SILENCIOSO — a partida migraria sem falhar.

Por que (assinatura, codigo) e NÃO (codigo, nome): o nome é o dado que a
spec proíbe usar, porque é justamente o que está inconsistente. A
assinatura é descoberta pela FORMA do plano de contas
(contabilidade_utils.classificar_assinatura), sem ler nome nenhum.

🔬 04/09, no banco de dev: o par (codigo, nome) teria falhado também —
`5.1.03.001` está gravado como **'CMV'** no banco e como *'Aluguel de
Equipamentos'* em `financeiro_seeds.py:85`. O nome do banco não bate com o
nome do seeder que o criou.

Código sem destino na assinatura do tenant => a migration FALHA e nomeia
o par. Nunca chuta.

⚠️ ESTE ARQUIVO É PARA REVISÃO LINHA A LINHA antes de a migration rodar em
produção. Os destinos abaixo são recomendação do executor, não decisão
tomada: `Ferramentas`, `EPIs` e `Aluguel de Equipamentos` caindo todos em
`Despesa com Material` é a escolha mais discutível da tabela.
"""

DEPARA_5X: dict = {
    # --- assinatura 'contabilidade_utils' (seeder nº1, 3 analíticas em 5.x) ---
    ('contabilidade_utils', '5.1.01'): '6.1.02.003',  # Materiais Diretos -> Despesa com Material
    ('contabilidade_utils', '5.1.02'): '6.1.01.001',  # Mão de Obra Direta -> Despesa com Salários
    ('contabilidade_utils', '5.2.01'): '6.1.02.003',  # Materiais Indiretos -> Despesa com Material
    # --- assinatura 'financeiro_seeds' (seeder nº2, 16 analíticas) ---
    ('financeiro_seeds', '5.1.01.001'): '6.1.01.001',  # Salários
    ('financeiro_seeds', '5.1.01.002'): '6.1.01.001',  # Encargos Sociais
    ('financeiro_seeds', '5.1.01.003'): '6.1.02.002',  # Vale Transporte -> Despesa com Transporte
    ('financeiro_seeds', '5.1.01.004'): '6.1.01.002',  # Vale Alimentação -> Despesa com Alimentação
    ('financeiro_seeds', '5.1.02.001'): '6.1.02.003',  # Material de Construção
    ('financeiro_seeds', '5.1.02.002'): '6.1.02.003',  # Ferramentas
    ('financeiro_seeds', '5.1.02.003'): '6.1.02.003',  # EPIs
    ('financeiro_seeds', '5.1.03.001'): '6.1.02.003',  # Aluguel de Equipamentos
    ('financeiro_seeds', '5.1.03.002'): '6.1.02.003',  # Manutenção de Equipamentos
    ('financeiro_seeds', '5.1.04.001'): '6.1.02.001',  # Combustível
    ('financeiro_seeds', '5.1.04.002'): '6.1.02.001',  # Manutenção de Veículos
    ('financeiro_seeds', '5.1.04.003'): '6.1.02.001',  # IPVA e Licenciamento
    ('financeiro_seeds', '5.1.05.001'): '6.1.02.003',  # Material de Escritório
    ('financeiro_seeds', '5.1.05.002'): '6.1.02.003',  # Telefone e Internet
    ('financeiro_seeds', '5.1.05.003'): '6.1.02.003',  # Energia Elétrica
    ('financeiro_seeds', '5.1.05.004'): '6.1.02.003',  # Água e Esgoto
}

# Derivado, nunca escrito à mão: os códigos 5.x que este de-para conhece.
CONTAS_5X_CONHECIDAS: set = {codigo for (_ass, codigo) in DEPARA_5X}
