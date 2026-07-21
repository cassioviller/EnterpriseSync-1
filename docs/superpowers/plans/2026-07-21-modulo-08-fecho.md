# Módulo 08 — Interface de Cronograma na Obra — Fecho

> Fecha o M08 conforme o plano `2026-07-21-modulo-08-implementacao-interface-obra.md`
> (spec `2026-07-17-modulo-08-interface-obra.md`).

## Entregue (commits nesta branch `feat/cronograma-mpp-m03-upload-parser`)

| Task | Conteúdo |
|---|---|
| 1 | Endpoints de apoio (listas de importações/versões, status, cancelar) + flag `cronograma_mpp_ativo` |
| 2 | Seção na aba Cronograma (parcial + JS: upload modal, polling, restaurar com confirmação dupla) |
| 3 | Prévia com decisão de mapeamentos, aplicação, resultado e auditoria |
| 4 | Playwright da jornada completa + este fecho |

## Checklist §22 da spec — estado

- [x] **Seção na aba Cronograma atrás de flag** — include único no template
      de 157 KB, atrás de `is_v2_active` + `cronograma_mpp_ativo`
      (ponto único em `utils/tenant.py` para o M10 endurecer; hoje = V2).
      Teste: presente para admin V2, ausente para V1.
- [x] **Upload→prévia→aplicar→resultado completo** — sem sair da página da
      obra: modal de upload (.xml MSPDI primário e .mpp — a spec citava
      ".mpp/.json", desatualizada vs adendo M03), lista com status/erro/
      pendências, prévia com reconcile automático de importação
      'normalizado', aplicação com confirmação e página de resultado com
      antes/depois + relatório do replanejamento (M06).
- [x] **Edição manual de mapeamentos funcional** — modal por linha
      (casar com candidatos/chaves livres, arquivar, nova → PATCH M05);
      pendências bloqueiam o Aplicar na UI E na API (422 — critério 2).
- [x] **Restaurar e auditoria visíveis** — restauração no histórico de
      versões com confirmação dupla (digitar o nº); trilha de eventos com
      usuário/data/detalhes na prévia e no resultado.
- [x] **Zero referência a baias no código novo** — verificado por grep nos
      arquivos novos (critério global 17).
- [x] **Playwright verde** — `test_cronograma_importacao_obra_playwright.py`:
      jornada completa (upload de MSPDI gerado no teste com rename + nova +
      removida + ambígua → prévia com 1 pendência → decisão manual →
      aplicar → resultado → efeitos verificados no banco: rename in-place,
      arquivamento sem DELETE, inserção, ambígua casada, versão ativa).
      Gate escopado: 144 testes em 10 suítes + E2E.

## Ressalvas de execução

1. **Polling é cosmético** — o upload do M03 é síncrono (a resposta já sai
   'normalizado'/'falhou'); o polling de 2s cobre apenas o caminho `.mpp`
   lento e estados intermediários raros. Estado `falhou` é terminal e
   sempre exibido com o erro.
2. **Modais dentro do tab-pane** — o pane tem transform de animação, o que
   quebra `position:fixed`; o JS move o modal para `document.body` ao abrir
   (workaround padrão do Bootstrap, descoberto pelo E2E).
3. **Auditoria embutida** — a spec §4.3 pedia "aba" de auditoria; entregue
   como seção nas páginas de prévia e resultado (mesma informação, menos
   um nível de navegação).
4. **Sem tela dedicada de snapshot de versão** — "ver snapshot" da spec
   §4.1 ficou como contagem de snapshots na lista + restauração; a
   visualização completa do snapshot é candidata ao M10/backlog.
5. **Confirmação de restauração usa `prompt()` nativo** — padrão simples;
   consistente com os `confirm()` do restante do projeto.

## Próximo

M09 (migração das baias): migrar o import físico-financeiro para o serviço
de apontamento (aposenta o formato antigo e o fallback do portal) e
reimportar as obras existentes pelo pipeline novo. Depois M10 (flag real,
observabilidade, rollout).
