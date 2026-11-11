Page({
  data: {
    isFav: false,
    package: {
      badge: '限时特惠',
      name: '家庭清洁年卡',
      description: '全年 24 次家政服务，专业阿姨上门，省心省力',
      price: 1999,
      originalPrice: 3599,
      people: 4,
      duration: '2小时/次',
      sales: 286,
      services: [
        { id: 1, title: '客厅卧室清洁', desc: '地面清洁、家具擦拭、垃圾清运', duration: '60分钟' },
        { id: 2, title: '厨房深度清洁', desc: '油烟清洗、灶台消毒、餐具整理', duration: '40分钟' },
        { id: 3, title: '卫生间清洁', desc: '马桶消毒、浴缸清洁、地漏疏通', duration: '30分钟' },
        { id: 4, title: '阳台清洁', desc: '地面冲洗、杂物整理', duration: '20分钟' }
      ],
      highlights: [
        { id: 1, icon: '✅', text: '全年 24 次' },
        { id: 2, icon: '👩', text: '固定阿姨' },
        { id: 3, icon: '🧽', text: '环保清洁剂' },
        { id: 4, icon: '🛡️', text: '服务保障' }
      ],
      notices: [
        '请提前 24 小时预约',
        '服务面积不超过 150㎡',
        '超出面积按¥5/㎡加收'
      ]
    },
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },

  onToggleFav() {
    this.setData({ isFav: !this.data.isFav });
    wx.showToast({ title: this.data.isFav ? '已收藏' : '已取消收藏', icon: 'none' });
  },

  onBuy() {
    wx.showToast({ title: '跳转支付...', icon: 'none' });
  }
})
