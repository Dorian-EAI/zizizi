Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/index/index', text: '首页', emoji: '🏠' },
      { pagePath: '/pages/publish/publish', text: '发布', emoji: '➕' },
      { pagePath: '/pages/orders/orders', text: '订单', emoji: '📋' },
      { pagePath: '/pages/mine/mine', text: '我的', emoji: '👤' }
    ]
  },
  methods: {
    switchTab(e) {
      const index = e.currentTarget.dataset.index;
      const url = this.data.list[index].pagePath;
      wx.switchTab({ url: url });
    }
  }
});
