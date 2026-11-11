Page({
  data: {
    authStatus: 'unverified',
    canSubmit: false,
    agreed: false,
    form: {
      name: '',
      idCard: '',
      phone: '',
      region: '',
      idFront: '',
      idBack: ''
    },
    verifiedInfo: {
      name: '张*明',
      idCard: '110101********1234',
      time: '2026-06-15 10:30'
    },
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({ [`form.${field}`]: value });
    this.checkSubmit();
  },

  onSelectRegion() {
    wx.showToast({ title: '选择地区', icon: 'none' });
  },

  onUploadIdFront() {
    wx.chooseImage({
      count: 1,
      success: (res) => {
        this.setData({ 'form.idFront': res.tempFilePaths[0] });
        this.checkSubmit();
      }
    });
  },

  onUploadIdBack() {
    wx.chooseImage({
      count: 1,
      success: (res) => {
        this.setData({ 'form.idBack': res.tempFilePaths[0] });
        this.checkSubmit();
      }
    });
  },

  onToggleAgree() {
    this.setData({ agreed: !this.data.agreed });
    this.checkSubmit();
  },

  onViewAgreement() {
    wx.showToast({ title: '查看协议', icon: 'none' });
  },

  onViewPrivacy() {
    wx.showToast({ title: '查看隐私政策', icon: 'none' });
  },

  onContactSupport() {
    wx.showToast({ title: '联系客服', icon: 'none' });
  },

  checkSubmit() {
    const f = this.data.form;
    const canSubmit = f.name && f.idCard && f.phone && f.region && f.idFront && f.idBack && this.data.agreed;
    this.setData({ canSubmit: !!canSubmit });
  },

  onSubmit() {
    if (!this.data.canSubmit) {
      wx.showToast({ title: '请完善信息', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '提交中...' });
    setTimeout(() => {
      wx.hideLoading();
      this.setData({ authStatus: 'pending' });
    }, 1200);
  }
})
