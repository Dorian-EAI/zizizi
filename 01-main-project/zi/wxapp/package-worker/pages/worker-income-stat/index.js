// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-income-stat",
  route: "pages/worker-income-stat/index",
  source: "pages/worker-income-stat.html",
  sourceHash: "fnv1a-34d7c9b9",
  title: "收入统计"
}))
