"""
Seed fixture mínimo para validar Task #213 via Playwright.

Cria: admin + cliente + insumo + servico + composição + template (1 grupo + 2 subatividades)
+ Proposta status='RASCUNHO' com 1 item ligado ao serviço.

Imprime no stdout (linha única JSON) os dados que o Playwright precisa:
{"proposta_id": ..., "admin_email": "...", "admin_senha": "...", "sub_a_nome": "...", "sub_b_nome": "..."}
"""
import os
import sys
import json
import secrets
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Cliente,
    Insumo, ComposicaoServico,
    Servico,
    CronogramaTemplate, CronogramaTemplateItem,
    SubatividadeMestre,
    Proposta, PropostaItem,
)

TAG = f"PW213-{secrets.token_hex(3).upper()}"
SENHA = "Senha@2026"


def main():
    with app.app_context():
        admin = Usuario(
            username=f"adm_{TAG.lower()}",
            email=f"{TAG.lower()}@e2e.local",
            nome=f"Admin {TAG}",
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema="v2",
        )
        db.session.add(admin)
        db.session.flush()

        cliente = Cliente(
            admin_id=admin.id,
            nome=f"Cliente {TAG}",
            email=f"cli_{TAG.lower()}@e2e.local",
            telefone="11999999999",
        )
        db.session.add(cliente)

        sub_a_nome = f"Preparo {TAG}"
        sub_b_nome = f"Aplicacao {TAG}"
        sub_a = SubatividadeMestre(admin_id=admin.id, nome=sub_a_nome, unidade_medida="m3")
        sub_b = SubatividadeMestre(admin_id=admin.id, nome=sub_b_nome, unidade_medida="m2")
        db.session.add_all([sub_a, sub_b])
        db.session.flush()

        template = CronogramaTemplate(
            admin_id=admin.id, nome=f"Tpl {TAG}", categoria="Alvenaria", ativo=True,
        )
        db.session.add(template)
        db.session.flush()

        grupo = CronogramaTemplateItem(
            template_id=template.id, admin_id=admin.id,
            nome_tarefa=f"Etapa {TAG}", ordem=0, duracao_dias=10,
        )
        db.session.add(grupo)
        db.session.flush()

        db.session.add_all([
            CronogramaTemplateItem(
                template_id=template.id, admin_id=admin.id,
                parent_item_id=grupo.id, subatividade_mestre_id=sub_a.id,
                nome_tarefa=sub_a_nome, ordem=0, duracao_dias=4, responsavel="empresa",
            ),
            CronogramaTemplateItem(
                template_id=template.id, admin_id=admin.id,
                parent_item_id=grupo.id, subatividade_mestre_id=sub_b.id,
                nome_tarefa=sub_b_nome, ordem=1, duracao_dias=6, responsavel="empresa",
            ),
        ])
        db.session.flush()

        insumo = Insumo(
            admin_id=admin.id, nome=f"Cimento {TAG}", tipo="MATERIAL",
            unidade="kg", coeficiente_padrao=Decimal("1"), ativo=True,
        )
        db.session.add(insumo)
        db.session.flush()

        servico = Servico(
            admin_id=admin.id,
            nome=f"Alvenaria {TAG}",
            categoria="Estrutura",
            unidade_medida="m2",
            imposto_pct=Decimal("13.5"),
            margem_lucro_pct=Decimal("20"),
            template_padrao_id=template.id,
            ativo=True,
        )
        db.session.add(servico)
        db.session.flush()

        db.session.add(ComposicaoServico(
            admin_id=admin.id,
            servico_id=servico.id, insumo_id=insumo.id,
            coeficiente=Decimal("12.5"), unidade="kg",
        ))

        prop = Proposta(
            admin_id=admin.id,
            numero=f"PROP-{TAG}",
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            cliente_email=cliente.email,
            titulo=f"Proposta {TAG}",
            status="RASCUNHO",
            data_proposta=date.today(),
            valor_total=Decimal("12000.00"),
            token_cliente=secrets.token_urlsafe(24),
        )
        db.session.add(prop)
        db.session.flush()

        db.session.add(PropostaItem(
            admin_id=admin.id,
            proposta_id=prop.id,
            servico_id=servico.id,
            item_numero=1,
            descricao=f"Alvenaria estrutural {TAG}",
            unidade="m2",
            quantidade=Decimal("100"),
            preco_unitario=Decimal("120"),
            ordem=1,
        ))

        db.session.commit()

        out = {
            "proposta_id": prop.id,
            "admin_email": admin.email,
            "admin_senha": SENHA,
            "sub_a_nome": sub_a_nome,
            "sub_b_nome": sub_b_nome,
            "grupo_nome": f"Etapa {TAG}",
            "tag": TAG,
        }
        print("FIXTURE_JSON=" + json.dumps(out))


if __name__ == "__main__":
    main()
