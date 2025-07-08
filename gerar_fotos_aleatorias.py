#!/usr/bin/env python3
"""
Script para gerar fotos aleatórias para funcionários usando SVG
"""

import os
import sys
import random
from pathlib import Path

# Adicionar o diretório atual ao path do Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Funcionario

def gerar_svg_avatar(nome, codigo):
    """Gera um avatar SVG único baseado no nome e código do funcionário"""
    
    # Cores de fundo aleatórias
    cores_fundo = [
        "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
        "#1abc9c", "#34495e", "#e67e22", "#95a5a6", "#16a085"
    ]
    
    # Selecionar cor baseada no código para consistência
    cor_index = hash(codigo) % len(cores_fundo)
    cor_fundo = cores_fundo[cor_index]
    
    # Iniciais do nome
    palavras = nome.split()
    if len(palavras) >= 2:
        iniciais = palavras[0][0].upper() + palavras[1][0].upper()
    else:
        iniciais = palavras[0][:2].upper()
    
    # SVG com as iniciais
    svg_content = f'''<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
    <rect width="200" height="200" fill="{cor_fundo}"/>
    <text x="100" y="120" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="60" font-weight="bold">{iniciais}</text>
</svg>'''
    
    return svg_content

def gerar_fotos_funcionarios():
    """Gera fotos SVG para todos os funcionários"""
    
    print("🖼️  Gerando fotos aleatórias para funcionários...")
    
    with app.app_context():
        try:
            # Criar diretório se não existir
            fotos_dir = Path("static/fotos_funcionarios")
            fotos_dir.mkdir(exist_ok=True)
            
            funcionarios = Funcionario.query.all()
            total_funcionarios = len(funcionarios)
            
            print(f"📋 Processando {total_funcionarios} funcionários...")
            
            for i, funcionario in enumerate(funcionarios, 1):
                try:
                    # Gerar nome do arquivo baseado no código
                    nome_arquivo = f"{funcionario.codigo}.svg"
                    caminho_foto = fotos_dir / nome_arquivo
                    
                    # Gerar SVG
                    svg_content = gerar_svg_avatar(funcionario.nome, funcionario.codigo)
                    
                    # Salvar arquivo
                    with open(caminho_foto, 'w', encoding='utf-8') as f:
                        f.write(svg_content)
                    
                    # Atualizar campo foto no banco
                    funcionario.foto = f"fotos_funcionarios/{nome_arquivo}"
                    
                    print(f"✅ [{i:3d}/{total_funcionarios}] {funcionario.nome} ({funcionario.codigo}) -> {nome_arquivo}")
                    
                except Exception as e:
                    print(f"❌ Erro ao processar {funcionario.nome}: {str(e)}")
            
            # Salvar alterações no banco
            db.session.commit()
            
            print(f"\n🎉 Fotos geradas com sucesso!")
            print(f"📁 Localização: {fotos_dir.absolute()}")
            print(f"📊 Total processado: {total_funcionarios} funcionários")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro durante a geração: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    if gerar_fotos_funcionarios():
        print("\n✨ Processo concluído com sucesso!")
        print("\nPróximos passos:")
        print("1. As fotos SVG foram geradas na pasta static/fotos_funcionarios")
        print("2. Os caminhos foram atualizados no banco de dados")
        print("3. As fotos devem aparecer nos cards e perfis dos funcionários")
    else:
        print("\n💥 Falha na geração de fotos!")
        sys.exit(1)