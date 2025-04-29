from django.contrib import admin
from .models import Page, PageLayout, ComponentType, ComponentInstance, DataSource


class PageLayoutInline(admin.StackedInline):
    model = PageLayout
    can_delete = False
    verbose_name_plural = 'Page Layout'


class ComponentInstanceInline(admin.TabularInline):
    model = ComponentInstance
    extra = 0
    readonly_fields = ('instance_id',)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'created_at', 'updated_at')
    list_filter = ('is_published', 'created_at', 'updated_at')
    search_fields = ('title', 'slug', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PageLayoutInline, ComponentInstanceInline]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'description', 'is_published')
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_global', 'created_at', 'updated_at')
    list_filter = ('is_global', 'created_at', 'updated_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'icon', 'description', 'default_config')
        }),
        ('Availability', {
            'fields': ('is_global',)
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ComponentInstance)
class ComponentInstanceAdmin(admin.ModelAdmin):
    list_display = ('title', 'component_type', 'page', 'instance_id', 'created_at', 'updated_at')
    list_filter = ('component_type', 'created_at', 'updated_at')
    search_fields = ('title', 'instance_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('page', 'component_type')
    fieldsets = (
        (None, {
            'fields': ('page', 'component_type', 'title', 'instance_id')
        }),
        ('Configuration', {
            'fields': ('config', 'position', 'data_source', 'data_source_creds')
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_type', 'is_global', 'created_by', 'created_at', 'updated_at')
    list_filter = ('source_type', 'is_global', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'source_type', 'config', 'created_by')
        }),
        ('Availability', {
            'fields': ('is_global',)
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
