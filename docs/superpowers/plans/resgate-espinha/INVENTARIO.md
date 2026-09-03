# Inventário do PR #6 conferido — Resgate da Espinha Financeira

> **Medido em 2026-09-03**, na branch `sdd/espinha-financeira` (base `30287f3b`).
> Task 1 do plano `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`,
> executada pela Task 8 do plano de fecho de 31/08.
>
> **Nada aqui foi escrito por suposição.** Cada número saiu de um comando, e o
> comando está escrito ao lado.

## O ref durável

A origem do porte é a tag **`espinha-pr6-origem`**, criada nesta execução:

```
git tag espinha-pr6-origem origin/design/espinha-financeira-obra
espinha-pr6-origem -> a18f86e7   (2026-06-15)
```

⚠️ **Emenda ao Step 1 do plano.** Ele mandava `git fetch origin
design/…:refs/heads/resgate/espinha-financeira-origem` primeiro. Isso já não era
necessário — o ref é remote-tracking local e `git cat-file -p` lê todos os blobs.
**Mas a tag não existia** (`git tag | grep espinha` → vazio), e sem ela todo
`git show espinha-pr6-origem:…` das Tasks 2–9 falharia. O `fetch` era dispensável;
a tag, não.

## As linhagens continuam disjuntas

```
git merge-base main origin/design/espinha-financeira-obra   ->  (vazio)
git rev-list --count origin/fix/fase-0-estancar..main       ->  722
```

**O PR #6 não é mesclável.** Não há ancestral comum: `git merge-base` devolve
vazio. Isto é porte, não merge — e a Task 10 tem de escrever isso onde alguém
vá procurar, senão alguém tentará mesclar.

🔬 **A régua andou duas vezes.** O plano de 24/08 escreve **476**; o pré-voo de
02/09 mediu **706**; hoje são **722** — o merge da Onda 4 mexeu o número entre
ontem e hoje. O número é volátil e **deve ser medido no dia**; o que não muda é
o fato, e o fato é o `merge-base` vazio.

## O inventário do Step 2 — bate exatamente, 10 dias depois

| Arquivo | Esperado (24/08) | Medido (03/09) | |
|---|---|---|---|
| `services/resultado_atividade_service.py` | 537 | **537** | ✅ |
| `services/importar_obra_completa.py` | 291 | **291** | ✅ |
| `services/caixa_obra_service.py` | 27 | **27** | ✅ |
| `services/aprendizado_produtividade.py` | 63 | **63** | ✅ |
| `resultado_views.py` | 174 | **174** | ✅ |
| `templates/resultado/` | 4 arquivos | **4** (`caixa_obra`, `importar_obra`, `por_atividade`, `portfolio`) | ✅ |

**A cláusula "se divergir, pare" não dispara.** A branch está congelada em
`a18f86e7` desde 15/06 e o porte está inteiro e acessível.

## O que existe na `main` hoje — 4 de 21, não 7 de 20

🔬 Medido caminho a caminho sobre os 21 do *File Structure*
(`[ -f "$f" ]` na `main`, `git cat-file -p espinha-pr6-origem:$f | wc -l` na branch):

| Caminho | Na `main` | Linhas na branch |
|---|---|---|
| `services/caixa_obra_service.py` | ausente | 27 |
| `services/aprendizado_produtividade.py` | ausente | 63 |
| `services/resultado_atividade_service.py` | ausente | 537 |
| `services/importar_obra_completa.py` | ausente | 291 |
| `resultado_views.py` | ausente | 174 |
| `templates/resultado/por_atividade.html` | ausente | 121 |
| `templates/resultado/caixa_obra.html` | ausente | 87 |
| `templates/resultado/portfolio.html` | ausente | 83 |
| `templates/resultado/importar_obra.html` | ausente | 37 |
| `scripts/criar_orcamento_baia_rev10.py` | **existe** 🔴 | 87 |
| `scripts/seed_templates_baia_rev10.py` | ausente | 87 |
| `scripts/importar_baia_easypanel.py` | ausente | 61 |
| `migrations.py` | **existe** | (arquivo da árvore) |
| `tests/test_resultado_atividade_service.py` | ausente | 406 |
| `tests/test_resultado_fatia2_custo_nao_mo.py` | ausente | 228 |
| `tests/test_importar_obra_completa.py` | ausente | 299 |
| `tests/test_caixa_obra.py` | ausente | 92 |
| `tests/test_fatia5_inteligencia.py` | ausente | 167 |
| `tests/test_import_baia_e2e.py` | ausente | 153 |
| `tests/test_rdo_edicao_preserva_tarefa.py` | **existe** ✅ | 105 |
| `ESTADO_design_espinha_financeira.md` | **existe** | 97 |

**4 de 21.** O cabeçalho do plano dizia "7 de 20" — régua velha, corrigida no
mesmo commit que renumerou as migrations. Não é bloqueio: é expectativa. **Há
mais porte a fazer do que se anunciava, não menos.**

🔬 Somando os caminhos a portar (fora `migrations.py` e o doc a aposentar):
**3.105 linhas** na branch, contra as "2.542" que o cabeçalho anuncia.

### Os três que existem e não são iguais

- 🔴 `scripts/criar_orcamento_baia_rev10.py` — **existe e diverge**. A `main` tem
  o `main()` velho, que pega o primeiro ADMIN; a branch tem
  `criar_orcamento_baia(admin_id, xlsx_path)`, a forma reusável que o E2E chama.
  Na Task 9 é **sobrescrita consciente**, não criação.
- ✅ `tests/test_rdo_edicao_preserva_tarefa.py` — **já portado, byte a byte
  idêntico** à branch; chegou em `b30923b5` (22/07). Nada a fazer.
- `ESTADO_design_espinha_financeira.md` — é o documento a **aposentar** na
  Task 10, não a portar.

## O arquivo que o plano não vê, e sem o qual a Task 8 não fecha

🔴 `cronograma_views.py` **não era citado nenhuma vez** no plano da Espinha — nem
no *File Structure*, nem nos `Files:` de nenhuma das dez tasks. E
`tests/test_resultado_fatia2_custo_nao_mo.py:184` (na branch) faz
`from cronograma_views import _registrar_custo_subempreitada`, função com **zero**
ocorrências na `main`.

⚠️ Os dois `cronograma_views.py` são de linhagens disjuntas e **não** são
portáveis por cópia: `main` tem 186.853 bytes, a branch 103.217. O porte é **da
função**, localizada por conteúdo. Virou o **Step 3b** da Task 8.

## Ordem interna que não pode ser trocada

- **Task 5 → Task 8** em `services/resultado_atividade_service.py`: a 5 **remove**
  o ramo de subempreitada, a 8 **devolve**. É desenho, não acidente.
- **Task 5 → Task 8** em `tests/test_resultado_fatia2_custo_nao_mo.py`: a 5 **põe**
  o `xfail`, a 8 **tira**. Com `strict=True`, marcador que sobra depois do
  conserto **falha o gate por XPASS**. 🔬 O arquivo tem 6 testes e **1** toca
  subempreitada: o `xfailed` sobe **1** e volta **1**.
- **Tasks 3, 4 e 8** tocam `models.py` e o registry de `migrations.py`, uma em
  cada número (**319**, **320**, **321**). Sequenciais, nunca em paralelo.
