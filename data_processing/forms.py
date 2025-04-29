from django import forms
from .models import DataEnrichment, DataIngestion, DataEmbedding
from backend.services.langfuse_service import LangfuseService
from backend.logger import Logger
import json

logger = Logger(Logger.INFO_LOG)


class DataEnrichmentForm(forms.ModelForm):

    prompt = forms.ChoiceField(
        choices=[],  # Will be populated dynamically
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = DataEnrichment
        fields = ['input_file', 'prompt', 'llm_model', 'batch_size']

    def __init__(self, *args, **kwargs):  
        # Get company and request from class attributes
        request = getattr(self.__class__, 'request', None)
        company = request.user.current_company if request and request.user else None
        super().__init__(*args, **kwargs)
        
        try:
            # Initialize LangfuseService with company
            langfuse_service = LangfuseService(company_id=company.id if company else None)
            # Get all available prompts
            prompts = langfuse_service.get_all_prompts()
            print("----------------------------------------", prompts)
            # Create choices list with prompt names
            prompt_choices = [(name, name) for name in prompts]
            
            # Set choices for the prompt field
            self.fields['prompt'].choices = prompt_choices
            
            # If editing an existing instance, set initial value
            if self.instance and self.instance.pk:
                self.fields['prompt'].initial = self.instance.prompt
                
        except Exception as e:
            logger.add(f"Failed to fetch prompts from Langfuse: {str(e)}", level='ERROR')
            print(f"Failed to fetch prompts from Langfuse: {str(e)}")
            # Provide a default empty choice if Langfuse is unavailable
            self.fields['prompt'].choices = [('', 'No prompts available')]

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Save the selected prompt name
        instance.prompt = self.cleaned_data['prompt']
        
        # Get company and request from class attributes
        company = getattr(self.__class__, 'company', None)
        request = getattr(self.__class__, 'request', None)
        
        # Set company if not already set
        if company and not instance.company_id:
            instance.company = company
            
        # Set created_by/updated_by if model supports it
        if hasattr(instance, 'created_by') and not instance.pk and request:
            instance.created_by = request.user
        if hasattr(instance, 'updated_by') and request:
            instance.updated_by = request.user
        
        if commit:
            instance.save()
        return instance
    

class DataIngestionForm(forms.ModelForm):

    workflow = forms.ChoiceField(
        required=False,
        choices=[],
        help_text="API Controller to use if execution type is workflow"
    )
    prompt_name = forms.ChoiceField(
        required=False,
        choices=[],
        help_text="Langfuse prompt name to use if execution type is prompt"
    )
    prompt_defined_schema = forms.ChoiceField(
        required=False,
        choices=[],
        help_text="Prompt with the defined schema"
    )
    prompt_create_schema = forms.ChoiceField(
        required=False,
        choices=[],
        help_text="Prompt used to create schema using LLM"
    )

    class Meta:
        model = DataIngestion
        fields = fields = ['name', 'file', 'execution_type', 'workflow', 'prompt_name','schema_type', 'prompt_defined_schema', 'prompt_create_schema' ,'chunk_size', 'chunk_overlap']

    def __init__(self, *args, **kwargs):  
        # Get company and request from class attributes
        request = getattr(self.__class__, 'request', None)
        company = request.user.current_company if request and request.user else None
        print(f"\n company : {company} \n")
        super().__init__(*args, **kwargs)
        
        try:
            langfuse_service = LangfuseService(company_id=company.id if company else None)
            prompts = langfuse_service.get_all_prompts()
            prompt_choices = [(name, name) for name in prompts]
            
            self.fields['prompt_name'].choices = prompt_choices
            self.fields['prompt_defined_schema'].choices = prompt_choices
            self.fields['prompt_create_schema'].choices = prompt_choices
            
            if self.instance and self.instance.pk:
                self.fields['prompt_name'].initial = self.instance.prompt_name
                self.fields['prompt_defined_schema'].initial = self.instance.prompt_defined_schema
                self.fields['prompt_create_schema'].initial = self.instance.prompt_create_schema

                
        except Exception as e:
            logger.add(f"Failed to fetch prompts from Langfuse: {str(e)}", level='ERROR')
            print(f"Failed to fetch prompts from Langfuse: {str(e)}")
            self.fields['prompt_name'].choices = [('', 'No prompts available')]
            self.fields['prompt_defined_schema'].choices = [('', 'No prompts available')]
            self.fields['prompt_create_schema'].choices = [('', 'No prompts available')]

        
        try:
            from api_controller.api.views import APIControllerManager
            manager = APIControllerManager()
            class MockRequest:
                def __init__(self, data):
                    self.data = data
            
            request = MockRequest({'company_id': company.id})
            workflow_response = manager.get_available_routes(request)
            if workflow_response.status_code == 200:
                data = workflow_response.data['data']
                self.fields['workflow'].choices = [
                    (item['id'], item['name']) for item in data
                ]

        except Exception as e:
            # Handle API fetch errors gracefully
            self.fields['workflow'].choices = [('', 'No workflows available')]

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Save the selected prompt name
        instance.prompt_name = self.cleaned_data['prompt_name']
        instance.prompt_defined_schema = self.cleaned_data['prompt_defined_schema']
        instance.prompt_create_schema = self.cleaned_data['prompt_create_schema']
        
        # Get company and request from class attributes
        company = getattr(self.__class__, 'company', None)
        request = getattr(self.__class__, 'request', None)
        
        # Set company if not already set
        if company and not instance.company_id:
            instance.company = company
            
        # Set created_by/updated_by if model supports it
        if hasattr(instance, 'created_by') and not instance.pk and request:
            instance.created_by = request.user
        if hasattr(instance, 'updated_by') and request:
            instance.updated_by = request.user
        
        if commit:
            instance.save()
        return instance

class DataEmbeddingForm(forms.ModelForm):
    
    labels = forms.CharField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'label-checkbox-list'}),
        help_text="Select Neo4j node labels to process"
    )
    
    embedding_groups = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 8,
            'style': 'font-family: monospace;',
            'placeholder': '{"Label1": {"group1_embedding": ["prop1", "prop2"], "group2_embedding": ["prop3"]}}'
        }),
        help_text="JSON mapping of labels to embedding groups and their properties"
    )

    class Meta:
        model = DataEmbedding
        fields = [
            'name', 'labels', 'embedding_groups',
            'batch_size', 'max_label_workers', 'max_batch_workers']

    def __init__(self, *args, **kwargs):
        print("\n\n===================== FORM INITIALIZATION =====================")
        
        request = getattr(self.__class__, 'request', None)
        company = request.user.current_company if request and request.user else None
        
        if len(args) > 0 and hasattr(args[0], 'get'):
            print("\nForm POST data keys:", list(args[0].keys()))
            print("Embedding groups in POST data:", args[0].get('embedding_groups', 'NOT FOUND'))
            print("Labels in POST data:", args[0].getlist('labels'))
        
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            print("\nExisting instance found with ID:", self.instance.pk)
            if hasattr(self.instance, 'labels') and isinstance(self.instance.labels, list):
                self.fields['labels'].initial = self.instance.labels
                print("Setting initial labels:", self.instance.labels)
            
            if hasattr(self.instance, 'embedding_groups'):
                if isinstance(self.instance.embedding_groups, dict):
                    self.fields['embedding_groups'].initial = json.dumps(
                        self.instance.embedding_groups, indent=2
                    )
                    print("Setting initial embedding_groups from dict:", self.instance.embedding_groups)
                elif isinstance(self.instance.embedding_groups, str):
                    try:
                        groups = json.loads(self.instance.embedding_groups)
                        self.fields['embedding_groups'].initial = json.dumps(groups, indent=2)
                        print("Setting initial embedding_groups from JSON string:", groups)
                    except json.JSONDecodeError:
                        self.fields['embedding_groups'].initial = self.instance.embedding_groups
                        print("Setting initial embedding_groups from raw string:", self.instance.embedding_groups)
            
            if hasattr(self.instance, 'whole_nodes'):
                self.fields['whole_nodes'].initial = self.instance.whole_nodes
        
        print("===================== END FORM INITIALIZATION =====================\n\n")
    
    def clean_embedding_groups(self):
        """Convert embedding_groups from JSON string to Python dict"""
        embedding_groups = self.cleaned_data.get('embedding_groups', '')
        print("\n\n===================== CLEAN EMBEDDING GROUPS =====================")
        print("Raw embedding_groups value:", embedding_groups)
        
        if not embedding_groups:
            print("No embedding groups found, returning empty dict")
            return {}
            
        try:
            groups = json.loads(embedding_groups)
            print("Successfully parsed JSON:", groups)
            
            for label, group_dict in groups.items():
                if not isinstance(group_dict, dict):
                    raise forms.ValidationError(f"Value for label '{label}' must be a dictionary of embedding groups")
                
                for group_name, props in group_dict.items():
                    if not isinstance(props, list):
                        raise forms.ValidationError(f"Properties for group '{group_name}' under label '{label}' must be a list")
            
            return groups
        except json.JSONDecodeError as e:
            print("Error parsing JSON:", str(e))
            raise forms.ValidationError(f"Invalid JSON format for embedding groups: {str(e)}")
        finally:
            print("===================== END CLEAN EMBEDDING GROUPS =====================\n\n")
            
    def clean(self):
        print("\n\n===================== CLEAN FORM =====================")
        cleaned_data = super().clean()
        
        if hasattr(self, '_errors') and self._errors:
            print("Form has errors:", self._errors)
        
        use_company_credentials = cleaned_data.get('use_company_credentials')
        
        selected_labels = self.data.getlist('labels')
        cleaned_data['labels'] = selected_labels
        
        print("Selected Labels:", selected_labels)
        print("Embedding Groups:", cleaned_data.get('embedding_groups', {}))
        
        embedding_groups = cleaned_data.get('embedding_groups', {})
        whole_nodes = cleaned_data.get('whole_nodes', False)
        
        if selected_labels and not embedding_groups and not whole_nodes:
            self.add_error(
                'embedding_groups', 
                'You must define embedding groups or enable "Generate embeddings for whole nodes" when labels are selected'
            )
                    
        print("Final cleaned data:", cleaned_data)
        print("===================== END CLEAN FORM =====================\n\n")
        return cleaned_data

    def save(self, commit=True):
        print("\n\n===================== SAVE FORM =====================")
        print("Commit:", commit)
        
        try:
            instance = super().save(commit=False)
            print("Created instance (commit=False):", instance)
            
            selected_labels = self.cleaned_data.get('labels', [])
            instance.labels = selected_labels
            print("Set labels:", selected_labels)
            
            embedding_groups = self.cleaned_data.get('embedding_groups', {})
            instance.embedding_groups = embedding_groups
            print("Set embedding_groups:", embedding_groups)
            
            whole_nodes = self.cleaned_data.get('whole_nodes', False)
            instance.whole_nodes = whole_nodes
            print("Set whole_nodes:", whole_nodes)
            
            company = getattr(self.__class__, 'company', None)
            request = getattr(self.__class__, 'request', None)
            
            if company and not instance.company_id:
                instance.company = company
                print("Set company:", company)
                
            if hasattr(instance, 'created_by') and not instance.pk and request:
                instance.created_by = request.user
                print("Set created_by:", request.user)
            if hasattr(instance, 'updated_by') and request:
                instance.updated_by = request.user
                print("Set updated_by:", request.user)
            
            if not instance.company_id and request and hasattr(request, 'user') and hasattr(request.user, 'current_company'):
                instance.company = request.user.current_company
                print("Set company from request user:", request.user.current_company)
            
            if commit:
                print("Saving instance with commit=True")
                instance.save()
                print("Instance saved successfully with ID:", instance.pk)
                
            print("Returning instance:", instance)
            return instance
            
        except Exception as e:
            print(f"Error in save method: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            print("===================== END SAVE FORM =====================\n\n")

# from django import forms
# from .models import DataEnrichment, DataIngestion, DataEmbedding
# from backend.services.langfuse_service import LangfuseService
# from backend.logger import Logger

# # Initialize logger
# logger = Logger(Logger.INFO_LOG)


# class DataEnrichmentForm(forms.ModelForm):

#     prompt = forms.ChoiceField(
#         choices=[],  # Will be populated dynamically
#         required=True,
#         widget=forms.Select(attrs={'class': 'form-control'})
#     )

#     class Meta:
#         model = DataEnrichment
#         fields = ['input_file', 'prompt', 'llm_model', 'batch_size']

#     def __init__(self, *args, **kwargs):  
#         # Get company and request from class attributes
#         request = getattr(self.__class__, 'request', None)
#         company = request.user.current_company if request and request.user else None
#         super().__init__(*args, **kwargs)
        
#         try:
#             # Initialize LangfuseService with company
#             langfuse_service = LangfuseService(company_id=company.id if company else None)
#             # Get all available prompts
#             prompts = langfuse_service.get_all_prompts()
#             print("----------------------------------------", prompts)
#             # Create choices list with prompt names
#             prompt_choices = [(name, name) for name in prompts]
            
#             # Set choices for the prompt field
#             self.fields['prompt'].choices = prompt_choices
            
#             # If editing an existing instance, set initial value
#             if self.instance and self.instance.pk:
#                 self.fields['prompt'].initial = self.instance.prompt
                
#         except Exception as e:
#             logger.add(f"Failed to fetch prompts from Langfuse: {str(e)}", level='ERROR')
#             print(f"Failed to fetch prompts from Langfuse: {str(e)}")
#             # Provide a default empty choice if Langfuse is unavailable
#             self.fields['prompt'].choices = [('', 'No prompts available')]

#     def save(self, commit=True):
#         instance = super().save(commit=False)
        
#         # Save the selected prompt name
#         instance.prompt = self.cleaned_data['prompt']
        
#         # Get company and request from class attributes
#         company = getattr(self.__class__, 'company', None)
#         request = getattr(self.__class__, 'request', None)
        
#         # Set company if not already set
#         if company and not instance.company_id:
#             instance.company = company
            
#         # Set created_by/updated_by if model supports it
#         if hasattr(instance, 'created_by') and not instance.pk and request:
#             instance.created_by = request.user
#         if hasattr(instance, 'updated_by') and request:
#             instance.updated_by = request.user
        
#         if commit:
#             instance.save()
#         return instance
    

# class DataIngestionForm(forms.ModelForm):

#     workflow = forms.ChoiceField(
#         required=False,
#         choices=[],
#         help_text="API Controller to use if execution type is workflow"
#     )
#     prompt_name = forms.ChoiceField(
#         required=False,
#         choices=[],
#         help_text="Langfuse prompt name to use if execution type is prompt"
#     )
#     prompt_defined_schema = forms.ChoiceField(
#         required=False,
#         choices=[],
#         help_text="Prompt with the defined schema"
#     )
#     prompt_create_schema = forms.ChoiceField(
#         required=False,
#         choices=[],
#         help_text="Prompt used to create schema using LLM"
#     )

#     class Meta:
#         model = DataIngestion
#         fields = fields = ['name', 'file', 'execution_type', 'workflow', 'prompt_name','schema_type', 'prompt_defined_schema', 'prompt_create_schema' ,'chunk_size', 'chunk_overlap']

#     def __init__(self, *args, **kwargs):  
#         # Get company and request from class attributes
#         request = getattr(self.__class__, 'request', None)
#         company = request.user.current_company if request and request.user else None
#         print(f"\n company : {company} \n")
#         super().__init__(*args, **kwargs)
        
#         try:
#             langfuse_service = LangfuseService(company_id=company.id if company else None)
#             prompts = langfuse_service.get_all_prompts()
#             prompt_choices = [(name, name) for name in prompts]
            
#             self.fields['prompt_name'].choices = prompt_choices
#             self.fields['prompt_defined_schema'].choices = prompt_choices
#             self.fields['prompt_create_schema'].choices = prompt_choices
            
#             if self.instance and self.instance.pk:
#                 self.fields['prompt_name'].initial = self.instance.prompt_name
#                 self.fields['prompt_defined_schema'].initial = self.instance.prompt_defined_schema
#                 self.fields['prompt_create_schema'].initial = self.instance.prompt_create_schema

                
#         except Exception as e:
#             logger.add(f"Failed to fetch prompts from Langfuse: {str(e)}", level='ERROR')
#             print(f"Failed to fetch prompts from Langfuse: {str(e)}")
#             self.fields['prompt_name'].choices = [('', 'No prompts available')]
#             self.fields['prompt_defined_schema'].choices = [('', 'No prompts available')]
#             self.fields['prompt_create_schema'].choices = [('', 'No prompts available')]

        
#         try:
#             from api_controller.api.views import APIControllerManager
#             manager = APIControllerManager()
#             class MockRequest:
#                 def __init__(self, data):
#                     self.data = data
            
#             request = MockRequest({'company_id': company.id})
#             workflow_response = manager.get_available_routes(request)
#             if workflow_response.status_code == 200:
#                 data = workflow_response.data['data']
#                 self.fields['workflow'].choices = [
#                     (item['id'], item['name']) for item in data
#                 ]

#         except Exception as e:
#             # Handle API fetch errors gracefully
#             self.fields['workflow'].choices = [('', 'No workflows available')]

#     def save(self, commit=True):
#         instance = super().save(commit=False)
        
#         # Save the selected prompt name
#         instance.prompt_name = self.cleaned_data['prompt_name']
#         instance.prompt_defined_schema = self.cleaned_data['prompt_defined_schema']
#         instance.prompt_create_schema = self.cleaned_data['prompt_create_schema']
        
#         # Get company and request from class attributes
#         company = getattr(self.__class__, 'company', None)
#         request = getattr(self.__class__, 'request', None)
        
#         # Set company if not already set
#         if company and not instance.company_id:
#             instance.company = company
            
#         # Set created_by/updated_by if model supports it
#         if hasattr(instance, 'created_by') and not instance.pk and request:
#             instance.created_by = request.user
#         if hasattr(instance, 'updated_by') and request:
#             instance.updated_by = request.user
        
#         if commit:
#             instance.save()
#         return instance

# class DataEmbeddingForm(forms.ModelForm):
#     node_labels = forms.CharField(
#         required=False,
#         widget=forms.Textarea(attrs={'rows': 3}),
#         help_text="Enter node labels separated by commas. Leave empty to process all labels."
#     )

#     class Meta:
#         model = DataEmbedding
#         fields = [
#             'name', 'node_labels',
#             'batch_size', 'max_label_workers', 'max_batch_workers'
#         ]
#         widgets = {
#             'NEO4J_PASSWORD': forms.PasswordInput(render_value=True),
#             'OPENAI_API_KEY': forms.PasswordInput(render_value=True),
#         }

#     def __init__(self, *args, **kwargs):
#         request = getattr(self.__class__, 'request', None)
#         company = request.user.current_company if request and request.user else None
#         super().__init__(*args, **kwargs)
        
#         if self.instance and self.instance.pk and isinstance(self.instance.node_labels, list):
#             self.fields['node_labels'].initial = ', '.join(self.instance.node_labels)
            
#         if self.instance and self.instance.use_company_credentials:
#             self.fields['NEO4J_URL'].required = False
#             self.fields['NEO4J_USERNAME'].required = False
#             self.fields['NEO4J_PASSWORD'].required = False
#             self.fields['OPENAI_API_KEY'].required = False
        
#         self.toggle_credential_fields()
        
#     def toggle_credential_fields(self):
#         """Toggle visibility of credential fields based on use_company_credentials"""
#         use_company_creds = self.instance.use_company_credentials if self.instance and self.instance.pk else True
        
#         if use_company_creds:
#             self.fields['NEO4J_URL'].widget.attrs['readonly'] = True
#             self.fields['NEO4J_USERNAME'].widget.attrs['readonly'] = True
#             self.fields['NEO4J_PASSWORD'].widget.attrs['readonly'] = True
#             self.fields['OPENAI_API_KEY'].widget.attrs['readonly'] = True
            
#             for field_name in ['NEO4J_URL', 'NEO4J_USERNAME', 'NEO4J_PASSWORD', 'OPENAI_API_KEY']:
#                 self.fields[field_name].widget.attrs['class'] = 'disabled-field'
#         else:
#             for field_name in ['NEO4J_URL', 'NEO4J_USERNAME', 'NEO4J_PASSWORD', 'OPENAI_API_KEY']:
#                 if 'readonly' in self.fields[field_name].widget.attrs:
#                     del self.fields[field_name].widget.attrs['readonly']
#                 if 'class' in self.fields[field_name].widget.attrs:
#                     del self.fields[field_name].widget.attrs['class']

#     def clean_node_labels(self):
#         """Convert comma-separated node labels to list"""
#         node_labels_str = self.cleaned_data.get('node_labels', '')
#         if not node_labels_str:
#             return []
            
#         node_labels = [label.strip() for label in node_labels_str.split(',') if label.strip()]
#         return node_labels
        
#     def clean(self):
#         cleaned_data = super().clean()
#         use_company_credentials = cleaned_data.get('use_company_credentials')
        
#         if not use_company_credentials:
#             required_fields = ['NEO4J_URL', 'NEO4J_USERNAME', 'NEO4J_PASSWORD', 'OPENAI_API_KEY']
#             for field_name in required_fields:
#                 if not cleaned_data.get(field_name):
#                     self.add_error(field_name, 'This field is required when not using company credentials.')
        
#         return cleaned_data

#     def save(self, commit=True):
#         instance = super().save(commit=False)
        
#         company = getattr(self.__class__, 'company', None)
#         request = getattr(self.__class__, 'request', None)
        
#         if company and not instance.company_id:
#             instance.company = company
            
#         if hasattr(instance, 'created_by') and not instance.pk and request:
#             instance.created_by = request.user
#         if hasattr(instance, 'updated_by') and request:
#             instance.updated_by = request.user
        
#         if commit:
#             instance.save()
#         return instance