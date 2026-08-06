const api = require('../../api/index')

Page({
  data: {
    loading: true,
    loadError: false,
    exchangeId: '',
    productId: '',
    exchange: {
      productName: '',
      spec: '',
      pointsCost: '',
      remainingPoints: '',
      orderNo: '',
      success: true,
      iconText: '✓',
      iconClass: ''
    }
  },

  onLoad(query) {
    const exchangeId = query.exchangeId || query.id || ''
    const productId = query.productId || query.product_id || ''
    this.setData({ exchangeId, productId })
    this.loadExchangeResult()
  },

  async loadExchangeResult() {
    this.setData({ loading: true, loadError: false })
    try {
      const params = {}
      if (this.data.exchangeId) {
        params.exchange_id = this.data.exchangeId
      }
      if (this.data.productId) {
        params.product_id = this.data.productId
      }

      const logs = await api.points.logs(params)

      let targetLog = null
      if (Array.isArray(logs) && logs.length > 0) {
        if (this.data.exchangeId) {
          targetLog = logs.find(log =>
            log.exchange_id === this.data.exchangeId ||
            log.order_no === this.data.exchangeId ||
            String(log.id) === this.data.exchangeId
          )
        }
        if (!targetLog && this.data.productId) {
          targetLog = logs.find(log =>
            log.product_id === this.data.productId ||
            String(log.productId) === this.data.productId
          )
        }
        if (!targetLog) {
          targetLog = logs.find(log =>
            log.type === 'exchange' || log.type === 'consume' ||
            log.action === 'exchange' || log.action === 'consume'
          )
        }
        if (!targetLog && logs.length > 0) {
          targetLog = logs[0]
        }
      }

      if (targetLog) {
        const isSuccess = targetLog.status !== 'failed' &&
                          targetLog.status !== 'cancelled' &&
                          targetLog.status !== 'expired'

        this.setData({
          exchange: {
            productName: targetLog.product_name ||
                         targetLog.productName ||
                         targetLog.description ||
                         '商品兑换',
            spec: targetLog.spec ||
                  targetLog.specification ||
                  targetLog.product_spec ||
                  '',
            pointsCost: this.formatPoints(
              targetLog.points ||
              targetLog.points_cost ||
              targetLog.amount ||
              targetLog.change
            ),
            remainingPoints: this.formatPoints(
              targetLog.remaining_points ||
              targetLog.remainingPoints ||
              targetLog.balance ||
              targetLog.current_balance ||
              ''
            ),
            orderNo: targetLog.order_no ||
                     targetLog.orderNo ||
                     targetLog.exchange_id ||
                     targetLog.id ||
                     '',
            success: isSuccess,
            iconText: isSuccess ? '✓' : '✕',
            iconClass: isSuccess ? '' : 'failed'
          },
          loading: false
        })
      } else {
        this.setData({
          exchange: {
            productName: this.data.productId ? '积分商品' : '商品兑换',
            spec: '',
            pointsCost: '',
            remainingPoints: '',
            orderNo: this.data.exchangeId || '',
            success: true,
            iconText: '✓',
            iconClass: ''
          },
          loading: false
        })
      }
    } catch (error) {
      console.error('加载兑换结果失败', error)
      this.setData({ loading: false, loadError: true })
    }
  },

  formatPoints(value) {
    if (value === null || value === undefined || value === '') return ''
    var str = String(Math.abs(Number(value)))
    return str.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  },

  onBack() {
    wx.navigateBack({
      delta: 1,
      fail: function () {
        wx.reLaunch({ url: '/pages/client-points-mall/index' })
      }
    })
  },

  onTapProduct() {
    var productId = this.data.productId
    if (productId) {
      wx.navigateTo({
        url: '/pages/client-points-product/index?id=' + productId,
        fail: function () {
          wx.showToast({ title: '页面暂不可用', icon: 'none' })
        }
      })
    } else {
      wx.navigateTo({
        url: '/pages/client-points-mall/index',
        fail: function () {
          wx.showToast({ title: '页面暂不可用', icon: 'none' })
        }
      })
    }
  },

  onGoHome() {
    wx.reLaunch({
      url: '/pages/client-home/index',
      fail: function () {
        wx.redirectTo({
          url: '/pages/client-home/index',
          fail: function () {
            wx.showToast({ title: '页面暂不可用', icon: 'none' })
          }
        })
      }
    })
  },

  onGoMall() {
    wx.reLaunch({
      url: '/pages/client-points-mall/index',
      fail: function () {
        wx.redirectTo({
          url: '/pages/client-points-mall/index',
          fail: function () {
            wx.showToast({ title: '页面暂不可用', icon: 'none' })
          }
        })
      }
    })
  },

  onRetry() {
    this.loadExchangeResult()
  }
})