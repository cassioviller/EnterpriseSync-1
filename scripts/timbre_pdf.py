#!/usr/bin/env python3
"""Mostra e define o timbre dos PDFs de um tenant — logo, CNPJ, endereço, site.

Uso:
    python scripts/timbre_pdf.py <admin_id> --status
    python scripts/timbre_pdf.py <admin_id> --definir --logo static/images/logo_veks.png \\
        --cnpj 42.547.087/0001-61 --endereco "São José dos Campos/SP" \\
        --website veksengenharia.com --aplicar

Existe porque o cabeçalho dos PDFs (cronograma, proposta, mapa) sai de
`ConfiguracaoEmpresa`, e não do código: `services/cronograma_pdf.montar_marca_tenant`
tenta `logo_pdf_base64`, cai em `logo_base64` e, sem nenhuma das duas, imprime
o nome da empresa em texto. O primeiro export real do cronograma saiu assim —
"veks" miúdo no canto — porque o cadastro estava vazio, e não porque o layout
estivesse errado.

O caminho normal para isso é a TELA (Configurações → Empresa → "Logo para
PDF", `templates/configuracoes/empresa.html:224`), que já converte o arquivo
para base64. Este script serve a dois casos que a tela não cobre: rodar por
console no servidor (EasyPanel) e conferir/comparar o estado de um tenant sem
abrir o navegador.

NADA é escrito sem `--aplicar`: sem a flag o script imprime o que FARIA. É
escrita em dado de produção; a confirmação explícita é o freio.
"""
import argparse
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ConfiguracaoEmpresa, Usuario, db

CAMPOS_TEXTO = ('cnpj', 'endereco', 'website')


def _resumo(config) -> str:
    if config is None:
        return 'SEM ConfiguracaoEmpresa'
    partes = [f'nome_empresa={config.nome_empresa!r}']
    for campo in CAMPOS_TEXTO:
        partes.append(f'{campo}={(getattr(config, campo) or "") or "—"!r}')
    for campo in ('logo_pdf_base64', 'logo_base64', 'header_pdf_base64'):
        partes.append(f'{campo}={len(getattr(config, campo) or "")} chars')
    return ' | '.join(partes)


def _logo_em_base64(caminho: str) -> str:
    """Lê a imagem e devolve base64 puro, sem o prefixo `data:`.

    O campo guarda base64 puro — é o que o template do cadastro grava e o que
    `montar_marca_tenant` decodifica. Valida que o arquivo é imagem legível
    antes de gravar: base64 de um arquivo corrompido passa pela decodificação
    e só falha no desenho, quando o usuário já clicou em baixar.
    """
    with open(caminho, 'rb') as fh:
        bruto = fh.read()
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(bruto))
        img.verify()
    except Exception as e:
        raise SystemExit(f'ABORTADO: {caminho} não é uma imagem legível ({e})')
    return base64.b64encode(bruto).decode('ascii')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--status', action='store_true',
                       help='imprime o timbre atual do tenant')
    grupo.add_argument('--definir', action='store_true',
                       help='grava os campos informados (exige --aplicar)')
    parser.add_argument('--logo', help='arquivo de imagem para logo_pdf_base64')
    parser.add_argument('--cnpj')
    parser.add_argument('--endereco')
    parser.add_argument('--website')
    parser.add_argument('--aplicar', action='store_true',
                        help='sem esta flag, nada é escrito')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        config = ConfiguracaoEmpresa.query.filter_by(
            admin_id=args.admin_id).first()

        if args.status:
            admin = db.session.get(Usuario, args.admin_id)
            print(f'admin_id={args.admin_id} '
                  f'({getattr(admin, "email", None) or "usuário inexistente"})')
            print(_resumo(config))
            return 0

        mudancas = {}
        if args.logo:
            mudancas['logo_pdf_base64'] = _logo_em_base64(args.logo)
        for campo in CAMPOS_TEXTO:
            valor = getattr(args, campo)
            if valor is not None:
                mudancas[campo] = valor
        if not mudancas:
            print('ABORTADO: nada a definir. Informe --logo, --cnpj, '
                  '--endereco ou --website.')
            return 1

        if config is None:
            # `nome_empresa` é NOT NULL — mesma derivação dos scripts de flag.
            admin = db.session.get(Usuario, args.admin_id)
            nome = getattr(admin, 'nome', None) or f'Empresa {args.admin_id}'
            print(f'ATENÇÃO: tenant sem ConfiguracaoEmpresa; será criada com '
                  f'nome_empresa={nome!r}')

        print(f'ANTES: {_resumo(config)}')
        for campo, valor in mudancas.items():
            atual = getattr(config, campo, None) if config else None
            if campo.endswith('base64'):
                print(f'  {campo}: {len(atual or "")} chars → '
                      f'{len(valor)} chars')
            else:
                print(f'  {campo}: {atual!r} → {valor!r}')

        if not args.aplicar:
            print('\nNADA FOI ESCRITO. Repita com --aplicar para gravar.')
            return 0

        if config is None:
            admin = db.session.get(Usuario, args.admin_id)
            nome = getattr(admin, 'nome', None) or f'Empresa {args.admin_id}'
            config = ConfiguracaoEmpresa(admin_id=args.admin_id,
                                         nome_empresa=nome)
            db.session.add(config)
        for campo, valor in mudancas.items():
            setattr(config, campo, valor)
        db.session.commit()
        print(f'\nDEPOIS: {_resumo(config)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
