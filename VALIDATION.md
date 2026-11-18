# 验证记录

日期：2026-11-18（America/Los_Angeles）。对象：本公开候选。

## 已执行
- `python -m unittest discover -s tests -v`：6 项全部通过。覆盖：像素换算（210→2480、270→3189）、合格 JPG、“只改 DPI 标签”报 fail、合格外发包、未转曲+多余 PDF+像素不对、PDF 改扩展名冒充 AI、命令行与 manifest。
- 用两份厂内试跑 AI（一份转曲、一份未转曲，不随仓库发布）读取：画板 467.86×344.5mm 一致；字体数分别为 0 和 3；都有 Illustrator 标记。

## 未验证
- 非 PDF 兼容保存的 AI；Illustrator 图层结构与逐元素检查（需人工）。
- JPG 上刀线是否可见（需人工）。不代替印前复核和放行签字。
