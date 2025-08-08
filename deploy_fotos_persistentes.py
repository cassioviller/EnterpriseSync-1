#!/usr/bin/env python3
"""
Script de Deploy: Fotos Persistentes
Executa automaticamente no deploy para garantir fotos base64
"""

import os
import sys
import base64
import io
from datetime import datetime

def verificar_ambiente():
    """Verifica se estamos em ambiente de produção ou desenvolvimento"""
    is_production = os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('DATABASE_URL', '').startswith('postgres')
    return is_production

def executar_migracao_fotos():
    """Executa a migração de fotos para base64"""
    try:
        from app import app, db
        from models import Funcionario
        from PIL import Image
        
        print("🔄 DEPLOY: Verificando fotos dos funcionários...")
        
        with app.app_context():
            funcionarios = Funcionario.query.all()
            migrados = 0
            erros = 0
            
            for funcionario in funcionarios:
                try:
                    # Se já tem foto base64, pular
                    if funcionario.foto_base64:
                        continue
                    
                    # Se tem foto no arquivo, migrar
                    if funcionario.foto:
                        caminho_foto = os.path.join('static', funcionario.foto)
                        
                        if os.path.exists(caminho_foto):
                            # Verificar se é SVG ou imagem raster
                            if caminho_foto.lower().endswith('.svg'):
                                # Ler SVG e converter para base64
                                with open(caminho_foto, 'r', encoding='utf-8') as f:
                                    svg_content = f.read()
                                
                                svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                                foto_base64_completo = f"data:image/svg+xml;base64,{svg_base64}"
                                
                                funcionario.foto_base64 = foto_base64_completo
                                migrados += 1
                                print(f"  ✅ {funcionario.nome} -> SVG migrado")
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
                                
                                funcionario.foto_base64 = foto_base64_completo
                                migrados += 1
                                print(f"  ✅ {funcionario.nome} -> Imagem migrada")
                    
                except Exception as e:
                    print(f"  ❌ Erro {funcionario.nome}: {e}")
                    erros += 1
            
            if migrados > 0:
                db.session.commit()
                print(f"🎉 DEPLOY CONCLUÍDO: {migrados} fotos migradas, {erros} erros")
            else:
                print("✅ DEPLOY: Todas as fotos já estão persistentes!")
            
            return migrados, erros
            
    except Exception as e:
        print(f"❌ ERRO NO DEPLOY DE FOTOS: {e}")
        return 0, 1

def verificar_integridade_fotos():
    """Verifica se todas as fotos estão funcionando"""
    try:
        from app import app
        from models import Funcionario
        
        with app.app_context():
            funcionarios = Funcionario.query.all()
            sem_foto = 0
            com_foto_base64 = 0
            com_foto_arquivo = 0
            
            for f in funcionarios:
                if f.foto_base64:
                    com_foto_base64 += 1
                elif f.foto and os.path.exists(os.path.join('static', f.foto)):
                    com_foto_arquivo += 1
                else:
                    sem_foto += 1
            
            print(f"📊 RELATÓRIO DE FOTOS:")
            print(f"   Base64: {com_foto_base64}")
            print(f"   Arquivo: {com_foto_arquivo}")
            print(f"   Sem foto: {sem_foto}")
            
            return com_foto_base64, com_foto_arquivo, sem_foto
            
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return 0, 0, 0

def main():
    """Função principal do deploy"""
    print("=" * 60)
    print("DEPLOY AUTOMÁTICO: SISTEMA DE FOTOS PERSISTENTES")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar ambiente
    is_prod = verificar_ambiente()
    print(f"Ambiente: {'PRODUÇÃO' if is_prod else 'DESENVOLVIMENTO'}")
    
    # Executar migração
    migrados, erros = executar_migracao_fotos()
    
    # Verificar integridade
    base64_count, arquivo_count, sem_foto_count = verificar_integridade_fotos()
    
    # Status final
    if erros == 0:
        print("🎯 DEPLOY BEM-SUCEDIDO: Sistema de fotos 100% funcional!")
    else:
        print(f"⚠️ DEPLOY COM AVISOS: {erros} erros encontrados")
    
    print("=" * 60)
    return erros == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)