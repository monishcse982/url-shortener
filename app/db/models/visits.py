from tortoise import fields
from tortoise.models import Model


class Visit(Model):
    id = fields.IntField(primary_key=True)
    link = fields.ForeignKeyField(
        "models.Link",
        related_name="visits",
        on_delete=fields.CASCADE,
    )
    visited_at = fields.DatetimeField(auto_now_add=True)
    user_agent = fields.CharField(max_length=512, null=True)
    referrer = fields.CharField(max_length=2048, null=True)
    ip_address = fields.CharField(max_length=64, null=True)

    class Meta:
        table = "visits"
        app = "models"
