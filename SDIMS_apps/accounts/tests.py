from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin1', password='pass', role='admin',
            phone='9800000000', address='KTM', must_change_password=False
        )

    def test_admin_login_redirects_to_admin_dashboard(self):
        self.client.login(username='admin1', password='pass')
        resp = self.client.get('/', follow=True)
        self.assertRedirects(resp, '/admin-dashboard/')
