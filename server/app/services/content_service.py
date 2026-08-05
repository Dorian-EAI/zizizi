"""FAQ、协议页、关于我们等内容页业务逻辑"""

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.faq import FAQ, FAQCategory
from app.models.agreement import PageContent


DEFAULT_PAGE_CONTENTS = {
    "about": {
        "title": "关于我们",
        "content": """# 关于自家人

**自家人居家维修** 是专注于社区家庭维修服务的平台。我们致力于为每一个家庭提供**便捷、专业、透明、可靠**的居家维修解决方案。

## 我们的使命

让居家维修不再难 —— 一键下单，师傅上门，明码标价，售后无忧。

## 核心优势

- **严选师傅**：实名认证+技能考核+服务评级，只留好师傅
- **明码标价**：起步价公开透明，报价后再施工，绝不乱加价
- **极速响应**：同城师傅平均 30 分钟接单，当天可上门
- **售后保障**：维修项目质保 30-90 天，出问题免费返修
- **资金托管**：用户验收满意再付款，服务更安心

## 联系我们

- 客服电话：400-000-0000（工作日 9:00-21:00）
- 官方微信：自家人居家维修
- 商务合作：business@zjr.example.com

© 2024 自家人科技 版权所有
""",
    },
    "agreement": {
        "title": "用户服务协议",
        "content": """# 用户服务协议

本协议是您（以下简称"用户"）与自家人居家维修平台（以下简称"平台"）之间就平台服务等相关事宜所订立的协议。请您在使用平台服务前仔细阅读本协议的全部内容。

## 一、服务说明

1. 平台为用户提供居家维修服务信息的发布、接单撮合、支付托管等服务。
2. 平台本身不直接提供维修服务，具体服务由经平台认证的合作师傅提供。

## 二、账号注册与使用

1. 用户需通过真实有效的手机号或第三方账号完成注册。
2. 用户应妥善保管账号信息，因用户保管不当造成的损失由用户自行承担。
3. 用户承诺所发布的信息真实、合法，不得利用平台从事任何违法违规活动。

## 三、订单与支付

1. 用户下单时应提供准确的服务地址、联系方式和问题描述。
2. 师傅上门检测后给出报价，用户确认后再进行施工。
3. 平台提供资金托管服务，用户验收满意后款项结算给师傅。

## 四、服务质保

1. 各类维修服务均有约定质保期（具体以服务详情为准），质保期内因同一问题返修免人工费。
2. 如因师傅施工质量问题造成用户损失，平台协助用户向师傅追偿。

## 五、用户行为规范

用户不得从事以下行为：
- 发布虚假、欺诈、恶意评价信息
- 虚构订单或恶意拖欠费用
- 骚扰、辱骂平台工作人员或师傅
- 侵犯他人合法权益或违反法律法规

## 六、协议修改

平台有权根据业务发展需要修改本协议，修改后的协议将在平台公布并生效。

---
**最后更新：2024 年 1 月**
""",
    },
    "privacy": {
        "title": "隐私政策",
        "content": """# 隐私政策

自家人居家维修平台（以下简称"我们"）非常重视用户的隐私保护。本政策将说明我们如何收集、使用、存储和保护您的个人信息。

## 一、信息收集范围

为向您提供服务，我们可能会收集以下信息：

1. **注册信息**：手机号、微信 OpenID、昵称、头像
2. **服务信息**：服务地址（含经纬度）、联系人、联系电话、问题描述与图片
3. **交易信息**：订单记录、支付信息（通过第三方支付平台处理）
4. **设备与日志**：设备型号、操作系统版本、访问日志

## 二、信息使用目的

我们仅会将收集的信息用于：
- 创建与管理您的账号
- 为您匹配附近师傅并完成服务
- 处理订单、支付、退款与售后
- 改进平台服务质量与体验
- 保障账号安全与风控

## 三、信息共享与披露

我们**不会**向任何无关第三方出售或出租您的个人信息，仅在以下情况可能共享：
- 经您事先明确同意
- 为完成服务必要地向提供服务的师傅展示必要信息（如地址、联系电话）
- 根据法律法规要求或司法、行政机关的合法请求
- 为保护用户或公众的人身财产安全

## 四、信息存储与安全

- 您的个人信息将存储于中华人民共和国境内的服务器
- 我们采用业界标准的加密、访问控制、审计等安全措施保护信息安全
- 除法律另有规定外，我们仅在服务必要的最短期限内保存您的信息

## 五、您的权利

您可以随时：
- 访问、更正、删除您的个人信息
- 注销您的账号
- 撤回此前给予的授权同意
- 联系客服提出任何隐私相关问题

## 六、联系我们

如有任何疑问、投诉或请求，请通过以下方式联系我们：
- 客服电话：400-000-0000
- 邮箱：privacy@zjr.example.com

---
**最后更新：2024 年 1 月**
""",
    },
    "help": {
        "title": "帮助中心",
        "content": """# 帮助中心

## 快速导航

- [新手入门](#新手入门)
- [订单服务](#订单服务)
- [支付与退款](#支付与退款)
- [质保与售后](#质保与售后)

---

## 新手入门

### 1. 如何下单？
1. 进入首页选择所需维修服务类型
2. 填写问题描述、上传图片、选择地址和上门时间
3. 提交订单 → 附近师傅报价 → 选择心仪师傅 → 等待上门

### 2. 必须注册才能下单吗？
首次使用可用微信快捷登录，后续为了订单跟踪与售后，建议绑定手机号。

---

## 订单服务

### 1. 师傅多久能上门？
一般情况下师傅接单后可当日上门，具体以双方约定的时间为准。加急订单优先安排。

### 2. 如何取消订单？
- 师傅接单前：用户可任意取消，不产生费用
- 师傅接单后未上门：联系客服或直接取消，视情况可能扣除上门交通费
- 施工中/完成：不可取消，有争议可申请售后介入

### 3. 对师傅服务不满意怎么办？
可在订单详情页点击"申请售后"，或联系客服 400-000-0000，我们会第一时间处理。

---

## 支付与退款

### 1. 支持哪些付款方式？
目前支持微信支付、钱包余额支付；支付宝、银行卡尚未开放。

### 2. 为什么先付款？
资金由平台托管，您验收满意后才会结算给师傅，保障您的权益。

### 3. 退款流程
申请售后 → 客服/系统判定 → 退款原路返回（一般 1-3 个工作日到账）。

---

## 质保与售后

### 1. 维修项目质保多久？
| 项目 | 质保期 |
| --- | --- |
| 水电/电路维修 | 90 天 |
| 家电维修 | 60 天 |
| 管道疏通 | 30 天 |
| 门窗/家具安装 | 60 天 |

### 2. 如何申请质保返修？
在已完成订单详情点击"申请返修"，或直接拨打客服电话，我们将安排原师傅或更高级别师傅免费上门（同一问题）。

---

**仍未解决？** 转人工客服 → 400-000-0000
""",
    },
}


DEFAULT_FAQ_CATEGORIES = [
    ("账号", 1),
    ("订单", 2),
    ("支付", 3),
    ("师傅与服务", 4),
    ("隐私与安全", 5),
]


DEFAULT_FAQS = [
    # 账号
    ("账号", "如何注册账号？", '进入小程序后点击"我的"，使用微信快捷登录即可一键完成注册。建议绑定手机号以便后续接收订单通知。'),
    ("账号", "忘记密码/无法登录怎么办？", "本平台使用微信快捷登录或手机验证码登录，无需设置密码。如遇登录异常，请联系客服 400-000-0000。"),
    ("账号", "如何修改昵称和头像？", '进入"我的"页面，点击头像进入个人资料页即可修改昵称、头像、联系方式等。'),
    ("账号", "怎么绑定手机号？", "我的 → 设置 → 账号与安全 → 绑定手机号，按提示输入验证码完成绑定。"),

    # 订单
    ("订单", "如何下单维修服务？", "首页选择服务类型 → 填写问题描述和图片 → 选择地址和预约时间 → 提交订单。附近师傅会实时报价，您选择心仪师傅后等待上门即可。"),
    ("订单", "可以取消订单吗？", "师傅接单前可任意取消；师傅已接单但未上门，如无合理原因取消将可能产生少量交通补偿费；施工后订单不可取消。"),
    ("订单", "师傅一直不接单怎么办？", "如 30 分钟内无师傅接单，系统会自动扩大范围推送并短信提醒热门师傅；您也可以联系客服协助加急。"),
    ("订单", "可以指定某个师傅上门吗？", '可以，师傅详情页有"立即下单"按钮，可直接指定该师傅为您服务。'),
    ("订单", "下单后可以修改服务时间吗？", '在师傅接单前，您可在订单详情页修改；师傅已接单则需与师傅协商，并通过订单"改约"功能确认。'),

    # 支付
    ("支付", "支持哪些支付方式？", "目前支持微信支付、钱包余额支付；支付宝、银行卡尚未开放。"),
    ("支付", "为什么要先付款给平台？", '平台采用"资金托管"模式：用户先付款给平台，验收满意后才结算给师傅，杜绝乱收费、师傅跑路等风险，保障您的权益。'),
    ("支付", "什么时候可以退款？", "以下情况可申请退款：①师傅无法按约定时间服务且无法协调；②维修经两次返修仍无法解决；③经平台认定的其他合理情况。"),
    ("支付", "退款多久到账？", "审核通过后退款原路返回，微信支付通常 1-3 个工作日到账，银行卡可能需 3-7 个工作日。"),
    ("支付", "有发票吗？", "在订单完成后可于订单详情页申请电子发票，按提示填写发票抬头与税号，1-3 个工作日将发送至您填写的邮箱。"),

    # 师傅与服务
    ("师傅与服务", "平台师傅可靠吗？", "平台所有师傅均经过实名认证（身份证+人脸）、技能考核、背景审查与培训，定期评级，不合格者立即清退，您可放心选择。"),
    ("师傅与服务", "上门检测后不维修需要付费吗？", "需支付 30-50 元上门检测费（根据服务类型），如最终选择该师傅维修，则检测费可直接抵扣维修费。"),
    ("师傅与服务", "价格怎么定？会不会加价？", "平台设置起步价参考，师傅上门检测后给出具体报价，**用户确认后才施工**，杜绝先斩后奏。若师傅私下加价，欢迎举报，平台将予以处罚。"),
    ("师傅与服务", "维修后有保修吗？", "所有维修项目均提供 30-90 天质保（详见帮助中心-质保列表）。质保期内同一问题免费返修。"),
    ("师傅与服务", "师傅带的配件是正品吗？", "平台要求师傅使用合格配件，重要配件建议用户索要购买凭证。如因配件质量问题引起故障，平台将协助您维权。"),
    ("师傅与服务", "服务过程中出现损坏/安全事故怎么办？", "平台对服务过程中因师傅责任造成的用户损失提供协助追偿机制；严重情况建议拨打 110 并联系客服介入。"),

    # 隐私与安全
    ("隐私与安全", "我的地址和电话会泄露吗？", "不会。仅被您选中的师傅在接单后才能看到您的联系电话和服务地址；服务结束后师傅端信息自动脱敏。我们绝不会将您的信息出售给无关第三方。"),
    ("隐私与安全", "上传的问题图片会被用作其他用途吗？", '仅用于师傅更准确地判断问题与报价。用户可随时在"我的-设置-隐私"中要求删除历史工单图片。'),
    ("隐私与安全", "如何注销账号？", "我的 → 设置 → 账号与安全 → 注销账号。注销后您的所有个人信息将在法律要求的期限届满后删除或匿名化。"),
]


def list_faqs(db: Session) -> List[dict]:
    """获取全部分类 + 所属 FAQ 列表"""
    categories = (
        db.query(FAQCategory)
        .order_by(FAQCategory.sort_order.asc(), FAQCategory.id.asc())
        .limit(100)
        .all()
    )
    # GET 请求不得在部署环境偷偷写入演示内容；正式内容应由运营后台显式发布。
    if not categories:
        from app.config import settings

        if settings.is_deployed:
            return []
        seed_default_faqs(db)
        categories = (
            db.query(FAQCategory)
            .order_by(FAQCategory.sort_order.asc(), FAQCategory.id.asc())
            .limit(100)
            .all()
        )

    result = []
    for cat in categories:
        faqs = (
            db.query(FAQ)
            .filter(FAQ.category_id == cat.id, FAQ.is_active == True)
            .order_by(FAQ.sort_order.asc(), FAQ.id.asc())
            .limit(200)
            .all()
        )
        result.append({
            "category_id": cat.id,
            "name": cat.name,
            "faqs": [
                {"id": f.id, "category_id": f.category_id, "question": f.question, "answer": f.answer}
                for f in faqs
            ],
        })
    return result


def _default_page(key: str) -> dict:
    """获取页面的默认兜底内容"""
    default = DEFAULT_PAGE_CONTENTS.get(key)
    if default:
        return {
            "key": key,
            "title": default["title"],
            "content": default["content"],
            "updated_at": None,
        }
    return {
        "key": key,
        "title": "页面建设中",
        "content": "该页面内容正在建设中，请稍后再来。",
        "updated_at": None,
    }


def get_page(db: Session, key: str) -> dict:
    """获取页面内容；找不到则返回该 key 对应默认文本"""
    page = db.query(PageContent).filter(PageContent.key == key).first()
    if page:
        return {
            "key": page.key,
            "title": page.title,
            "content": page.content,
            "updated_at": page.updated_at,
        }
    from app.config import settings

    if settings.is_deployed:
        raise HTTPException(status_code=503, detail="页面内容尚未由运营后台发布")
    # 本地开发返回只读默认文案；显式 seed 命令才允许写入数据库。
    return _default_page(key)


def seed_default_pages(db: Session) -> int:
    """初始化默认页面（about/agreement/privacy/help）"""
    count = 0
    for key, val in DEFAULT_PAGE_CONTENTS.items():
        existing = db.query(PageContent).filter(PageContent.key == key).first()
        if existing:
            continue
        page = PageContent(
            key=key,
            title=val["title"],
            content=val["content"],
        )
        db.add(page)
        count += 1
    db.commit()
    return count


def upsert_page(db: Session, key: str, title: str, content: str) -> PageContent:
    """创建或更新页面内容"""
    if not key:
        raise HTTPException(status_code=400, detail="key 不可为空")
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title 不可为空")
    if not content:
        raise HTTPException(status_code=400, detail="content 不可为空")

    page = db.query(PageContent).filter(PageContent.key == key).first()
    if page:
        page.title = title
        page.content = content
    else:
        page = PageContent(key=key, title=title, content=content)
        db.add(page)
    db.commit()
    db.refresh(page)
    return page


def seed_default_faqs(db: Session) -> int:
    """初始化默认 FAQ 分类和问题（约 20 条，分 5 大类）"""
    count = 0
    cat_map = {}
    for name, order in DEFAULT_FAQ_CATEGORIES:
        cat = db.query(FAQCategory).filter(FAQCategory.name == name).first()
        if not cat:
            cat = FAQCategory(name=name, sort_order=order)
            db.add(cat)
            db.flush()
            count += 1
        cat_map[name] = cat.id

    for cat_name, q, a in DEFAULT_FAQS:
        cat_id = cat_map.get(cat_name)
        if not cat_id:
            continue
        existing = db.query(FAQ).filter(FAQ.category_id == cat_id, FAQ.question == q).first()
        if existing:
            continue
        faq = FAQ(
            category_id=cat_id,
            question=q,
            answer=a,
            sort_order=0,
            is_active=True,
        )
        db.add(faq)
        count += 1
    db.commit()
    return count
