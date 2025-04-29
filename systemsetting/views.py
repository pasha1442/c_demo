from django.contrib.admin import site
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied


# Create your views here.
class HealthStatus(TemplateView):

    template_name = 'admin/health_status/health_status_dashboard.html'

    def get_context_dataq(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        if not self.request.user.has_perm('auth.can_view_health_check_view'):
            raise PermissionDenied  # Raise 403 error if the user lacks permission

        # Add additional context
        context['title'] = 'Health Status'
        return context

    def get_context_data(self, **kwargs):

        if not self.request.user.has_perm('auth.can_view_health_check_view'):
            raise PermissionDenied  # Raise 403 error if the user lacks permission

        return dict(
            site.each_context(self.request),
        )

