// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-help-category",
  route: "pages/worker-help-category/index",
  source: "pages/worker-help-category.html",
  sourceHash: "fnv1a-bd708849",
  title: "接单与报价"
}))
