import functools
from json import dumps, loads

from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="Link",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "short_code",
                    fields.CharField(unique=True, db_index=True, max_length=32),
                ),
                ("owner_sub", fields.CharField(db_index=True, max_length=128)),
                ("original_url", fields.CharField(max_length=2048)),
                ("title", fields.CharField(null=True, max_length=256)),
                ("max_visits", fields.IntField(null=True)),
                (
                    "expires_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                (
                    "policy",
                    fields.JSONField(
                        null=True,
                        default=dict,
                        encoder=functools.partial(dumps, separators=(",", ":")),
                        decoder=loads,
                    ),
                ),
                ("is_deleted", fields.BooleanField(default=False)),
                ("visit_count", fields.IntField(default=0)),
            ],
            options={"table": "links", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Visit",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "link",
                    fields.ForeignKeyField(
                        "models.Link",
                        source_field="link_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="visits",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("visited_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("user_agent", fields.CharField(null=True, max_length=512)),
                ("referrer", fields.CharField(null=True, max_length=2048)),
                ("ip_address", fields.CharField(null=True, max_length=64)),
            ],
            options={"table": "visits", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
