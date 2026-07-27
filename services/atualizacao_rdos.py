"""Atualização NÃO-DESTRUTIVA dos RDOs de uma obra.

Por que este módulo existe: até 27/07/2026 o único caminho para entrar com
RDOs em lote era a seção `"rdos"` do reimport físico-financeiro
(`services/importacao_fisico_financeiro.py`). Aquele caminho:

  1. **apaga** tarefas, propostas, orçamentos, medições e TODOS os RDOs da
     obra antes de recriar (`_limpar_derivados` + a idempotência destrutiva
     de `_materializar_rdos`);
  2. é **recusado** em obra já versionada pela importação de cronograma
     (`_recusar_se_versionada_pelo_fluxo_novo`) — o caso da Baia depois da
     migração M09.

Ou seja: acrescentar sete dias de RDO ao diário de uma obra em andamento não
tinha caminho. Este módulo é esse caminho.

O que ele faz e o que NÃO faz:

  • upsert por `(obra_id, data_relatorio)` — dia novo cria, dia existente
    atualiza. Nada é apagado: nem RDO, nem tarefa, nem medição, nem proposta;
  • RDO em estado imutável da Fase 5 (assinado/aprovado/retificado) é
    **pulado com aviso**. Escrever nele levantaria `RDOImutavel` na guarda
    `before_flush` e derrubaria a transação inteira — o dia bom cairia junto
    com o dia travado;
  • apontamento vai por `cronograma_apontamento_service.registrar_apontamento`,
    não por escrita direta no modelo. É o único ponto que faz UPSERT por
    rdo+tarefa, valida retrocesso/sobre-execução/marco e honra a flag
    `rdo_percentual_livre`. (O import físico-financeiro ainda grava direto,
    no formato antigo — ver a docstring daquele serviço.);
  • `tarefa_mpp` que não resolve vira **pendência no relatório**, nunca
    silêncio. O `_materializar_rdos` descarta id desconhecido sem dizer nada,
    e um typo no JSON some sem rastro;
  • `dry_run=True` roda tudo e dá `rollback()` — o relatório sai igual, o
    banco fica intacto.

Formato de cada item de `rdos` (o mesmo da seção `"rdos"` do JSON canônico):

    {"data": "2026-07-14",
     "clima": "Não informado", "precipitacao": "Não informado",
     "comentario": "Efetivo: 05 colaboradores\\n\\nAtividades executadas:…",
     "mao_de_obra": 0,
     "fotos": [{"arquivo": "1.jpg", "legenda": "…"}],
     "apontamentos": [{"tarefa_mpp": 59, "pct": 65},
                      {"tarefa_mpp": 14, "quantidade": 10}]}

Chaves começadas por `_` (ex.: `_sugestoes`, escrito por
`scripts/whatsapp_para_rdos.py`) são ignoradas de propósito: servem à revisão
humana, não à gravação.
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import date

logger = logging.getLogger(__name__)

# Estado em que o RDO importado nasce. Mesma decisão do import
# físico-financeiro: RDO trazido de fora é histórico consolidado, não
# rascunho. Nascer 'rascunho' faria a UI oferecer "Submeter", e submeter
# dispararia `rdo_finalizado → lancar_custos_rdo` sobre medição que a
# importação já dirigiu — custo em dobro.
from services.rdo_ciclo_vida import PREENCHIDO, e_imutavel, estado_de


def _sem_acento(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto or '')
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def _data(valor):
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


class IndiceTarefas:
    """Resolve `tarefa_mpp` do payload → `TarefaCronograma` da obra.

    Dois critérios, nesta ordem:

      1. `mpp_uid` — gravado pelo importador de cronograma .mpp
         (`services/cronograma_versao_service.py`);
      2. nome normalizado, quando o caller informa `mapa_mpp_nome`
         (`{id_mpp: {"nome": …, "caminho": [ancestrais…]}}`, derivável da
         seção `cronograma_tarefas` do JSON canônico por
         `mapa_nomes_do_json`).

    ⚠️ O importador JSON **não grava `mpp_uid`** — ele só monta um
    `tid_to_db` em memória. Numa obra criada por JSON o critério 1 vem vazio
    e tudo depende do critério 2.

    O desempate NÃO pode ser só o pai imediato. No cronograma real da Baia a
    hierarquia é `Baias > Galpão A|B > Fundação > <tarefa>`: as duas
    "Execução de Ferragens Para Fundação" têm o MESMO pai ("Fundação") e só se
    distinguem no avô. Por isso o critério é a cadeia inteira de ancestrais —
    vence o candidato que cobre mais ancestrais do payload, e só se a vitória
    for única.
    """

    def __init__(self, obra_id, mapa_mpp_nome=None):
        from models import TarefaCronograma
        self.mapa_mpp_nome = mapa_mpp_nome or {}
        tarefas = TarefaCronograma.query.filter_by(
            obra_id=obra_id, ativa=True).all()
        self._por_id = {t.id: t for t in tarefas}
        self._por_uid = {}
        self._por_nome = {}
        self._ancestrais = {}
        for t in tarefas:
            if t.mpp_uid is not None:
                self._por_uid.setdefault(int(t.mpp_uid), []).append(t)
            self._por_nome.setdefault(_sem_acento(t.nome_tarefa), []).append(t)
        for t in tarefas:
            self._ancestrais[t.id] = self._subir(t)

    def _subir(self, tarefa):
        """Nomes normalizados de todos os ancestrais da tarefa."""
        nomes, atual, visto = set(), tarefa, set()
        while atual is not None and atual.id not in visto:
            visto.add(atual.id)
            atual = self._por_id.get(atual.tarefa_pai_id)
            if atual is not None:
                nomes.add(_sem_acento(atual.nome_tarefa))
        return nomes

    def _rotulo_ancestrais(self, tarefa):
        cadeia, atual, visto = [], tarefa, set()
        while atual is not None and atual.id not in visto:
            visto.add(atual.id)
            atual = self._por_id.get(atual.tarefa_pai_id)
            if atual is not None:
                cadeia.append(atual.nome_tarefa)
        return ' < '.join(cadeia) if cadeia else '—'

    def resolver(self, mpp_id):
        """Devolve (tarefa, motivo_da_pendencia). Um dos dois é None."""
        try:
            mpp_id = int(mpp_id)
        except (TypeError, ValueError):
            return None, f'tarefa_mpp inválido: {mpp_id!r}'

        candidatos = self._por_uid.get(mpp_id) or []
        if len(candidatos) == 1:
            return candidatos[0], None
        if len(candidatos) > 1:
            return None, (f'tarefa_mpp {mpp_id}: {len(candidatos)} tarefas '
                          f'ativas com o mesmo mpp_uid — resolva à mão')

        ref = self.mapa_mpp_nome.get(mpp_id) or self.mapa_mpp_nome.get(str(mpp_id))
        if not ref:
            return None, (f'tarefa_mpp {mpp_id}: nenhuma tarefa com esse '
                          f'mpp_uid e sem mapa de nomes para o fallback')

        nome = _sem_acento(ref.get('nome'))
        candidatos = self._por_nome.get(nome) or []
        if not candidatos:
            return None, (f'tarefa_mpp {mpp_id} ("{ref.get("nome")}"): '
                          f'nenhuma tarefa ativa com esse nome na obra')
        if len(candidatos) == 1:
            return candidatos[0], None

        caminho = [_sem_acento(n) for n in (ref.get('caminho') or []) if n]
        if not caminho and ref.get('pai'):
            caminho = [_sem_acento(ref['pai'])]
        if caminho:
            pontos = [(len(self._ancestrais.get(c.id, set()) & set(caminho)), c)
                      for c in candidatos]
            melhor = max(p for p, _ in pontos)
            vencedores = [c for p, c in pontos if p == melhor]
            if melhor > 0 and len(vencedores) == 1:
                return vencedores[0], None

        rotulos = sorted(self._rotulo_ancestrais(c) for c in candidatos)
        return None, (f'tarefa_mpp {mpp_id} ("{ref.get("nome")}"): '
                      f'{len(candidatos)} tarefas com esse nome e a cadeia de '
                      f'ancestrais não desempata (candidatos: '
                      f'{" | ".join(rotulos)}) — resolva à mão')


def _numero_rdo(obra_id, dia):
    return f'RDO-{obra_id}-{dia.strftime("%Y%m%d")}'


def _fotos_ja_anexadas(rdo_id):
    from models import RDOFoto
    return (RDOFoto.query.filter_by(rdo_id=rdo_id).count() or 0)


def atualizar_rdos(obra, admin_id, rdos, *, dry_run=False, com_fotos=True,
                   base_fotos=None, mapa_mpp_nome=None):
    """Cria/atualiza os RDOs de `obra` a partir do payload. NÃO apaga nada.

    Devolve o relatório:
        {'criados': [...], 'atualizados': [...], 'pulados': [...],
         'apontamentos': n, 'fotos': n, 'avisos': [...], 'pendencias': [...]}

    Com `dry_run=True` a transação é revertida no fim — o relatório é o mesmo.
    """
    from app import db
    from models import RDO
    from services.cronograma_apontamento_service import (
        ApontamentoInvalido, registrar_apontamento)
    from services.rdo_fotos_import import materializar_fotos_rdo
    from utils.cronograma_engine import sincronizar_percentuais_obra

    rel = {'criados': [], 'atualizados': [], 'pulados': [],
           'apontamentos': 0, 'fotos': 0, 'avisos': [], 'pendencias': []}

    # Aquece o calendário do tenant ANTES de abrir trabalho: `get_calendario`
    # cria o padrão e **comita** quando não existe (cronograma_engine), e
    # `registrar_apontamento` o chama lá no meio via `calcular_progresso_rdo`.
    # Sem isso, esse commit alheio levaria junto os RDOs pendentes e o
    # `dry_run` gravaria — foi exatamente o que aconteceu no 1º teste.
    from utils.cronograma_engine import get_calendario
    get_calendario(admin_id)

    indice = IndiceTarefas(obra.id, mapa_mpp_nome)
    itens = sorted((i for i in (rdos or []) if i.get('data')),
                   key=lambda i: _data(i['data']))

    try:
        for item in itens:
            dia = _data(item['data'])
            existentes = (RDO.query
                          .filter_by(obra_id=obra.id, data_relatorio=dia)
                          .order_by(RDO.id).all())
            if len(existentes) > 1:
                rel['avisos'].append(
                    f'{dia.isoformat()}: {len(existentes)} RDOs na mesma data — '
                    f'atualizando o primeiro (id={existentes[0].id})')
            rdo = existentes[0] if existentes else None

            if rdo is not None and e_imutavel(rdo):
                rel['pulados'].append({
                    'data': dia.isoformat(),
                    'motivo': f'RDO {rdo.numero_rdo} está {estado_de(rdo)} — '
                              f'para corrigir, emita um RDO retificador'})
                continue

            novo = rdo is None
            if novo:
                rdo = RDO(
                    numero_rdo=_numero_rdo(obra.id, dia),
                    obra_id=obra.id,
                    admin_id=admin_id,
                    criado_por_id=admin_id,
                    data_relatorio=dia,
                    local='Campo',
                    status='Finalizado',
                    estado=PREENCHIDO,
                )
                db.session.add(rdo)
                db.session.flush()   # precisa do rdo.id para foto/apontamento

            # Campos de texto: só sobrescreve o que veio no payload — dia sem
            # `comentario` não zera o comentário que já estava lá.
            if item.get('clima'):
                rdo.clima_geral = str(item['clima'])[:50]
            if item.get('precipitacao'):
                rdo.precipitacao = str(item['precipitacao'])[:20]
            if item.get('comentario'):
                rdo.comentario_geral = item['comentario']

            for ap in item.get('apontamentos') or []:
                tarefa, motivo = indice.resolver(ap.get('tarefa_mpp'))
                if tarefa is None:
                    rel['pendencias'].append(f'{dia.isoformat()}: {motivo}')
                    continue
                qtd = ap.get('quantidade')
                pct = ap.get('pct', ap.get('percentual'))
                if (qtd is None) == (pct is None):
                    rel['pendencias'].append(
                        f'{dia.isoformat()}: tarefa {ap.get("tarefa_mpp")} — '
                        f'informe exatamente um entre "quantidade" e "pct"')
                    continue
                try:
                    registrar_apontamento(
                        rdo, tarefa,
                        quantidade_dia=qtd,
                        percentual_acumulado=pct,
                        admin_id=admin_id,
                        permitir_retrocesso=bool(ap.get('permitir_retrocesso')),
                        justificativa=ap.get('justificativa'),
                        permitir_sobreexecucao=bool(ap.get('permitir_sobreexecucao')),
                    )
                except ApontamentoInvalido as e:
                    # Violação de regra de apontamento é dado errado, não bug:
                    # o dia continua, a linha vira pendência com a mensagem
                    # verbatim que a UI mostraria.
                    rel['pendencias'].append(
                        f'{dia.isoformat()}: tarefa {ap.get("tarefa_mpp")} '
                        f'("{tarefa.nome_tarefa}") — {e}')
                    continue
                rel['apontamentos'] += 1

            if com_fotos and item.get('fotos') and dry_run:
                # `salvar_foto_rdo` grava arquivo otimizado em disco — em
                # dry-run isso deixaria lixo que o rollback não desfaz.
                rel['avisos'].append(
                    f'{dia.isoformat()}: dry-run — {len(item["fotos"])} foto(s) '
                    f'NÃO processadas')
            elif com_fotos and item.get('fotos'):
                ja = _fotos_ja_anexadas(rdo.id)
                if ja:
                    rel['avisos'].append(
                        f'{dia.isoformat()}: RDO já tem {ja} foto(s) — álbum '
                        f'preservado, nada anexado (evita duplicar na 2ª rodada)')
                else:
                    rel['fotos'] += materializar_fotos_rdo(
                        rdo, admin_id, dia, item['fotos'],
                        base=base_fotos, prefixo_log='ATUALIZA_RDO')

            (rel['criados'] if novo else rel['atualizados']).append(dia.isoformat())

        db.session.flush()
        if dry_run:
            db.session.rollback()
            rel['avisos'].append('dry-run: transação revertida, nada gravado')
            return rel

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # Fora da transação de escrita: a sincronização comita por conta própria.
    sincronizar_percentuais_obra(obra.id, admin_id)
    return rel


def formatar_relatorio(rel, obra=None):
    """Relatório em texto para o CLI (e para colar no runbook)."""
    cab = f'[atualizacao_rdos] obra {obra.nome!r} (id={obra.id})' if obra \
        else '[atualizacao_rdos]'
    linhas = [
        cab,
        f'  criados:     {len(rel["criados"])}  {", ".join(rel["criados"])}',
        f'  atualizados: {len(rel["atualizados"])}  {", ".join(rel["atualizados"])}',
        f'  apontamentos gravados: {rel["apontamentos"]}',
        f'  fotos anexadas:        {rel["fotos"]}',
    ]
    if rel['pulados']:
        linhas.append(f'  pulados ({len(rel["pulados"])}):')
        linhas.extend(f'    - {p["data"]}: {p["motivo"]}' for p in rel['pulados'])
    if rel['pendencias']:
        linhas.append(f'  PENDÊNCIAS ({len(rel["pendencias"])}):')
        linhas.extend(f'    - {p}' for p in rel['pendencias'])
    if rel['avisos']:
        linhas.append(f'  avisos ({len(rel["avisos"])}):')
        linhas.extend(f'    - {a}' for a in rel['avisos'])
    return '\n'.join(linhas)


def mapa_nomes_do_json(payload):
    """`{id_mpp: {"nome":…, "pai":…, "caminho": [ancestrais]}}` a partir de
    `cronograma_tarefas`.

    A hierarquia sai do campo `nivel` — a mesma leitura que
    `_materializar_cronograma_mpp` faz na importação. O `caminho` traz TODOS
    os ancestrais, não só o pai: na Baia os dois galpões compartilham o pai
    "Fundação" e só se distinguem no avô ("Galpão A" × "Galpão B").
    """
    mapa, pilha = {}, {}
    for t in payload.get('cronograma_tarefas') or []:
        nivel = int(t.get('nivel') or 1)
        for n in list(pilha):
            if n >= nivel:
                del pilha[n]
        caminho = [pilha[n] for n in sorted(pilha)]
        pilha[nivel] = t.get('nome')
        mapa[int(t['id'])] = {
            'nome': t.get('nome'),
            'pai': caminho[-1] if caminho else None,
            'caminho': caminho,
        }
    return mapa
