// utils/order-actions.js — 兼容服务端 allowed_actions 的对象合同与旧字符串数组
function actionKeys(order) {
  const actions = Array.isArray(order && order.allowed_actions) ? order.allowed_actions : []
  return actions
    .map(item => {
      if (typeof item === 'string') return item
      if (item && item.enabled !== false) return item.key
      return ''
    })
    .filter(Boolean)
}

function hasAction(order, key) {
  if (!order || !key) return false
  const keys = Array.isArray(order.allowed_action_keys)
    ? order.allowed_action_keys
    : actionKeys(order)
  return keys.indexOf(key) >= 0
}

module.exports = {
  actionKeys,
  hasAction
}
