"""
Configuração global do pytest.

Alguns arquivos em tests/ são scripts standalone — funções com assinaturas
não-pytest (ex.: `def teste_xx(falhas: list[str])`) ou fixtures inexistentes
(`admin`, `proposta`, `obra`, `cliente`) usadas como parâmetros posicionais.
Esses arquivos rodam direto via `python tests/<arquivo>.py` e devem ser
ignorados pela coleta do pytest.
"""
collect_ignore_glob = [
    "test_insumo_coeficiente_padrao.py",
    "test_orcamento_formato_br.py",
    "test_task_45_catalogo_eventos.py",
]
