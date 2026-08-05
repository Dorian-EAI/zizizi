const { createBusinessPage } = require('../../utils/design-business-page')
const { money, safePositiveId } = require('../../utils/client-finance')

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-coupon-detail', route: 'pages/client-coupon-detail/index',
  source: 'pages/client-coupon-detail.html', sourceHash: 'fnv1a-156a2d15', title: '优惠券详情'
}), {
  data: { couponId: 0, loading: true, found: false, coupon: null, loadError: '' },

  onLoad(options) {
    this.setData({ couponId: safePositiveId(options && options.couponId) })
    this.loadCoupon()
  },

  async loadCoupon() {
    if (!this.data.couponId) {
      this.setData({ loading: false, found: false, loadError: '未提供优惠券编号' })
      return
    }
    try {
      const list = await getApp().getApi().coupon.mine()
      const raw = (Array.isArray(list) ? list : []).find(item => Number(item.id) === this.data.couponId)
      if (!raw) throw new Error('当前账户未找到该优惠券')
      const template = raw.template || {}
      const value = template.type === 'percent'
        ? ((1 - Number(template.value || 0)) * 10).toFixed(1) + ' 折'
        : (template.type === 'free' ? '免单' : ('¥' + money(template.value)))
      this.setData({
        loading: false, found: true, loadError: '',
        coupon: {
          id: raw.id, name: template.name || '优惠券', value,
          minSpendText: money(template.min_spend),
          expireText: raw.expire_at || template.valid_end || '长期有效',
          serviceText: template.service_type ? ('限 ' + template.service_type + ' 服务') : '平台适用服务',
          status: raw.status || 'unknown', code: raw.code || ''
        }
      })
    } catch (error) {
      this.setData({ loading: false, found: false, coupon: null, loadError: error.message || '优惠券详情加载失败' })
    }
  },

  onUse() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-publish/index' }) })
  }
}))
