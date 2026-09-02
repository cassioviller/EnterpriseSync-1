# Operação — tudo o que roda por agendamento

> Decisão de 01/09 (`docs/superpowers/plans/2026-09-01-decisoes-respondidas.md`,
> §A25 e §backup): agendador vive FORA do processo web. O guard multi-worker do
> APScheduler é manual (`app.py:1055-1058`, `SCHEDULER_ENABLED`) e quebra no
> primeiro `-w 2`.

## Backup do banco (Fase 0.5 — ❌ até o job existir)

- Job de cron do EasyPanel, diário:
  `pg_dump "$DATABASE_URL" | gzip > /backups/sige_$(date +%F).sql.gz`
- Retenção mínima 14 dias; testar o RESTORE uma vez por mês, não só o dump.

## Notificações n8n (A25)

- Pré-requisito: `N8N_WEBHOOK_URL` no ambiente (dono define; sem ela o
  despachante é no-op — `app.py:436`).
- Job diário do EasyPanel: `flask emitir-propostas-expirando`
  (comando de `notificacoes_cli.py:130`, registrado em `app.py:1043`;
  use `--dry-run` para validar antes de armar o cron).

## Cobertura ociosa (job mensal já existente)

- Hoje roda via APScheduler in-process (`app.py:1089-1092`, dia 1 às 06:00,
  timezone America/Sao_Paulo).
- Ao criar os jobs externos acima, migrar este também:
  `flask cobertura-ociosa` (comando de `cobertura_ociosa_cli.py:17`,
  registrado em `app.py:1046`) no cron do dia 1, e `SCHEDULER_ENABLED=0`
  no serviço web.

## Antes de qualquer deploy que contenha as tasks de 01/09

- `DATABASE_URL=<prod> python scripts/medir_funcionarios_sem_admin_id.py` —
  mede quantos usuários passam a receber 403 com a falha-fechada do tenant
  (Task 10/11); o reparo é preencher `usuario.admin_id`.
- Regenerar `cache_facial.pkl` (`python gerar_cache_facial.py`) — a Task 8
  trocou o engine facial para o SFace nativo; os floats são os mesmos, mas a
  regeneração é a prova operacional.
- O rateio de encargos (A24) sobe DESLIGADO; liga-se por
  `python scripts/flag_folha_rateio_encargos.py <admin_id> --ligar` depois de
  ratificar com o dono (custo de obra sobe ~28% na mão de obra).
