# Módulo 4 — Normalização e Classificação Determinística (substitui a integração com API externa)

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`. **Decisão D1: sem API externa.** Este módulo entrega, por lógica determinística + revisão manual, o que a spec original delegava ao Claude: normalizar nomes, gerar fingerprints, classificar, sugerir vínculos e apontar inconsistências. O ponto de extensão futuro opcional está no master plan §9.

## 1. Objetivo

Transformar o JSON bruto do parser (M3) em um JSON normalizado, validado por JSON Schema versionado, com nomes canônicos, fingerprints determinísticos, classificação por regras e avisos de inconsistência — insumo direto da reconciliação (M5).

## 2. Estado atual encontrado no código

- Normalização existente é ad-hoc e específica das baias: `scripts/rebuild_baia_from_0607_mpp.py::na()` (NFKD sem acentos) e `etapa_de()` (`:19-39`, classificador por palavra-chave com ordem significativa, códigos HIDRO/ELET/PRELIM/…/FUND, `'??'` para não classificado, `None` para físico-puro).
- `services/importacao_fisico_financeiro.py::_materializar_cronograma_mpp` (`:182`) consome o JSON já normalizado do arquivo canônico; hierarquia por `nivel` (outline+1), sem validação de schema.
- Nenhuma validação de JSON Schema no projeto para esse fluxo (`importacao_views.py:1039` faz `json.load` cru).
- Matching por nome já é praticado em produção: portal casa cronograma-cliente↔interno por string exata de nome (`portal_obras_views.py:126-137`).

## 3. Problemas atuais

1. Regras de normalização/classificação presas num script de uma obra.
2. Sem schema: payload malformado só explode dentro do serviço.
3. Sem fingerprint estável: impossível reconhecer a "mesma" tarefa entre versões sem UID.

## 4. Escopo

Novo `services/cronograma_normalizacao.py` (funções puras, sem I/O, sem DB):

- `normalizar_nome(nome: str) -> str`: NFKD sem acento, uppercase→casefold, colapso de espaços, remoção de pontuação/sufixos numéricos de duplicata (` (1)`), preservando dígitos significativos ("BAIA 01"). Determinística e testada por tabela de casos.
- `caminho_hierarquico(tarefa, tarefas) -> str`: "raiz/…/pai/nome" com nomes normalizados (usa outline/parent do JSON bruto).
- `fingerprint(tarefa) -> str`: SHA-256 hex truncado (16) de campos estáveis `nome_normalizado|caminho_pai_normalizado|dias|unidade|quantidade` — **sem datas** (mudam entre versões por replanejamento) e **sem id** (instável por definição). Documentar a fórmula no docstring; mudar a fórmula ⇒ bump de `normalizador_versao`.
- `classificar(tarefa) -> dict`: `{is_resumo, is_marco, is_transversal, categoria_sugerida}` — `is_resumo`/`is_marco` vêm do parser; `categoria_sugerida` por tabela de regras genérica (extraída e generalizada de `etapa_de()`: dicionário palavra-chave→categoria, configurável por dados, não hardcoded por obra; sem match ⇒ `null` — nunca inventa).
- `detectar_inconsistencias(tarefas) -> list[Aviso]`: datas fim<início; folha sem datas; duração 0 sem marco; predecessora inexistente; ciclo de predecessoras; outline saltando níveis; nomes duplicados no mesmo pai (gera aviso `ambiguidade_potencial`); quantidade sem unidade e vice-versa; pct_project>0 (avisa que será ignorado se a obra tiver RDO).
- `normalizar(json_bruto: dict) -> dict`: pipeline completo → JSON normalizado; valida ENTRADA e SAÍDA com `jsonschema` (dependência nova leve) contra schemas versionados.
- Sanitização: strings truncadas aos limites de coluna; controle chars removidos; notas limitadas (ex. 2000 chars). Como não há LLM, "prompt injection em nomes/notas" deixa de ser vetor; ainda assim nomes são tratados como texto puro (escape no template — M8).

Schemas novos versionados em `services/schemas/cronograma_bruto.schema.json` e `services/schemas/cronograma_normalizado.schema.json` (campo `versao` no topo; `normalizador_versao` gravado na importação — M2).

JSON normalizado (contrato para M5):
```json
{"versao": "1.0", "tarefas": [{
  "chave": "uid:132" ,            // ordem de preferência: uid → wbs → fingerprint
  "uid": 132, "wbs": "1.3.2", "id_arquivo": 15,
  "nome_original": "Ferragens p/ fundação", "nome_normalizado": "FERRAGENS P FUNDACAO",
  "caminho": "OBRA/FUNDACAO/FERRAGENS P FUNDACAO", "fingerprint": "a3f9...",
  "nivel": 3, "pai_chave": "uid:130", "ordem": 15,
  "inicio": "2026-07-01", "fim": "2026-07-08", "dias": 6.0,
  "is_resumo": false, "is_marco": false, "categoria_sugerida": "FUND",
  "predecessoras": [{"chave": "uid:130", "tipo": "FS", "lag_dias": 0}],
  "quantidade_total": 48.0, "unidade": "un", "pct_project": 100.0,
  "notas": null}],
 "avisos": [{"codigo": "sem_datas", "tarefa_chave": "uid:200", "mensagem": "..."}]}
```

## 5. Fora de escopo

Comparação com o cronograma atual (M5); persistência (o chamador grava `json_normalizado` na importação); UI; qualquer sugestão não determinística.

## 6. Arquivos atuais envolvidos

`scripts/rebuild_baia_from_0607_mpp.py` (fonte das regras a generalizar — não alterado aqui; descontinuação no M9), `services/importacao_fisico_financeiro.py` (referência de convenções `nivel`).

## 7. Arquivos novos ou alterados previstos

Novos: `services/cronograma_normalizacao.py`, `services/schemas/cronograma_bruto.schema.json`, `services/schemas/cronograma_normalizado.schema.json`, `tests/test_cronograma_normalizacao.py`. Alterado: `pyproject.toml` (+`jsonschema`).

## 8. Alterações de banco

Nenhuma.

## 9. Serviços e responsabilidades

Módulo puro: entrada dict, saída dict, exceção tipada `NormalizacaoError` (payload inválido contra schema). Chamado pela view do M3 após parse; resultado gravado em `cronograma_importacao.json_normalizado`, status `normalizado`, evento registrado.

## 10. Rotas e contratos de API

Nenhuma rota; contratos = schemas §4.

## 11. Fluxo de frontend

Nenhum (avisos aparecem na prévia — M8).

## 12. Regras de negócio

- `chave` da tarefa: `uid:<n>` se uid existe; senão `wbs:<código>`; senão `fp:<fingerprint>` — a mesma regra é usada pelo M5 na reconciliação.
- Nunca inventar dados: campo ausente permanece null; tarefa sem datas entra com aviso, não com data de hoje.
- Determinismo bit-a-bit: mesma entrada ⇒ mesma saída (testado por dupla execução + comparação).

## 13. Estratégia de migração

Nenhum dado migrado. Tabela de categorias inicial (dados, não código) parte das palavras-chave de `etapa_de()` generalizadas — sem casos "FAZENDA/AJR" específicos das baias (esses ficam mapeados manualmente no M9).

## 14. Compatibilidade

Nada existente chama este módulo ainda; o formato aceita também o JSON de contingência do CLI (mesmo schema bruto).

## 15. Segurança

Validação estrita de tipos/limites via schema; strings tratadas como dados (sem eval/format dinâmico); tamanho máximo do payload herdado do limite de upload (M3).

## 16. Observabilidade

Retorno inclui contadores (n_tarefas, n_folhas, n_avisos por código) gravados no evento `normalizado`.

## 17. Testes

- Tabela de casos de `normalizar_nome` (acentos, caixa, espaços, sufixos, dígitos significativos).
- Fingerprint: estável entre execuções; insensível a datas; sensível a nome/pai/duração/quantidade.
- `detectar_inconsistencias`: um caso por código de aviso.
- Pipeline: json bruto real do `CRONOGRAMA 06.07.mpp` (gerado no M3) → normalizado válido pelo schema, 101 tarefas, zero perda.
- Schema: payloads inválidos (tipo errado, campo faltando) → `NormalizacaoError`.
- Propriedade: `normalizar(normalizar(x)_reserializado)` estável (idempotência do normalizador de nomes).

## 18. Critérios de aceite

1. JSON bruto das baias normaliza sem avisos inesperados e valida contra o schema.
2. Duas execuções = saída idêntica (determinismo).
3. Nenhuma rede/DB tocada pelo módulo (import lint: módulo não importa `models`/`db`/`requests`).

## 19. Riscos

- Regras de nome agressivas demais colapsarem tarefas distintas ⇒ fingerprint colide → aviso `ambiguidade_potencial` + resolução manual no M5 (nunca merge silencioso).
- Tabela de categorias genérica insuficiente para outras obras → categoria null é aceitável (campo sugestivo, não obrigatório).

## 20. Dependências

M3 (formato do JSON bruto). Sem dependência de M2.

## 21. Ordem detalhada de implementação

1. Schemas (bruto/normalizado) + testes de validação. 2. `normalizar_nome` + tabela de casos (TDD). 3. `caminho_hierarquico` + `fingerprint` + testes de estabilidade. 4. `classificar` + tabela de categorias. 5. `detectar_inconsistencias` (um teste por aviso). 6. `normalizar()` integrando tudo + teste com fixture real. 7. Integração na view do M3 (status/evento). Commits por passo.

## 22. Checklist de conclusão

- [ ] Schemas versionados no repo
- [ ] Funções puras 100% cobertas por testes
- [ ] Fixture real (101 tarefas) normaliza limpa
- [ ] Determinismo provado
- [ ] Sem I/O no módulo
