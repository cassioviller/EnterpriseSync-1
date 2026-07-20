"""Compara o parser MSPDI (stdlib) com o parser MPXJ (JVM) sobre o mesmo cronograma.

Duas camadas (Task 2 do plano M03):

1. **Legada** (9 campos): projeta o contrato novo de `parse_mspdi` para o
   shape de `scripts/dump_mpp.py::dump` (pct_fisico=pct_project,
   predecessoras=[ids]) e compara campo a campo.
2. **Estendida**: uid↔getUniqueID, wbs↔getWBS, marco↔getMilestone e, por
   vínculo, tipo↔RelationType (str) / lag_dias↔getLag convertido a dias.
   É esta camada que confirma a tabela _TIPO_VINCULO do parser.

Uso:
    python scripts/verificar_paridade_mspdi.py "<arquivo.mpp>" [<arquivo.xml>]

Sem o .xml, gera um MSPDI a partir do .mpp usando o próprio MPXJ — útil
como smoke, mas NÃO prova paridade contra um export real do MS Project.
Passe um .xml exportado pelo Project para a verificação que vale.
Requer JVM (só para produzir o baseline).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.mspdi_parser import parse_mspdi  # noqa: E402

CAMPOS_LEGADOS = ['outline', 'nome', 'inicio', 'fim', 'dias', 'pct_fisico',
                  'predecessoras', 'resumo']

# TimeUnit.toString() do MPXJ → fator para dias úteis (8h/dia, 5d/semana).
_FATOR_UNIDADE_DIA = {'d': 1.0, 'h': 1 / 8.0, 'm': 1 / 480.0, 'w': 5.0, 'mo': 20.0}


def projetar_legado(tarefa):
    """Contrato novo → shape de dump_mpp.py (9 campos)."""
    return {
        'id': tarefa['id'],
        'outline': tarefa['outline'],
        'nome': tarefa['nome'],
        'inicio': tarefa['inicio'],
        'fim': tarefa['fim'],
        'dias': tarefa['dias'],
        'pct_fisico': tarefa['pct_project'],
        'predecessoras': [p['id'] for p in tarefa['predecessoras']],
        'resumo': tarefa['resumo'],
    }


def _lag_dias_mpxj(rel):
    lag = rel.getLag()
    if lag is None:
        return 0.0
    valor = float(lag.getDuration())
    unidade = str(lag.getUnits().toString())
    fator = _FATOR_UNIDADE_DIA.get(unidade)
    if fator is None:
        raise RuntimeError(f'unidade de lag do MPXJ não tratada: {unidade!r} '
                           f'(valor={valor}) — NÃO arredondar; tratar o formato.')
    return valor * fator


def dump_mpxj_estendido(caminho_mpp):
    """{id: {uid, wbs, marco, vinculos: [(pred_id, tipo, lag_dias)]}} via MPXJ."""
    from dump_mpp import _achar_java_home
    jh = _achar_java_home()
    if jh:
        os.environ['JAVA_HOME'] = jh
    import mpxj  # noqa: F401
    import jpype
    import jpype.imports  # noqa: F401
    if not jpype.isJVMStarted():
        jpype.startJVM()
    from org.mpxj.reader import UniversalProjectReader

    project = UniversalProjectReader().read(caminho_mpp)
    out = {}
    for t in project.getTasks():
        tid = t.getID()
        if tid is None:
            continue
        vinculos = []
        for rel in (t.getPredecessors() or []):
            st = rel.getPredecessorTask()
            if st is None or st.getID() is None:
                continue
            vinculos.append((
                int(st.getID().intValue()),
                str(rel.getType()),
                round(_lag_dias_mpxj(rel), 6),
            ))
        uid = t.getUniqueID()
        out[int(tid.intValue())] = {
            'uid': int(uid.intValue()) if uid is not None else None,
            'wbs': str(t.getWBS()) if t.getWBS() is not None else None,
            'marco': bool(t.getMilestone()),
            'vinculos': sorted(vinculos),
        }
    return out


def projetar_estendido(tarefa):
    return {
        'uid': tarefa['uid'],
        'wbs': tarefa['wbs'],
        'marco': tarefa['marco'],
        'vinculos': sorted(
            (p['id'], p['tipo'], round(p['lag_dias'], 6))
            for p in tarefa['predecessoras']
        ),
    }


def verificar_par(caminho_mpp, caminho_xml=None):
    from dump_mpp import dump  # sobe a JVM
    baseline_legado = {t['id']: t for t in dump(caminho_mpp)}
    baseline_ext = dump_mpxj_estendido(caminho_mpp)

    if caminho_xml is None:
        import jpype  # noqa: F401 — JVM já de pé pelo dump()
        from org.mpxj.reader import UniversalProjectReader
        from org.mpxj.mspdi import MSPDIWriter
        caminho_xml = caminho_mpp + '.mspdi.xml'
        MSPDIWriter().write(UniversalProjectReader().read(caminho_mpp), caminho_xml)
        print(f'[aviso] MSPDI gerado pelo MPXJ ({caminho_xml}) — nao prova paridade '
              f'contra export real do MS Project.')

    contrato = parse_mspdi(caminho_xml)
    obtido_legado = {t['id']: projetar_legado(t) for t in contrato['tarefas']}
    obtido_ext = {t['id']: projetar_estendido(t) for t in contrato['tarefas']}

    ids_iguais = set(baseline_legado) == set(obtido_legado)
    print(f'mpxj={len(baseline_legado)} mspdi={len(obtido_legado)} '
          f'ids_iguais={ids_iguais}')

    divergencias = 0
    ids_comuns = sorted(set(baseline_legado) & set(obtido_legado))

    for tid in ids_comuns:
        for campo in CAMPOS_LEGADOS:
            if baseline_legado[tid][campo] != obtido_legado[tid][campo]:
                divergencias += 1
                print(f'  [legado] id{tid}.{campo}: '
                      f'mpxj={baseline_legado[tid][campo]!r} '
                      f'mspdi={obtido_legado[tid][campo]!r}')

    n_vinculos = 0
    for tid in ids_comuns:
        b, o = baseline_ext[tid], obtido_ext[tid]
        for campo in ('uid', 'wbs', 'marco'):
            if b[campo] != o[campo]:
                divergencias += 1
                print(f'  [estendido] id{tid}.{campo}: '
                      f'mpxj={b[campo]!r} mspdi={o[campo]!r}')
        n_vinculos += len(b['vinculos'])
        if b['vinculos'] != o['vinculos']:
            divergencias += 1
            print(f'  [estendido] id{tid}.vinculos: '
                  f'mpxj={b["vinculos"]!r} mspdi={o["vinculos"]!r}')

    print(f'vinculos_comparados={n_vinculos} divergencias={divergencias}')
    return 0 if divergencias == 0 and ids_iguais else 1


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: python scripts/verificar_paridade_mspdi.py '
                 '"<arquivo.mpp>" [<arquivo.xml>]')
    caminho_xml = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(verificar_par(sys.argv[1], caminho_xml))


if __name__ == '__main__':
    main()
