from django.db import models
from django.contrib.auth import get_user_model
from company.models import CompanyBaseModel, GlobalMixedCompanyBaseModel

User = get_user_model()


class Page(CompanyBaseModel):
    """Model for storing basic page information"""
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    # created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_pages')
    is_published = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    
    class Meta:
        db_table = 'insights_pages'
        verbose_name = 'Page'
        verbose_name_plural = 'Pages'


class PageLayout(CompanyBaseModel):
    """Model for storing page layout configuration"""
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name='layout')
    layout_config = models.JSONField(default=dict)
    
    def __str__(self):
        return f"Layout for {self.page.title}"
    
    class Meta:
        db_table = 'insights_page_layouts'
        verbose_name = 'Page Layout'
        verbose_name_plural = 'Page Layouts'


class ComponentType(GlobalMixedCompanyBaseModel):
    """Model for defining available component types"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    default_config = models.JSONField(default=dict)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'insights_component_types'
        verbose_name = 'Component Type'
        verbose_name_plural = 'Component Types'


class ComponentInstance(CompanyBaseModel):
    """Model for tracking instances of components placed on pages"""
    page = models.ForeignKey(Page, related_name='components', on_delete=models.CASCADE)
    component_type = models.ForeignKey(ComponentType, related_name='instances', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    instance_id = models.CharField(max_length=100)
    config = models.JSONField(default=dict)
    position = models.JSONField(default=dict)
    data_source = models.JSONField(default=dict, blank=True, null=True)
    data_source_creds = models.JSONField(default=dict, blank=True, null=True)
    def __str__(self):
        return f"{self.title} ({self.component_type.name})"
    
    class Meta:
        db_table = 'insights_component_instances'
        verbose_name = 'Component Instance'
        verbose_name_plural = 'Component Instances'
        unique_together = ('page', 'instance_id')


class DataSource(GlobalMixedCompanyBaseModel):
    """Model for defining data sources for components"""
    SOURCE_TYPES = (
        ('neo4j', 'Neo4j'),
        ('bigquery', 'BigQuery'),
        ('api', 'API'),
        ('static', 'Static'),
    )
    
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    config = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_data_sources')
    
    def __str__(self):
        return f"{self.name} ({self.source_type})"
    
    class Meta:
        db_table = 'insights_data_sources'
        verbose_name = 'Data Source'
        verbose_name_plural = 'Data Sources'
