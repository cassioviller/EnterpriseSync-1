from flask import Blueprint, render_template
from flask_login import login_required

cadastros_hub_bp = Blueprint('cadastros_hub', __name__, url_prefix='/cadastros')


@cadastros_hub_bp.route('/')
@login_required
def index():
    return render_template('cadastros/index.html')
