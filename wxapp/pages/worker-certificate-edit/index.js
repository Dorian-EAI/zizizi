// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-certificate-edit",
  route: "pages/worker-certificate-edit/index",
  source: "pages/worker-certificate-edit.html",
  sourceHash: "fnv1a-f6830624",
  title: "证书资料"
}))
