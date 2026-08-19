"""A numeração das migrações — 2026-08-19.

🔬 O CASO REAL. Entre 13 e 19/08 duas linhagens deste repositório andaram em
paralelo, e as duas alocaram o número **287**: aqui ele era
`nota_e_adiantamento` (duas tabelas novas da Fase 2), na outra era
`alcadas_avancadas` (dez colunas em `requisicao_compra`). Os dois docstrings
trazem a mesma justificativa — *"conferido em `migration_history` do dev"* —,
um de 14/08 e outro de 16/08: **duas pessoas lendo o mesmo banco de
desenvolvimento em dias diferentes escolhem o mesmo número livre.**

📖 O runner pula por NÚMERO (`executed_cache`), não por nome. Num banco que já
tivesse rodado a outra linhagem, o 287 constaria como `success` e a migração
deste lado **nunca rodaria** — e o sintoma não é no boot, é no primeiro uso, com
`relation does not exist`.

Este arquivo lê `migrations.py` por AST, sem importar nada e sem tocar em banco.
Três invariantes, e cada uma pega um erro diferente:

  1. **número repetido** — a segunda ocorrência seria pulada em silêncio;
  2. **fora de ordem** — a lista é a ordem de execução; número menor depois de
     maior esconde dependência mal declarada e atrapalha quem lê;
  3. **número da tupla ≠ número no nome da função** — foi o erro possível ao
     renumerar a 287: trocar a tupla e esquecer o `def`, ou o contrário. Aí o
     histórico grava um número e o código executa outro.

E a quarta, que não é de numeração mas mora no mesmo lugar: 📖
`migration_history.migration_name` é `VARCHAR(200)` e 📖 `record_migration`
**engole a exceção** — descrição mais longa faz a migração rodar, não ficar
registrada, e voltar a rodar a cada boot. Já aconteceu com a 310.
"""
import ast
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITE_MIGRATION_NAME = 200


def _entradas_do_runner():
    """(numero, descricao, nome_da_funcao) de cada migração declarada.

    Por AST e não por regex: a lista tem strings com parênteses e vírgulas
    dentro, e regex sobre isso erra em silêncio — que é justamente o modo de
    falha que este arquivo existe para impedir.
    """
    with open(os.path.join(RAIZ, 'migrations.py'), encoding='utf-8') as fh:
        arvore = ast.parse(fh.read())

    entradas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Tuple) or len(no.elts) != 3:
            continue
        num, desc, func = no.elts
        if not (isinstance(num, ast.Constant) and isinstance(num.value, int)):
            continue
        if not (isinstance(desc, ast.Constant) and isinstance(desc.value, str)):
            continue
        if not isinstance(func, ast.Name):
            continue
        if not re.match(r'_?migration_\d+', func.id):
            continue
        entradas.append((num.value, desc.value, func.id))
    return entradas


def test_o_runner_foi_encontrado():
    """Se a forma da lista mudar, os outros testes passariam medindo o vazio."""
    entradas = _entradas_do_runner()
    assert len(entradas) > 100, \
        f'só {len(entradas)} migrações encontradas — a lista mudou de forma?'


def test_nenhum_numero_se_repete():
    """O defeito de 19/08. Número repetido = a segunda é pulada em silêncio."""
    numeros = [n for n, _, _ in _entradas_do_runner()]
    repetidos = sorted({n for n in numeros if numeros.count(n) > 1})
    assert not repetidos, (
        f'número(s) de migração repetido(s): {repetidos}. O runner pula por '
        f'NÚMERO: a segunda nunca roda, e o sintoma aparece no primeiro uso, '
        f'não no boot.')


def test_a_ordem_da_lista_e_crescente():
    numeros = [n for n, _, _ in _entradas_do_runner()]
    fora = [(a, b) for a, b in zip(numeros, numeros[1:]) if b < a]
    assert not fora, (
        f'a lista é a ordem de execução e está fora de ordem em: {fora}')


def test_o_numero_da_tupla_bate_com_o_nome_da_funcao():
    """Ao renumerar, trocar a tupla e esquecer o `def` (ou o contrário) faz o
    histórico gravar um número e o código executar outro."""
    divergentes = []
    for numero, _, nome in _entradas_do_runner():
        no_nome = int(re.search(r'(\d+)', nome).group(1))
        if no_nome != numero:
            divergentes.append((numero, nome))
    assert not divergentes, \
        f'tupla e nome de função discordam do número: {divergentes}'


def test_nenhuma_descricao_estoura_o_limite_da_coluna():
    """📖 `migration_history.migration_name` é VARCHAR(200) e
    `record_migration` engole a exceção: a migração roda, não fica registrada, e
    volta a rodar a cada boot. Aconteceu com a 310."""
    longas = [(n, len(d)) for n, d, _ in _entradas_do_runner()
              if len(d) > LIMITE_MIGRATION_NAME]
    assert not longas, (
        f'descrição maior que VARCHAR({LIMITE_MIGRATION_NAME}) em {longas} — '
        f'o INSERT do histórico falha em silêncio e a migração re-roda sempre.')
