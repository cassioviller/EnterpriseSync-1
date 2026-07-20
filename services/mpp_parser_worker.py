"""Worker MPXJ — `python -m services.mpp_parser_worker <arquivo.mpp>`.

Roda SEMPRE em subprocess (disparado por services/mpp_parser.py): o JPype
sobe uma JVM dentro do processo, e crash/OOM/travamento da JVM não pode
derrubar o gunicorn. Emite no stdout o MESMO contrato JSON de
services/mspdi_parser.py::parse_mspdi (plano M03, §"Contrato de saída do
parser"); qualquer erro vai para stderr com exit 1 — o orquestrador
tipifica o motivo a partir do stderr.

Dependências: pip install mpxj jpype1 + JRE/JDK COMPLETO (o jdk4py não
inclui o charset MacRoman dos .mpp) — resolução de JAVA_HOME herdada de
scripts/dump_mpp.py via services.mpp_parser._achar_java_home.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

from services.mpp_parser import _achar_java_home

# TimeUnit.toString() do MPXJ → fator para dias úteis (8h/dia, 5d/semana).
# Mesma tabela de scripts/verificar_paridade_mspdi.py (Task 2 do M03).
_FATOR_UNIDADE_DIA = {'d': 1.0, 'h': 1 / 8.0, 'm': 1 / 480.0, 'w': 5.0, 'mo': 20.0}


def _d(v):
    if v is None:
        return None
    try:
        return date(v.getYear(), v.getMonthValue(), v.getDayOfMonth()).isoformat()
    except Exception:
        s = str(v)[:10]
        return s if s[:4].isdigit() else None


def _num(v):
    if v is None:
        return None
    try:
        return float(v.doubleValue() if hasattr(v, 'doubleValue') else v)
    except Exception:
        try:
            return float(str(v))
        except Exception:
            return None


def _lag_dias(rel):
    """getLag() → dias úteis. Mesma conversão de verificar_paridade_mspdi.py."""
    lag = rel.getLag()
    if lag is None:
        return 0.0
    valor = float(lag.getDuration())
    unidade = str(lag.getUnits().toString())
    fator = _FATOR_UNIDADE_DIA.get(unidade)
    if fator is None:
        raise RuntimeError(f'unidade de lag do MPXJ não tratada: {unidade!r} '
                           f'(valor={valor}) — NÃO arredondar; tratar o formato.')
    # 6 casas: mesma canonicalização de services/mspdi_parser.py — sem isso os
    # dois caminhos divergem por ruído de float (ex.: 1.0000000002 vs 1.0).
    return round(valor * fator, 6)


def dump_contrato(caminho: str) -> dict:
    """Lê o .mpp via MPXJ e devolve o contrato completo {"projeto", "tarefas"}."""
    jh = _achar_java_home()
    if jh:
        os.environ['JAVA_HOME'] = jh
    import mpxj  # noqa: F401  (registra os .jar no classpath)
    import jpype
    import jpype.imports  # noqa: F401
    if not jpype.isJVMStarted():
        jpype.startJVM()
    from org.mpxj.reader import UniversalProjectReader

    project = UniversalProjectReader().read(caminho)
    if project is None:
        raise RuntimeError('formato de arquivo não reconhecido pelo MPXJ '
                           '(UniversalProjectReader devolveu null)')

    props = project.getProjectProperties()

    def _prop_texto(getter):
        if props is None:
            return None
        v = getter()
        return (str(v).strip() or None) if v is not None else None

    projeto = {
        # MSPDI toma o nome de <Title> com fallback <Name> (mspdi_parser.py);
        # espelhamos a MESMA precedência aqui (getProjectTitle == <Title>,
        # getName == <Name>) senão o .mpp real sai com nome=None — o <Name>
        # do arquivo é vazio e só <Title> carrega "Obra Itu - ...".
        'nome': _prop_texto(props.getProjectTitle) or _prop_texto(props.getName),
        'data_status': _d(props.getStatusDate()) if props is not None else None,
    }

    tarefas = []
    for t in project.getTasks():
        tid = t.getID()
        if tid is None:
            continue

        predecessoras = []
        for rel in (t.getPredecessors() or []):
            st = rel.getPredecessorTask()
            if st is None or st.getID() is None:
                continue
            uid_pred = st.getUniqueID()
            predecessoras.append({
                'id': int(st.getID().intValue()),
                'uid': int(uid_pred.intValue()) if uid_pred is not None else None,
                'tipo': str(rel.getType()),
                'lag_dias': _lag_dias(rel),
            })

        dur = t.getDuration()
        uid = t.getUniqueID()
        notas = t.getNotes()
        notas = (str(notas).strip() or None) if notas is not None else None
        tarefas.append({
            'id': int(tid.intValue()),
            'uid': int(uid.intValue()) if uid is not None else None,
            'wbs': str(t.getWBS()) if t.getWBS() is not None else None,
            'outline': int(t.getOutlineLevel().intValue()) if t.getOutlineLevel() is not None else None,
            'nome': str(t.getName() or '').strip(),
            'inicio': _d(t.getStart()),
            'fim': _d(t.getFinish()),
            'dias': _num(dur.getDuration()) if dur is not None else None,
            'pct_project': _num(t.getPercentageComplete()),
            'resumo': bool(t.getSummary()),
            'marco': bool(t.getMilestone()),
            'predecessoras': predecessoras,
            'notas': notas,
        })

    return {'projeto': projeto, 'tarefas': tarefas}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('uso: python -m services.mpp_parser_worker <arquivo.mpp>',
              file=sys.stderr)
        return 2

    # A JVM escreve no fd 1 por fora do sys.stdout do Python (medido em
    # 2026-07-20: "main ERROR Log4j API could not find a logging provider.")
    # e corromperia o JSON. Enquanto a JVM roda, o fd 1 aponta para o
    # stderr; o JSON sai pelo fd real, preservado via dup().
    stdout_real = os.dup(1)
    os.dup2(2, 1)
    try:
        dados = dump_contrato(argv[0])
    except Exception as exc:  # noqa: BLE001 — stderr é o canal de tipificação
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    finally:
        sys.stdout.flush()
    os.write(stdout_real, json.dumps(dados, ensure_ascii=False).encode('utf-8'))
    os.close(stdout_real)
    return 0


if __name__ == '__main__':
    sys.exit(main())
