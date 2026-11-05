#!/usr/bin/env python3
"""README 解析：标题层级/行号/链接/代码标记；不推断功能。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
from parsers import readme as RM

DOC = """# Project

Intro line.

## Installation

```bash
npm install
```

### Deep heading

See [docs](https://example.com/docs) for more.

## Usage
"""


class TestReadme(unittest.TestCase):
    def test_format(self):
        self.assertEqual(RM.document_format("README.md"), "markdown")
        self.assertEqual(RM.document_format("README.txt"), "text")
        self.assertTrue(RM.is_readme("README.md"))
        self.assertTrue(RM.is_readme("docs/README.markdown"))
        self.assertFalse(RM.is_readme("src/main.py"))

    def test_headings(self):
        h, _, _ = RM.parse(DOC)
        self.assertEqual(len(h), 4)
        self.assertEqual(h[0]["level"], 1); self.assertEqual(h[0]["title"], "Project")
        self.assertEqual(h[1]["level"], 2); self.assertEqual(h[1]["title"], "Installation")
        self.assertEqual(h[2]["level"], 3); self.assertEqual(h[2]["title"], "Deep heading")
        self.assertEqual(h[3]["level"], 2); self.assertEqual(h[3]["title"], "Usage")

    def test_heading_line_numbers(self):
        h, _, _ = RM.parse(DOC)
        self.assertEqual(h[1]["line"], 5, "## Installation 在第 5 行")
        self.assertEqual(h[1]["start_byte"], len("# Project\n\nIntro line.\n\n"))

    def test_links(self):
        _, links, _ = RM.parse(DOC)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["target"], "https://example.com/docs")
        self.assertEqual(links[0]["text"], "docs")

    def test_fence_language_marker(self):
        _, _, fences = RM.parse(DOC)
        self.assertGreaterEqual(len(fences), 1)
        self.assertEqual(fences[0]["language_marker"], "bash")

    def test_no_function_inference(self):
        """★ 有 Installation 标题 ≠ 安装流程完整可运行。"""
        import content_extractor as EX
        sem = EX.CLAIM_SEMANTICS[EX.F_README_HEADING]
        self.assertIn("标题", sem["meaning"])
        self.assertNotIn("可运行的安装", sem["meaning"])

    def test_long_line_safe(self):
        long_doc = "# T\n" + "x" * 10000 + "\n"
        h, _, _ = RM.parse(long_doc)
        self.assertEqual(len(h), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
