Page({
  data: {
    tab: 'order',
    orderFilter: 'all',
    summary: {
      totalAmount: '2680.00',
      orderCount: 12,
      saveAmount: '320.00'
    },
    orders: [
      { id: 1, date: '2026-08-03', icon: '🔧', title: '水电维修', desc: '张师傅 · 1.5小时', amount: '268.00', status: 'completed', statusText: '已完成' },
      { id: 2, date: '2026-07-28', icon: '❄️', title: '空调维修', desc: '李师傅 · 2小时', amount: '380.00', status: 'completed', statusText: '已完成' },
      { id: 3, date: '2026-07-20', icon: '🧹', title: '家政保洁', desc: '王阿姨 · 3小时', amount: '299.00', status: 'completed', statusText: '已完成' },
      { id: 4, date: '2026-07-15', icon: '📦', title: '搬家服务', desc: '搬家团队 · 半天', amount: '800.00', status: 'completed', statusText: '已完成' }
    ],
    coupons: [
      { id: 1, value: '50', title: '满200元立减券', condition: '满200可用', expire: '2026-12-31', used: false },
      { id: 2, value: '100', title: '新用户大礼包', condition: '满500可用', expire: '2026-10-31', used: false },
      { id: 3, value: '30', title: '家电维修专享', condition: '满150可用', expire: '2026-09-30', used: true }
    ],
    favorites: [
      { id: 1, icon: '🧹', title: '张阿姨', desc: '家政保洁 · 好评4.9' },
      { id: 2, icon: '🔧', title: '李师傅', desc: '水电维修 · 好评4.9' },
      { id: 3, icon: '❄️', title: '王师傅', desc: '空调维修 · 好评4.8' }
    ],
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },
  onTabChange(e) { this.setData({ tab: e.currentTarget.dataset.tab }); },
  onOrderFilter(e) { this.setData({ orderFilter: e.currentTarget.dataset.filter }); },
  onOrderTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/package-client/pages/client-order-detail/index?orderId=' + id });
  },
  onRemoveFav(e) {
    const id = e.currentTarget.dataset.id;
    const favorites = this.data.favorites.filter(f => f.id !== id);
    this.setData({ favorites });
    wx.showToast({ title: '已取消收藏' });
  }
})
