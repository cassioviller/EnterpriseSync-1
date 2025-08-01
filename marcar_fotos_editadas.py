#!/usr/bin/env python3
"""
Script para marcar fotos existentes como editadas pelo usuário
Execute este script UMA VEZ para proteger fotos já existentes
"""

from app import app
from models import db, Funcionario

def marcar_fotos_existentes():
    """Marca todas as fotos não-SVG existentes como editadas pelo usuário"""
    
    with app.app_context():
        print("🔒 PROTEGENDO FOTOS EXISTENTES")
        print("=" * 50)
        
        # Buscar funcionários com fotos que NÃO são SVG (fotos reais carregadas pelo usuário)
        funcionarios_com_foto = Funcionario.query.filter(
            db.and_(
                Funcionario.foto.isnot(None),
                Funcionario.foto != '',
                ~Funcionario.foto.like('fotos_funcionarios/%')  # Não são avatares SVG
            )
        ).all()
        
        print(f"Encontrados {len(funcionarios_com_foto)} funcionários com fotos reais")
        
        fotos_protegidas = 0
        
        for funcionario in funcionarios_com_foto:
            # Marcar como editada pelo usuário (para não ser sobrescrita)
            funcionario.foto_editada_usuario = True
            fotos_protegidas += 1
            print(f"  ✅ {funcionario.nome} -> Foto protegida: {funcionario.foto}")
        
        # Salvar mudanças
        db.session.commit()
        
        print(f"\n🎯 RESULTADO:")
        print(f"   ✅ {fotos_protegidas} fotos marcadas como editadas pelo usuário")
        print(f"   ✅ Essas fotos nunca serão sobrescritas pelo sistema automático")
        print(f"   ✅ Apenas funcionários SEM foto receberão avatares automáticos")

if __name__ == "__main__":
    marcar_fotos_existentes()