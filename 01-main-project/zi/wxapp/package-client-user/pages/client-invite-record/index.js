const { createRuntimePage } = require('../../utils/detail-page')

Page(createRuntimePage({
  pageId: 'page-client-invite-record',
  route: 'pages/client-invite-record/index',
  source: 'pages/client-invite-record.html',
  sourceHash: 'fnv1a-2c2a2ae8',
  title: '邀请记录'
}, {
  data: {
    activeTab: 'finished',
    tabs: [
      { key: 'finished', name: '已完成' },
      { key: 'pending', name: '进行中' },
      { key: 'expired', name: '已失效' }
    ]
  },

  onTab(event) {
    this.setData({ activeTab: event.currentTarget.dataset.key || 'finished' })
  }
}))
