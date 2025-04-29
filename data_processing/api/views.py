from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from company.utils import CompanyUtils
from django.utils import timezone
from ..models import DataEnrichment, DataEnrichmentPartition


class DataEnrichmentPartitionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DataEnrichmentManager(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = DataEnrichmentPartitionPagination

    def get(self, request):
        """
        Get paginated list of partitioned files for a data enrichment request.
        
        Query Parameters:
        - enrichment_id (required): ID of the data enrichment request
        - status (optional): Filter by partition status
        - page (optional): Page number for pagination
        - page_size (optional): Number of items per page
        """
        try:
            # Get enrichment ID from query params
            enrichment_id = request.query_params.get('enrichment_id')
            if not enrichment_id:
                return Response(
                    {"error": "enrichment_id is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get enrichment request
            enrichment = get_object_or_404(DataEnrichment, id=enrichment_id)
            
            # Set company context
            CompanyUtils.set_company_registry(enrichment.company)

            # Get status filter
            status_filter = request.query_params.get('status', '').lower()

            # Query partitions
            partitions = DataEnrichmentPartition.objects.filter(
                request=enrichment
            ).order_by('-created_at')

            # Apply status filter if provided
            if status_filter:
                partitions = partitions.filter(status__iexact=status_filter)

            # Get pagination parameters with validation
            try:
                page = int(request.query_params.get('page', 1))
                page_size = min(
                    int(request.query_params.get('page_size', 10)),
                    self.pagination_class.max_page_size
                )
            except ValueError:
                return Response(
                    {"error": "Invalid pagination parameters"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create paginator
            paginator = Paginator(partitions, page_size)
            
            try:
                current_page = paginator.page(page)
            except EmptyPage:
                # If page is out of range, deliver last page
                current_page = paginator.page(paginator.num_pages)
                page = paginator.num_pages

            # Prepare response data
            partition_data = []
            for partition in current_page:
                partition_data.append({
                    'id': partition.id,
                    'status': partition.status,
                    'input_file_path': partition.input_file_path,
                    'output_file_path': partition.output_file_path,
                    'created_at': partition.created_at.isoformat() if partition.created_at else None,
                    'processed_at': partition.processed_at.isoformat() if partition.processed_at else None,
                    'error_message': partition.error_message,
                    'metadata': partition.metadata,
                    'input_file_url': partition.get_input_file_url(),
                    'output_file_url': partition.get_output_file_url() if partition.output_file_path else None,
                })

            # Prepare pagination metadata
            response_data = {
                'results': partition_data,
                'pagination': {
                    'current_page': page,
                    'num_pages': paginator.num_pages,
                    'has_next': current_page.has_next(),
                    'has_previous': current_page.has_previous(),
                    'total_items': paginator.count,
                    'page_size': page_size
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """
        Get paginated list of partitioned files for a data enrichment request.
        
        Request Body:
        - enrichment_id (required): ID of the data enrichment request
        - status (optional): Filter by partition status
        - page (optional): Page number for pagination
        - page_size (optional): Number of items per page
        """
        try:
            # Get enrichment ID from request data
            enrichment_id = request.data.get('enrichment_id')
            if not enrichment_id:
                return Response(
                    {"error": "enrichment_id is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get enrichment request
            enrichment = get_object_or_404(DataEnrichment, id=enrichment_id)
            
            # Set company context
            CompanyUtils.set_company_registry(enrichment.company)

            # Get status filter
            status_filter = request.data.get('status', '').lower()

            # Get partitions query
            partitions = DataEnrichmentPartition.objects.filter(request=enrichment).order_by('-id')
            
            # Apply status filter if provided
            if status_filter:
                partitions = partitions.filter(status=status_filter)

            # Get pagination parameters
            page = request.data.get('page', 1)
            page_size = request.data.get('page_size', 10)

            # Paginate results
            paginator = Paginator(partitions, page_size)
            try:
                current_page = paginator.page(page)
            except EmptyPage:
                current_page = paginator.page(paginator.num_pages)

            # Prepare response data
            results = []
            for partition in current_page:
                results.append({
                    'id': partition.id,
                    'input_file': partition.input_file_path,
                    'output_file': partition.output_file_path,
                    'status': partition.status,
                    'processed_at': partition.processed_at.isoformat() if partition.processed_at else None,
                    'error_message': partition.error_message
                })

            return Response({
                'results': results,
                'total_count': paginator.count,
                'num_pages': paginator.num_pages,
                'current_page': current_page.number
            })

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request):
        """
        Update status of a data enrichment partition.
        
        Request Body:
        - partition_id (required): ID of the partition to update
        - status (required): New status value (pending, processing, done, error)
        """
        try:
            # Get partition ID and new status from request data
            partition_id = request.data.get('partition_id')
            new_status = request.data.get('status', '').lower()

            if not partition_id or not new_status:
                return Response(
                    {"error": "partition_id and status are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate status value
            valid_statuses = ['pending', 'processing', 'done', 'error']
            if new_status not in valid_statuses:
                return Response(
                    {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get partition
            partition = get_object_or_404(DataEnrichmentPartition, id=partition_id)
            
            # Set company context
            CompanyUtils.set_company_registry(partition.request.company)

            # Update status and processed_at if status is 'done'
            partition.status = new_status
            if new_status == 'done':
                partition.processed_at = timezone.now()
            elif new_status == 'error':
                # Clear processed_at if status is error
                partition.processed_at = None
            elif new_status == 'pending':
                # Clear processed_at and error message if status is pending
                partition.processed_at = None
                partition.error_message = ''
            partition.save()

            return Response({
                'id': partition.id,
                'status': partition.status,
                'processed_at': partition.processed_at.isoformat() if partition.processed_at else None,
                'error_message': partition.error_message,
                'message': 'Status updated successfully'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
