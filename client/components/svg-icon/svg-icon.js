// svg-icon 组件 — 原生小程序实现（从 zijiarennn 项目复用）
// 用法: <svg-icon name="plumbing" color="blue" size="24"></svg-icon>
// color: blue | purple | white | (默认灰 black)
// name: 图标名，对应 /assets/svg/ 下的文件名（不含 _blue/_purple/_white 后缀和 .svg 扩展名）
//   例: plumbing, electric, appliance, carpentry, clean, pipeline, paint, wall,
//       hammer, wrench, home, user, wallet, message, calendar, clock, location,
//       heart, award, shield, sun, search, plus, check, phone, lock, settings 等
Component({
  properties: {
    name: { type: String, value: 'home' },
    color: { type: String, value: 'black' },  // blue | purple | white | black
    size: { type: Number, value: 24 }
  },
  data: {
    iconPath: ''
  },
  lifetimes: {
    attached() {
      this._updatePath()
    }
  },
  observers: {
    'name, color': function() {
      this._updatePath()
    }
  },
  methods: {
    _updatePath() {
      const { name, color } = this.data
      let suffix = ''
      if (color === 'blue') suffix = '_blue'
      else if (color === 'purple') suffix = '_purple'
      else if (color === 'white') suffix = '_white'
      // 路径适配：图标已迁移至 /assets/svg/
      this.setData({ iconPath: '/assets/svg/' + name + suffix + '.svg' })
    }
  }
})
