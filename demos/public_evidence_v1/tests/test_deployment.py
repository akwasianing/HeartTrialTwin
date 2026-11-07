"""Offline guards for the exact public Pages folder; no hosting/API access."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "demos/public_evidence_v1/site"
ALLOWED = {"index.html", "style.css", "app.mjs", "evidence.mjs", "integrity.mjs", "evidence.json"}


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class PagesDeploymentTests(unittest.TestCase):
    def test_only_six_small_public_static_files_can_be_uploaded(self):
        paths = list(SITE.rglob("*"))
        self.assertEqual({p.relative_to(SITE).as_posix() for p in paths}, ALLOWED)
        self.assertTrue(all(p.is_file() and not p.is_symlink() for p in paths))
        self.assertLess(sum(p.stat().st_size for p in paths), 100_000)

    def test_landing_links_and_nested_asset_paths(self):
        parsed = Elements()
        parsed.feed((SITE / "index.html").read_text())
        elements = parsed.elements
        anchors = [attrs for tag, attrs in elements if tag == "a"]
        self.assertTrue(any(a.get("class") == "launch" and a.get("href") == "#evidence-demo" for a in anchors))
        github = [a for a in anchors if a.get("href") == "https://github.com/akwasianing/HeartTrialTwin"]
        self.assertGreaterEqual(len(github), 2)
        self.assertTrue(all("noopener" in a.get("rel", "") for a in github))
        ids = {attrs["id"] for _, attrs in elements if "id" in attrs}
        for anchor in anchors:
            if anchor.get("href", "").startswith("#"):
                self.assertIn(anchor["href"][1:], ids)
        for tag, attrs in elements:
            if tag in {"script", "link"}:
                asset = attrs.get("src") or attrs.get("href")
                self.assertIn(asset, ALLOWED)
                self.assertTrue((SITE / asset).is_file())

    def test_workflow_is_manual_main_only_and_uploads_only_site(self):
        workflow = (ROOT / ".github/workflows/public-evidence-pages.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("path: demos/public_evidence_v1/site\n", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertNotIn("enablement:", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("build_site.py --check", workflow)


if __name__ == "__main__":
    unittest.main()
