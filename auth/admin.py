from django.contrib.auth.models import Group
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext, gettext_lazy as _

from auth.models import OTP
from basics.admin import BaseModelAdmin

User = get_user_model()


@admin.register(User)
class UserAdmin(UserAdmin):
    model = User
    # change_form_template = 'user/change_form.html'
    # change_list_template = 'user/change_list.html'
    # inlines = [UserVerificationOTPInline]
    # add_form = UserCreationForm
    # form = UserChangeForm
    list_display_links = ('id', 'username', 'name', 'mobile_number', 'email', 'current_company', 'is_superuser', 'is_staff', 'is_active', 'date_joined')
    list_display = ('id', 'username', 'name', 'mobile_number', 'email', 'current_company', 'is_superuser', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_superuser', 'is_staff', 'is_active')
    readonly_fields = ('date_joined', 'last_login')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': (
        'username', 'password', 'mobile_number', 'current_company', 'available_companies', 'user_notification_group')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email' )}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'is_staff', 'is_active')}
         ),
    )

    def name(self, obj):
        return f'{obj.first_name} {obj.last_name}'

    # def action_buttons(self, obj):
    #     return format_html(
    #         f'<button id="force_logout_user" type="button" class="force_logout_user btn btn-sm btn-outline-danger" '
    #         f'type="button" data-id="{obj.id}" data-username="{obj.username}" style="min-width:100px;"> Force Logout '
    #         f'</button> '
    #     )


@admin.register(OTP)
class UserOTPAdmin(BaseModelAdmin):
    list_display_links = ('id', 'company', 'mobile_number', 'email_id', 'notification_type', 'request_id', 'otp', 'is_otp_used', 'access_attempts', 'is_blacklisted', 'created_at', 'expired_at')
    list_display = ('id', 'company', 'mobile_number', 'email_id', 'notification_type', 'request_id', 'otp', 'is_otp_used', 'access_attempts', 'is_blacklisted', 'created_at', 'expired_at')
    list_filter = ('mobile_number', 'email_id', 'notification_type',)
    readonly_fields = ('created_at', 'expired_at')
    search_fields = ('notification_type',)
    ordering = ('id',)
    fields = ('id', 'company', 'mobile_number', 'email_id', 'notification_type', 'request_id', 'otp', 'is_otp_used', 'access_attempts', 'is_blacklisted', 'created_at', 'expired_at')
