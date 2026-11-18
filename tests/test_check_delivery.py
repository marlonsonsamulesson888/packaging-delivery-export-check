"""两件交付核对单元测试（合成文件）。运行：python -m unittest discover -s tests -v"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("check_delivery", ROOT / "scripts/check_delivery.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
MM = 72 / 25.4


def fake_ai(path, w_mm, h_mm, text=False, illustrator=True):
    doc = pymupdf.open()
    pg = doc.new_page(width=w_mm * MM, height=h_mm * MM)
    pg.draw_rect(pymupdf.Rect(10, 10, 100, 100), color=(1, 0, 0))
    if text:
        pg.insert_text((20, 50), "LIVE TEXT", fontsize=12)
    if illustrator:
        doc.set_metadata({"creator": "Adobe Illustrator 28.0"})
    doc.save(str(path), garbage=0, deflate=False)


def jpg(path, px, dpi=(300, 300)):
    Image.new("RGB", px, "white").save(path, "JPEG", dpi=dpi)


class Delivery(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)

    def test_calc(self):
        self.assertEqual(m.expected_px(210), 2480)
        self.assertEqual(m.expected_px(270), 3189)

    def test_good_jpg(self):
        p = self.d / "a.jpg"
        jpg(p, (2480, 3189))
        r = m.check_jpg(p, [210, 270])
        st = {c["rule"]: c["status"] for c in r["checks"]}
        self.assertNotIn("fail", st.values())

    def test_dpi_tag_only(self):
        p = self.d / "b.jpg"
        jpg(p, (827, 1063))  # 72dpi 像素却标 300
        r = m.check_jpg(p, [210, 270])
        self.assertTrue(any(c["rule"] == "只改了 DPI 标签" and c["status"] == "fail" for c in r["checks"]))

    def test_package_ok_and_problems(self):
        out = self.d / "外发"
        out.mkdir()
        fake_ai(out / "盒.ai", 210, 270)
        jpg(out / "盒.jpg", (2480, 3189))
        r = m.check_package(out)
        self.assertEqual(r["summary"]["fail"], 0)
        self.assertEqual(r["ai"][0]["font_count"], 0)
        # 未转曲 + 多一个 PDF + JPG 尺寸不对
        bad = self.d / "外发2"
        bad.mkdir()
        fake_ai(bad / "盒.ai", 210, 270, text=True)
        jpg(bad / "盒.jpg", (2400, 3189))
        (bad / "检查用.pdf").write_bytes(b"%PDF-1.4\n")
        r2 = m.check_package(bad)
        self.assertGreaterEqual(r2["summary"]["fail"], 2)
        self.assertEqual(r2["summary"]["warn"], 1)

    def test_renamed_pdf_flagged(self):
        out = self.d / "x"
        out.mkdir()
        fake_ai(out / "盒.ai", 100, 100, illustrator=False)
        jpg(out / "盒.jpg", (1181, 1181))
        r = m.check_package(out)
        self.assertEqual(r["ai"][0]["checks"][0]["status"], "fail")

    def test_cli(self):
        p = self.d / "a.jpg"
        jpg(p, (2480, 3189))
        self.assertEqual(m.main(["jpg", str(p), "--artboard", "210x270", "--json", str(self.d / "r.json")]), 0)
        self.assertEqual(m.main(["jpg", str(p), "--artboard", "200x270", "--json", str(self.d / "r2.json")]), 1)
        self.assertEqual(m.main(["jpg", str(p)]), 2)
        self.assertEqual(m.main(["manifest", str(self.d)]), 0)


if __name__ == "__main__":
    unittest.main()
