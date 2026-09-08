"""Merge the independent support and dashboard branding migrations.

Keep both existing revisions intact so databases on either branch can upgrade.
The two branches change different tables; no additional DDL is necessary.
"""

revision = "0042_merge_support_branding"
down_revision = ("0041_dashboard_branding_asset", "0041_support_workflow")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
