Page({
  data: {
    worker: {},
    reviews: []
  },

  onLoad(options) {
    this.setData({
      worker: {
        initial: '张',
        name: '张师傅',
        rating: '4.9',
        completed: '328',
        praiseRate: '98%',
        bio: '从事水电维修行业 8 年，擅长水管漏水检测与维修、电路检修、卫浴安装等服务。持有国家职业资格证书，服务态度好，干活细致。',
        skills: ['水管维修', '电路检修', '卫浴安装', '防水补漏'],
        experience: '8 年',
        area: '市区及周边',
        workingHours: '8:00 - 20:00'
      },
      reviews: [
        { id: '1', ratingText: '★★★★★ 非常专业', content: '师傅上门很准时，检测仔细，维修效果很好，价格也合理，推荐！' },
        { id: '2', ratingText: '★★★★★ 态度很好', content: '张师傅服务态度非常好，耐心解答问题，干活认真负责，下次还找他。' }
      ]
    });
  },

  onBack() {
    wx.navigateBack();
  },

  onShare() {
    wx.showToast({ title: '分享功能开发中', icon: 'none' });
  },

  onContact() {
    wx.showToast({ title: '正在联系师傅...', icon: 'none' });
  }
});
