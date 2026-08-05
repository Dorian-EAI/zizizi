// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-cert-manage",
  route: "pages/worker-cert-manage/index",
  source: "pages/worker-cert-manage.html",
  sourceHash: "fnv1a-4dd8025a",
  title: "证书管理"
}))
