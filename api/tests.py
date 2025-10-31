import io
import os
import json
import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from images.models import ImageConversion, GeneratedImage


class AuthAPITestCase(TestCase):
    """認証APIのユニットテスト"""

    def setUp(self):
        self.password = 'password123'
        self.user = User.objects.create_user(
            username='tester',
            email='tester@example.com',
            password=self.password,
        )
        self.csrf_client = Client(enforce_csrf_checks=True)

        self.login_url = reverse('api:login')
        self.logout_url = reverse('api:logout')
        self.me_url = reverse('api:me')
        self.csrf_url = reverse('api:csrf_token')

    def _get_csrf_token(self):
        response = self.csrf_client.get(self.csrf_url)
        self.assertEqual(response.status_code, 200)
        return response.cookies['csrftoken'].value

    def test_login_requires_csrf(self):
        response = self.csrf_client.post(
            self.login_url,
            data=json.dumps({'username': self.user.username, 'password': self.password}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_login_success_with_csrf(self):
        token = self._get_csrf_token()
        response = self.csrf_client.post(
            self.login_url,
            data=json.dumps({'username': self.user.username, 'password': self.password}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertIn('_auth_user_id', self.csrf_client.session)

    def test_login_failure_with_invalid_credentials(self):
        token = self._get_csrf_token()
        response = self.csrf_client.post(
            self.login_url,
            data=json.dumps({'username': self.user.username, 'password': 'wrong'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 'error')

    def test_logout_clears_session(self):
        token = self._get_csrf_token()
        login_response = self.csrf_client.post(
            self.login_url,
            data=json.dumps({'username': self.user.username, 'password': self.password}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('_auth_user_id', self.csrf_client.session)

        logout_token = login_response.cookies.get('csrftoken')
        logout_token_value = logout_token.value if logout_token else token

        response = self.csrf_client.post(
            self.logout_url,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=logout_token_value,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.csrf_client.session)

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'AUTHENTICATION_REQUIRED')

    def test_me_returns_profile_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['user']['username'], self.user.username)


class UsageAPITestCase(TestCase):
    """利用状況APIのユニットテスト"""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='usage',
            email='usage@example.com',
            password='password123',
        )
        self.client.force_login(self.user)
        self.summary_url = reverse('api:usage_summary')
        self.history_url = reverse('api:usage_history')

    def tearDown(self):
        cache.clear()

    def test_usage_summary_returns_profile_data(self):
        profile = self.user.profile
        profile.monthly_limit = 200
        profile.monthly_used = 50
        profile.save()

        response = self.client.get(self.summary_url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        data = payload['data']
        self.assertEqual(data['monthly_limit'], 200)
        self.assertEqual(data['monthly_used'], 50)
        self.assertEqual(data['remaining'], profile.remaining)
        self.assertAlmostEqual(data['usage_percentage'], 25.0)

    def test_usage_summary_requires_authentication(self):
        anonymous_client = Client()
        response = anonymous_client.get(self.summary_url)
        self.assertEqual(response.status_code, 401)

    def test_usage_history_returns_monthly_stats(self):
        now = timezone.now()
        profile = self.user.profile
        profile.monthly_limit = 150
        profile.save()

        current_conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/user_1/current.jpg',
            original_image_name='current.jpg',
            original_image_size=1234,
            prompt='current',
            generation_count=2,
            status='completed',
        )
        ImageConversion.objects.filter(pk=current_conversion.pk).update(created_at=now)

        previous_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        past_conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/user_1/past.jpg',
            original_image_name='past.jpg',
            original_image_size=1234,
            prompt='past',
            generation_count=3,
            status='completed',
        )
        ImageConversion.objects.filter(pk=past_conversion.pk).update(created_at=previous_month)

        response = self.client.get(f"{self.history_url}?months=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        history = payload['data']['history']
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['month'], now.strftime('%Y-%m'))
        self.assertEqual(history[0]['used'], 2)
        self.assertEqual(history[0]['limit'], 150)
        self.assertEqual(history[1]['used'], 3)

    def test_usage_history_validates_months_parameter(self):
        response = self.client.get(f"{self.history_url}?months=abc")
        self.assertEqual(response.status_code, 400)

    def test_usage_history_requires_authentication(self):
        anonymous_client = Client()
        response = anonymous_client.get(self.history_url)
        self.assertEqual(response.status_code, 401)


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
        mock_delay.return_value = SimpleNamespace(id='task-123')

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
