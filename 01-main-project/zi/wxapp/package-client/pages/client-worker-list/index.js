Page({
  data: {
    category: '水电维修',
    activeFilter: 'all',
    filters: [
      { key: 'all', name: '全部' },
      { key: 'nearby', name: '附近' },
      { key: 'high-rated', name: '高评分' },
      { key: 'experienced', name: '经验丰富' }
    ],
    workers: []
  },

  onLoad(options) {
    const category = options.category || '水电维修';
    this.setData({ category });
    this.loadWorkers(category);
  },

  loadWorkers(category) {
    this.setData({
      workers: [
        {
          id: '1',
          name: '张师傅',
          initial: '张',
          rating: '4.9',
          completed: '328',
          skills: ['水管维修', '电路检修', '卫浴安装'],
          price: '80'
        },
        {
          id: '2',
          name: '李师傅',
          initial: '李',
          rating: '4.8',
          completed: '256',
          skills: ['水管维修', '防水补漏'],
          price: '60'
        },
        {
          id: '3',
          name: '王师傅',
          initial: '王',
          rating: '4.9',
          completed: '412',
          skills: ['水电维修', '管道疏通', '卫浴安装'],
          price: '100'
        }
      ]
    });
  },

  onBack() {
    wx.navigateBack();
  },

  onFilter() {
    wx.showToast({ title: '筛选功能开发中', icon: 'none' });
  },

  onFilterChange(e) {
    this.setData({ activeFilter: e.currentTarget.dataset.key });
  },

  onWorkerTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/package-client/pages/client-worker-detail/index?id=' + id });
  },

  onPublish(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/client-publish/index?workerId=' + id });
  }
});
