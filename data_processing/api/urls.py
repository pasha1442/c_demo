from django.urls import path
from .views import DataEnrichmentManager
from .views_ingestion import DataIngestionManager

urlpatterns = [
    # Data Enrichment API endpoints
    path('data-enrichment/get-partitioned-files-list/', DataEnrichmentManager.as_view(), name='get_partitioned_files_list'),
    path('data-enrichment/update-partition-status/', DataEnrichmentManager.as_view(), name='update_partition_status'),
    
    # Data Ingestion API endpoints
    path('data-ingestion/get-partitioned-files-list/', DataIngestionManager.as_view(), name='get_ingestion_partitioned_files_list'),
    path('data-ingestion/update-partition-status/', DataIngestionManager.as_view(), name='update_ingestion_partition_status'),
]
