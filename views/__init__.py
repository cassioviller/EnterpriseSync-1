from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

from views.helpers import safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico, verificar_dados_producao

from views import auth
from views import dashboard
from views import users
from views import employees
from views import obras
from views import vehicles
from views import rdo
from views import api
from views import admin
