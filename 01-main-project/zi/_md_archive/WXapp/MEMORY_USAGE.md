# 自家长小程序内存占用分析

> 生成时间：2026-08-07
> 最后更新：2026-08-07 17:20
> 项目路径：/Users/dorian/Documents/troe_projects/zi/WXapp

---

## 一、总体概况

| 指标 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| **项目总大小** | 5.2 MB | 4.9 MB | ↓ 300 KB |
| **主包大小** | 704 KB | 704 KB | 不变 |
| **分包数量** | 2 个 | 4 个 | ↑ 2 个 |
| **package-client** | 2.1 MB | 440 KB | ↓ 1.66 MB ✅ |
| **package-client-order** | - | 376 KB | 新增 |
| **package-client-user** | - | 1.3 MB | 新增 |
| **package-worker** | 996 KB | 996 KB | 不变 |

---

## 二、分包结构

### 2.1 优化后分包架构

```
WXapp/                          4.9 MB
├── pages/                      704 KB  (主包 - 核心功能)
│   ├── entry/                  启动页
│   ├── client-home/            客户端首页
│   ├── client-publish/         发布服务
│   ├── worker-home/            师傅端首页
│   └── ...                     其他核心页面
│
├── package-client/             440 KB  (核心分包 - 18 页面)
│   ├── client-worker-list/     师傅列表
│   ├── client-worker-detail/   师傅详情
│   ├── client-service/         服务
│   ├── client-search/          搜索
│   └── ...                     其他核心功能
│
├── package-client-order/       376 KB  (订单分包 - 14 页面)
│   ├── client-order-detail/    订单详情
│   ├── client-order-tracking/  订单跟踪
│   ├── client-quote-list/      报价列表
│   └── ...                     其他订单功能
│
├── package-client-user/        1.3 MB  (用户分包 - 62 页面)
│   ├── client-wallet/          钱包
│   ├── client-member/          会员
│   ├── client-coupon/          优惠券
│   └── ...                     其他用户功能
│
├── package-worker/             996 KB  (师傅分包 - 36 页面)
│   ├── worker-detail/          师傅详情
│   ├── worker-settings/        师傅设置
│   └── ...                     其他师傅功能
│
└── assets/fonts/               612 KB  (base64 字体)
    └── fonts.js                Noto Serif SC + Cormorant Garamond
```

### 2.2 分包大小对比

| 分包 | 大小 | 页面数 | 状态 |
|------|------|--------|------|
| pages (主包) | 704 KB | 18 | ✅ |
| package-client | 440 KB | 18 | ✅ |
| package-client-order | 376 KB | 14 | ✅ |
| package-client-user | 1.3 MB | 62 | ✅ |
| package-worker | 996 KB | 36 | ✅ |

---

## 三、优化历史

### 3.1 字体资源优化

**优化前：**
```
assets/fonts/
├── fonts.js                    612 KB  (base64 数据)
├── NotoSerifSC-Subset-400.woff2   215 KB  ← 冗余
├── NotoSerifSC-Subset-700.woff2   222 KB  ← 冗余
└── CormorantGaramond-Bold.woff2    22 KB  ← 冗余
总计: 1.1 MB
```

**优化后：**
```
assets/fonts/
└── fonts.js                    612 KB  (仅保留 base64)
总计: 612 KB
```

**节省空间：** 459 KB

### 3.2 分包结构优化

**优化前：**
```
package-client/                 2.1 MB  (94 页面) ⚠️ 超过 2MB 限制
```

**优化后：**
```
package-client/                 440 KB  (18 页面) ✅
package-client-order/           376 KB  (14 页面) ✅
package-client-user/            1.3 MB  (62 页面) ✅
```

---

## 四、微信小程序限制检查

| 限制项 | 限制值 | 当前值 | 状态 |
|--------|--------|--------|------|
| 主包大小 | ≤ 2 MB | 704 KB | ✅ |
| 单个分包 | ≤ 2 MB | 1.3 MB (max) | ✅ |
| 总包体 | ≤ 20 MB | 4.9 MB | ✅ |
| 单页代码包 | ≤ 2 MB | - | ✅ |
| 本地缓存 | ≤ 10 MB | - | ✅ |

---

## 五、后续优化建议

### 5.1 package-client-user 可继续优化

当前 package-client-user 为 1.3 MB，包含 62 个页面。可进一步按功能拆分：

```
package-client-user/        1.3 MB (当前)
    ↓ 拆分为
package-client-pay/         ~400 KB (支付/钱包相关)
package-client-marketing/   ~300 KB (营销/积分/优惠券)
package-client-setting/     ~600 KB (设置/评价/其他)
```

### 5.2 字体加载优化

当前字体为 base64 内嵌方案，可考虑：
- 按需加载：仅在需要衬线字体的页面加载
- 子集优化：仅加载使用的字符集

### 5.3 代码层面优化

- 检查页面中是否有重复的工具函数
- 考虑将公共组件移至主包
- 使用 `wx.canIUse` 检测 API 支持性

---

## 六、总结

### 6.1 已完成优化

- ✅ 移除重复字体文件（节省 459 KB）
- ✅ package-client 拆分为 3 个分包（解决 2MB 超限问题）
- ✅ 项目总大小从 5.2 MB 降至 4.9 MB

### 6.2 当前状态

- ✅ 所有分包均在 2MB 限制内
- ✅ 字体资源仅保留一份（base64）
- ✅ 结构清晰，按需加载

### 6.3 建议后续操作

- 💡 真机测试分包跳转功能
- 💡 考虑进一步拆分 package-client-user
- 💡 定期审查分包大小（建议每 30 天）

---

*文档生成时间：2026-08-07*
*下次审查建议：真机测试后或新增页面时*
