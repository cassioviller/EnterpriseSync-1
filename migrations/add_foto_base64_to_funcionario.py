#!/usr/bin/env python3
"""
Migração: Adicionar coluna foto_base64 à tabela funcionario
Seguindo o padrão estabelecido para admin_id e kpi_associado
"""

import os
import sys
import base64
import io
from datetime import datetime
from sqlalchemy import text

# Adicionar o diretório raiz ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def executar_migracao():
    """Executa a migração da coluna foto_base64"""
    
    try:
        from app import app, db
        from models import Funcionario
        
        with app.app_context():
            print("=" * 60)
            print("MIGRAÇÃO: Adicionando coluna foto_base64 à tabela funcionario")
            print("=" * 60)
            print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. Verificar se a coluna já existe
            print("\n🔍 Verificando se a coluna foto_base64 já existe...")
            
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'funcionario' 
                AND column_name = 'foto_base64'
            """)).fetchone()
            
            if result:
                print(f"✅ Coluna foto_base64 já existe: {result[1]}")
                coluna_existe = True
            else:
                print("❌ Coluna foto_base64 não existe")
                coluna_existe = False
            
            # 2. Criar a coluna se não existir
            if not coluna_existe:
                print("\n🔧 Criando coluna foto_base64...")
                try:
                    db.session.execute(text("ALTER TABLE funcionario ADD COLUMN foto_base64 TEXT"))
                    db.session.commit()
                    print("✅ Coluna foto_base64 criada com sucesso!")
                except Exception as e:
                    print(f"❌ Erro ao criar coluna: {e}")
                    db.session.rollback()
                    return False
            
            # 3. Verificar funcionários existentes
            print("\n📊 Verificando funcionários existentes...")
            funcionarios = Funcionario.query.all()
            print(f"Total de funcionários: {len(funcionarios)}")
            
            # 4. Migrar fotos existentes para base64
            print("\n🔄 Migrando fotos existentes para base64...")
            migrados = 0
            erros = 0
            
            for funcionario in funcionarios:
                try:
                    # Pular se já tem foto_base64
                    if funcionario.foto_base64:
                        continue
                    
                    # Se tem foto em arquivo, migrar
                    if funcionario.foto:
                        caminho_foto = os.path.join('static', funcionario.foto)
                        
                        if os.path.exists(caminho_foto):
                            # Processar SVG
                            if caminho_foto.lower().endswith('.svg'):
                                with open(caminho_foto, 'r', encoding='utf-8') as f:
                                    svg_content = f.read()
                                
                                svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                                foto_base64_completo = f"data:image/svg+xml;base64,{svg_base64}"
                                
                                funcionario.foto_base64 = foto_base64_completo
                                migrados += 1
                                print(f"  ✅ {funcionario.nome} -> SVG migrado")
                            
                            # Processar imagens raster
                            else:
                                try:
                                    from PIL import Image
                                    
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
                                    
                                except ImportError:
                                    print(f"  ⚠️ PIL não disponível, pulando {funcionario.nome}")
                
                except Exception as e:
                    print(f"  ❌ Erro ao migrar {funcionario.nome}: {e}")
                    erros += 1
            
            # 5. Commit das alterações
            if migrados > 0:
                try:
                    db.session.commit()
                    print(f"\n💾 Alterações salvas: {migrados} fotos migradas")
                except Exception as e:
                    print(f"\n❌ Erro ao salvar: {e}")
                    db.session.rollback()
                    return False
            
            # 6. Verificação final
            print("\n🔍 Verificação final...")
            funcionarios_com_base64 = Funcionario.query.filter(Funcionario.foto_base64.isnot(None)).count()
            print(f"Funcionários com foto_base64: {funcionarios_com_base64}")
            
            # 7. Resultado final
            print("\n" + "=" * 60)
            print("RESULTADO DA MIGRAÇÃO:")
            print(f"✅ Coluna foto_base64: {'Criada' if not coluna_existe else 'Já existia'}")
            print(f"✅ Fotos migradas: {migrados}")
            print(f"❌ Erros: {erros}")
            print(f"📊 Total com base64: {funcionarios_com_base64}")
            
            if erros == 0:
                print("🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            else:
                print(f"⚠️ MIGRAÇÃO CONCLUÍDA COM {erros} AVISOS")
            
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO NA MIGRAÇÃO: {e}")
        return False

if __name__ == "__main__":
    success = executar_migracao()
    sys.exit(0 if success else 1)