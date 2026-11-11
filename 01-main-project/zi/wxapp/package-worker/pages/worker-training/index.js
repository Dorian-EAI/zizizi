// pages/worker-training/index.js — 师傅培训页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const TABS = [
  { key: 'all', name: '全部' },
  { key: 'required', name: '必修' },
  { key: 'optional', name: '选修' },
  { key: 'skill', name: '技能提升' }
]

const LEARNING_NOTES = [
  { prefix: '课程进度与学分由平台学习记录实时统计', highlight: '', suffix: '' },
  { prefix: '完成课程后可参加对应考试', highlight: '', suffix: '' },
  { prefix: '实际接单资格与结算规则以服务端结果为准', highlight: '', suffix: '' }
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
      creditPercent: 0
    },
    courses: [],
    records: [],
    benefits: LEARNING_NOTES,
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
        return Object.assign({}, c, {
          progress: c.progress != null ? c.progress : progress,
          learnStatus: status,
          durationText: c.duration_minutes != null ? (c.duration_minutes + '分钟') : '时长未配置',
          creditText: c.credits != null ? (c.credits + '学分') : '学分未配置'
        })
      })
      const completedCount = stats && stats.completed_courses != null
        ? Number(stats.completed_courses)
        : coursesList.filter(c => c && c.progress >= 100).length
      const totalCourses = coursesList.length
      const credit = Number((stats && stats.total_credits) || 0)
      const creditPercent = totalCourses ? Math.min(100, Math.round(completedCount / totalCourses * 100)) : 0
      this.setData({
        courses: coursesList,
        stats: {
          credit,
          completedCount,
          totalCourses,
          creditPercent
        },
        records: records || []
      })
    } catch (e) {
      console.error('加载培训数据失败', e)
    }
  },

  onViewRecords() {
    const statusMap = {
      studying: '学习中',
      completed: '已完成',
      passed: '考试通过',
      failed: '考试未通过'
    }
    const lines = this.data.records.slice(0, 10).map(record => {
      const course = record.course || {}
      return (course.title || ('课程 #' + record.course_id)) + '：' + (statusMap[record.status] || record.status || '状态未知')
    })
    wx.showModal({
      title: '学习记录',
      content: lines.length ? lines.join('\n') : '暂无学习记录',
      showCancel: false,
      confirmColor: '#2D6CDF'
    })
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
      wx.navigateTo({ url: '/package-worker/pages/worker-training-exam/index?courseId=' + courseId })
    } catch (err) {
      console.error('开始学习失败', err)
      wx.showToast({ title: '请稍后重试', icon: 'none' })
    }
  },

  onContinueCourse(e) {
    const courseId = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/package-worker/pages/worker-training-exam/index?courseId=' + courseId })
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
