const api = require('../../../utils/request')

Page({
  data: {
    orderId: null,
    order: null,
    loading: true
  },

  onLoad(options) {
    const id = options.order_id || options.id
    this.setData({ orderId: id })
    this.loadOrderDetail(id)
  },

  loadOrderDetail(id) {
    wx.showLoading({ title: '加载中...' })
    api.get(`/api/worker/orders/${id}`).then(data => {
      const order = this.transformOrder(data)
      this.setData({ order, loading: false })
      wx.setNavigationBarTitle({ title: '订单详情' })
    }).catch(() => {
      this.loadMockData()
    }).finally(() => {
      wx.hideLoading()
    })
  },

  loadMockData() {
    const order = {
      order_no: 'ZR20250108001234',
      status_chip: '待服务',
      eta_text: '预约今天 15:00-18:00',
      status_desc: '客户已确认，等待您上门服务',
      timeline_progress: 62,
      timeline: [
        { key: 'created', label: '订单创建', time: '10:30', state: 'done' },
        { key: 'accepted', label: '师傅接单', time: '10:45', state: 'done' },
        { key: 'depart', label: '出发中', time: '14:20', state: 'active' },
        { key: 'arrive', label: '到达现场', time: '预计15:10', state: 'pending' },
        { key: 'complete', label: '服务完成', time: '预计17:00', state: 'pending' }
      ],
      customer_name: '张女士',
      customer_rating: '4.8',
      order_count: 12,
      customer_phone: '138****6789',
      customer_avatar: '',
      service_type: '家电维修 · 冰箱',
      service_name: '冰箱不制冷维修',
      address: '浙江省杭州市西湖区文三路 478 号华星时代广场 A 座 1203 室',
      appoint_time: '2025-01-08 15:00-18:00',
      appoint_time_text: '2025年1月8日 15:00-18:00',
      description: '海尔三门冰箱购买3年，最近不制冷，压缩机有嗡嗡声',
      remark: '请携带备用压缩机，小区停车在B1层',
      quote_price: 280,
      final_price: 280,
      estimated_time: '约2小时',
      material_cost: 80,
      platform_fee: 28,
      estimated_income: 248,
      checkin_steps: [
        { key: 'depart', title: '出发签到', status_text: '已完成', state: 'done', meta: '14:20 已签', icon: '/assets/svg/car.svg' },
        { key: 'arrive', title: '到达签到', status_text: '待签到', state: 'current', meta: '到达后拍照定位', emoji: '📍', action: true, action_text: '到达签到' },
        { key: 'before', title: '服务前拍照', status_text: '待上传', state: 'pending', meta: '拍摄故障部位', emoji: '📸', action: true, action_text: '上传照片' },
        { key: 'after', title: '服务后拍照', status_text: '待上传', state: 'pending', meta: '拍摄修复效果', emoji: '✅', action: true, action_text: '上传照片' }
      ],
      extra_fee: false,
      can_apply_extra_fee: true,
      primary_action_text: '立即出发'
    }
    this.setData({ order, loading: false })
  },

  transformOrder(data) {
    if (!data) return null
    return {
      ...data,
      timeline_progress: data.timeline_progress || 62,
      timeline: data.timeline || [],
      checkin_steps: data.checkin_steps || [],
      primary_action_text: data.primary_action_text || '立即出发'
    }
  },

  goBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.switchTab({ url: '/pages/worker/orders/orders' }) })
  },

  onMoreTap() {
    wx.showActionSheet({
      itemList: ['联系客服', '举报问题', '取消订单'],
      success: (res) => {
        const index = res.tapIndex
        if (index === 0) this.contactService()
        else if (index === 1) this.reportIssue()
        else if (index === 2) this.cancelOrder()
      }
    })
  },

  contactService() {
    wx.showToast({ title: '正在联系客服', icon: 'none' })
  },

  reportIssue() {
    wx.showToast({ title: '请在订单中提交举报', icon: 'none' })
  },

  cancelOrder() {
    wx.showModal({
      title: '取消订单',
      content: '确定要取消该订单吗？取消后将无法恢复。',
      confirmColor: '#C4533A',
      success: (res) => {
        if (res.confirm) {
          api.post(`/api/worker/orders/${this.data.orderId}/cancel`).then(() => {
            wx.showToast({ title: '订单已取消', icon: 'success' })
            setTimeout(() => wx.navigateBack(), 1500)
          }).catch(err => {
            wx.showToast({ title: err.message || '取消失败', icon: 'none' })
          })
        }
      }
    })
  },

  callCustomer(e) {
    const phone = e.currentTarget.dataset.phone || this.data.order?.customer_phone
    if (!phone) {
      wx.showToast({ title: '暂无客户电话', icon: 'none' })
      return
    }
    const cleanPhone = phone.replace(/\*/g, '')
    wx.makePhoneCall({ phoneNumber: cleanPhone || phone })
  },

  contactCustomer(e) {
    this.callCustomer(e)
  },

  messageCustomer() {
    wx.showToast({ title: '正在打开聊天', icon: 'none' })
  },

  departAction() {
    wx.showModal({
      title: '确认出发',
      content: '确认您已出发前往客户地址？',
      success: (res) => {
        if (res.confirm) {
          api.post(`/api/worker/orders/${this.data.orderId}/depart`).then(() => {
            wx.showToast({ title: '已出发', icon: 'success' })
            this.loadOrderDetail(this.data.orderId)
          }).catch(err => {
            wx.showToast({ title: err.message || '操作失败', icon: 'none' })
          })
        }
      }
    })
  },

  onCheckinAction(e) {
    const key = e.currentTarget.dataset.key
    wx.showModal({
      title: '签到确认',
      content: '是否现在进行签到？系统将自动获取您的位置信息。',
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '定位中...' })
          wx.getLocation({
            type: 'gcj02',
            success: (loc) => {
              api.post(`/api/worker/orders/${this.data.orderId}/checkin`, {
                step: key,
                latitude: loc.latitude,
                longitude: loc.longitude
              }).then(() => {
                wx.hideLoading()
                wx.showToast({ title: '签到成功', icon: 'success' })
                this.loadOrderDetail(this.data.orderId)
              }).catch(err => {
                wx.hideLoading()
                wx.showToast({ title: err.message || '签到失败', icon: 'none' })
              })
            },
            fail: () => {
              wx.hideLoading()
              wx.showToast({ title: '定位失败，请手动签到', icon: 'none' })
            }
          })
        }
      }
    })
  },

  applyExtraFee() {
    wx.showModal({
      title: '申请补差价',
      editable: true,
      placeholderText: '请输入补差价原因',
      success: (res) => {
        if (res.confirm && res.content) {
          wx.showModal({
            title: '补差价金额',
            editable: true,
            placeholderText: '请输入补差价金额',
            success: (res2) => {
              if (res2.confirm && res2.content) {
                const amount = parseFloat(res2.content)
                if (isNaN(amount) || amount <= 0) {
                  wx.showToast({ title: '请输入有效金额', icon: 'none' })
                  return
                }
                api.post(`/api/worker/orders/${this.data.orderId}/extra-fee`, {
                  reason: res.content,
                  amount
                }).then(() => {
                  wx.showToast({ title: '申请已提交', icon: 'success' })
                  this.loadOrderDetail(this.data.orderId)
                }).catch(err => {
                  wx.showToast({ title: err.message || '提交失败', icon: 'none' })
                })
              }
            }
          })
        }
      }
    })
  },

  onShareAppMessage() {
    return {
      title: '自家人维修 - 订单详情',
      path: `/pages/worker/detail/detail?order_id=${this.data.orderId}`
    }
  }
})
