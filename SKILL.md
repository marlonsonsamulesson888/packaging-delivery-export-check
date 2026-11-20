---
name: packaging-delivery-export-check
description: 彩盒设计对外交付的“两件套”导出与核对：分层转曲 AI 加整画板带刀线 300DPI JPG，工作版 AI 留厂；按画板毫米算 JPG 应有像素，查只改 DPI 标签、没导整画板、未转曲、PDF 改扩展名冒充 AI、多带第三类文件，并按安全规则把文件放到新文件夹、核对字节和 SHA-256。用于“导出给客户/印厂”“交付包对不对”“JPG 是不是 300DPI”，不代替印前复核和放行签字。
---

# 两件交付导出与核对

对外只发两件：**分层转曲 AI** 和 **整画板、显示刀线的 300DPI JPG**。可编辑未转曲的工作 AI 留在厂内。规则和默认值见 [delivery-rules.md](references/delivery-rules.md)，可按客户合同改。

## 1. 导出前确认
- 最终设计已通过印前技术复核（出血、墨量、字号、位图 ppi 等不在本技能里查）。
- 确认画板：编号、实际宽×高 mm（含不含出血按本厂口径记录）。多画板时每个画板各出一张 JPG。
- 先算应有像素：`python scripts/check_delivery.py calc 210x270` → 2480×3189。公式：mm ÷ 25.4 × 300，四舍五入。

## 2. 导出
- AI：从工作版另存，文字全部转曲，图层名保留（刀线层、印刷层分开），刀线保留在独立层。不覆盖工作版。
- JPG：导出**整个画板**，刀线层显示，分辨率 300ppi，像素必须等于上一步的数。只把 DPI 标签改成 300 不算数。
- 两件放进一个**新建的外发文件夹**，不混入 PDF、PNG、预览图、说明文档（厂内检查用 PDF 另放）。

## 3. 核对
```bash
python scripts/check_delivery.py package 外发文件夹 --json 交付核对.json
```
- 查：AI/JPG 各一份、无第三类文件；AI 有 Illustrator 标记（不是 PDF 改扩展名）、字体数 0（已转曲）；JPG 是真 JPEG、像素等于画板毫米换算（±1px）、DPI 标签 300、长宽比与画板一致、“标签 300 但像素不足”单独报 fail。
- 单查 JPG：`check_delivery.py jpg 图.jpg --artboard 210x270` 或 `--from-ai 外发.ai`。
- `manual` 项必须人工做：在 Illustrator 里重开 AI，看图层、刀线层、逐元素是否矢量；打开 JPG 放大看刀线是否显示、画板是否完整。
- 退出码：0 无 fail；1 有 fail；2 读取错误。**0 不等于放行**。

## 4. 搬运和告知
放到老板/客户电脑或共享盘时，按 [file-handoff.md](references/file-handoff.md)：源盘只读、先进中转目录、再移到目标盘**新建文件夹**、前后对字节数和 SHA-256、报告完整路径。不放桌面和系统盘，不覆盖旧版。

## 5. 交付说明
写清：文件名、画板 mm、JPG 像素和 DPI、AI 转曲状态（字体数）、谁做了技术/审美复核（AI 检查写“AI 复核，待人工确认”）、未检项。放行只能由技术员和审美员签。

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
