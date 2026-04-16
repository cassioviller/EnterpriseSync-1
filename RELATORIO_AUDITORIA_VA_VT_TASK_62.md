# Relatório de Auditoria — Cartões de Alimentação (VA) e Transporte (VT)

Task: #62 — Consolidar VA e VT duplicados existentes
Data da auditoria: 2026-04-16
Banco auditado: ambiente de desenvolvimento (mesmo schema de produção)
Tenant ativo: `admin_id = 63`

## Resumo executivo

A auditoria nos cartões de **Gestão de Custos V2** para as categorias
`ALIMENTACAO` e `TRANSPORTE` foi concluída e **não foram encontrados grupos
duplicados em aberto** em nenhum dos três recortes verificados. A migração
115 (consolidação por `admin_id + entidade_id + categoria_normalizada`) e a
normalização aplicada em `utils/financeiro_integration.py` já eliminaram
todos os casos de duplicação previamente reportados na Task #60.

## Consulta 1 — Resumo por categoria

```sql
SELECT tipo_categoria,
       COUNT(*) AS total,
       SUM(CASE WHEN entidade_id IS NOT NULL THEN 1 ELSE 0 END) AS com_entidade_id,
       SUM(CASE WHEN entidade_id IS NULL     THEN 1 ELSE 0 END) AS sem_entidade_id,
       SUM(CASE WHEN status='PARCIAL'   THEN 1 ELSE 0 END) AS parcial,
       SUM(CASE WHEN status='PAGO'      THEN 1 ELSE 0 END) AS pago,
       SUM(CASE WHEN status='PENDENTE'  THEN 1 ELSE 0 END) AS pendente,
       SUM(CASE WHEN status='SOLICITADO'THEN 1 ELSE 0 END) AS solicitado
FROM gestao_custo_pai
WHERE tipo_categoria IN ('ALIMENTACAO','TRANSPORTE')
GROUP BY tipo_categoria
ORDER BY tipo_categoria;
```

Resultado real (saída SQL):

| tipo_categoria | total | com_entidade_id | sem_entidade_id | parcial | pago | pendente | solicitado |
|----------------|-------|-----------------|-----------------|---------|------|----------|------------|
| ALIMENTACAO    | 19    | 18              | 1               | 3       | 1    | 15       | 0          |
| TRANSPORTE     | 22    | 21              | 1               | 5       | 0    | 16       | 1          |

Conferência aritmética:
- ALIMENTACAO: 18 + 1 = 19 ✓ ; 3 + 1 + 15 + 0 = 19 ✓
- TRANSPORTE: 21 + 1 = 22 ✓ ; 5 + 0 + 16 + 1 = 22 ✓

## Consulta 2 — Verificação de duplicatas (em aberto)

Critério "em aberto": `status NOT IN ('PAGO','RECUSADO','PARCIAL')`
(idêntico ao usado pela Migration 115 para evitar mexer em cartões já
liquidados ou parcialmente pagos).

```sql
-- a) STRICT: (admin_id, tipo_categoria, entidade_id, entidade_nome)
-- b) BY_ENTIDADE_ID: (admin_id, tipo_categoria, entidade_id) — chave canônica
-- c) BY_NAME_NORM: (admin_id, tipo_categoria, LOWER(TRIM(entidade_nome)))
--    detecta variações de caixa/espaços em legados sem entidade_id
```

Resultado real (saída SQL):

| check          | dups |
|----------------|------|
| STRICT         | 0    |
| BY_ENTIDADE_ID | 0    |
| BY_NAME_NORM   | 0    |

**Zero duplicatas** em qualquer um dos três recortes — nada a consolidar.

## Consulta 3 — Listagem completa dos cartões inspecionados

```sql
SELECT id, admin_id, tipo_categoria, entidade_id, entidade_nome,
       status, valor_total,
       (SELECT COUNT(*) FROM gestao_custo_filho f WHERE f.pai_id = p.id) AS filhos
FROM gestao_custo_pai p
WHERE tipo_categoria IN ('ALIMENTACAO','TRANSPORTE')
ORDER BY tipo_categoria, admin_id, entidade_nome, id;
```

### ALIMENTACAO — 19 cartões

| id   | entidade_id | entidade_nome                       | status   | valor_total | filhos |
|------|-------------|-------------------------------------|----------|-------------|--------|
| 13   | (null)      | Alimentação                         | PAGO     | 50.00       | 1      |
| 1611 | 329         | CRISTIANO MATIAS DA SILVA           | PENDENTE | 1254.00     | 67     |
| 147  | 32          | Cantina da Obra                     | PARCIAL  | 1719.19     | 13     |
| 1626 | 317         | DAVI FERREIRA DA SILVA              | PENDENTE | 10.00       | 1      |
| 1655 | 341         | Danilo Vinicius Santos Vitório      | PENDENTE | 40.00       | 4      |
| 1635 | 318         | FABRICIO FERREIRA DA SILVA          | PENDENTE | 290.00      | 29     |
| 1653 | 340         | Josué Dias De Andrade               | PENDENTE | 40.00       | 4      |
| 1640 | 320         | LEONARDO OLIVEIRA SANTOS            | PENDENTE | 460.00      | 34     |
| 1617 | 321         | LUCAS HENRIQUE ALBERNAZ             | PENDENTE | 50.00       | 5      |
| 1649 | 322         | MARCOS VINICIUS BARBOSA CARDOSO     | PENDENTE | 250.00      | 25     |
| 1644 | 323         | MATHEUS ANTONIO BARBOSA DOS SANTOS  | PENDENTE | 420.00      | 30     |
| 146  | 33          | Marmitaria Central                  | PARCIAL  | 1386.73     | 10     |
| 1637 | 324         | PAULO CESAR BITENCOURT DE SOUSA     | PENDENTE | 90.00       | 9      |
| 1632 | 325         | PEDRO EDNEI BATISTA PEREIRA         | PENDENTE | 30.00       | 3      |
| 1620 | 326         | ROGER ARMANDO SEQUERA RIVAS         | PENDENTE | 485.00      | 27     |
| 1646 | 339         | Renan Andler Araújo Simeão          | PENDENTE | 50.00       | 5      |
| 145  | 34          | Restaurante Bom Sabor               | PARCIAL  | 1403.48     | 10     |
| 1629 | 327         | VINÍCIUS OLIVEIRA COSTA ROMANO      | PENDENTE | 490.00      | 37     |
| 1623 | 328         | VITOR HUGO BRAGA                    | PENDENTE | 340.00      | 34     |

Quebra por origem (soma = 19):
- **15 funcionários** (status PENDENTE, com `entidade_id`): ids 1611, 1617,
  1620, 1623, 1626, 1629, 1632, 1635, 1637, 1640, 1644, 1646, 1649, 1653,
  1655.
- **3 fornecedores legados** (status PARCIAL, intocáveis pela Migration 115):
  Cantina da Obra (147), Marmitaria Central (146), Restaurante Bom Sabor (145).
- **1 cartão legado sem `entidade_id`** (status PAGO, intocável): "Alimentação" (13).
- Total: 15 + 3 + 1 = **19** ✓

### TRANSPORTE — 22 cartões

| id   | entidade_id | entidade_nome                       | status     | valor_total | filhos |
|------|-------------|-------------------------------------|------------|-------------|--------|
| 141  | 299         | Ana Silva V2                        | PARCIAL    | 562.89      | 25     |
| 1612 | 329         | CRISTIANO MATIAS DA SILVA           | PENDENTE   | 990.00      | 67     |
| 144  | 300         | Carlos Souza V2                     | PARCIAL    | 346.84      | 22     |
| 1625 | 317         | DAVI FERREIRA DA SILVA              | PENDENTE   | 425.00      | 34     |
| 1656 | 341         | Danilo Vinicius Santos Vitório      | SOLICITADO | 65.00       | 5      |
| 1614 | 338         | Ednilson Bernardo Da Silva          | PENDENTE   | 840.50      | 41     |
| 1634 | 318         | FABRICIO FERREIRA DA SILVA          | PENDENTE   | 165.50      | 14     |
| 140  | 304         | Joana Lima V2                       | PARCIAL    | 262.51      | 22     |
| 1652 | 340         | Josué Dias De Andrade               | PENDENTE   | 338.00      | 26     |
| 1641 | 320         | LEONARDO OLIVEIRA SANTOS            | PENDENTE   | 104.00      | 8      |
| 1616 | 321         | LUCAS HENRIQUE ALBERNAZ             | PENDENTE   | 604.80      | 49     |
| 1650 | 322         | MARCOS VINICIUS BARBOSA CARDOSO     | PENDENTE   | 390.00      | 30     |
| 1643 | 323         | MATHEUS ANTONIO BARBOSA DOS SANTOS  | PENDENTE   | 468.00      | 36     |
| 143  | 301         | Maria Oliveira V2                   | PARCIAL    | 341.30      | 22     |
| 1638 | 324         | PAULO CESAR BITENCOURT DE SOUSA     | PENDENTE   | 585.00      | 45     |
| 1631 | 325         | PEDRO EDNEI BATISTA PEREIRA         | PENDENTE   | 815.00      | 64     |
| 142  | 303         | Pedro Costa V2                      | PARCIAL    | 270.14      | 22     |
| 1619 | 326         | ROGER ARMANDO SEQUERA RIVAS         | PENDENTE   | 442.00      | 35     |
| 1647 | 339         | Renan Andler Araújo Simeão          | PENDENTE   | 13.00       | 1      |
| 2    | (null)      | Transporte Geral                    | PENDENTE   | 2825.00     | 3      |
| 1628 | 327         | VINÍCIUS OLIVEIRA COSTA ROMANO      | PENDENTE   | 225.50      | 19     |
| 1622 | 328         | VITOR HUGO BRAGA                    | PENDENTE   | 254.50      | 21     |

Quebra por origem (soma = 22):
- **16 funcionários** (status PENDENTE/SOLICITADO, com `entidade_id`): ids
  1612, 1614, 1616, 1619, 1622, 1625, 1628, 1631, 1634, 1638, 1641, 1643,
  1647, 1650, 1652, 1656.
- **5 funcionários legados V2** (status PARCIAL, intocáveis): Ana Silva V2
  (141), Carlos Souza V2 (144), Joana Lima V2 (140), Maria Oliveira V2
  (143), Pedro Costa V2 (142).
- **1 cartão legado sem `entidade_id`** (status PENDENTE, único pelo
  fallback de `entidade_nome`): "Transporte Geral" (2).
- Total: 16 + 5 + 1 = **22** ✓

## Conclusão

- **Nada a consolidar** em ALIMENTACAO ou TRANSPORTE.
- A combinação Migration 115 + normalização em
  `registrar_custo_automatico` (Task #60) cobriu todo o backlog identificado.
- Novos lançamentos (Importação, V2 manual, módulos operacionais) seguirão
  caindo no cartão único de cada (admin, categoria, entidade) graças ao
  filtro por `entidade_id` e à lista `categorias_equivalentes` em
  `utils/financeiro_integration.py`.
- Os cartões com status `PARCIAL`/`PAGO` permanecem isolados por design da
  Migration 115 (não são tocados para preservar histórico de pagamentos).

## Como reauditar a qualquer momento

Basta executar as três SQLs deste relatório. Enquanto a "Verificação de
duplicatas" continuar retornando zero em todos os recortes, o agrupamento
ponta-a-ponta segue íntegro. A Migration 115 é idempotente e pode ser
reaplicada sem efeitos colaterais.
