Page({
  data: {
    template: {},
    favorited: false
  },

  onLoad(options) {
    const id = options.id || 'default';
    this.loadTemplate(id);
  },

  loadTemplate(id) {
    this.setData({
      template: {
        name: '水电维修 · 水管漏水',
        description: '专业水管漏水检测与维修，含上门检测、漏点定位、维修或更换服务',
        category: '水电维修',
        duration: '约 1-2 小时',
        area: '市区范围',
        workerReq: '需持证上岗',
        items: ['漏水检测', '漏点定位', '维修更换', '压力测试'],
        basePrice: '80',
        visitFee: '¥30',
        estimatedPrice: '150-300'
      }
    });
  },

  onBack() {
    wx.navigateBack();
  },

  onFavorite() {
    this.setData({ favorited: !this.data.favorited });
  },

  onUseTemplate() {
    wx.showToast({ title: '正在跳转发布页...', icon: 'none' });
    setTimeout(() => {
      wx.navigateTo({ url: '/pages/client-publish/index' });
    }, 500);
  }
});
