// 已审计：独立契约未就绪时仅展示受限态，并引导到已接入的真实功能中心。
const { createDesignPage } = require('../../utils/design-page-runtime')

Page(createDesignPage({
  pageId: "page-worker-chat",
  route: "pages/worker-chat/index",
  source: "pages/worker-chat.html",
  sourceHash: "fnv1a-69074a8d",
  title: "订单聊天 - 师傅端"
}))
