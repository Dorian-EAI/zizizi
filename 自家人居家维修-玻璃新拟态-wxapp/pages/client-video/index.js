const { createRuntimePage } = require('../../utils/detail-page')

Page(createRuntimePage({
  pageId: 'page-client-video',
  route: 'pages/client-video/index',
  source: 'pages/client-video.html',
  sourceHash: 'fnv1a-69d5e806',
  title: '居家安全课堂'
}, {
  data: {
    courseAvailable: false
  }
}))
