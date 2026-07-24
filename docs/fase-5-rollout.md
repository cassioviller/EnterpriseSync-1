# Fase 5 — runbook de rollout

Duas partes com riscos muito diferentes. **Não misture as duas no mesmo
deploy.**

| Parte | Tasks | Risco | Depende de humano? |
|---|---|---|---|
| Ciclo de vida + assinatura | 1–12, 16 | Baixo, aditivo | não |
| Migração das fotos | 13–15 | **Alto, destrutivo no passo final** | **sim** |

## Passo 0 — a dependência de `escopo_obra_ativo` (leia antes de tudo)

Mesma dependência dura da Fase 3 (achado nº 1 do review de 23/07,
generalizado na revisão de premissas como N3): **a diferenciação de
papel na assinatura só existe em tenant com `escopo_obra_ativo=TRUE`.**
Com a flag OFF — o default —, `papel_na_obra` devolve GESTOR a todo
autenticado do tenant (`utils/autorizacao.py`, decisão da Fase 1), e
portanto **qualquer um assina, aprova, reabre e retifica** RDO.

A Fase 5 não tem flag própria, de propósito: em tenant com a flag OFF a
assinatura ainda vale como **autoria** (a identidade vem de
`Usuario.funcionario_id` via `utils/identidade.py`, não do papel) e a
imutabilidade vale igual — o que não existe é o **controle de alçada**
(quem pode o quê). Antes de anunciar o fluxo assinar/aprovar num tenant,
confira a flag:

    python scripts/flag_escopo_obra.py <admin_id>            # consulta
    python scripts/flag_escopo_obra.py <admin_id> --ligar    # exige usuario_obra populada

## Parte A — ciclo de vida e assinatura

Aditiva por construção. Depois das migrations 260–264, todos os RDOs
existentes estão em `estado='preenchido'`, que é mutável — a
imutabilidade só passa a existir quando alguém clicar em "Assinar".

1. **Rode as migrations.**

       python -c "
       from app import app
       from migrations import executar_migracoes
       with app.app_context():
           executar_migracoes()
       " 2>&1 | grep -E "Migration 26[0-4]"

2. **Confira o backfill.** O número que importa é quantos RDOs ficaram
   em `assinado` — tem que ser **zero** (num banco recém-migrado; num
   banco onde a suíte já rodou, o invariante é assinado-sem-trilha == 0,
   ver `tests/test_fase5_rdo_ciclo_vida.py::test_backfill_marcou_os_rdos_historicos_como_preenchido`).

       python -c "
       from app import app, db
       from sqlalchemy import text
       with app.app_context():
           for linha in db.session.execute(text(
                   'SELECT estado, count(*) FROM rdo GROUP BY estado ORDER BY 2 DESC')):
               print(linha)
       "

3. **Confira que a guarda subiu.** No log do boot tem que aparecer
   `[OK] Fase 5: guarda de imutabilidade de RDO ativa`. Se aparecer o
   `[ERRO]`, o import de `services.rdo_ciclo_vida` falhou e **não existe
   imutabilidade nenhuma** — o resto da fase vira decoração.

4. **Assine um RDO de teste** numa obra de homologação e confirme que a
   tela recusa a edição depois.

### Rollback da parte A

Não precisa de rollback de schema. Um comando devolve todos os RDOs ao
comportamento mutável:

    UPDATE rdo SET estado = 'preenchido' WHERE estado IN ('assinado', 'aprovado');

As assinaturas e a trilha continuam gravadas — a informação de quem
assinou não se perde, só deixa de travar a edição.

## Parte B — migração das fotos (16 GB)

### Os seis pré-requisitos, todos bloqueantes

1. Volume persistente montado, **≥ 25 GB** livres (`df -h $UPLOADS_PATH`).
2. `UPLOADS_PATH` definido no painel do EasyPanel apontando para ele.
3. Task 13 **já em produção**. Sem ela, definir `UPLOADS_PATH` faz TODAS
   as fotos sumirem da tela no mesmo instante — `salvar_foto_rdo` grava
   em `$UPLOADS_PATH/rdo/…` e o `servir_foto` antigo procurava em
   `static/uploads/rdo/…`.
4. Dump COMPLETO do banco, com as fotos, guardado **fora** do servidor:

       python scripts/backup_banco.py        # 16 GB — NÃO use --sem-fotos

5. Snapshot do volume confirmado com a Hostinger (pendência já anotada em
   `ESTADO-ATUAL.md`).
6. Janela de manutenção para o `VACUUM FULL`, que trava a tabela.

### A ordem

    # 1. Ensaio: 50 fotos de um tenant, dry-run e depois aplicado
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50 --aplicar
    # → abra a tela de um RDO desse tenant e confirme que as fotos aparecem

    # 2. Tenant inteiro, passada 1 (reversível)
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID>
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --aplicar

    # 3. ESPERE UM CICLO DE DEPLOY.
    #    É a única forma de provar que o volume sobrevive ao restart —
    #    exatamente o que a base64 garantia e o que se está abrindo mão.

    # 4. Passada 2 em dry-run. Se `recusadas > 0`, PARE.
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar

    # 5. Passada 2 aplicada (DESTRUTIVA)
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar --aplicar

    # 6. Janela de manutenção: recupera o espaço
    VACUUM FULL ANALYZE rdo_foto;

### Rollback da parte B

| Momento | Rollback |
|---|---|
| Depois da passada 1 | `--reverter --aplicar`. Um comando; a base64 nunca saiu do banco |
| Depois da passada 2 | **Só restore do dump do pré-requisito 4.** Por isso o dump vem antes, e por isso o passo 3 existe |

## O que a Fase 5 deliberadamente NÃO fez

- **Não migrou o portal do cliente para servir foto por URL.**
  `rdo_crud.servir_foto` exige `@login_required` e o portal é por token.
  Criar a rota equivalente por token é Fase 9a, junto do login de
  cliente. Até lá `templates/portal/_portal_rdos.html` continua lendo
  `thumbnail_base64` — o que significa que a **passada 2 da parte B
  quebra a miniatura do portal** para as fotos liberadas (e as fotos
  NOVAS, sem base64 desde a Task 14, já caem no fallback de arquivo no
  detalhe e no ícone genérico na listagem). Decida com o Cássio: ou a
  Fase 9a vem antes da passada 2, ou o portal fica sem miniatura no
  intervalo.
- **Não unificou os oito caminhos de escrita de RDO.** A guarda
  `before_flush` os cobre todos, mas `views/rdo.py` continua com 5.000+
  linhas e seis rotas que fazem quase a mesma coisa. Refatoração é outra
  fase.
- **Não criou assinatura do cliente.** `RDOAssinatura.PAPEL_CLIENTE`
  existe e a coluna aceita, mas não há rota que o preencha — é Fase 9a.
- **Não implementou clima manhã/tarde, alerta de RDO em atraso nem
  link ocorrência→requisição**, que a `DEVOLUTIVA.md:243` lista junto
  desta fase. Clima manhã/tarde esbarra nos atributos fantasma
  `tempo_manha`/`tempo_tarde` que ainda são escritos sem efeito em
  `views/rdo.py` (escritas silenciosamente descartadas pelo SQLAlchemy);
  o link ocorrência→requisição depende de `Requisicao`, que é da Fase 3.
- **Não tocou no modo de apontamento** (percentual × quantidade). É o
  plano irmão `2026-07-21-cronograma-editavel-rdo-percentual.md`.
