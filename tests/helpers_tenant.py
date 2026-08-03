"""Arreio de isolamento entre empresas — Step 0 do p1.

Existe porque o critério de pronto do p1 é um teste que **hoje passa
vermelho**: sem dois tenants semeados lado a lado, afirmar "não vaza" é
opinião. O padrão nasceu em `tests/test_gestao_custo_filho_tenant.py:44` e
estava a caminho da terceira cópia — aqui ele vira helper.

Uso:

    from helpers_tenant import dois_tenants, cliente_de

    a, b = dois_tenants('rel')
    resposta = cliente_de(a.admin_id).post('/relatorios/gerar/funcionarios',
                                           json={})
    assert b.marca not in resposta.get_data(as_text=True)

A regra do arreio: **nada é compartilhado entre A e B de propósito** — nem
cliente, nem obra, nem funcionário, nem restaurante. É compartilhamento
acidental que estes testes procuram, e um fixture que reaproveita registro
"para economizar" esconde exatamente o defeito que se quer ver.

Cada tenant carrega uma `marca` única no nome de tudo que semeia. É por ela
que o teste procura o vazamento, e não por contagem: contar dá o mesmo número
quando os dois tenants têm um registro cada.
"""
import uuid
from datetime import date

from werkzeug.security import generate_password_hash

from app import app, db
from models import (Cliente, CustoObra, Funcionario, Obra, RegistroAlimentacao,
                    RegistroPonto, TipoUsuario, Usuario)

SENHA = 'Senha@2026'


class Tenant:
    """Um tenant semeado, com os ids que os testes precisam citar."""

    def __init__(self, marca, admin_id, obra_id, funcionario_id, cliente_id):
        self.marca = marca
        self.admin_id = admin_id
        self.obra_id = obra_id
        self.funcionario_id = funcionario_id
        self.cliente_id = cliente_id

    def __repr__(self):  # pragma: no cover - conveniência de depuração
        return f'<Tenant {self.marca} admin={self.admin_id} obra={self.obra_id}>'


def _um_tenant(prefixo, lado, data_ref):
    """Admin + cliente + obra + funcionário + 3 fatos operacionais.

    Os fatos (ponto com hora extra, alimentação, custo de obra) são o mínimo
    para os relatórios do p1 terem o que devolver — cada um deles lê uma
    tabela diferente.
    """
    marca = f'{prefixo.upper()}{lado}{uuid.uuid4().hex[:6].upper()}'

    admin = Usuario(
        username=f'{marca}_user', email=f'{marca}@t.local',
        nome=f'Empresa {marca}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cliente = Cliente(nome=f'Cliente {marca}', admin_id=admin.id)
    db.session.add(cliente)
    db.session.flush()

    obra = Obra(nome=f'Obra {marca}', codigo=marca[:10],
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cliente.id, valor_contrato=100000,
                orcamento=100000, status='Em andamento')
    db.session.add(obra)
    db.session.flush()

    funcionario = Funcionario(
        codigo=marca[:10], nome=f'Funcionario {marca}',
        cpf=f'{uuid.uuid4().int % 10**11:011d}',
        data_admissao=date(2026, 1, 2), admin_id=admin.id, ativo=True,
        salario=3000.0, tipo_remuneracao='salario')
    db.session.add(funcionario)
    db.session.flush()

    db.session.add(RegistroPonto(
        funcionario_id=funcionario.id, obra_id=obra.id, admin_id=admin.id,
        data=data_ref, horas_trabalhadas=8.0, horas_extras=2.0))

    db.session.add(RegistroAlimentacao(
        funcionario_id=funcionario.id, obra_id=obra.id, admin_id=admin.id,
        data=data_ref, tipo='almoco', valor=25.0))

    db.session.add(CustoObra(
        obra_id=obra.id, admin_id=admin.id, tipo='material',
        descricao=f'Custo {marca}', valor=1234.0, data=data_ref))

    db.session.commit()
    return Tenant(marca, admin.id, obra.id, funcionario.id, cliente.id)


def dois_tenants(prefixo, data_ref=None):
    """(A, B) — dois tenants completos e sem nada em comum."""
    data_ref = data_ref or date(2026, 6, 15)
    return (_um_tenant(prefixo, 'A', data_ref),
            _um_tenant(prefixo, 'B', data_ref))


def cliente_de(user_id):
    """Test client autenticado como `user_id` (mesmo atalho de sessão que a
    suíte já usa em `test_gestao_custo_filho_tenant.py:80`)."""
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c
