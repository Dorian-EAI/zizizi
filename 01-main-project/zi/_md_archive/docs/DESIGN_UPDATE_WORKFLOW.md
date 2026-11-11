# zjrnew.design → 微信小程序更新流程

`zjrnew.design` 的当前 `data[]` 是页面范围、节点映射和已登记 HTML 快照的唯一画布事实源。生成器只处理明确引用 `assets/detail-page.css` 的页面，不会把未登记 HTML 自动扩进小程序。

## 日常检查

```powershell
node tools/generate-design-pages.mjs
node tools/design-sync.mjs
node tools/runtime-integrity.mjs
```

第一条是只读预检；`tools/design-pages.manifest.json` 记录当前设计 SHA、每页源哈希、目标路由和接入状态。`design-sync` 不会自动接受基线。

## 首次新增画布页面

```powershell
node tools/generate-design-pages.mjs --write --register
```

它会生成缺失页面四件套、更新共享 `styles/generated-detail-page.wxss`、注册 `app.json`，并刷新 manifest。已有业务 JS 不会被覆盖。

## 画布或 HTML 已修改

先让 `.design` 重新登记并确认其快照哈希无异常，再运行：

```powershell
node tools/generate-design-pages.mjs --write --refresh-generated
```

该命令只刷新仍带 `AUTO-GENERATED DESIGN VIEW` 标记、且源哈希确有变化的 WXML；业务化后移除 WXML 首行标记，即可保护人工数据绑定。共享 WXSS 会按 `detail-page.css` 更新，页面 JS 默认始终保留。

定向刷新可用：

```powershell
node tools/generate-design-pages.mjs --write --force-view --only=client-about,worker-help
```

`--force-view` 会覆盖指定页的 WXML/WXSS，只应在确认没有未合并人工视图改动时使用。

## 业务接入约束

- 自动生成 JS 默认让未接入契约的 `data-action` 明确失败关闭，不模拟成功。
- 页面接入真实 API 后，移除 JS 首行 `AUTO-GENERATED PAGE CONTROLLER` 标记，并在 manifest/评审记录中标明真实化状态。
- 支付、提现、退款、补差价等结果只认服务端终态；不得根据客户端回调或静态画布文案宣称成功。
- 完成后运行 `node tools/release-gate.mjs`。只有设计同步、运行完整性和支付行为全部通过，才进入微信开发者工具人工视觉验收。
