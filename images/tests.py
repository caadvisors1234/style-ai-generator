import io
import os
import shutil
import tempfile

from PIL import Image
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

from images.services.upload import ImageUploadService, UploadValidationError
from images.services.brightness import BrightnessAdjustmentService, BrightnessAdjustmentError


class ImageUploadServiceTests(TestCase):
    """
    ImageUploadService の振る舞いを検証するテスト
    """

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def _make_image_file(self, name='upload.jpg'):
        buffer = io.BytesIO()
        image = Image.new('RGB', (128, 128), color=(100, 150, 200))
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')

    def test_process_uploads_saves_file_and_thumbnail(self):
        """
        正常系: ファイルとサムネイルが保存され、相対パスが返る
        """
        service = ImageUploadService(user_id=1)
        result = service.process_uploads([self._make_image_file()])

        self.assertEqual(len(result), 1)
        stored = result[0]
        self.assertTrue(stored['file_path'].startswith('uploads/1/'))
        self.assertIn('thumbnail_path', stored)

        file_path = os.path.join(self.temp_media, stored['file_path'])
        thumb_path = os.path.join(self.temp_media, stored['thumbnail_path'])
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(os.path.exists(thumb_path))

    def test_process_uploads_raises_on_invalid_extension(self):
        """
        不正な拡張子の場合は UploadValidationError が発生する
        """
        service = ImageUploadService(user_id=1)
        invalid_file = SimpleUploadedFile(
            'malicious.txt',
            b'invalid content',
            content_type='text/plain'
        )

        with self.assertRaises(UploadValidationError):
            service.process_uploads([invalid_file])


class BrightnessAdjustmentServiceTests(TestCase):
    """
    BrightnessAdjustmentService の検証
    """

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()
        self.image_path = os.path.join('generated', 'source.jpg')
        full_path = os.path.join(self.temp_media, self.image_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with Image.new('RGB', (64, 64), color=(120, 120, 120)) as img:
            img.save(full_path, format='JPEG')

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_adjust_brightness_creates_adjusted_file(self):
        """
        輝度調整後のファイルが作成され、パスが更新される
        """
        adjusted_path = BrightnessAdjustmentService.adjust_brightness(self.image_path, 10)
        self.assertNotEqual(adjusted_path, self.image_path)

        full_adjusted_path = os.path.join(self.temp_media, adjusted_path)
        self.assertTrue(os.path.exists(full_adjusted_path))

    def test_adjust_brightness_rejects_invalid_value(self):
        """
        許容範囲外の調整値は BrightnessAdjustmentError を送出する
        """
        with self.assertRaises(BrightnessAdjustmentError):
            BrightnessAdjustmentService.adjust_brightness(self.image_path, 100)
