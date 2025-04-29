class CustomPagesPermissionManager():

    def get_backend_custom_page_permissions(self, request):
        if request.user.has_perm('can_access_backend_custom_pages') or request.user.is_superuser:
            return True
        return False
