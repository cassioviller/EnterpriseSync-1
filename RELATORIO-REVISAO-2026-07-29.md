# Revisão de código — 29/07/2026 (Fase 6 do cronograma + Fase 9a)

> **Status: concluída. 10 achados, 10 corrigidos**, cada um com teste que foi
> verificado **falhando contra o código anterior** antes de a correção ser
> aceita. Todas as correções estão nos dois commits de feature deste branch —
> nenhum commit desta série contém o código vulnerável.

Duas passagens de revisão:

1. **Interrompida** (`wf_c7e4f5d5-7b3`), parada no meio para troca de modelo.
   O `journal.jsonl` gravou `null` para os agentes concluídos, então retomar
   por `resumeFromRunId` devolveria vazio; os achados foram resgatados à mão
   dos transcripts. Serviram de pista, não de verdade.
2. **Completa** (`wf_ac53f780-d12`), relançada do zero com instrução explícita
   de reverificar tudo — 41 agentes, verificação adversarial por achado.

O que a segunda passagem mudou em relação à primeira: derrubou candidatos que
pareciam sólidos, e encontrou dois defeitos que a primeira não alcançou (a
migração que não roda em ambiente novo e a sessão que não é revogada).

---

## Achados e correções

### 1. Vazamento entre tenants — `views/obras.py`

`editar_obra` usava `Obra.query.get_or_404(id)` **sem filtro de `admin_id`**.
O bug já existia; a Fase 9a o tornou grave ao pendurar ali a lista de
responsáveis do cliente — nome, e-mail, último acesso, estado da senha.

Corrigido com `obras_visiveis().filter(Obra.id == id).first_or_404()`, que
resolve tenant **e** escopo por obra de uma vez e mantém o 404 opaco.
`_obra_do_tenant` passou a usar a mesma fechadura.

### 2. CSRF ausente nas rotas de signatário — `views/obras.py`

As três rotas de mutação vivem no blueprint `main`, isento de CSRF em bloco
(`app.py:1051`). Um POST forjado de outra aba trocava a senha do responsável
do cliente usando o cookie de um funcionário logado; contra `/toggle`, tirava
a pessoa do denominador e um RDO "2 de 3" passava a ler "2 de 2 — Ciência
completa".

Criado o decorator `exige_csrf`, que reativa `csrf.protect()` só onde o risco
está. **Ele respeita `WTF_CSRF_ENABLED`** — a primeira versão não respeitava e
rejeitava todo POST da suíte, o que fez os testes de escopo passarem pelo
motivo errado (*"nada foi criado"* também é o resultado de um bloqueio de
CSRF).

A isenção do blueprint inteiro **não** foi removida: ela cobre dezenas de
rotas legadas cujo front pode não mandar token, e virar isso de uma vez
quebraria o sistema em lugares que esta revisão não olhou.

### 3. Migração 268 não removia o índice antigo — `migrations.py`

A 268 removia a unicidade antiga com `DROP CONSTRAINT IF EXISTS`, mas a
migração **262** cria aquele mesmo nome como `CREATE UNIQUE INDEX`. No
PostgreSQL, `DROP CONSTRAINT` contra um índice é **no-op silencioso**
(reproduzido numa tabela de rascunho no banco vivo).

Efeito em **instalação nova**: `db.create_all()` roda antes das migrações e a
tabela nasce sem a constraint; a 262 instala o índice global; a 268 não o
remove. O primeiro responsável dá ciência, o segundo estoura `IntegrityError`
— a feature de N signatários nasce morta. A suíte não acusava porque o banco
de desenvolvimento veio pelo caminho da constraint.

Adicionada a **migração 269**, que cobre as duas formas (constraint e depois
índice), garante os dois índices parciais e **falha em voz alta** se o nome
antigo sobreviver a ambos.

### 4. Rate-limit contornável — `portal_obras_views.py`

A chave usava a string crua de `signatario_id` enquanto `autenticar`
normaliza com `int()`: `5`, `05`, ` 5` e `+5` são a mesma conta em baldes
diferentes. Ciclando grafias, o limite nunca disparava e `falhas_login`
subia sempre — travando todos os responsáveis da obra em menos de um minuto.

Chave normalizada com o mesmo `int()`; entrada não numérica cai num balde
único para que varrer lixo também esbarre no limite.

### 5. Sessão não revogada ao trocar a senha — `portal_signatario_auth.py`

`sessao_atual` só reconferia `ativo`. A construtora gerava senha nova
acreditando ter cortado o acesso do intruso, e ele seguia assinando.

A sessão passou a carregar `cred` — impressão SHA-256 truncada do hash
vigente — conferida a cada acesso. Trocar a senha revoga toda sessão aberta.
Somado um **teto absoluto de 12h** desde o login (`ini`), porque a janela de
15 min é de *inatividade* e se renovava a cada page view: sem o teto, uma aba
em uso mantinha a sessão viva indefinidamente. `ciencia_trocar_senha` reabre a
sessão, para que trocar a própria senha não deslogue quem se protegeu.

### 6. Enumeração de contas — `portal_signatario_auth.py`

"Bloqueado" e "senha temporária venceu" eram reportados **antes** de
`check_password_hash`. O dropdown de nomes do portal é público: bastava
percorrê-lo com senha qualquer para mapear quais responsáveis estavam
travados e quais tinham senha da construtora não reivindicada — exatamente as
contas que valem atacar. O docstring justificava a exposição dizendo que "o
atacante já teria acertado a senha para chegar lá", o que não era verdade
porque a checagem vinha antes.

A conferência da senha passou para primeiro.

### 7. `IntegrityError` não tratado — `portal_obras_views.py`

`ja_assinou` não é atômica: em duplo-toque no celular os dois POSTs passam por
ela antes de qualquer commit e o índice parcial barra o segundo no flush.
Isso é `IntegrityError`, não `CienciaInvalida`, e escapava como **500 cru**
com a sessão sem rollback.

Adicionado o ramo com rollback, log e a mesma mensagem do caminho detectado —
o banco decidiu certo, a ciência está registrada, só não por aquela
requisição.

### 8. Alvo obsoleto no arrastar-para-aninhar — `templates/obras/cronograma.html`

`onMove` só dispara sobre itens da lista. Se o ponteiro cruzava a faixa
central de uma linha e depois saía da tabela, `_alvoNest` ficava armado e o
`onEnd` aninhava numa linha onde o cursor já não estava — em vez de reordenar,
como fazia antes da Fase 6.

O alvo passou a ser reconferido no `onEnd` contra as coordenadas reais do
soltar (`_soltouSobreOAlvo`), com as mesmas constantes `NEST_MIN`/`NEST_MAX`
das duas checagens. Sem coordenadas legíveis devolve `false` e o gesto vira
reordenação.

### 9. Senha temporária na query string — `views/obras.py`

`?senha_gerada=...` ia para histórico e autocomplete do navegador, log de
acesso do gunicorn/EasyPanel e header `Referer` de todo asset de terceiro —
derrotando o desenho de `gerar_senha_temporaria`, que devolve o texto claro
exatamente uma vez *"porque não há como recuperá-la depois"*.

Passou a viajar pela sessão Flask, consumida na primeira renderização. O
redirect não carrega mais querystring alguma.

### 10. IP probatório forjável — `services/rdo_ciencia_cliente.py`

`_contexto_request` parseava `X-Forwarded-For` à mão e pegava o salto **mais
à esquerda** — que é o que o cliente escreve. Postar `X-Forwarded-For:
8.8.8.8` ao assinar gravava esse IP num registro que o módulo apresenta como
evidência de autoria sob a MP 2.200-2/2001.

Passou a usar `request.remote_addr`, que o `ProxyFix(x_for=1)` (`app.py:94`)
já resolveu promovendo o salto mais à **direita** — o que o proxy confiável
escreveu. Mesma implementação da irmã em `services/rdo_assinatura`.

---

## Verificação

Cada correção tem teste, e cada teste foi executado contra o código anterior
para confirmar que falhava. Os que não podiam ser reproduzidos no ambiente
compartilhado foram isolados:

* a **migração 269** é testada numa tabela de rascunho, porque a
  `rdo_assinatura` deste banco já tem RDOs com duas assinaturas de cliente
  (a feature funciona aqui) e recriar o índice global falharia no setup;
* o **arrastar-para-aninhar** é testado extraindo a função do template e
  exercitando a geometria no Node, porque o Playwright não sobe neste
  ambiente (`libnspr4.so` ausente).

```
tests/test_rdo_ciencia_cliente.py + grade + undo     104 passed
regressão rdo/portal/obra/cronograma                1136 passed
```

Os 5 fracassos e 48 erros restantes são **todos** Playwright, idênticos ao
estado anterior às correções — verificado que nenhum é de outra natureza. Os
testes de browser continuam sem cobertura executável neste ambiente.

## Pendência conhecida

O manual em PDF do cronograma (`static/docs/manual-cronograma.pdf`) teve o
texto e a tabela de atalhos atualizados para a Fase 6, mas **as seis capturas
de tela continuam as antigas** e não mostram os botões novos da barra.
Regerá-las exige `scripts/manual_cronograma_capturas.py`, que depende do
Chromium indisponível aqui.
