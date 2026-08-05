// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-income-category-detail",
  route: "pages/worker-income-category-detail/index",
  source: "pages/worker-income-category-detail.html",
  sourceHash: "fnv1a-abdcbcc9",
  title: "类别收入"
}))
