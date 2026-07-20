# Adendo ao Módulo 3 — caminho MSPDI XML sem JVM

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development ou superpowers:executing-plans. Este documento **revisa** `2026-07-17-modulo-03-upload-parser-mpp.md` §4.1/§4.2/§19/§20 — não o substitui. Ler o M03 antes.

**Goal:** Permitir que produção importe cronograma sem JVM, aceitando MSPDI XML (`.xml`) parseado com a stdlib, mantendo o caminho `.mpp`/MPXJ como opcional.

**Architecture:** Dois leitores atrás de um contrato único. `.xml` (MSPDI) → `xml.etree.ElementTree` da stdlib, zero dependências. `.mpp` → MPXJ/JPype em subprocess, **só se** a toolchain Java existir. A app degrada com mensagem acionável em vez de quebrar.

**Tech Stack:** `xml.etree.ElementTree` (stdlib), `re` (stdlib). MPXJ/JPype/JDK passam a ser opcionais.

---

## 1. Por que este adendo existe

O M03 assume MPXJ como parser canônico e trata a ausência de JVM como "contingência" resolvida por upload de `.json` gerado manualmente por um dev (o fluxo atual das baias). Medição feita em 2026-07-20 mostra que existe caminho melhor: o **MSPDI XML** — formato de exportação nativo do MS Project (*Salvar como → XML*) — entrega os mesmos dados com parser de ~30 linhas de stdlib.

## 2. Evidência medida

Método: `UniversalProjectReader` lê o `.mpp` e `MSPDIWriter` grava o MSPDI; um parser stdlib lê esse XML; compara-se campo a campo com a saída de `scripts/dump_mpp.py::dump` (o parser canônico atual) sobre o mesmo arquivo.

```
CRONOGRAMA 06.07.mpp       mpxj= 101  purepy= 101  ids_iguais=True  divergencias=0
CRONOGRAMA OFICIAL.mpp     mpxj=  57  purepy=  57  ids_iguais=True  divergencias=0
CRONOGRAMA 16.07.mpp/.xml  mpxj= 103  purepy= 103  ids_iguais=True  divergencias=0   ← XML REAL do Project
```

261 tarefas, 8 campos comparados (`outline`, `nome`, `inicio`, `fim`, `dias`, `pct_fisico`, `predecessoras`, `resumo`), **zero divergências**.

**Atualização 2026-07-20 (mesma data, mais tarde): a Task 1 foi cumprida.** O usuário forneceu `CRONOGRAMA 16.07.xml` exportado pelo **MS Project real** (`BuildNumber 16.0.19725.20170`, `standalone="yes"`) junto com o `.mpp` correspondente. O diff do parser stdlib sobre esse XML contra o baseline MPXJ sobre o `.mpp` deu **zero divergências em 103 tarefas** — a linha marcada acima. A ressalva da §3.1 está encerrada.

Detalhe que custou uma iteração e precisa ficar registrado: na primeira tentativa `predecessoras` divergiu em 66/101 tarefas. **Não era perda de dado** — o MSPDI referencia predecessoras por `UID`, enquanto `dump_mpp.py` usa `getID()`. Resolvido com um mapa `uid → id` construído em uma passada prévia sobre `<Task>`. Qualquer reimplementação que pule esse mapa vai produzir predecessoras silenciosamente erradas, e o grafo de dependências é justamente o que alimenta `recalcular_cronograma` (`utils/cronograma_engine.py:237`).

## 3. Limites desta evidência — leia antes de confiar

1. ~~**O MSPDI foi gerado pelo MPXJ, não pelo MS Project.**~~ **RESOLVIDO em 2026-07-20**: paridade verificada contra `CRONOGRAMA 16.07.xml`, export real do MS Project (BuildNumber 16.0.19725.20170) — 103 tarefas, zero divergências (§2). A Task 1 abaixo fica mantida como passo de regressão (rodar o script de paridade sobre esse par de arquivos), não mais como dúvida aberta.
2. **Três arquivos, uma origem.** Todos vieram do mesmo autor/empresa (`Guilherme Angelin` / `VEKS ENGENHARIA`, code page 1252) e provavelmente da mesma versão do Project. Não exercitam: calendários customizados, recursos atribuídos, vínculos SS/SF/FF, lag ≠ 0, marcos, campos personalizados.
3. **A comparação cobre os 9 campos que a app usa hoje**, não o formato. O M03 §4.1 quer ampliar a extração (`uid`, `wbs`, `marco`, `tipo` de vínculo, `lag_dias`, recursos, notas, custom). Esses campos **não foram medidos** — `dias` bate hoje porque as durações desses arquivos são inteiras em dias; a conversão ISO-8601 → dias assume jornada de 8h e vai divergir em tarefa com duração fracionária ou calendário não-padrão.

## 4. Revisão do M03

### 4.1 Substitui o M03 §4.1

`services/mpp_parser.py` expõe o mesmo contrato, com despacho por extensão:

- `.xml` → `services/mspdi_parser.py` (stdlib, in-process, sem subprocess — não há JVM para isolar).
- `.mpp` → worker MPXJ em subprocess, como o M03 já especifica.
- Se `.mpp` e `java_disponivel()` é falso → `MppParserError('java_indisponivel')`, cuja mensagem na UI **precisa** instruir a exportação: *"Este servidor não lê .mpp. No MS Project: Arquivo → Salvar como → tipo 'XML' (.xml), e suba o .xml."*

### 4.2 Substitui o M03 §4.2 (validações de upload)

- Extensões aceitas: `.xml` (MSPDI) e `.mpp`. O `.json` de contingência do M03 **sai** — era o fluxo manual das baias, que este caminho torna desnecessário.
- Magic bytes: `.mpp` → OLE2 (`D0 CF 11 E0 A1 B1 1A E1`, confirmado nos dois arquivos). `.xml` → validar que o root é `{http://schemas.microsoft.com/project}Project`, rejeitando XML arbitrário.
- **Segurança do XML:** `xml.etree.ElementTree` do CPython não expande entidades externas e levanta em DTD com entidades recursivas, mas o parse ocorre **antes** de qualquer escrita — casar com o limite de tamanho (≤ 20 MB) e o timeout do M03. Não usar `lxml` sem `resolve_entities=False`.

### 4.3 Substitui o M03 §20 (dependências)

MPXJ/JPype/JDK passam de "declarar em produção" para **opcionais**: se declarados, o `.mpp` funciona; se não, a app funciona com `.xml`. Isso remove +150-300 MB da imagem e tira a JVM do caminho crítico de deploy. Decisão de declarar ou não fica para o rollout (M10), não bloqueia o M03.

---

## Task 1: Retirar a dúvida da §3.1 — **CUMPRIDA em 2026-07-20** (vira regressão)

**Files:** nenhum — coleta de evidência.

- [x] **Step 1: Obter um MSPDI real**

O usuário forneceu `CRONOGRAMA 16.07.xml` (export do MS Project, BuildNumber 16.0.19725.20170) e o `CRONOGRAMA 16.07.mpp` correspondente, na raiz do projeto.

- [x] **Step 2: Rodar o diff de paridade contra o baseline MPXJ**

Feito inline (o script da Task 2 ainda não existia): baseline `dump_mpp.py::dump` sobre o `.mpp`, parser stdlib sobre o `.xml`.
Resultado: `mpxj=103 purepy=103 ids_iguais=True divergencias=0`.

- [x] **Step 3: Decidir**

`divergencias=0` → o caminho MSPDI está validado contra a fonte real. Seguir.

- [ ] **Step 4 (regressão, executar junto com a Task 2): reproduzir com o script**

Run: `.pythonlibs/bin/python scripts/verificar_paridade_mspdi.py "CRONOGRAMA 16.07.mpp" "CRONOGRAMA 16.07.xml"`
Expected: `divergencias=0` em 103 tarefas, exit 0.

---

## Task 2: Parser MSPDI em stdlib + script de paridade

**Files:**
- Create: `services/mspdi_parser.py`
- Create: `scripts/verificar_paridade_mspdi.py`
- Create: `tests/test_mspdi_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
"""M03 adendo — parser MSPDI stdlib extrai os campos que a app consome."""
import os
import pytest
from services.mspdi_parser import parse_mspdi

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'mspdi_minimo.xml')


def test_parse_mspdi_extrai_campos_e_mapeia_predecessora_por_uid():
    tarefas = parse_mspdi(FIXTURE)
    assert [t['id'] for t in tarefas] == [1, 2]
    raiz, filha = tarefas
    assert raiz['nome'] == 'Fundacao'
    assert raiz['resumo'] is True
    assert raiz['outline'] == 1
    assert filha['inicio'] == '2026-07-06'
    assert filha['fim'] == '2026-07-07'
    assert filha['dias'] == 2.0
    assert filha['pct_fisico'] == 50.0
    # UID 101 no XML deve virar ID 1 na saída — este é o bug sutil da §2.
    assert filha['predecessoras'] == [1]


def test_parse_mspdi_rejeita_xml_que_nao_e_mspdi(tmp_path):
    ruim = tmp_path / 'qualquer.xml'
    ruim.write_text('<?xml version="1.0"?><Qualquer/>', encoding='utf-8')
    with pytest.raises(ValueError, match='não é MSPDI'):
        parse_mspdi(str(ruim))
```

Criar a fixture `tests/fixtures/mspdi_minimo.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
  <Tasks>
    <Task>
      <UID>100</UID><ID>1</ID><Name>Fundacao</Name>
      <OutlineLevel>1</OutlineLevel><Summary>1</Summary>
      <Start>2026-07-06T08:00:00</Start><Finish>2026-07-07T17:00:00</Finish>
      <Duration>PT16H0M0S</Duration><PercentComplete>0</PercentComplete>
    </Task>
    <Task>
      <UID>101</UID><ID>2</ID><Name>Sapatas</Name>
      <OutlineLevel>2</OutlineLevel><Summary>0</Summary>
      <Start>2026-07-06T08:00:00</Start><Finish>2026-07-07T17:00:00</Finish>
      <Duration>PT16H0M0S</Duration><PercentComplete>50</PercentComplete>
      <PredecessorLink><PredecessorUID>100</PredecessorUID></PredecessorLink>
    </Task>
  </Tasks>
</Project>
```

Atenção: a predecessora aponta para `UID` 100, cujo `ID` é 1 — por isso o assert espera `[1]` e não `[100]`.

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.pythonlibs/bin/python -m pytest tests/test_mspdi_parser.py -p no:cacheprovider -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.mspdi_parser'`

- [ ] **Step 3: Implementar o parser**

Criar `services/mspdi_parser.py`:

```python
"""Parser MSPDI (MS Project XML) — stdlib pura, sem JVM.

MSPDI é o formato de "Salvar como → XML" do MS Project. Este parser
existe para que produção importe cronograma sem MPXJ/JPype/JDK.
Paridade com o parser MPXJ medida em 2026-07-20 sobre 158 tarefas
(2 arquivos), zero divergências nos 9 campos consumidos pela app —
ver docs/superpowers/plans/2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md
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


def _duracao_dias(texto):
    if not texto:
        return None
    m = _DUR.match(texto)
    if not m:
        return None
    dias, horas, minutos, segundos = (float(x) if x else 0.0 for x in m.groups())
    return round(dias + (horas + minutos / 60 + segundos / 3600) / _HORAS_POR_DIA, 4)


def parse_mspdi(caminho: str) -> list[dict]:
    """Lê um MSPDI e devolve a mesma estrutura de scripts/dump_mpp.py::dump."""
    root = ET.parse(caminho).getroot()
    if root.tag != _ROOT:
        raise ValueError(f'arquivo não é MSPDI (root={root.tag!r})')

    tarefas = root.findall('m:Tasks/m:Task', NS)

    # Passada 1: mapa UID -> ID. O MSPDI referencia predecessoras por UID,
    # mas a app (e o parser MPXJ) trabalha com ID. Sem este mapa as
    # predecessoras saem silenciosamente erradas.
    uid_para_id = {}
    for t in tarefas:
        uid = t.findtext('m:UID', namespaces=NS)
        tid = t.findtext('m:ID', namespaces=NS)
        if uid is not None and tid is not None:
            uid_para_id[int(uid)] = int(tid)

    saida = []
    for t in tarefas:
        def campo(tag):
            return t.findtext(f'm:{tag}', default=None, namespaces=NS)

        if campo('ID') is None:
            continue

        predecessoras = []
        for uid_el in t.findall('m:PredecessorLink/m:PredecessorUID', NS):
            alvo = uid_para_id.get(int(uid_el.text))
            if alvo is not None:
                predecessoras.append(alvo)

        saida.append({
            'id': int(campo('ID')),
            'outline': int(campo('OutlineLevel')) if campo('OutlineLevel') else None,
            'nome': (campo('Name') or '').strip(),
            'inicio': (campo('Start') or '')[:10] or None,
            'fim': (campo('Finish') or '')[:10] or None,
            'dias': _duracao_dias(campo('Duration')),
            'pct_fisico': float(campo('PercentComplete')) if campo('PercentComplete') else None,
            'predecessoras': predecessoras,
            'resumo': campo('Summary') == '1',
        })
    return saida
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.pythonlibs/bin/python -m pytest tests/test_mspdi_parser.py -p no:cacheprovider -q`
Expected: `2 passed`

- [ ] **Step 5: Criar o script de paridade**

Criar `scripts/verificar_paridade_mspdi.py`:

```python
"""Compara o parser MSPDI (stdlib) com o parser MPXJ (JVM) sobre o mesmo cronograma.

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

from services.mspdi_parser import parse_mspdi

CAMPOS = ['outline', 'nome', 'inicio', 'fim', 'dias', 'pct_fisico',
          'predecessoras', 'resumo']


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: python scripts/verificar_paridade_mspdi.py "<arquivo.mpp>" [<arquivo.xml>]')
    caminho_mpp = sys.argv[1]

    from dump_mpp import dump  # noqa: E402 — sobe a JVM
    baseline = {t['id']: t for t in dump(caminho_mpp)}

    if len(sys.argv) > 2:
        caminho_xml = sys.argv[2]
    else:
        import jpype
        from org.mpxj.reader import UniversalProjectReader
        from org.mpxj.mspdi import MSPDIWriter
        caminho_xml = caminho_mpp + '.mspdi.xml'
        MSPDIWriter().write(UniversalProjectReader().read(caminho_mpp), caminho_xml)
        print(f'[aviso] MSPDI gerado pelo MPXJ ({caminho_xml}) — nao prova paridade '
              f'contra export real do MS Project.')

    obtido = {t['id']: t for t in parse_mspdi(caminho_xml)}

    print(f'mpxj={len(baseline)} mspdi={len(obtido)} ids_iguais={set(baseline) == set(obtido)}')
    divergencias = 0
    for tid in sorted(set(baseline) & set(obtido)):
        for campo in CAMPOS:
            if baseline[tid][campo] != obtido[tid][campo]:
                divergencias += 1
                print(f'  id{tid}.{campo}: mpxj={baseline[tid][campo]!r} '
                      f'mspdi={obtido[tid][campo]!r}')
    print(f'divergencias={divergencias}')
    sys.exit(1 if divergencias or set(baseline) != set(obtido) else 0)


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    main()
```

- [ ] **Step 6: Rodar a paridade nos dois arquivos do repo**

Run: `.pythonlibs/bin/python scripts/verificar_paridade_mspdi.py "CRONOGRAMA 06.07.mpp"`
Expected: `divergencias=0`, exit 0 (com o aviso de MSPDI sintético).

Run: `.pythonlibs/bin/python scripts/verificar_paridade_mspdi.py "CRONOGRAMA OFICIAL.mpp"`
Expected: `divergencias=0`, exit 0.

- [ ] **Step 7: Commit**

```bash
git add services/mspdi_parser.py scripts/verificar_paridade_mspdi.py \
        tests/test_mspdi_parser.py tests/fixtures/mspdi_minimo.xml
git commit -m "feat(cronograma): parser MSPDI em stdlib, sem dependencia de JVM"
```

---

## Task 3: Despacho por extensão no contrato do M03

**Files:**
- Modify: `services/mpp_parser.py` (criado pelo M03 §4.1 — esta task pressupõe o M03 executado)
- Modify: `tests/test_mspdi_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_mspdi_parser.py`:

```python
def test_parse_cronograma_despacha_xml_sem_jvm(monkeypatch):
    """.xml não pode exigir Java nem subprocess."""
    from services import mpp_parser
    monkeypatch.setattr(mpp_parser, 'java_disponivel', lambda: False)
    tarefas = mpp_parser.parse_cronograma(FIXTURE)
    assert [t['id'] for t in tarefas] == [1, 2]


def test_parse_cronograma_mpp_sem_java_da_erro_acionavel(monkeypatch, tmp_path):
    from services import mpp_parser
    monkeypatch.setattr(mpp_parser, 'java_disponivel', lambda: False)
    falso = tmp_path / 'x.mpp'
    falso.write_bytes(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    with pytest.raises(mpp_parser.MppParserError) as exc:
        mpp_parser.parse_cronograma(str(falso))
    assert exc.value.motivo == 'java_indisponivel'
    assert 'Salvar como' in str(exc.value)
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.pythonlibs/bin/python -m pytest tests/test_mspdi_parser.py -p no:cacheprovider -q`
Expected: FAIL — `parse_cronograma` não existe.

- [ ] **Step 3: Implementar o despacho**

Acrescentar a `services/mpp_parser.py`:

```python
MSG_SEM_JAVA = (
    'Este servidor não lê arquivos .mpp. No MS Project: Arquivo → Salvar como → '
    "tipo 'XML' (.xml), e envie o .xml gerado."
)


def parse_cronograma(caminho: str, timeout_s: int = 120) -> list[dict]:
    """Ponto de entrada único. .xml → stdlib; .mpp → MPXJ em subprocess."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext == '.xml':
        from services.mspdi_parser import parse_mspdi
        return parse_mspdi(caminho)
    if ext == '.mpp':
        if not java_disponivel():
            raise MppParserError('java_indisponivel', MSG_SEM_JAVA)
        return parse_mpp(caminho, timeout_s=timeout_s)
    raise MppParserError('extensao_invalida', f'extensão não suportada: {ext!r}')
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.pythonlibs/bin/python -m pytest tests/test_mspdi_parser.py -p no:cacheprovider -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add services/mpp_parser.py tests/test_mspdi_parser.py
git commit -m "feat(cronograma): despacha .xml/.mpp e degrada sem JVM"
```

---

## Task 4: Alinhar os documentos

**Files:**
- Modify: `docs/superpowers/plans/2026-07-17-modulo-03-upload-parser-mpp.md` (§4.1, §4.2, §20)
- Modify: `docs/superpowers/plans/2026-07-17-cronograma-mpp-rdo-master-plan.md` (§1.1)

- [ ] **Step 1: Apontar o M03 para este adendo**

No cabeçalho do M03, após a linha `> Parte do plano mestre...`, inserir:

```markdown
> **REVISADO** por `2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md`: §4.1, §4.2 e §20 mudam — MSPDI XML (stdlib) é o caminho primário, MPXJ/JVM vira opcional. Ler o adendo junto.
```

- [ ] **Step 2: Corrigir §1.1 do plano mestre**

Após a frase que termina em `— **produção não parseia `.mpp`**.`, acrescentar:

```markdown
  Medido em 2026-07-20: isso deixa de ser bloqueio se a importação aceitar **MSPDI XML** (*Salvar como → XML* no MS Project), parseável com `xml.etree` da stdlib com paridade exata (158 tarefas, 2 arquivos, zero divergências nos 9 campos consumidos). Não existe leitor `.mpp` em Python puro — o formato é OLE2 proprietário; a única alternativa Python é comercial (Aspose.Tasks, que exige runtime .NET). Ver `2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/
git commit -m "docs(plano): MSPDI sem JVM revisa o M03 e o diagnostico do mestre"
```

---

## Critérios de aceite

1. `.xml` MSPDI importa sem JVM, sem subprocess e sem dependência nova.
2. `.mpp` sem Java falha com erro tipado `java_indisponivel` e mensagem que ensina a exportar.
3. Predecessoras mapeadas por `UID → ID`, com teste que falharia se o mapa fosse removido.
4. `scripts/verificar_paridade_mspdi.py` sai com `divergencias=0` nos dois `.mpp` do repo.
5. A dúvida da §3.1 (export real do Project) resolvida na Task 1, ou explicitamente registrada como aberta caso o usuário não forneça o arquivo.

## Riscos

| Risco | Mitigação |
|---|---|
| Export real do Project divergir do MSPDI do MPXJ | Task 1 bloqueia as demais; `scripts/verificar_paridade_mspdi.py` aceita o XML real como argumento |
| Jornada ≠ 8h/dia distorcer `dias` | `_HORAS_POR_DIA` isolado em constante; M03 §4.1 já prevê extrair calendário — quando existir, derivar daí |
| Usuário subir XML que não é MSPDI | Validação de root namespace + teste `test_parse_mspdi_rejeita_xml_que_nao_e_mspdi` |
| Campos novos do M03 (`wbs`, `marco`, `tipo`, `lag`) não medidos | Ampliar `CAMPOS` em `verificar_paridade_mspdi.py` junto com a extração, no M03 |
