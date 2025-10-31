from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from images.models import ImageConversion


class UserProfileModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='tester', email='tester@example.com', password='secret123'
        )

    def test_profile_auto_created(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_remaining_and_usage_percentage(self):
        profile = self.user.profile
        profile.monthly_limit = 10
        profile.monthly_used = 4
        profile.save()

        self.assertEqual(profile.remaining, 6)
        self.assertEqual(profile.usage_percentage, 40)

    def test_can_generate_and_increment_usage(self):
        profile = self.user.profile
        profile.monthly_limit = 3
        profile.monthly_used = 1
        profile.save()

        self.assertTrue(profile.can_generate(2))
        profile.increment_usage(2)
        profile.refresh_from_db()

        self.assertEqual(profile.monthly_used, 3)
        self.assertFalse(profile.can_generate(1))

    def test_cache_invalidated_on_save(self):
        profile = self.user.profile
        cache_key = f'usage_summary:{self.user.id}'
        cache_history_key = f'usage_history:{self.user.id}:6'

        cache.set(cache_key, {'dummy': True}, 60)
        cache.set(cache_history_key, [{'month': '2025-10'}], 60)

        profile.increment_usage(1)

        self.assertIsNone(cache.get(cache_key))
        self.assertIsNone(cache.get(cache_history_key))


class ResetMonthlyUsageCommandTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='command', email='command@example.com', password='secret123'
        )
        profile = self.user.profile
        profile.monthly_limit = 20
        profile.monthly_used = 5
        profile.save()

    def test_reset_monthly_usage_command(self):
        call_command('reset_monthly_usage')

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_used, 0)


class PermissionTests(TestCase):
    @override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
    def test_user_cannot_access_other_conversion(self):
        user1 = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='secret123'
        )
        user2 = get_user_model().objects.create_user(
            username='viewer', email='viewer@example.com', password='secret123'
        )

        conversion = ImageConversion.objects.create(
            user=user1,
            original_image_path='uploads/u1.jpg',
            original_image_name='u1.jpg',
            original_image_size=100,
            prompt='prompt',
            generation_count=1,
        )

        client = Client()
        client.login(username='viewer', password='secret123')

        response = client.get(f'/api/v1/convert/{conversion.id}/status/')
        self.assertEqual(response.status_code, 404)
