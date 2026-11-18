#!/usr/bin/env python3
"""两件交付核对：分层转曲 AI + 整画板带刀线 300DPI JPG（只给数据，不放行）。

子命令：
  calc     按画板毫米算应有像素：python check_delivery.py calc 210x270 [--dpi 300]
  jpg      核 JPG 像素与 DPI 标签：python check_delivery.py jpg 图.jpg --artboard 210x270
           或 --from-ai 文件.ai（读 PDF 兼容画板尺寸）
  manifest 列文件名/字节数/SHA-256：python check_delivery.py manifest 目录
  package  核整个外发文件夹：python check_delivery.py package 外发目录 [--expect-ai 1 --expect-jpg 1]
依赖：Pillow；读 AI/PDF 画板与字体需 PyMuPDF。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MM_PER_IN = 25.4
PT2MM = 25.4 / 72


def expected_px(mm, dpi=300):
    return int(round(mm / MM_PER_IN * dpi))


def parse_wh(s):
    parts = [float(p) for p in s.lower().replace("×", "x").replace("*", "x").split("x")]
    if len(parts) != 2:
        raise ValueError("画板尺寸写成 宽x高（mm），如 210x270")
    return parts


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_ai(path, page=0, box="mediabox"):
    """读 AI（PDF 兼容）/ PDF：画板 mm、字体数、是否像真 AI。"""
    raw = Path(path).read_bytes()
    head = raw[:16]
    is_pdf_compat = head.startswith(b"%PDF")
    is_ps = head.startswith(b"%!PS-Adobe")
    illustrator_marks = any(m in raw for m in (b"AIPrivateData", b"Adobe Illustrator", b"/Illustrator"))
    info = {"file": Path(path).name, "sha256": sha256(path), "size_bytes": len(raw),
            "header": "PDF 兼容" if is_pdf_compat else ("PostScript" if is_ps else "未知"),
            "illustrator_markers": illustrator_marks}
    if not is_pdf_compat:
        info["note"] = "不是 PDF 兼容格式，读不到画板和字体；用 Illustrator 打开核对"
        return info
    try:
        import pymupdf as fitz
    except ImportError:  # pragma: no cover
        import fitz  # type: ignore
    doc = fitz.open(path)
    info["pages"] = len(doc)
    pg = doc[min(page, len(doc) - 1)]
    r = getattr(pg, box)
    info["artboard_box"] = box
    info["artboard_mm"] = [round(r.width * PT2MM, 2), round(r.height * PT2MM, 2)]
    fonts = set()
    for p in doc:
        for f in p.get_fonts():
            fonts.add(f[3] or f[4])
    info["fonts"] = sorted(fonts)
    info["font_count"] = len(fonts)
    info["image_count"] = sum(len(p.get_images()) for p in doc)
    ocgs = doc.get_ocgs() if hasattr(doc, "get_ocgs") else {}
    info["pdf_layers"] = sorted(v.get("name", "") for v in ocgs.values()) if ocgs else []
    doc.close()
    return info


def check_jpg(path, artboard_mm, dpi=300, tol_px=1):
    from PIL import Image
    with Image.open(path) as im:
        fmt, mode, (w, h) = im.format, im.mode, im.size
        tag = im.info.get("dpi")
    ew, eh = expected_px(artboard_mm[0], dpi), expected_px(artboard_mm[1], dpi)
    tag_ok = bool(tag) and all(abs(float(t) - dpi) < 0.6 for t in tag)
    px_ok = abs(w - ew) <= tol_px and abs(h - eh) <= tol_px
    checks = [
        {"rule": "文件真的是 JPEG", "status": "ok" if fmt == "JPEG" else "fail", "detail": str(fmt)},
        {"rule": f"横纵像素 = 画板 mm ÷ 25.4 × {dpi}（±{tol_px}px）", "status": "ok" if px_ok else "fail",
         "detail": f"实测 {w}×{h}，应为 {ew}×{eh}（画板 {artboard_mm[0]}×{artboard_mm[1]} mm）"},
        {"rule": f"DPI 标签 = {dpi}", "status": "ok" if tag_ok else "warn", "detail": str(tag)},
    ]
    if tag_ok and not px_ok:
        checks.append({"rule": "只改了 DPI 标签", "status": "fail",
                       "detail": "标签是 300 但像素不够，按规定不算 300DPI，要从 AI 按整画板重新导出"})
    eff = [round(w / (artboard_mm[0] / MM_PER_IN), 1), round(h / (artboard_mm[1] / MM_PER_IN), 1)]
    checks.append({"rule": "画板长宽比一致", "status": "ok" if abs(w / h - artboard_mm[0] / artboard_mm[1]) < 0.003 else "fail",
                   "detail": f"JPG {w / h:.4f} vs 画板 {artboard_mm[0] / artboard_mm[1]:.4f}（不一致多半是没导出整画板）"})
    checks.append({"rule": "刀线在图上可见", "status": "manual", "detail": "脚本不判断，打开 JPG 放大看刀线是否显示、是否整画板"})
    return {"file": Path(path).name, "sha256": sha256(path), "format": fmt, "mode": mode,
            "pixels": [w, h], "expected_pixels": [ew, eh], "dpi_tag": tag, "effective_ppi": eff,
            "checks": checks}


def check_package(folder, dpi=300, expect_ai=1, expect_jpg=1, tol_px=1):
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    ais = [p for p in files if p.suffix.lower() == ".ai"]
    jpgs = [p for p in files if p.suffix.lower() in (".jpg", ".jpeg")]
    others = [p for p in files if p not in ais and p not in jpgs]
    checks = [
        {"rule": f"外发 AI 数量 = {expect_ai}", "status": "ok" if len(ais) == expect_ai else "fail", "detail": str(len(ais))},
        {"rule": f"外发 JPG 数量 = {expect_jpg}", "status": "ok" if len(jpgs) == expect_jpg else "fail", "detail": str(len(jpgs))},
        {"rule": "没有第三类外发文件", "status": "ok" if not others else "warn",
         "detail": ", ".join(p.name for p in others) or "无"},
    ]
    ai_reports, jpg_reports = [], []
    for a in ais:
        info = read_ai(a)
        info["checks"] = [
            {"rule": "看起来是真 AI，不是 PDF 改扩展名", "status": "ok" if info["illustrator_markers"] else "fail",
             "detail": "有 Illustrator 私有数据标记" if info["illustrator_markers"] else "没找到 Illustrator 标记"},
            {"rule": "已转曲（字体数 = 0）", "status": "ok" if info.get("font_count") == 0 else ("fail" if info.get("font_count") else "manual"),
             "detail": ", ".join(info.get("fonts", [])) or "0"},
            {"rule": "分层、刀线层、对象逐元素检查", "status": "manual", "detail": "要在 Illustrator 里重开核对，脚本看不到 AI 图层"},
        ]
        ai_reports.append(info)
    ref = ai_reports[0].get("artboard_mm") if ai_reports else None
    for j in jpgs:
        if ref:
            jpg_reports.append(check_jpg(j, ref, dpi, tol_px))
        else:
            jpg_reports.append({"file": j.name, "checks": [{"rule": "画板尺寸", "status": "manual", "detail": "没有可读的 AI 画板，用 jpg --artboard 手动核"}]})
    every = checks + [c for r in ai_reports + jpg_reports for c in r["checks"]]
    return {"folder": folder.name, "dpi": dpi, "package_checks": checks, "ai": ai_reports, "jpg": jpg_reports,
            "summary": {s: sum(1 for c in every if c["status"] == s) for s in ("ok", "warn", "fail", "manual")},
            "verdict": "仅数据；manual 项必须人工核，放行由技术员和审美员签"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="两件交付核对")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calc"); c.add_argument("artboard"); c.add_argument("--dpi", type=int, default=300)
    j = sub.add_parser("jpg"); j.add_argument("jpg"); j.add_argument("--artboard"); j.add_argument("--from-ai")
    j.add_argument("--box", default="mediabox"); j.add_argument("--dpi", type=int, default=300); j.add_argument("--tol", type=int, default=1)
    mf = sub.add_parser("manifest", help="列出文件夹内文件名、字节数、SHA-256，供搬运前后核对")
    mf.add_argument("folder")
    p = sub.add_parser("package"); p.add_argument("folder"); p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--expect-ai", type=int, default=1); p.add_argument("--expect-jpg", type=int, default=1); p.add_argument("--tol", type=int, default=1)
    for s in (j, p):
        s.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "calc":
            w, h = parse_wh(a.artboard)
            r = {"artboard_mm": [w, h], "dpi": a.dpi, "pixels": [expected_px(w, a.dpi), expected_px(h, a.dpi)],
                 "formula": f"mm ÷ 25.4 × {a.dpi}，四舍五入"}
            print(json.dumps(r, ensure_ascii=False))
            return 0
        if a.cmd == "manifest":
            fs = sorted(x for x in Path(a.folder).iterdir() if x.is_file())
            print(json.dumps([{"name": x.name, "bytes": x.stat().st_size, "sha256": sha256(x).upper()} for x in fs],
                             ensure_ascii=False, indent=2))
            return 0
        if a.cmd == "jpg":
            if a.artboard:
                ab = parse_wh(a.artboard)
            elif a.from_ai:
                ab = read_ai(a.from_ai, box=a.box)["artboard_mm"]
            else:
                raise ValueError("要给 --artboard 或 --from-ai")
            r = check_jpg(a.jpg, ab, a.dpi, a.tol)
            statuses = [x["status"] for x in r["checks"]]
        else:
            r = check_package(a.folder, a.dpi, a.expect_ai, a.expect_jpg, a.tol)
            statuses = [x["status"] for x in r["package_checks"]] + [x["status"] for y in r["ai"] + r["jpg"] for x in y["checks"]]
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        return 2
    t = json.dumps(r, ensure_ascii=False, indent=2)
    if getattr(a, "json", None):
        Path(a.json).write_text(t, encoding="utf-8")
    else:
        print(t)
    return 1 if "fail" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
