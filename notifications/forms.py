from django import forms

from notifications.models import Notification


class NotificationForm(forms.ModelForm):
    notification_type = forms.MultipleChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        widget=forms.SelectMultiple
    )

    class Meta:
        model = Notification
        fields = "__all__"

    def clean_notification_type(self):
        return self.cleaned_data["notification_type"]  # Convert to list before saving

