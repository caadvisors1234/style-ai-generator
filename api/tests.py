import io
import os
import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from images.models import ImageConversion, GeneratedImage


class ConvertAPITestCase(TestCase):
    """
    画像変換APIの挙動を検証するテストケース
    """

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()

        self.user = User.objects.create_user(
            username='tester',
            email='tester@example.com',
            password='password123',
        )
        self.client.login(username='tester', password='password123')

        self.convert_url = reverse('api:convert_start')
        self.status_url = lambda pk: reverse('api:convert_status', kwargs={'conversion_id': pk})

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def _make_test_image(self, filename='sample.jpg'):
        """
        テスト用の画像ファイルを生成
        """
        buffer = io.BytesIO()
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        return SimpleUploadedFile(
            filename,
            buffer.read(),
            content_type='image/jpeg'
        )

    @patch('api.views.convert.process_image_conversion.delay')
    def test_convert_start_success(self, mock_delay):
        """
        画像変換開始APIが正常にジョブを登録できることを確認
        """
        upload = self._make_test_image()
        response = self.client.post(
            self.convert_url,
            {
                'prompt': '背景を白に変更',
                'generation_count': 2,
                'image': upload,
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(ImageConversion.objects.exists())
        conversion = ImageConversion.objects.get()

        self.assertEqual(conversion.user, self.user)
        self.assertEqual(conversion.prompt, '背景を白に変更')
        self.assertEqual(conversion.generation_count, 2)
        mock_delay.assert_called_once_with(conversion.id)

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_used, 2)

    @patch('api.views.convert.process_image_conversion.delay')
    def test_convert_start_rejects_when_limit_reached(self, mock_delay):
        """
        月次利用数が上限に達した場合は403が返る
        """
        profile = self.user.profile
        profile.monthly_used = profile.monthly_limit
        profile.save()

        upload = self._make_test_image()
        response = self.client.post(
            self.convert_url,
            {
                'prompt': 'テスト',
                'generation_count': 1,
                'image': upload,
            }
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')
        self.assertFalse(ImageConversion.objects.exists())
        mock_delay.assert_not_called()

    def test_convert_status_returns_generated_images(self):
        """
        変換が完了した場合に生成画像情報を返却することを確認
        """
        conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/user_1/original.jpg',
            original_image_name='original.jpg',
            original_image_size=1234,
            prompt='テストプロンプト',
            generation_count=1,
            status='completed',
            processing_time=Decimal('1.23'),
        )

        generated_path = os.path.join('generated', 'image.jpg')
        full_path = os.path.join(self.temp_media, generated_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as fh:
            fh.write(b'\xff\xd8\xff\xd9')

        GeneratedImage.objects.create(
            conversion=conversion,
            image_path=generated_path,
            image_name='image.jpg',
            image_size=2,
            expires_at=timezone.now() + timedelta(days=30),
        )

        response = self.client.get(self.status_url(conversion.id))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['conversion']['status'], 'completed')
        self.assertEqual(len(data['images']), 1)
        self.assertTrue(data['images'][0]['url'].startswith('/media/'))

    def test_convert_status_returns_404_for_other_user(self):
        """
        所有者以外のユーザーは変換情報を取得できない
        """
        other = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='password456',
        )
        conversion = ImageConversion.objects.create(
            user=other,
            original_image_path='uploads/user_2/original.jpg',
            original_image_name='original.jpg',
            original_image_size=1234,
            prompt='テスト',
            generation_count=1,
        )

        response = self.client.get(self.status_url(conversion.id))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'error')
