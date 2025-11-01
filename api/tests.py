import io
import json
import os
import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from images.models import ImageConversion, GeneratedImage
from images.services.brightness import BrightnessAdjustmentService
from images.services.upload import ImageUploadService


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
        now = timezone.localtime(timezone.now())
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
            aspect_ratio='4:3',
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
            aspect_ratio='4:3',
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
                'aspect_ratio': '16:9',
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
        self.assertEqual(conversion.aspect_ratio, '16:9')
        self.assertEqual(data['aspect_ratio'], '16:9')
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
            aspect_ratio='4:3',
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
        self.assertEqual(data['conversion']['aspect_ratio'], '4:3')

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
            aspect_ratio='4:3',
        )

        response = self.client.get(self.status_url(conversion.id))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'error')


class GalleryAPITestCase(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media, ALLOWED_HOSTS=['testserver', 'localhost'])
        self.override.enable()

        self.user = User.objects.create_user(
            username='gallery_user', email='gallery@example.com', password='password123'
        )
        self.client.login(username='gallery_user', password='password123')

        self.conversion = ImageConversion.objects.create(
            user=self.user,
            original_image_path='uploads/user_1/original.jpg',
            original_image_name='original.jpg',
            original_image_size=1024,
            prompt='ギャラリーテスト',
            generation_count=1,
            aspect_ratio='4:3',
            status='completed',
        )

        self.generated_path = os.path.join('generated', 'user_1', 'generated.jpg')
        full_generated_path = os.path.join(self.temp_media, self.generated_path)
        os.makedirs(os.path.dirname(full_generated_path), exist_ok=True)
        with Image.new('RGB', (64, 64), color=(200, 200, 200)) as img:
            img.save(full_generated_path, format='JPEG')

        self.generated_image = GeneratedImage.objects.create(
            conversion=self.conversion,
            image_path=self.generated_path,
            image_name='generated.jpg',
            image_size=4,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_gallery_list_returns_conversions(self):
        response = self.client.get('/api/v1/gallery/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['pagination']['total_count'], 1)
        self.assertEqual(payload['conversions'][0]['id'], self.conversion.id)
        self.assertEqual(payload['conversions'][0]['aspect_ratio'], '4:3')

    def test_gallery_detail_and_image_detail(self):
        response = self.client.get(f'/api/v1/gallery/{self.conversion.id}/')
        self.assertEqual(response.status_code, 200)
        detail = response.json()['conversion']
        self.assertEqual(detail['prompt'], 'ギャラリーテスト')
        self.assertEqual(detail['aspect_ratio'], '4:3')

        image_response = self.client.get(f'/api/v1/gallery/images/{self.generated_image.id}/')
        self.assertEqual(image_response.status_code, 200)
        self.assertTrue(image_response.json()['image']['image_url'].endswith('generated.jpg'))

    def test_brightness_adjust_and_download(self):
        original_path = self.generated_image.image_path

        adjust_response = self.client.patch(
            f'/api/v1/gallery/images/{self.generated_image.id}/brightness/',
            data=json.dumps({'adjustment': 10}),
            content_type='application/json'
        )
        self.assertEqual(adjust_response.status_code, 200)
        adjust_payload = adjust_response.json()
        self.assertEqual(adjust_payload['status'], 'success')
        self.assertEqual(adjust_payload['image']['brightness_adjustment'], 10)
        self.assertIn('_brightness_+10', adjust_payload['image']['image_url'])

        self.generated_image.refresh_from_db()
        adjusted_path = self.generated_image.image_path
        self.assertIn('_brightness_+10', adjusted_path)
        self.assertEqual(self.generated_image.brightness_adjustment, 10)

        second_adjust = self.client.patch(
            f'/api/v1/gallery/images/{self.generated_image.id}/brightness/',
            data=json.dumps({'adjustment': 20}),
            content_type='application/json'
        )
        self.assertEqual(second_adjust.status_code, 200)
        second_payload = second_adjust.json()
        self.assertEqual(second_payload['image']['brightness_adjustment'], 20)
        self.assertIn('_brightness_+20', second_payload['image']['image_url'])

        self.generated_image.refresh_from_db()
        self.assertEqual(self.generated_image.brightness_adjustment, 20)
        self.assertIn('_brightness_+20', self.generated_image.image_path)

        reset_response = self.client.patch(
            f'/api/v1/gallery/images/{self.generated_image.id}/brightness/',
            data=json.dumps({'adjustment': 0}),
            content_type='application/json'
        )
        self.assertEqual(reset_response.status_code, 200)
        reset_payload = reset_response.json()
        self.assertEqual(reset_payload['status'], 'success')
        self.assertEqual(reset_payload['image']['brightness_adjustment'], 0)
        self.assertEqual(reset_payload['image']['message'], '輝度をリセットしました')
        self.assertNotIn('_brightness_', reset_payload['image']['image_url'])

        self.generated_image.refresh_from_db()
        self.assertEqual(self.generated_image.image_path, original_path)

        download_response = self.client.get(f'/api/v1/gallery/images/{self.generated_image.id}/download/')
        self.assertEqual(download_response.status_code, 200)
        self.assertIn('attachment', download_response['Content-Disposition'])

    def test_delete_image_and_conversion(self):
        delete_image_resp = self.client.delete(f'/api/v1/gallery/images/{self.generated_image.id}/delete/')
        self.assertEqual(delete_image_resp.status_code, 200)
        self.assertEqual(delete_image_resp.json()['status'], 'success')

        delete_conv_resp = self.client.delete(f'/api/v1/gallery/{self.conversion.id}/delete/')
        self.assertEqual(delete_conv_resp.status_code, 200)
        self.assertFalse(ImageConversion.objects.filter(id=self.conversion.id, is_deleted=False).exists())

    def test_gallery_permission_denied_for_other_user(self):
        other = User.objects.create_user('otheruser', 'other@example.com', 'pass12345')
        other_client = Client()
        other_client.login(username='otheruser', password='pass12345')

        response = other_client.get(f'/api/v1/gallery/{self.conversion.id}/')
        self.assertEqual(response.status_code, 404)


class IntegrationFlowTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media, ALLOWED_HOSTS=['testserver', 'localhost'])
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    @patch('api.views.convert.process_image_conversion.delay')
    @patch('images.tasks.GeminiImageAPIService.save_generated_image')
    @patch('images.tasks.GeminiImageAPIService.generate_images_from_reference')
    @patch('images.tasks.GeminiImageAPIService.load_image', return_value=b'input-bytes')
    def test_end_to_end_flow(self, mock_load, mock_generate, mock_save, mock_delay):
        user = User.objects.create_user('flowuser', 'flow@example.com', 'password123')
        client = Client()
        client.login(username='flowuser', password='password123')

        mock_generate.return_value = [{
            'image_data': b'\xff\xd8\xff\xd9',
            'description': 'generated',
            'generation_number': 1,
            'prompt_used': 'prompt',
            'aspect_ratio': '3:4'
        }]

        def save_generated(image_data, output_dir, filename):
            relative = os.path.join(output_dir, filename)
            full_path = os.path.join(self.temp_media, relative)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as fh:
                fh.write(image_data)
            return relative

        mock_save.side_effect = save_generated

        from images.tasks import process_image_conversion

        def run_task(conv_id):
            process_image_conversion.apply(args=(conv_id,), throw=True)
            return SimpleNamespace(id='task-sync')

        mock_delay.side_effect = run_task

        upload_path = os.path.join(self.temp_media, 'upload.jpg')
        with Image.new('RGB', (64, 64), color=(100, 100, 200)) as img:
            img.save(upload_path, format='JPEG')

        with open(upload_path, 'rb') as f:
            response = client.post(
                '/api/v1/convert/',
                {
                    'prompt': 'プロフェッショナルに',
                    'generation_count': 1,
                    'aspect_ratio': '3:4',
                    'image': f,
                }
            )

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        conversion_id = response_payload['conversion_id']
        self.assertEqual(response_payload['aspect_ratio'], '3:4')

        status_response = client.get(f'/api/v1/convert/{conversion_id}/status/')
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload['conversion']['status'], 'completed')
        self.assertEqual(status_payload['conversion']['aspect_ratio'], '3:4')

        gallery_response = client.get('/api/v1/gallery/')
        self.assertEqual(gallery_response.status_code, 200)
        gallery_payload = gallery_response.json()
        self.assertGreaterEqual(gallery_payload['pagination']['total_count'], 1)
        self.assertEqual(gallery_payload['conversions'][0]['aspect_ratio'], '3:4')


class GalleryPerformanceTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media, ALLOWED_HOSTS=['testserver', 'localhost'])
        self.override.enable()

        self.user = User.objects.create_user('perf', 'perf@example.com', 'password123')
        self.client.login(username='perf', password='password123')

        for index in range(3):
            conv = ImageConversion.objects.create(
                user=self.user,
                original_image_path=f'uploads/u_{index}.jpg',
                original_image_name=f'u_{index}.jpg',
                original_image_size=1000,
                prompt=f'prompt {index}',
                generation_count=1,
                aspect_ratio='4:3',
                status='completed'
            )

            image_rel = os.path.join('generated', f'user_{self.user.id}', f'generated_{index}.jpg')
            full_path = os.path.join(self.temp_media, image_rel)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with Image.new('RGB', (32, 32), color=(index * 40, index * 40, 200)) as img:
                img.save(full_path, format='JPEG')

            GeneratedImage.objects.create(
                conversion=conv,
                image_path=image_rel,
                image_name=f'generated_{index}.jpg',
                image_size=1024,
            )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_gallery_list_queries(self):
        with self.assertNumQueries(5):
            response = self.client.get('/api/v1/gallery/?per_page=12')
            self.assertEqual(response.status_code, 200)
