# [Refactor A] Eliminar cache de instância ORM (bug de worker longevo)

> Bloco A do plano `docs/superpowers/plans/2026-06-08-remediacao-saude-app-plan.md`. Prioridade P1 — baixo risco, alto retorno.

## Problem Statement

Vários getters cacheiam instâncias SQLAlchemy num cache de processo. Em worker
longevo (gunicorn), a instância cacheada fica *detached* após o teardown da
sessão e, no request seguinte, o acesso aos atributos lança
`DetachedInstanceError`. O efeito é intermitente e invisível: a folha, por
exemplo, deixava de gerar lançamento contábil até o worker reiniciar. Um caso
(`_obter_parametros_legais`) já foi corrigido; restam pelo menos dois getters
com o mesmo padrão, mais uma auditoria geral.

## Solution

Padronizar "cachear **valores**, nunca entidades". Cada getter cacheado passa a
retornar um value-object imutável (namedtuple/dataclass) com os campos usados,
ou faz consulta direta quando o ganho do cache não justifica o risco. A
invalidação ao editar continua funcionando.

## Commits

1. Teste RED de regressão: invocar o getter de parâmetros legais em dois
   contextos de aplicação distintos (simulando dois requests) e acessar um
   atributo no segundo — hoje quebra para os getters ainda não corrigidos.
2. Converter o getter cacheado de parâmetros legais para retornar um
   value-object imutável (ou consulta direta); manter a função de invalidação.
3. Converter o getter cacheado de contas do plano de contas do mesmo modo;
   ajustar todos os consumidores (lançamentos, folha, handlers contábeis).
4. Auditoria: localizar todo `@lru_cache` e todo cache de módulo que retorne
   entidade; corrigir os remanescentes seguindo o mesmo padrão.
5. Garantir que a edição de parâmetros/contas invalide o caminho de cache certo
   (teste cobrindo "editar → próximo cálculo enxerga o novo valor").
6. Verde: suíte de folha/contabilidade + all-modules sem regressão.

## Decision Document

- Padrão único do projeto: caches retornam valores imutáveis, não objetos ORM.
- Caches por-request (escopo de aplicação) são preferidos para dados de tenant;
  caches de processo só para valores derivados sem sessão.
- A interface pública dos getters de parâmetros e de contas pode mudar do
  retorno "instância" para "value-object"; os consumidores acessam os mesmos
  campos por nome.

## Testing Decisions

- Bom teste aqui exercita **comportamento externo**: "chamar duas vezes em
  contextos diferentes retorna dados válidos e iguais", não o mecanismo de
  cache em si.
- Módulos testados: serviço de folha (parâmetros legais) e o helper de contas
  contábeis.
- Prior art: testes de serviço que abrem `app.app_context()` e fazem rollback,
  como na suíte de orçamento.

## Out of Scope

- Trocar a estratégia de cache por uma lib externa (Redis etc.).
- Otimizações de performance não relacionadas ao bug de detachment.

## Further Notes

A correção de `_obter_parametros_legais` (serviço de folha) já está em `main` e
serve de referência de padrão.
