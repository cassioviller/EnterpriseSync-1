#!/usr/bin/env python3
"""
Script para corrigir imports circulares e consolidar models
"""

import os
import shutil

def consolidate_models():
    """Consolida todos os models em um único arquivo"""
    
    # Backup dos arquivos originais
    if os.path.exists('models_backup.py'):
        os.remove('models_backup.py')
    shutil.copy('models.py', 'models_backup.py')
    
    # Ler conteúdo dos arquivos de models
    models_content = ""
    models_servicos_content = ""
    models_propostas_content = ""
    
    if os.path.exists('models.py'):
        with open('models.py', 'r') as f:
            models_content = f.read()
    
    if os.path.exists('models_servicos.py'):
        with open('models_servicos.py', 'r') as f:
            models_servicos_content = f.read()
            
    if os.path.exists('models_propostas.py'):
        with open('models_propostas.py', 'r') as f:
            models_propostas_content = f.read()
    
    # Consolidar em um único arquivo
    consolidated_content = """# MODELS CONSOLIDADOS - SIGE v8.0
# Arquivo único para eliminar dependências circulares

from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func, JSON
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import uuid
import secrets

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

"""
    
    # Remover imports e db definitions dos conteúdos
    def clean_content(content):
        lines = content.split('\n')
        cleaned_lines = []
        skip_imports = True
        
        for line in lines:
            # Pular imports e definições de db
            if line.strip().startswith('from ') or line.strip().startswith('import '):
                continue
            if 'db = SQLAlchemy' in line:
                continue
            if 'class Base(' in line:
                continue
                
            # Começar a adicionar linhas após encontrar primeira class
            if line.strip().startswith('class ') and not 'Base(' in line:
                skip_imports = False
                
            if not skip_imports:
                cleaned_lines.append(line)
                
        return '\n'.join(cleaned_lines)
    
    # Adicionar conteúdo limpo
    if models_content:
        consolidated_content += clean_content(models_content)
        consolidated_content += "\n\n"
    
    if models_servicos_content:
        consolidated_content += "# MODELS DE SERVIÇOS\n"
        consolidated_content += clean_content(models_servicos_content)
        consolidated_content += "\n\n"
        
    if models_propostas_content:
        consolidated_content += "# MODELS DE PROPOSTAS\n" 
        consolidated_content += clean_content(models_propostas_content)
        consolidated_content += "\n\n"
    
    # Escrever arquivo consolidado
    with open('models.py', 'w') as f:
        f.write(consolidated_content)
    
    print("✅ Models consolidados em models.py")
    print("✅ Backup salvo em models_backup.py")
    
    # Remover arquivos separados para evitar conflitos
    for file in ['models_servicos.py', 'models_propostas.py']:
        if os.path.exists(file):
            os.rename(file, f"{file}.disabled")
            print(f"✅ {file} desabilitado")

if __name__ == '__main__':
    consolidate_models()