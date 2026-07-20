"""Parser MSPDI (MS Project XML) — stdlib pura, sem JVM.

MSPDI é o formato de "Salvar como → XML" do MS Project. Este parser
existe para que produção importe cronograma sem MPXJ/JPype/JDK.
Paridade com o parser MPXJ medida em 2026-07-20 sobre 261 tarefas
(3 arquivos, incluindo export real do Project — BuildNumber
16.0.19725.20170), zero divergências nos 9 campos legados — ver
docs/superpowers/plans/2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md.
Os campos estendidos (uid/wbs/marco/tipo/lag_dias) são verificados pela
Task 2 de 2026-07-20-modulo-03-implementacao-upload-parser.md via
scripts/verificar_paridade_mspdi.py.

Contrato de saída (plano M03, §"Contrato de saída do parser"):

    {"projeto": {"nome": str, "data_status": str|None},
     "tarefas": [{"id", "uid", "wbs", "outline", "nome", "inicio", "fim",
                  "dias", "pct_project", "resumo", "marco",
                  "predecessoras": [{"id", "uid", "tipo", "lag_dias"}],
                  "notas"}]}
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

NS = {'m': 'http://schemas.microsoft.com/project'}
_ROOT = '{http://schemas.microsoft.com/project}Project'

# MSPDI grava duração em ISO-8601 (PT16H0M0S, P2DT4H...). A app trabalha
# em dias úteis; 8h = 1 dia é a jornada padrão do MS Project. Tarefa com
# calendário não-padrão pode divergir — ver §3.3 do adendo.
_HORAS_POR_DIA = 8.0
_DUR = re.compile(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?')

# <PredecessorLink><Type> → tipo de vínculo. Tabela CANDIDATA — a Task 2
# do plano M03 confirma contra o MPXJ (RelationType por vínculo) nos 3
# pares de arquivos do repo antes de remover o marcador abaixo.
_TIPO_VINCULO = {0: 'FF', 1: 'FS', 2: 'SF', 3: 'SS'}  # VERIFICAR-T2

# <LinkLag> vem em décimos de minuto: 4800 = 480 min = 8 h = 1 dia útil.
_LAG_POR_DIA = 4800.0


def _duracao_dias(texto):
    if not texto:
        return None
    m = _DUR.match(texto)
    if not m:
        return None
    dias, horas, minutos, segundos = (float(x) if x else 0.0 for x in m.groups())
    return round(dias + (horas + minutos / 60 + segundos / 3600) / _HORAS_POR_DIA, 4)


def _data(texto):
    """'2026-07-06T08:00:00' → '2026-07-06'; vazio/None → None."""
    return (texto or '')[:10] or None


def parse_mspdi(caminho: str) -> dict:
    """Lê um MSPDI e devolve o contrato completo {"projeto", "tarefas"}."""
    root = ET.parse(caminho).getroot()
    if root.tag != _ROOT:
        raise ValueError(f'arquivo não é MSPDI (root={root.tag!r})')

    projeto = {
        'nome': (root.findtext('m:Title', namespaces=NS)
                 or root.findtext('m:Name', namespaces=NS)
                 or '').strip() or None,
        'data_status': _data(root.findtext('m:StatusDate', namespaces=NS)),
    }

    tarefas_xml = root.findall('m:Tasks/m:Task', NS)

    # Passada 1: mapa UID -> ID. O MSPDI referencia predecessoras por UID,
    # mas a app (e o parser MPXJ) trabalha com ID. Sem este mapa as
    # predecessoras saem silenciosamente erradas (§2 do adendo).
    uid_para_id = {}
    for t in tarefas_xml:
        uid = t.findtext('m:UID', namespaces=NS)
        tid = t.findtext('m:ID', namespaces=NS)
        if uid is not None and tid is not None:
            uid_para_id[int(uid)] = int(tid)

    tarefas = []
    for t in tarefas_xml:
        def campo(tag):
            return t.findtext(f'm:{tag}', default=None, namespaces=NS)

        if campo('ID') is None:
            continue

        predecessoras = []
        for link in t.findall('m:PredecessorLink', NS):
            uid_pred = link.findtext('m:PredecessorUID', namespaces=NS)
            if uid_pred is None:
                continue
            uid_pred = int(uid_pred)
            id_pred = uid_para_id.get(uid_pred)
            if id_pred is None:
                continue  # vínculo externo/cross-project: fora do grafo local
            tipo_raw = link.findtext('m:Type', namespaces=NS)
            lag_raw = link.findtext('m:LinkLag', namespaces=NS)
            predecessoras.append({
                'id': id_pred,
                'uid': uid_pred,
                'tipo': _TIPO_VINCULO.get(int(tipo_raw)) if tipo_raw is not None else None,
                'lag_dias': (int(lag_raw) / _LAG_POR_DIA) if lag_raw is not None else 0.0,
            })

        tarefas.append({
            'id': int(campo('ID')),
            'uid': int(campo('UID')) if campo('UID') is not None else None,
            'wbs': campo('WBS'),
            'outline': int(campo('OutlineLevel')) if campo('OutlineLevel') else None,
            'nome': (campo('Name') or '').strip(),
            'inicio': _data(campo('Start')),
            'fim': _data(campo('Finish')),
            'dias': _duracao_dias(campo('Duration')),
            'pct_project': float(campo('PercentComplete')) if campo('PercentComplete') else None,
            'resumo': campo('Summary') == '1',
            'marco': campo('Milestone') == '1',
            'predecessoras': predecessoras,
            'notas': (campo('Notes') or '').strip() or None,
        })

    return {'projeto': projeto, 'tarefas': tarefas}
