# Plano de implementação — Importação de obra com coeficientes SINAPI

> Spec: `docs/superpowers/specs/2026-06-11-importacao-obra-coeficientes-sinapi-design.md`
> Obra-piloto: Baia REV10 (Kabod Cabana — Fazenda Santa Mônica, Itu/SP)

Dois fluxos: **Parte A** = importador de Composições (código no sistema, commits pequenos); **Parte B** = converter a obra (dados, item a item). A Parte A é pré-requisito do Passo B2.

---

## PARTE A — Importador de Composições (feature)

### A1. Função núcleo + testes
Arquivo: `services/catalogo_excel.py` — `importar_composicoes_xlsx(arquivo, admin_id) -> dict`, espelhando `importar_insumos_xlsx` (`:300`).

- Ler aba "Composicoes" (ou 1ª), cabeçalho na linha 1.
- Colunas: `servico_nome`, `servico_unidade`, `categoria?`, `insumo_nome`, `coeficiente`, `unidade_insumo?`, `observacao?`.
- Por linha: upsert `Servico` por `(admin_id, lower(servico_nome))`; resolver `Insumo` por `(admin_id, lower(insumo_nome))` → rejeita se não existe; upsert `ComposicaoServico` por UNIQUE `(servico_id, insumo_id)`; ao mudar coeficiente, gravar `ComposicaoServicoHistorico`.
- Retorno: `{servicos_created, servicos_updated, composicoes_created, composicoes_updated, rejected:[{linha,motivo}]}`.

Testes (`tests/test_importar_composicoes.py`):
1. planilha válida → cria serviço + composições.
2. insumo inexistente → linha rejeitada com motivo.
3. coeficiente inválido → linha rejeitada.
4. reimportação com coeficiente novo → atualiza + grava histórico.
5. reimportação idêntica → 0 alterações.

**Commit:** `feat(orcamento): importador de composições via Excel (núcleo + testes)`

### A2. Rota + UI
- Rota de upload em `importacao_views.py` (ao lado do de insumos), validando arquivo e chamando a função.
- Botão/seção "Importar Composições" no template de importação, exibindo o resumo do retorno (criados/atualizados/rejeitados).
- Smoke test manual com planilha de exemplo.

**Commit:** `feat(orcamento): tela de importação de composições`

---

## PARTE B — Converter a obra (17 itens)

### B0. Premissas (Passo 0)
Tabela de premissas confirmada:
- Jornada **8 h/dia, 22 dias/mês**.
- **Validação dupla**: custo recalculado × custo REV10 **e** venda pós-BDI × venda REV10 (colunas K–AE).
- **Corrigir** erros da planilha na importação (não replicar), documentando cada correção.
- Mapear lucro/imposto por item → `Servico.imposto_pct` / `Servico.margem_lucro_pct` (ou override no Orçamento). Base da `composicao_servicos_baia_rev10.md`: Material lucro 20–25% (imposto 0); M.O. imposto 13% + lucro 28% (15% no 1.17).

### B1. Catálogo de Insumos (Passo 1)
Montar aba "Insumos" (materiais, mão de obra, equipamento) com `nome, tipo, unidade, preco_base, fator_comercial?`. Importar pelo importador existente (`importar_insumos_xlsx`). Mão de obra com R$/h da tabela da `composicao_servicos_baia_rev10.md` (Encarregado 36,36; Montador líder 31,82; Montador 26,14; Ajudante 20,46; Pedreiro 25,00; etc.).

### B2. Composições — mapeamento serviço → SINAPI (Passo 2)
Para cada item: puxar a composição SINAPI da web (orcamentor.com tem o analítico), extrair coeficientes, ajustar à jornada, montar a aba "Composicoes", importar pela Parte A. Mapeamento candidato (confirmar código vigente na execução; **prioridade nos pesados** marcados ★):

| Item | Serviço | Un | Qtd | Família SINAPI candidata | Obs |
|---|---|---|---:|---|---|
| 1.1 ★ | Estrutura Aço LSF Z275 | kg | 21.900 | **Light Steel Frame** (perfil galvanizado parafusado) — NÃO usar 100764 (laminado+guindaste) | confirmar código LSF |
| 1.2 | Pintura aço estrutural | m² | 1.173 | pintura esmalte/alquídica s/ metal | |
| 1.3 | Pintura/Stain portão pinus | m² | 161 | stain/verniz s/ madeira | |
| 1.4 | Portão Pinus | un | 48 | sem SINAPI direto → bottom-up (madeira+ferragem+M.O.) | |
| 1.5 ★ | Fechamento placa cimentícia | m² | 900 | painel/placa cimentícia em steel frame | |
| 1.6 | Fechamento régua pinus | m² | 660 | revestimento madeira/réguas | |
| 1.7 | Pintura fechamentos internos | m² | 900 | pintura | ⚠️ rever qtd |
| 1.8 | Stain paredes externas | m² | 660 | stain madeira | |
| 1.9 | Verticalização pilares roliços | un | 32 | bottom-up | 🔴 rever |
| 1.10 ★ | Corredores concreto | m² | 500,4 | piso/contrapiso concreto | |
| 1.11 | Revestimento pedra moledo | m² | 40 | revestimento pedra | |
| 1.12 | Pontos de luz | vb | 1 | ponto elétrico (converter vb→un pontos) | ⚠️ |
| 1.13 ★ | Telha Shingle | m² | 1.173 | telha shingle s/ estrutura madeira | |
| 1.14 | Cercado das baias | un | 24 | bottom-up | |
| 1.15 | Pintura Stain cercado | un | 24 | stain | 🔴 unidade |
| 1.16 | Ponto hidráulico por baia | un | 24 | ponto hidráulico (água) | 🔴 corrigir material 1×→24 |
| 1.17 | Pacote complementar REV10 | vb | 1 | decompor antes de mapear | 🧩 |

Itens "bottom-up" (1.4, 1.9, 1.14) não têm SINAPI direto → composição montada dos insumos reais.

### B3. Quantitativos (Passo 3)
Confirmar quantidades da REV10; cruzar com pranchas PDF nos pesados (1.1, 1.5, 1.13, 1.10). Resolver **22 × 24 baias** (cobertura mostra blocos 01–12 e 13–24 = 24) e o material 1× do 1.16. Pranchas: `obra_kabod/.../PROJETOS/{COBERTURA,BLOCO 1 E 2,IMPLANTACAO,DETALHE_ESTUDO,CROQUIS...}.pdf`.

### B4. Orçamento (Passo 4)
Criar `Orcamento` + 17 `OrcamentoItem` com quantidade; sistema recalcula custo (`orcamento_service.calcular_precos_servico`) e aplica BDI (`pricing.precificar`).

### B5. Validação (Passo 5)
Relatório por item: custo recalc × custo REV10 e venda pós-BDI × venda REV10. Marcar bate/não-bate e justificar cada divergência.

### B6. Calibração (Passo 6)
Usuário ajusta coeficientes que destoam da realidade; histórico em `ComposicaoServicoHistorico`.

---

## Ordem de execução
A1 → A2 (importador pronto e testado) → B0 → B1 → B2 → B3 → B4 → B5 → B6.
Primeiro item ponta-a-ponta sugerido: **1.1 (Estrutura LSF)** — valida o fluxo inteiro antes de escalar pros 17.
