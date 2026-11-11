Page({
  data: {
    rating: 0,
    professional: 0,
    attitude: 0,
    content: '',
    order: {
      orderNo: 'WX20260803001',
      workerName: '张师傅',
      workerAvatar: '',
      workerRating: '4.9',
      serviceType: '水电维修',
      completedAt: '2026-08-03 14:30',
      price: '268.00'
    },
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onLoad(options) {
    if (options && options.orderId) {
      this.setData({ 'order.orderNo': options.orderId });
    }
  },

  onBack() {
    wx.navigateBack();
  },

  onRateChange(e) {
    const rating = e.currentTarget.dataset.rating;
    this.setData({ rating: this.data.rating === rating ? 0 : rating });
  },

  onRateField(e) {
    const rating = e.currentTarget.dataset.rating;
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: this.data[field] === rating ? 0 : rating });
  },

  onContentInput(e) {
    this.setData({ content: e.detail.value });
  },

  onUploadImage() {
    wx.chooseImage({
      count: 6,
      success: (res) => {
        console.log('selected images:', res.tempFilePaths);
      }
    });
  },

  onSubmitReview() {
    if (this.data.rating === 0) {
      wx.showToast({ title: '请先评分', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '提交中...' });
    setTimeout(() => {
      wx.hideLoading();
      wx.showToast({ title: '评价成功', icon: 'success' });
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    }, 800);
  }
})
