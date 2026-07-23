# Fase 3 — runbook de rollout

Duas coisas foram entregues, e elas têm riscos diferentes.

**As correções de segurança do portal (Task 10) já estão valendo** assim
que o código sobe — não há flag. São elas:

- `/portal/obra/<token>/compra/<id>/aprovar` recusa compra que não seja
  `tipo_compra='aprovacao_cliente'` (já vinha da Fase 0.6/D2, via
  `_get_compra_do_portal`);
- token do portal expira em 180 dias, carimbado a cada `toggle_portal`;
- os cinco POSTs anônimos gravam IP e user-agent em `portal_acesso_evento`.

**O resto está atrás de `compras_governanca_ativa`, desligada por
padrão.** Todo o risco está em ligá-la.

## Antes de ligar, por tenant

1. **Confira as faixas de alçada.**

       python -c "
       from app import app
       from models import FaixaAlcada
       with app.app_context():
           for f in FaixaAlcada.query.filter_by(admin_id=<ID>).order_by(FaixaAlcada.ordem):
               print(f.ordem, f.valor_ate, f.aprovacoes_necessarias,
                     f.exige_admin, f.exige_mapa_concorrencia)
       "

   Os valores semeados (R$ 5.000 / R$ 30.000 / acima) são a
   **recomendação do plano**, não uma decisão do negócio. Confirme com o
   Cássio antes de ligar. Editar é UPDATE na tabela — não precisa de
   deploy.

2. **Confira que existe quem aprove.** Toda obra ativa do tenant precisa
   de pelo menos um `UsuarioObra` com papel `GESTOR` **que não seja o
   solicitante habitual**, senão as requisições daquela obra travam.

       python -c "
       from app import app
       from models import Obra, UsuarioObra, PapelObra
       with app.app_context():
           for o in Obra.query.filter_by(admin_id=<ID>, ativo=True):
               n = UsuarioObra.query.filter_by(obra_id=o.id, papel=PapelObra.GESTOR, ativo=True).count()
               if n == 0:
                   print('SEM GESTOR:', o.id, o.nome)
       "

   `ADMIN` sempre pode aprovar, então uma obra sem gestor não fica
   bloqueada — mas concentra tudo no dono da empresa.

3. **Confira que existe quem compre.** Pelo menos um `UsuarioObra` com
   papel `COMPRADOR`, ou o ADMIN vira o único que emite pedido.

4. **Ligue a flag.**

       python scripts/flag_compras_governanca.py <ID> --ligar

   O script recusa se o tenant não tiver faixa de alçada ativa.

5. **Faça o ciclo completo numa obra piloto**, com três pessoas
   diferentes: um cria a requisição, outro aprova, um terceiro emite o
   pedido. Confirme que o `GestaoCustoFilho` gerado tem `obra_id`
   preenchido.

## Rollback

Um comando, sem tocar em schema:

    python scripts/flag_compras_governanca.py <ID> --desligar

`compras.nova_post` volta a aceitar pedido direto no mesmo minuto. As
requisições já criadas continuam lá, inertes; as aprovadas continuam
podendo virar pedido.

As correções do portal (Task 10) **não têm rollback por flag**. Se uma
delas quebrar um cliente em produção, o caminho é reverter o commit —
e, no caso específico da expiração, `UPDATE obra SET
token_cliente_expira_em = NULL WHERE id = <ID>` devolve o acesso àquela
obra sem mexer em código.

## O que a Fase 3 deliberadamente NÃO fez

- **Não trocou o token do portal por login de cliente.** É a Fase 9a, e
  exige cadastro e recuperação de senha para o cliente — decisão de
  produto. Aqui o token ganhou prazo e trilha; continua sendo um sistema
  de identidade paralelo, sem escopo de ação.
- **Não criou `Recebimento` como entidade.** O recebimento parcial por
  item já existe (`compras_views.py:841-948`) e não foi refeito. O que
  falta é o recebimento ser o **gatilho** da obrigação financeira, em vez
  de o financeiro nascer no registro da compra — isso é Fase 4/8, e mexe
  em `processar_compra_normal`.
- **Não criou avaliação de fornecedor.** Sem verbo nesta fase; é
  candidata natural da Fase 8 (o dado de desempenho vem do recebimento).
- **Não tornou `pedido_compra.obra_id` NOT NULL.** Isso é Fase 4 e é a
  migração mais cara do roadmap: exige classificar os registros órfãos
  antes. O que a Fase 3 fez foi garantir que todo pedido **emitido por
  requisição** já nasce com obra.
- **Não amarrou o almoxarifado a papel.** `views/almoxarifado/*.py`
  continua com `@login_required` puro em ~20 rotas. O papel `COMPRADOR`
  agora existe e é o primeiro candidato a consumi-lo — mas trancar essas
  rotas hoje tiraria acesso de campo. Decisão D5.
- **Não migrou o `MapaConcorrencia` V1** (`models.py:5512`). Ele
  continua vivo em paralelo ao V2. A requisição só se liga ao V2
  (`RequisicaoCompra.mapa_v2_id`).
- **Não mexeu em `GestaoCustoPai`,** que continua sem coluna `obra_id`
  (a obra vive em `entidade_id`, um inteiro sem FK — `models.py:5227`).
  É Fase 4.
