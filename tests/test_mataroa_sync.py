import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mataroa_sync as sync  # noqa: E402


class MarkdownTests(unittest.TestCase):
    def test_round_trip_frontmatter_and_body(self):
        metadata = {
            "title": '中文标题: "引号"',
            "slug": "test-post",
            "published_at": "2026-10-28",
        }
        body = "## 正文\n\n你好，世界。\n"
        rendered = sync.render_markdown(metadata, body)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "post.md"
            path.write_text(rendered, encoding="utf-8")
            parsed_metadata, parsed_body = sync.parse_markdown_file(path)
        self.assertEqual(parsed_metadata, metadata)
        self.assertEqual(parsed_body, body)

    def test_draft_parser_accepts_plain_title(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.md"
            path.write_text("---\ntitle: A title: with colon\npublished_at: 2026-10-28\n---\n\nBody here.\n", encoding="utf-8")
            metadata, body = sync.parse_markdown_file(path)
        self.assertEqual(metadata["title"], "A title: with colon")
        self.assertEqual(body, "Body here.\n")

    def test_slug_filename_encodes_path_separator(self):
        filename = sync.filename_for_slug("../evil/slug")
        self.assertNotIn("/", filename)
        self.assertNotIn("\\", filename)
        self.assertTrue(filename.endswith(".md"))


class BackupTests(unittest.TestCase):
    def test_backup_keeps_old_archive_files_and_writes_live_post(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "posts").mkdir()
            old_file = root / "posts" / "previously-deleted.md"
            old_file.write_text("old archive stays", encoding="utf-8")
            with patch.object(sync, "ROOT", root), patch.object(sync, "list_posts", return_value=[
                {
                    "slug": "hello-world",
                    "title": "Hello 世界",
                    "body": "本文内容。",
                    "published_at": "2026-10-28",
                    "url": "https://example.mataroa.blog/blog/hello-world/",
                }
            ]):
                sync.backup_posts()
            self.assertEqual(old_file.read_text(encoding="utf-8"), "old archive stays")
            new_file = root / "posts" / "hello-world.md"
            self.assertTrue(new_file.exists())
            saved = new_file.read_text(encoding="utf-8")
            self.assertIn("Hello 世界", saved)
            self.assertIn("本文内容。", saved)


class PublishTests(unittest.TestCase):
    def test_prepare_adds_stable_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft_dir = root / "drafts"
            draft_dir.mkdir()
            (root / "published").mkdir()
            draft = draft_dir / "note.md"
            draft.write_text("---\ntitle: Test post\n---\n\nBody.\n", encoding="utf-8")
            with patch.object(sync, "ROOT", root):
                sync.prepare_publish("drafts/note.md")
                metadata, body = sync.parse_markdown_file(draft)
                self.assertRegex(metadata["mataroa_bridge_id"], r"^[0-9a-f]{32}$")
                self.assertEqual(body, "Body.\n")

    def test_publish_posts_new_article_and_moves_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "drafts").mkdir()
            (root / "published").mkdir()
            draft = root / "drafts" / "note.md"
            draft.write_text(
                "---\ntitle: Test post\npublished_at: 2026-10-28\nmataroa_bridge_id: 0123456789abcdef0123456789abcdef\n---\n\nBody.\n",
                encoding="utf-8",
            )
            get_response = {"ok": True, "post_list": []}
            post_response = {"ok": True, "slug": "test-post", "url": "https://example.mataroa.blog/blog/test-post/"}
            with patch.object(sync, "ROOT", root), patch.object(sync, "api_request", side_effect=[get_response, post_response]) as api:
                sync.publish_new_post("drafts/note.md")
            self.assertFalse(draft.exists())
            published = root / "published" / "note.md"
            self.assertTrue(published.exists())
            saved = published.read_text(encoding="utf-8")
            self.assertIn("test-post", saved)
            self.assertIn("mataroa-bridge-id: 0123456789abcdef0123456789abcdef", saved)
            api.assert_any_call("POST", "/posts/", {
                "title": "Test post",
                "body": "Body.\n\n<!-- mataroa-bridge-id: 0123456789abcdef0123456789abcdef -->\n",
                "published_at": "2026-10-28",
            })

    def test_existing_marker_prevents_duplicate_post(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "drafts").mkdir()
            (root / "published").mkdir()
            draft = root / "drafts" / "note.md"
            bridge_id = "0123456789abcdef0123456789abcdef"
            draft.write_text(
                f"---\ntitle: Test post\npublished_at: 2026-10-28\nmataroa_bridge_id: {bridge_id}\n---\n\nBody.\n",
                encoding="utf-8",
            )
            existing = {
                "slug": "test-post",
                "title": "Test post",
                "published_at": "2026-10-28",
                "url": "https://example.mataroa.blog/blog/test-post/",
                "body": f"Body.\n\n<!-- mataroa-bridge-id: {bridge_id} -->\n",
            }
            with patch.object(sync, "ROOT", root), patch.object(sync, "api_request", return_value={"ok": True, "post_list": [existing]}) as api:
                sync.publish_new_post("drafts/note.md")
            self.assertFalse(draft.exists())
            self.assertTrue((root / "published" / "note.md").exists())
            api.assert_called_once_with("GET", "/posts/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
