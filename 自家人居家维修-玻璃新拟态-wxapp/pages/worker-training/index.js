// pages/worker-training/index.js — 师傅培训页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const TABS = [
  { key: 'all', name: '全部' },
  { key: 'required', name: '必修' },
  { key: 'optional', name: '选修' },
  { key: 'skill', name: '技能提升' }
]

const MOCK_BENEFITS = [
  { prefix: '学分达60分，解锁高客单价订单', highlight: '', suffix: '' },
  { prefix: '学分达100分，', highlight: '平台抽成降低1%', suffix: '' },
  { prefix: '学分达150分，享优先派单权益', highlight: '', suffix: '' },
  { prefix: '完成全部课程，获"金牌师傅"认证标识', highlight: '', suffix: '' }
]

Page({
  data: {
    statusBarHeight: 20,
    tabs: TABS,
    activeTab: 'all',
    stats: {
      credit: 0,
      completedCount: 0,
      totalCourses: 0,
      creditTarget: app.globalData.useMock ? 100 : '—',
      creditPercent: 0,
      creditRemain: app.globalData.useMock ? 100 : '—'
    },
    courses: [],
    records: [],
    benefits: app.globalData.useMock ? MOCK_BENEFITS : [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.brandWorker),
        book: buildIcon('book', COLORS.brandWorker),
        smile: buildIcon('smile', COLORS.accentDark),
        zap: buildIcon('zap', '#5A8FAD'),
        carpentry: buildIcon('carpentry', COLORS.green),
        check: buildIcon('check', COLORS.green),
        checkGreen: buildIcon('check', COLORS.green),
        arrowRight: buildIcon('arrowRight', COLORS.brandWorker)
      }
    })
    this.loadData()
  },

  onShow() {
    if (this.data.courses.length) this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const [courses, stats, records] = await Promise.all([
        api.training.courses(),
        api.training.stats().catch(() => ({})),
        api.training.records().catch(() => [])
      ])
      // 后端 stats 字段为 total_credits/completed_courses；课程无 progress，需由 records(status: studying/completed/passed/failed) 派生
      const recordMap = {}
      ;(records || []).forEach(r => { if (r && r.course_id != null) recordMap[r.course_id] = r })
      const coursesList = (courses || []).map(c => {
        const r = recordMap[c.id]
        const status = r ? r.status : 'not_started'
        const progress = (status === 'completed' || status === 'passed' || status === 'failed') ? 100 : 0
        return Object.assign({}, c, { progress: c.progress != null ? c.progress : progress, learnStatus: status })
      })
      const completedCount = coursesList.filter(c => c && c.progress >= 100).length
      const totalCourses = coursesList.length
      const credit = (stats && (stats.total_credits != null ? stats.total_credits : (stats.credit || stats.completedCount))) || 0
      const creditTarget = app.globalData.useMock ? 100 : '—'
      const creditPercent = app.globalData.useMock ? Math.min(100, Math.round((credit / 100) * 100)) : 0
      const creditRemain = app.globalData.useMock ? Math.max(0, 100 - credit) : '—'
      this.setData({
        courses: coursesList,
        stats: {
          credit,
          completedCount,
          totalCourses,
          creditTarget,
          creditPercent,
          creditRemain
        },
        records: records || []
      })
    } catch (e) {
      console.error('加载培训数据失败', e)
    }
  },

  onViewRecords() {
    wx.showToast({ title: '查看学习记录', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key })
  },

  filteredCourses() {
    const tab = this.data.activeTab
    if (tab === 'all') return this.data.courses
    return this.data.courses.filter(c => c.category === tab)
  },

  async onStartCourse(e) {
    const courseId = e.currentTarget.dataset.id
    const api = app.getApi()
    try {
      await api.training.start(courseId)
      wx.navigateTo({ url: '/pages/worker-training-exam/index?courseId=' + courseId })
    } catch (err) {
      console.error('开始学习失败', err)
      wx.showToast({ title: '请稍后重试', icon: 'none' })
    }
  },

  onContinueCourse(e) {
    const courseId = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/worker-training-exam/index?courseId=' + courseId })
  },

  async onCompleteCourse(e) {
    const courseId = e.currentTarget.dataset.id
    const api = app.getApi()
    wx.showModal({
      title: '完成学习',
      content: '确认已学习完该课程？',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.training.complete(courseId)
          wx.showToast({ title: '已完成', icon: 'success' })
          this.loadData()
        } catch (err) {
          console.error('完成失败', err)
          wx.showToast({ title: '操作失败', icon: 'none' })
        }
      }
    })
  }
})
