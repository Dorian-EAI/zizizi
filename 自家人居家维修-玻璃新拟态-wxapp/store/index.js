// store/index.js — 简单全局状态管理
const storage = require('../utils/storage')

const state = {
  role: 'client',
  userInfo: null,
  currentOrder: null,
  addressList: []
}

function init() {
  state.role = storage.get(storage.KEYS.ROLE) || 'client'
  state.userInfo = storage.get(storage.KEYS.USER) || null
  state.addressList = storage.get(storage.KEYS.ADDRESS) || []
}

function setRole(role) {
  state.role = role
  storage.set(storage.KEYS.ROLE, role)
  const app = getApp()
  if (app) app.globalData.role = role
}

function setUser(user) {
  state.userInfo = user
  storage.set(storage.KEYS.USER, user)
}

function getRole() {
  return state.role
}

function getUser() {
  return state.userInfo
}

init()

module.exports = { state, setRole, setUser, getRole, getUser }
