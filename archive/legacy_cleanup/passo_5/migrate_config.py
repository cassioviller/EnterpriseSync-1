#!/usr/bin/env python3
"""
Configuração do Flask-Migrate para SIGE v8.0
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Criar app para migrações
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///sige.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Inicializar SQLAlchemy
db = SQLAlchemy(app, model_class=Base)

# Inicializar Flask-Migrate
migrate = Migrate(app, db)

# Importar todos os modelos para que as migrações os detectem
with app.app_context():
    from models import *

if __name__ == '__main__':
    app.run()