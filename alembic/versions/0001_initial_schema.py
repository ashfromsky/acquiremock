"""Initial pre-v2 schema baseline

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("webhook_url", sa.String(), nullable=False),
        sa.Column("redirect_url", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("otp_email", sa.String(), nullable=True),
        sa.Column("otp_code", sa.String(), nullable=True),
        sa.Column("card_mask", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("psp_transaction_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("webhook_attempts", sa.Integer(), nullable=False),
        sa.Column("webhook_last_attempt", sa.DateTime(), nullable=True),
        sa.Column("webhook_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_reference", "payments", ["reference"], unique=False)
    op.create_index("ix_payments_idempotency_key", "payments", ["idempotency_key"], unique=False)

    op.create_table(
        "successful_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("card_mask", sa.String(), nullable=False),
        sa.Column("redirect_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_successful_operations_payment_id",
        "successful_operations",
        ["payment_id"],
        unique=True,
    )
    op.create_index(
        "ix_successful_operations_email",
        "successful_operations",
        ["email"],
        unique=False,
    )

    op.create_table(
        "saved_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("card_token", sa.String(), nullable=False),
        sa.Column("card_hash", sa.String(), nullable=False),
        sa.Column("cvv_hash", sa.String(), nullable=False),
        sa.Column("expiry", sa.String(), nullable=False),
        sa.Column("card_mask", sa.String(), nullable=False),
        sa.Column("psp_provider", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_cards_email", "saved_cards", ["email"], unique=False)

    op.create_table(
        "webhook_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("webhook_url", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.String(), nullable=True),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_logs_payment_id", "webhook_logs", ["payment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_webhook_logs_payment_id", table_name="webhook_logs")
    op.drop_table("webhook_logs")
    op.drop_index("ix_saved_cards_email", table_name="saved_cards")
    op.drop_table("saved_cards")
    op.drop_index("ix_successful_operations_email", table_name="successful_operations")
    op.drop_index("ix_successful_operations_payment_id", table_name="successful_operations")
    op.drop_table("successful_operations")
    op.drop_index("ix_payments_idempotency_key", table_name="payments")
    op.drop_index("ix_payments_reference", table_name="payments")
    op.drop_table("payments")
