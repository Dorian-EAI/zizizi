const { createRuntimePage } = require('../../utils/detail-page')

Page(createRuntimePage({
  pageId: 'page-client-history',
  route: 'pages/client-history/index',
  source: 'pages/client-history.html',
  sourceHash: 'fnv1a-30344e2a',
  title: '浏览历史'
}, {
  data: {
    activeTab: 'all',
    tabs: [
      { key: 'all', name: '全部' },
      { key: 'service', name: '服务' },
      { key: 'worker', name: '师傅' },
      { key: 'product', name: '商品' }
    ]
  },

  onTab(event) {
    this.setData({ activeTab: event.currentTarget.dataset.key || 'all' })
  }
}))
