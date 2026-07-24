# Plano de Implementação — Fase 5: Manual de uso em PDF (`cronograma_editor_v2`)

Spec: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md` (seção 7). Base: Fase 4 mergeada em `dd414212`. Tudo atrás da flag `cronograma_editor_v2` — **flag OFF = byte-idêntico**.

## O que o spec pede

- Botão "Manual (PDF)" na toolbar da página do cronograma, servindo `static/docs/manual-cronograma.pdf`.
- Conteúdo: edição na grade e atalhos, formato de predecessoras, recálculo automático (âncoras, dias úteis), caminho crítico, linha de base e desfazer — **com capturas de tela da ferramenta**.
- Arquivo estático **versionado no repositório** (sem geração dinâmica), atualizado quando a ferramenta mudar.

## Contexto verificado no ambiente

- Existe um sistema de manual em Markdown (`views/manual_views.py` + `manual/*.md`), mas o spec decidiu explicitamente por **PDF estático em `static/docs/`** — não misturar os dois fluxos.
- Playwright (Python) está instalado, mas sem navegadores baixados e sem como baixá-los (falta `libnspr4.so` no sistema — falha pré-existente conhecida). **Porém** o nix store tem `ungoogled-chromium 131.0.6778.204`, que roda headless e funciona como `executable_path` do Playwright (testado nesta sessão: launch + screenshot OK). As capturas serão reais, não ilustrações.
- `reportlab>=4.4.2` já é dependência do projeto (usada em `services/rdo_pdf_service.py`) — nenhuma dependência nova. Acentos pt-BR são Latin-1, cobertos pelas fontes built-in.
- Página do cronograma: `GET /cronograma/obra/<id>`; login em `/login`. Caminho crítico (barra vermelha), baseline (barra cinza + coluna Desvio) e toolbar de histórico já renderizam com a flag ON.
- Fixtures de seed reutilizáveis: padrão `_ambiente`/`_tarefa` de `tests/test_cronograma_versao_service.py`.

## Decisão 1: capturas reprodutíveis por script versionado

O PDF é estático, mas quem o atualiza na próxima mudança da ferramenta precisa refazer as capturas de forma idêntica. Por isso os dois scripts entram no repo:

- `scripts/manual_cronograma_capturas.py` — sobe o app em porta própria (5100), semeia um tenant de demonstração com sufixo único (obra "Residencial Vila Verde" com hierarquia, vínculos TI/II/TT com lag, tarefas iniciadas/ancoradas, baseline ativa com desvio), liga a flag, loga via Playwright (chromium do nix via env `CHROMIUM_BIN`, com fallback para o caminho conhecido do nix store) e captura as telas em `docs/img/manual-cronograma/`. Ao final **remove o tenant de demonstração** (delete cascade) — o banco de dev não acumula lixo.
- `scripts/manual_cronograma_pdf.py` — monta o PDF com reportlab/platypus a partir do texto (no próprio script) + capturas, gravando `static/docs/manual-cronograma.pdf`.

As capturas ficam versionadas junto com o PDF: regerar o PDF (ajuste de texto) não obriga a refazer capturas, e o diff de imagem denuncia mudança de UI.

## Decisão 2: botão dentro do bloco `{% if editor_v2 %}`

O manual descreve exclusivamente recursos do editor v2 — com a flag OFF o botão não faz sentido e violaria o byte-idêntico. Entra como `<a target="_blank">` para `url_for('static', filename='docs/manual-cronograma.pdf')`, último item do grupo v2 da toolbar (depois do grupo de ações da grade), ícone `fa-book`. É um link estático: nenhuma rota nova, nenhum guard novo.

## Conteúdo do manual (pt-BR, ~8–10 páginas A4)

1. **Capa + visão geral** — o que é o editor, como chegar na página (captura: página inteira com grade + Gantt).
2. **Edição na grade** — seleção de célula, F2/Enter para editar, Tab/setas para navegar, Esc cancela; inserir linha acima/abaixo, excluir; recuar/desrecuar (Alt+Shift+→/←) e o efeito na hierarquia e numeração (captura: célula em edição + toolbar da grade).
3. **Predecessoras** — formato `12TI+3;15II-2`: número da tarefa + tipo (TI, II, TT, IT) + lag opcional em dias úteis; múltiplas separadas por `;` (captura: célula de predecessoras preenchida).
4. **Recálculo automático** — cascata imediata ao editar, calendário de dias úteis seg–sex, âncoras: tarefa já iniciada (avanço de RDO) não se move, mas empurra as sucessoras; destaque das `tarefas_afetadas` (captura: Gantt após edição).
5. **Caminho crítico** — o que significa, barra vermelha nas tarefas sem folga (captura: Gantt com barras críticas).
6. **Linha de base** — congelar o planejado, uma ativa por obra, barra cinza sob a barra real e coluna Desvio (captura: Gantt com baseline + coluna Desvio).
7. **Desfazer/refazer** — Ctrl+Z/Ctrl+Y e botões; reversão por campo; o percentual vindo de RDO nunca é revertido; excluir arquiva (recuperável via desfazer sem perder apontamentos).
8. **Tabela de atalhos** — resumo de todos os atalhos.

## Steps

- **Step A** — `scripts/manual_cronograma_capturas.py`: seed + servidor + Playwright + capturas em `docs/img/manual-cronograma/*.png`. Rodar e conferir visualmente cada PNG.
- **Step B** — `scripts/manual_cronograma_pdf.py`: gerar `static/docs/manual-cronograma.pdf`. Conferir o PDF página a página.
- **Step C** — botão na toolbar (`templates/obras/cronograma.html`, bloco `editor_v2`).
- **Step D** — `tests/test_cronograma_manual_pdf.py`: (1) flag ON → link para `docs/manual-cronograma.pdf` presente na página; (2) flag OFF → ausente; (3) tenant vizinho com flag OFF → ausente; (4) o arquivo existe, começa com `%PDF-` e tem tamanho plausível (> 50 KB, garante que as capturas foram embutidas); (5) `GET /static/docs/manual-cronograma.pdf` responde 200 com `Content-Type: application/pdf`.
- **Step E** — regressão completa; commit único da fase.

## Riscos

- **Instabilidade do chromium do nix** (versão fora da matriz do Playwright): mitigado porque só usamos goto/click/fill/screenshot — nada de APIs novas. Se um clique falhar, capturar com estado montado via URL/JS direto.
- **Banco de dev com tabelas de sessões antigas** (lição da Fase 4): o seed usa modelos já migrados nas fases 1–4; nenhuma tabela nova nesta fase.
- **PDF pesado**: capturas em viewport 1440×900 PNG; se o PDF passar de ~2 MB, reduzir para JPEG qualidade 85 no embed.
