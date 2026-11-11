// 资金写操作幂等键：同一次用户操作和结果未知的网络重试必须复用同一键。
// 键不是凭据，但仍使用时间、进程计数和多段随机值降低碰撞风险。
const STORAGE_PREFIX = '__FINANCIAL_IDEMPOTENCY__:'

let sequence = 0

function normalizeSlot(slot) {
  const value = String(slot || '').trim()
  if (!value) throw new Error('幂等操作标识不能为空')
  return value.replace(/[^A-Za-z0-9._:-]/g, '-').slice(0, 96)
}

function randomPart() {
  let value = ''
  for (let index = 0; index < 4; index += 1) {
    value += Math.floor(Math.random() * 0x100000000)
      .toString(16)
      .padStart(8, '0')
  }
  return value
}

function createKey(scope) {
  sequence = (sequence + 1) % 0x1000000
  const safeScope = normalizeSlot(scope).slice(0, 32)
  return [
    safeScope,
    Date.now().toString(36),
    sequence.toString(36),
    randomPart()
  ].join('-').slice(0, 128)
}

function storageKey(slot) {
  return STORAGE_PREFIX + normalizeSlot(slot)
}

function getOrCreate(slot) {
  const key = storageKey(slot)
  try {
    const existing = wx.getStorageSync(key)
    if (typeof existing === 'string' && existing.length >= 8 && existing.length <= 128) {
      return existing
    }
  } catch (error) {
    console.warn('[幂等键] 读取本地状态失败', error)
  }

  const value = createKey(slot)
  try {
    wx.setStorageSync(key, value)
  } catch (error) {
    // 存储失败不能阻断当次请求；页面内仍应持有返回值用于重试。
    console.warn('[幂等键] 保存本地状态失败', error)
  }
  return value
}

function clear(slot, expectedKey) {
  const key = storageKey(slot)
  try {
    const existing = wx.getStorageSync(key)
    if (expectedKey && existing && existing !== expectedKey) return false
    wx.removeStorageSync(key)
    return true
  } catch (error) {
    console.warn('[幂等键] 清理本地状态失败', error)
    return false
  }
}

module.exports = {
  createKey,
  getOrCreate,
  clear
}
