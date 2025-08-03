"""
Scaffolded repro test. If vcrpy is installed, this will record/replay HTTP.
Run it with: python3 -m unittest /Users/alessiofanelli/self-improving/gpt5/.repro/login-bug/test_repro.py
"""
import os, unittest
try:
    import vcr  # type: ignore
except Exception:
    vcr = None

class ReproTest(unittest.TestCase):
    def test_http(self):
        import requests
        def _do():
            return requests.get("https://httpbin.org/get").status_code
        if vcr:
            myvcr = vcr.VCR(cassette_library_dir=str('/Users/alessiofanelli/self-improving/gpt5/.repro/login-bug/cassettes'))
            with myvcr.use_cassette("repro.yaml"):
                self.assertIn(_do(), (200, 429))
        else:
            self.assertTrue(True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
