import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = REPO_ROOT / "ui"


class UiPrivacyTests(unittest.TestCase):
    def test_index_html_has_no_google_font_links(self):
        html = (UI_DIR / "index.html").read_text(encoding="utf-8").lower()
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)

    def test_styles_css_has_no_external_import_urls(self):
        css = (UI_DIR / "styles.css").read_text(encoding="utf-8").lower()
        self.assertNotRegex(css, r"@import\s+url\((['\"])?https?://")


if __name__ == "__main__":
    unittest.main()
