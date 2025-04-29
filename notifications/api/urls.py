from django.urls import path

from notifications.api.views import NotificationGroupManager

urlpatterns = [
    path('notification/send-group-notification', NotificationGroupManager.as_view({'post':'send_group_notification'}), name='send_group_notification'),
]