// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-service-scope",
  route: "pages/worker-service-scope/index",
  source: "pages/worker-service-scope.html",
  sourceHash: "fnv1a-30c7bda5",
  title: "服务范围"
}))
