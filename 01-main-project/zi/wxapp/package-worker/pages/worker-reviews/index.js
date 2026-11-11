// pages/worker-reviews/index.js — 师傅评价管理页
const app = getApp()
const api = app.getApi()
const { buildIcon, buildFilledIcon, COLORS } = require('../../utils/icons')

const MOCK_TAGS = [
  { label: '技术专业', count: 86, icon: 'carpentry', cls: 'tag-brand' },
  { label: '服务热情', count: 72, icon: 'heart', cls: 'tag-accent' },
  { label: '准时到达', count: 68, icon: 'clock', cls: 'tag-green' },
  { label: '价格合理', count: 54, icon: 'yuan', cls: 'tag-blue' },
  { label: '干净整洁', count: 48, icon: 'building', cls: 'tag-purple' }
]

Page({
  data: {
    statusBarHeight: 20,
    tabs: [
      { key: '', label: '全部', selected: true },
      { key: 'good', label: '好评', selected: false },
      { key: 'mid', label: '中评', selected: false },
      { key: 'bad', label: '差评', selected: false }
    ],
    starIndexes: [0, 1, 2, 3, 4],
    avgRating: 0,
    avgRound: 0,
    total: 0,
    distribution: [
      { star: 5, count: 0, percent: 0 },
      { star: 4, count: 0, percent: 0 },
      { star: 3, count: 0, percent: 0 }
    ],
    list: [],
    loading: false,
    showReply: false,
    replyContent: '',
    replyReviewId: '',
    tags: app.globalData.useMock ? MOCK_TAGS : [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        starOn: buildFilledIcon('star', COLORS.accent),
        starOff: buildIcon('star', COLORS.text4),
        reply: buildIcon('message', COLORS.brandWorker),
        check: buildIcon('check', COLORS.text3),
        carpentry: buildIcon('carpentry', COLORS.brandWorker),
        heart: buildIcon('heart', COLORS.accentDark),
        clock: buildIcon('clock', COLORS.green),
        yuan: buildIcon('yuan', '#5A8FAD'),
        building: buildIcon('building', COLORS.purple)
      }
    })
    this.loadReviews()
  },

  // 师傅 ID 必须由师傅令牌实时确认，避免角色切换后误用客户端缓存中的 userInfo.id。
  async resolveWorkerId() {
    try {
      const me = await api.auth.workerMe()
      return (me && (me.id || me.worker_id)) || null
    } catch (e) {
      return null
    }
  },

  async loadReviews() {
    this.setData({ loading: true })
    try {
      const workerId = await this.resolveWorkerId()
      if (!workerId) {
        // 未登录：清空列表并提示，避免调用需用户态的 /api/reviews/mine
        this.setData({ loading: false, list: [] })
        wx.showToast({ title: '请先登录师傅账号', icon: 'none' })
        return
      }

      const tab = this.data.tabs.find(t => t.selected)
      // tab → rating 过滤：好评=5星，差评=1星，中评/全部由后端返回后前端二次过滤
      let rating = null
      if (tab.key === 'good') rating = 5
      else if (tab.key === 'bad') rating = 1

      const params = { worker_id: workerId, page: 1, size: 20 }
      if (rating) params.rating = rating

      // 评价列表走公开端点 /api/reviews?worker_id=X；统计走 /api/reviews/worker/{id}/detail（仅首次加载）
      const tasks = [api.reviews.list(params)]
      if (!this._statsLoaded) tasks.push(api.reviews.workerDetail(workerId))
      const results = await Promise.all(tasks)
      const res = results[0]
      const detail = results[1]

      if (detail) {
        this._statsLoaded = true
        this.applyStats(detail)
      }

      let list = Array.isArray(res) ? res : ((res && (res.list || res.items || res.reviews)) || [])
      // 中评：后端无 2-4 星聚合参数，前端二次过滤
      if (tab.key === 'mid') list = list.filter(r => r.rating >= 2 && r.rating <= 4)

      list = this.enrichReviews(list)
      this.setData({ list: list, loading: false })
    } catch (e) {
      console.error('加载评价失败', e)
      this.setData({ loading: false })
    }
  },

  // 将后端 worker_detail.stats 映射为前端展示结构
  applyStats(detail) {
    const stats = (detail && detail.stats) || {}
    const avg = stats.avg_rating != null ? stats.avg_rating
      : (detail && detail.rating != null ? detail.rating : this.data.avgRating)
    const total = stats.total_count != null ? stats.total_count : this.data.total
    const counts = [
      stats.rating_5_count || 0,
      stats.rating_4_count || 0,
      stats.rating_3_count || 0
    ]
    const max = Math.max.apply(null, counts.concat([1]))
    const distribution = [5, 4, 3].map(function (star, i) {
      return { star: star, count: counts[i], percent: Math.round((counts[i] / max) * 100) }
    })

    // 标签云仅展示后端统计；显式 Mock 模式才保留设计示例。
    let tags = app.globalData.useMock ? MOCK_TAGS : []
    if (Array.isArray(stats.tag_counts) && stats.tag_counts.length) {
      const iconMap = { '技术专业': 'carpentry', '服务热情': 'heart', '准时到达': 'clock', '价格合理': 'yuan', '干净整洁': 'building' }
      const clsMap = { '技术专业': 'tag-brand', '服务热情': 'tag-accent', '准时到达': 'tag-green', '价格合理': 'tag-blue', '干净整洁': 'tag-purple' }
      tags = stats.tag_counts.slice(0, 5).map(function (t) {
        return {
          label: t.tag,
          count: t.count,
          icon: iconMap[t.tag] || 'star',
          cls: clsMap[t.tag] || 'tag-brand'
        }
      })
    }

    this.setData({
      avgRating: avg,
      avgRound: Math.round(avg),
      total: total,
      distribution: distribution,
      tags: tags
    })
  },

  // 统一映射后端评价字段为前端 wxml 期望的形状
  enrichReviews(list) {
    const self = this
    return list.map(function (item) {
      const anonymous = item.is_anonymous
      let name = anonymous
        ? '匿名用户'
        : (item.nickname || item.user_name || (item.user_id ? ('用户' + item.user_id) : '匿名用户'))
      let time = item.time || ''
      if (!time && item.created_at) time = self.formatDate(item.created_at)
      return Object.assign({}, item, {
        avatarText: name ? name[0] : '匿',
        displayName: name,
        // 后端 review_content → 前端 content
        content: item.content || item.review_content || '',
        // 后端 worker_reply → 前端 reply
        reply: item.reply || item.worker_reply || '',
        // 后端 service_type → 前端 service_name（wxml 兜底 item.service || item.service_name）
        service_name: item.service_name || item.service_type || '',
        time: time
      })
    })
  },

  formatDate(dt) {
    if (!dt) return ''
    const s = String(dt).replace('T', ' ')
    return s.length > 16 ? s.slice(0, 16) : s
  },

  onTab(e) {
    const idx = e.currentTarget.dataset.idx
    const tabs = this.data.tabs.map((t, i) => ({ ...t, selected: i === idx }))
    this.setData({ tabs })
    this.loadReviews()
  },

  openReply(e) {
    this.setData({
      replyReviewId: e.currentTarget.dataset.id,
      replyContent: '',
      showReply: true
    })
  },

  onReplyInput(e) {
    this.setData({ replyContent: e.detail.value })
  },

  closeReply() {
    this.setData({ showReply: false, replyContent: '', replyReviewId: '' })
  },

  async submitReply() {
    const { replyReviewId, replyContent } = this.data
    if (!replyContent.trim()) {
      wx.showToast({ title: '请输入回复内容', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中...' })
    try {
      await api.reviews.reply(replyReviewId, replyContent.trim())
      wx.hideLoading()
      wx.showToast({ title: '回复成功', icon: 'success' })
      const list = this.data.list.map(item => item.id === replyReviewId
        ? { ...item, reply: replyContent.trim(), reply_time: '刚刚' }
        : item)
      this.setData({ list: list, showReply: false, replyContent: '', replyReviewId: '' })
    } catch (e) {
      wx.hideLoading()
      console.error('回复失败', e)
      wx.showToast({ title: '回复失败', icon: 'none' })
    }
  },

  prevent() {},

  onBack() {
    wx.navigateBack()
  }
})
