from django.contrib import admin
from basics.services.thread_local_service import thread_local
from basics.admin import BaseAdminSite, BaseModelAdmin
from company.models import CompanyCustomer, CompanyPostProcessing, CompanyTest, CompanySetting, Company, CompanyEntity, \
    GlobalMixedCompanyBaseManager, CompanySettingProxyModel
# CompanyUser,
from django.contrib.auth.admin import UserAdmin
from basics.admin import BaseTabularInlineAdmin
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from django.urls import path
from django.db.models import Q
from dash.models import ApiKeyProxyModel
from dash.forms import ApiKeyProxyInlineForm


class CompanyAPIKeys(BaseTabularInlineAdmin):
    model = ApiKeyProxyModel
    extra = 1
    ordering = ("-created_at",)
    fields = ('company', 'key', 'created_at')
    readonly_fields = ('company', 'created_at',)
    form = ApiKeyProxyInlineForm

    # def get_queryset(self, request):
    #     queryset = super().get_queryset(request)
    #     return queryset.prefetch_related('created_by', 'updated_by')

    def save_model(self, request, obj, form, change):
        # pre save stuff
        if obj._state.adding is True:
            obj.created_by = request.user
            obj.updated_by = request.user
        else:
            obj.updated_by = request.user
        obj.save()


class CompanySettingInlineAdmin(BaseTabularInlineAdmin):
    model = CompanySettingProxyModel
    extra = 1
    ordering = ("-created_at",)
    fields = ('key', 'value', 'created_at')
    readonly_fields = ('company', 'created_at')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset


@admin.register(CompanySetting)
class CompanySettingAdminSite(BaseModelAdmin):
    list_display_links = ('id', 'company', 'key', 'value', 'is_active', 'is_global', 'is_deleted', 'created_at')
    list_display = ('id', 'company', 'key', 'value', 'is_active', 'is_global', 'is_deleted', 'created_at')
    list_filter = ('is_global', 'is_active')
    readonly_fields = ('created_at', 'deleted_at')
    search_fields = ('key',)
    ordering = ('id',)
    fields = ('is_global', 'is_active', 'is_deleted', 'key', 'value', 'created_at', 'deleted_at')


@admin.register(Company)
class CompanyAdminSite(BaseModelAdmin):
    site_header = 'SiteName'
    inlines = [CompanySettingInlineAdmin, CompanyAPIKeys]
    list_display_links = ('id', 'name', 'current_env', 'is_active', 'is_deleted', 'created_at')
    list_display = (
        'id', 'name', 'current_env', 'get_frontend_link',
        'langfuse_secret_key', 'langfuse_public_key', 'is_active', 'is_deleted', 'comment', 'created_at')
    list_filter = ('is_active', 'is_deleted')
    readonly_fields = ('created_at', 'deleted_at')
    search_fields = ('name', 'prefix')
    ordering = ('id',)
    fields = (
        'name', 'current_env', 'code', 'prefix', 'frontend_link',
        # 'workflow_processing_queue',
        'langfuse_project_id', 'langfuse_secret_key', 'langfuse_public_key',
        'openmeter_secret_key',
        'comment',
        'is_active',
        'is_deleted', 'created_at', 'deleted_at')

    # def get_inline_instances(self, request, obj=None):
    #     inline_instances = super().get_inline_instances(request, obj)
    #     # Pass parent admin instance to the inline
    #     for inline in inline_instances:
    #         if isinstance(inline, CompanySettingInlineAdmin):
    #             inline.company_obj = obj
    #             pass
    #     return inline_instances

    def get_frontend_link(self, obj):

        if obj and obj.frontend_link:
            return format_html(
                '<a target="_blank" class="button" href="{}"><b>Link</b></a>', obj.frontend_link)
        else:
            return "-"

    get_frontend_link.short_description = "Demo Link"

    @staticmethod
    def set_company(company):
        thread_local.set('company', company)

    @staticmethod
    def get_company():
        return thread_local.get('company')


@admin.register(CompanyEntity)
class CompanyEntityAdminSite(BaseModelAdmin):
    list_display_links = (
        'id', 'company', 'type', 'reference_id', 'data', 'is_active', 'is_global', 'is_deleted', 'created_at')
    list_display = (
        'id', 'company', 'type', 'reference_id', 'data', 'is_active', 'is_global', 'is_deleted', 'created_at')
    list_filter = ('is_global', 'is_active')
    readonly_fields = ('created_at', 'deleted_at')
    search_fields = ('reference_id', 'type')
    ordering = ('id',)


@admin.register(CompanyPostProcessing)
class CompanyEntityAdminSite(BaseModelAdmin):
    list_display = ('id', 'session_id', 'session_nature', 'action')
    search_fields = ('session_id',)


class CompanySecondaryAdminSite(BaseAdminSite):
    site_header = 'SiteName'

    list_display_links = ('id', 'name', 'code', 'prefix', 'is_active', 'is_deleted', 'created_at', 'deleted_At')
    list_display = ('id', 'name', 'code', 'prefix', 'is_active', 'is_deleted', 'created_at', 'deleted_At')
    list_filter = ('is_active', 'is_deleted')
    readonly_fields = ('created_at', 'deleted_at')
    search_fields = ('name', 'prefix')
    ordering = ('id',)
    fields = ('name', 'code', 'prefix', 'is_active', 'is_deleted', 'created_at', 'deleted_At')

    @staticmethod
    def set_company(company):
        thread_local.set('company', company)

    @staticmethod
    def get_company():
        return thread_local.get('company')


class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'set_company_link')

    def set_company_link(self, obj):
        current_active_company = company_admin_site.get_company()
        company = get_object_or_404(Company, pk=obj.id)
        if current_active_company and obj.id == current_active_company.id:
            return "Active"
        else:
            return format_html(
                '<a class="button" href="{}">Set active company</a>',
                reverse('admin:set_active_company', args=[obj.pk])
            )

    set_company_link.short_description = 'Set Company'
    set_company_link.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('set_active_company/<int:company_id>/', self.admin_site.admin_view(self.set_active_company),
                 name='set_active_company'),
        ]
        return custom_urls + urls

    def set_active_company(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id)
        if not company or not company.is_active:
            self.message_user(request, "Cannot set this company as active", level='error')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        request.session['company'] = company.id  # type: ignore
        company_admin_site.set_company(company)
        self.message_user(request, f"Successfully set {company.name} as active")
        return HttpResponseRedirect('/company-admin/')


class CompanyUserAdmin(UserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        active_company = company_admin_site.get_company()
        return qs.filter(
            (Q(company=active_company) | Q(is_global=True)) & ~Q(is_superuser=True)
        )


class CompanySettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'key')
    search_fields = ('key',)


company_admin_site = CompanySecondaryAdminSite(name='company_admin_site')
# admin.site.register(Company, CompanyAdmin)
# company_admin_site.register(CompanyUser,CompanyUserAdmin)
# company_admin_site.register(CompanyTest)
# company_admin_site.register(CompanySetting, CompantSettingAdmin)
# company_admin_site.register(CompanyCustomer)
# company_admin_site.register(CompanyEntity, CompanyEntityAdmin)
# company_admin_site.register(CompanyPostProcessing, CompanyPostProcessingAdmin)
