from django.db import migrations
from basics.utils import UUID
from django.db import migrations, models

def populate_session_id(apps, schema_editor):
    """Populate session_id field with unique UUIDs for existing records"""
    DataEnrichment = apps.get_model('data_processing', 'DataEnrichment')
    for enrichment in DataEnrichment.objects.all():
        enrichment.session_id = UUID.get_uuid()
        enrichment.save()

class Migration(migrations.Migration):
    dependencies = [
        ('data_processing', '0009_alter_dataenrichment_llm_model'),  # Replace with your previous migration
    ]

    operations = [
        # First add the field without unique=True
        migrations.AddField(
            model_name='dataenrichment',
            name='session_id',
            field=models.CharField(
                max_length=36,
                null=True,  # Allow null initially
                help_text='Unique session identifier for this enrichment request'
            ),
        ),
        # Run the data migration
        migrations.RunPython(
            populate_session_id,
            reverse_code=migrations.RunPython.noop
        ),
        # Now add the unique constraint and non-null
        migrations.AlterField(
            model_name='dataenrichment',
            name='session_id',
            field=models.CharField(
                max_length=36,
                unique=True,
                default=UUID.get_uuid,
                editable=False,
                help_text='Unique session identifier for this enrichment request'
            ),
        ),
    ]