// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-service-area",
  route: "pages/worker-service-area/index",
  source: "pages/worker-service-area.html",
  sourceHash: "fnv1a-08796649",
  title: "服务区域"
}))
