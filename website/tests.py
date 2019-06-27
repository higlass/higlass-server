import django.test as dt

class SiteTests(dt.TestCase):
    def test_link_url(self):
        ret = self.client.get('/site/link')
        print("ret:", ret.content)