from functools import update_wrapper
from django.contrib import admin
from basics.services.thread_local_service import thread_local


# Register your models here.
class BaseAdminSite(admin.AdminSite):

    @staticmethod
    def set_extra_context(key, value):
        extra_context = thread_local.get('extra_context', {})
        extra_context[key] = value
        thread_local.set('extra_context', extra_context)

    @staticmethod
    def get_extra_context():
        return thread_local.get('extra_context')


class BaseModelAdmin(admin.ModelAdmin):
    pass


class BaseModelCompleteUserTimestampsAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

    def save_model(self, request, obj, form, change):
        # pre save stuff
        if obj._state.adding is True:
            obj.created_by = request.user
            obj.updated_by = request.user
        else:
            obj.updated_by = request.user
        obj.save()


class BaseInlineAdmin(admin.StackedInline):
    pass


class BaseTabularInlineAdmin(admin.TabularInline):
    pass


def wrap_admin_view(view, cacheable=False):
    """
    Use this to wrap view functions used in admin dashboard
    Note: Only the views that require a admin login
    """
    from django.contrib import admin

    def wrapper(*args, **kwargs):
        return admin.site.admin_view(view, cacheable)(*args, **kwargs)

    wrapper.admin_site = admin.site
    return update_wrapper(wrapper, view)
