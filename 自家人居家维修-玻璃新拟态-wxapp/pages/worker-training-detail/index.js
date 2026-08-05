// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-training-detail",
  route: "pages/worker-training-detail/index",
  source: "pages/worker-training-detail.html",
  sourceHash: "fnv1a-c219ec5d",
  title: "课程详情"
}))
