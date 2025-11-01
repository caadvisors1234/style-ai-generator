from django.apps import AppConfig


class ImagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'images'

    def ready(self):
        """
        アプリケーション起動時の処理
        シグナルをインポートして登録
        """
        import images.signals  # noqa
