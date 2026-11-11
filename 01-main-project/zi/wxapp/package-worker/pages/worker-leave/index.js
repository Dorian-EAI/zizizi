Page({
  data: {
    form: {
      startDate: '',
      endDate: '',
      reason: ''
    },
    history: [
      { id: '1', startDate: '2025-01-15', endDate: '2025-01-17', reason: '家中有事', status: 'approved', statusText: '已批准' },
      { id: '2', startDate: '2024-12-20', endDate: '2024-12-25', reason: '身体不适', status: 'approved', statusText: '已批准' }
    ]
  },

  onBack() {
    wx.navigateBack();
  },

  onDateChange(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  onSubmit() {
    if (!this.data.form.startDate || !this.data.form.endDate) {
      wx.showToast({ title: '请选择请假时间', icon: 'none' });
      return;
    }
    wx.showToast({ title: '申请已提交', icon: 'success' });
    setTimeout(() => {
      wx.navigateBack();
    }, 1000);
  }
});
