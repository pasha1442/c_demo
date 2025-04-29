from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Main router
router = DefaultRouter()
router.register(r'pages', views.PageViewSet, basename='pages')
router.register(r'component-types', views.ComponentTypeViewSet, basename='component-types')
router.register(r'data-sources', views.DataSourceViewSet, basename='data-sources')
router.register(r'page-components', views.PageComponentsViewSet, basename='page-components')
router.register(r'page-layouts', views.PageLayoutViewSet, basename='page-layouts')
router.register(r'session-analytics', views.AnalyticsViewSet, basename='session-analytics')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Custom nested URLs (without using nested routers)
    path('api/pages/<int:page_pk>/components/', views.PageComponentsViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('api/pages/<int:page_pk>/components/<int:pk>/', views.PageComponentsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})),
    path('api/pages/<int:page_pk>/components/bulk/', views.PageComponentsViewSet.as_view({'post': 'bulk'})),
    
    path('api/pages/<int:page_pk>/layout/', views.PageLayoutViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update'})),
]
