# fotos_rdos/ — fotos dos RDOs (entram no import)

Uma **subpasta por dia de RDO**, com o nome no formato **`AAAA-MM-DD`** (a mesma
data do campo `data` do RDO no `cronograma_fisico_financeiro_baias.json`).

Dentro de cada subpasta, as imagens são **numeradas em ordem**: `1.jpg`, `2.jpg`,
`3.png`… A ordem dos números é a ordem em que as fotos aparecem no RDO, e é a
mesma ordem das **legendas** que você manda no chat.

```
fotos_rdos/
├── 2026-06-22/
│   ├── 1.jpg
│   ├── 2.jpg
│   └── 3.jpg
├── 2026-06-23/
│   └── 1.jpg
└── ...
```

Formatos aceitos: `jpg, jpeg, png, gif, webp` (máx. 5 MB, até 20 fotos por RDO).

## Como isso vira foto no RDO

No `cronograma_fisico_financeiro_baias.json`, o RDO do dia ganha uma lista
`fotos` com **uma legenda por imagem, na ordem dos arquivos**:

```json
{
  "data": "2026-06-22",
  "comentario": "...",
  "apontamentos": [...],
  "fotos": [
    "Topógrafo levantando os níveis do platô",
    "Marcação do gabarito da Baia 01",
    "Container de apoio instalado"
  ]
}
```

`"fotos"[0]` → `1.<ext>`, `"fotos"[1]` → `2.<ext>`, e assim por diante.
Ao **reimportar**, o app lê os arquivos desta pasta, otimiza (WebP + base64) e
anexa ao RDO — igual ao upload manual da tela, mas automático.

> Se um arquivo estiver faltando, aquela foto é **pulada com aviso** (o import
> não quebra). Se quiser fixar o nome do arquivo em vez da ordem, use a forma
> longa: `{"arquivo": "2.jpg", "legenda": "..."}`.

Fluxo completo e schema do RDO: veja **`RDO.md`** na raiz do projeto.
