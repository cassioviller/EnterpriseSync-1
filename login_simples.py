"""
Sistema de login simplificado para acesso direto ao dashboard
"""

from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, redirect, url_for, session
import sqlite3
import os

def criar_usuario_sqlite():
    """Criar usuário admin em SQLite local se não existir"""
    try:
        # Conectar ao SQLite local
        conn = sqlite3.connect('local_users.db')
        cursor = conn.cursor()
        
        # Criar tabela se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                tipo TEXT DEFAULT 'ADMIN'
            )
        ''')
        
        # Verificar se admin já existe
        cursor.execute('SELECT * FROM usuarios WHERE email = ?', ('admin@sige.com',))
        if not cursor.fetchone():
            # Criar admin
            password_hash = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO usuarios (email, password_hash, nome, tipo)
                VALUES (?, ?, ?, ?)
            ''', ('admin@sige.com', password_hash, 'Administrador SIGE', 'SUPER_ADMIN'))
            
            conn.commit()
            print("✅ Usuário admin criado em SQLite local")
        else:
            print("ℹ️ Usuário admin já existe")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar usuário: {e}")
        return False

def verificar_login_sqlite(email, password):
    """Verificar login no SQLite local"""
    try:
        conn = sqlite3.connect('local_users.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM usuarios WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        
        if user_data and check_password_hash(user_data[2], password):
            # Simular objeto usuário
            class MockUser:
                def __init__(self, data):
                    self.id = data[0]
                    self.email = data[1]
                    self.nome = data[3]
                    self.tipo_usuario = data[4]
                    self.is_authenticated = True
                    self.is_active = True
                    self.is_anonymous = False
                
                def get_id(self):
                    return str(self.id)
            
            conn.close()
            return MockUser(user_data)
        
        conn.close()
        return None
        
    except Exception as e:
        print(f"❌ Erro na verificação de login: {e}")
        return None

def setup_login_bypass():
    """Configurar bypass de login para acesso direto"""
    
    @app.before_request
    def bypass_login():
        # Apenas para desenvolvimento - bypass automático
        if request.endpoint and request.endpoint != 'main.login':
            # Simular usuário logado
            if 'user_id' not in session:
                session['user_id'] = 1
                session['user_email'] = 'admin@sige.com'
                session['user_name'] = 'Admin SIGE'
                session['user_type'] = 'SUPER_ADMIN'
    
    print("🔓 Sistema de login em modo de desenvolvimento")

if __name__ == '__main__':
    criar_usuario_sqlite()
    setup_login_bypass()