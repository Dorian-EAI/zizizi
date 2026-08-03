// utils/validate.js — 校验工具
function isPhone(v) {
  return /^1[3-9]\d{9}$/.test(v)
}
function isNumber(v) {
  return /^\d+(\.\d+)?$/.test(v)
}
function isEmpty(v) {
  return v === null || v === undefined || v === '' || (typeof v === 'string' && v.trim() === '')
}
function isIdCard(v) {
  return /^\d{17}[\dXx]$/.test(v)
}
module.exports = { isPhone, isNumber, isEmpty, isIdCard }
