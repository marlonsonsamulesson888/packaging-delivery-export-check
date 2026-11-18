# 用户电脑/共享盘文件读写规则（通用版）

代理在自己的工作机上做事，用户电脑上的盘只当来源或交付地。目的是：不动原件、不丢文件、能说清文件在哪。

## 读
1. 素材盘（如 E:）和客户原稿目录**只读**：只复制，不移动、不改名、不删除。
2. 先复制到用户电脑上的中转目录（如 `C:\Users\<用户>\agent-tools\`），再传到工作机处理。大目录先列清单再挑要的文件，不整盘拷。
3. 记下源路径和 SHA-256，处理后的文件能对回原件。

## 写
1. 输出只放到数据盘（如 D:）下**新建的项目子文件夹**，命名带项目、轮次、日期，例：`D:\<交付根>\<项目>_<日期>\<轮次>\`。
2. 不写桌面、不写系统盘、不覆盖已有文件；同名先改版本号。
3. 先把文件放进中转目录，核对字节数和 SHA-256 与工作机一致，再移动到目标文件夹，**移动后再核一次**。可用 `scripts/check_delivery.py manifest 目录` 生成清单。
4. 报告目标文件夹的完整路径和文件数，必要时帮用户打开文件夹。

## PowerShell 模板（中转 → 目标，逐个校验）
```powershell
$ErrorActionPreference = 'Stop'
$src = 'C:\Users\<用户>\agent-tools'
$dst = 'D:\<交付根>\<项目>_<日期>\<轮次>'
New-Item -ItemType Directory -Path $dst -Force | Out-Null
$files = @(@{n='文件1.jpg'; l=123456; h='<SHA256大写>'})
foreach ($f in $files) {
  $a = Join-Path $src $f.n; $z = Join-Path $dst $f.n
  if ((Get-Item -LiteralPath $a).Length -ne $f.l -or (Get-FileHash -LiteralPath $a).Hash -ne $f.h) { throw "中转文件不一致：$($f.n)" }
  if (Test-Path -LiteralPath $z) { throw "目标已有同名文件：$($f.n)" }
  Move-Item -LiteralPath $a -Destination $z
  if ((Get-FileHash -LiteralPath $z).Hash -ne $f.h) { throw "移动后不一致：$($f.n)" }
}
Get-ChildItem -LiteralPath $dst | Select-Object Name, Length
```

## 不做
不删除用户电脑上的任何文件（用户明确说要删时，单独确认）；不上传到网盘或对外发送，除非用户点名要求。
