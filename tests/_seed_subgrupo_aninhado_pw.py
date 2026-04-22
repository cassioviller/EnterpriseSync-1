"""Helper para o teste Playwright da Task #154.

Seeda um admin + obra + cronograma aninhado e imprime os IDs e a senha
para o agente de testes UI consumir. Idempotente por sufixo recebido em
argv[1] (ou gera um novo).

Uso:
    python tests/_seed_subgrupo_aninhado_pw.py
Saída (linhas chave):
    EMAIL=t154pw_<suf>@test.local
    PASSWORD=Senha@2026
    ADMIN_ID=...
    OBRA_ID=...
    RAIZ_ID=...
    SUB_ID=...
    FA_ID=...
    FB_ID=...
"""
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash
from models import Usuario, TipoUsuario, Obra, Cliente, TarefaCronograma


def main():
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f't154pw_{suf}@test.local'
    senha = 'Senha@2026'
    with app.app_context():
        admin = Usuario(
            username=f't154pw_{suf}',
            email=email, nome='T154 PW Admin',
            password_hash=generate_password_hash(senha),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        admin_id = admin.id
        cli = Cliente(admin_id=admin_id, nome=f'Cli PW {suf}',
                      email=f'cli_{suf}@test.local', telefone='119')
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra T154 PW {suf}', codigo=f'T154-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(), cliente_nome=cli.nome,
        )
        db.session.add(obra); db.session.flush()
        raiz = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, nome_tarefa='LSF PW',
            ordem=1, duracao_dias=10, data_inicio=date.today(),
            responsavel='empresa', is_cliente=False,
        )
        db.session.add(raiz); db.session.flush()
        sub = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=raiz.id,
            nome_tarefa='Estrutura PW', ordem=2, duracao_dias=10,
            data_inicio=date.today(), responsavel='empresa', is_cliente=False,
        )
        db.session.add(sub); db.session.flush()
        fa = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Aco Laminado PW', ordem=3, duracao_dias=4,
            data_inicio=date.today(), quantidade_total=100.0, unidade_medida='kg',
            responsavel='empresa', is_cliente=False,
        )
        fb = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Concretagem PW', ordem=4, duracao_dias=6,
            data_inicio=date.today(), quantidade_total=200.0, unidade_medida='m3',
            responsavel='empresa', is_cliente=False,
        )
        db.session.add_all([fa, fb])
        db.session.commit()
        print(f'EMAIL={email}')
        print(f'PASSWORD={senha}')
        print(f'ADMIN_ID={admin_id}')
        print(f'OBRA_ID={obra.id}')
        print(f'RAIZ_ID={raiz.id}')
        print(f'SUB_ID={sub.id}')
        print(f'FA_ID={fa.id}')
        print(f'FB_ID={fb.id}')


if __name__ == '__main__':
    main()
