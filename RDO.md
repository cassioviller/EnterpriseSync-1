# RDO da Baia — como o import funciona e como atualizar

> Guia operacional. O objetivo é: **você me manda o RDO do dia aqui no chat
> (texto + fotos numa pasta), eu edito o JSON, você reimporta.** Não precisa mexer
> no RDO pela tela — o reimport reconstrói tudo (comentário, clima, % de avanço e
> fotos).
>
> **ATUALIZAÇÃO (2026-07-21, M09):** para atualizar o CRONOGRAMA a obra não
> usa mais reimport de JSON — use a aba Cronograma da página da obra
> (Importar cronograma .xml/.mpp → prévia → Aplicar), que preserva RDOs,
> fotos e histórico com versões restauráveis. O reimport de JSON é recusado
> em obra já migrada; segue valendo apenas como criação inicial. RDOs do
> dia a dia: registre pela tela de Novo RDO (M07 — modos quantitativo e
> percentual). Ver `ESTADO_ATUALIZACAO_BAIA.md`.
>
> **ATUALIZAÇÃO (2026-07-27):** para acrescentar RDOs EM LOTE a uma obra em
> andamento, use o caminho não-destrutivo — `scripts/atualizar_rdos_obra.py`
> (serviço `services/atualizacao_rdos.py`): faz upsert por data, não apaga
> tarefa/proposta/medição/RDO nenhum e funciona em obra já versionada por
> .mpp. E se os RDOs vêm do grupo de WhatsApp, `scripts/whatsapp_para_rdos.py`
> monta o payload e extrai as fotos com as legendas. O reimport descrito
> abaixo continua valendo só para **criação inicial**.

---

## 1. Estado atual do import

- O import físico-financeiro é feito por **upload de um arquivo JSON** na tela
  **Importação → Físico-Financeiro** (`/importacao/fisico-financeiro`). Não há
  caminho fixo: vale o arquivo que você sobe.
- **Arquivo canônico (o que você sobe):**
  `cronograma_fisico_financeiro_baias.json` — **na raiz do projeto**.
  A fixture dos testes (`tests/fixtures/cronograma_fisico_financeiro_baias.json`)
  é um **symlink** para esse mesmo arquivo, então o que você importa e o que os
  testes verificam **nunca divergem**.
  - _(Existe um `Baia_fisico_financeiro_IMPORTAR.json` legado na raiz, sem seção
    `rdos`. Não use mais — foi substituído pelo canônico acima.)_
- O import é **idempotente e por obra**: reimportar **não duplica** — ele apaga os
  RDOs anteriores da obra e recria a partir do JSON. As fotos antigas somem junto
  (FK `ON DELETE CASCADE`) e são recriadas. Pode reimportar quantas vezes quiser.

### De onde sai o "% da obra"

O avanço físico da obra vem dos **RDOs** (seção `rdos` do JSON). Cada RDO tem
**apontamentos** que dizem "tal tarefa está em X%". O app acumula isso por data e
calcula o progresso geral (`calcular_progresso_geral_obra_v2`). Hoje a Baia tem
**31 RDOs** (22/06 a 29/07). Não há RDO nos domingos nem nos fins de semana de
11-12, 18-19 e 25-26/07 — a obra trabalhou alguns sábados (27/06, 04/07), outros
não. Os 17 últimos (07/07 a 29/07) vieram de dois exports do WhatsApp, em 27/07
e 30/07 — ver `ESTADO_ATUALIZACAO_BAIA.md`.

> Se o JSON **não** tiver a seção `rdos`, o import cai num modo de fallback: cria
> **1 RDO sintético** a partir do `pct_fisico` das tarefas. Como agora usamos RDOs
> diários de verdade, mantenha sempre a seção `rdos`.

---

## 2. Seção `rdos` — schema de um RDO

Cada item da lista `rdos` é um dia:

```json
{
  "data": "2026-06-22",
  "clima": "Nublado",
  "precipitacao": "Sem chuva",
  "comentario": "Texto livre do que aconteceu no dia (vai no 'Comentário Geral').",
  "mao_de_obra": 0,
  "apontamentos": [
    { "tarefa_mpp": 3, "pct": 100 },
    { "tarefa_mpp": 4, "pct": 50 }
  ],
  "fotos": [
    "Legenda da foto 1.jpg",
    "Legenda da foto 2.jpg"
  ]
}
```

| Campo | O que é | Obrigatório |
|---|---|---|
| `data` | Dia do RDO, `AAAA-MM-DD`. Vira o número do RDO e é a data do avanço. | **sim** |
| `clima` | Ex.: "Ensolarado", "Nublado", "Chuvoso". | não |
| `precipitacao` | Ex.: "Sem chuva", "Chuva fraca". | não |
| `comentario` | Texto livre (relato do dia). | não |
| `mao_de_obra` | Quantas pessoas anexar (0 = nenhuma; você lança a equipe real editando o RDO, se quiser). Mão de obra do RDO **não gera custo**. | não (default 0) |
| `apontamentos` | Avanço das tarefas no dia. Dois modos por item (ver abaixo). `tarefa_mpp` é o **id da tarefa no cronograma** (coluna do MS Project). | não |
| `fotos` | Lista de **legendas em ordem** (foto 1, 2, 3…) OU objetos `{arquivo, legenda}`. Ver seção 3. | não |

**Sobre `apontamentos`:** você **não precisa** saber os ids. É só me descrever no
chat ("estudo de solo 100%, projetos em 65%, nivelamento do platô 20%") que eu
traduzo para os `tarefa_mpp` certos. A tabela de ids está em `cronograma_tarefas`
dentro do próprio JSON (cada tarefa tem `id` + `nome`).

**Dois modos de apontamento** (por item):

1. **Percentual direto** — `{"tarefa_mpp": 6, "pct": 65}`: você diz o % da tarefa.
2. **Quantitativo (automático)** — `{"tarefa_mpp": 15, "quantidade": 10}`: você diz
   **quanto fez** e o sistema calcula o % sozinho, pela `quantidade_total` da tarefa
   no cronograma. Ex.: brocas com `quantidade_total: 48` → "fez 10" = **20,83%**; no
   RDO seguinte "fez mais 15" → acumula 25 → **52,08%** (soma sozinho entre RDOs).

Para o modo quantitativo, a **tarefa no cronograma** precisa ter o total:
```json
{ "id": 15, "nome": "EXECUÇÃO DE FERRAGENS PARA FUNDAÇÃO",
  "quantidade_total": 48, "unidade": "un", ... }
```
> O `quantidade_total` governa **só o % daquela tarefa**. No progresso geral da obra
> (o anel), o peso da tarefa continua pela **duração** — a menos que **todas** as
> tarefas tenham quantitativo (aí o peso passa a ser o quantitativo). Isso evita
> misturar unidades ("48 brocas" × "dias" das outras tarefas).

---

## 3. Fotos — pasta por dia + legendas

As imagens ficam em **`fotos_rdos/<data>/`**, numeradas em ordem:

```
fotos_rdos/
└── 2026-06-22/
    ├── 1.jpg
    ├── 2.jpg
    └── 3.jpg
```

- O nome da subpasta é a **mesma `data` do RDO** (`AAAA-MM-DD`).
- As fotos são numeradas `1, 2, 3…` na ordem que você quer que apareçam.
- No JSON, `fotos` é a lista de **legendas na mesma ordem**: a 1ª legenda é do
  `1.<ext>`, a 2ª do `2.<ext>`, etc.
- No **reimport**, o app lê os arquivos, otimiza (WebP + base64) e anexa ao RDO —
  igual ao upload da tela, mas automático e **persistente** (sobrevive a deploy).
- Formatos: `jpg, jpeg, png, gif, webp`. Máx. 5 MB/foto, até 20 fotos/RDO.
- **Foto faltando na pasta = pulada com aviso** (o import não quebra).
- Precisa fixar o nome do arquivo em vez da ordem? Use a forma longa:
  `{ "arquivo": "2.jpg", "legenda": "..." }`.

**Dia com fotos, mas SEM legenda:** se o RDO **não** tiver a chave `fotos` no JSON e
a pasta do dia tiver imagens, o import anexa **todas** as imagens da pasta (ordem
numérica) com **legenda vazia**. Ou seja: é só largar as fotos na pasta — tendo
legenda ou não, elas entram no reimport. (Quando você manda legendas, aí eu ponho a
lista `fotos` e cada foto sai legendada.)

Detalhes também em `fotos_rdos/README.md`.

### Apagar as fotos da raiz depois de importar (para aliviar espaço)

As fotos, uma vez importadas, ficam **em base64 no banco** (persistentes). Então
você **pode apagar os arquivos** de `fotos_rdos/<data>/` depois de importar, sem
perder nada. A regra do reimport é:

| Estado da pasta `fotos_rdos/<data>/` no reimport | O que acontece com as fotos do RDO |
|---|---|
| **Tem arquivos** | A pasta manda: reconstrói as fotos daquele dia a partir dela (substitui). |
| **Vazia / não existe** | **Preserva** as fotos que já estavam no RDO (não apaga). |

Ou seja: importar com fotos → apagar os arquivos da raiz → reimportar **mantém**
as fotos. Para **trocar** as fotos de um dia, é só colocar os arquivos novos na
pasta e reimportar. Para **zerar** as fotos de um dia sem colocar outras, apague-as
pela tela do RDO (o reimport sozinho, com a pasta vazia, nunca remove).

> Cuidado: se a pasta tiver **qualquer** arquivo, ela substitui o conjunto inteiro
> daquele dia. Não deixe 1 arquivo solto achando que os outros serão preservados.

---

## 4. O fluxo (o que você faz × o que eu faço)

**Você:**
1. Cria a pasta do dia: `fotos_rdos/AAAA-MM-DD/` e joga as fotos numeradas
   (`1.jpg`, `2.jpg`…).
2. Me manda **aqui no chat**: a data, clima, o relato do dia, o avanço de cada
   frente ("solo 100%, projetos 65%…") e as **legendas na ordem das fotos**.

**Eu:**
3. Edito `cronograma_fisico_financeiro_baias.json`: adiciono/atualizo o RDO daquele
   dia na seção `rdos` (comentário, clima, `apontamentos`, `fotos`).
4. Confirmo que os testes passam.

**Você:**
5. Faz **upload** do `cronograma_fisico_financeiro_baias.json` em
   Importação → Físico-Financeiro. Pronto: RDO do dia com texto, avanço e fotos.

---

## 5. Onde isso mora no código (referência)

- Import + RDOs + fotos: `services/importacao_fisico_financeiro.py`
  - `_materializar_rdos` — cria os RDOs, apontamentos e chama as fotos; idempotente.
  - `_materializar_fotos_rdo` — lê `fotos_rdos/<data>/`, gera `RDOFoto` (base64).
  - `FOTOS_RDO_BASE` — base das pastas de foto (default `fotos_rdos`; sobrescrevível
    por env `FOTOS_RDO_BASE`).
- Processamento da imagem (otimização + base64): `services/rdo_foto_service.py`.
- Modelo da foto: `RDOFoto` em `models.py` (base64 no banco → não some em deploy).
- Testes: `tests/test_importacao_fisico_financeiro.py`
  (`test_import_anexa_fotos_do_rdo`, `test_import_cria_rdos_da_secao_rdos`, …).

### Validar localmente antes de subir

```bash
GIT_CONFIG_NOSYSTEM=1 python3 -m pytest tests/test_importacao_fisico_financeiro.py -q
```

---

## 6. Carga de QUALQUER obra — export + WhatsApp + % do .mpp (2026-08-10)

> A generalização não-destrutiva do fluxo da Baia, para obra que JÁ existe
> em produção (casos Angela id=43 e Pablo/OB004). Plano e decisões:
> `docs/superpowers/plans/2026-08-10-carga-nao-destrutiva-cronograma-rdos.md`.

Três artefatos entram na raiz do repo:

1. **Zip do botão "Exportar RDOs (.zip)"** (aba RDOs da página da obra) —
   obra.json (identidade + tabela de tarefas) + rdos.json + mapa_nomes.json.
   Autossuficiente: os scripts locais não tocam o banco de produção.
2. **Export da conversa do WhatsApp** — Android ("Conversa do WhatsApp
   com ...zip") OU iOS ("WhatsApp Chat - ...zip" com `_chat.txt`); o
   parser entende os dois. Marcadores com várias grafias entram como
   apelidos separados por vírgula.
3. **Cronograma `.mpp`/`.xml`** com as % (opcional) — as FOLHAS com pct>0
   viram apontamentos distribuídos pelos dias de RDO: 100% no primeiro
   RDO ≥ `data_fim` da tarefa; parcial no último RDO (snapshot: afirmar
   antes inventaria história).

### Preparar (local, sem banco)

```bash
python scripts/preparar_carga_obra.py \
    --export rdos_43_2026-08-10.zip \
    --whatsapp "WhatsApp Chat - ....zip" \
    --obra-marcador "Obra a Angela,Obra casa Angela,Obra Angela" \
    --mpp "Veks - Angela - Cronograma Atual25.05.mpp" \
    --corrigir-data 2016-03-09=2026-03-09 \
    --conflito sistema
```

Sai `cargas/obra-<codigo|id>/payload_rdos.json` + relatório + fotos em
`fotos_rdos/obras/<codigo|id>/<data>/` — base POR OBRA; a base legada
`fotos_rdos/<data>/` é da Baia e não é tocada.

Regras que o preparo impõe (nada em silêncio):

- **dia só no chat** → item novo; **campo vazio no sistema** → completado;
- **campo preenchido nos dois lados e diferente** → `--conflito sistema`
  mantém o do sistema com aviso (decisão de 2026-08-10: o que entrou
  manualmente é o registro curado); default `pendencia` para revisão;
- **RDO assinado/aprovado/retificado** → pulado; **ano implausível**
  (typo "2016") → pendência, corrigível por `--corrigir-data`;
- **dia com foto no banco** → fotos do chat descartadas (o updater
  preserva as existentes);
- **data com 2 RDOs no sistema** → o export retrata o PRIMEIRO (o mesmo
  que o updater atualiza); zip antigo ("mais recente") segura o texto.

### Aplicar (produção, nesta ORDEM)

```bash
# 1) aba Cronograma da obra: Importar .mpp → prévia → Aplicar
#    (grava mpp_uid; SEM isso os apontamentos do payload não resolvem)
# 2) o payload (obra sem código aceita o id):
python scripts/atualizar_rdos_obra.py veks 43 \
    cargas/obra-43/payload_rdos.json --fotos-base fotos_rdos/obras/43 --dry-run
# sem pendências → rodar de novo sem --dry-run
```

Em obra COM RDO o `pct_project` do .mpp **não** carrega no import do
cronograma (por design) — é o payload que leva as %. Reaplicar o payload
é idempotente.

- Código: `views/rdo.py` (rota do zip), `services/exportacao_rdos.py`,
  `scripts/preparar_carga_obra.py`, `scripts/whatsapp_para_rdos.py`
  (parser iOS + apelidos), `scripts/atualizar_rdos_obra.py`.
- Testes: `tests/test_e2e_carga_obra.py` (ponta a ponta, rota→banco),
  `test_exportacao_rdos.py`, `test_preparar_carga_obra.py`,
  `test_whatsapp_parser_ios.py`.
