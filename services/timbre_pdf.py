"""Timbre dos PDFs — a identidade visual do tenant, em um JSON importável.

Antes disto, o que aparece no cabeçalho de um PDF vinha de dois lugares e
nenhum deles era editável de ponta a ponta:

* **texto e logo** de campos soltos de `ConfiguracaoEmpresa` (`nome_empresa`,
  `cnpj`, `endereco`, `website`, `logo_pdf_base64`);
* **cores e tipografia** de constantes no código (`services/cronograma_pdf`),
  iguais para todo tenant.

Agora existe `configuracao_empresa.timbre_pdf` (JSON, migration 286) e um par
importar/exportar na tela de Configurações. O JSON é a fonte única do que o
documento mostra, e o formato é versionado (`versao: 1`) para que um arquivo
salvo hoje continue sendo lido depois de o schema crescer.

**Precedência**, do mais fraco ao mais forte:

1. `PADRAO` — os tokens do kit oficial (`veks_layout_pdf/template_veks.html`);
2. os campos soltos de `ConfiguracaoEmpresa` — o que a tela de Empresa já
   preenchia antes desta fase, e que continua valendo;
3. o JSON `timbre_pdf` — o que foi importado.

Essa ordem é o que torna a mudança aditiva: tenant que nunca importar JSON vê
exatamente o que via antes, e tenant que importar sobrescreve só as chaves que
o arquivo trouxer (merge por chave, não substituição do bloco).
"""

from __future__ import annotations

import base64
import binascii
import copy
import logging
import re

logger = logging.getLogger(__name__)

VERSAO_ATUAL = 1

# Tokens do kit oficial — o :root do template_veks.html. São o padrão de todo
# tenant que não configurou nada.
PADRAO: dict = {
    'versao': VERSAO_ATUAL,
    'empresa': {
        'nome': '',
        'razao_social': '',
        'cnpj': '',
        'endereco': '',
        'website': '',
    },
    'cores': {
        'navy': '#16294A',      # --navy
        'navy_rotulo': '#1E3A5F',  # --navy2
        'laranja': '#E8611A',   # --orange
        'fio': '#D8DDE5',       # --line
        'cinza': '#6B7280',     # --gray
        'ink': '#26303D',       # cor do corpo
        'realce_linha': '#EEF0F4',  # tr.totalrow
    },
    'logo_base64': '',
}

CHAVES_CORES = tuple(PADRAO['cores'].keys())
CHAVES_EMPRESA = tuple(PADRAO['empresa'].keys())

_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')

# Um JSON de timbre carrega a logo embutida em base64. 4 MB de base64 são ~3 MB
# de imagem: acima disso é quase certo que alguém colou um PNG de câmera, que
# não melhora nada num carimbo de 13mm de altura e engorda toda geração de PDF.
LIMITE_JSON_BYTES = 4 * 1024 * 1024
LIMITE_TEXTO = 200


class TimbreInvalido(ValueError):
    """Erros de validação, com a lista completa — não só o primeiro.

    Quem importa um arquivo quer saber tudo o que está errado nele de uma vez,
    e não descobrir um problema por tentativa.
    """

    def __init__(self, erros):
        self.erros = list(erros)
        super().__init__('; '.join(self.erros))


def carregar(admin_id: int) -> dict:
    """O timbre efetivo do tenant, já mesclado e pronto para desenhar.

    Nunca levanta e nunca devolve chave faltando: o pior caso é o `PADRAO`
    puro. Um PDF com a marca errada é um problema; um PDF que não sai por
    causa de cadastro é pior.
    """
    from models import ConfiguracaoEmpresa

    timbre = copy.deepcopy(PADRAO)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        timbre['empresa']['nome'] = 'Empresa'
        return timbre

    # Camada 2 — os campos soltos que a tela de Empresa já preenchia.
    timbre['empresa'].update({
        'nome': (config.nome_empresa or 'Empresa'),
        'cnpj': (config.cnpj or ''),
        'endereco': (config.endereco or '').replace('\n', ' ').strip(),
        'website': (config.website or ''),
    })
    logo = (config.logo_pdf_base64 or '').strip() or \
        (config.logo_base64 or '').strip()
    if logo:
        timbre['logo_base64'] = logo

    # Camada 3 — o JSON importado, chave por chave.
    guardado = getattr(config, 'timbre_pdf', None)
    if isinstance(guardado, dict):
        _mesclar(timbre, guardado)
    elif guardado:
        logger.warning('[TIMBRE] timbre_pdf do tenant %s não é objeto JSON '
                       '(%s) — ignorado', admin_id, type(guardado).__name__)
    return timbre


def _mesclar(destino: dict, origem: dict) -> None:
    """Merge por chave nos blocos conhecidos; ignora o resto em silêncio.

    Ignorar chave desconhecida é deliberado: um arquivo exportado por uma
    versão futura, com um bloco novo, ainda deve ser importável nesta.
    """
    for bloco in ('empresa', 'cores'):
        valores = origem.get(bloco)
        if isinstance(valores, dict):
            for chave, valor in valores.items():
                if chave in destino[bloco] and valor not in (None, ''):
                    destino[bloco][chave] = valor
    if origem.get('logo_base64'):
        destino['logo_base64'] = origem['logo_base64']


def validar(payload) -> dict:
    """Valida o JSON importado e devolve só o que deve ser guardado.

    Guarda apenas as chaves reconhecidas e não vazias — o que evita gravar um
    bloco cheio de strings vazias que depois sobrescreveria os campos soltos
    da tela com nada.

    Levanta `TimbreInvalido` com TODOS os erros encontrados.
    """
    erros: list[str] = []
    if not isinstance(payload, dict):
        raise TimbreInvalido(['o arquivo precisa ser um objeto JSON'])

    versao = payload.get('versao', VERSAO_ATUAL)
    if not isinstance(versao, int) or versao < 1:
        erros.append(f'versao inválida: {versao!r}')
    elif versao > VERSAO_ATUAL:
        erros.append(f'arquivo na versão {versao}; esta instalação lê até '
                     f'{VERSAO_ATUAL}')

    limpo: dict = {'versao': VERSAO_ATUAL}

    empresa = payload.get('empresa')
    if empresa is not None:
        if not isinstance(empresa, dict):
            erros.append('"empresa" precisa ser um objeto')
        else:
            bloco = {}
            for chave, valor in empresa.items():
                if chave not in CHAVES_EMPRESA:
                    continue
                if not isinstance(valor, str):
                    erros.append(f'empresa.{chave}: precisa ser texto')
                    continue
                valor = valor.strip()
                if len(valor) > LIMITE_TEXTO:
                    erros.append(f'empresa.{chave}: mais de {LIMITE_TEXTO} '
                                 f'caracteres')
                    continue
                if valor:
                    bloco[chave] = valor
            if bloco:
                limpo['empresa'] = bloco

    cores = payload.get('cores')
    if cores is not None:
        if not isinstance(cores, dict):
            erros.append('"cores" precisa ser um objeto')
        else:
            bloco = {}
            for chave, valor in cores.items():
                if chave not in CHAVES_CORES:
                    erros.append(f'cores.{chave}: cor desconhecida (aceitas: '
                                 f'{", ".join(CHAVES_CORES)})')
                    continue
                if not isinstance(valor, str) or not _HEX.match(valor.strip()):
                    erros.append(f'cores.{chave}: use #RRGGBB, recebido '
                                 f'{valor!r}')
                    continue
                bloco[chave] = valor.strip().upper()
            if bloco:
                limpo['cores'] = bloco

    logo = payload.get('logo_base64')
    if logo:
        if not isinstance(logo, str):
            erros.append('logo_base64: precisa ser texto')
        else:
            texto = logo.strip()
            if texto.startswith('data:'):
                _, _, texto = texto.partition(',')
            try:
                bruto = base64.b64decode(texto, validate=True)
            except (binascii.Error, ValueError):
                erros.append('logo_base64: não é base64 válido')
            else:
                erro_img = _erro_de_imagem(bruto)
                if erro_img:
                    erros.append(f'logo_base64: {erro_img}')
                else:
                    limpo['logo_base64'] = texto

    if erros:
        raise TimbreInvalido(erros)
    return limpo


def _erro_de_imagem(bruto: bytes) -> str | None:
    """Confere que os bytes são imagem legível, e não só base64 bem formado.

    Sem esta checagem, o erro só apareceria no desenho do PDF — depois de o
    usuário salvar, sair da tela e clicar em baixar. `Image.verify()` lê o
    cabeçalho sem decodificar a imagem inteira.
    """
    try:
        import io
        from PIL import Image
        Image.open(io.BytesIO(bruto)).verify()
    except Exception as e:
        return f'não é uma imagem legível ({e})'
    return None


def importar(admin_id: int, conteudo: bytes) -> dict:
    """Valida e grava o JSON no tenant. Devolve o timbre efetivo resultante.

    Não commita: quem chama decide, junto com o resto da transação da tela.
    """
    import json

    from models import ConfiguracaoEmpresa, Usuario, db

    if len(conteudo) > LIMITE_JSON_BYTES:
        raise TimbreInvalido([
            f'arquivo com {len(conteudo) // 1024} KB; o limite é '
            f'{LIMITE_JSON_BYTES // 1024} KB'])
    try:
        payload = json.loads(conteudo.decode('utf-8'))
    except UnicodeDecodeError:
        raise TimbreInvalido(['o arquivo não está em UTF-8'])
    except json.JSONDecodeError as e:
        raise TimbreInvalido([f'JSON inválido: {e.msg} (linha {e.lineno})'])

    limpo = validar(payload)

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        # `nome_empresa` é NOT NULL — mesma derivação dos scripts de flag.
        admin = db.session.get(Usuario, admin_id)
        nome = getattr(admin, 'nome', None) or f'Empresa {admin_id}'
        config = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=nome)
        db.session.add(config)

    atual = getattr(config, 'timbre_pdf', None)
    base = copy.deepcopy(atual) if isinstance(atual, dict) else {}
    _mesclar_guardado(base, limpo)
    config.timbre_pdf = base
    return carregar(admin_id)


def _mesclar_guardado(base: dict, novo: dict) -> None:
    """Merge do que já estava guardado com o que veio agora.

    Importar um arquivo só com `cores` não pode apagar a logo importada na
    semana passada — o import é incremental por chave, como o `_mesclar` da
    leitura.
    """
    base['versao'] = VERSAO_ATUAL
    for bloco in ('empresa', 'cores'):
        if bloco in novo:
            base.setdefault(bloco, {}).update(novo[bloco])
    if 'logo_base64' in novo:
        base['logo_base64'] = novo['logo_base64']


def exportar(admin_id: int, *, com_logo: bool = True) -> dict:
    """O timbre efetivo do tenant no formato do arquivo de import.

    É o que a tela oferece para download: serve de ponto de partida para
    editar (as chaves já vêm todas preenchidas, com os padrões do kit onde o
    tenant não configurou) e de backup antes de trocar de identidade.

    `com_logo=False` produz um arquivo leve, útil para versionar ou mandar por
    e-mail — a logo é o que faz o JSON passar de 100 KB.
    """
    timbre = carregar(admin_id)
    if not com_logo:
        timbre = copy.deepcopy(timbre)
        timbre['logo_base64'] = ''
    return timbre
