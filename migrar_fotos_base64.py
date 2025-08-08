#!/usr/bin/env python3
"""
Script para migrar todas as fotos existentes para o sistema base64
Este script converte fotos de arquivos para base64 no banco de dados
"""

from app import app, db
from models import Funcionario
from utils import salvar_foto_funcionario
import os
import base64
from PIL import Image
import io

def migrar_fotos_para_base64():
    """Migra todas as fotos existentes para base64"""
    
    with app.app_context():
        print("🔄 MIGRAÇÃO: Convertendo fotos para Base64")
        print("=" * 50)
        
        funcionarios = Funcionario.query.filter(
            Funcionario.foto.isnot(None),
            Funcionario.foto != '',
            Funcionario.foto_base64.is_(None)
        ).all()
        
        print(f"Encontrados {len(funcionarios)} funcionários com fotos para migrar")
        
        migrados = 0
        erros = 0
        
        for funcionario in funcionarios:
            try:
                caminho_foto = os.path.join('static', funcionario.foto)
                
                if os.path.exists(caminho_foto):
                    # Verificar se é SVG ou imagem raster
                    if caminho_foto.lower().endswith('.svg'):
                        # Ler SVG e converter para base64
                        with open(caminho_foto, 'r', encoding='utf-8') as f:
                            svg_content = f.read()
                        
                        svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                        foto_base64_completo = f"data:image/svg+xml;base64,{svg_base64}"
                        
                        print(f"✅ {funcionario.nome} -> SVG convertido para Base64")
                    else:
                        # Processar imagem raster
                        with open(caminho_foto, 'rb') as f:
                            foto_data = f.read()
                        
                        # Redimensionar e otimizar
                        image = Image.open(io.BytesIO(foto_data))
                        image = image.convert('RGB')
                        image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                        
                        # Converter para base64
                        img_buffer = io.BytesIO()
                        image.save(img_buffer, format='JPEG', quality=85, optimize=True)
                        img_buffer.seek(0)
                        foto_otimizada = img_buffer.getvalue()
                        
                        foto_base64 = base64.b64encode(foto_otimizada).decode('utf-8')
                        foto_base64_completo = f"data:image/jpeg;base64,{foto_base64}"
                        
                        print(f"✅ {funcionario.nome} -> Imagem convertida para Base64")
                    
                    # Atualizar banco de dados
                    funcionario.foto_base64 = foto_base64_completo
                    migrados += 1
                    
                else:
                    print(f"⚠️ {funcionario.nome} -> Arquivo não encontrado: {caminho_foto}")
                    # Criar avatar SVG como fallback
                    from corrigir_fotos_funcionarios import criar_avatar_svg
                    svg_content = criar_avatar_svg(funcionario.codigo, funcionario.nome)
                    
                    # Converter SVG para base64
                    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                    funcionario.foto_base64 = f"data:image/svg+xml;base64,{svg_base64}"
                    
                    print(f"✅ {funcionario.nome} -> Avatar SVG criado")
                    migrados += 1
                    
            except Exception as e:
                print(f"❌ Erro ao migrar {funcionario.nome}: {e}")
                erros += 1
        
        # Salvar mudanças
        db.session.commit()
        
        print(f"\n🎉 MIGRAÇÃO CONCLUÍDA!")
        print(f"   ✅ Migrados: {migrados}")
        print(f"   ❌ Erros: {erros}")
        print(f"   📁 Fotos agora são 100% persistentes!")
        
        return migrados, erros

if __name__ == "__main__":
    migrar_fotos_para_base64()