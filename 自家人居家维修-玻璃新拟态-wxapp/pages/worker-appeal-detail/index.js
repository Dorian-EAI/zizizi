// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-appeal-detail",
  route: "pages/worker-appeal-detail/index",
  source: "pages/worker-appeal-detail.html",
  sourceHash: "fnv1a-1b310a4d",
  title: "申诉详情"
}))
