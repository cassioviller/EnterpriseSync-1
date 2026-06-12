# HANDOFF — Obra Baia REV10 (Kabod Cabana) · estado da sessão

> Ponto de entrada único para retomar o trabalho. Última atualização: 2026-06-12.
> Detalhes estão nos docs apontados; aqui é o resumo + o que falta.

## Onde estamos (resumo)
Convertendo o orçamento manual `Orçamento - Baia - REV10.xlsx` (24 baias de bovinos, Fazenda
Santa Mônica/Itu-SP, cliente Grupo Mônica) para o sistema SIGE, e agora montando o **cronograma
vinculado ao orçamento** para gerar **medições ao cliente**.

## Já feito ✅
1. **Item 1.17 decomposto** em 5 serviços reais: Fundação (R$92.001, enxugada de R$121k:
   equipe 40→20 dias + escavação dupla removida), Infra Elétrica (R$17,4k), Infra Hidráulica
   (R$19,0k, inclui banheiro), Isolamento lã de rocha (R$6,9k), Forro PVC (R$12,9k). Valores
   ancorados em SINAPI-SP e na análise dos projetos (PDFs). 1.17 real = **R$148.211**.
2. **Validação dupla do orçamento inteiro:** achado o **erro do item 1.3** (R$128k fantasma —
   Stain global em H vs ×161 em J). Custo coerente ≈ R$1.017.875.
3. **Importado no sistema:** orçamento **`ORC-BAIA-REV10` (id 98)**, 21 itens, idempotente via
   `scripts/criar_orcamento_baia_rev10.py`.
4. **Venda calibrada para bater com o original:** markup **UNIFORME +69,06%** → venda total
   **R$1.720.796,75** (= soma da coluna O da proposta). No sistema deu R$1.720.836,70 (+R$40 por
   causa do limite de 2 casas do campo `margem_pct`).
5. **Apresentação** (Excel+PDF) e **planilha de importação** regeneradas com o 1.17 decomposto
   e a venda calibrada.

## Em andamento 🚧 — Cronograma + Medições
- O mecanismo do sistema já existe (ver `ESTUDO_cronograma_baia_rev10.md`):
  `CronogramaTemplate` por serviço → `TarefaCronograma` na aprovação da proposta →
  `ItemMedicaoComercial` (valor de venda) → peso por horas → RDO atualiza % → medição = Δ% ×
  venda → ContaReceber (fatura o cliente).
- Esboço do cronograma em **`Projeto1.mpp`** (MS Project, ~30 tarefas extraídas).

## ⚠️ Maior pendência — Cobertura mudou para aço laminado viga I
O cronograma tem "ESTRUTURA METÁLICA PARA TELHADO" + "FABRICAÇÃO DE AÇO PARA TELHADO" (aço
laminado **viga I**, antes era steel frame/LSF). **Isso NÃO está no orçamento** (o item 1.1 é o
LSF das baias, não o telhado). Falta criar um item de orçamento para o telhado em viga I
(peso kg, perfil, preço/kg, fabricação+montagem). Sem isso, a maior atividade do telhado não mede.

## Próximos passos / decisões pendentes do usuário
1. **Telhado viga I:** tem projeto estrutural (perfis/peso)? O DWG `EST_PROJBAIAS_FAZMONICA_REV01
   (2).dwg` pode ter (ainda não lido — é binário). Ou começar com verba estimada.
2. **Datas do cronograma:** exportar o `.mpp` para **XML** (MS Project → Salvar como XML) para
   extrair datas/durações/predecessoras (o binário só deu os nomes).
3. **Granularidade da medição:** por serviço (~17 itens) ou por atividade (~30 tarefas do MPP)?
4. Decidir as 3 questões do 1.3/1.16/louças (ver CONTEXTO §5) e venda exata à vírgula + limpar
   5 serviços órfãos com sufixo "(1.17)" no catálogo.

## Documentos (todos em /home/runner/workspace)
- **`CONTEXTO_orcamento_baia_rev10.md`** — como o app calcula o orçamento + estado + arquivos (mestre do orçamento).
- **`ESTUDO_cronograma_baia_rev10.md`** — mecânica cronograma↔orçamento↔medição + tarefas do MPP + cobertura.
- `relatorio_analise_orcamento_baia_rev10.md` — análise item a item (1.1–1.17).
- `entrega_baia_rev10/` — pasta com todos os arquivos relevantes (planilha, projetos, scripts, apresentação).
- `APRESENTACAO_Baia_REV10.pdf/.xlsx` — apresentação (serviço → insumos, % markup, venda).
- `Projeto1.mpp` — esboço do cronograma (MS Project).

## Scripts (rodam com `PYTHONPATH=/home/runner/workspace python3 scripts/<x>.py`)
- `gerar_importacao_baia_rev10.py` — gera planilha de importação (venda = original).
- `criar_orcamento_baia_rev10.py` — importa catálogo + monta orçamento no sistema.
- `decompor_117_fundacao.py` / `decompor_117_resto.py` — decomposição do 1.17 (catálogo).
- `validar_orcamento_baia_rev10.py` — validação dupla.
- `apresentacao_orcamento_baia_rev10.py` — Excel/PDF de apresentação.

## Git
Branch `main`. Últimos commits relevantes: a51d512 (estudo cronograma), 8bcca88 (venda=original),
3ac47d3 (import 1.17 decomposto), 7b65400 (validação), 38ee74c (fundação enxugada).
