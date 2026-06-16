# Entrega — Orçamento "Baia REV10" (Kabod Cabana)

Pasta autossuficiente com tudo que é relevante para continuar o trabalho do orçamento das
24 baias de bovinos (Fazenda Santa Mônica, Itu/SP) e a conversão para o sistema SIGE.

## ⭐ Comece por aqui
**`03_analise_contexto/CONTEXTO_orcamento_baia_rev10.md`** — documento mestre. Explica como o
app calcula o orçamento, o estado do trabalho, todos os arquivos e as decisões em aberto.
É o arquivo para colar inteiro em outro LLM.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `01_planilha_original/` | A planilha original `Orçamento - Baia - REV10.xlsx` (fonte de verdade = aba `Proposta Comercial`) + proposta REV10 (pdf/docx). |
| `02_projetos/` | Projetos da obra: DETALHE (legenda elétrica/hidráulica), BLOCO 1 E 2 (planta das 24 baias), IMPLANTAÇÃO, croquis 3D e o estrutural (`.dwg`, ainda não lido). |
| `03_analise_contexto/` | **CONTEXTO** (mestre) + relatório de análise item a item + plano de conversão + composições. |
| `04_scripts/` | Scripts Python idempotentes (decomposição do 1.17, validação dupla, importação). Rodam com `PYTHONPATH=<raiz_do_app> python3 <script>.py`. |
| `05_importacao/` | Planilhas de importação geradas. |
| `06_codigo_calculo/` | Código do sistema que calcula custo→venda: `pricing.py` (BDI/TCU), `orcamento_service.py`, `orcamento_view_service.py`, `orcamentos_views.py` + spec e ADR do BDI. |

## Números-chave (custo)
- Total exibido na planilha (J27): **R$ 1.145.717,42** — contém **R$128k fantasma** do erro do item 1.3.
- Custo consistente (corrige 1.3): **R$ 1.017.717,42**.
- Custo validado (com o 1.17 decomposto): **R$ 1.073.364,66**.
- Item 1.17 decomposto: **R$ 148.211** (Fundação 92k + Elétrica 17,4k + Hidráulica 19k + Isolamento 6,9k + Forro 12,9k).

## Decisões em aberto (ver detalhe no CONTEXTO, seção 5)
1.3 (Stain global vs /m², R$128k) · 1.16 (material 1× vs ×24) · material das louças (R$40,9k) ·
custo×venda + BDI · modelo de M.O. · quantidades 1.9/1.12 · premissas 🧩 do 1.17.

> Convenções de confiança: ✅ confirmado · ⚠️ validar · 🔴 erro · 🧩 inferência.
