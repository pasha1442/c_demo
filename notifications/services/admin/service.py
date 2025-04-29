from itertools import zip_longest

from basics.utils import DateTimeConversion
from notifications.models import NotificationTemplates


class NotificationAdminServices():

    def get_notification_icon(self, notification_type):
        nitification_icon = ""
        if notification_type == NotificationTemplates.NOTIFICATION_TYPE_WHATSAPP:
            nitification_icon = '<i class="fab fa-whatsapp"></i>'
        elif notification_type == NotificationTemplates.NOTIFICATION_TYPE_SMS:
            nitification_icon = '<i class="fas fa-sms"></i>'
        elif notification_type == NotificationTemplates.NOTIFICATION_TYPE_EMAIL:
            nitification_icon = '<i class="fas fa-envelope"></i>'

        return nitification_icon

    def get_recipients_list_html_template(self, recipients_list, notification_type):

        # Generate HTML table
        # TABLE FOR SMS LIST
        nitification_icon = self.get_notification_icon(notification_type)
        notification_type_dict = dict(NotificationTemplates.NOTIFICATION_TYPE)
        notification_type = notification_type_dict.get(notification_type)

        table_html = ""
        if recipients_list:
            table_html = f"""
                    <table class="table table-bordered" style="">
                        <thead>
                            <tr colspan=2>
                                <th style="padding: 5px;">{nitification_icon} {notification_type}</th>
                            </tr>
                        </thead>
                        <tbody>
                    """
            cnt = 0
            for value in recipients_list:
                cnt += 1
                table_html += f"""
                    <tr>
                        <td style="padding: 5px;">{cnt}</td>
                        <td style="padding: 5px;">{value or '-'}</td>
                    </tr>
                """

            table_html += "</tbody></table>"
            table_html += "<br>"

        return table_html

    def get_recipients_status_html_template(self, obj):

        table_html = ""
        recipients_status = obj.recipients_status
        for channel, recipients in recipients_status.items():
            table_html += self.generate_recipients_status_html_by_json(recipients, channel)

        return table_html

    def generate_recipients_status_html_by_json(self, data_dict={}, channel=None):
        notification_type_dict = dict(NotificationTemplates.NOTIFICATION_TYPE)
        nitification_icon = self.get_notification_icon(channel)
        channel_name = notification_type_dict.get(channel)
        table_html = f"""
                        <table class="table table-bordered" style="">
                            <thead>
                                <tr style="">
                                    <th colspan=5 style="padding: 10px;">{nitification_icon} {channel_name}</th>
                                </tr>
                                <tr>
                                    <th style="padding: 10px; text-align: left; min-width:30px;">SN</th>
                                    <th style="padding: 10px; text-align: left;">Recipient</th>
                                    <th style="padding: 10px; text-align: left;">Status</th>
                                    <th style="padding: 10px; text-align: left;">Sent At</th>
                                    <th style="padding: 10px; text-align: left;">Error</th>
                                </tr>
                            </thead>
                        <tbody>
                    """

        cnt = 0
        for recipient, details in data_dict.items():
            cnt += 1
            sent_at = details.get("sent_at")
            status = details.get("status")

            if status == 'success':
                status_icon = f'<i class ="fas fa-check-circle" style="color:#28a745"> </i>'
            elif status == 'error' or status == 'failed':
                status_icon = f'<i class="fas fa-times-circle" style="color:#dc3545"></i>'
            else:
                status_icon = f'<i class="fas fa-pause-circle" style="color:#ffc107"></i>'

            if sent_at:
                sent_at = DateTimeConversion.to_string(DateTimeConversion.str_to_datetime(sent_at), "%Y-%m-%d %I:%M:%S %p")
            table_html += f"""
                            <tr border="1">
                                <td style="padding: 10px; width:5%">{cnt}</td>
                                <td style="padding: 10px; width:15%;">{recipient or '-'}</td>
                                <td style="padding: 10px; width:20%;" data-toggle="tooltip" title="{status}">{status_icon} {status}</td>
                                <td style="padding: 10px; width:30%;">{sent_at or '-'}</td>
                                <td style="padding: 10px; width:30%;">{details.get("error", "-")}</td>
                            </tr>
                            """

        table_html += "</tbody></table>"
        table_html += "<br>"

        return table_html

