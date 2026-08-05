# 自家人居家维修平台

自家人是面向家庭维修场景的竞价式 O2O 平台：用户发布上门需求，认证师傅报价，用户自主选择；平台提供实时追踪、支付结算、补差价、保险/保证金、评价与售后工单。

> 当前业务基线为 **v6.2**。主 PRD 因兼容历史链接仍命名为 [`PRD_v6.0.md`](./PRD_v6.0.md)，文件正文已明确为 v6.2；它是本仓库唯一业务事实源。

## 产品形态

同一个微信账号可以拥有用户和师傅两个身份，角色切换不退出登录：

- 用户端已开通师傅身份时：**我的 > 切换到师傅工作台**；
- 用户端未开通师傅身份时：**我的 > 申请成为师傅**；
- 师傅端：**我的 > 切换到找服务**。

管理员不属于小程序角色。仓库内置的 `/admin` SPA 只供开发/测试联调；体验和正式环境强制 `ENABLE_BUILTIN_ADMIN=false`，应部署独立构建并受同源、鉴权和审计保护的 Web 管理后台。

| 端 | 四个根 Tab | 核心任务 |
|---|---|---|
| 用户端 | 首页 / 发布 / 订单 / 我的 | 三步竞价发布、选师傅、追踪、支付、评价、售后 |
| 师傅端 | 接单 / 订单 / 钱包 / 我的 | 准入、报价、履约、定位、补差价、结算、提现 |
| 管理后台 | 独立 Web，无小程序 Tab | 审核、订单、售后、提现、内容和数据运营；生产不使用内置调试 SPA |

v6.2 只定义竞价发布；一口价、悬赏、指定师傅直接成交、支付宝/银行卡直付、师傅收入钱包充值/互转和小程序管理员角色不在本版本范围。

## 文档入口与权威层级

发生冲突时按以下顺序处理：

1. [产品需求文档 v6.2](./PRD_v6.0.md)：业务范围、角色、状态、权限、资金和验收的唯一事实源；文件名为兼容路径。
2. [功能与交互文档](./docs/design/功能与交互文档.md)：入口、操作、反馈、返回和异常恢复。
3. [样式规范](./docs/design/样式规范详尽文档.md)：视觉 Token、组件、布局、动效边界和可访问性。
4. [后端目标契约](./PRD_BACKEND_v2.0.md)：经评审的数据、接口、并发、迁移和安全字段；不得反向改变产品规则。
5. [`zjrnew.design`](./zjrnew/zjrnew.design)：已登记页面的具体几何和画面，仅表达视觉状态。
6. 实施清单、运行手册、代码和 OpenAPI：说明当前实现；缺口应登记，不能据此删除需求。

| 文档 | 职责 |
|---|---|
| [产品需求文档 v6.2](./PRD_v6.0.md) | 产品规则与验收 |
| [功能与交互文档](./docs/design/功能与交互文档.md) | 全功能入口、流程、反馈与恢复 |
| [样式规范](./docs/design/样式规范详尽文档.md) | 统一设计系统与页面视觉规则 |
| [后端目标契约](./PRD_BACKEND_v2.0.md) | 后端目标数据与技术合同 |
| [实施状态与上线清单](./实施状态与上线清单.md) | 当前能力、缺口、配置、发布与回滚 |
| [小程序动画与布局实现规范](./zjrnew/小程序动画与布局实现规范.md) | 特殊滚动态、固定层级和微信运行时实现 |
| [需求完成对照](./zjrnew/需求完成对照.md) | 分开记录设计、实现与可用性证据 |
| [数据库迁移规范](./server/alembic/README.md) | Alembic 高风险操作手册 |
| [后端测试规范](./server/tests/README.md) | 测试运行、安全和覆盖缺口 |
| [运行时与对象存储上线说明](./server/运行时与对象存储上线说明.md) | 并发、调度、资金幂等、OSS/COS 删除和生命周期边界 |
| [画布同步流程](./自家人居家维修-玻璃新拟态-wxapp/样式画布同步流程.md) | 画布迁移、截图验收和基线接受条件 |
| [真实接口联调](./自家人居家维修-玻璃新拟态-wxapp/运行环境与真实接口联调.md) | 环境隔离、Mock 开关、联调链路和门禁 |
| [设计同步报告](./自家人居家维修-玻璃新拟态-wxapp/DESIGN_SYNC_REPORT.md) | 工具自动生成的当前视觉一致性结果，禁止手工维护 |
| [历史资源来源](./client/IMPORTED_RESOURCES.md) | 旧客户端资源溯源与禁止复用范围 |

业务变化先改主 PRD，再依次同步交互、样式、后端合同、实现和测试；自动报告只由工具生成。已失效的历史方案不留在活动文档中，避免被误当成当前需求。

## 仓库结构

```text
zi/
├── server/                         FastAPI 后端、ORM、调度任务、Web 管理后台
│   ├── run.py                      服务启动、并发与环境边界入口
│   ├── .env.example               配置模板
│   ├── app/                        API、模型、服务、任务和静态后台
│   └── tests/                      权限、状态机、支付幂等、短信和迁移测试
├── 自家人居家维修-玻璃新拟态-wxapp/ 当前微信小程序运行代码
│   ├── app.json                    小程序注册页唯一事实源（数量随画布迁移动态变化）
│   ├── config/env.js               开发/体验/正式环境隔离
│   ├── pages/                      用户与师傅页面
│   └── tools/design-sync.mjs       画布变更门禁
├── client/                         旧小程序实现，仅作历史参考
├── docs/design/                    功能交互和样式规范
├── zjrnew/zjrnew.design            已登记页面的具体视觉画布
├── zjrnew/pages/                   画布登记渲染源，不代表业务已完成
├── PRD_v6.0.md                    PRD v6.2（兼容文件名）
└── README.md
```

视觉 Token、组件和状态规则以样式规范为准；已登记页面的具体几何与画面以评审后的 `zjrnew/zjrnew.design` 为准。产品是否可运行以目标 wxapp、`server/` 和主 PRD 的验收结果为准。

## 本地启动

### 前置条件

- Python 3.12（当前发布依赖的干净环境验证基线）；
- 微信开发者工具；
- 本地快速体验可使用 SQLite；生产迁移与发布演练使用 MySQL 8；
- 真实微信登录、支付、短信、对象存储和路线 ETA 需要各平台配置。

### Windows PowerShell

```powershell
Set-Location server
Copy-Item .env.example .env

py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 编辑 .env：本地快速体验至少将 DB_DRIVER 改为 sqlite
# APP_DEBUG=true 时才开放 Swagger / ReDoc
& .\.venv\Scripts\python.exe run.py
```

### macOS / Linux

```bash
cd server
cp .env.example .env

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 编辑 .env：本地快速体验至少将 DB_DRIVER 改为 sqlite
# APP_DEBUG=true 时才开放 Swagger / ReDoc
.venv/bin/python run.py
```

`run.py` 仅在 `development/testing` 自动建表并写入本地种子数据。`staging/production` 不执行 `create_all`、不自动 seed，数据库必须先显式执行 `alembic upgrade head`，且启动时会动态比较数据库 revision 与代码的 Alembic head，不一致就拒绝启动。

生产首个超级管理员只能在迁移完成且 `admins` 表为空时，使用一次性脚本创建；密码通过隐藏输入或 Secret Manager 管道传入，不写日志：

```powershell
Set-Location server
& .\.venv\Scripts\python.exe scripts\bootstrap_super_admin.py --username <生产管理员账号>
```

该脚本录入的是首个超级管理员的最终密码。之后通过 API 创建或重置的管理员会被标记为“必须首次改密”，除改密接口外不能访问后台；改密后所有旧管理员 Token 立即失效。

### 启动后地址

| 地址 | 用途 |
|---|---|
| `http://localhost:8000/health` | 健康检查 |
| `http://localhost:8000/docs` | Swagger，要求 `APP_DEBUG=true` |
| `http://localhost:8000/redoc` | ReDoc，要求 `APP_DEBUG=true` |
| `http://localhost:8000/admin` | 仅 `development/testing` 且 `ENABLE_BUILTIN_ADMIN=true` 时使用的内置联调后台 |

### 打开微信小程序

1. 用微信开发者工具打开 [`自家人居家维修-玻璃新拟态-wxapp/`](./自家人居家维修-玻璃新拟态-wxapp)；
2. 在 [`config/env.js`](./自家人居家维修-玻璃新拟态-wxapp/config/env.js) 配置对应环境的 `baseURL`；
3. 本机开发者工具可使用 `http://localhost:8000`；真机需使用可访问的 HTTPS 域名并配置小程序 request 合法域名；
4. 使用真实微信能力前配置 `WX_APPID/WX_SECRET` 等环境变量。

### 运行后端测试

```powershell
Set-Location server
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS / Linux 将 Python 路径替换为 `.venv/bin/python`。当前回归套件使用 Python 标准库 `unittest`。

发布候选版本还应在全新的 Python 3.12 虚拟环境安装锁定依赖并执行依赖一致性检查，不能用长期复用的开发环境代替：

```powershell
Set-Location server
py -3.12 -m venv .venv-release
& .\.venv-release\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-release\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv-release\Scripts\python.exe -m pip check
& .\.venv-release\Scripts\python.exe -m unittest discover -s tests -v
```

## 常用配置

完整配置见 [`server/.env.example`](./server/.env.example)。

| 配置 | 本地建议 | 生产要求 |
|---|---|---|
| `APP_ENV` | `development` | 体验 `staging` / 正式 `production`；两者使用同一安全门禁 |
| `APP_DEBUG` | `true` | `false` |
| `ENABLE_BUILTIN_ADMIN` | `true` 可用于本地联调 | 必须 `false`，另行部署生产管理前端 |
| `DB_DRIVER` | `sqlite` | 必须 `mysql` |
| `SQLITE_PATH` | `./zjr_repair.db` | 不建议用于生产 |
| `JWT_SECRET_KEY` | 可用本地随机值 | 非默认高强度密钥 |
| `ADMIN_DEFAULT_PASSWORD` | 仅用于本地种子账号 | 部署环境忽略；首个管理员通过 bootstrap 的隐藏输入创建 |
| `WX_PAY_MOCK_ENABLED` | `true` | 必须 `false` |
| `MAP_PROVIDER` | `local` | 必须 `amap` / `tencent`，禁止直线距离降级 |
| `AI_PROVIDER` | `mock` | 必须 `doubao` / `qwen` 并提供真实配置 |
| `SMS_PROVIDER` | `mock` | `aliyun` / `tencent` |
| `OSS_PROVIDER` | `local` | 必须 `aliyun` / `tencent`，禁止本地存储降级 |
| `CERTIFICATE_PRIVATE_STORAGE` | 本地联调可关闭 | 必须 `true`，证件对象使用私有 ACL 和短签名 URL |
| `OBJECT_STORAGE_LIFECYCLE_CONFIRMED` | `false` | 完成版本、分片、保留/清理演练后才可设为 `true` |
| `WEB_CONCURRENCY` | 热重载时必须 `1` | 依据容量设置 1–32，并验证 Redis 调度锁 |
| `SCHEDULER_ENABLED` | 可按联调需要开关 | 多进程/多副本共用 Redis；也可仅在独立 scheduler 实例开启 |
| `CORS_ORIGINS`、`ALLOWED_HOSTS` | 按本地需要 | 必须显式白名单 |

开发环境可使用 mock/local 方便联调，但不得把 mock 支付、未发送短信或直线距离标记为生产真实成功。

## 当前技术基线

| 层 | 实现 |
|---|---|
| 小程序 | 原生 WXML/WXSS/JS |
| 后端 | FastAPI 0.115、SQLAlchemy 2、Pydantic 2 |
| 数据库 | MySQL / SQLite 本地模式 |
| 调度 | APScheduler；当前启动注册 12 类任务，每次执行使用 Redis 所有者令牌锁去重 |
| 缓存与限流 | Redis；开发能力可降级，体验/生产在就绪、令牌失效、限流和任务锁上失败关闭 |
| 支付 | 微信支付 API v3、余额及相关账务基础 |
| 地图 | 微信地图 + 高德/腾讯 REST，local 模式使用直线距离 |
| 通知 | 站内消息、微信订阅消息、可选短信 |
| 对象存储 | 阿里云 OSS / 腾讯云 COS；证件私有 ACL、短签名读取、受管 key 删除和持久化审计 |
| 管理后台 | `/admin` 为本地联调 SPA；体验/生产必须部署独立管理前端 |

后端当前覆盖认证、订单竞价、服务、实时追踪、地图、钱包/微信支付、优惠券、年卡、积分、会员、收藏、保险、保证金、补差价、质检、培训、工单、消息、反馈、短信、AI、财务、导出和管理后台。精确路由与字段以运行时 OpenAPI 为准。

## 当前实现边界

以下描述用于避免把“有页面/有接口”误认为“已按 v6.2 验收”。

### 已有基础

- 后端已有用户与师傅资料、两类登录、角色切换 API 和对象级鉴权基础；
- 已有竞价下单、选师傅、出发/到达/开工/完工、定位追踪和评价主链路；
- 已有钱包/微信支付、退款基础、补差价、保险理赔、客服工单、保证金、培训、权益和消息模块；
- `app.json` 是注册页数量的唯一事实源。最新一次重读时仍注册 44 页：42 个既有视觉目标、入口和搜索两个辅助页面；其中已包含登录授权、在线客服、积分中心、邀请奖励、确认支付、服务评价、差价确认 7 个此前新增页面；
- `zjrnew.design` 已再次扩展为 129 个节点、127 个唯一小程序目标。当前自动报告仅完成 44/129 个节点映射，85 个节点对应目标仍缺失；快照哈希异常为 0，但有 131 个基线后变更，尚未完成视觉迁移与验收；在批量实现、注册、截图比对和人工确认前不得执行 `--accept` 或发布；
- 钱包充值、JSAPI 充值、钱包/JSAPI 订单支付和退款发起均支持持久化 `Idempotency-Key`；体验/生产缺键返回 428，同键改请求返回 409；
- 师傅收入钱包充值与互转在客户端无真实动作，服务端对师傅令牌的充值请求返回 403；`worker-recharge` 仅保留为历史画布对照页；
- 生产不自动建表、seed 或创建默认管理员；Alembic head、管理员密码生命周期、支付幂等、订单状态并发、权限、短信验证和迁移已有专项检查；
- OSS/COS 删除只允许超级管理员删除服务端受管 key，并记录持久化审计；证件材料强制私有存储和短签名读取。

### 仍需按 v6.2 收口

- 同账号双角色目前仍由用户表、师傅表和角色字段拼接，需完成角色范围 Token、动态师傅四 Tab和前端切换闭环；
- 订单接口尚未完整返回履约、支付、售后、补差价四轴状态、资金桶和 `allowed_actions`；
- 已接单后的取消、争议、退款/理赔编排及全部结果页/消息深链需继续补齐；
- 客户端已按当前 API 契约接入真实登录、上传、支付状态查询、订单、服务、客服与双角色页面；仍需在真实微信账号和外部供应商环境完成异常、回调、页面栈恢复与消息深链的端到端验收；
- 搜索、消息中心、选择页返回协议、登录后续办和跨角色页面栈恢复仍需统一验收；
- 外部服务未配置时仅开发环境可使用 mock/local；生产环境失败关闭，不能视为生产可用。

### 不应从原型带入正式实现

- 一口价、悬赏、指定师傅直接成交；
- 用户“确认到达”或独立“待验收”主状态；
- 补差价超时自动同意或“同意并立即支付”；
- 支付宝、银行卡直付；
- 师傅收入钱包充值或师傅间转账（保证金使用独立缴纳流程）；
- 订单消息进入 AI 会话；
- 二级详情页继续显示根 Tab；
- 小程序内管理员入口。

## 核心业务流程

```text
用户三步发布竞价单
    ↓
合格师傅提交报价 → 用户选择有效报价 → 服务端原子进入“已接单”
    （师傅无需二次确认接单）
    ↓
师傅出发 → 实时追踪 → 到达 → 开工 → 完工
    ↓
用户确认明细并支付 / 报告问题
    ↓
平台记账与师傅结算 → 用户评价 / 售后
```

具体状态、`allowed_actions`、补差价、支付、结算和售后规则请直接查阅[产品需求文档 v6.2](./PRD_v6.0.md)。

## 生产上线提醒

可执行的配置、测试和自动门禁见[实施状态与上线清单](./实施状态与上线清单.md)，真实接口链路见[真实接口联调](./自家人居家维修-玻璃新拟态-wxapp/运行环境与真实接口联调.md)，设计、实现与可用性完成度见[需求完成对照](./zjrnew/需求完成对照.md)。

- 禁止使用默认 JWT、管理员密码、mock 支付和宽泛 CORS/Host 配置；
- 微信支付回调、退款回调和订阅消息必须在正式环境验证；
- 用户钱包/JSAPI 充值、钱包/JSAPI 订单支付及管理员退款必须携带并在重试/恢复期间复用 `Idempotency-Key`；
- 数据库迁移、备份恢复、金额对账、权限越权和重复请求必须通过发布门槛；
- 私有 OSS/COS 上传、短签名读取、受管 key 删除、删除审计和生命周期规则必须在测试 bucket 演练；
- 生产依赖必须在干净 Python 3.12 环境完成安装、`pip check` 和全量回归；
- 精确位置、身份证、手机号、地址和聊天内容不得进入普通日志或分析埋点；
- 管理员凭据和真实密钥只放安全配置，不写入 README、代码或提交记录。

仓库当前仍有两类发布阻断：129 节点画布尚有 85 个节点对应目标未迁移，设计基线未验收；体验版/正式版 API 地址与客服电话、后端微信/支付、MySQL、Redis、短信、对象存储、地图、AI、证书和生产管理前端尚未由部署方提供并完成演练。因此当前发布门禁应保持失败，这些内部验收和外部条件未满足前不得描述为“已上线”。
