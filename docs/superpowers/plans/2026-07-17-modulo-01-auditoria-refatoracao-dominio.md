# Módulo 1 — Auditoria e Refatoração de Domínio

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`. Sem API externa; tudo determinístico.

## 1. Objetivo

Separar responsabilidades hoje entrelaçadas no importador físico-financeiro e nas views de cronograma/RDO, extraindo serviços genéricos reutilizáveis, para que os módulos 2–9 construam sobre fronteiras limpas — sem alterar comportamento observável (suíte `--gate` permanece verde).

## 2. Estado atual encontrado no código

- `services/importacao_fisico_financeiro.py` (762 linhas) faz 6 coisas num único fluxo (`importar_fisico_financeiro`, `:552`): resolve cliente/obra, cria orçamento/proposta, emite `proposta_aprovada` via `EventManager`, materializa cronograma (`_materializar_cronograma_mpp`, `:182`), materializa custos por etapa, cria medições de contrato, materializa RDOs+fotos (`_materializar_rdos`, `:423`). A limpeza `_limpar_derivados` (`:141`) mistura derivados comerciais e cronograma.
- Lógica de apontamento duplicada: `views/rdo.py:4556-4609` × `cronograma_views.py:1134-1217` (mesma fórmula acumulado+incremento→percentual). Rollup de pais triplicado: `utils/cronograma_engine.py:216-229` e `:335-344` (persistido) × `cronograma_views.py:913-934` (on-the-fly).
- Três handlers de gravação de RDO: `views/rdo.py:salvar_rdo_flexivel` (`:3851`, principal), `views/rdo.py:rdo_salvar_unificado` (`:2513`, legado, log `[LEGACY-RDO]`) e `crud_rdo_completo.py:salvar_rdo` (`:232`, legado) — os dois últimos colidem na URL `/rdo/salvar` (resolução depende da ordem de registro de blueprints em `app.py`/`main.py`).
- Progresso geral calculado por ≥5 caminhos (ver master plan §1.2).
- Especificidades das baias vivem em scripts e arquivos de dados, não no schema: `scripts/rebuild_baia_from_0607_mpp.py` (classificador `etapa_de()` `:19-39`, `FERRAGENS_KEY` `:42`, `REMAP` `:92`, caminhos absolutos `:11-13`), `scripts/seed_*baias.py`, JSONs na raiz, `fotos_rdos/`. Comentários de spec-baia dentro do serviço genérico (`services/importacao_fisico_financeiro.py:255` e `:427`).
- `decorators.py:11,19`: `admin_required`/`login_required` com bypass total ("Durante desenvolvimento").
- Funções excessivamente grandes: `importar_fisico_financeiro` (~210 linhas), `salvar_rdo_flexivel` (~750 linhas), `tarefas_rdo` (~100 linhas com cálculo embutido), `cronograma_obra` (`cronograma_views.py:166`).

## 3. Problemas atuais

1. Importação inicial e atualização de cronograma são o mesmo código destrutivo — impossível atualizar cronograma sem apagar RDOs.
2. Duplicação de fórmulas ⇒ risco de drift (o comentário em `cronograma_views.py:914` já admite cópia).
3. Colisão de rota `/rdo/salvar` ⇒ comportamento dependente de ordem de import.
4. Sem fronteira de serviço para "cronograma": views fazem query + cálculo + persistência.
5. Autorização desligada nos decorators.

## 4. Escopo

- Inventário formal (documento gerado durante execução) de todos os pontos que tocam `TarefaCronograma`, `RDOApontamentoCronograma`, `RDOServicoSubatividade` (grep versionado no doc de execução).
- Extração, sem mudança de comportamento, de:
  - `services/cronograma_apontamento_service.py` — função única `registrar_apontamento(tarefa, rdo, valor, tipo)` usada por `views/rdo.py` e `cronograma_views.py` (elimina duplicação §3.2).
  - `services/importacao_fisico_financeiro.py` reorganizado internamente em blocos nomeados: `_importar_comercial(...)`, `_importar_cronograma(...)`, `_importar_custos(...)`, `_importar_medicoes(...)`, `_importar_rdos(...)` — mesmas chamadas, mesma ordem, mesma transação (preparação para o Módulo 5 reusar `_importar_cronograma` isoladamente NÃO acontece aqui; aqui é só organização).
- Resolução da colisão `/rdo/salvar`: verificado em runtime que `main.rdo_salvar_unificado` sempre vence (ordem de registro de blueprint, regras estáticas de mesmos métodos). A perdedora `rdo_crud.salvar_rdo` é inalcançável por construção, portanto NÃO pode redirecionar nem devolver 410 — qualquer resposta dela exigiria criar uma URL nova. Correção: remover o registro de rota da perdedora (função preservada para o rollout do Módulo 07). Ver `2026-07-20-modulo-01-passo-5-colisao-rota-rdo-salvar.md`.
- Definição documentada da separação de casos de uso: criação inicial de obra completa | importação/substituição de cronograma | importação de RDO | atualização de custos | atualização de medições (tabela de responsabilidade por serviço).
- Reativar autorização real em `decorators.py` **apenas** para as rotas novas dos módulos 3/5/8 (decorator novo `cronograma_import_required`), sem tocar o comportamento das rotas existentes (mudar o bypass global é fora de escopo — risco amplo).

## 5. Fora de escopo

- Qualquer mudança de schema (Módulo 2).
- Unificação dos caminhos de progresso B/C/D/E (Módulo 6).
- Remoção dos handlers legados de RDO (apenas resolver a colisão; remoção fica para depois do rollout).
- Refatorar `salvar_rdo_flexivel` por inteiro (Módulo 7 altera pontos cirúrgicos).

## 6. Arquivos atuais envolvidos

- `services/importacao_fisico_financeiro.py`
- `views/rdo.py`, `cronograma_views.py`, `crud_rdo_completo.py`, `rdo_editar_sistema.py`
- `utils/cronograma_engine.py`
- `decorators.py`, `app.py`, `main.py` (ordem de registro de blueprints)
- `scripts/rebuild_baia_from_0607_mpp.py`, `scripts/seed_*baias.py` (somente inventariados)

## 7. Arquivos novos ou alterados previstos

- Novo: `services/cronograma_apontamento_service.py`.
- Novo: `docs/superpowers/specs/2026-07-XX-separacao-casos-de-uso-importacao.md` (tabela de responsabilidades, gerada na execução).
- Alterados: `services/importacao_fisico_financeiro.py` (reorganização interna), `views/rdo.py` e `cronograma_views.py` (delegam ao serviço de apontamento), `crud_rdo_completo.py` ou `views/rdo.py` (colisão de rota), `decorators.py` (novo decorator, sem tocar os existentes).

## 8. Alterações de banco

Nenhuma.

## 9. Serviços e responsabilidades (alvo)

| Serviço | Responsabilidade única |
|---|---|
| `services/importacao_fisico_financeiro.py` | Criação inicial de obra completa a partir do JSON canônico (fluxo baias) — congelado |
| `services/cronograma_apontamento_service.py` | Registrar apontamento (quantitativo/percentual) com acumulado correto |
| `utils/cronograma_engine.py` | Cálculo puro de datas/planejado/realizado/rollup (permanece; consolidado no M6) |
| (futuros, módulos 3-5) | `mpp_parser`, `cronograma_normalizacao`, `cronograma_reconciliacao`, `cronograma_versao_service` |

## 10. Rotas e contratos de API

Sem rotas novas. Contrato interno novo:

```python
# services/cronograma_apontamento_service.py
def registrar_apontamento(rdo, tarefa, *, quantidade_dia=None, percentual_acumulado=None,
                          admin_id) -> RDOApontamentoCronograma:
    """Exatamente a semântica atual de views/rdo.py:4556-4609.
    quantidade_dia XOR percentual_acumulado. Sem commit (caller comita)."""
```

## 11. Fluxo de frontend

Nenhuma mudança visível.

## 12. Regras de negócio

Invariantes a preservar (extraídas dos testes): idempotência do import por `(codigo, admin_id)`; INDIRETOS não vira tarefa; RDOs do import sem mão de obra; incremento = diferença de acumulados; fallback percentual sem `quantidade_total`.

## 13. Estratégia de migração

Refatoração pura; deploy normal; nenhum dado tocado.

## 14. Compatibilidade

- Suíte `tests/` `--gate` inteira verde antes/depois de cada extração (rodar por commit).
- Nenhuma URL muda de comportamento exceto a colisão `/rdo/salvar`, que hoje já é indefinida — o teste novo fixa o vencedor atual.

## 15. Segurança

Novo decorator exige usuário autenticado + `admin_id` resolvido via `utils/tenant.get_tenant_admin_id` (não o bypass de `decorators.py`).

## 16. Observabilidade

Log estruturado no serviço de apontamento (tarefa, rdo, tipo, valores antes/depois) — substitui prints dispersos.

## 17. Testes

- Teste de caracterização ANTES de extrair: gravar apontamento quantitativo e percentual pelos dois caminhos atuais e congelar o estado resultante (valores de `quantidade_acumulada`, `percentual_realizado`, `percentual_planejado`).
- Teste da colisão de rota: assert de qual handler atende `/rdo/salvar` hoje; depois assert do redirect do perdedor.
- `run_tests.sh --gate` completo.

## 18. Critérios de aceite

1. Zero mudança de comportamento (suíte verde, caracterização idêntica).
2. `views/rdo.py` e `cronograma_views.py` não contêm mais a fórmula duplicada de acumulado.
3. Documento de separação de casos de uso escrito e revisado.
4. Colisão `/rdo/salvar` determinística e testada.

## 19. Riscos

- Extração alterar sutilmente arredondamento (`round(...,2)` vs `min(100.0, ...)` — copiar literalmente; teste de caracterização pega).
- Ordem de registro de blueprints variar entre dev e prod (main.py registra extras) — o teste roda contra o app real.

## 20. Dependências

Nenhuma (primeiro módulo).

## 21. Ordem detalhada de implementação

1. Escrever testes de caracterização dos dois caminhos de apontamento; rodar, verde.
2. Criar `services/cronograma_apontamento_service.py` copiando a lógica de `views/rdo.py:4556-4609` literalmente; testes unitários do serviço.
3. Trocar `views/rdo.py` para delegar; suíte verde; commit.
4. Trocar `cronograma_views.py:apontar_producao` para delegar; suíte verde; commit.
5. Teste da colisão `/rdo/salvar`; implementar redirect no perdedor; commit.
6. Reorganizar `importar_fisico_financeiro` em blocos nomeados (sem mudar ordem/transação); suíte verde; commit.
7. Novo decorator; teste; commit.
8. Escrever o doc de separação de casos de uso; commit.

## 22. Checklist de conclusão

- [x] Caracterização congelada e verde (`3d94224`)
- [x] Serviço de apontamento único em uso pelos dois callers (`c58b98e`, `d60e107`)
- [x] Colisão de rota resolvida e testada (2026-07-20; `tests/test_rota_rdo_salvar_unica.py`)
- [x] Importador reorganizado sem mudança de comportamento (`6782960`)
- [ ] Decorator de autorização novo pronto para M3/M5/M8
- [ ] Doc de casos de uso publicado
- [ ] `run_tests.sh --gate` verde
