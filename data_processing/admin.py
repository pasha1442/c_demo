from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import DataEnrichment, DataEnrichmentPartition, DataIngestion, DataIngestionPartition, DataEmbedding
from .forms import DataEmbeddingForm
from basics.admin import BaseModelAdmin
from django.utils import timezone
from .forms import DataEnrichmentForm, DataIngestionForm
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
import math
from django.http import JsonResponse
from neo4j import GraphDatabase
from company.models import CompanySetting


class SaveInlineModelAdmin(admin.TabularInline):
    """Base class for inlines with save buttons"""
    template = 'admin/edit_inline/tabular_with_save.html'
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.request = request  # Store request for use in save_inline
        return formset


class DataEnrichmentPartitionInline(SaveInlineModelAdmin):
    model = DataEnrichmentPartition
    extra = 0
    readonly_fields = ('partition_id', 'input_file_link', 'created_at', 'processed_at', 'error_message')
    fields = ('partition_id', 'status', 'input_file_link', 'processed_at', 'error_message', 'created_at')
    can_delete = True
    max_num = 0
    template = 'admin/data_processing/dataenrichment/partitions_inline.html'

    def has_add_permission(self, request, obj=None):
        return False

    def partition_id(self, obj):
        return obj.id
    partition_id.short_description = 'Partition ID'

    def input_file_link(self, obj):
        """Display input file link"""
        if obj.input_file_path:
            url = obj.get_input_file_url()
            file_name = obj.input_file_path.split('/')[-1]
            button_style = """
                background-color: #5bc0de;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
                url, button_style, file_name
            )
        return "-"
    input_file_link.short_description = 'Input File'
    input_file_link.allow_tags = True

    class Media:
        js = ('data_processing/js/admin/data_enrichment.js',)

    def save_inline(self, obj):
        """Display save button for individual inline"""
        if obj and obj.pk:
            button_style = """
                background-color: #5cb85c;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
                border: none;
                cursor: pointer;
            """
            return format_html(
                '<button type="submit" name="_save_inline" value="{}" style="{}" onclick="return confirm(\'Save this partition?\')"> Save</button>',
                obj.pk,
                button_style
            )
        return ""
    save_inline.short_description = ''
    save_inline.allow_tags = True

    def output_file_link(self, obj):
        """Display output file link"""
        if obj.output_file_path:
            url = obj.get_output_file_url()
            file_name = obj.output_file_path.split('/')[-1]
            button_style = """
                background-color: #5cb85c;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View Output</a><br><small>{}</small>',
                url, button_style, file_name
            )
        return "-"
    output_file_link.short_description = 'Output File'
    output_file_link.allow_tags = True


@admin.register(DataEnrichment)
class DataEnrichmentAdmin(BaseModelAdmin):
    form = DataEnrichmentForm
    inlines = [DataEnrichmentPartitionInline]
    list_display = ('id', 'session_id', 'name', 'prompt', 'llm_model', 'status',
                    'status_with_progress', 'partition_status', 'input_file_size', 'get_input_file', 'get_output_file',
                    'execution_time_display', 'created_at', 'is_active', 'reset_button')
    list_display_links = ('id', 'session_id', 'name', 'prompt', 'created_at')
    list_filter = ('status', 'llm_model', 'is_active')
    search_fields = ('prompt', 'id', 'name')
    readonly_fields = ('file_size', 'completion_percentage', 'execution_start_at', 
                       'execution_end_at', 'execution_time_display', 
                       'partition_status', # 'status_metadata', 
                       'file_status_table', 'session_id', 'reset_button')
    list_per_page = 20
    list_editable = ('status','llm_model')
    fieldsets = (
            ('Basic Information', {
                'fields': ('session_id', 'status', 'name', 'input_file', 'output_file', 'prompt',
                'llm_model', 'batch_size', 'file_size', 
                'completion_percentage',
                'combine_output_files', 
                'parallel_threading_count', 'metadata', 'status_metadata', 'processing_error', 'reset_button')
            }),
            ('File Status', {
                'fields': ('file_status_table',),
            }),
            ('Execution Details', {
                'fields': ('execution_start_at', 'execution_end_at', 'execution_time_display', 'partition_status'),
                'classes': ('collapse',)
            }),
        )

    class Media:
        css = {
            'all': ('data_processing/css/admin/custom.css',)
        }
        js = ('data_processing/js/admin/data_enrichment.js',)

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        urls = [
            path(
                '<path:object_id>/reset/',
                self.admin_site.admin_view(self.reset_view),
                name='%s_%s_reset' % info
            ),
            path(
                '<path:object_id>/save_partition/<path:partition_id>/',
                self.admin_site.admin_view(self.save_partition_view),
                name='%s_%s_save_partition' % info
            ),
        ]
        return urls + super().get_urls()

    def save_partition_view(self, request, object_id, partition_id):
        """Handle saving individual partition"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=405)
            
        try:
            # Get the partition being saved
            partition = DataEnrichmentPartition.objects.get(
                pk=partition_id,
                enrichment_id=object_id
            )
            
            # Update partition fields from form data
            prefix = f'dataenrichmentpartition_set-{partition_id}'
            form_data = {}
            for key, value in request.POST.items():
                if key.startswith(prefix):
                    field = key.replace(f'{prefix}-', '')
                    if hasattr(partition, field):
                        form_data[field] = value
            
            # Update partition fields
            for field, value in form_data.items():
                setattr(partition, field, value)
            
            # Save only the partition
            partition.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully saved partition {partition.id}'
            })
            
        except DataEnrichmentPartition.DoesNotExist:
            return JsonResponse({
                'error': f'Partition {partition_id} not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'error': f'Error saving partition: {str(e)}'
            }, status=500)

    def save_model(self, request, obj, form, change):
        if obj.input_file:
            try:
                file_size_bytes = obj.input_file.size
                if file_size_bytes < 1024 * 1024:  # Less than 1MB
                    # Store KB value with one decimal
                    obj.file_size = round(file_size_bytes / 1024, 1)
                else:
                    # Store MB value rounded up
                    obj.file_size = math.ceil(file_size_bytes / (1024 * 1024))
            except Exception as e:
                print("Exception", str(e))
                obj.file_size = 0
        super().save_model(request, obj, form, change)

    def reset_button(self, obj):
        """Display reset button in admin"""
        if not obj or not obj.pk:  # Check if object exists
            return ""

        non_resettable_states = [
            # DataEnrichment.STATUS_PARTITION_CREATED,  # Already in initial state
            # DataEnrichment.STATUS_PENDING,  # Nothing to reset
            # DataEnrichment.STATUS_PROCESSING,  # Cannot reset while processing
        ]
        
        if obj.status not in non_resettable_states:
            button_style = """
                background-color: #d9534f;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
            """
            url = f"../../{obj.pk}/reset/"
            return format_html(
                '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this request? This will:\n\n1. Reset all partitions to pending state\n2. Clear execution timestamps\n3. Reset completion percentage to 0\n4. Preserve original data and partition structure\n\nProceed?\')">Reset Request</a>',
                button_style,
                url
            )
        elif obj.status == DataEnrichment.STATUS_PROCESSING:
            button_style = """
                background-color: #777;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
                cursor: not-allowed;
                opacity: 0.65;
            """
            return format_html(
                '<span style="{}" title="Cannot reset while request is being processed - {} partitions are currently being processed in parallel">Reset Request</span>',
                button_style,
                5  # From memory: PARALLEL_EXECUTION_COUNT
            )
        return ""
    reset_button.short_description = 'Reset'
    reset_button.allow_tags = True

    def reset_view(self, request, object_id):
        """Handle reset action"""
        try:
            obj = self.get_object(request, object_id)
            if not obj:
                self.message_user(request, "Request not found.", messages.ERROR)
                return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

            if obj.status == DataEnrichment.STATUS_PROCESSING:
                self.message_user(
                    request, 
                    f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.",
                    messages.WARNING
                )
            else:
                summary = obj.reset_partition_stats()
                self.message_user(
                    request, 
                    f"Request has been reset successfully. All {summary['total']} partitions are now in pending state and ready for parallel processing.",
                    messages.SUCCESS
                )
        except ValueError as e:
            self.message_user(request, str(e), messages.WARNING)
        except Exception as e:
            self.message_user(request, f"Error resetting request: {str(e)}", messages.ERROR)
        
        change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
        return redirect(change_url)

    def get_form(self, request, obj=None, **kwargs):
        """
        Override get_form to inject company and request context into form
        """
        form = super().get_form(request, obj, **kwargs)

        # Set request as a class attribute for access in __init__
        form.request = request
        return form

    def status_with_progress(self, obj):
        """Display status with progress percentage if processing"""
        status_display = obj.get_status_display_with_percentage()
        status_colors = {
            DataEnrichment.STATUS_PENDING: '#f0ad4e',     # Orange
            DataEnrichment.STATUS_PROCESSING: '#5bc0de',  # Blue
            DataEnrichment.STATUS_DONE: '#5cb85c',       # Green
            DataEnrichment.STATUS_ERROR: '#d9534f'       # Red
        }
        color = status_colors.get(obj.status, 'inherit')
        return format_html('<span style="color: {};">{}</span>', color, status_display)
    status_with_progress.short_description = 'Status'

    def partition_status(self, obj):
        """Display partition processing status"""
        summary = obj.get_partition_status_summary()
        if obj.status == DataEnrichment.STATUS_ERROR:
            return format_html('<span style="color: #d9534f;">{}</span>', summary)
        return summary
    partition_status.short_description = 'Partitions'

    def execution_time_display(self, obj):
        """Display execution time in human-readable format"""
        return obj.get_execution_time_display()
    execution_time_display.short_description = 'Execution Time'

    def file_status_table(self, obj):
        """Display file status table with processing details"""
        if not obj.status_metadata:
            return "No file status information available"

        # Define table styles
        table_style = """
            <style>
                .file-status-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }
                .file-status-table th, .file-status-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                .file-status-table th {
                    background-color: #f5f5f5;
                }
                .file-status-table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                .status-icon {
                    font-size: 18px;
                }
                .status-success {
                    color: #5cb85c;
                }
                .status-error {
                    color: #d9534f;
                }
            </style>
        """

        # Create table header
        table_html = f"""
            {table_style}
            <table class="file-status-table">
                <tr>
                    <th>S.No</th>
                    <th>Input File</th>
                    <th>Output File</th>
                    <th>Status</th>
                    <th>Processed At</th>
                    <th>Error</th>
                </tr>
        """

        # Add rows for each partition
        for idx, partition in enumerate(obj.status_metadata, 1):
            is_processed = partition.get("is_processed", False)
            error = partition.get("error", "")
            processed_at = partition.get("processed_at", "")
            
            # Create status icon
            if is_processed and not error:
                status_icon = '<span class="status-icon status-success">✓</span>'
            else:
                status_icon = '<span class="status-icon status-error">✗</span>'

            # Format processed_at
            if processed_at:
                # Assuming ISO format string, convert to more readable format
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
                    processed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

            table_html += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{partition.get("input_file_name", "")}</td>
                    <td>{partition.get("output_file_name", "")}</td>
                    <td>{status_icon}</td>
                    <td>{processed_at}</td>
                    <td style="color: #d9534f;">{error}</td>
                </tr>
            """

        table_html += "</table>"
        return mark_safe(table_html)
    file_status_table.short_description = 'File Status'

    def get_input_file(self, obj):
        """Display input file link"""
        if obj.input_file:
            url = obj.get_input_file_url()
            file_name = obj.input_file.name.split('/')[-1]
            button_style = """
                background-color: #5bc0de;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
                url, button_style, file_name
            )
        return "-"
    get_input_file.short_description = 'Input File'
    get_input_file.allow_tags = True

    def get_output_file(self, obj):
        """Display output file link"""
        if obj.output_file:
            url = obj.get_output_file_url()
            file_name = obj.output_file.name.split('/')[-1]
            button_style = """
                background-color: #5cb85c;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View Output</a><br><small>{}</small>',
                url, button_style, file_name
            )
        return "-"
    get_output_file.short_description = 'Output File'
    get_output_file.allow_tags = True

    def get_completion_percentage(self, obj):
        return f"{obj.completion_percentage}%"
    get_completion_percentage.short_description = '%'

    def get_execution_time(self, obj):
        """Display execution time as end - start"""
        if obj.execution_start_at and obj.execution_end_at:
            duration = obj.execution_end_at - obj.execution_start_at
            # Convert to hours, minutes, seconds
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            seconds = duration.seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"
    get_execution_time.short_description = "Execution Time"


class DataIngestionPartitionInline(SaveInlineModelAdmin):
    model = DataIngestionPartition
    extra = 0
    readonly_fields = ('partition_id', 'input_file_link', 'created_at', 'processed_at', 'error_message')
    fields = ('partition_id', 'status', 'input_file_link', 'processed_at', 'error_message', 'created_at')
    can_delete = True
    max_num = 0
    template = 'admin/data_processing/dataingestion/partitions_inline.html'

    def has_add_permission(self, request, obj=None):
        return False

    def partition_id(self, obj):
        return obj.id
    partition_id.short_description = 'Partition ID'

    def input_file_link(self, obj):
        """Display input file link"""
        if obj.input_file_path:
            url = obj.get_input_file_url()
            file_name = obj.input_file_path.split('/')[-1]
            button_style = """
                background-color: #5bc0de;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
                url, button_style, file_name
            )
        return "-"
    input_file_link.short_description = 'Input File'
    input_file_link.allow_tags = True
    
    class Media:
        js = ('data_processing/js/admin/data_ingestion.js',)

    def save_inline(self, obj):
        """Display save button for individual inline"""
        if obj and obj.pk:
            button_style = """
                background-color: #5cb85c;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
                border: none;
                cursor: pointer;
            """
            return format_html(
                '<button type="submit" name="_save_inline" value="{}" style="{}" onclick="return confirm(\'Save this partition?\');"> Save</button>',
                obj.pk,
                button_style
            )
        return ""
    save_inline.short_description = ''
    save_inline.allow_tags = True

@admin.register(DataIngestion)
class DataIngestionAdmin(BaseModelAdmin):
    form = DataIngestionForm
    inlines = [DataIngestionPartitionInline]
    list_display = ('id', 'session_id', 'name', 'status', 'execution_type', 'destination', 
                   'status_with_progress', 'partition_status', 'get_file', 
                   'execution_time_display', 'created_at', 'is_active', 'reset_button')
    list_display_links = ('id', 'session_id', 'name', 'created_at')
    list_filter = ('status', 'execution_type', 'destination', 'is_active')
    search_fields = ('name', 'id')
    readonly_fields = ('execution_time_display', 'partition_status', 'status_with_progress',
                      'completion_percentage', 'execution_start_at', 'execution_end_at', 'session_id', 
                      'reset_button')
    list_per_page = 20
    list_editable = ('status',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('session_id', 'status', 'name', 'file', 'execution_type', 'workflow', 'prompt_name',
            'schema_type', 'prompt_defined_schema', 'prompt_create_schema', 'destination',
            'chunking_status', 'chunk_size', 'chunk_overlap', 'completion_percentage', 'status_metadata', 'processing_error', 'reset_button')
        }),
        ('Execution Details', {
            'fields': ('execution_start_at', 'execution_end_at', 'execution_time_display', 'partition_status'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        js = ('data_processing/static/data_processing/js/admin/data_ingestion.js',)

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        urls = [
            path(
                '<path:object_id>/reset/',
                self.admin_site.admin_view(self.reset_view),
                name='%s_%s_reset' % info
            ),
        ]
        return urls + super().get_urls()

    def reset_button(self, obj):
        """Display reset button in admin"""
        if not obj or not obj.pk:  # Check if object exists
            return ""

        non_resettable_states = [
            # DataIngestion.STATUS_PROCESSING,  # Cannot reset while processing
        ]

        if obj.status not in non_resettable_states:
            button_style = """
                background-color: #d9534f;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
            """
            url = f"../../{obj.pk}/reset/"
            return format_html(
                '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this request? This will:\n\n1. Reset all partitions to pending state\n2. Clear execution timestamps\n3. Reset completion percentage to 0\n4. Preserve original data and partition structure\n\nProceed?\')">Reset Request</a>',
                button_style,
                url
            )
        elif obj.status == DataIngestion.STATUS_PROCESSING:
            button_style = """
                background-color: #777;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
                cursor: not-allowed;
                opacity: 0.65;
            """
            return format_html(
                '<span style="{}" title="Cannot reset while request is being processed - {} partitions are currently being processed in parallel">Reset Request</span>',
                button_style,
                5  # From memory: PARALLEL_EXECUTION_COUNT
            )
        return ""
    reset_button.short_description = 'Reset'
    reset_button.allow_tags = True

    def reset_view(self, request, object_id):
        """Handle reset action"""
        try:
            obj = self.get_object(request, object_id)
            if not obj:
                self.message_user(request, "Request not found.", messages.ERROR)
                return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

            if obj.status == DataIngestion.STATUS_PROCESSING:
                self.message_user(
                    request, 
                    f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.",
                    messages.WARNING
                )
            else:
                summary = obj.reset_partition_stats()
                self.message_user(
                    request, 
                    f"Request has been reset successfully. All {summary['total']} partitions are now in pending state and ready for parallel processing.",
                    messages.SUCCESS
                )
        except ValueError as e:
            self.message_user(request, str(e), messages.WARNING)
        except Exception as e:
            self.message_user(request, f"Error resetting request: {str(e)}", messages.ERROR)

        change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
        return redirect(change_url)

    def get_form(self, request, obj=None, **kwargs):
        """
        Override get_form to inject company and request context into form
        """
        form = super().get_form(request, obj, **kwargs)

        # Set request as a class attribute for access in __init__
        form.request = request
        return form

    def status_with_progress(self, obj):
        """Display status with progress percentage if processing"""
        status_display = obj.get_status_display_with_percentage()
        status_colors = {
            DataIngestion.STATUS_PENDING: '#f0ad4e',     # Orange
            DataIngestion.STATUS_PROCESSING: '#5bc0de',  # Blue
            DataIngestion.STATUS_DONE: '#5cb85c',       # Green
            DataIngestion.STATUS_ERROR: '#d9534f'       # Red
        }
        color = status_colors.get(obj.status, 'inherit')
        return format_html('<span style="color: {};">{}</span>', color, status_display)
    status_with_progress.short_description = 'Status'

    def partition_status(self, obj):
        """Display partition processing status"""
        summary = obj.get_partition_status_summary()
        if obj.status == DataIngestion.STATUS_ERROR:
            return format_html('<span style="color: #d9534f;">{}</span>', summary)
        return summary
    partition_status.short_description = 'Partitions'

    def execution_time_display(self, obj):
        """Display execution time in human-readable format"""
        return obj.get_execution_time_display()
    execution_time_display.short_description = 'Execution Time'

    def get_file(self, obj):
        """Display file link"""
        if obj.file:
            file_url = obj.file.url if hasattr(obj.file, 'url') else f"/media/{obj.file.name}"
            file_name = obj.file.name.split('/')[-1]
            button_style = """
                background-color: #5bc0de;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            """
            return format_html(
                '<a href="{}" style="{}" target="_blank">📄 View File</a><br><small>{}</small>',
                file_url, button_style, file_name
            )
        return "-"
    get_file.short_description = 'File'
    get_file.allow_tags = True

    def save_model(self, request, obj, form, change):
        # Add any pre-save logic if needed
        super().save_model(request, obj, form, change)

@admin.register(DataEmbedding)
class DataEmbeddingAdmin(BaseModelAdmin):
    form = DataEmbeddingForm
    list_display = ('id', 'session_id', 'name', 'status', 'status_with_progress', 
                   'nodes_count', 'embeddings_count', 
                   'execution_time_display', 'created_at', 'is_active', 'reset_button')
    list_display_links = ('id', 'session_id', 'name', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('name', 'id')
    readonly_fields = ('session_id', 'completion_percentage', 'nodes_processed', 
                  'embeddings_generated', 'total_processing_time', 'execution_start_at', 
                  'execution_end_at', 'execution_time_display', 'status_with_progress',
                  'reset_button', 'label_summary', 'batch_summary', 'embedding_group_summary')

    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('session_id', 'name', 'status', 'completion_percentage')
        }),
        ('Embedding Configuration', {
        'fields': ('labels', 'embedding_groups', 'batch_size', 
                  'max_label_workers', 'max_batch_workers'),
        }),
        ('Processing Statistics', {
            'fields': ('nodes_processed', 'embeddings_generated', 'total_processing_time', 
                      'execution_start_at', 'execution_end_at', 'execution_time_display'),
        }),
        ('Detailed Statistics', {
        'fields': ('label_summary', 'batch_summary', 'embedding_group_summary'),
        'classes': ('collapse',),
        }),
        ('Advanced', {
            'fields': ('status_metadata', 'processing_error', 'reset_button'),
            'classes': ('collapse',),
        }),
    )
    
    change_form_template = 'admin/data_processing/data_embedding/change_form.html'
    change_list_template = 'admin/data_processing/data_embedding/change_list.html'
    
    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        urls = [
            path(
                '<path:object_id>/reset/',
                self.admin_site.admin_view(self.reset_view),
                name='%s_%s_reset' % info
            ),
            path(
                '<path:object_id>/run/',
                self.admin_site.admin_view(self.run_view),
                name='%s_%s_run' % info
            ),
            path(
                'fetch_neo4j_labels/',
                self.admin_site.admin_view(self.fetch_neo4j_labels_view),
                name='%s_%s_fetch_labels' % info
            ),
            path(
                'fetch_label_properties/<str:label>/',
                self.admin_site.admin_view(self.fetch_label_properties_view),
                name='%s_%s_fetch_properties' % info
            ),
        ]
        return urls + super().get_urls()

    def fetch_neo4j_labels_view(self, request):
        """
        View to fetch labels from Neo4j database
        Returns JSON response with list of labels
        """
        if request.method != 'POST':
            return JsonResponse({
                'success': False,
                'error': 'Invalid request method'
            }, status=405)
            
        try:
            company = request.user.current_company
            if not company:
                return JsonResponse({
                    'success': False,
                    'error': 'No company context available'
                }, status=400)
                
            credentials = CompanySetting.without_company_objects.get(
                key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS,
                company=company
            )
            
            credentials_dict = {k: v for d in credentials.value for k, v in d.items()}
            neo4j_username = credentials_dict.get("neo4j_username")
            neo4j_password = credentials_dict.get("neo4j_password")
            neo4j_url = credentials_dict.get("neo4j_url")  
            
            if not all([neo4j_url, neo4j_username, neo4j_password]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing Neo4j credentials in company settings'
                }, status=400)
            
            driver = GraphDatabase.driver(
                neo4j_url, 
                auth=(neo4j_username, neo4j_password)
            )
            
            with driver.session() as session:
                result = session.run("CALL db.labels()")
                labels = []
                
                for record in result:
                    label_name = record["label"]
                    
                    properties_query = f"""
                    MATCH (n:`{label_name}`) 
                    WHERE n IS NOT NULL
                    RETURN keys(n) AS properties
                    LIMIT 1
                    """
                    
                    properties_result = session.run(properties_query)
                    properties = []
                    
                    for prop_record in properties_result:
                        properties = prop_record["properties"]
                    
                    labels.append({
                        'name': label_name,
                        'properties': properties
                    })
                
                driver.close()
                
                return JsonResponse({
                    'success': True,
                    'labels': labels
                })
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        
    def fetch_label_properties_view(self, request, label):
        """
        View to fetch properties for a specific label
        Returns JSON response with list of properties
        """
        if request.method != 'GET':
            return JsonResponse({
                'success': False,
                'error': 'Invalid request method'
            }, status=405)
            
        try:
            company = request.user.current_company
            if not company:
                return JsonResponse({
                    'success': False,
                    'error': 'No company context available'
                }, status=400)
                
            credentials = CompanySetting.without_company_objects.get(
                key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS,
                company=company
            )
            
            credentials_dict = {k: v for d in credentials.value for k, v in d.items()}
            neo4j_username = credentials_dict.get("neo4j_username")
            neo4j_password = credentials_dict.get("neo4j_password")
            neo4j_url = credentials_dict.get("neo4j_url")
            
            driver = GraphDatabase.driver(
                neo4j_url, 
                auth=(neo4j_username, neo4j_password)
            )
            
            with driver.session() as session:
                properties_query = f"""
                MATCH (n:`{label}`) 
                WHERE n IS NOT NULL
                RETURN keys(n) AS properties
                LIMIT 1
                """
                
                result = session.run(properties_query)
                properties = []
                
                for record in result:
                    properties = record["properties"]
                
                driver.close()
                
                return JsonResponse({
                    'success': True,
                    'label': label,
                    'properties': properties
                })
                
        except Exception as e:
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
            
    def embedding_group_summary(self, obj):
        """Display summary of embedding groups processing"""
        if not obj.status_metadata or not isinstance(obj.status_metadata, dict):
            return "No embedding group data available"
            
        summary = obj.status_metadata.get("embedding_group_stats", {})
        if not summary:
            return "No embedding group data available"
            
        table_style = """
            <style>
                .group-summary-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }
                .group-summary-table th, .group-summary-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                .group-summary-table th {
                    background-color: #f5f5f5;
                }
                .group-summary-table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
            </style>
        """
        
        table_html = f"""
            {table_style}
            <table class="group-summary-table">
                <tr>
                    <th>Label</th>
                    <th>Embedding Group</th>
                    <th>Embeddings Generated</th>
                    <th>Avg. Processing Time (s)</th>
                </tr>
        """
        
        for label, groups in summary.items():
            for group_name, stats in groups.items():
                table_html += f"""
                    <tr>
                        <td>{label}</td>
                        <td>{group_name}</td>
                        <td>{stats.get('count', 0)}</td>
                        <td>{stats.get('avg_time', 0):.2f}</td>
                    </tr>
                """
            
        table_html += "</table>"
        return mark_safe(table_html)
    embedding_group_summary.short_description = 'Embedding Groups Summary'


    def get_form(self, request, obj=None, **kwargs):
        """
        Override get_form to inject company and request context into form
        """
        form = super().get_form(request, obj, **kwargs)

        form.request = request
        return form

    def status_with_progress(self, obj):
        """Display status with progress percentage if processing"""
        status_colors = {
            DataEmbedding.STATUS_PENDING: '#f0ad4e',     
            DataEmbedding.STATUS_PROCESSING: '#5bc0de',  
            DataEmbedding.STATUS_DONE: '#5cb85c',       
            DataEmbedding.STATUS_ERROR: '#d9534f'       
        }
        color = status_colors.get(obj.status, 'inherit')
        
        if obj.status == DataEmbedding.STATUS_PROCESSING:
            status_text = f"{obj.get_status_display()} ({obj.completion_percentage}%)"
        else:
            status_text = obj.get_status_display()
            
        return format_html('<span style="color: {};">{}</span>', color, status_text)
    status_with_progress.short_description = 'Status'

    def nodes_count(self, obj):
        """Display number of processed nodes"""
        return format_html('<b>{}</b>', obj.nodes_processed)
    nodes_count.short_description = 'Nodes'

    def embeddings_count(self, obj):
        """Display number of generated embeddings"""
        return format_html('<b>{}</b>', obj.embeddings_generated)
    embeddings_count.short_description = 'Embeddings'

    def execution_time_display(self, obj):
        """Display execution time in human-readable format"""
        return obj.get_execution_time_display()
    execution_time_display.short_description = 'Execution Time'

    def reset_button(self, obj):
        """Display reset button in admin"""
        if not obj or not obj.pk:  
            return ""

        non_resettable_states = [
            DataEmbedding.STATUS_PROCESSING,  
        ]
        
        if obj.status not in non_resettable_states:
            button_style = """
                background-color: #d9534f;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
            """
            url = f"../../{obj.pk}/reset/"
            return format_html(
                '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this embedding job? This will clear all statistics and reset the status to pending.\')">Reset Job</a>',
                button_style,
                url
            )
        elif obj.status == DataEmbedding.STATUS_PROCESSING:
            button_style = """
                background-color: #777;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                text-decoration: none;
                font-weight: bold;
                display: inline-block;
                margin: 4px 0;
                cursor: not-allowed;
                opacity: 0.65;
            """
            return format_html(
                '<span style="{}" title="Cannot reset while job is being processed">Reset Job</span>',
                button_style
            )
        return ""
    reset_button.short_description = 'Reset'
    reset_button.allow_tags = True

    def label_summary(self, obj):
        """Display summary of label processing times"""
        if not obj.status_metadata or not isinstance(obj.status_metadata, dict):
            return "No label processing data available"
            
        summary = obj.status_metadata.get("average_label_processing_times", {})
        if not summary:
            return "No label processing data available"
            
        table_style = """
            <style>
                .label-summary-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }
                .label-summary-table th, .label-summary-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                .label-summary-table th {
                    background-color: #f5f5f5;
                }
                .label-summary-table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
            </style>
        """
        
        table_html = f"""
            {table_style}
            <table class="label-summary-table">
                <tr>
                    <th>Node Label</th>
                    <th>Avg. Processing Time (seconds)</th>
                </tr>
        """
        
        for label, time in summary.items():
            table_html += f"""
                <tr>
                    <td>{label}</td>
                    <td>{time:.2f}</td>
                </tr>
            """
            
        table_html += "</table>"
        return mark_safe(table_html)
    label_summary.short_description = 'Label Processing Summary'
    
    def batch_summary(self, obj):
        """Display summary of batch processing times"""
        if not obj.status_metadata or not isinstance(obj.status_metadata, dict):
            return "No batch processing data available"
            
        summary = obj.status_metadata.get("average_batch_processing_times", {})
        if not summary:
            return "No batch processing data available"
            
        table_style = """
            <style>
                .batch-summary-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }
                .batch-summary-table th, .batch-summary-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                .batch-summary-table th {
                    background-color: #f5f5f5;
                }
                .batch-summary-table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
            </style>
        """
        
        table_html = f"""
            {table_style}
            <table class="batch-summary-table">
                <tr>
                    <th>Node Label</th>
                    <th>Avg. Batch Processing Time (seconds)</th>
                </tr>
        """
        
        for label, time in summary.items():
            table_html += f"""
                <tr>
                    <td>{label}</td>
                    <td>{time:.2f}</td>
                </tr>
            """
            
        table_html += "</table>"
        return mark_safe(table_html)
    batch_summary.short_description = 'Batch Processing Summary'

    def run_view(self, request, object_id):
        """Handle run action to start embedding job"""
        try:
            obj = self.get_object(request, object_id)
            if not obj:
                self.message_user(request, "Embedding job not found.", messages.ERROR)
                return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

            if obj.status == DataEmbedding.STATUS_PROCESSING:
                self.message_user(
                    request, 
                    "Cannot start job while it is already being processed.",
                    messages.WARNING
                )
            else:
                obj.status = DataEmbedding.STATUS_PENDING
                obj.completion_percentage = 0
                obj.nodes_processed = 0
                obj.embeddings_generated = 0
                obj.total_processing_time = 0
                obj.execution_start_at = None
                obj.execution_end_at = None
                obj.save()
                
                from django.core.management import call_command
                try:
                    call_command('generate_embedding_for_data_processing', id=str(obj.id))
                    self.message_user(
                        request, 
                        f"Embedding job '{obj.name}' has been started. You can check the status on this page.",
                        messages.SUCCESS
                    )
                except Exception as e:
                    obj.status = DataEmbedding.STATUS_ERROR
                    obj.processing_error = str(e)
                    obj.save()
                    self.message_user(
                        request, 
                        f"Error starting embedding job: {str(e)}",
                        messages.ERROR
                    )
        
        except Exception as e:
            self.message_user(request, f"Error running embedding job: {str(e)}", messages.ERROR)
        
        change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
        return redirect(change_url)

    def reset_view(self, request, object_id):
        """Handle reset action to reset embedding job stats"""
        try:
            obj = self.get_object(request, object_id)
            if not obj:
                self.message_user(request, "Embedding job not found.", messages.ERROR)
                return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

            if obj.status == DataEmbedding.STATUS_PROCESSING:
                self.message_user(
                    request, 
                    "Cannot reset job while it is being processed.",
                    messages.WARNING
                )
            else:
                obj.status = DataEmbedding.STATUS_PENDING
                obj.completion_percentage = 0
                obj.nodes_processed = 0
                obj.embeddings_generated = 0
                obj.total_processing_time = 0
                obj.execution_start_at = None
                obj.execution_end_at = None
                obj.processing_error = ""
                obj.status_metadata = {}
                obj.save()
                
                self.message_user(
                    request, 
                    f"Embedding job '{obj.name}' has been reset successfully.",
                    messages.SUCCESS
                )
        
        except Exception as e:
            self.message_user(request, f"Error resetting embedding job: {str(e)}", messages.ERROR)
        
        change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
        return redirect(change_url)

    def save_model(self, request, obj, form, change):
        """Handle saving model"""
        if not change:
            obj.status = DataEmbedding.STATUS_PENDING
            obj.completion_percentage = 0
        print('obj', obj.labels, obj.selected_properties)
        super().save_model(request, obj, form, change)
        
        if not change and request.POST.get('_run_immediately'):
            self.run_view(request, obj.pk)

# from django.contrib import admin
# from django.utils.html import format_html
# from django.utils.safestring import mark_safe
# from .models import DataEnrichment, DataEnrichmentPartition, DataIngestion, DataIngestionPartition, DataEmbedding
# from .forms import DataEmbeddingForm
# from basics.admin import BaseModelAdmin
# from django.utils import timezone
# from .forms import DataEnrichmentForm, DataIngestionForm
# from django.urls import path, reverse
# from django.shortcuts import redirect
# from django.contrib import messages
# import math
# from django.http import JsonResponse


# class SaveInlineModelAdmin(admin.TabularInline):
#     """Base class for inlines with save buttons"""
#     template = 'admin/edit_inline/tabular_with_save.html'
    
#     def get_formset(self, request, obj=None, **kwargs):
#         formset = super().get_formset(request, obj, **kwargs)
#         formset.request = request  # Store request for use in save_inline
#         return formset


# class DataEnrichmentPartitionInline(SaveInlineModelAdmin):
#     model = DataEnrichmentPartition
#     extra = 0
#     readonly_fields = ('partition_id', 'input_file_link', 'created_at', 'processed_at', 'error_message')
#     fields = ('partition_id', 'status', 'input_file_link', 'processed_at', 'error_message', 'created_at')
#     can_delete = True
#     max_num = 0
#     template = 'admin/data_processing/dataenrichment/partitions_inline.html'

#     def has_add_permission(self, request, obj=None):
#         return False

#     def partition_id(self, obj):
#         return obj.id
#     partition_id.short_description = 'Partition ID'

#     def input_file_link(self, obj):
#         """Display input file link"""
#         if obj.input_file_path:
#             url = obj.get_input_file_url()
#             file_name = obj.input_file_path.split('/')[-1]
#             button_style = """
#                 background-color: #5bc0de;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
#                 url, button_style, file_name
#             )
#         return "-"
#     input_file_link.short_description = 'Input File'
#     input_file_link.allow_tags = True

#     class Media:
#         js = ('data_processing/js/admin/data_enrichment.js',)

#     def save_inline(self, obj):
#         """Display save button for individual inline"""
#         if obj and obj.pk:
#             button_style = """
#                 background-color: #5cb85c;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#                 border: none;
#                 cursor: pointer;
#             """
#             return format_html(
#                 '<button type="submit" name="_save_inline" value="{}" style="{}" onclick="return confirm(\'Save this partition?\')"> Save</button>',
#                 obj.pk,
#                 button_style
#             )
#         return ""
#     save_inline.short_description = ''
#     save_inline.allow_tags = True

#     def output_file_link(self, obj):
#         """Display output file link"""
#         if obj.output_file_path:
#             url = obj.get_output_file_url()
#             file_name = obj.output_file_path.split('/')[-1]
#             button_style = """
#                 background-color: #5cb85c;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View Output</a><br><small>{}</small>',
#                 url, button_style, file_name
#             )
#         return "-"
#     output_file_link.short_description = 'Output File'
#     output_file_link.allow_tags = True


# @admin.register(DataEnrichment)
# class DataEnrichmentAdmin(BaseModelAdmin):
#     form = DataEnrichmentForm
#     inlines = [DataEnrichmentPartitionInline]
#     list_display = ('id', 'session_id', 'name', 'prompt', 'llm_model', 'status',
#                     'status_with_progress', 'partition_status', 'input_file_size', 'get_input_file', 'get_output_file',
#                     'execution_time_display', 'created_at', 'is_active', 'reset_button')
#     list_display_links = ('id', 'session_id', 'name', 'prompt', 'created_at')
#     list_filter = ('status', 'llm_model', 'is_active')
#     search_fields = ('prompt', 'id', 'name')
#     readonly_fields = ('file_size', 'completion_percentage', 'execution_start_at', 
#                        'execution_end_at', 'execution_time_display', 
#                        'partition_status', # 'status_metadata', 
#                        'file_status_table', 'session_id', 'reset_button')
#     list_per_page = 20
#     list_editable = ('status','llm_model')
#     fieldsets = (
#             ('Basic Information', {
#                 'fields': ('session_id', 'status', 'name', 'input_file', 'output_file', 'prompt',
#                 'llm_model', 'batch_size', 'file_size', 
#                 'completion_percentage',
#                 'combine_output_files', 
#                 'parallel_threading_count', 'metadata', 'status_metadata', 'processing_error', 'reset_button')
#             }),
#             ('File Status', {
#                 'fields': ('file_status_table',),
#             }),
#             ('Execution Details', {
#                 'fields': ('execution_start_at', 'execution_end_at', 'execution_time_display', 'partition_status'),
#                 'classes': ('collapse',)
#             }),
#         )

#     class Media:
#         css = {
#             'all': ('data_processing/css/admin/custom.css',)
#         }
#         js = ('data_processing/js/admin/data_enrichment.js',)

#     def get_urls(self):
#         info = self.model._meta.app_label, self.model._meta.model_name
#         urls = [
#             path(
#                 '<path:object_id>/reset/',
#                 self.admin_site.admin_view(self.reset_view),
#                 name='%s_%s_reset' % info
#             ),
#             path(
#                 '<path:object_id>/save_partition/<path:partition_id>/',
#                 self.admin_site.admin_view(self.save_partition_view),
#                 name='%s_%s_save_partition' % info
#             ),
#         ]
#         return urls + super().get_urls()

#     def save_partition_view(self, request, object_id, partition_id):
#         """Handle saving individual partition"""
#         if request.method != 'POST':
#             return JsonResponse({'error': 'Invalid request method'}, status=405)
            
#         try:
#             # Get the partition being saved
#             partition = DataEnrichmentPartition.objects.get(
#                 pk=partition_id,
#                 enrichment_id=object_id
#             )
            
#             # Update partition fields from form data
#             prefix = f'dataenrichmentpartition_set-{partition_id}'
#             form_data = {}
#             for key, value in request.POST.items():
#                 if key.startswith(prefix):
#                     field = key.replace(f'{prefix}-', '')
#                     if hasattr(partition, field):
#                         form_data[field] = value
            
#             # Update partition fields
#             for field, value in form_data.items():
#                 setattr(partition, field, value)
            
#             # Save only the partition
#             partition.save()
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f'Successfully saved partition {partition.id}'
#             })
            
#         except DataEnrichmentPartition.DoesNotExist:
#             return JsonResponse({
#                 'error': f'Partition {partition_id} not found'
#             }, status=404)
#         except Exception as e:
#             return JsonResponse({
#                 'error': f'Error saving partition: {str(e)}'
#             }, status=500)

#     def save_model(self, request, obj, form, change):
#         if obj.input_file:
#             try:
#                 file_size_bytes = obj.input_file.size
#                 if file_size_bytes < 1024 * 1024:  # Less than 1MB
#                     # Store KB value with one decimal
#                     obj.file_size = round(file_size_bytes / 1024, 1)
#                 else:
#                     # Store MB value rounded up
#                     obj.file_size = math.ceil(file_size_bytes / (1024 * 1024))
#             except Exception as e:
#                 print("Exception", str(e))
#                 obj.file_size = 0
#         super().save_model(request, obj, form, change)

#     def reset_button(self, obj):
#         """Display reset button in admin"""
#         if not obj or not obj.pk:  # Check if object exists
#             return ""

#         non_resettable_states = [
#             # DataEnrichment.STATUS_PARTITION_CREATED,  # Already in initial state
#             # DataEnrichment.STATUS_PENDING,  # Nothing to reset
#             # DataEnrichment.STATUS_PROCESSING,  # Cannot reset while processing
#         ]
        
#         if obj.status not in non_resettable_states:
#             button_style = """
#                 background-color: #d9534f;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#             """
#             url = f"../../{obj.pk}/reset/"
#             return format_html(
#                 '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this request? This will:\n\n1. Reset all partitions to pending state\n2. Clear execution timestamps\n3. Reset completion percentage to 0\n4. Preserve original data and partition structure\n\nProceed?\')">Reset Request</a>',
#                 button_style,
#                 url
#             )
#         elif obj.status == DataEnrichment.STATUS_PROCESSING:
#             button_style = """
#                 background-color: #777;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#                 cursor: not-allowed;
#                 opacity: 0.65;
#             """
#             return format_html(
#                 '<span style="{}" title="Cannot reset while request is being processed - {} partitions are currently being processed in parallel">Reset Request</span>',
#                 button_style,
#                 5  # From memory: PARALLEL_EXECUTION_COUNT
#             )
#         return ""
#     reset_button.short_description = 'Reset'
#     reset_button.allow_tags = True

#     def reset_view(self, request, object_id):
#         """Handle reset action"""
#         try:
#             obj = self.get_object(request, object_id)
#             if not obj:
#                 self.message_user(request, "Request not found.", messages.ERROR)
#                 return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

#             if obj.status == DataEnrichment.STATUS_PROCESSING:
#                 self.message_user(
#                     request, 
#                     f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.",
#                     messages.WARNING
#                 )
#             else:
#                 summary = obj.reset_partition_stats()
#                 self.message_user(
#                     request, 
#                     f"Request has been reset successfully. All {summary['total']} partitions are now in pending state and ready for parallel processing.",
#                     messages.SUCCESS
#                 )
#         except ValueError as e:
#             self.message_user(request, str(e), messages.WARNING)
#         except Exception as e:
#             self.message_user(request, f"Error resetting request: {str(e)}", messages.ERROR)
        
#         change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
#         return redirect(change_url)

#     def get_form(self, request, obj=None, **kwargs):
#         """
#         Override get_form to inject company and request context into form
#         """
#         form = super().get_form(request, obj, **kwargs)

#         # Set request as a class attribute for access in __init__
#         form.request = request
#         return form

#     def status_with_progress(self, obj):
#         """Display status with progress percentage if processing"""
#         status_display = obj.get_status_display_with_percentage()
#         status_colors = {
#             DataEnrichment.STATUS_PENDING: '#f0ad4e',     # Orange
#             DataEnrichment.STATUS_PROCESSING: '#5bc0de',  # Blue
#             DataEnrichment.STATUS_DONE: '#5cb85c',       # Green
#             DataEnrichment.STATUS_ERROR: '#d9534f'       # Red
#         }
#         color = status_colors.get(obj.status, 'inherit')
#         return format_html('<span style="color: {};">{}</span>', color, status_display)
#     status_with_progress.short_description = 'Status'

#     def partition_status(self, obj):
#         """Display partition processing status"""
#         summary = obj.get_partition_status_summary()
#         if obj.status == DataEnrichment.STATUS_ERROR:
#             return format_html('<span style="color: #d9534f;">{}</span>', summary)
#         return summary
#     partition_status.short_description = 'Partitions'

#     def execution_time_display(self, obj):
#         """Display execution time in human-readable format"""
#         return obj.get_execution_time_display()
#     execution_time_display.short_description = 'Execution Time'

#     def file_status_table(self, obj):
#         """Display file status table with processing details"""
#         if not obj.status_metadata:
#             return "No file status information available"

#         # Define table styles
#         table_style = """
#             <style>
#                 .file-status-table {
#                     width: 100%;
#                     border-collapse: collapse;
#                     margin-top: 10px;
#                 }
#                 .file-status-table th, .file-status-table td {
#                     border: 1px solid #ddd;
#                     padding: 8px;
#                     text-align: left;
#                 }
#                 .file-status-table th {
#                     background-color: #f5f5f5;
#                 }
#                 .file-status-table tr:nth-child(even) {
#                     background-color: #f9f9f9;
#                 }
#                 .status-icon {
#                     font-size: 18px;
#                 }
#                 .status-success {
#                     color: #5cb85c;
#                 }
#                 .status-error {
#                     color: #d9534f;
#                 }
#             </style>
#         """

#         # Create table header
#         table_html = f"""
#             {table_style}
#             <table class="file-status-table">
#                 <tr>
#                     <th>S.No</th>
#                     <th>Input File</th>
#                     <th>Output File</th>
#                     <th>Status</th>
#                     <th>Processed At</th>
#                     <th>Error</th>
#                 </tr>
#         """

#         # Add rows for each partition
#         for idx, partition in enumerate(obj.status_metadata, 1):
#             is_processed = partition.get("is_processed", False)
#             error = partition.get("error", "")
#             processed_at = partition.get("processed_at", "")
            
#             # Create status icon
#             if is_processed and not error:
#                 status_icon = '<span class="status-icon status-success">✓</span>'
#             else:
#                 status_icon = '<span class="status-icon status-error">✗</span>'

#             # Format processed_at
#             if processed_at:
#                 # Assuming ISO format string, convert to more readable format
#                 try:
#                     from datetime import datetime
#                     dt = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
#                     processed_at = dt.strftime('%Y-%m-%d %H:%M:%S')
#                 except:
#                     pass

#             table_html += f"""
#                 <tr>
#                     <td>{idx}</td>
#                     <td>{partition.get("input_file_name", "")}</td>
#                     <td>{partition.get("output_file_name", "")}</td>
#                     <td>{status_icon}</td>
#                     <td>{processed_at}</td>
#                     <td style="color: #d9534f;">{error}</td>
#                 </tr>
#             """

#         table_html += "</table>"
#         return mark_safe(table_html)
#     file_status_table.short_description = 'File Status'

#     def get_input_file(self, obj):
#         """Display input file link"""
#         if obj.input_file:
#             url = obj.get_input_file_url()
#             file_name = obj.input_file.name.split('/')[-1]
#             button_style = """
#                 background-color: #5bc0de;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
#                 url, button_style, file_name
#             )
#         return "-"
#     get_input_file.short_description = 'Input File'
#     get_input_file.allow_tags = True

#     def get_output_file(self, obj):
#         """Display output file link"""
#         if obj.output_file:
#             url = obj.get_output_file_url()
#             file_name = obj.output_file.name.split('/')[-1]
#             button_style = """
#                 background-color: #5cb85c;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View Output</a><br><small>{}</small>',
#                 url, button_style, file_name
#             )
#         return "-"
#     get_output_file.short_description = 'Output File'
#     get_output_file.allow_tags = True

#     def get_completion_percentage(self, obj):
#         return f"{obj.completion_percentage}%"
#     get_completion_percentage.short_description = '%'

#     def get_execution_time(self, obj):
#         """Display execution time as end - start"""
#         if obj.execution_start_at and obj.execution_end_at:
#             duration = obj.execution_end_at - obj.execution_start_at
#             # Convert to hours, minutes, seconds
#             hours = duration.seconds // 3600
#             minutes = (duration.seconds % 3600) // 60
#             seconds = duration.seconds % 60
            
#             if hours > 0:
#                 return f"{hours}h {minutes}m {seconds}s"
#             elif minutes > 0:
#                 return f"{minutes}m {seconds}s"
#             else:
#                 return f"{seconds}s"
#         return "-"
#     get_execution_time.short_description = "Execution Time"


# class DataIngestionPartitionInline(admin.TabularInline):
#     model = DataIngestionPartition
#     extra = 0
#     readonly_fields = ('partition_id', 'input_file_link', 'created_at', 'processed_at', 'error_message')
#     fields = ('partition_id', 'status', 'input_file_link', 'processed_at', 'error_message', 'created_at')
#     can_delete = True
#     max_num = 0

#     def has_add_permission(self, request, obj=None):
#         return False

#     def partition_id(self, obj):
#         return obj.id
#     partition_id.short_description = 'Partition ID'

#     def input_file_link(self, obj):
#         """Display input file link"""
#         if obj.input_file_path:
#             url = obj.get_input_file_url()
#             file_name = obj.input_file_path.split('/')[-1]
#             button_style = """
#                 background-color: #5bc0de;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View Input</a><br><small>{}</small>',
#                 url, button_style, file_name
#             )
#         return "-"
#     input_file_link.short_description = 'Input File'
#     input_file_link.allow_tags = True

# @admin.register(DataIngestion)
# class DataIngestionAdmin(BaseModelAdmin):
#     form = DataIngestionForm
#     inlines = [DataIngestionPartitionInline]
#     list_display = ('id', 'session_id', 'name', 'status', 'execution_type', 'destination', 
#                    'status_with_progress', 'partition_status', 'get_file', 
#                    'execution_time_display', 'created_at', 'is_active', 'reset_button')
#     list_display_links = ('id', 'session_id', 'name', 'created_at')
#     list_filter = ('status', 'execution_type', 'destination', 'is_active')
#     search_fields = ('name', 'id')
#     readonly_fields = ('execution_time_display', 'partition_status', 'status_with_progress',
#                       'completion_percentage', 'execution_start_at', 'execution_end_at', 'session_id', 
#                       'reset_button')
#     list_per_page = 20
#     list_editable = ('status',)
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('session_id', 'status', 'name', 'file', 'execution_type', 'workflow', 'prompt_name',
#             'schema_type', 'prompt_defined_schema', 'prompt_create_schema', 'destination',
#             'chunk_size', 'chunk_overlap', 'completion_percentage', 'status_metadata', 'processing_error', 'reset_button')
#         }),
#         ('Execution Details', {
#             'fields': ('execution_start_at', 'execution_end_at', 'execution_time_display', 'partition_status'),
#             'classes': ('collapse',)
#         }),
#     )

#     class Media:
#         js = ('data_processing/static/data_processing/js/admin/data_ingestion.js',)

#     def get_urls(self):
#         info = self.model._meta.app_label, self.model._meta.model_name
#         urls = [
#             path(
#                 '<path:object_id>/reset/',
#                 self.admin_site.admin_view(self.reset_view),
#                 name='%s_%s_reset' % info
#             ),
#         ]
#         return urls + super().get_urls()

#     def reset_button(self, obj):
#         """Display reset button in admin"""
#         if not obj or not obj.pk:  # Check if object exists
#             return ""

#         non_resettable_states = [
#             # DataIngestion.STATUS_PROCESSING,  # Cannot reset while processing
#         ]

#         if obj.status not in non_resettable_states:
#             button_style = """
#                 background-color: #d9534f;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#             """
#             url = f"../../{obj.pk}/reset/"
#             return format_html(
#                 '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this request? This will:\n\n1. Reset all partitions to pending state\n2. Clear execution timestamps\n3. Reset completion percentage to 0\n4. Preserve original data and partition structure\n\nProceed?\')">Reset Request</a>',
#                 button_style,
#                 url
#             )
#         elif obj.status == DataIngestion.STATUS_PROCESSING:
#             button_style = """
#                 background-color: #777;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#                 cursor: not-allowed;
#                 opacity: 0.65;
#             """
#             return format_html(
#                 '<span style="{}" title="Cannot reset while request is being processed - {} partitions are currently being processed in parallel">Reset Request</span>',
#                 button_style,
#                 5  # From memory: PARALLEL_EXECUTION_COUNT
#             )
#         return ""
#     reset_button.short_description = 'Reset'
#     reset_button.allow_tags = True

#     def reset_view(self, request, object_id):
#         """Handle reset action"""
#         try:
#             obj = self.get_object(request, object_id)
#             if not obj:
#                 self.message_user(request, "Request not found.", messages.ERROR)
#                 return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

#             if obj.status == DataIngestion.STATUS_PROCESSING:
#                 self.message_user(
#                     request, 
#                     f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.",
#                     messages.WARNING
#                 )
#             else:
#                 summary = obj.reset_partition_stats()
#                 self.message_user(
#                     request, 
#                     f"Request has been reset successfully. All {summary['total']} partitions are now in pending state and ready for parallel processing.",
#                     messages.SUCCESS
#                 )
#         except ValueError as e:
#             self.message_user(request, str(e), messages.WARNING)
#         except Exception as e:
#             self.message_user(request, f"Error resetting request: {str(e)}", messages.ERROR)

#         change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
#         return redirect(change_url)

#     def get_form(self, request, obj=None, **kwargs):
#         """
#         Override get_form to inject company and request context into form
#         """
#         form = super().get_form(request, obj, **kwargs)

#         # Set request as a class attribute for access in __init__
#         form.request = request
#         return form

#     def status_with_progress(self, obj):
#         """Display status with progress percentage if processing"""
#         status_display = obj.get_status_display_with_percentage()
#         status_colors = {
#             DataIngestion.STATUS_PENDING: '#f0ad4e',     # Orange
#             DataIngestion.STATUS_PROCESSING: '#5bc0de',  # Blue
#             DataIngestion.STATUS_DONE: '#5cb85c',       # Green
#             DataIngestion.STATUS_ERROR: '#d9534f'       # Red
#         }
#         color = status_colors.get(obj.status, 'inherit')
#         return format_html('<span style="color: {};">{}</span>', color, status_display)
#     status_with_progress.short_description = 'Status'

#     def partition_status(self, obj):
#         """Display partition processing status"""
#         summary = obj.get_partition_status_summary()
#         if obj.status == DataIngestion.STATUS_ERROR:
#             return format_html('<span style="color: #d9534f;">{}</span>', summary)
#         return summary
#     partition_status.short_description = 'Partitions'

#     def execution_time_display(self, obj):
#         """Display execution time in human-readable format"""
#         return obj.get_execution_time_display()
#     execution_time_display.short_description = 'Execution Time'

#     def get_file(self, obj):
#         """Display file link"""
#         if obj.file:
#             file_url = obj.file.url if hasattr(obj.file, 'url') else f"/media/{obj.file.name}"
#             file_name = obj.file.name.split('/')[-1]
#             button_style = """
#                 background-color: #5bc0de;
#                 color: white;
#                 padding: 4px 8px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-size: 12px;
#                 display: inline-block;
#             """
#             return format_html(
#                 '<a href="{}" style="{}" target="_blank">📄 View File</a><br><small>{}</small>',
#                 file_url, button_style, file_name
#             )
#         return "-"
#     get_file.short_description = 'File'
#     get_file.allow_tags = True

#     def save_model(self, request, obj, form, change):
#         # Add any pre-save logic if needed
#         super().save_model(request, obj, form, change)


# @admin.register(DataEmbedding)
# class DataEmbeddingAdmin(BaseModelAdmin):
#     form = DataEmbeddingForm
#     list_display = ('id', 'session_id', 'name', 'status', 'status_with_progress', 
#                    'nodes_count', 'embeddings_count', 
#                    'execution_time_display', 'created_at', 'is_active', 'reset_button')
#     list_display_links = ('id', 'session_id', 'name', 'created_at')
#     list_filter = ('status', 'is_active')
#     search_fields = ('name', 'id')
#     readonly_fields = ('session_id', 'status', 'completion_percentage', 'nodes_processed', 
#                       'embeddings_generated', 'total_processing_time', 'execution_start_at', 
#                       'execution_end_at', 'execution_time_display', 'status_with_progress',
#                       'reset_button', 'label_summary', 'batch_summary')
#     list_per_page = 20
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('session_id', 'name', 'status', 'completion_percentage')
#         }),
#         ('Neo4j & OpenAI Configuration', {
#             'fields': ('use_company_credentials', 'NEO4J_URL', 'NEO4J_USERNAME', 'NEO4J_PASSWORD', 'OPENAI_API_KEY'),
#         }),
#         ('Embedding Configuration', {
#             'fields': ('node_labels', 'batch_size', 'max_label_workers', 'max_batch_workers'),
#         }),
#         ('Processing Statistics', {
#             'fields': ('nodes_processed', 'embeddings_generated', 'total_processing_time', 
#                       'execution_start_at', 'execution_end_at', 'execution_time_display'),
#         }),
#         ('Detailed Statistics', {
#             'fields': ('label_summary', 'batch_summary'),
#             'classes': ('collapse',),
#         }),
#         ('Advanced', {
#             'fields': ('status_metadata', 'processing_error', 'reset_button'),
#             'classes': ('collapse',),
#         }),
#     )

#     class Media:
#         css = {
#             'all': ('data_processing/css/admin/custom.css',)
#         }
#         js = ('data_processing/js/admin/data_embedding.js',)

#     def get_urls(self):
#         info = self.model._meta.app_label, self.model._meta.model_name
#         urls = [
#             path(
#                 '<path:object_id>/reset/',
#                 self.admin_site.admin_view(self.reset_view),
#                 name='%s_%s_reset' % info
#             ),
#             path(
#                 '<path:object_id>/run/',
#                 self.admin_site.admin_view(self.run_view),
#                 name='%s_%s_run' % info
#             ),
#         ]
#         return urls + super().get_urls()

#     def get_form(self, request, obj=None, **kwargs):
#         """
#         Override get_form to inject company and request context into form
#         """
#         form = super().get_form(request, obj, **kwargs)

#         form.request = request
#         return form

#     def status_with_progress(self, obj):
#         """Display status with progress percentage if processing"""
#         status_colors = {
#             DataEmbedding.STATUS_PENDING: '#f0ad4e',     
#             DataEmbedding.STATUS_PROCESSING: '#5bc0de',  
#             DataEmbedding.STATUS_DONE: '#5cb85c',       
#             DataEmbedding.STATUS_ERROR: '#d9534f'       
#         }
#         color = status_colors.get(obj.status, 'inherit')
        
#         if obj.status == DataEmbedding.STATUS_PROCESSING:
#             status_text = f"{obj.get_status_display()} ({obj.completion_percentage}%)"
#         else:
#             status_text = obj.get_status_display()
            
#         return format_html('<span style="color: {};">{}</span>', color, status_text)
#     status_with_progress.short_description = 'Status'

#     def nodes_count(self, obj):
#         """Display number of processed nodes"""
#         return format_html('<b>{}</b>', obj.nodes_processed)
#     nodes_count.short_description = 'Nodes'

#     def embeddings_count(self, obj):
#         """Display number of generated embeddings"""
#         return format_html('<b>{}</b>', obj.embeddings_generated)
#     embeddings_count.short_description = 'Embeddings'

#     def execution_time_display(self, obj):
#         """Display execution time in human-readable format"""
#         return obj.get_execution_time_display()
#     execution_time_display.short_description = 'Execution Time'

#     def reset_button(self, obj):
#         """Display reset button in admin"""
#         if not obj or not obj.pk:  
#             return ""

#         non_resettable_states = [
#             DataEmbedding.STATUS_PROCESSING,  
#         ]
        
#         if obj.status not in non_resettable_states:
#             button_style = """
#                 background-color: #d9534f;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#             """
#             url = f"../../{obj.pk}/reset/"
#             return format_html(
#                 '<a style="{}" href="{}" onclick="return confirm(\'Are you sure you want to reset this embedding job? This will clear all statistics and reset the status to pending.\')">Reset Job</a>',
#                 button_style,
#                 url
#             )
#         elif obj.status == DataEmbedding.STATUS_PROCESSING:
#             button_style = """
#                 background-color: #777;
#                 color: white;
#                 padding: 8px 16px;
#                 border-radius: 4px;
#                 text-decoration: none;
#                 font-weight: bold;
#                 display: inline-block;
#                 margin: 4px 0;
#                 cursor: not-allowed;
#                 opacity: 0.65;
#             """
#             return format_html(
#                 '<span style="{}" title="Cannot reset while job is being processed">Reset Job</span>',
#                 button_style
#             )
#         return ""
#     reset_button.short_description = 'Reset'
#     reset_button.allow_tags = True

#     def label_summary(self, obj):
#         """Display summary of label processing times"""
#         if not obj.status_metadata or not isinstance(obj.status_metadata, dict):
#             return "No label processing data available"
            
#         summary = obj.status_metadata.get("average_label_processing_times", {})
#         if not summary:
#             return "No label processing data available"
            
#         table_style = """
#             <style>
#                 .label-summary-table {
#                     width: 100%;
#                     border-collapse: collapse;
#                     margin-top: 10px;
#                 }
#                 .label-summary-table th, .label-summary-table td {
#                     border: 1px solid #ddd;
#                     padding: 8px;
#                     text-align: left;
#                 }
#                 .label-summary-table th {
#                     background-color: #f5f5f5;
#                 }
#                 .label-summary-table tr:nth-child(even) {
#                     background-color: #f9f9f9;
#                 }
#             </style>
#         """
        
#         table_html = f"""
#             {table_style}
#             <table class="label-summary-table">
#                 <tr>
#                     <th>Node Label</th>
#                     <th>Avg. Processing Time (seconds)</th>
#                 </tr>
#         """
        
#         for label, time in summary.items():
#             table_html += f"""
#                 <tr>
#                     <td>{label}</td>
#                     <td>{time:.2f}</td>
#                 </tr>
#             """
            
#         table_html += "</table>"
#         return mark_safe(table_html)
#     label_summary.short_description = 'Label Processing Summary'
    
#     def batch_summary(self, obj):
#         """Display summary of batch processing times"""
#         if not obj.status_metadata or not isinstance(obj.status_metadata, dict):
#             return "No batch processing data available"
            
#         summary = obj.status_metadata.get("average_batch_processing_times", {})
#         if not summary:
#             return "No batch processing data available"
            
#         table_style = """
#             <style>
#                 .batch-summary-table {
#                     width: 100%;
#                     border-collapse: collapse;
#                     margin-top: 10px;
#                 }
#                 .batch-summary-table th, .batch-summary-table td {
#                     border: 1px solid #ddd;
#                     padding: 8px;
#                     text-align: left;
#                 }
#                 .batch-summary-table th {
#                     background-color: #f5f5f5;
#                 }
#                 .batch-summary-table tr:nth-child(even) {
#                     background-color: #f9f9f9;
#                 }
#             </style>
#         """
        
#         table_html = f"""
#             {table_style}
#             <table class="batch-summary-table">
#                 <tr>
#                     <th>Node Label</th>
#                     <th>Avg. Batch Processing Time (seconds)</th>
#                 </tr>
#         """
        
#         for label, time in summary.items():
#             table_html += f"""
#                 <tr>
#                     <td>{label}</td>
#                     <td>{time:.2f}</td>
#                 </tr>
#             """
            
#         table_html += "</table>"
#         return mark_safe(table_html)
#     batch_summary.short_description = 'Batch Processing Summary'

#     def run_view(self, request, object_id):
#         """Handle run action to start embedding job"""
#         try:
#             obj = self.get_object(request, object_id)
#             if not obj:
#                 self.message_user(request, "Embedding job not found.", messages.ERROR)
#                 return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

#             if obj.status == DataEmbedding.STATUS_PROCESSING:
#                 self.message_user(
#                     request, 
#                     "Cannot start job while it is already being processed.",
#                     messages.WARNING
#                 )
#             else:
#                 obj.status = DataEmbedding.STATUS_PENDING
#                 obj.completion_percentage = 0
#                 obj.nodes_processed = 0
#                 obj.embeddings_generated = 0
#                 obj.total_processing_time = 0
#                 obj.execution_start_at = None
#                 obj.execution_end_at = None
#                 obj.save()
                
#                 # Start the embedding job in a background task
#                 # Here you would typically call a background task or add to a queue
#                 # For simplicity, let's assume you have a management command to do this
#                 from django.core.management import call_command
#                 try:
#                     # Start embedding process in background
#                     call_command('generate_embedding_for_data_processing', id=str(obj.id))
#                     self.message_user(
#                         request, 
#                         f"Embedding job '{obj.name}' has been started. You can check the status on this page.",
#                         messages.SUCCESS
#                     )
#                 except Exception as e:
#                     obj.status = DataEmbedding.STATUS_ERROR
#                     obj.processing_error = str(e)
#                     obj.save()
#                     self.message_user(
#                         request, 
#                         f"Error starting embedding job: {str(e)}",
#                         messages.ERROR
#                     )
        
#         except Exception as e:
#             self.message_user(request, f"Error running embedding job: {str(e)}", messages.ERROR)
        
#         change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
#         return redirect(change_url)

#     def reset_view(self, request, object_id):
#         """Handle reset action to reset embedding job stats"""
#         try:
#             obj = self.get_object(request, object_id)
#             if not obj:
#                 self.message_user(request, "Embedding job not found.", messages.ERROR)
#                 return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

#             if obj.status == DataEmbedding.STATUS_PROCESSING:
#                 self.message_user(
#                     request, 
#                     "Cannot reset job while it is being processed.",
#                     messages.WARNING
#                 )
#             else:
#                 obj.status = DataEmbedding.STATUS_PENDING
#                 obj.completion_percentage = 0
#                 obj.nodes_processed = 0
#                 obj.embeddings_generated = 0
#                 obj.total_processing_time = 0
#                 obj.execution_start_at = None
#                 obj.execution_end_at = None
#                 obj.processing_error = ""
#                 obj.status_metadata = {}
#                 obj.save()
                
#                 self.message_user(
#                     request, 
#                     f"Embedding job '{obj.name}' has been reset successfully.",
#                     messages.SUCCESS
#                 )
        
#         except Exception as e:
#             self.message_user(request, f"Error resetting embedding job: {str(e)}", messages.ERROR)
        
#         change_url = reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name), args=[object_id])
#         return redirect(change_url)

#     def save_model(self, request, obj, form, change):
#         """Handle saving model"""
#         if not change:
#             obj.status = DataEmbedding.STATUS_PENDING
#             obj.completion_percentage = 0
            
#         super().save_model(request, obj, form, change)
        
#         if not change and request.POST.get('_run_immediately'):
#             self.run_view(request, obj.pk)