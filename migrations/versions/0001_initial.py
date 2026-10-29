"""Initial lead responder schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("leads", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ghl_contact_id", sa.String(128), unique=True), sa.Column("name", sa.String(200)),
        sa.Column("phone", sa.String(40)), sa.Column("email", sa.String(320)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_leads_ghl_contact_id", "leads", ["ghl_contact_id"])
    op.create_index("ix_leads_phone", "leads", ["phone"])
    op.create_table("conversations", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), unique=True),
        sa.Column("status", sa.String(40), nullable=False), sa.Column("answers_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_table("messages", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", sa.String(12), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(128), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table("webhook_events", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(200), nullable=False), sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_key", name="uq_webhook_event_key"))
    op.create_index("ix_webhook_events_event_key", "webhook_events", ["event_key"])
    op.create_table("appointments", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("ghl_appointment_id", sa.String(128), unique=True),
        sa.Column("idempotency_key", sa.String(200), unique=True, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False))
    op.create_index("ix_appointments_conversation_id", "appointments", ["conversation_id"])


def downgrade():
    op.drop_table("appointments")
    op.drop_index("ix_webhook_events_event_key", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_leads_phone", table_name="leads")
    op.drop_index("ix_leads_ghl_contact_id", table_name="leads")
    op.drop_table("leads")
