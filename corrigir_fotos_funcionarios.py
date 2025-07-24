#!/usr/bin/env python3
"""
Script para corrigir e manter fotos dos funcionários persistentes
Este script deve ser executado sempre que o sistema for atualizado
"""

from app import app
from models import db, Funcionario
import os
from datetime import datetime

def criar_avatar_svg(codigo_funcionario, nome_funcionario):
    """Cria um avatar SVG personalizado para o funcionário"""
    # Gerar cor baseada no hash do nome
    import hashlib
    hash_nome = hashlib.md5(nome_funcionario.encode()).hexdigest()
    cor_fundo = f"#{hash_nome[:6]}"
    
    # Pegar iniciais do nome
    palavras = nome_funcionario.split()
    iniciais = ""
    if len(palavras) >= 2:
        iniciais = palavras[0][0] + palavras[-1][0]
    else:
        iniciais = palavras[0][:2] if palavras else "??"
    
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="60" cy="60" r="60" fill="{cor_fundo}"/>
  <text x="60" y="70" font-family="Arial, sans-serif" font-size="40" font-weight="bold" 
        text-anchor="middle" fill="white">{iniciais.upper()}</text>
</svg>'''
    
    return svg_content

def garantir_estrutura_diretorios():
    """Garante que todos os diretórios necessários existam"""
    diretorios = [
        os.path.join('static', 'images'),
        os.path.join('static', 'fotos'),
        os.path.join('static', 'fotos_funcionarios'), 
        os.path.join('static', 'uploads', 'funcionarios')
    ]
    
    for diretorio in diretorios:
        os.makedirs(diretorio, exist_ok=True)
        print(f"✓ Diretório garantido: {diretorio}")

def corrigir_fotos_funcionarios():
    """Corrige as fotos de todos os funcionários"""
    
    with app.app_context():
        print("=" * 60)
        print("CORREÇÃO DE FOTOS DE FUNCIONÁRIOS - SISTEMA PERSISTENTE")
        print("=" * 60)
        
        # Garantir estrutura de diretórios
        garantir_estrutura_diretorios()
        
        # Buscar todos os funcionários
        funcionarios = Funcionario.query.all()
        print(f"Encontrados {len(funcionarios)} funcionários")
        
        funcionarios_atualizados = 0
        
        for funcionario in funcionarios:
            codigo = funcionario.codigo or f"F{funcionario.id:04d}"
            
            # Caminhos possíveis para foto existente
            caminhos_possiveis = [
                f"fotos_funcionarios/{codigo}.svg",
                f"fotos/{codigo}.svg", 
                f"uploads/funcionarios/{codigo}.png",
                f"uploads/funcionarios/{codigo}.jpg"
            ]
            
            foto_encontrada = None
            
            # Verificar se existe alguma foto
            for caminho in caminhos_possiveis:
                caminho_completo = os.path.join('static', caminho)
                if os.path.exists(caminho_completo):
                    foto_encontrada = caminho
                    break
            
            # Se não encontrou foto, criar avatar SVG
            if not foto_encontrada:
                svg_content = criar_avatar_svg(codigo, funcionario.nome)
                caminho_svg = f"fotos_funcionarios/{codigo}.svg"
                caminho_completo = os.path.join('static', caminho_svg)
                
                with open(caminho_completo, 'w', encoding='utf-8') as f:
                    f.write(svg_content)
                
                foto_encontrada = caminho_svg
                print(f"  ✓ Avatar criado: {funcionario.nome} -> {caminho_svg}")
            
            # Atualizar banco de dados se necessário
            if funcionario.foto != foto_encontrada:
                funcionario.foto = foto_encontrada
                funcionarios_atualizados += 1
                print(f"  ✓ Foto atualizada no DB: {funcionario.nome} -> {foto_encontrada}")
        
        # Salvar mudanças
        db.session.commit()
        
        print(f"\n✅ CONCLUÍDO!")
        print(f"   - {funcionarios_atualizados} funcionários atualizados no banco")
        print(f"   - Todas as fotos agora são persistentes")
        print(f"   - Sistema pronto para produção")
        
        # Criar arquivo de controle
        with open('fotos_corrigidas.log', 'w') as f:
            f.write(f"Fotos corrigidas em: {datetime.now()}\n")
            f.write(f"Funcionários processados: {len(funcionarios)}\n")
            f.write(f"Funcionários atualizados: {funcionarios_atualizados}\n")

if __name__ == "__main__":
    corrigir_fotos_funcionarios()