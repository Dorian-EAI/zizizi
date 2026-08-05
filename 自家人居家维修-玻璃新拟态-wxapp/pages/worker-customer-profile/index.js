// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-customer-profile",
  route: "pages/worker-customer-profile/index",
  source: "pages/worker-customer-profile.html",
  sourceHash: "fnv1a-1c0354ca",
  title: "客户资料"
}))
