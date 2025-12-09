from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("images", "0006_update_prompt_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="imageconversion",
            name="preset_id",
            field=models.IntegerField(
                blank=True,
                help_text="選択されたプリセットのID",
                null=True,
                verbose_name="プリセットID",
            ),
        ),
        migrations.AddField(
            model_name="imageconversion",
            name="preset_name",
            field=models.CharField(
                blank=True,
                help_text="選択されたプリセットの表示名（日本語）",
                max_length=150,
                null=True,
                verbose_name="プリセット表示名",
            ),
        ),
    ]
