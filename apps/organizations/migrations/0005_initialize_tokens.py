from django.db import migrations

def do_nothing(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0004_add_token_fields'),
    ]

    operations = [
        migrations.RunPython(do_nothing, do_nothing),
    ]
