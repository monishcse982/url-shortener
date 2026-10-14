from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.fields.relational import ReverseRelation
from tortoise.models import Model

if TYPE_CHECKING:
    from app.db.models.visits import Visit


class Link(Model):
    id = fields.IntField(primary_key=True)
    short_code = fields.CharField(max_length=32, unique=True, db_index=True, null=False)
    original_url = fields.CharField(max_length=2048, null=False)
    title = fields.CharField(max_length=256, null=True)
    max_visits = fields.IntField(null=True)
    expires_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=False)
    policy = fields.JSONField(default=dict, null=True)
    is_deleted = fields.BooleanField(default=False, null=False)
    visit_count = fields.IntField(default=0)
    visits: ReverseRelation["Visit"]

    class Meta:
        table = "links"
        app = "models"
