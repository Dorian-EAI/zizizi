// pages/worker-training-exam/index.js — 培训课程考试页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    courseId: '',
    course: null,
    loading: true,
    questions: [],
    currentQuestionIndex: 0,
    selectedAnswers: {},
    timer: '10:00',
    totalQuestions: 0,
    answeredCount: 0,
    progressPercent: 0,
    question: null,
    icons: {}
  },

  onLoad(query) {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      courseId: query.courseId || '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.brandWorker),
        upload: buildIcon('arrow-up', COLORS.brandWorker),
        alertTriangle: buildIcon('alertTriangle', COLORS.accent),
        clock: buildIcon('clock', COLORS.accent),
        check: buildIcon('check', COLORS.brandWorker),
        chevronLeft: buildIcon('chevronLeft', COLORS.text2),
        chevronRight: buildIcon('chevronRight', COLORS.white)
      }
    })
    this.loadCourse()
  },

  onUnload() {
    if (this._timer) clearInterval(this._timer)
  },

  async loadCourse() {
    const api = app.getApi()
    try {
      const exam = await api.training.exam(this.data.courseId)
      // 后端 /exam 返回题目数组（非 {questions}）；字段 question/options(List[str])/sort_order，前端需 stem/options[{letter,text}]
      const rawList = Array.isArray(exam) ? exam : (exam && exam.questions ? exam.questions : [])
      const questions = rawList.map(q => ({
        id: q.id,
        type: q.type || '单选题',
        stem: q.question || q.stem || '',
        options: (q.options || []).map((text, i) => ({ letter: String.fromCharCode(65 + i), text: text }))
      }))
      if (questions.length) {
        this.setData({
          course: Array.isArray(exam) ? null : exam,
          loading: false,
          questions: questions,
          totalQuestions: questions.length,
          question: questions[0],
          currentQuestionIndex: 0,
          progressPercent: Math.round((1 / questions.length) * 100)
        })
        this.startTimer()
      } else {
        this.setData({ course: Array.isArray(exam) ? null : exam, loading: false, questions: [], question: null, totalQuestions: 0 })
        wx.showToast({ title: '当前课程暂无可用考试', icon: 'none' })
      }
    } catch (e) {
      console.error('加载课程失败', e)
      this.setData({ loading: false, questions: [], question: null, totalQuestions: 0 })
    }
  },

  startTimer() {
    if (!this.data.totalQuestions) return
    if (this._timer) clearInterval(this._timer)
    let seconds = 10 * 60
    this._timer = setInterval(() => {
      seconds--
      if (seconds <= 0) {
        clearInterval(this._timer)
        this.setData({ timer: '00:00' })
        this.onSubmitExam()
        return
      }
      const minutes = Math.floor(seconds / 60)
      const secs = seconds % 60
      this.setData({
        timer: minutes.toString().padStart(2, '0') + ':' + secs.toString().padStart(2, '0')
      })
    }, 1000)
  },

  onOptionSelect(e) {
    const { qid, option } = e.currentTarget.dataset
    const selectedAnswers = Object.assign({}, this.data.selectedAnswers)
    selectedAnswers[qid] = option
    this.setData({ selectedAnswers })
    this.updateAnsweredCount()
  },

  onPrevQuestion() {
    if (this.data.currentQuestionIndex > 0) {
      this.updateCurrentQuestion(this.data.currentQuestionIndex - 1)
    }
  },

  onNextQuestion() {
    if (this.data.currentQuestionIndex < this.data.totalQuestions - 1) {
      this.updateCurrentQuestion(this.data.currentQuestionIndex + 1)
    } else {
      this.onSubmitExam()
    }
  },

  onAnsCellTap(e) {
    const idx = e.currentTarget.dataset.idx
    this.updateCurrentQuestion(idx)
  },

  updateCurrentQuestion(idx) {
    const question = this.data.questions[idx]
    if (!question || !this.data.totalQuestions) return
    const progressPercent = Math.round(((idx + 1) / this.data.totalQuestions) * 100)
    this.setData({
      currentQuestionIndex: idx,
      question: question,
      progressPercent: progressPercent
    })
  },

  updateAnsweredCount() {
    const count = Object.keys(this.data.selectedAnswers).length
    this.setData({ answeredCount: count })
  },

  onSubmitExam() {
    if (!this.data.totalQuestions) {
      wx.showToast({ title: '暂无可提交的考试', icon: 'none' })
      return
    }
    if (this._timer) clearInterval(this._timer)
    const answered = Object.keys(this.data.selectedAnswers).length
    const total = this.data.totalQuestions
    wx.showModal({
      title: '提交考试',
      content: '已答 ' + answered + ' / ' + total + ' 题，确认提交本次考试答案？',
      success: (res) => {
        if (res.confirm) {
          this.submitExam()
        } else {
          this.startTimer()
        }
      }
    })
  },

  async submitExam() {
    const api = app.getApi()
    try {
      // 后端 /exam/submit 接收 answers(dict: {题目id: 选项字母})，返回 {score, passed, correct_answers, total_questions}
      const result = await api.training.submitExam(this.data.courseId, this.data.selectedAnswers)
      const passed = result && result.passed
      wx.showToast({ title: passed ? '考试通过' : '已提交', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1 }), 1000)
    } catch (e) {
      console.error('提交失败', e)
      wx.showToast({ title: (e && e.message) || '提交失败，请重试', icon: 'none' })
      this.startTimer()
    }
  },

  onBack() {
    wx.showModal({
      title: '确认退出',
      content: '退出将不保存进度，确定退出吗？',
      success: (res) => {
        if (res.confirm) {
          if (this._timer) clearInterval(this._timer)
          wx.navigateBack({ delta: 1 })
        }
      }
    })
  }
})
