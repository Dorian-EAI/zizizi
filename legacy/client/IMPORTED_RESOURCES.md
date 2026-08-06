# 复用资源说明

> 文档状态：历史资源来源说明（非产品、交互或视觉事实源）  
> 最近核对：2026-08-03 / 产品 v6.2  
> 当前视觉规范：[`../docs/design/样式规范详尽文档.md`](../docs/design/样式规范详尽文档.md)  
> 当前交互规范：[`../docs/design/功能与交互文档.md`](../docs/design/功能与交互文档.md)

本目录下资源从 `trae_projects/zijiarennn` 项目复用而来。该参考项目使用 **uni-app 框架**，编译产物（`mp-weixin/components/*.js`、`mp-weixin/utils/*.js`、`mp-weixin/pages/*`）不能直接复制到原生小程序。仅复制了以下**纯原生小程序源码与资源**。

## 资源清单

### 1. 设计令牌与全局样式

| 文件 | 用途 | 使用方式 |
|------|------|----------|
| `styles/design-v2.app.wxss` | 设计 v2 完整版（深邃蓝/紫 Hero + 白底卡片，含 CSS 变量 Token + 30+ 工具类） | 在 `app.wxss` 顶部 `@import "/styles/design-v2.app.wxss";`，或直接 merge 内容 |
| `styles/design-v1-stone.app.wxss` | 备用风格（stone/zinc 暖灰底 + indigo/teal/amber/rose/sky 五色系统，`.u-card/.u-tag/.u-btn` 命名空间） | 仅作设计参考，不直接生效 |
| `styles/*.reference.wxss` | AppTabbar/TabBar/index/mine/orders/publish 各页面样式参考 | 仅作样式参考 |

### 2. 组件（原生小程序源码）

#### `components/svg-icon/` — SVG 图标组件

```xml
<!-- 用法 -->
<svg-icon name="plumbing" color="blue" size="24"></svg-icon>
```

| 属性 | 类型 | 默认 | 说明 |
|------|------|------|------|
| name | String | `home` | 图标名（对应 `/assets/svg/<name>[_color].svg`） |
| color | String | `black` | `blue` / `purple` / `white` / `black` |
| size | Number | `24` | 图标尺寸（rpx = size × 2） |

#### `components/custom-tab-bar/` — 历史原生自定义 Tab Bar 参考

该组件来自旧参考项目，不是当前双端导航实现。当前正式实现以 `wxapp/components/tab-bar/` 为准：用户端为“首页/发布/订单/我的”，师傅端为“接单/订单/钱包/我的”。不要直接启用本组件覆盖正式导航。

启用方式（`app.json`）：
```json
{
  "tabBar": {
    "custom": true,
    "color": "#94a3b8",
    "selectedColor": "#2563eb",
    "list": [
      { "pagePath": "pages/index/index", "text": "首页" },
      { "pagePath": "pages/publish/publish", "text": "发布" },
      { "pagePath": "pages/orders/orders", "text": "订单" },
      { "pagePath": "pages/mine/mine", "text": "我的" }
    ]
  }
}
```
然后将 `components/custom-tab-bar/` 整个目录移到项目根目录的 `custom-tab-bar/`（微信小程序约定路径）。

### 3. 图标资源

| 目录 | 数量 | 说明 |
|------|------|------|
| `assets/svg/` | 200 个 | SVG 矢量图标，4 套配色（默认/blue/purple/white）<br>覆盖：plumbing/electric/appliance/carpentry/clean/pipeline/paint/wall/hammer/wrench/home/user/wallet/message/calendar/clock/location/heart/award/shield/sun/search/plus/check/phone/lock/settings/coupon/crown/document/droplet/gift/lightbulb/money/sofa/tasks/tv/zap 等 |
| `assets/tabbar/` | 8 个 | tabBar PNG 图标（home/orders/publish/mine × 2 态） |

### 4. 设计规范文档

| 文件 | 大小 | 说明 |
|------|------|------|
| `../docs/design/样式规范详尽文档.md` | 当前 | 完整设计规范：颜色、排版、组件、任务层级和页面规范等 |

## 不可复用的资源（已排除）

以下资源在原项目存在，但因为是 **uni-app 编译产物**而**未复制**：

- `mp-weixin/components/{AppTabbar,CouponCard,MacpawEmptyState,TabBar,UserNavBar,WorkerNavBar}.js` — 含 `require("../common/vendor.js")`，依赖 uni-app runtime
- `mp-weixin/utils/*.js` — 9 个工具文件均为压缩编译产物
- `mp-weixin/pages/*` — 所有页面 .js/.wxml 为编译产物（含 `data-v-xxx` scoped 属性、`{{a}}{{b}}` 简化变量绑定）
- `zjr/src/*.vue` — uni-app/Vue3 源码，与原生小程序技术栈不兼容

如需这些组件的功能，应**根据 wxml 编译产物的结构 + backup/styles_v1 中的样式**，重写为原生小程序组件。

## 设计风格说明

参考项目包含两套设计风格：

### Design v2（历史参考，不直接采用）
- 用户端：深邃蓝 `#1e3a8a → #2563eb → #60a5fa` 渐变 Hero
- 师傅端：深邃紫 `#312e81 → #6366f1 → #818cf8` 渐变 Hero
- 卡片：白底 + `--shadow-card: 0 2rpx 8rpx rgba(15, 23, 42, 0.04)` 克制阴影
- 标题：Georgia 衬线粗体 + 负字距（杂志风）
- 数字：Georgia 衬线超粗（金额/统计突出）
- 背景：`radial-gradient` 顶部柔光渐层

### Design v1（备用）
- 底色：stone-50 `#fafaf9` 米白暖色
- 四色主题：indigo/teal/amber/rose/sky
- 命名空间：`.u-card` `.u-tag` `.u-btn`（避免与现有类冲突）
- 风格参考：lilu-value-investing-30.html

## 下一步建议

1. **先核对正式规范**：任何复用都不得覆盖 v6.2 的双端导航、固定语义状态色和功能入口。
2. **按需接入 SvgIcon**：在页面 `.json` 中注册后使用；图标语义与无障碍名称必须符合正式规范。
3. **仅提取无业务含义的资源**：字体、通用图标和纯工具样式可评估复用；导航、订单卡和业务状态组件必须按当前原生小程序重写。
4. **禁止复制编译产物**：继续遵守本文件的排除清单。
5. **完成回归**：复用后验证用户端/师傅端身份、四项 Tab、长文案、大字体、空错态和低性能材质降级。
