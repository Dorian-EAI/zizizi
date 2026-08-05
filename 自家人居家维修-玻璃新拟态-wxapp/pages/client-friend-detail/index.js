const { createRuntimePage } = require('../../utils/detail-page')

Page(createRuntimePage({
  pageId: 'page-client-friend-detail',
  route: 'pages/client-friend-detail/index',
  source: 'pages/client-friend-detail.html',
  sourceHash: 'fnv1a-2ec3288f',
  title: '邀请详情'
}, {
  data: {
    integrationPending: true
  }
}))
