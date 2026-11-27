"""AcquireMock v2.0 security, reliability, and integer minor units

Revision ID: 0002_v2_security
Revises: 0001_initial
Create Date: 2026-11-27 00:01:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_v2_security"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    payment_indexes = {idx["name"] for idx in inspector.get_indexes("payments")}

    amount_alter_kwargs = {}
    if is_postgres:
        amount_alter_kwargs["postgresql_using"] = "ROUND(amount)::BIGINT"

    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Float(),
            type_=sa.BigInteger(),
            existing_nullable=False,
            **amount_alter_kwargs,
        )
        batch_op.add_column(
            sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("otp_expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("otp_resend_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("webhook_next_attempt_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("webhook_locked_until", sa.DateTime(), nullable=True)
        )
        if "ix_payments_idempotency_key" in payment_indexes:
            batch_op.drop_index("ix_payments_idempotency_key")
        batch_op.create_index(
            "ix_payments_idempotency_key",
            ["idempotency_key"],
            unique=True,
        )
        batch_op.create_index(
            "ix_payments_webhook_next_attempt_at",
            ["webhook_next_attempt_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_payments_status_expires_at",
            ["status", "expires_at"],
            unique=False,
        )

    with op.batch_alter_table("successful_operations") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Float(),
            type_=sa.BigInteger(),
            existing_nullable=False,
            **amount_alter_kwargs,
        )

    with op.batch_alter_table("webhook_logs") as batch_op:
        batch_op.add_column(
            sa.Column("trigger", sa.String(), nullable=False, server_default="auto")
        )

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_sessions_session_id", "admin_sessions", ["session_id"], unique=True
    )
    op.create_index(
        "ix_admin_sessions_username", "admin_sessions", ["username"], unique=False
    )
    op.create_index(
        "ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"], unique=False
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_location", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_idempotency_keys_idempotency_key",
        "idempotency_keys",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_idempotency_keys_payment_id",
        "idempotency_keys",
        ["payment_id"],
        unique=False,
    )

    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_challenges_email", "auth_challenges", ["email"], unique=True)
    op.create_index(
        "ix_auth_challenges_expires_at", "auth_challenges", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_auth_challenges_expires_at", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_email", table_name="auth_challenges")
    op.drop_table("auth_challenges")

    op.drop_index("ix_idempotency_keys_payment_id", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_idempotency_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_username", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_session_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")

    with op.batch_alter_table("webhook_logs") as batch_op:
        batch_op.drop_column("trigger")

    with op.batch_alter_table("successful_operations") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.BigInteger(),
            type_=sa.Float(),
            existing_nullable=False,
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_status_expires_at")
        batch_op.drop_index("ix_payments_webhook_next_attempt_at")
        batch_op.drop_index("ix_payments_idempotency_key")
        batch_op.create_index(
            "ix_payments_idempotency_key",
            ["idempotency_key"],
            unique=False,
        )
        batch_op.drop_column("webhook_locked_until")
        batch_op.drop_column("webhook_next_attempt_at")
        batch_op.drop_column("otp_resend_count")
        batch_op.drop_column("otp_expires_at")
        batch_op.drop_column("otp_attempts")
        batch_op.alter_column(
            "amount",
            existing_type=sa.BigInteger(),
            type_=sa.Float(),
            existing_nullable=False,
        )
