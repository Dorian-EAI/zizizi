// utils/order-status.js — 订单状态统一映射
// 后端状态码 → 中文文案 / chip 样式 / 操作按钮文案
// 用于订单列表、订单详情、追踪页

const { actionKeys } = require('./order-actions')

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

const PAYMENT_LABEL = {
  unpaid: '待支付',
  processing: '支付确认中',
  paid: '已支付',
  failed: '支付失败',
  refunding: '退款处理中',
  refunded: '已退款'
}

const AFTERSALE_LABEL = {
  requested: '售后待处理',
  processing: '售后处理中',
  resolved: '售后已解决',
  rejected: '售后未通过',
  appealing: '售后申诉中'
}

const CANCEL_LABEL = {
  pending: '取消申请待处理',
  rejected: '取消申请未通过',
  withdrawn: ''
}

const ACTION_TEXT = {
  confirm_and_pay: '去支付',
  review_order: '去评价',
  track_worker: '实时追踪',
  view_bids: '查看报价',
  select_worker: '选择师傅',
  handle_extra_fee: '处理差价',
  view_cancel_request: '查看取消申请',
  request_cancel: '申请取消',
  cancel_order: '取消订单',
  open_dispute: '报告问题',
  contact_worker: '联系师傅',
  contact_user: '联系用户',
  contact_support: '联系客服',
  reorder: '再次发布',
  depart_order: '出发',
  arrive_order: '到达',
  start_service: '开始服务',
  complete_service: '完工',
  apply_extra_fee: '申请差价',
  view_settlement: '查看结算',
  reply_review: '回复评价'
}

const CLIENT_ACTION_PRIORITY = [
  'confirm_and_pay',
  'review_order',
  'track_worker',
  'view_bids',
  'select_worker',
  'handle_extra_fee',
  'view_cancel_request',
  'request_cancel',
  'open_dispute',
  'contact_worker',
  'reorder',
  'cancel_order',
  'contact_support'
]

const WORKER_ACTION_PRIORITY = [
  'depart_order',
  'arrive_order',
  'start_service',
  'complete_service',
  'apply_extra_fee',
  'reply_review',
  'view_settlement',
  'contact_user',
  'contact_support'
]

function normalizeStatus(status) {
  return status === 'cancelled' ? 'canceled' : status
}

function deriveOrderView(order, role) {
  const raw = order || {}
  const serviceState = raw.service_state || raw.status || 'pending'
  const paymentState = raw.payment_state || ''
  const aftersaleState = raw.aftersale_state || 'none'
  const cancelState = raw.cancel_request_state || 'none'
  const priceAdjustState = raw.price_adjust_state || 'none'

  let statusText = STATUS_TEXT[normalizeStatus(serviceState)] || raw.status_text || ''
  if (cancelState === 'pending') {
    statusText = CANCEL_LABEL.pending
  } else if (AFTERSALE_LABEL[aftersaleState]) {
    statusText = AFTERSALE_LABEL[aftersaleState]
  } else if (paymentState === 'processing') {
    statusText = '支付确认中'
  } else if (paymentState === 'failed') {
    statusText = '支付失败'
  } else if (paymentState === 'refunding') {
    statusText = '退款处理中'
  } else if (paymentState === 'refunded') {
    statusText = '已退款'
  } else if (serviceState === 'completed' && paymentState === 'unpaid') {
    statusText = '待支付'
  } else if (serviceState === 'reviewed' && paymentState === 'paid') {
    statusText = '已完成'
  }

  const keys = actionKeys(raw)
  const priority = role === 'worker' ? WORKER_ACTION_PRIORITY : CLIENT_ACTION_PRIORITY
  let actionKey = ''
  for (let i = 0; i < priority.length; i += 1) {
    if (keys.indexOf(priority[i]) >= 0) {
      actionKey = priority[i]
      break
    }
  }
  if (!actionKey && keys.length) actionKey = keys[0]

  const axisTags = []
  if (paymentState === 'processing' || paymentState === 'failed' || paymentState === 'refunding' || paymentState === 'refunded') {
    axisTags.push(PAYMENT_LABEL[paymentState])
  }
  if (aftersaleState !== 'none' && AFTERSALE_LABEL[aftersaleState]) {
    axisTags.push(AFTERSALE_LABEL[aftersaleState])
  }
  if (CANCEL_LABEL[cancelState]) {
    axisTags.push(CANCEL_LABEL[cancelState])
  }
  if (priceAdjustState === 'pending') {
    axisTags.push('待处理差价')
  }

  return {
    statusText,
    statusClass: STATUS_CHIP[normalizeStatus(serviceState)] || '',
    actionKey,
    actionText: ACTION_TEXT[actionKey] || '查看详情',
    axisTags
  }
}

module.exports = {
  STATUS,
  STATUS_TEXT,
  STATUS_CHIP,
  CLIENT_ACTION_TEXT,
  WORKER_ACTION_TEXT,
  TRACKING_STEPS,
  getStepIndex,
  deriveOrderView
}
