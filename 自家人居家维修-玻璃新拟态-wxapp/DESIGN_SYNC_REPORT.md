# zjrnew.design 强一致性报告

> 自动生成的视觉同步报告；适用产品规则 v6.2。  
> 业务规则以 PRD 为准；交互与样式规范定义体验和视觉系统，评审后的 `../zjrnew/zjrnew.design` 表达已登记页面的具体画面。  
> “通过”只表示画布节点、登记渲染源、目标四件套与辅助视觉令牌一致，不表示路由、按钮、接口或完整用户任务可用。

- 设计节点：37
- 小程序目标页面：35
- 节点映射完整：37/37
- 画布快照哈希异常：0
- 无效交互目标：0
- 核心令牌差异：0
- 基线后变更文件：4
- 功能可用性：本报告不评估，须按 PRD 与交互文档单独验收

## 检测到的源变更（未验收 / 未接受基线）

> 下列文件相对已接受基线发生变化。本报告只检测，不代表已完成视觉迁移，也不会自动接受新基线。

- `zjrnew.design` — 已登记页面的具体画面来源
- `pages/client-order-tracking.html` — 画布登记渲染源
- `../docs/design/样式规范详尽文档.md` — 样式规范事实源（需与评审画布一致）
- `小程序动画与布局实现规范.md` — 小程序特殊动效与布局实现规范

## 设计节点映射

| Design ID | 标题 | HTML 源 | 画布 | 小程序目标 | 校验 |
|---|---|---|---:|---|---|
| `page-client-mine` | 客户端我的 | `pages/client-mine.html` | 375×900 | `pages/client-mine` | 通过 |
| `page-client-orders` | 客户端订单 | `pages/client-orders.html` | 375×900 | `pages/client-orders` | 通过 |
| `page-client-publish` | 客户端发布 | `pages/client-publish.html` | 374×900 | `pages/client-publish` | 通过 |
| `page-client-home-glass-neu` | 客户端首页 下拉后页面 | `pages/client-home-glass-neu.html` | 374×900 | `pages/client-home` | 通过 |
| `page-client-service-detail` | 服务详情 | `pages/client-service-detail.html` | 374×900 | `pages/client-service-detail` | 通过 |
| `page-client-order-detail` | 订单详情 | `pages/client-order-detail.html` | 375×900 | `pages/order-detail-client` | 通过 |
| `page-client-quote-list` | 报价列表 | `pages/client-quote-list.html` | 375×900 | `pages/client-quote-list` | 通过 |
| `page-client-address` | 地址管理 | `pages/client-address.html` | 375×900 | `pages/address` | 通过 |
| `page-client-coupon` | 优惠券 | `pages/client-coupon.html` | 375×900 | `pages/client-coupon` | 通过 |
| `page-client-settings` | 设置 | `pages/client-settings.html` | 374×900 | `pages/client-settings` | 通过 |
| `page-worker-home` | 师傅端接单大厅 | `pages/worker-home.html` | 375×900 | `pages/worker-home` | 通过 |
| `page-worker-orders` | 师傅端订单管理 | `pages/worker-orders.html` | 375×900 | `pages/worker-orders` | 通过 |
| `page-worker-profile` | 师傅端个人中心 | `pages/worker-profile.html` | 375×900 | `pages/worker-profile` | 通过 |
| `page-worker-wallet` | 师傅端钱包 | `pages/worker-wallet.html` | 375×900 | `pages/worker-wallet` | 通过 |
| `page-worker-quote-submit` | 提交报价 | `pages/worker-quote-submit.html` | 375×900 | `pages/worker-quote-submit` | 通过 |
| `page-worker-order-detail` | 师傅订单详情 | `pages/worker-order-detail.html` | 375×900 | `pages/order-detail-worker` | 通过 |
| `page-worker-withdraw` | 提现 | `pages/worker-withdraw.html` | 375×900 | `pages/worker-withdraw` | 通过 |
| `page-worker-transactions` | 收支明细 | `pages/worker-transactions.html` | 375×900 | `pages/worker-transactions` | 通过 |
| `page-worker-reviews` | 评价管理 | `pages/worker-reviews.html` | 375×900 | `pages/worker-reviews` | 通过 |
| `page-worker-settings` | 师傅设置 | `pages/worker-settings.html` | 375×900 | `pages/worker-settings` | 通过 |
| `page-client-chat` | AI智能助手 | `pages/client-chat.html` | 374×900 | `pages/client-chat` | 通过 |
| `page-client-member` | 会员中心 | `pages/client-member.html` | 375×900 | `pages/client-member` | 通过 |
| `page-client-favorite-workers` | 收藏的师傅 | `pages/client-favorite-workers.html` | 375×900 | `pages/client-favorite-workers` | 通过 |
| `page-client-service` | 客服中心 | `pages/client-service.html` | 374×900 | `pages/client-service` | 通过 |
| `page-client-feedback` | 意见反馈 | `pages/client-feedback.html` | 374×900 | `pages/client-feedback` | 通过 |
| `page-client-annual-card` | 家庭年卡 | `pages/client-annual-card.html` | 375×900 | `pages/client-annual-card` | 通过 |
| `page-client-insurance-claim` | 理赔申请 | `pages/client-insurance-claim.html` | 374×900 | `pages/client-insurance-claim` | 通过 |
| `page-worker-recharge` | 师傅充值 | `pages/worker-recharge.html` | 374×900 | `pages/worker-recharge` | 通过 |
| `page-worker-certification` | 资质认证 | `pages/worker-certification.html` | 374×900 | `pages/worker-certification` | 通过 |
| `page-worker-deposit` | 保证金管理 | `pages/worker-deposit.html` | 374×900 | `pages/worker-deposit` | 通过 |
| `page-worker-training` | 培训中心 | `pages/worker-training.html` | 375×900 | `pages/worker-training` | 通过 |
| `page-worker-training-exam` | 在线考试 | `pages/worker-training-exam.html` | 374×900 | `pages/worker-training-exam` | 通过 |
| `page-worker-appeal` | 申诉中心 | `pages/worker-appeal.html` | 375×900 | `pages/worker-appeal` | 通过 |
| `page-client-order-tracking` | 实时追踪 | `pages/client-order-tracking.html` | 374×900 | `pages/client-order-tracking` | 通过 |
| `page-worker-location-report` | 位置上报 | `pages/worker-location-report.html` | 374×900 | `pages/worker-location-report` | 通过 |
| `page-client-order-tracking-2` | 实时追踪 下拉页面 | `pages/client-order-tracking-2.html` | 375×900 | `pages/client-order-tracking` | 通过 |
| `page-client-home-glass-neu-contrast-1` | 客户端首页 | `pages/client-home-glass-neu-contrast-1.html` | 374×900 | `pages/client-home` | 通过 |

## 强校验异常

- `.design` sourceHash 与 HTML 全部一致

## 报告边界

- 业务规则唯一事实源：`../PRD_v6.0.md`（正文 v6.2）。
- 入口、操作与异常恢复以 `../docs/design/功能与交互文档.md` 为准；Token、组件、布局规则与动效边界以 `../docs/design/样式规范详尽文档.md` 为准。
- 评审后的 `../zjrnew/zjrnew.design` 表达已登记页面的具体几何与画面；若与上级规范冲突，暂停同步并先完成评审和源文件修订。
- `../zjrnew/小程序动画与布局实现规范.md`、HTML/CSS 与小程序代码是特殊动效、布局或运行实现，不得自行反向修改规范或画布。
- `.design` 的交互元数据只用于视觉热点和页面映射；按钮权限、状态迁移、支付与资金结果仍以 PRD 和服务端契约为准。
- `page-worker-recharge` 是历史视觉节点：v6.2 不开放师傅收入钱包充值，节点“通过”不代表可注册入口或支付动作。
- 首页与实时追踪的两个节点是同一页面的滚动状态，不是两条产品路由。
- 正式发布还必须验证双角色切换、双端四项 Tab、稳定入口、订单多轴状态、AI/订单聊天/人工客服分流、权限、支付、位置和资金闭环。
