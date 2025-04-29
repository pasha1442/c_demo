from django.contrib import admin
from .models import ApiKey
from basics.admin import BaseModelAdmin
from dash.forms import ApiKeyProxyInlineForm

# from .models import Service

# class ServiceInline(admin.TabularInline):
#     model = Client.services.through
#     extra = 1

# class ApiKeysAdmin(admin.ModelAdmin):
#     list_display = ('id', 'key', 'created_at')

# class ServideAdmin(admin.ModelAdmin):
#     model = Service
#     list_display = ['name','cost']

# company_admin_site.register(ApiKey, ApiKeysAdmin)
# admin.site.register(Service, ServideAdmin)


@admin.register(ApiKey)
class ApiKeyAdmin(BaseModelAdmin):

    form = ApiKeyProxyInlineForm
    list_display_links = ('id', 'company', 'name', 'usage', 'grant', 'expired_at', 'created_at')
    list_display = ('id', 'company', 'name', 'key', 'usage', 'grant', 'expired_at', 'created_at')

    list_filter = ('is_active', 'is_deleted')
    readonly_fields = ('company', 'created_at', )
    search_fields = ('name', 'key')
    ordering = ('id',)
    fields = ('name', 'key', 'usage', 'grant', 'expired_at')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.company = request.user.current_company
        return form