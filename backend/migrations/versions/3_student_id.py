"""Optional student identifier; stored as text to preserve leading zeros."""
from alembic import op
import sqlalchemy as sa
revision = '3_student_id'
down_revision = '2_profile'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('userprofile', sa.Column('student_id', sa.String(32), server_default='', nullable=False))

def downgrade():
    op.drop_column('userprofile', 'student_id')
