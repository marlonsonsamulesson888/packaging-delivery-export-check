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

class MultiBoard(unittest.TestCase):
    setUp = Delivery.setUp
    def multi(self, same=False):
        d = pymupdf.open()
        d.new_page(width=25.4 * MM, height=50.8 * MM)
        d.new_page(width=(25.4 if same else 50.8) * MM, height=50.8 * MM)
        d.set_metadata({'creator': 'Adobe Illustrator'})
        d.save(self.d / 'a.ai'); d.close()
        jpg(self.d / 'one.jpg', (300, 600))
        jpg(self.d / 'two.jpg', (300 if same else 600, 600))
        return [{'ai':'a.ai', 'page':0, 'jpg':'one.jpg'},
                {'ai':'a.ai', 'page':1, 'jpg':'two.jpg'}]

    def test_explicit_correct_and_no_map(self):
        pairs = self.multi()
        r = m.check_package(self.d, expect_jpg=2, pairs=pairs)
        self.assertEqual(r['summary']['fail'], 0)
        self.assertEqual(r['jpg'][1]['pair']['page'], 1)
        self.assertEqual(r['jpg'][1]['expected_pixels'], [600,600])
        self.assertGreater(m.check_package(self.d, expect_jpg=2)['summary']['fail'], 0)

    def test_invalid_maps(self):
        pairs = self.multi()
        bad = [pairs[:1], pairs + [pairs[0]],
               [pairs[0], dict(pairs[1], page=2)],
               [pairs[0], dict(pairs[1], page=-1)],
               [pairs[0], dict(pairs[1], page=True)],
               [pairs[0], dict(pairs[1], page=0)],
               [pairs[0], dict(pairs[1], jpg='one.jpg')],
               [pairs[0], dict(pairs[1], ai='../a.ai')],
               {'pairs':pairs}]
        for mapping in bad:
            with self.subTest(mapping=mapping):
                self.assertGreater(m.check_package(self.d, expect_jpg=2, pairs=mapping)['summary']['fail'], 0)

    def test_wrong_size_pair_fails(self):
        pairs = self.multi()
        pairs[0]['page'], pairs[1]['page'] = 1,0
        self.assertGreater(m.check_package(self.d, expect_jpg=2, pairs=pairs)['summary']['fail'], 0)

    def test_same_size_remains_manual(self):
        pairs = self.multi(same=True)
        pairs[0]['page'], pairs[1]['page'] = 1,0
        r = m.check_package(self.d, expect_jpg=2, pairs=pairs)
        self.assertEqual(r['summary']['fail'], 0)
        self.assertTrue(all(any(c['rule']=='画板内容与 JPG 对应' and c['status']=='manual'
                                for c in j['checks']) for j in r['jpg']))

    def test_page_cli_and_bounds(self):
        import json
        self.multi()
        for page in (-1, 2):
            with self.assertRaises(ValueError):
                m.read_ai(self.d / 'a.ai', page)
        out = self.d / 'report.json'
        self.assertEqual(m.main(['ai',str(self.d/'a.ai'),'--page','1','--json',str(out)]),0)
        self.assertEqual(json.loads(out.read_text())['artboard_mm'],[50.8,50.8])
        self.assertEqual(m.main(['jpg',str(self.d/'two.jpg'),'--from-ai',str(self.d/'a.ai'),'--page','1','--json',str(out)]),0)
        self.assertEqual(m.main(['jpg',str(self.d/'two.jpg'),'--from-ai',str(self.d/'a.ai'),'--page','9']),2)

    def test_cli_rejects_explicit_null_pairs(self):
        fake_ai(self.d/'a.ai',25.4,25.4)
        jpg(self.d/'a.jpg',(300,300))
        with tempfile.TemporaryDirectory() as config:
            mapping = Path(config)/'pairs.json'
            mapping.write_text('null')
            self.assertEqual(m.main(['package',str(self.d),'--pairs',str(mapping)]),2)

    def test_multiple_ai_requires_map(self):
        fake_ai(self.d/'a.ai',25.4,25.4)
        fake_ai(self.d/'b.ai',50.8,50.8)
        jpg(self.d/'a.jpg',(300,300)); jpg(self.d/'b.jpg',(600,600))
        self.assertGreater(m.check_package(self.d,expect_ai=2,expect_jpg=2)['summary']['fail'],0)
        pairs=[{'ai':'a.ai','page':0,'jpg':'a.jpg'},{'ai':'b.ai','page':0,'jpg':'b.jpg'}]
        self.assertEqual(m.check_package(self.d,expect_ai=2,expect_jpg=2,pairs=pairs)['summary']['fail'],0)


if __name__ == "__main__":
    unittest.main()
