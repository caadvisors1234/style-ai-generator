from django.db import migrations, models
from django.db.models import F
from django.core.validators import MinValueValidator


def set_usage_consumed(apps, schema_editor):
    ImageConversion = apps.get_model('images', 'ImageConversion')
    ImageConversion.objects.all().update(usage_consumed=F('generation_count'))


def reset_usage_consumed(apps, schema_editor):
    ImageConversion = apps.get_model('images', 'ImageConversion')
    ImageConversion.objects.all().update(usage_consumed=0)


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0007_add_preset_fields_to_imageconversion'),
    ]

    operations = [
        migrations.AddField(
            model_name='imageconversion',
            name='model_name',
            field=models.CharField(default='gemini-2.5-flash-image', help_text='画像生成に使用したモデル', max_length=100, verbose_name='モデル名'),
        ),
        migrations.AddField(
            model_name='imageconversion',
            name='usage_consumed',
            field=models.IntegerField(default=0, help_text='この変換で消費したクレジット数', validators=[MinValueValidator(0)], verbose_name='消費クレジット'),
        ),
        migrations.RunPython(set_usage_consumed, reset_usage_consumed),
    ]
