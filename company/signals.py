from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver
from company.models import Company


@receiver(post_save, sender=Company)
def create_conversation_partition(sender, instance, created, **kwargs):
    pass
    # if created:
    #     with connection.cursor() as cursor:
    #         cursor.execute(
    #             f"""
    #             CREATE TABLE IF NOT EXISTS conversations_company_{instance.id}
    #             PARTITION OF conversations
    #             FOR VALUES IN ({instance.id});
    #             """
    #         )
