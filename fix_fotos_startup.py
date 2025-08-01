#!/usr/bin/env python3
"""
Correção de fotos que sempre funciona - para ser chamada no startup
"""

def fix_fotos_startup():
    """Garante que todos os funcionários tenham fotos - modo startup otimizado"""
    try:
        from models import db, Funcionario
        import os
        import hashlib
        
        # Buscar funcionários sem foto válida
        funcionarios_problema = Funcionario.query.filter(
            db.or_(
                Funcionario.foto.is_(None),
                Funcionario.foto == '',
                ~Funcionario.foto.like('fotos_funcionarios/%')
            )
        ).all()
        
        if not funcionarios_problema:
            return True  # Todos têm fotos válidas
            
        print(f"🔧 Corrigindo {len(funcionarios_problema)} funcionários sem foto...")
        
        # Garantir diretório
        os.makedirs('static/fotos_funcionarios', exist_ok=True)
        
        for func in funcionarios_problema:
            codigo = func.codigo or f"F{func.id:04d}"
            
            # Criar SVG simples e rápido
            hash_nome = hashlib.md5(func.nome.encode()).hexdigest()
            cor = f"#{hash_nome[:6]}"
            
            palavras = func.nome.split()
            iniciais = (palavras[0][0] + palavras[-1][0]) if len(palavras) >= 2 else palavras[0][:2]
            
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
  <circle cx="60" cy="60" r="60" fill="{cor}"/>
  <text x="60" y="70" font-family="Arial" font-size="40" font-weight="bold" 
        text-anchor="middle" fill="white">{iniciais.upper()}</text>
</svg>'''
            
            # Salvar arquivo
            caminho = f"static/fotos_funcionarios/{codigo}.svg"
            with open(caminho, 'w', encoding='utf-8') as f:
                f.write(svg)
            
            # Atualizar banco
            func.foto = f"fotos_funcionarios/{codigo}.svg"
        
        db.session.commit()
        print(f"✅ {len(funcionarios_problema)} fotos corrigidas no startup")
        return True
        
    except Exception as e:
        print(f"⚠️ Erro na correção de fotos: {e}")
        return False