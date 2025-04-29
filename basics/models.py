import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.deletion import Collector

User = get_user_model()


class BaseQuerySet(models.QuerySet):
    def delete(self):
        # Delete Dependent...
        del_query = self._chain()

        del_query._for_write = True

        # Disable non-supported fields.
        del_query.query.select_for_update = False
        del_query.query.select_related = False
        del_query.query.clear_ordering()

        collector = Collector(using='default')
        collector.collect(del_query)

        # Dependencies...
        self.manage_delete_dependency(collector)

        update = {
            'deleted_at': datetime.datetime.utcnow()
        }
        return super(BaseQuerySet, self).update(**update)

    def hard_delete(self):
        return super(BaseQuerySet, self).delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.exclude(is_deleted=False)

    @staticmethod
    def manage_delete_dependency(collector):
        for fast_deletes in collector.fast_deletes:
            if len(fast_deletes):
                for delete_obj in fast_deletes:
                    delete_obj.deleted_at = datetime.datetime.utcnow()
                    delete_obj.save()

        for model, data in collector.data.items():
            for obj in data:
                obj.deleted_at = datetime.datetime.utcnow()
                obj.save()


class BaseManager(models.Manager.from_queryset(BaseQuerySet)):
    def __init__(self, *args, **kwargs) -> None:
        self.alive_only = kwargs.pop('alive_only', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.alive_only:
            queryset = queryset.alive()
        return queryset

    def hard_delete(self):
        return self.get_queryset().hard_delete()


class BaseModel(models.Model):
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self):
        # Delete Dependent...
        collector = Collector(using='default')
        collector.collect([self], keep_parents=False)

        # Dependencies...
        BaseQuerySet.manage_delete_dependency(collector)

        self.deleted_at = datetime.datetime.utcnow()
        self.save()


#
# class BaseManager(models.Manager):
#
#     def get_table_name(self):
#         return self.model.get_table_name()
#
#
# class BaseModel(models.Model):
#     objects = BaseManager()
#
#     @classmethod
#     def get_table_name(cls):
#         if hasattr(cls._meta, 'db_table'):
#             return cls._meta.db_table
#
#         return cls.objects.get_table_name()
#
#     @classmethod
#     def get_field_names(cls, exclude=()):
#         return [f.name for f in cls._meta.get_fields() if f.name not in exclude]
#
#     class Meta:
#         abstract = True
#
#
# class BaseModelTimestamps(BaseModel):
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     objects = BaseModelTimestampsManager()
#
#     class Meta:
#         abstract = True
#
#
class BaseModelCompleteUserTimestamps(BaseModel):
    created_by = models.ForeignKey(to=User, on_delete=models.DO_NOTHING, null=True, blank=True,
                                   related_name='%(class)s_created_by')
    updated_by = models.ForeignKey(to=User, on_delete=models.DO_NOTHING, null=True, blank=True,
                                   related_name='%(class)s_updated_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #  objects = BaseModelCompleteUserTimestampsManager()

    class Meta:
        abstract = True


class BaseModelPartialUserTimestamps(BaseModel):
    created_by = models.ForeignKey(to=User, on_delete=models.DO_NOTHING, null=True, blank=True,
                                   related_name='%(class)s_created_by')
    created_at = models.DateTimeField(auto_now_add=True)

    # objects = BaseModelPartialUserTimestampsManager()

    class Meta:
        abstract = True
