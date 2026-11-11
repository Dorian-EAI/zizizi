// pages/client-coupon/index.js — 优惠券 像素级复刻 client-coupon.html
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

// 券状态元信息
const STATUS_META = {
  available: { text: '可使用', chipClass: 'chip-success' },
  used:      { text: '已使用', chipClass: 'chip-info' },
  expired:   { text: '已过期', chipClass: 'chip-warning' }
}

Page({
  data: {
    statusBarHeight: 20,
    tabs: [
      { key: 'available', name: '未使用' },
      { key: 'used',      name: '已使用' },
      { key: 'expired',   name: '已过期' }
    ],
    activeTab: 'available',
    coupons: [],
    availableCount: 0,
    // 后端当前未提供累计节省统计，真实环境不展示演示金额。
    totalSaved: app.globalData.useMock ? 86 : '—',
    claiming: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        redeem: buildIcon('coupon', COLORS.text1),
        check: buildIcon('check', COLORS.text3),
        coupon: buildIcon('coupon', COLORS.accent),
        empty: buildIcon('coupon', COLORS.text3),
        arrowRight: buildIcon('arrowRight', COLORS.white)
      }
    })
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const status = this.data.activeTab
      const list = await api.coupon.mine(status)
      const coupons = (list || []).map(c => {
        const meta = STATUS_META[c.status || status] || {}
        // 后端将面值/门槛/名称嵌套在 template 下，WXML 期望扁平 amount/threshold/name/expireAt
        const t = c.template || {}
        return Object.assign({}, c, {
          name: t.name != null ? t.name : c.name,
          amount: t.value != null ? t.value : c.amount,
          threshold: t.min_spend != null ? t.min_spend : c.threshold,
          type: t.type != null ? t.type : c.type,
          expireAt: c.expire_at != null ? c.expire_at : c.expireAt,
          orderNo: c.used_order_no != null ? c.used_order_no : c.orderNo,
          statusText: meta.text || c.statusText || '',
          statusChipClass: meta.chipClass || ''
        })
      })
      const patch = { coupons }
      // 仅在「可使用」tab 时同步可用数量
      if (status === 'available') patch.availableCount = coupons.length
      this.setData(patch)
    } catch (e) {
      console.error('加载优惠券失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key, coupons: [] })
    this.loadData()
  },

  onCouponTap(e) {
    const item = e.currentTarget.dataset.item
    if (!item) return
    if (!item.id) {
      wx.showToast({ title: '优惠券编号无效', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: '/package-client/pages/client-coupon-detail/index?couponId=' + encodeURIComponent(String(item.id))
    })
  },

  onRedeemCode() {
    wx.showToast({ title: '兑换码接口暂未开放', icon: 'none' })
  },

  async onClaimCenterTap() {
    if (this.data.claiming) return
    const api = app.getApi()
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const result = await api.coupon.templates()
      const templates = (Array.isArray(result) ? result : ((result && result.items) || []))
        .filter(item => item && item.id)
        .slice(0, 6)
      wx.hideLoading()
      if (!templates.length) {
        wx.showToast({ title: '暂无可领取优惠券', icon: 'none' })
        return
      }
      wx.showActionSheet({
        itemList: templates.map(item => item.name || ('优惠券 #' + item.id)),
        success: res => this.claimTemplate(templates[res.tapIndex])
      })
    } catch (error) {
      wx.hideLoading()
      console.error('加载领券中心失败', error)
    }
  },

  async claimTemplate(template) {
    if (!template || this.data.claiming) return
    this.setData({ claiming: true })
    wx.showLoading({ title: '领取中', mask: true })
    try {
      const api = app.getApi()
      await api.coupon.claim(template.id)
      wx.hideLoading()
      wx.showToast({ title: '领取成功', icon: 'success' })
      if (this.data.activeTab === 'available') await this.loadData()
    } catch (error) {
      wx.hideLoading()
      console.error('领取优惠券失败', error)
    } finally {
      this.setData({ claiming: false })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  },

  onUseCoupon() {
    wx.showToast({ title: '去下单时选择优惠券', icon: 'none' })
  }
})
