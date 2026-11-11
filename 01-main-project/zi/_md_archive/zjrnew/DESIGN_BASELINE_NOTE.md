# zjrnew 画布样式基线说明

## 背景

2026-08-07 对 `zjrnew.design` 执行 HTML → 画布同步后，设计工作区校验产生 174 条软警告（soft warnings），无阻塞性渲染错误。

## 警告分类

### 1. 双品牌色设计（非错误，保留）

项目采用 **青绿色（Teal）+ 琥珀色（Amber）** 双品牌色体系：

- `--brand: #0D9488` / `--brand-mid: #14B8A6` / `--brand-light: #CCFBF1`
- `--accent: #D4944C` / `--accent-mid: #E8C088` / `--accent-light: #F5E6D0`

这些变量在 `colors_and_type.css` 与每页 `<style id="theme-vars">` 中统一登记，是画布评审后的正式视觉风格。`free-explore` 校验器提示「不得使用 secondary/accent 品牌变量」，但本项目为保持玻璃新拟态与双色调视觉层次，**故意保留**该配色方案。

### 2. 硬编码渐变/装饰色（视觉锚点，保留）

少量页面在 hero、状态栏、头像装饰等位置使用了一次性渐变，例如：

- `client-member.html` 会员页 hero 光晕
- `client-chat.html` 聊天页顶部 radial-gradient
- `client-price-adjust.html` / `client-review.html` 证据/评价占位图渐变
- `worker-deposit.html` 等级卡片渐变

这些色值与当前画布像素级对应，是特定页面的视觉锚点。若强行抽成通用变量，会稀释语义或引入大量一次性 token，因此**保持原样**。

## 结论

为「忠于画布样式」，以上 174 条软警告作为**已接受的视觉基线**处理，不反向修改 `.design`、不删除 accent 品牌变量、不强行统一为单色系。后续如需进入严格单主色模式，需先完成设计评审并更新样式规范文档。
