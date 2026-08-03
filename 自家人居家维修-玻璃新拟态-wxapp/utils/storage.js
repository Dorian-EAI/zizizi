// utils/storage.js — 本地存储封装
const KEYS = {
  TOKEN: 'token',
  USER: 'userInfo',
  ROLE: 'role',
  ADDRESS: 'addressList',
  SEARCH_HISTORY: 'searchHistory'
}

function get(key) {
  try { return wx.getStorageSync(key) } catch (e) { return null }
}

function set(key, value) {
  try { wx.setStorageSync(key, value) } catch (e) {}
}

function remove(key) {
  try { wx.removeStorageSync(key) } catch (e) {}
}

function clear() {
  try { wx.clearStorageSync() } catch (e) {}
}

module.exports = { KEYS, get, set, remove, clear }
