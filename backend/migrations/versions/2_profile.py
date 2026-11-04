"""Personal profiles; permission and lab membership remain on the account."""
from alembic import op
import sqlalchemy as sa
revision = '2_profile'
down_revision = 'c1950f8c6289'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('userprofile',sa.Column('user_id',sa.Uuid(),nullable=False),sa.Column('bio',sa.String(500),nullable=False),sa.Column('phone',sa.String(30),nullable=False),sa.ForeignKeyConstraint(['user_id'],['user.id']),sa.PrimaryKeyConstraint('user_id'))

def downgrade():
    op.drop_table('userprofile')
