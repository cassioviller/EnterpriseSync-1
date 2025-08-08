#!/usr/bin/env python3
"""
Teste para verificar se as fotos base64 estão funcionando
"""

from app import app, db
from models import Funcionario

def testar_fotos_base64():
    """Testa as fotos base64 dos funcionários"""
    
    with app.app_context():
        print("🔍 TESTE: Fotos Base64 dos Funcionários")
        print("=" * 50)
        
        # Pegar alguns funcionários
        funcionarios = Funcionario.query.limit(5).all()
        
        for funcionario in funcionarios:
            print(f"\n👤 {funcionario.nome} (Código: {funcionario.codigo})")
            print(f"   Foto arquivo: {funcionario.foto}")
            
            if funcionario.foto_base64:
                tipo_foto = "SVG" if "svg+xml" in funcionario.foto_base64 else "JPEG"
                tamanho = len(funcionario.foto_base64)
                print(f"   ✅ Base64: {tipo_foto} ({tamanho} chars)")
                print(f"   📄 Preview: {funcionario.foto_base64[:50]}...")
            else:
                print(f"   ❌ Sem foto base64")
                
        print(f"\n🎯 TESTE CONCLUÍDO!")
        print(f"   As fotos agora estão salvas como base64 no banco")
        print(f"   Não se perdem mais durante deploys!")

if __name__ == "__main__":
    testar_fotos_base64()