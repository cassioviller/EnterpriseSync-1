#!/usr/bin/env python3
"""
Script simplificado para criar funcionário Caio Fabio Silva de Azevedo
"""

from app import app
from datetime import date, datetime, time

def criar_funcionario_caio_simples():
    with app.app_context():
        from models import db, Funcionario, Departamento, Funcao, HorarioTrabalho
        
        print("=== CRIANDO FUNCIONÁRIO CAIO FABIO ===")
        
        # Verificar se já existe
        caio = Funcionario.query.filter_by(nome="Caio Fabio Silva de Azevedo").first()
        if caio:
            print(f"   - Funcionário já existe: {caio.nome} ({caio.codigo})")
            return caio
        
        # Criar horário de trabalho
        horario = HorarioTrabalho.query.filter_by(nome="Turno 7h12-17h").first()
        if not horario:
            horario = HorarioTrabalho(
                nome="Turno 7h12-17h",
                entrada=time(7, 12),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                dias_semana="1,2,3,4,5",
                horas_diarias=8.8,
                valor_hora=15.00
            )
            db.session.add(horario)
            db.session.commit()
        
        # Buscar departamento e função
        departamento = Departamento.query.first()
        funcao = Funcao.query.first()
        
        # Gerar código único
        ultimo_funcionario = Funcionario.query.order_by(Funcionario.id.desc()).first()
        numero = 1
        if ultimo_funcionario and ultimo_funcionario.codigo:
            numero = int(ultimo_funcionario.codigo.replace('F', '')) + 1
        codigo = f"F{numero:04d}"
        
        # Criar funcionário
        funcionario = Funcionario(
            nome="Caio Fabio Silva de Azevedo",
            codigo=codigo,
            cpf="12345678901",
            telefone="(11) 98765-4321",
            email="caio.fabio@estruturasdovale.com.br",
            salario=3500.00,
            departamento_id=departamento.id,
            funcao_id=funcao.id,
            horario_trabalho_id=horario.id,
            ativo=True,
            data_admissao=date(2024, 1, 15)
        )
        
        db.session.add(funcionario)
        db.session.commit()
        
        print(f"   - Funcionário criado: {funcionario.nome} ({funcionario.codigo})")
        print(f"   - Horário: {horario.nome} - {horario.horas_diarias}h diárias")
        print(f"   - Valor/hora: R$ {horario.valor_hora}")
        print(f"   - ID: {funcionario.id}")
        
        return funcionario

if __name__ == "__main__":
    funcionario = criar_funcionario_caio_simples()
    print(f"\nFuncionário criado com sucesso!")
    print(f"Para continuar, use o ID: {funcionario.id}")