from rest_framework import serializers
from .models import Page, PageLayout, ComponentType, ComponentInstance, DataSource


class ComponentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentType
        fields = ['id', 'name', 'code', 'icon', 'description', 'default_config', 'is_global']


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'name', 'source_type', 'config', 'is_global']


class ComponentInstanceSerializer(serializers.ModelSerializer):
    component_type_details = ComponentTypeSerializer(source='component_type', read_only=True)
    
    class Meta:
        model = ComponentInstance
        fields = ['id', 'page', 'component_type', 'component_type_details', 'title', 
                  'instance_id', 'config', 'position', 'data_source']
        read_only_fields = ['id']


class ComponentInstanceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentInstance
        fields = ['title', 'config', 'position', 'data_source']


class PageLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageLayout
        fields = ['id', 'page', 'layout_config']
        read_only_fields = ['id']


class PageSerializer(serializers.ModelSerializer):
    layout = PageLayoutSerializer(read_only=True)
    components = ComponentInstanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Page
        fields = ['id', 'title', 'slug', 'description', 
                  'is_published', 'created_at', 'updated_at', 'layout', 'components']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PageCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ['id', 'title', 'slug', 'description', 'is_published']
        read_only_fields = ['id']


class PagePublishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ['is_published']


class PageLayoutUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageLayout
        fields = ['layout_config']


class ComponentInstanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentInstance
        fields = ['component_type', 'title', 'instance_id', 'config', 'position', 'data_source']

    def create(self, validated_data):
        # Get page from context (this will be set in the view)
        page_id = self.context.get('page_id')
        if not page_id:
            raise serializers.ValidationError("Page ID is required")
            
        try:
            page = Page.objects.get(id=page_id)
        except Page.DoesNotExist:
            raise serializers.ValidationError("Page with the provided ID does not exist")
        
        # Ensure is_deleted is set to False when creating
        instance = ComponentInstance(
            page=page,
            is_deleted=False,
            **validated_data
        )
        
        # Get company from the page to ensure proper company association
        if hasattr(page, 'company') and page.company:
            instance.company = page.company
            
        instance.save()
        return instance


class ComponentBulkUpdateSerializer(serializers.Serializer):
    components = serializers.ListField(
        child=serializers.DictField()
    )


class PageFullUpdateSerializer(serializers.Serializer):
    page = PageCreateUpdateSerializer(required=False)
    layout = PageLayoutUpdateSerializer(required=False)
    components = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
    removed_components = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate(self, data):
        # At least one of page, layout, or components must be provided
        if not any(k in data for k in ['page', 'layout', 'components']):
            raise serializers.ValidationError(
                "At least one of 'page', 'layout', or 'components' must be provided"
            )
        return data
