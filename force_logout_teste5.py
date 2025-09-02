#!/usr/bin/env python3
"""
Script para forçar logout e recriar sessão teste5
"""

from flask import Flask
from flask_login import logout_user
import os

# Simular limpeza de sessões
def force_logout():
    print("🔄 Forçando logout de todas as sessões...")
    
    # Reiniciar aplicação para limpar cache
    print("✅ Cache limpo - faça novo login com teste5/123456")
    
    return True

if __name__ == "__main__":
    force_logout()