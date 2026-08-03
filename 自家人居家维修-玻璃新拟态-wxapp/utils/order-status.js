// utils/order-status.js — 订单状态统一映射
// 后端状态码 → 中文文案 / chip 样式 / 操作按钮文案
// 用于订单列表、订单详情、追踪页

// 订单状态枚举（与后端 Order.status 对齐）
const STATUS = {
  PENDING:     'pending',       // 待接单（用户发布后等待师傅报价）
  BIDDING:     'bidding',       // 竞价中（多师傅报价中）
  ACCEPTED:    'accepted',      // 已选定师傅（待出发）
  DEPARTING:   'departing',     // 师傅已出发
  ARRIVED:     'arrived',       // 师傅已到达
  SERVING:     'serving',       // 服务中
  COMPLETED:   'completed',     // 待支付 / 服务已完工
  PAID:         'paid',          // 已支付，待评价（PRD v6.0）
  REVIEWED:     'reviewed',      // 已评价，流程完成（PRD v6.0）
  PENDING_REVIEW: 'pending_review', // 待评价
  CANCELED:    'canceled',      // 已取消
  CLOSED:      'closed'         // 已关闭
}

// 状态文案
const STATUS_TEXT = {
  pending:         '待接单',
  bidding:         '竞价中',
  accepted:        '已选定师傅',
  departing:       '师傅已出发',
  arrived:         '师傅已到达',
  serving:         '服务中',
  completed:       '待支付',
  paid:            '待评价',
  reviewed:        '已完成',
  pending_review:  '待评价',
  canceled:        '已取消',
  closed:          '已关闭'
}

// 状态 chip 样式（对应 app.wxss 中的 .chip-* 类）
const STATUS_CHIP = {
  pending:         'chip-warning',
  bidding:         'chip-danger',
  accepted:        'chip-info',
  departing:       'chip-info',
  arrived:         'chip-info',
  serving:         'chip-info',
  completed:       'chip-warning',
  paid:            'chip-warning',
  reviewed:        'chip-success',
  pending_review:  'chip-warning',
  canceled:        '',
  closed:          ''
}

// 用户端操作按钮文案
const CLIENT_ACTION_TEXT = {
  pending:        '查看报价',
  bidding:         '查看报价',
  accepted:        '联系师傅',
  departing:       '实时追踪',
  arrived:         '联系师傅',
  serving:         '联系师傅',
  completed:       '去支付',
  paid:            '去评价',
  reviewed:        '查看详情',
  pending_review:  '去评价',
  canceled:        '查看详情',
  closed:          '查看详情'
}

// 师傅端操作按钮文案
const WORKER_ACTION_TEXT = {
  pending:        '立即报价',
  bidding:        '查看详情',
  accepted:       '出发',
  departing:      '到达',
  arrived:        '开始服务',
  serving:        '完成服务',
  completed:      '等待支付',
  paid:           '查看评价',
  reviewed:       '查看详情',
  pending_review: '查看评价',
  canceled:       '查看详情',
  closed:         '查看详情'
}

// 追踪时间线节点（用户端追踪页）
const TRACKING_STEPS = [
  { key: 'accepted',  title: '师傅接单' },
  { key: 'departing', title: '师傅出发' },
  { key: 'arrived',   title: '师傅到达' },
  { key: 'serving',   title: '开始服务' },
  { key: 'completed', title: '服务完成' }
]

// 获取某个状态对应的时间线索引（0~4）
function getStepIndex(status) {
  const order = ['accepted', 'departing', 'arrived', 'serving', 'completed']
  const idx = order.indexOf(status)
  return idx === -1 ? 0 : idx
}

module.exports = {
  STATUS,
  STATUS_TEXT,
  STATUS_CHIP,
  CLIENT_ACTION_TEXT,
  WORKER_ACTION_TEXT,
  TRACKING_STEPS,
  getStepIndex
}
