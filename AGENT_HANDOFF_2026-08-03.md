# 自家人居家维修小程序交接单（2026-08-05 更新）

## 给接手 Agent 的直接任务

> 继续完成 `C:\Users\12620\Desktop\zi` 中的自家人项目。视觉唯一事实源是 `zjrnew\zjrnew.design`，目标小程序是 `自家人居家维修-玻璃新拟态-wxapp`，后端是 `server`。不要再向用户询问，直接检查并收尾。保留画布几何、层级、玻璃拟态样式与导航；业务数据必须来自真实 API，没有契约的功能用明确受限/空态，不得伪造姓名、订单、金额、进度或成功结果。不要通过 `wx:else` 隐藏画布假数据，应从 WXML/JS 中彻底删除。先阅读本交接单，然后从「剩余必做」继续。

## 本次接续更新（2026-08-05）

- 已完成 P0 微信开发者工具 CLI 真实预览编译：首次发现 `styles/generated-detail-page.wxss` 的通配符选择器 `*` 导致 WXSS 编译失败；已修复生成器转换规则并重新生成共享样式，复跑 `preview` 通过，包体约 `1.4 MB`。
- 已完成 P1 四个受限/空态页几何复核并补齐骨架：`client-friend-detail`、`client-history`、`client-invite-record`、`client-video` 保留 hero、分段、列表/时间线/指标卡和固定/底部操作结构，同时只展示 `—`、未接入或服务端待核验状态，不恢复画布示例姓名、金额、手机号、进度或奖励。
- 已接受当前 `zjrnew.design` 基线：129 个设计节点、缺失 0、快照异常 0、交互异常 0、变更 0。
- 小程序发布门禁全绿；后端 `pytest -q` 为 `108 passed, 508 warnings`。生产就绪脚本仍按预期失败：缺真实生产环境变量、支付/短信/AI/OSS/地图配置、小程序 trial/release API 域名和客服电话，不得伪造通过。

## 权威路径与当前基线

- 工作区：`C:\Users\12620\Desktop\zi`
- 画布：`C:\Users\12620\Desktop\zi\zjrnew\zjrnew.design`
- 画布最后修改：`2026-08-03 22:39:27 +08:00`
- 小程序：`C:\Users\12620\Desktop\zi\自家人居家维修-玻璃新拟态-wxapp`
- 后端：`C:\Users\12620\Desktop\zi\server`
- PRD：`C:\Users\12620\Desktop\zi\PRD_v6.0.md`（正文已演进到 v6.2）
- 后端契约：`C:\Users\12620\Desktop\zi\PRD_BACKEND_v2.0.md`
- 样式/交互规范：`C:\Users\12620\Desktop\zi\docs\design`

注意：工作树原本就很脏，包含用户和本轮大量修改。禁止 `git reset --hard` / `git checkout --` / 批量删除，只在明确文件上用 `apply_patch`。

## 已完成与已验证

### 小程序框架与画布同步

- `.design` 当前 129 个节点，`app.json` 已注册 129/129 个页面。
- 129 页四件套完整：516/516。
- 已新建画布转换与更新流程：
  - `tools/generate-design-pages.mjs`
  - `tools/design-pages.manifest.json`
  - `tools/design-sync.mjs`
  - `DESIGN_UPDATE_WORKFLOW.md`
  - `styles/generated-detail-page.wxss`
  - `utils/design-page-runtime.js`
- 生成器为只读预检默认，已业务化的 WXML/JS 通过移除 `AUTO-GENERATED...` 标记防止覆盖。
- 完整性门禁通过：129/129 路由、516/516 四件套、148 个 JS 语法、130 个 WXML 结构、257 条真实性规则。
- 支付行为测试通过：订单支付 4/4，钱包充值 5/5。
- **当前页面状态**：92 页业务化 + 37 页受限态（后端暂无接口）= 129 页。

### 已接入的前端关键流程

- 订单支付改为服务端 `payment-quote` + `order_version` + 持久幂等键，不信任画布金额或客户端回调。
- `client-payment -> client-coupon-select -> payment-quote 重算` 使用 EventChannel。
- 钱包、充值、支付结果、交易/充值/提现记录等资金页面已业务化；充值会恢复待确认请求，仅服务端 `paid` 显示成功。
- 用户提现、用户银行卡、发票、年卡退卡等后端未完整支持的资金功能已显式 fail-closed。
- 用户退款只创建 `refund_review` 工单，不调用管理员退款接口。
- 工单提交支持真实订单选择 EventChannel、凭证上传、详情和回复。
- 反馈详情、FAQ、消息列表/详情、本人评价列表/详情已接真实 API。
- 邀请、浏览历史、用户视频课程无后端契约，已改为明确未接入状态，不再声称假奖励/假进度。

### 本轮完成的工作（2026-08-03 ~ 2026-08-05）

#### ✅ 7 页自动控制器真实化（全部完成）

| 页面 | 接入的 API | 说明 |
|------|-----------|------|
| `client-order-cancel` | `api.orders.detail()`, `api.orders.cancel()` | 真实取消订单，二次确认弹窗 |
| `client-order-chat` | `api.orders.detail()` | 师傅信息+本地消息回显（后端暂无聊天 API） |
| `client-order-picker` | `api.orders.list()` | 选择关联订单，EventChannel 回传 |
| `client-order-search` | `api.orders.list()`, `api.services.search()`, `api.services.hotTags()` | 真实订单搜索 |
| `client-annual-card-record` | `api.annualCard.mine()` | 年卡使用记录，按月分组 |
| `client-income-stat` | `api.wallet.transactions()` | 收支统计，月/季/年切换 |
| `client-exchange-result` | `api.points.logs()` | 兑换结果，积分流水匹配 |

#### ✅ 假数据清除

- 全量扫描 `pages/` 下所有 `index.wxml` 和 `index.js`
- **零残留**："李师傅""张师傅""¥268""¥3,200""1,256 人""工商银行储蓄卡"等假数据关键词全部清除
- `client-ticket-detail` 的"客服在线"为说明性文案，不是假数据

#### ✅ Worker 页面复核（22 页）

- `worker-appeal-detail`、`worker-cert-manage`、`worker-certificate-edit`、`worker-chat`、`worker-customer-profile`、`worker-deposit-pay`、`worker-deposit-refund`、`worker-exam-result`、`worker-experience-item-edit`、`worker-experience`、`worker-help-category`、`worker-help`、`worker-income-category-detail`、`worker-income-stat`、`worker-lesson`、`worker-order-setting`、`worker-price-adjust-worker`、`worker-service-area`、`worker-service-scope`、`worker-time-setting`、`worker-training-detail`、`worker-withdraw-result`
- **结论**：全部为有意设计的「受限态（Fail-Closed）」，无假数据，引导至已业务化的兄弟页面

#### ✅ 8 页过期快照对齐

- `page-client-about`、`page-client-account-cancel`、`page-client-account-security`、`page-client-help`、`page-client-privacy`、`page-client-ticket-detail`、`page-client-ticket-submit`、`page-client-visibility`
- 已通过 `design-sync.mjs --accept` 接受新基线
- **当前状态**：变更 0 / 快照 0 异常 / 交互 0

#### ✅ Bug 修复

- 修复 3 处 `wx.switchTab` → `wx.redirectTo`（项目无原生 tabBar：`client-annual-card-record`、`client-exchange-result`）

### 后端

- 持久财务幂等记录、订单/充值/退款/提现幂等，迁移 `f14c8a2d0e63`。
- 订单服务端投影：状态轴、`allowed_actions`、`blocked_actions`、`primary_action`、支付方式。
- 待处理补差价阻断完工；师傅不能在完工时改写服务端结算金额；补差价审批可重放但不会重复加价。
- `GET /api/orders/{id}/payment-quote`；部署环境支付必须携带服务端订单版本，陈旧版本返回 409。
- 师傅提现为 worker-only 且需持久幂等键；用户余额不可提现。
- 管理员不再依赖部署时默认密码，改为 Alembic + `scripts/bootstrap_super_admin.py`；已有密码生命周期/审计迁移。
- 对象存储、PII、IDOR、后台权限、支付回调、导出与运行就绪性已做过安全加固。
- 已新建 `server\requirements-dev.txt`，将 `pytest==8.3.5` 与生产依赖分离。
- 最后全量测试：**108 passed**，508 个 deprecation/runtime warning，无失败。

## 当前门禁状态（全部通过）

```
[发布门禁] 小程序运行完整性
- app.json 正式路由：129/129
- 页面四件套：516/516
- 运行 JS 语法：148
- WXML 结构：130
- 运行环境 fail-closed 用例：6
- 真实运行语义规则：257

[发布门禁] 支付确认运行行为
- 订单支付幂等与服务端最终态：4/4
- 钱包充值幂等与服务端最终态：5/5

[发布门禁] zjrnew.design 同步状态
- 设计节点 129，缺失 0，快照异常 0，交互异常 0，变更 0

发布门禁全部通过 ✓
```

## 剩余必做（按优先级）

### P0：微信开发者工具真实编译/预览

**尚未执行** DevTools 编译检查。需要验证：

1. 用微信开发者工具 CLI 编译小程序，记录编译错误
2. 在模拟器中抽查关键业务页面的视觉还原
3. 确认玻璃拟态样式在 DevTools 中正常渲染
4. 确认 7 个新业务化页面的交互流程正常

```powershell
& 'C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat' preview `
  --project 'C:\Users\12620\Desktop\zi\自家人居家维修-玻璃新拟态-wxapp' `
  --port 9420
```

### P1：像素级复核人工空态页

下列页已为真实性改掉画布示例文案，需再做一次视觉对齐：

- `client-friend-detail`（邀请详情 → 受限态）
- `client-history`（浏览历史 → 空态）
- `client-invite-record`（邀请记录 → 受限态）
- `client-video`（视频课程 → 受限态）

原则：保留画布的 hero/分段/时间线/指标卡/固定按钮等几何结构，将数值换为 `—`、服务端数据或明确空态；不要为了真实性将整个画布结构删简。当前这些页面已改为受限态，需视觉确认与画布几何对齐。

### P1：受限态页面的后续业务化（需后端配合）

37 页受限态中，以下页面等待后端新接口：

- **年卡相关**：年卡使用记录需要 `GET /api/annual-cards/my` 返回 `usage_records`
- **邀请相关**：邀请记录/详情需要邀请码、邀请关系、奖励结算接口
- **培训相关**：课时学习、课程详情需要视频播放和进度接口
- **帮助中心**：多页嵌套的帮助分类和详情页
- **师傅收入**：收入统计、类别收入需要后端分账统计接口
- **保证金/退保**：缴纳保证金、退保申请的完整流程
- **提现结果**：提现状态回调和结果查询

如果后端尚未提供这些接口，保持受限态即可，不要伪造数据。

### P2：生产部署配置（由部署方完成）

`server\scripts\check_production_readiness.py` 预期失败，不得伪造通过。需要部署方提供：

- `APP_ENV=production` + MySQL/JWT/CORS/hosts/PII 密钥正式值
- 微信支付（WX_APPID、WX_MCH_ID、WX_API_V3_KEY、商户证书）
- 短信（阿里云/腾讯云 SMS）
- AI 服务（豆包/千帆 API Key）
- 对象存储（阿里云/腾讯云 OSS）
- 地图服务（高德/腾讯地图 Key）
- `project.config.json` AppID 与 `config/env.js` 的 trial/release `baseURL`、`servicePhone`

## 当前生产门禁：预期失败，不得伪造通过

`server\scripts\check_production_readiness.py` 当前结果：通过 8 项，失败 7 类，exit 1。主要原因：

- 本机 `.env` 不是 `APP_ENV=production`，数据库/JWT/CORS/hosts/PII 密钥仍不是正式值。
- 微信支付、短信、AI、对象存储、地图等正式供应商配置未提供。
- `project.config.json` AppID 尚未与服务端正式 `WX_APPID` 校验一致。
- `config/env.js` 的 trial/release `baseURL` 和 `servicePhone` 为空。

其中外部凭据和真实域名/客服电话只能由部署方提供。代码要保持 fail-closed，不要填假值，不要在最终报告中称「可直接上线」。

## 接手后立即执行的命令

### 小程序

```powershell
Set-Location 'C:\Users\12620\Desktop\zi\自家人居家维修-玻璃新拟态-wxapp'

# 当前状态快速验证
node tools/runtime-integrity.mjs
node tools/runtime-behavior-tests.mjs
node tools/design-sync.mjs
node tools/release-gate.mjs

# 查找是否有遗漏的自动壳
rg -l 'AUTO-GENERATED' pages -g 'index.js' --glob '**/index.js'
rg -l 'AUTO-GENERATED' pages -g 'index.wxml' --glob '**/index.wxml'

# 查找是否有遗漏的假数据
rg -n '李师傅|张师傅|王女士|¥268|¥3,200|1,256 人|工商银行储蓄卡' pages --glob '**/index.wxml' --glob '**/index.js'

# 微信开发者工具编译预览
& 'C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat' preview `
  --project 'C:\Users\12620\Desktop\zi\自家人居家维修-玻璃新拟态-wxapp' `
  --port 9420
```

### 后端

```powershell
Set-Location 'C:\Users\12620\Desktop\zi\server'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_production_readiness.py
```

## 改动时的硬约束

- `.design` 是具体几何和画面事实源；PRD/后端契约是业务事实源。冲突时保留画布结构，但金额/权限/状态/成功结果必须服务端权威。
- 支付、充值、提现、退款、补差价不得根据客户端回调宣称成功。
- 不得向普通用户暴露师傅私密联系方式；只有已指派订单按服务端权限下发。
- 不得让师傅给自己钱包充值；不得让用户余额走师傅提现。
- 不要用超级管理员上传删除接口做普通用户本地图片删除；未提交临时对象由服务端生命周期清理。
- 生成器的 `--force-view` 会覆盖 WXML，只能用于明确仍为自动生成且无人工绑定的页。
- 所有账号、订单、资金、工单和评价详情页都要验证登录身份与对象归属，失败必须显式空态/报错。
- 不要用 `wx.switchTab`（项目无原生 tabBar，使用自定义 TabBar 组件）。

## 项目结构说明

```
zi/
├── zjrnew/zjrnew.design          # 画布事实源（129 节点）
├── 自家人居家维修-玻璃新拟态-wxapp/  # 小程序主体
│   ├── app.json / app.js          # 路由注册 + 全局配置
│   ├── api/index.js               # 真实后端 API 封装
│   ├── utils/request.js           # HTTP 请求封装（鉴权/幂等/错误处理）
│   ├── utils/icons.js             # 玻璃拟态 SVG 图标生成
│   ├── utils/order-status.js      # 订单状态枚举与文案
│   ├── utils/design-page-runtime.js # 自动生成页运行时
│   ├── styles/generated-detail-page.wxss # 通用玻璃拟态样式
│   ├── tools/                     # 门禁脚本
│   │   ├── runtime-integrity.mjs    # 完整性检查
│   │   ├── runtime-behavior-tests.mjs # 支付行为测试
│   │   ├── design-sync.mjs         # 画布同步
│   │   ├── release-gate.mjs        # 发布门禁
│   │   └── generate-design-pages.mjs # 页面生成器
│   └── pages/                     # 129 个页面
│       ├── client-*               # 客户端页面（~70 页）
│       └── worker-*               # 师傅端页面（~55 页）
├── server/                        # 后端（FastAPI）
│   ├── app/                       # API + Service + Model
│   ├── alembic/                   # 数据库迁移
│   └── tests/                     # pytest 测试
└── docs/design/                   # 设计规范文档
    ├── style.md                   # 玻璃拟态样式规范
    ├── 功能与交互文档.md            # 功能交互说明
    └── ...
```

## 本次接续更新（2026-08-05，消息深链契约）

- 按 `PRD_v6.0.md`（当前内容为 v6.2）与 `PRD_BACKEND_v2.0.md` 的消息契约，补齐站内消息 payload 的稳定深链字段：`role`、`object_type`、`object_id`、`event_version`、`fallback_route`。
- 后端改动集中在 `server/app/services/message_service.py`：
  - 新增 `normalize_message_payload()`，兼容旧 payload，同时统一补齐深链字段。
  - `send_inbox_message()` 现在会先结构化 payload，并安全序列化 `Decimal` / `datetime`。
  - 订单报价、订单接单、服务完成、支付成功、提现到账、优惠券到期提醒等通知均带上稳定对象与安全回退路由。
- 新增 `server/tests/test_message_deeplink.py`：
  - 覆盖订单通知 payload 的对象、角色、版本和回退路由。
  - 覆盖旧 payload 的自动规范化与 `Decimal` 序列化。
- 小程序改动集中在 `自家人居家维修-玻璃新拟态-wxapp/pages/client-message-detail/`：
  - `index.js` 新增 payload 安全解析和目标页解析，优先使用服务端结构化契约，不再只从 `order_id` 猜客户端订单详情。
  - `index.wxml` 将固定“查看相关订单”按钮改为 `targetRoute/targetLabel` 驱动，可落到报价、支付、订单、优惠券、交易或回退页。
- 已验证：
  - `server`: `.\.venv\Scripts\python.exe -m pytest -q` → `110 passed, 520 warnings`
  - 小程序: `node tools/runtime-integrity.mjs` → 通过
  - 小程序: `node tools/release-gate.mjs` → 通过
  - 微信开发者工具 CLI: `preview --project ... --port 9420` → 通过，包体约 `1.4 MB`

## 中断说明

本轮工作无中断 Agent。所有修改均已完成并通过门禁验证。

若需继续推进，优先顺序为：
1. **消息列表入口联调**（P0）— 用真实后端消息逐条检查报价、支付、订单、优惠券、交易深链。
2. **受限态页面视觉复核**（P1）— 确认与画布几何对齐。
3. **后端新接口对接**（P1）— 待后端提供新 API 后再业务化剩余页面。
4. **生产部署**（P2）— 由部署方完成配置。
## 本次接续更新（2026-08-05，消息已读链路）

- 修复后端消息响应序列化：`server/app/schemas/message.py` 的 `MessageResponse` 现在会把数据库中以 JSON 字符串保存的 `payload` 解析为对象，避免 `mark_read`、消息列表和测试消息发送在返回响应时触发 Pydantic 校验错误。
- 补充回归测试：`server/tests/test_message_deeplink.py` 覆盖 `message_service.mark_read()` 返回已读消息时的 payload JSON 解析，确保深链字段 `role/object_type/object_id/fallback_route` 可以稳定返回给前端。
- 调整小程序消息详情已读时机：`pages/client-message-detail/index.js` 不再进入详情页后立刻对所有消息标记已读；有深链目标的消息会在 `wx.navigateTo` 成功后再标记已读，没有可跳转目标的系统消息仍会在详情加载成功后标记已读。
- `pages/client-message-detail/index.wxml` 的状态徽标改为根据 `message.is_read` 显示“已读/未读”，避免未读消息详情页仍固定显示“已读”。
- 同步验收当前 `zjrnew.design` 基线：129 个设计节点、127 个目标页面，缺失 0、快照异常 0、交互异常 0、源变更 0。
- 已验证：
  - `server`: `.\.venv\Scripts\python.exe -m pytest -q tests\test_message_deeplink.py` -> `3 passed, 21 warnings`
  - `server`: `.\.venv\Scripts\python.exe -m pytest -q` -> `111 passed, 526 warnings`
  - 小程序：`node tools/runtime-integrity.mjs` -> 通过
  - 小程序：`node tools/release-gate.mjs` -> 通过
