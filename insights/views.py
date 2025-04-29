from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
from django.http import JsonResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
from rest_framework import mixins
from chat.models import ConversationSession
from chat.auth import ApiKeyAuthentication

from .models import Page, PageLayout, ComponentType, ComponentInstance, DataSource
from .serializers import (
    PageSerializer, 
    PageCreateUpdateSerializer, 
    PagePublishSerializer,
    PageFullUpdateSerializer,
    ComponentTypeSerializer, 
    ComponentInstanceSerializer,
    ComponentInstanceUpdateSerializer,
    ComponentInstanceCreateSerializer,
    ComponentBulkUpdateSerializer,
    PageLayoutSerializer,
    PageLayoutUpdateSerializer,
    DataSourceSerializer
)


# API ViewSets
@method_decorator(csrf_exempt, name='dispatch')
class PageViewSet(viewsets.ModelViewSet):
    """API endpoint for pages"""
    authentication_classes = [ApiKeyAuthentication]
    
    def get_queryset(self):
        return Page.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PageCreateUpdateSerializer
        elif self.action == 'publish':
            return PagePublishSerializer
        elif self.action == 'full_update':
            return PageFullUpdateSerializer
        return PageSerializer
    
    def perform_create(self, serializer):
        # Save the page with the current user as creator
        page = serializer.save()
        # Create an empty layout for the page
        PageLayout.objects.create(page=page, layout_config={'columns': 12, 'rowHeight': 50})
    
    @action(detail=True, methods=['get'], url_path='full')
    def full_config(self, request, pk=None):
        """Get the full configuration of a page including layout and components"""
        page = self.get_object()
        
        serializer = PageSerializer(page)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish or unpublish a page"""
        page = self.get_object()
        serializer = self.get_serializer(page, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PageSerializer(page).data)
    
    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_page(self, request, pk=None):
        """Delete a page along with all its component instances"""
        try:
            # Explicitly get the page by ID instead of using self.get_object()
            page = Page.objects.get(id=pk)
            page_id = page.id  # Store the ID before deletion
            
            with transaction.atomic():
                # Hard delete all component instances associated with the page
                components = ComponentInstance.objects.filter(page=page)
                for component in components:
                    # Use hard_delete() to actually remove from database
                    component.hard_delete() if hasattr(component, 'hard_delete') else component.delete()
                
                # Delete the page layout
                try:
                    # Check if layout exists
                    layout = PageLayout.objects.get(page=page)
                    layout_id = layout.id
                    # Use hard_delete() to actually remove from database
                    layout.hard_delete() if hasattr(layout, 'hard_delete') else layout.delete()
                except PageLayout.DoesNotExist:
                    pass
                
                # Hard delete the page itself
                # Use hard_delete() to actually remove from database
                if hasattr(page, 'hard_delete'):
                    page.hard_delete()
                else:
                    # If hard_delete is not available on the instance, try using the manager
                    if hasattr(Page.objects, 'hard_delete'):
                        Page.objects.filter(id=page_id).hard_delete()
                    else:
                        # Fall back to regular delete as last resort
                        page.delete()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Page.DoesNotExist:
            return Response(
                {"error": f"Page with ID {pk} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the error for debugging
            print(f"Error deleting page {pk}: {str(e)}")
            return Response(
                {"error": f"Failed to delete page: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['put'], url_path='full-update')
    def full_update(self, request, pk=None):
        """Update page, layout, and components in one call"""
        page = self.get_object()
        data = request.data
        # serializer = self.get_serializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            # Update page data if provided
            if 'page' in data:
                page_data = data['page']
                
                # Check if slug is being changed and if it already exists
                if 'slug' in page_data and page_data['slug'] != page.slug:
                    existing_page = Page.objects.filter(slug=page_data['slug']).exclude(pk=page.pk).first()
                    if existing_page:
                        return Response(
                            {"error": f"A page with slug '{page_data['slug']}' already exists."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                page_serializer = PageCreateUpdateSerializer(page, data=page_data)
                page_serializer.is_valid(raise_exception=True)
                page = page_serializer.save()
            
            # Update layout if provided
            if 'layout' in data:
                layout_data = data['layout']
                try:
                    layout = page.layout
                    layout_serializer = PageLayoutUpdateSerializer(layout, data=layout_data)
                except PageLayout.DoesNotExist:
                    # Create new layout if it doesn't exist
                    layout_serializer = PageLayoutUpdateSerializer(data=layout_data)
                
                layout_serializer.is_valid(raise_exception=True)
                if hasattr(page, 'layout'):
                    layout_serializer.save()
                else:
                    layout_serializer.save(page=page)
            
            # Update components if provided
            if 'components' in data:
                components_data = data['components']
                for component_data in components_data:
                    component_id = component_data.pop('id', None)
                    
                    if component_id:  # Update existing component
                        try:
                            component = ComponentInstance.objects.get(id=component_id, page=page)
                            for key, value in component_data.items():
                                setattr(component, key, value)
                            component.save()
                        except ComponentInstance.DoesNotExist:
                            pass
                    else:  # Create new component
                        if 'component_type' in component_data and 'instance_id' in component_data:
                            # Get the actual ComponentType object instead of just using the ID
                            component_type_id = component_data.pop('component_type')
                            try:
                                component_type = ComponentType.objects.get(id=component_type_id)
                                
                                ComponentInstance.objects.create(
                                    page=page,
                                    component_type=component_type,
                                    company=page.company if hasattr(page, 'company') else None,
                                    is_deleted=False,
                                    **component_data
                                )
                            except ComponentType.DoesNotExist:
                                # Skip this component if component_type doesn't exist
                                continue
            
            # Remove components if provided
            if 'removed_components' in data:
                component_ids = data['removed_components']
                ComponentInstance.objects.filter(
                    id__in=component_ids,
                    page=page
                ).update(is_deleted=True, deleted_at=timezone.now())
        
        # Return the updated page with all its data
        return Response(PageSerializer(page).data)


@method_decorator(csrf_exempt, name='dispatch')
class ComponentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for component types - read-only"""
    serializer_class = ComponentTypeSerializer
    authentication_classes = [ApiKeyAuthentication]
    
    def get_queryset(self):
        return ComponentType.objects.all()


@method_decorator(csrf_exempt, name='dispatch')
class PageComponentsViewSet(mixins.CreateModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin,
                            mixins.DestroyModelMixin,
                            mixins.ListModelMixin,
                            GenericViewSet):
    """API endpoint for components within a page (nested resource)"""
    authentication_classes = [ApiKeyAuthentication]
    
    def get_queryset(self):
        # Only return non-deleted components for the specific page
        page_id = self.kwargs.get('page_pk')
        if not page_id:
            return ComponentInstance.objects.none()
        return ComponentInstance.objects.filter(page_id=page_id, is_deleted=False)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ComponentInstanceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ComponentInstanceUpdateSerializer
        elif self.action == 'bulk':
            return ComponentBulkUpdateSerializer
        return ComponentInstanceSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['page_id'] = self.kwargs.get('page_pk')
        return context
    
    def perform_destroy(self, instance):
        # Soft delete instead of hard delete
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()
    
    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request, page_pk=None):
        """Bulk create/update components for a page"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get the page
        page_id = self.kwargs.get('page_pk')
        try:
            page = Page.objects.get(id=page_id)
        except Page.DoesNotExist:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
            
        components_data = serializer.validated_data.get('components', [])
        updated_components = []
        
        with transaction.atomic():
            for component_data in components_data:
                component_id = component_data.pop('id', None)
                
                if component_id:  # Update existing component
                    try:
                        component = ComponentInstance.objects.get(id=component_id, page=page)
                        for key, value in component_data.items():
                            setattr(component, key, value)
                        component.save()
                        updated_components.append(component)
                    except ComponentInstance.DoesNotExist:
                        continue
                else:  # Create new component
                    if 'component_type' in component_data and 'instance_id' in component_data:
                        # Get the actual ComponentType object instead of just using the ID
                        component_type_id = component_data.pop('component_type')
                        try:
                            component_type = ComponentType.objects.get(id=component_type_id)
                            
                            component = ComponentInstance.objects.create(
                                page=page,
                                component_type=component_type,
                                company=page.company if hasattr(page, 'company') else None,
                                is_deleted=False,
                                **component_data
                            )
                            updated_components.append(component)
                        except ComponentType.DoesNotExist:
                            # Skip this component if component_type doesn't exist
                            continue
        
        result_serializer = ComponentInstanceSerializer(updated_components, many=True)
        return Response(result_serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class PageLayoutViewSet(mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin,
                        GenericViewSet):
    """API endpoint for page layout (nested resource)"""
    authentication_classes = [ApiKeyAuthentication]
    serializer_class = PageLayoutSerializer
    
    def get_queryset(self):
        page_id = self.kwargs.get('page_pk')
        if not page_id:
            return PageLayout.objects.none()
        return PageLayout.objects.filter(page_id=page_id)
    
    def get_object(self):
        # Get the page layout or create one if it doesn't exist
        page_id = self.kwargs.get('page_pk')
        try:
            page = Page.objects.get(id=page_id)
            try:
                return page.layout
            except PageLayout.DoesNotExist:
                return PageLayout.objects.create(page=page, layout_config={})
        except Page.DoesNotExist:
            self.permission_denied(self.request)
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return PageLayoutUpdateSerializer
        return PageLayoutSerializer


@method_decorator(csrf_exempt, name='dispatch')
class DataSourceViewSet(viewsets.ModelViewSet):
    """API endpoint for data sources"""
    serializer_class = DataSourceSerializer
    authentication_classes = [ApiKeyAuthentication]
    
    def get_queryset(self):
        return DataSource.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@method_decorator(csrf_exempt, name='dispatch')
class AnalyticsViewSet(viewsets.ViewSet):
    """API endpoint for session analytics"""
    authentication_classes = [ApiKeyAuthentication]
    
    def list(self, request):
        """
        Default endpoint that returns available analytics endpoints
        """
        return Response({
            "available_endpoints": [
                "/api/v1/insights/api/session-analytics/daily_sessions/",
                "/api/v1/insights/api/session-analytics/request_medium_distribution/",
                "/api/v1/insights/api/session-analytics/company_session_comparison/",
                "/api/v1/insights/api/session-analytics/api_controller_usage/",
                "/api/v1/insights/api/session-analytics/total_api_controllers/",
                "/api/v1/insights/api/session-analytics/total_sessions/",
                "/api/v1/insights/api/session-analytics/unique_users/",
                "/api/v1/insights/api/session-analytics/network_graph/",
                "/api/v1/insights/api/session-analytics/neo4j_network_graph/"
            ],
            "message": "Please use one of the available endpoints for specific analytics data"
        })
    
    @action(detail=False, methods=['get'])
    def daily_sessions(self, request):
        """
        Get the count of sessions created daily for a specified number of days
        
        Query Parameters:
        - days: Number of days to fetch data for (default: 30)
        """
        # Get the number of days from query parameters (default to 30 if not provided)
        days = int(request.query_params.get('days', 7))
        
        # Calculate date range based on the requested number of days
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Query to get daily session counts
        daily_sessions = (
            ConversationSession.without_company_objects
            .filter(created_at__gte=start_date, created_at__lte=end_date)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # Format the response
        formatted_data = []
        for session in daily_sessions:
            formatted_data.append({
                'date': session['date'].strftime('%d %b, %Y'),
                'sessions': session['count']
            })
        
        return Response({'data': formatted_data})
    
    @action(detail=False, methods=['get'])
    def request_medium_distribution(self, request):
        """
        Get the distribution of request mediums used in conversations
        
        Query Parameters:
        - days: Number of days to fetch data for (default: 30)
        - company_id: Optional filter by company ID
        """
        # Get parameters
        days = int(request.query_params.get('days', 30))
        company_id = request.query_params.get('company_id')
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base query filters
        filters = {
            'created_at__gte': start_date,
            'created_at__lte': end_date
        }
        
        if company_id:
            filters['company_id'] = company_id
            
        # Query to get request medium distribution
        from chat.models import ConversationSession, RequestMedium
        
        # Get distribution data
        distribution = (
            ConversationSession.without_company_objects
            .filter(**filters)
            .values('request_medium')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Format the response
        formatted_data = []
        total_count = sum(item['count'] for item in distribution)
        
        # Map request medium codes to readable names
        medium_names = dict(RequestMedium.REQUEST_MEDIUM_CHOICES)
        
        for item in distribution:
            medium = item['request_medium']
            count = item['count']
            percentage = (count / total_count * 100) if total_count > 0 else 0
            
            formatted_data.append({
                'name': medium_names.get(medium, medium),
                'value': count,
                'percentage': round(percentage, 2)
            })
            
        return Response({
            'data': formatted_data,
            'total': total_count
        })
    
    @action(detail=False, methods=['get'])
    def company_session_comparison(self, request):
        """
        Get company-wise session usage comparison
        
        Query Parameters:
        - days: Number of days to fetch data for (default: 30)
        - limit: Maximum number of companies to include (default: 10)
        """
        # Get parameters
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Query to get company-wise session counts
        from chat.models import ConversationSession
        from company.models import Company
        
        company_usage = (
            ConversationSession.without_company_objects
            .filter(created_at__gte=start_date, created_at__lte=end_date)
            .values('company_id')
            .annotate(session_count=Count('id'))
            .order_by('-session_count')
            [:limit]
        )
        
        # Get company names
        company_ids = [item['company_id'] for item in company_usage]
        companies = {
            company.id: company.name
            for company in Company.objects.filter(id__in=company_ids)
        }
        
        # Format the response
        formatted_data = []
        for item in company_usage:
            company_id = item['company_id']
            company_name = companies.get(company_id, f"Company {company_id}")
            
            formatted_data.append({
                'company': company_name,
                'sessions': item['session_count']
            })
        
        return Response({'data': formatted_data})
    
    @action(detail=False, methods=['get'])
    def api_controller_usage(self, request):
        """
        Get count of each API controller used in conversations, company-wise
        
        Query Parameters:
        - days: Number of days to fetch data for (default: 30)
        - company_id: Optional filter by company ID
        """
        # Get parameters
        days = int(request.query_params.get('days', 30))
        company_id = request.query_params.get('company_id')
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base query filters
        filters = {
            'created_at__gte': start_date,
            'created_at__lte': end_date,
            'api_controller__isnull': False
        }
        
        if company_id:
            filters['company_id'] = company_id
        
        # Query to get API controller usage
        from chat.models import ConversationSession
        from api_controller.models import ApiController
        from django.db.models import Count
        
        # Get controller usage data
        controller_usage = (
            ConversationSession.objects
            .filter(**filters)
            .values('api_controller')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Get controller names
        controller_ids = [item['api_controller'] for item in controller_usage if item['api_controller']]
        controllers = {
            controller.id: controller.name
            for controller in ApiController.objects.filter(id__in=controller_ids)
        }
        
        # Format the response
        formatted_data = []
        for item in controller_usage:
            controller_id = item['api_controller']
            if controller_id:
                controller_name = controllers.get(controller_id, f"Controller {controller_id}")
                
                formatted_data.append({
                    'name': controller_name,
                    'value': item['count']
                })
        
        return Response({'data': formatted_data})
        
    @action(detail=False, methods=['get'])
    def total_api_controllers(self, request):
        """
        Get the total number of API controllers
        
        Query Parameters:
        - active_only: Only count active controllers (default: true)
        """
        # Import required models
        from api_controller.models import ApiController
        from company.models import Company
        
        companies = Company.objects.count()
        
        total_workflows = ApiController.without_company_objects.filter().count()
        
        # Format response in the requested format
        formatted_response = {
            "heading": "Total Workflows",
            "Value": total_workflows,
            "sub-heading": f"across {companies} companies"
        }
        
        return Response(formatted_response)
    
    @action(detail=False, methods=['get'])
    def total_sessions(self, request):
        """
        Get the total number of sessions
        
        Query Parameters:
        - active_only: Only count active controllers (default: true)
        """
        # Import required models
        from chat.models import ConversationSession
        from company.models import Company
        
        companies = Company.objects.count()
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        total_sessions = ConversationSession.without_company_objects.filter(created_at__gte=start_date).count()
        
        # Format response in the requested format
        formatted_response = {
            "heading": "Total Sessions(last 30 days)",
            "Value": total_sessions,
            "sub-heading": f"across {companies} companies"
        }
        
        return Response(formatted_response)
    
    @action(detail=False, methods=['get'])
    def unique_users(self, request):
        """
        Get the total number of unique users (client identifiers) in the last 30 days
        
        Query Parameters:
        - days: Number of days to fetch data for (default: 30)
        """
        # Import required models
        from chat.models import ConversationSession
        from company.models import Company
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        # Get query parameters
        days = int(request.query_params.get('days', 30))
        
        # Get total companies
        companies = Company.objects.count()
        
        # Calculate date range for current period
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Count unique client identifiers in the current period
        # Exclude null client identifiers
        current_unique_users = ConversationSession.without_company_objects.filter(
            created_at__gte=start_date,
            client_identifier__isnull=False
        ).values('client_identifier').distinct().count()
        
        # Calculate date range for previous period (same duration)
        prev_end_date = start_date
        prev_start_date = prev_end_date - timedelta(days=days)
        
        # Count unique client identifiers in the previous period
        prev_unique_users = ConversationSession.without_company_objects.filter(
            created_at__gte=prev_start_date,
            created_at__lt=prev_end_date,
            client_identifier__isnull=False
        ).values('client_identifier').distinct().count()
        
        # Calculate growth percentage
        if prev_unique_users > 0:
            growth_percentage = ((current_unique_users - prev_unique_users) / prev_unique_users) * 100
            growth_text = f"{abs(growth_percentage):.1f}% {'growth' if growth_percentage >= 0 else 'decline'} from previous {days} days"
        else:
            growth_text = "no data from previous period for comparison"
        
        # Format response in the requested format
        formatted_response = {
            "heading": f"Unique Users (last {days} days)",
            "Value": current_unique_users,
            "sub-heading": f"{growth_text}"
        }
        
        return Response(formatted_response)
   
    @action(detail=False, methods=['post'])
    def neo4j_network_graph(self, request):
        """
        Generate a Neo4j Cypher query based on a user's question and return the results
        in a format suitable for network graph visualization.
        
        Request body should contain:
        - query: The user's natural language question
        - company_id: (Optional) The company ID for context
        
        The endpoint will:
        1. Generate a Cypher query from the user's question
        2. Execute the query against Neo4j
        3. Return the results formatted for network graph visualization
        """
        from chat.retriever.neo4j_graph_data_retriever import Neo4jGraphDataRetriever
        from company.models import Company
        from rest_framework.response import Response
        from rest_framework import status
        import traceback
        
        # Get request data
        user_question = request.data.get('query')
        component_id = request.data.get('component_id')
        
        if not user_question:
            return Response(
                {"error": "No question provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            credentials_dict = None
            print("component_id", component_id)
            if component_id:
                try:
                    from insights.models import ComponentInstance
                    component = ComponentInstance.objects.get(id=component_id)
                    print("component", component.company)
                    if component.data_source_creds:
                        credentials_dict = component.data_source_creds
                except ComponentInstance.DoesNotExist:
                    return Response(
                        {"error": f"Component with ID {component_id} not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                    
            # Initialize the Neo4j Graph Data Retriever
            retriever = Neo4jGraphDataRetriever(credentials=credentials_dict, company=component.company)
            
            # Process the question and get the graph data
            result = retriever.query(user_question)
            
            # Close the Neo4j connection
            retriever.close()
            
            # Return the result
            return Response(result)
            
        except Exception as e:
            error_trace = traceback.format_exc()
            return Response(
                {
                    "error": str(e),
                    "trace": error_trace
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )