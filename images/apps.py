from django.apps import AppConfig
import pillow_heif


class ImagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'images'

    def ready(self):
        """
        アプリケーション起動時の処理
        シグナルをインポートして登録
        """
        # HEIF/HEICデコードをPillowに登録
        pillow_heif.register_heif_opener()
        import images.signals  # noqa
