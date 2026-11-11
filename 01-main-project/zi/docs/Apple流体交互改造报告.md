# Apple流体交互UI评审报告

**评审日期**：2026-09-05
**评审对象**：`zjrnew/` 玻璃新拟态页面群（131 个 HTML，70201 行）+ `zjrnew/colors_and_type.css`（283 行设计令牌）
**评审依据**：Apple 流体交互五要素 + 八大设计原则
**评审方式**：全量静态扫描（关键词计数）+ 令牌对比度实测（WCAG 2.1 相对亮度算法）

---

## 一、总体判断

**材质层 90 分，运动层 5 分。** 玻璃、新拟态阴影、双品牌色的完成度很高，截图层面已经很接近。但界面是"会摆姿势"而不是"会运动"——所有动画都是发射后不管的固定时长过渡，手指在动画期间完全不参与。

扫描证据：

| 检测项 | 命中次数 | 结论 |
|---|---|---|
| `touchstart` / `touchmove` / `touchend` | **0 / 0 / 0** | 没有一帧是手势驱动的 |
| `requestAnimationFrame` | **2** | 没有物理循环 |
| `scroll-snap` | **0** | 轮播/列表无吸附 |
| `overscroll-behavior` | **0** | 滚动到顶无橡胶回弹 |
| `-webkit-overflow-scrolling` | **0** | iOS 惯性滚动未启用 |
| `:hover` | **0** | 桌面端预览全无反馈 |
| `onclick` / `addEventListener` / `classList.add` | **0 / 6 / 9** | 95 处 sheet 是静态摆设 |
| `will-change` | **1** vs `backdrop-filter` **836** | 移动端 GPU 重灾区 |
| `transition` 总数 / 其中 `.2s` | **797 / 327** | 全站共用一个时长 |
| `prefers-reduced-motion` | 38（覆盖 29% 页面） | 无障碍覆盖不均衡 |

---

## 二、核心交互校验（7 项）

- [x] **按下即反馈** — 1172 处 `:active`，但全部是 `transform:scale(0.94)` 配 `transition`。问题：`:active` 在移动端有约 100ms 的判定延迟，且不可中途打断。**建议改为 `pointerdown` 驱动**。
- [ ] **拖拽 1:1 跟随手指** — 0 处手势监听。抽屉、滑块、卡片全部不可拖。
- [ ] **动画随时可打断** — CSS `transition` 一旦触发，时长与路径锁死，无法从实时位置接管。这是全站最大的机制性缺陷。
- [ ] **使用弹簧而非固定时长 transition** — 现有 `--spring: cubic-bezier(0.175,0.885,0.32,1.275)` 是"假弹簧"：固定 0.2s、固定过冲 1.275 倍，与速度无关。
- [ ] **手势释放移交原始速度** — 无速度采集，无动量投射。
- [ ] **边界使用橡胶缓冲** — 无 `overscroll-behavior`，滚动到边界是硬截断。
- [ ] **出场入场路径对称** — 13 处 `@keyframes` 分散在 131 页，无统一入场编排，弹层不从触发源弹出。

---

## 三、物理参数（已写入 `fluid-motion.js`）

Apple 官方给的是「阻尼比 ζ + 响应时间」，而 Web 弹簧需要「刚度 k + 阻尼 c」。换算按 5% 稳定判据 `3.0 = ζ · ωn · response`：

```
ωn = 3.0 / (ζ · response)      k = ωn²      c = 2ζωn
```

| 交互类型 | 阻尼比 ζ | 响应时间 | k | c | 完全稳定(2%) |
|---|---|---|---|---|---|
| 抽屉 / 底部弹窗 | 0.8 | 0.3s | 156 | 20.0 | 0.46s |
| 移动 / 画中画 | 1.0 | 0.4s | 56 | 15.0 | 0.61s |
| 旋转 | 0.8 | 0.4s | 88 | 15.0 | 0.61s |
| 按压·按下 | 1.0 | 0.12s | 625 | 50.0 | 0.18s |
| 按压·抬起 | 0.6 | 0.32s | 244 | 18.8 | 0.49s |

> 按下走临界阻尼（干脆不晃），抬起走欠阻尼（轻回弹）——这个不对称是 Apple 手感的关键。

两个必须复用的官方公式：

```js
// 橡胶边界：over=超出距离，dim=容器尺寸，c=0.55
function rubber(over, dim, c) { return (over * dim * c) / (dim + c * over); }

// 动量投射：rate 0.998 普通滚动 / 0.99 更干脆
function project(velocity, rate) { return (velocity / 1000) * (rate / (1 - rate)); }
```

---

## 四、材质与层级

**已做好**：`--neu-out-sm/md/lg` 三级阴影层次清晰，tab-bar 的 48px 双层毛玻璃 + inset 高光 + mask 描边是教科书级实现。

**三个必须改的问题**：

1. **836 处 `backdrop-filter` 只有 1 处 `will-change`**。移动端每帧重算模糊，中低端机直接掉帧。按层级分级：
   - 常驻层（tab-bar、导航栏）：`blur(24px)`，加 `will-change: transform`
   - 弹出层（sheet、弹窗）：`blur(40px)`，**动画期间才启用，静止后降级为纯色**
   - 列表卡片：`blur(0)`，直接用半透明实色 + 阴影模拟
2. **`.tab-item` 用了 `transition: all .2s`** —— `all` 会让浏览器监听所有属性，是明确的性能反模式。改成枚举属性。
3. **`background: var(--popover)` 是 `#fff` 不透明**，与玻璃层叠时会出现"实心块贴玻璃"的割裂感，建议改 `rgba(255,255,255,0.86)` + `backdrop-filter`。

---

## 五、排版：光学字号体系缺失

扫描结果：

- 字号出现 **10.5 / 11 / 11.5 / 12 / 12.5 / 13 / 13.5 / 14 / 15 / 16 / 17 / 18 / 24 / 26px** 共 14 档，其中半像素档（10.5/11.5/12.5/13.5）合计 **118 处**
- **`font-size:11px` 有 186 处**，`10.5px` 还有 16 处 —— 低于中文可读性下限
- `line-height` 全站只出现约 150 次，对应数千处文字节点，绝大多数靠浏览器默认
- `letter-spacing` 混用 `em` 与绝对值 px（`-0.01em` 164 处、`-.2px`/`-.5px`/`-1.2px` 共 25 处）

**诊断**：14 档字号是"凑出来的"，不是体系。Apple 的光学字号是 **字号越大、字间距越紧、行高越小**，三者联动。中文衬线体（Noto Serif SC）在 13px 以下横笔画会断，比拉丁字体的安全下限更高。

建议收敛为 6 档，并给出联动参数：

| 角色 | 字号 | 行高 | 字间距 | 用途 |
|---|---|---|---|---|
| caption | 12px | 1.5 | +0.01em | 标签、时间戳 |
| body | 14px | 1.6 | 0 | 正文、描述 |
| body-strong | 15px | 1.5 | -0.01em | 列表主标题 |
| title | 17px | 1.4 | -0.015em | 卡片标题 |
| headline | 22px | 1.3 | -0.02em | 区块标题 |
| display | 28px | 1.2 | -0.025em | 数值、金额 |

**11px 的 186 处建议全部提到 12px**，10.5px 直接并入 12px。

---

## 六、无障碍：这是本轮最严重的问题

对比度实测（WCAG 2.1 相对亮度算法，底色 `#F2EDE8`）：

| 令牌 | 色值 | 实测对比度 | 判定 |
|---|---|---|---|
| `--text-1` | #2C2824 | 12.57:1 | 通过 |
| `--text-2` | #8B8178 | **3.28:1** | 正文不达标（需 4.5） |
| `--text-3` | #B5ADA5 | **1.90:1** | **严重不达标** |
| `--brand` | #0D9488 | **3.22:1** | 作为文字色不达标 |
| `--accent` | #D4944C | **2.22:1** | **严重不达标** |
| `--state-error` | #C4533A | 3.89:1 | 正文不达标 |
| `--state-success` | #5B8C5A | 3.38:1 | 正文不达标 |

按钮上的白字：

| 底色 | 对比度 | 判定 |
|---|---|---|
| `--primary` #0D9488 | **3.74:1** | **不达标**（按钮字号 13px，需 4.5） |
| `--brand-dark` #0A7A70 | 5.21:1 | 通过 |
| `--accent` #D4944C | **2.58:1** | **严重不达标** |

**最致命的一处**：`.tab-item` 未选中态用 `--text-3`（1.90:1），字号 11px。底部导航是最高频的操作入口，1.9:1 意味着弱视用户基本看不见未选中的 tab。

**修复建议**（实测值）：

```css
--text-2: #6E665E;  /* 4.85:1，正文达标 */
--text-3: #6E665E;  /* tab 未选中必须到 4.5:1，与 text-2 合并 */
--primary: #0A7A70; /* 白字按钮 5.21:1 */
--accent-text: #8A5A1E; /* 琥珀色仅作装饰，文字场景改用深色 */
```

同时补三段媒体查询（全站覆盖，目前只有 29% 页面有）：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .tab-bar, .sheet { backdrop-filter: none; background: rgba(255,255,255,0.92); }
}
@media (prefers-reduced-transparency: reduce) {
  .tab-bar, .sheet, .card { backdrop-filter: none; background: #FFFFFF; }
}
@media (prefers-contrast: high) {
  :root { --text-2: #4A443E; --text-3: #4A443E; --border: rgba(44,40,36,0.20); }
}
```

---

## 七、八大设计原则打分

| 原则 | 得分 | 问题 |
|---|---|---|
| 目的性 Clarity | 6/10 | 文字对比度拖累，11px 字号过多 |
| 用户控制权 Control | **2/10** | 动画全部不可打断，手势零参与 |
| 责任 Responsibility | 5/10 | 无障碍覆盖 29%，对比度多处不达标 |
| 熟悉感 Familiarity | 8/10 | 底部 tab、sheet、卡片布局符合平台惯例 |
| 灵活性 Flexibility | 4/10 | 无桌面端 hover，无横屏适配证据 |
| 简洁 Simplicity | 7/10 | 材质层次偏多，部分页面装饰与内容争夺注意力 |
| 工艺 Craft | 8/10 | 毛玻璃与新拟态细节到位，但运动工艺缺失 |
| 愉悦感 Delight | **3/10** | 愉悦感几乎全部来自静态材质，动态层面没有 |

**综合 5.4/10**。短板高度集中在「用户控制权」和「愉悦感」，而这两项恰好都由**运动**贡献，不由材质贡献。

---

## 八、改造方案与落地步骤

已交付：`zjrnew/fluid-motion.js`（零依赖，约 260 行，语法已校验）。

### 第 1 步 · 全站接入（改动最小，收益最大）

131 个页面各加两行：

```html
<script src="../fluid-motion.js" defer></script>
<script>document.addEventListener('DOMContentLoaded', function(){ Fluid.autobind(); });</script>
```

然后给需要反馈的元素加属性，无需改 CSS：

```html
<div class="btn-neu-primary" data-fluid-press="0.94">立即预约</div>

<div id="timeSheet" class="sheet" data-fluid-sheet data-fluid-sheet-scrim="#scrim">…</div>
<div id="scrim" class="scrim"></div>
<button data-fluid-toggle="#timeSheet">选择时间</button>
```

运行时会自动完成：pointerdown 当帧起效、拖拽 1:1 跟随、松手速度移交、动量投射吸附、橡胶边界、`prefers-reduced-motion` 直接落位。

### 第 2 步 · 令牌修正

在 `colors_and_type.css` 的 `:root` 里改 4 个值（`--text-2`、`--text-3`、`--primary`、新增 `--accent-text`），并补上第六节的三段媒体查询。这一步是纯增益，不影响视觉风格。

### 第 3 步 · 性能优化

- `.tab-item` 的 `transition: all .2s` → `transition: color .2s, background-color .2s`
- 836 处 `backdrop-filter` 按层级分级（弹出层静止后降级）
- 常驻玻璃层加 `will-change: transform`

### 第 4 步 · 排版收敛

14 档字号收敛到 6 档，建立「字号 × 行高 × 字间距」联动表，186 处 11px 提到 12px。

### 优先级建议

**第 1、2 步先做**——第 1 步解决"不会动"，第 2 步解决"看不清"，这两项决定了产品的下限。第 3、4 步是打磨，可以渐进推进。

---

## 附：验收清单

改完后用这 7 条自查，全部通过才算达到 Apple 流体标准：

1. 手指按住元素的**同一帧**就有视觉反馈，不等抬起
2. 拖动抽屉时元素**完全贴住手指**，抓取点不跳
3. 抽屉下落到一半伸手按住，能**接住**并从当前位置继续
4. 快速轻扫一下就关闭，慢慢拖一半松开会**回弹**——同一套物理，不同输入不同结果
5. 拖过顶部时阻力**渐进变大**，不是硬卡住
6. 系统开启「减弱动效」后，所有动画变为瞬时切换，功能不受影响
7. 底部 tab 未选中态在**强光下**仍然清晰可辨
