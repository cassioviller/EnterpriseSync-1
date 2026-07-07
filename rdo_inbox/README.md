# 📥 Caixa de entrada de RDO — obra Baias Kabod

Cole aqui o **texto** e as **fotos** dos RDOs (Relatório Diário de Obra). Depois é
só me pedir: **"reorganiza o JSON com os RDOs novos"** — eu leio esta pasta,
atualizo o `%físico` de cada etapa em
`tests/fixtures/cronograma_fisico_financeiro_baias.json` e o cronograma fica
pronto pra re-seedar.

## Como usar

1. Crie uma pasta por dia, no formato `AAAA-MM-DD/` (ex.: `2026-07-07/`).
   - Já deixei `2026-07-07/` pronta, com o modelo.
2. Dentro dela:
   - **`rdo.md`** → cole o texto do RDO (copie o modelo de `_MODELO_rdo.md`).
   - **`fotos/`** → jogue as imagens (`.jpg`/`.png`), com nomes que ajudem
     (`fundacao-galpao-a-01.jpg`, `ferragem-02.jpg`, ...).
3. Me chame pra reorganizar.

## O que eu faço com isso

- Leio o `%` (ou a descrição de avanço) de cada etapa/tarefa que você anotar.
- Atualizo o `pct_fisico` das tarefas em `cronograma_tarefas` e o `%físico base`
  de cada etapa da EAP no JSON.
- Registro no `_meta` a data do último RDO aplicado.
- As **fotos ficam versionadas aqui** (referência), e eu cito quais entraram.

> A **base** de hoje já veio dos percentuais do MS Project (`CRONOGRAMA 06.07.mpp`).
> Os RDOs servem pra **refinar/avançar** esses números a partir daqui.

## Etapas da obra (códigos que uso no JSON)

| Código | Etapa |
|---|---|
| PRELIM | Preliminares e projetos |
| FUND | Fundação (Galpão A + B) |
| ESTMET | Estrutura metálica (cobertura) |
| ESTLSF | Estrutura LSF (baias) |
| COBERT | Cobertura (telhado shingle) |
| FECHA | Fechamentos (plaqueamento) |
| PINT | Pintura / Stain |
| MOLEDO | Pedra moledo |
| PORTAO | Portões |
| ELET | Elétrica |
| HIDRO | Hidráulica |
| INDIRETOS | Indiretos / gestão |
