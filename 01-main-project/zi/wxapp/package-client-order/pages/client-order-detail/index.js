Page({
  data: {
    order: {
      status: 'pending',
      statusIndex: 1,
      orderNo: 'WX20260803001',
      workerName: '张师傅',
      workerAvatar: '',
      workerRating: '4.9',
      orderCount: 1286,
      serviceType: '水电维修',
      serviceTime: '2026-08-03 14:00',
      address: '北京市朝阳区建国路88号',
      remark: '厨房水管漏水，需要紧急维修',
      serviceFee: '238.00',
      deliveryFee: '30.00',
      discount: '0.00',
      total: '268.00',
      payMethod: '微信支付',
      createdAt: '2026-08-03 13:00',
      acceptedAt: '',
      arrivedAt: '',
      completedAt: '',
      commented: false
    },
    icons: {
      back: '/assets/icons/back.svg'
    },
    statusIcon: '⏳',
    statusText: '等待支付',
    statusDesc: '请在 15:00 内完成支付，超时订单将自动取消'
  },

  onLoad(options) {
    if (options && options.orderId) {
      this.setData({ 'order.orderNo': options.orderId });
    }
    this.updateStatusUI();
  },

  updateStatusUI() {
    const status = this.data.order.status;
    const map = {
      pending: { icon: '⏳', text: '等待支付', desc: '请在 15:00 内完成支付，超时订单将自动取消' },
      paid: { icon: '🔧', text: '师傅正在赶来', desc: '预计 30 分钟内到达' },
      completed: { icon: '✅', text: '服务已完成', desc: '感谢您的使用，期待再次为您服务' },
      cancelled: { icon: '❌', text: '订单已取消', desc: '如有疑问请联系客服' }
    };
    this.setData({
      statusIcon: map[status].icon,
      statusText: map[status].text,
      statusDesc: map[status].desc
    });
  },

  onBack() { wx.navigateBack(); },
  onCancel() {
    wx.showModal({
      title: '确认取消订单',
      content: '取消订单后需要重新下单，确定要取消吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({
            'order.status': 'cancelled',
            'order.statusIndex': 0
          });
          this.updateStatusUI();
        }
      }
    });
  },
  onPay() {
    wx.showLoading({ title: '支付中...' });
    setTimeout(() => {
      wx.hideLoading();
      this.setData({
        'order.status': 'paid',
        'order.statusIndex': 2,
        'order.acceptedAt': '2026-08-03 13:05'
      });
      this.updateStatusUI();
    }, 1200);
  },
  onContactWorker() {
    wx.makePhoneCall({ phoneNumber: '13800138000' });
  },
  onChat() {
    wx.showToast({ title: '打开聊天', icon: 'none' });
  },
  onComment() {
    wx.navigateTo({ url: '/package-client/pages/client-order-comment/index?orderId=' + this.data.order.orderNo });
  },
  onRebook() {
    wx.showToast({ title: '再次预约', icon: 'none' });
  }
})
