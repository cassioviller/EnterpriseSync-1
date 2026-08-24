# RDO — Padrão de Preenchimento

Este capítulo é a **norma** do RDO. O capítulo anterior ensina onde clicar;
este define **o que precisa estar preenchido para o RDO ser aceito**.

> 📘 **Versão ilustrada:** [RDO, do cronograma à assinatura (PDF)](/static/docs/manual-rdo.pdf) —
> as mesmas regras, tela a tela, com as caixas numeradas. Regerável por
> `scripts/seed_manual_rdo.py` → `capturar_manual_rdo.py` → `gerar_manual_rdo.py`.

Ele existe porque o mesmo dia de obra hoje vira relatórios diferentes conforme
quem preenche. Um RDO que não permite reconstruir o dia não serve para medição,
não serve para produtividade e não serve como prova em discussão com o cliente.

## Regra geral

**Um RDO por obra, por dia trabalhado, lançado no mesmo dia.**

RDO lançado dias depois é reconstrução de memória: as horas arredondam, o
efetivo some e a ocorrência que importava não é registrada. Se o dia não teve
trabalho na obra, não se cria RDO.

O botão **Duplicar** cria um RDO **com a data de hoje**, para adiantar o
preenchimento a partir do dia anterior — não para corrigir um RDO que já
existe. Se hoje já tem RDO, não duplique: abra o que existe. O sistema **não
impede** dois RDOs no mesmo dia; quem garante o "um por dia" é quem preenche.

## 1. Efetivo próprio

Registre **todas** as pessoas da equipe própria que estiveram na obra, em cada
atividade em que trabalharam, com as horas.

- Use o botão de **equipe** (ícone de pessoas) na atividade.
- Só aparece pessoal **operacional**. Se alguém que trabalhou na obra não
  aparece na lista, a função dele está marcada como administrativa no cadastro
  — avise o escritório, não deixe de fora.
- Uma pessoa pode estar em mais de uma atividade no mesmo dia. Divida as horas
  entre elas; a soma tem de bater com a jornada.
- Se contratou ajudante avulso por alguns dias, ele precisa estar **cadastrado**
  antes de aparecer no RDO. Peça o cadastro ao escritório no primeiro dia — não
  no fim da semana, junto com o reembolso.

**Não é aceito:** escrever o efetivo em campo de observação, ou registrar só o
número de pessoas sem dizer quem.

## 2. Terceiros

Registre **cada equipe de terceiro** que trabalhou, na atividade em que
trabalhou, com o **nome do terceiro** e a **quantidade de pessoas**.

- Use o botão de **terceiro** (ícone de martelo) na atividade. Ele existe em
  qualquer atividade, inclusive nas que também têm equipe nossa.
- **Nome do terceiro**: o cadastro, não o apelido do dia. Se o terceiro não
  está cadastrado, peça o cadastro ao escritório.
- **Quantidade de pessoas**: quantas pessoas da equipe dele estavam na obra
  naquele dia. Este número é o que permite responder depois "o Abraão fez
  aquela fundação em quantos dias, com quantos homens".
- **Horas**: a jornada da equipe naquele dia.
- **Quantidade produzida**: preencha só quando houver medida física do dia
  (m², m³, unidades). Se não houver, deixe zero — registrar efetivo **não**
  move o avanço da atividade, e não é para mover.

**Não é aceito:** anotar "11 pessoas" em observação, ou deixar de registrar o
terceiro porque a atividade está marcada como nossa.

## 3. Avanço das atividades

Aponte o avanço **das atividades que andaram hoje**, e só delas.

- Atividade por **quantidade**: informe o que foi executado **hoje**, não o
  acumulado. O sistema soma.
- Atividade por **percentual**: informe o **percentual acumulado** da
  atividade, não o do dia.
- **Marco**: marque a caixa apenas no dia em que ele de fato ocorreu.
- Atividade que não andou fica **em branco**. Repetir o número da véspera para
  "não deixar vazio" cria avanço que não existiu.

**Não é aceito:** apontar 100% "porque está quase acabando".

## 4. Ocorrências

Registre toda ocorrência que **afetou ou pode afetar prazo, custo ou
segurança**, no dia em que aconteceu.

Entram, no mínimo:

- chuva ou condição que parou ou reduziu o serviço, **com o horário**;
- falta de material, equipamento ou frente de trabalho liberada;
- retrabalho e o motivo;
- acidente, quase-acidente ou interdição;
- visita ou determinação do cliente/fiscalização que mudou o combinado.

Escreva **o que aconteceu, quando e qual o efeito**. "Choveu" não é ocorrência;
"chuva das 10h às 14h, concretagem da sapata S3 adiada para o dia seguinte" é.

**Não é aceito:** deixar sem ocorrência um dia em que a produção caiu.

## 5. Fotos

Mínimo de **três fotos por dia**: uma da frente de serviço no início, uma do
que foi executado, e uma de qualquer ocorrência registrada.

- Foto de ocorrência é **obrigatória** quando a ocorrência é física (dano,
  interdição, material errado, alagamento).
- Foto tem de permitir identificar **o local**. Detalhe fechado sem referência
  não serve como prova depois.

## 6. Clima

Preencha o clima do dia. É o que sustenta a ocorrência de chuva quando ela vira
discussão de prazo com o cliente.

## 7. Fechamento

O RDO passa por estados, e cada um deles muda o que ainda dá para corrigir.
Vale a pena entender a sequência antes de precisar dela.

**Rascunho.** É como o RDO nasce, ao ser salvo pela tela de criação. Pode ser
editado à vontade, quantas vezes for preciso, durante o dia. Rascunho **não
lança custo**: o custo de mão de obra só entra no razão quando o dia é
submetido. Um RDO esquecido em rascunho é um dia sem fecho — sem custo, sem
assinatura, sem valor de documento.

**Submeter.** É o fecho do dia, no botão **Submeter** da tela do RDO. É aqui
que os custos de mão de obra são lançados, a medição é recalculada e o cliente
passa a enxergar o dia. Submeta **no fim do dia**, não no fim da semana.

**Corrigir depois de submeter.** Enquanto o RDO estiver *preenchido*, ele
continua corrigível: o gestor da obra usa **Reabrir**, o RDO volta a rascunho,
você corrige e submete de novo.

**Assinado e aprovado.** Depois de **Assinar** — e de **Aprovar**, que é o
aceite do gestor — o RDO fica **imutável**. Não é possível editá-lo, e isso é
proposital: a assinatura é o que dá a ele valor de documento.

**Retificar.** Achou um erro num RDO já assinado ou aprovado? Use **Retificar**.
O sistema emite um **novo RDO da mesma data**, dizendo o que o primeiro deveria
ter dito, e marca o original como *retificado* — ele fica preservado, e a
correção fica rastreável. É a prática de campo: um documento de data não se
apaga, se retifica.

**Nunca** crie um segundo RDO do mesmo dia "por fora" para consertar um erro.
Ou você reabre, ou você retifica.

## O que o escritório confere

Um RDO é devolvido para correção quando:

1. tem avanço apontado e **nenhum efetivo** (nem próprio, nem terceiro);
2. tem terceiro em observação em vez de registrado no campo próprio;
3. tem queda de produção **sem ocorrência** que a explique;
4. tem ocorrência física **sem foto**;
5. foi lançado com mais de **dois dias** de atraso;
6. ficou em **rascunho** — nesse caso não chega a ser devolvido: ele
   simplesmente não conta, e o dia aparece como se ninguém tivesse trabalhado.
