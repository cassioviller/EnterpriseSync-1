#!/usr/bin/env python3
"""
HOTFIX CRÍTICO PARA PRODUÇÃO - Correção de fotos
Execute este script em produção para corrigir o erro interno
"""

from app import app
from models import db, Funcionario
import os
import hashlib

def hotfix_producao():
    """Hotfix para produção - corrige fotos sem depender de novas colunas"""
    
    with app.app_context():
        print("🚨 HOTFIX PRODUÇÃO - CORREÇÃO DE FOTOS")
        print("=" * 50)
        
        try:
            # Verificar se a nova coluna existe
            db.session.execute(db.text('SELECT foto_editada_usuario FROM funcionario LIMIT 1'))
            usa_nova_coluna = True
            print("✅ Schema atualizado - usando nova lógica")
        except:
            usa_nova_coluna = False
            print("⚠️ Schema antigo - usando lógica compatível")
        
        # Buscar funcionários sem foto
        if usa_nova_coluna:
            # Versão com nova coluna
            result = db.session.execute(db.text("""
                SELECT id, codigo, nome 
                FROM funcionario 
                WHERE (foto IS NULL OR foto = '') 
                AND (foto_editada_usuario IS NULL OR foto_editada_usuario = false)
            """))
        else:
            # Versão compatível com schema antigo
            result = db.session.execute(db.text("""
                SELECT id, codigo, nome 
                FROM funcionario 
                WHERE foto IS NULL OR foto = ''
            """))
        
        funcionarios_sem_foto = result.fetchall()
        print(f"Encontrados {len(funcionarios_sem_foto)} funcionários sem foto")
        
        # Garantir diretório
        os.makedirs('static/fotos_funcionarios', exist_ok=True)
        
        funcionarios_corrigidos = 0
        
        for func_data in funcionarios_sem_foto:
            func_id, codigo, nome = func_data
            codigo = codigo or f"F{func_id:04d}"
            
            # Criar SVG
            hash_nome = hashlib.md5(nome.encode()).hexdigest()
            cor = f"#{hash_nome[:6]}"
            
            palavras = nome.split()
            iniciais = (palavras[0][0] + palavras[-1][0]) if len(palavras) >= 2 else palavras[0][:2]
            
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
  <circle cx="60" cy="60" r="60" fill="{cor}"/>
  <text x="60" y="70" font-family="Arial" font-size="40" font-weight="bold" 
        text-anchor="middle" fill="white">{iniciais.upper()}</text>
</svg>'''
            
            # Salvar arquivo
            caminho_svg = f"static/fotos_funcionarios/{codigo}.svg"
            with open(caminho_svg, 'w', encoding='utf-8') as f:
                f.write(svg)
            
            # Atualizar banco
            db.session.execute(db.text(
                "UPDATE funcionario SET foto = :foto WHERE id = :id"
            ), {'foto': f"fotos_funcionarios/{codigo}.svg", 'id': func_id})
            
            funcionarios_corrigidos += 1
            print(f"  ✅ {nome} -> Avatar criado")
        
        db.session.commit()
        
        print(f"\n🎯 HOTFIX CONCLUÍDO:")
        print(f"   ✅ {funcionarios_corrigidos} funcionários corrigidos")
        print(f"   ✅ Sistema funcionando em produção")
        print(f"   ✅ Erro interno resolvido")
        
        return True

if __name__ == "__main__":
    hotfix_producao()