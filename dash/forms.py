from django import forms
from .models import ApiKeyProxyModel, ApiKey


class ApiKeyProxyInlineForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value dynamically
        if not self.instance.pk and hasattr(self, "company"):
            # Example: Set initial value based on some custom logic
            self.fields['key'].initial = ApiKey().generate_api_key(company=self.company)

    def clean_key(self):
        key = self.cleaned_data.get('key')
        if key and ApiKeyProxyModel.objects.exclude(id=self.instance.id).filter(key=key).exists():
            raise forms.ValidationError("API Key already Exists.")
        return key

    class Meta:
        model = ApiKeyProxyModel
        fields = ['key']
