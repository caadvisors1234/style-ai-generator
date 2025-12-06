from django.db import migrations, models


NEW_CHOICES = [
    ('composition', '構図'),
    ('hair_style', '髪型/スタイル'),
    ('hair_color', '髪色'),
    ('background', '背景'),
    ('texture', '質感'),
    ('tone', 'トーン'),
    ('other', 'その他'),
]


def forward_update_categories(apps, schema_editor):
    PromptPreset = apps.get_model('images', 'PromptPreset')
    mapping = {
        'style': 'hair_style',
        'enhancement': 'other',
        'professional': 'other',
    }
    for old, new in mapping.items():
        PromptPreset.objects.filter(category=old).update(category=new)


def backward_update_categories(apps, schema_editor):
    PromptPreset = apps.get_model('images', 'PromptPreset')
    reverse_mapping = {
        'composition': 'style',
        'hair_style': 'style',
        'hair_color': 'style',
        'background': 'background',
        'texture': 'enhancement',
        'tone': 'tone',
        'other': 'other',
    }
    for new, old in reverse_mapping.items():
        PromptPreset.objects.filter(category=new).update(category=old)


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0005_make_generatedimage_expires_optional'),
    ]

    operations = [
        migrations.RunPython(
            forward_update_categories,
            backward_update_categories,
        ),
        migrations.AlterField(
            model_name='promptpreset',
            name='category',
            field=models.CharField(
                choices=NEW_CHOICES,
                default='other',
                max_length=20,
                verbose_name='カテゴリ',
            ),
        ),
    ]

