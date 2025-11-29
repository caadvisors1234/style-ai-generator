import io
import os
import shutil
import tempfile

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from images.services.upload import ImageUploadService, UploadValidationError
from images.services.brightness import BrightnessAdjustmentService, BrightnessAdjustmentError
from images.services.gemini_image_api import GeminiImageAPIService, GeminiImageAPIError
from images.models import ImageConversion, GeneratedImage


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


class ImageModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='image_tester', email='img@example.com', password='secret123'
        )

    def test_mark_status_helpers(self):
        conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/path.jpg',
            original_image_name='path.jpg',
            original_image_size=1234,
            prompt='test',
            generation_count=1,
            aspect_ratio='4:3',
        )

        self.assertEqual(conversion.job_id, f'job_{conversion.id}')

        conversion.mark_as_processing()
        conversion.refresh_from_db()
        self.assertEqual(conversion.status, 'processing')

        conversion.mark_as_completed(processing_time=1.23)
        conversion.refresh_from_db()
        self.assertEqual(conversion.status, 'completed')

        conversion.mark_as_failed('error')
        conversion.refresh_from_db()
        self.assertEqual(conversion.status, 'failed')
        self.assertEqual(conversion.error_message, 'error')

    def test_generated_image_auto_expires(self):
        conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/original.jpg',
            original_image_name='original.jpg',
            original_image_size=100,
            prompt='prompt',
            generation_count=1,
            aspect_ratio='4:3',
        )

        image = GeneratedImage.objects.create(
            conversion=conversion,
            image_path='generated/user_1/test.jpg',
            image_name='test.jpg',
            image_size=200,
        )

        self.assertIsNone(image.expires_at)
        self.assertFalse(image.is_expired)


class DeleteExpiredImagesCommandTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()

        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='cleanup', email='cleanup@example.com', password='secret123'
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_delete_expired_images_command_force(self):
        conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/original.jpg',
            original_image_name='original.jpg',
            original_image_size=100,
            prompt='prompt',
            generation_count=1,
            aspect_ratio='4:3',
        )

        expired_path = os.path.join('generated', 'expired.jpg')
        full_path = os.path.join(self.temp_media, expired_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with Image.new('RGB', (32, 32), color=(200, 200, 200)) as img:
            img.save(full_path, format='JPEG')

        GeneratedImage.objects.create(
            conversion=conversion,
            image_path=expired_path,
            image_name='expired.jpg',
            image_size=123,
            expires_at=timezone.now() - timedelta(days=1),
            is_deleted=False,
        )

        call_command('delete_expired_images', '--force')

        self.assertFalse(os.path.exists(full_path))
        self.assertFalse(GeneratedImage.objects.filter(image_name='expired.jpg').exists())


class GeminiImageServiceTests(TestCase):
    @patch('images.services.gemini_image_api.GeminiImageAPIService.load_image', return_value=b'input-bytes')
    @patch('images.services.gemini_image_api.GeminiImageAPIService.initialize_client')
    def test_generate_images_success(self, mock_client_factory, mock_load):
        mock_response = SimpleNamespace(parts=[
            SimpleNamespace(text='desc', inline_data=SimpleNamespace(data=b'\xff\xd8\xff\xd9'))
        ])
        mock_client_factory.return_value = SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **kwargs: mock_response)
        )

        results = GeminiImageAPIService.generate_images_from_reference('path.jpg', 'prompt', generation_count=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['description'], 'desc')

    @patch('images.services.gemini_image_api.GeminiImageAPIService.load_image', return_value=b'input-bytes')
    @patch('images.services.gemini_image_api.GeminiImageAPIService.initialize_client')
    def test_generate_images_raises_on_failure(self, mock_client_factory, mock_load):
        def failing_generate_content(**kwargs):
            raise RuntimeError('API failure')

        mock_client_factory.return_value = SimpleNamespace(
            models=SimpleNamespace(generate_content=failing_generate_content)
        )

        with self.assertRaises(GeminiImageAPIError):
            GeminiImageAPIService.generate_images_from_reference('path.jpg', 'prompt', generation_count=1)
