# 两件交付导出与核对

彩盒设计对外交付：分层转曲 AI + 整画板带刀线 300DPI JPG。脚本按画板毫米算 JPG 应有像素，核对外发文件夹里的件数、AI 转曲和真伪、JPG 像素与 DPI 标签，并能生成搬运用的 SHA-256 清单。只给数据，不放行。

入口：[SKILL.md](SKILL.md)。需要 Python 3.10+、Pillow、PyMuPDF。

```sh
python scripts/check_delivery.py calc 210x270
python scripts/check_delivery.py package 外发文件夹 --json 交付核对.json
python scripts/check_delivery.py manifest 外发文件夹
python -m unittest discover -s tests -v
```

## 限制
- 只能读 PDF 兼容保存的 AI；看不到 Illustrator 图层结构，图层和逐元素检查要人工在 Illustrator 里做。
- 不判断 JPG 上刀线是否显示，不做印前（出血、墨量、ppi）检查。

MIT，Copyright (c) 2026 Marlonson Samulesson，见 [LICENSE](LICENSE)。
