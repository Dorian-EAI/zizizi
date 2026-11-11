Page({
  data: {
    keyword: '',
    activeCategory: 'all',
    services: [
      { id: 1, icon: '🧹', name: '家政保洁', startPrice: '99', tags: ['好评如潮', '上门快'] },
      { id: 2, icon: '🔧', name: '水电维修', startPrice: '88', tags: ['专业', '价格透明'] },
      { id: 3, icon: '❄️', name: '空调维修', startPrice: '120', tags: ['持证', '上门快'] },
      { id: 4, icon: '📦', name: '搬家服务', startPrice: '300', tags: ['省心', '准时'] },
      { id: 5, icon: '🎨', name: '墙面刷新', startPrice: '15', tags: ['环保材料', '质保'] },
      { id: 6, icon: '🔨', name: '家电安装', startPrice: '50', tags: ['专业', '质保'] }
    ],
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },
  onSearch(e) { this.setData({ keyword: e.detail.value }); },
  onCategoryChange(e) { this.setData({ activeCategory: e.currentTarget.dataset.cat }); },
  onServiceTap(e) {
    wx.showToast({ title: '服务详情', icon: 'none' });
  }
})
