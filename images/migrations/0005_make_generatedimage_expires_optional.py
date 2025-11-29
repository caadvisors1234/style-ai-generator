from django.db import migrations, models


def clear_expires_at(apps, schema_editor):
    GeneratedImage = apps.get_model('images', 'GeneratedImage')
    GeneratedImage.objects.filter(expires_at__isnull=False).update(expires_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0004_update_aspect_ratio_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='generatedimage',
            name='expires_at',
            field=models.DateTimeField(
                blank=True,
                help_text='保持期限。未設定の場合は自動削除しません',
                null=True,
                verbose_name='削除予定日時',
            ),
        ),
        migrations.RunPython(clear_expires_at, migrations.RunPython.noop),
    ]
