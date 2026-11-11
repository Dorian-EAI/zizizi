Page({
  data: {
    user: {
      userId: '88888888',
      nickname: '用户_8888',
      avatar: '',
      phone: '138****8888',
      gender: '女',
      birthday: '1990-01-01',
      region: '北京 朝阳',
      signature: '',
      realNameAuth: false
    },
    icons: {
      back: '/assets/icons/back.svg'
    }
  },

  onBack() { wx.navigateBack(); },
  onChangeAvatar() { wx.showToast({ title: '更换头像', icon: 'none' }); },
  onEditAvatar() { wx.showToast({ title: '更换头像', icon: 'none' }); },
  onEditNickname() { wx.showToast({ title: '修改昵称', icon: 'none' }); },
  onEditPhone() { wx.showToast({ title: '修改手机号', icon: 'none' }); },
  onEditGender() { wx.showToast({ title: '选择性别', icon: 'none' }); },
  onEditBirthday() { wx.showToast({ title: '选择生日', icon: 'none' }); },
  onEditRegion() { wx.showToast({ title: '选择地区', icon: 'none' }); },
  onPreviewSignature() { wx.showToast({ title: '编辑签名', icon: 'none' }); },
  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '已退出登录' });
        }
      }
    });
  }
})
