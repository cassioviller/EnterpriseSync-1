#!/usr/bin/env python3
"""
Script para testar detecção de admin_id em todas as situações
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, Servico, Usuario, TipoUsuario
from sqlalchemy import text

def test_admin_detection():
    """Testa todas as formas de detectar admin_id"""
    print("=== TESTE COMPLETO DE DETECÇÃO ADMIN_ID ===\n")
    
    # 1. Testar dados do banco
    print("1. DADOS DO BANCO:")
    servicos_por_admin = db.session.execute(
        text("SELECT admin_id, COUNT(*) as total FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY admin_id")
    ).fetchall()
    print(f"   Serviços por admin_id: {[(row[0], row[1]) for row in servicos_por_admin]}")
    
    usuarios_admin = db.session.execute(
        text("SELECT id, email, tipo_usuario FROM usuario WHERE tipo_usuario = 'admin' ORDER BY id")
    ).fetchall()
    print(f"   Usuários ADMIN: {[(row[0], row[1], row[2]) for row in usuarios_admin]}")
    
    # 2. Testar busca específica para admin_id=2
    print("\n2. TESTE ADMIN_ID=2:")
    servicos_admin_2 = Servico.query.filter_by(admin_id=2, ativo=True).all()
    print(f"   Total serviços admin_id=2: {len(servicos_admin_2)}")
    for servico in servicos_admin_2[:3]:  # Mostrar apenas 3 primeiros
        print(f"   - {servico.nome} (ID:{servico.id}, admin_id:{servico.admin_id})")
    
    # 3. Testar fallback dinâmico
    print("\n3. TESTE FALLBACK DINÂMICO:")
    admin_funcionarios = db.session.execute(
        text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC")
    ).fetchall()
    print(f"   Funcionários por admin_id: {[(row[0], row[1]) for row in admin_funcionarios]}")
    
    # 4. Simular produção
    print("\n4. SIMULAÇÃO PRODUÇÃO:")
    print("   Em produção o usuário logado deve ter:")
    print("   - current_user.is_authenticated = True")
    print("   - current_user.tipo_usuario = TipoUsuario.ADMIN") 
    print("   - current_user.id = 2")
    print("   - Logo: admin_id deve ser 2")
    
if __name__ == "__main__":
    from main import app
    with app.app_context():
        test_admin_detection()