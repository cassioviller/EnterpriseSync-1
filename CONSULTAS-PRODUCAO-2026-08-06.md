# Pacote de consultas de PRODUÇÃO — 2026-08-06

> **Para o Cássio.** Nove consultas somente-leitura, para rodar de uma vez no banco de
> **produção**. Nenhuma escreve nada. Cada uma diz o que o resultado destrava e qual é o
> valor de referência em ⚠️ dev (`helium/heliumdb`) — que prova a forma, não o volume.
>
> Origem: F0.1 do `docs/superpowers/plans/2026-08-06-plano-execucao-b5.md`. As quatro
> primeiras são herdadas de Tasks anteriores; as cinco seguintes nasceram na rodada B5.
> Colar os resultados de volta na sessão fecha B2.13, decide o E02, destrava a B5.5 e
> dimensiona a B5.1/D-B5.1.

## Herdadas

```sql
-- [1] E02 / D11 — o gate que a B4.8 substituiu por contagem de dev (⚠️ dev: 0)
-- 0  ⇒ a decisão de 05/08 se confirma; a migração 279 vai dropar no boot com 'success'.
-- >0 ⇒ NÃO deployar sem plano: a migração aborta ('failed' a cada boot) e a exclusão de
--      RDO falha em silêncio → git revert ab626765 (roteiro no FECHO-SESSAO-2026-08-05.md).
SELECT count(*) FROM notificacao_cliente;

-- [2] B2.13 — invariante da folha (⚠️ expectativa fundamentada: 0 violações)
-- 0  ⇒ fecha a ÚLTIMA Task aberta do plano consolidado.
-- >0 ⇒ item novo com migração própria; a correção do histórico abre como item, não entra
--      em recorte existente.
SELECT count(*) FILTER (WHERE encargos_inss_patronal > 0) AS com_inss,
       count(*) FILTER (WHERE encargos_inss_patronal > 0
         AND ROUND(encargos_fgts + encargos_inss_patronal, 2)
          <> ROUND(custo_total_empresa - salario_bruto, 2)) AS violam
FROM folha_processada;

-- [3] B1.8 Step 2 (q7) — inventário do estrago já feito no ponto (⚠️ dev: sem pares)
-- Também decide se um índice único em (funcionario_id, data) passaria hoje.
WITH dups AS (
    SELECT admin_id, funcionario_id, data,
           count(*)                            AS registros,
           count(DISTINCT obra_id)             AS obras,
           sum(coalesce(horas_trabalhadas,0))  AS horas
    FROM registro_ponto
    GROUP BY admin_id, funcionario_id, data
    HAVING count(*) > 1
)
SELECT d.admin_id,
       count(*)         AS dias,
       sum(d.registros) AS registros,
       sum(d.horas)     AS horas_gravadas,
       sum(CASE WHEN d.obras > 1 THEN 1 ELSE 0 END) AS dias_multiobra,
       coalesce((SELECT sum(c.horas_trabalhadas)
                 FROM custo_obra c
                 WHERE c.admin_id = d.admin_id
                   AND c.categoria = 'PONTO_ELETRONICO'
                   AND (c.funcionario_id, c.data) IN (
                       SELECT dd.funcionario_id, dd.data
                       FROM dups dd WHERE dd.admin_id = d.admin_id)), 0) AS horas_custeadas
FROM dups d
GROUP BY d.admin_id
ORDER BY 2 DESC;

-- [4] E04 — AlocacaoEquipe.rdo_gerado_id (⚠️ dev 03/08: 33 linhas, 0 preenchidas)
-- Destrava a decisão de aposentadoria do E04 (adiada no plano consolidado §8.2).
-- Nota: o registro de "três pontos vivos" está errado — são DOIS; a B5.4 corrige.
SELECT count(*) AS linhas,
       count(*) FILTER (WHERE rdo_gerado_id IS NOT NULL) AS com_rdo
FROM alocacao_equipe;
```

## Da rodada B5

```sql
-- [5] B5.1 — o NameError atinge 100% das baixas de conta a pagar? (⚠️ dev: 0 de 627)
SELECT count(*) FILTER (WHERE conta_contabil_codigo IS NOT NULL) AS com_conta,
       count(*) AS total
FROM conta_pagar;

-- [6] B5.1 — alguém chegou a usar a URL de pagamento com fluxo de caixa? (⚠️ dev: 0)
SELECT count(*), min(data_movimento), max(data_movimento)
FROM fluxo_caixa WHERE referencia_tabela = 'conta_pagar';

-- [7] D-B5.1 — a sobreposição GestaoCustoPai × ContaPagar (⚠️ dev: 627/627 de COMPRA)
-- É o dado que sustenta (ou derruba) o default "GestaoCustoPai é a única fonte da SAÍDA".
SELECT origem_tipo, status, count(*) FROM conta_pagar GROUP BY 1, 2;

-- [8] B5.5 Step 1 — quantas obras teriam curva de baseline DIFERENTE da atual?
-- (⚠️ dev: 82 obras com divergência, e só 1 delas com RDO Finalizado, Δ máx 1,1 p.p.)
-- Se produção ≈ dev, a B5.5 NÃO se implementa — fecha como "medida e descartada".
SELECT count(DISTINCT b.obra_id)
FROM cronograma_baseline b
JOIN cronograma_baseline_item i ON i.baseline_id = b.id
JOIN tarefa_cronograma t ON t.id = i.tarefa_id
WHERE b.ativa
  AND (t.data_fim    IS DISTINCT FROM i.data_fim
    OR t.data_inicio IS DISTINCT FROM i.data_inicio);

-- [9] B5.5 Step 1 — e dessas, quantas têm curva calculável (RDO Finalizado)?
SELECT count(DISTINCT r.obra_id)
FROM rdo r
WHERE r.status = 'Finalizado'
  AND r.obra_id IN (
    SELECT DISTINCT b.obra_id
    FROM cronograma_baseline b
    JOIN cronograma_baseline_item i ON i.baseline_id = b.id
    JOIN tarefa_cronograma t ON t.id = i.tarefa_id
    WHERE b.ativa
      AND (t.data_fim    IS DISTINCT FROM i.data_fim
        OR t.data_inicio IS DISTINCT FROM i.data_inicio));
```

## O que cada resultado destrava

| # | Se vier igual a dev | Se vier diferente |
|---|---|---|
| 1 | deploy segue; migração 279 droppa | **segurar o deploy** e decidir com o roteiro do fecho |
| 2 | B2.13 fecha; plano consolidado 61/61 | item novo com migração própria |
| 3 | índice único passa; A10 sem estrago legado | dimensiona a perda em horas; correção de histórico vira item |
| 4 | E04 destravado para a aposentadoria | E04 continua adiado, com o número na mão |
| 5-6 | B5.1 confirmada como 100% das baixas; ninguém usou a URL | muda a severidade relatada, não a correção |
| 7 | default da D-B5.1 sustentado por produção | a D-B5.1 reabre com dado novo |
| 8-9 | **B5.5 não se implementa** | B5.5 destravada; seguem as D-B5.5a/b/c |
