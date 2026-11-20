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

## 多画板显式配对（v1.1）

页码为 **零基**：第一画板 `0`，第二画板 `1`。越界拒绝，不截断到末页。

```sh
python scripts/check_delivery.py ai 外发.ai --page 1
python scripts/check_delivery.py jpg 第二画板.jpg --from-ai 外发.ai --page 1
python scripts/check_delivery.py package 外发文件夹 --expect-jpg 2 --pairs 配对.json
```

配对文件放在外发目录之外，格式如下（相对外发目录，路径用 `/`）：

```json
[
  {"ai": "外发.ai", "page": 0, "jpg": "第一画板.jpg"},
  {"ai": "外发.ai", "page": 1, "jpg": "第二画板.jpg"}
]
```

多 AI 或多画板必须显式映射；每个 AI 画板、每张 JPG 恰好出现一次。
缺项、重复、越界、无效路径或尺寸不符均失败，不按文件排序或尺寸猜配对。
单 AI 单画板保留旧用法。映射检查失败时不继续进行未配对 JPG 的尺寸检查。
**同尺寸不代表同内容**：即使数字检查通过，也必须人工逐页核对图文对应。
返回 0 仍不是印刷放行；PDF 兼容信息和 Illustrator 标记不是原生 AI 完整性的证明。
