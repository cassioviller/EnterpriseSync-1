"""
WhatsApp → payload de RDOs.

Converte um **export de conversa do WhatsApp** (o `.zip` que o app gera em
"Exportar conversa > Incluir mídia") no payload de RDOs que o sistema já
consome — a seção `"rdos"` de `cronograma_fisico_financeiro_baias.json`,
lida por `services/atualizacao_rdos.py` e por `_materializar_rdos`.

O caso real: o grupo "📝 Diário de Obras - Veks Engenharia", onde o Eng. Alan
posta o RDO de cada dia em texto (Efetivo / Atividades Executadas /
Observações / Próximas Atividades) seguido das fotos, cada uma com a legenda
na linha de baixo.

Três armadilhas do formato, todas tratadas aqui:

1. **A data do RDO é a do TEXTO, não a da mensagem.** O RDO de 07/07 foi
   postado em 08/07 às 08:59. Datar pela mensagem desloca a série inteira.
2. **A legenda é continuação da mensagem do anexo**, não uma mensagem nova.
3. **Nem todo bloco repete o marcador da obra** — o RDO de 22/07 começa em
   "RDO – 22/07/2026", sem "Obra Itu". Bloco sem marcador HERDA a obra do
   bloco anterior do mesmo autor, e a herança sai no relatório como aviso:
   é inferência, não leitura.

O de-para atividade→tarefa/% NÃO é adivinhado em silêncio. Com `--regras`,
cada bullet do texto é confrontado com um arquivo de regras revisável e vira
uma **sugestão** (`_sugestoes`), que só entra em `apontamentos` com
`--aplicar-sugestoes`. Bullet que não casa nenhuma regra vira pendência no
relatório — o oposto do `_materializar_rdos`, que descarta `tarefa_mpp`
desconhecido sem dizer nada.

Uso:
    python scripts/whatsapp_para_rdos.py --zip "conversa (2).zip" \\
        --obra-marcador "Obra Itu" --saida /tmp/payload_rdos.json

    # sem gravar nada (nem fotos, nem JSON): só o relatório
    python scripts/whatsapp_para_rdos.py --zip "conversa (2).zip" \\
        --obra-marcador "Obra Itu" --dry-run

Não abre banco nem importa o app — é texto puro, roda em milissegundos.
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import date

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Extensões que viram RDOFoto. Vídeo do WhatsApp (.mp4) é descartado com
# aviso: `salvar_foto_rdo` só processa imagem.
EXTENSOES_IMAGEM = ('.jpg', '.jpeg', '.png', '.webp')

# `DD/MM/AAAA HH:MM - resto`. Só a linha que casa isso abre mensagem nova;
# todas as outras são continuação da anterior (é assim que texto de RDO com
# parágrafos e bullets sobrevive à exportação).
RE_CABECALHO = re.compile(r'^(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2}) - (.*)$')
# Autor é opcional: mensagem de sistema ("As mensagens e ligações são
# protegidas...", "Fulano criou o grupo") vem sem "Autor:".
RE_AUTOR = re.compile(r'^([^:]{1,80}): (.*)$')
RE_ANEXO = re.compile(r'^(.+?) \(arquivo anexado\)$')
# "Obra Itu - RDO – 07/07/2026", "*Obra a Angela - RDO 14/07/2026*", "RDO – 22/07/2026"
RE_RDO = re.compile(r'\bRDO\b\s*[–—:-]?\s*(\d{2}/\d{2}/\d{4})')
# Formato antigo do grupo: primeira linha só com a data em negrito.
RE_DATA_SOZINHA = re.compile(r'^\*?(\d{2}/\d{2}/\d{4})\*?$')

# Títulos de seção como o WhatsApp traz → como ficam no comentário do RDO.
# Mantém o vocabulário dos 19 RDOs que já estão no JSON canônico.
TITULOS = (
    (re.compile(r'^atividades\s+executadas:?$', re.I), 'Atividades executadas:'),
    (re.compile(r'^atividades:?$', re.I), 'Atividades executadas:'),
    (re.compile(r'^observa[çc][õo]es:?$', re.I), 'Observações:'),
    (re.compile(r'^pr[óo]ximas\s+atividades\s*(previstas)?\s*(\([^)]*\))?:?$', re.I),
     None),  # preserva o "(08/07)" — tratado em _normalizar_titulo
)


def _sem_acento(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto or '')
        if unicodedata.category(c) != 'Mn'
    ).lower()


def _limpar_marcas(linha):
    """Tira as marcas de direção que o WhatsApp injeta antes de autor e anexo."""
    return linha.replace('‎', '').replace('‏', '').replace('﻿', '')


class Mensagem:
    """Uma mensagem do export: cabeçalho + corpo (com as continuações)."""

    __slots__ = ('data', 'hora', 'autor', 'corpo', 'anexo', 'legenda')

    def __init__(self, data, hora, autor, corpo):
        self.data = data
        self.hora = hora
        self.autor = autor
        self.corpo = corpo
        self.anexo = None
        self.legenda = ''

    def finalizar(self):
        """Separa anexo e legenda depois que as continuações já entraram."""
        linhas = self.corpo.split('\n')
        m = RE_ANEXO.match(linhas[0].strip())
        if m:
            self.anexo = m.group(1).strip()
            self.legenda = '\n'.join(linhas[1:]).strip()
        return self


class BlocoRDO:
    """Um dia de RDO: o texto do relatório + as fotos postadas na sequência."""

    def __init__(self, data_rdo, autor, texto, marcador, herdou_marcador):
        self.data_rdo = data_rdo          # datetime.date
        self.autor = autor
        self.texto = texto                # corpo cru da mensagem do RDO
        self.marcador = marcador          # marcador de obra lido ou herdado
        self.herdou_marcador = herdou_marcador
        self.anexos = []                  # [(nome_arquivo, legenda)]


def _parse_data(txt):
    d, m, a = txt.split('/')
    return date(int(a), int(m), int(d))


def parse_mensagens(texto):
    """Quebra o .txt exportado em mensagens, colando as continuações."""
    mensagens = []
    atual = None
    for linha_bruta in texto.split('\n'):
        linha = _limpar_marcas(linha_bruta.rstrip('\r'))
        cab = RE_CABECALHO.match(linha)
        if cab:
            if atual is not None:
                mensagens.append(atual.finalizar())
            data_txt, hora, resto = cab.groups()
            ma = RE_AUTOR.match(resto)
            if ma:
                autor, corpo = ma.group(1).strip(), ma.group(2)
            else:
                autor, corpo = None, resto      # mensagem de sistema
            atual = Mensagem(_parse_data(data_txt), hora, autor, corpo)
        elif atual is not None:
            atual.corpo += '\n' + linha
    if atual is not None:
        mensagens.append(atual.finalizar())

    # Export em outro formato de data (locale US: "7/8/26, 8:59 AM - ") não
    # casa RE_CABECALHO e sairia como "0 dia(s) de RDO" — resultado vazio que
    # parece "não teve RDO" em vez de "não entendi o arquivo". Falha alto.
    if not mensagens and texto.strip():
        raise ValueError(
            'Nenhuma mensagem reconhecida no export. O parser espera o formato '
            '"DD/MM/AAAA HH:MM - Autor: texto" (exportação em pt-BR). Confira '
            'o idioma/locale do celular que gerou o arquivo.')
    return mensagens


def _data_do_rdo(corpo):
    """Data que o RDO declara no próprio texto (não a data da mensagem)."""
    primeiras = [l.strip() for l in corpo.split('\n')[:3] if l.strip()]
    for linha in primeiras:
        m = RE_RDO.search(linha)
        if m:
            return _parse_data(m.group(1))
    for linha in primeiras[:1]:
        m = RE_DATA_SOZINHA.match(linha.replace('*', '*').strip())
        if m:
            return _parse_data(m.group(1))
    return None


def _marcador_no_texto(corpo, marcadores_conhecidos):
    """Qual marcador de obra aparece no cabeçalho do bloco, se algum."""
    cabeca = _sem_acento('\n'.join(corpo.split('\n')[:3]))
    for marcador in marcadores_conhecidos:
        if _sem_acento(marcador) in cabeca:
            return marcador
    return None


def agrupar_rdos(mensagens, marcador_obra, marcadores_conhecidos=()):
    """Junta cada mensagem de RDO com as fotos postadas até o próximo RDO.

    Devolve (blocos_da_obra, avisos). Bloco sem marcador herda o do bloco
    anterior do MESMO autor — e a herança vira aviso.
    """
    conhecidos = list(dict.fromkeys(list(marcadores_conhecidos) + [marcador_obra]))
    blocos, avisos = [], []
    ultimo_marcador_por_autor = {}
    atual = None

    for msg in mensagens:
        data_rdo = None if msg.anexo else _data_do_rdo(msg.corpo)
        if data_rdo is not None:
            marcador = _marcador_no_texto(msg.corpo, conhecidos)
            herdou = False
            if marcador is None:
                marcador = ultimo_marcador_por_autor.get(msg.autor)
                herdou = marcador is not None
            if marcador is not None:
                ultimo_marcador_por_autor[msg.autor] = marcador
            atual = BlocoRDO(data_rdo, msg.autor, msg.corpo, marcador, herdou)
            blocos.append(atual)
            continue
        if msg.anexo and atual is not None:
            atual.anexos.append((msg.anexo, msg.legenda))

    da_obra = []
    for b in blocos:
        if b.marcador != marcador_obra:
            continue
        if b.herdou_marcador:
            avisos.append(
                f'{b.data_rdo.isoformat()}: bloco sem marcador de obra no texto — '
                f'atribuído a "{marcador_obra}" pelo autor ({b.autor}). Confira.'
            )
        da_obra.append(b)

    vistos = {}
    for b in da_obra:
        vistos.setdefault(b.data_rdo, []).append(b)
    for dia, lista in sorted(vistos.items()):
        if len(lista) > 1:
            avisos.append(
                f'{dia.isoformat()}: {len(lista)} blocos para o mesmo dia — '
                f'o último prevalece (mensagem editada/reenviada?).'
            )

    # Um bloco por dia: o último ganha (RDO reenviado corrigido), mas as fotos
    # de todos os blocos do dia são preservadas.
    consolidados = {}
    for b in da_obra:
        anterior = consolidados.get(b.data_rdo)
        if anterior is not None:
            b.anexos = anterior.anexos + b.anexos
        consolidados[b.data_rdo] = b
    return [consolidados[d] for d in sorted(consolidados)], avisos


def _normalizar_titulo(linha):
    """Título de seção do WhatsApp → título do comentário do RDO."""
    nu = linha.strip().rstrip(':').strip()
    for regex, destino in TITULOS:
        if regex.match(nu):
            if destino is not None:
                return destino
            # "Próximas Atividades Previstas (08/07)" → mantém o parêntese
            paren = re.search(r'\(([^)]*)\)', linha)
            return f'Próximas atividades ({paren.group(1)}):' if paren else 'Próximas atividades:'
    return None


def normalizar_comentario(texto):
    """Texto do RDO como vai para `rdo.comentario_geral`.

    Tira a linha do cabeçalho ("Obra Itu - RDO – 07/07/2026"), o marcador de
    edição do WhatsApp e o negrito de asterisco; padroniza os títulos de seção
    e colapsa as linhas em branco entre bullets. O conteúdo em si é
    **verbatim** — resumir relatório de obra não é trabalho de script.
    """
    linhas = texto.replace('<Mensagem editada>', '').split('\n')
    if linhas and (RE_RDO.search(linhas[0]) or RE_DATA_SOZINHA.match(linhas[0].strip())):
        linhas = linhas[1:]

    saida = []
    for linha in linhas:
        limpa = linha.replace('*', '').strip()
        if not limpa:
            if saida and saida[-1] != '':
                saida.append('')
            continue
        titulo = _normalizar_titulo(limpa)
        if titulo:
            if saida and saida[-1] != '':
                saida.append('')
            saida.append(titulo)
            continue
        if saida and saida[-1] == '' and limpa.startswith('•') and len(saida) >= 2 \
                and (saida[-2].startswith('•') or saida[-2].endswith(':')):
            saida.pop()          # bullets não ficam separados por linha em branco
        saida.append(limpa)

    while saida and saida[0] == '':
        saida.pop(0)
    while saida and saida[-1] == '':
        saida.pop()
    return '\n'.join(saida)


# ---------------------------------------------------------------- sugestões

def _bullets(comentario):
    """Bullets das seções de atividade — 'Próximas atividades' fica de fora:
    é plano, não execução, e apontar por ele adiantaria o físico."""
    dentro = False
    for linha in comentario.split('\n'):
        if linha.endswith(':'):
            # Qualquer outro título ("Observações:", "Próximas atividades:")
            # fecha a seção — é o que mantém plano fora do apontamento.
            dentro = _sem_acento(linha).startswith('atividades executadas')
            continue
        if dentro and linha.startswith('•'):
            yield linha.lstrip('•').strip()


def _numeros(texto):
    return [float(n.replace('.', '').replace(',', '.'))
            for n in re.findall(r'\d+(?:[.,]\d+)?', texto)]


def _galpoes(texto):
    """Galpões citados no bullet.

    Cobre as três formas que o Alan usa: "do Galpão B", "dos Galpões A e B" e
    "dos dois galpões". A segunda e a terceira valem para OS DOIS — tratá-las
    como "nenhum" perderia a concretagem das brocas, que foi feita nos dois
    galpões no mesmo dia.
    """
    baixo = _sem_acento(texto)
    achados = set(m.group(1).upper()
                  for m in re.finditer(r'galp[oa]?[eo]?s?\s+([ab])\b', baixo))
    achados |= set(m.upper() for m in re.findall(r'\b([ab])\s+e\s+[ab]\b', baixo)
                   if 'galp' in baixo)
    if re.search(r'(dois|ambos os)\s+galp', baixo):
        achados |= {'A', 'B'}
    if re.search(r'galp[oõ]es\s+a\s+e\s+b', baixo):
        achados |= {'A', 'B'}
    return achados


def sugerir_apontamentos(comentario, regras):
    """Confronta cada bullet de atividade com o arquivo de regras.

    Devolve (sugestoes, pendencias). Nenhuma sugestão vira apontamento sem
    `--aplicar-sugestoes`: o % de uma tarefa é decisão de engenharia.
    """
    sugestoes, pendencias = [], []
    if not regras:
        return sugestoes, pendencias

    for bullet in _bullets(comentario):
        baixo = _sem_acento(bullet)
        galpoes_bullet = _galpoes(bullet)
        casou = False
        for regra in regras.get('regras', []):
            if not all(_sem_acento(p) in baixo for p in regra.get('quando', [])):
                continue
            # `nao_quando` existe porque bullet de PREPARAÇÃO cita o serviço
            # que virá depois ("limpeza das valas … para a camada de concreto
            # magro") e casaria a regra do serviço que ainda não começou.
            if any(_sem_acento(p) in baixo for p in regra.get('nao_quando', [])):
                continue
            galpao_regra = (regra.get('galpao') or '').upper() or None
            if galpao_regra and galpao_regra not in galpoes_bullet:
                continue
            casou = True
            pct = _pct_da_regra(regra, bullet, baixo)
            sugestao = {
                'tarefa_mpp': regra['tarefa_mpp'],
                'tarefa_nome': regra.get('tarefa_nome', ''),
                'regra': regra.get('id', ''),
                'origem': bullet,
                'sugerido': True,
            }
            if pct is None:
                pendencias.append(
                    f'regra "{regra.get("id")}" casou mas não deu % — '
                    f'defina à mão: {bullet[:80]}')
            else:
                sugestao['pct'] = round(pct, 1)
            sugestoes.append(sugestao)
        if not casou:
            pendencias.append(f'bullet sem regra: {bullet[:100]}')
    return sugestoes, pendencias


def _pct_da_regra(regra, bullet, baixo):
    forma = regra.get('forma', 'pct')
    if forma == 'marco':
        concluiu = any(p in baixo for p in
                       ('finaliz', 'conclu', 'todas as', 'todos os', 'finalizado'))
        return 100.0 if concluiu else regra.get('pct_parcial')
    if forma == 'pct':
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', bullet)
        if m:
            return float(m.group(1).replace(',', '.'))
        return regra.get('pct')
    if forma == 'fracao':
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:m|metros|un|unidades)?\b[^.]*?'
                      r'\bde\s+(?:um\s+total\s+de\s+)?(\d+(?:[.,]\d+)?)', bullet, re.I)
        if m:
            executado = float(m.group(1).replace('.', '').replace(',', '.'))
            total = float(m.group(2).replace('.', '').replace(',', '.'))
            if total > 0:
                return min(100.0, executado / total * 100.0)
        return regra.get('pct')
    return regra.get('pct')


# -------------------------------------------------------------------- fotos

def _extensao(nome):
    return os.path.splitext(nome)[1].lower()


def _ordem_numerica(nome):
    """Chave de ordenação de `1.jpg`, `2.png`… — a MESMA de
    `services/rdo_fotos_import.listar_imagens_ordenadas`.

    Ordenar por `(len, nome)` parece equivalente e não é: com extensões
    misturadas, `2.jpg` (5 caracteres) vem antes de `1.jpeg` (6) e as
    legendas grudam nas fotos erradas.
    """
    base = os.path.splitext(os.path.basename(nome))[0]
    return (0, int(base), '') if base.isdigit() else (1, 0, base.lower())


def escrever_fotos(bloco, base_fotos, ler_midia, dry_run, forcar):
    """Grava as fotos do dia em `fotos_rdos/<AAAA-MM-DD>/N.ext`.

    A numeração segue a ordem do chat, que é a ordem das legendas — contrato
    do `fotos_rdos/README.md` e do `_materializar_fotos_rdo`.

    Pasta que já tem arquivo é preservada (sem `--forcar`): as legendas são
    casadas por ordem com o que está lá, e a divergência de contagem vira
    aviso. Devolve (lista_de_fotos, avisos).
    """
    avisos = []
    imagens = [(nome, legenda) for nome, legenda in bloco.anexos
               if _extensao(nome) in EXTENSOES_IMAGEM]
    ignorados = [nome for nome, _ in bloco.anexos
                 if _extensao(nome) not in EXTENSOES_IMAGEM]
    for nome in ignorados:
        avisos.append(f'{bloco.data_rdo.isoformat()}: "{nome}" ignorado (não é imagem)')

    pasta = os.path.join(base_fotos, bloco.data_rdo.isoformat())
    existentes = []
    if os.path.isdir(pasta):
        existentes = sorted(
            (f for f in os.listdir(pasta) if _extensao(f) in EXTENSOES_IMAGEM),
            key=_ordem_numerica,
        )

    if existentes and not forcar:
        if len(existentes) != len(imagens):
            avisos.append(
                f'{bloco.data_rdo.isoformat()}: pasta já tem {len(existentes)} '
                f'foto(s) e o chat traz {len(imagens)} — legendas casadas por '
                f'ordem, use --forcar para regravar')
        fotos = []
        for i, arquivo in enumerate(existentes):
            legenda = imagens[i][1] if i < len(imagens) else ''
            fotos.append({'arquivo': arquivo, 'legenda': legenda})
        return fotos, avisos

    fotos = []
    if not dry_run and imagens:
        os.makedirs(pasta, exist_ok=True)
    for i, (nome, legenda) in enumerate(imagens, start=1):
        destino_nome = f'{i}{_extensao(nome)}'
        if not dry_run:
            dados = ler_midia(nome)
            if dados is None:
                avisos.append(
                    f'{bloco.data_rdo.isoformat()}: mídia "{nome}" não está no '
                    f'export (pulada)')
                continue
            with open(os.path.join(pasta, destino_nome), 'wb') as fh:
                fh.write(dados)
        fotos.append({'arquivo': destino_nome, 'legenda': legenda})
    return fotos, avisos


# ------------------------------------------------------------------- export

def carregar_export(caminho_zip=None, caminho_txt=None, dir_midias=None):
    """Devolve (texto_da_conversa, ler_midia(nome)->bytes|None)."""
    if caminho_zip:
        with zipfile.ZipFile(caminho_zip) as z:
            nomes = z.namelist()
            txts = [n for n in nomes if n.lower().endswith('.txt')]
            if not txts:
                raise ValueError(f'{caminho_zip}: nenhum .txt no export')
            texto = z.read(txts[0]).decode('utf-8', errors='replace')
            # Lê a mídia sob demanda, mas com o zip já fechado: carrega o
            # índice agora e reabre no acesso (o export tem ~45 MB).
            indice = {os.path.basename(n): n for n in nomes}

            def ler(nome):
                alvo = indice.get(os.path.basename(nome))
                if alvo is None:
                    return None
                with zipfile.ZipFile(caminho_zip) as zz:
                    return zz.read(alvo)

            return texto, ler

    if not caminho_txt:
        raise ValueError('informe --zip ou --txt')
    with io.open(caminho_txt, encoding='utf-8', errors='replace') as fh:
        texto = fh.read()

    def ler_disco(nome):
        if not dir_midias:
            return None
        caminho = os.path.join(dir_midias, os.path.basename(nome))
        if not os.path.exists(caminho):
            return None
        with open(caminho, 'rb') as fh2:
            return fh2.read()

    return texto, ler_disco


def converter(caminho_zip=None, caminho_txt=None, dir_midias=None,
              marcador_obra='Obra Itu', marcadores_conhecidos=(),
              desde=None, ate=None, base_fotos=None, regras=None,
              aplicar_sugestoes=False, dry_run=False, forcar=False):
    """Pipeline inteiro: export → payload `{"rdos": [...]}` + relatório."""
    base_fotos = base_fotos or os.path.join(_RAIZ, 'fotos_rdos')
    texto, ler_midia = carregar_export(caminho_zip, caminho_txt, dir_midias)
    mensagens = parse_mensagens(texto)
    blocos, avisos = agrupar_rdos(mensagens, marcador_obra, marcadores_conhecidos)

    rdos, pendencias = [], []
    for bloco in blocos:
        if desde and bloco.data_rdo < desde:
            continue
        if ate and bloco.data_rdo > ate:
            continue
        comentario = normalizar_comentario(bloco.texto)
        fotos, avisos_fotos = escrever_fotos(
            bloco, base_fotos, ler_midia, dry_run, forcar)
        avisos.extend(avisos_fotos)
        sugestoes, pend = sugerir_apontamentos(comentario, regras)
        pendencias.extend(f'{bloco.data_rdo.isoformat()}: {p}' for p in pend)

        item = {
            'data': bloco.data_rdo.isoformat(),
            # O WhatsApp não reporta clima; afirmar "Sem chuva" seria inventar.
            'clima': 'Não informado',
            'precipitacao': 'Não informado',
            'comentario': comentario,
            # Efetivo fica só no texto: o importador escolhe funcionários
            # arbitrários do cadastro para preencher a mão de obra, o que
            # atribuiria nomes errados a um dia real.
            'mao_de_obra': 0,
            'apontamentos': [],
        }
        if fotos:
            item['fotos'] = fotos
        if sugestoes:
            aptos = [s for s in sugestoes if 'pct' in s]
            if aplicar_sugestoes:
                item['apontamentos'] = [
                    {'tarefa_mpp': s['tarefa_mpp'], 'pct': s['pct']} for s in aptos]
            item['_sugestoes'] = sugestoes
        rdos.append(item)

    return {'rdos': rdos}, {'avisos': avisos, 'pendencias': pendencias,
                            'blocos': len(blocos), 'dias': len(rdos)}


def _relatorio(payload, meta, marcador_obra):
    linhas = [f'[whatsapp_para_rdos] obra "{marcador_obra}": '
              f'{meta["dias"]} dia(s) de RDO']
    for item in payload['rdos']:
        sug = item.get('_sugestoes') or []
        linhas.append(
            f'  {item["data"]}  fotos={len(item.get("fotos") or [])}  '
            f'sugestões={len(sug)}  texto={len(item["comentario"])} car.')
        for s in sug:
            pct = f'{s["pct"]}%' if 'pct' in s else '— sem %'
            linhas.append(f'      tarefa {s["tarefa_mpp"]:>4} ({s.get("tarefa_nome", "")[:38]}) '
                          f'→ {pct}   [{s["regra"]}]')
            linhas.append(f'          origem: {s["origem"][:90]}')
    if meta['avisos']:
        linhas.append(f'  avisos ({len(meta["avisos"])}):')
        linhas.extend(f'    - {a}' for a in meta['avisos'])
    if meta['pendencias']:
        linhas.append(f'  pendências de apontamento ({len(meta["pendencias"])}):')
        linhas.extend(f'    - {p}' for p in meta['pendencias'])
    return '\n'.join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Converte export do WhatsApp no payload de RDOs do sistema.')
    p.add_argument('--zip', dest='caminho_zip', help='export .zip do WhatsApp')
    p.add_argument('--txt', dest='caminho_txt', help='conversa .txt já extraída')
    p.add_argument('--midias', dest='dir_midias', help='pasta das mídias (com --txt)')
    p.add_argument('--obra-marcador', default='Obra Itu',
                   help='marcador da obra no cabeçalho do RDO (default: "Obra Itu")')
    p.add_argument('--outros-marcadores', default='Obra Vila velha,Obra Anderson,Obra a Angela',
                   help='marcadores das OUTRAS obras do grupo, separados por vírgula')
    p.add_argument('--desde', help='primeira data de RDO (AAAA-MM-DD)')
    p.add_argument('--ate', help='última data de RDO (AAAA-MM-DD)')
    p.add_argument('--saida', help='arquivo JSON de saída')
    p.add_argument('--fotos-base', help='raiz das pastas de foto (default: fotos_rdos/)')
    p.add_argument('--regras', help='JSON de regras atividade→tarefa')
    p.add_argument('--aplicar-sugestoes', action='store_true',
                   help='promove as sugestões a apontamentos (default: não)')
    p.add_argument('--forcar', action='store_true',
                   help='regrava pasta de foto que já tem arquivo')
    p.add_argument('--dry-run', action='store_true',
                   help='não grava foto nem JSON — só o relatório')
    args = p.parse_args(argv)

    if not args.caminho_zip and not args.caminho_txt:
        p.error('informe --zip ou --txt')

    regras = None
    if args.regras:
        with open(args.regras, encoding='utf-8') as fh:
            regras = json.load(fh)

    payload, meta = converter(
        caminho_zip=args.caminho_zip,
        caminho_txt=args.caminho_txt,
        dir_midias=args.dir_midias,
        marcador_obra=args.obra_marcador,
        marcadores_conhecidos=[m.strip() for m in args.outros_marcadores.split(',') if m.strip()],
        desde=date.fromisoformat(args.desde) if args.desde else None,
        ate=date.fromisoformat(args.ate) if args.ate else None,
        base_fotos=args.fotos_base,
        regras=regras,
        aplicar_sugestoes=args.aplicar_sugestoes,
        dry_run=args.dry_run,
        forcar=args.forcar,
    )

    print(_relatorio(payload, meta, args.obra_marcador))
    if args.saida and not args.dry_run:
        with open(args.saida, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        print(f'  payload: {args.saida}')
    elif args.saida:
        print('  (--dry-run: payload NÃO gravado)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
