"""Fix restaurante schema duplicated columns

Revision ID: fix_restaurante
Revises: fa53b2005129
Create Date: 2025-07-25 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_restaurante'
down_revision = 'fa53b2005129'
branch_labels = None
depends_on = None

def upgrade():
    """Remove duplicated column and ensure correct schema"""
    
    # Remove coluna duplicada se existir
    try:
        op.drop_column('restaurante', 'contato_responsavel')
    except:
        pass  # Coluna pode não existir
    
    # Garantir que todas as colunas necessárias existem
    try:
        op.add_column('restaurante', sa.Column('responsavel', sa.String(100), nullable=True))
    except:
        pass  # Coluna pode já existir
    
    try:
        op.add_column('restaurante', sa.Column('preco_almoco', sa.Float(), nullable=True, default=0.0))
    except:
        pass
    
    try:
        op.add_column('restaurante', sa.Column('preco_jantar', sa.Float(), nullable=True, default=0.0))
    except:
        pass
    
    try:
        op.add_column('restaurante', sa.Column('preco_lanche', sa.Float(), nullable=True, default=0.0))
    except:
        pass
    
    try:
        op.add_column('restaurante', sa.Column('observacoes', sa.Text(), nullable=True))
    except:
        pass
    
    try:
        op.add_column('restaurante', sa.Column('admin_id', sa.Integer(), nullable=True))
    except:
        pass
    
    # Adicionar foreign key se não existir
    try:
        op.create_foreign_key('fk_restaurante_admin_id', 'restaurante', 'usuario', ['admin_id'], ['id'])
    except:
        pass  # FK pode já existir

def downgrade():
    """Reverter mudanças se necessário"""
    pass  # Não reverter por segurança