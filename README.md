# 自家人居家维修 · 工作区说明

本目录汇总「自家人居家维修」项目的唯一有效版本、设计参考与历史归档。

- 项目定位：面向家庭维修场景的竞价式 O2O 平台（用户发布需求 → 认证师傅报价 → 用户选师傅 → 履约、支付、评价、售后）
- 当前业务基线：**v6.2**
- 唯一有效的代码与文档都在 `01-main-project/zi`，其余目录仅作参考或留档

## 目录结构

```text
zizizi/
├── README.md                      本说明
├── 01-main-project/
│   └── zi/                        当前唯一有效项目（代码 + 文档 + 设计画布）
├── 02-design-reference/
│   └── style-references/          早期视觉方向比选稿（6 套风格）
└── 03-archive/
    ├── legacy-ziold/              2026-08 之前的旧版项目与历史 PRD
    └── early-prototype-zijiaren/  2026-05 的静态 HTML 原型
```

## 01-main-project / zi

日常开发、部署、评审只看这里。目录内自带完整的 [项目 README](01-main-project/zi/README.md)，关键入口：

| 内容 | 位置 |
|---|---|
| 产品需求文档（唯一业务事实源，v6.2） | `zi/PRD_v6.0.md`（文件名为兼容历史链接，正文为 v6.2） |
| 后端目标契约 | `zi/PRD_BACKEND_v2.0.md` |
| FastAPI 后端 + 管理后台 | `zi/server/` |
| 微信小程序运行代码 | `zi/WXapp/` |
| 设计画布与页面视觉 | `zi/zjrnew/` |
| 功能交互、样式规范、上线清单 | `zi/docs/` |
| 旧小程序实现（仅历史参考） | `zi/legacy/` |

快速启动（详见 `zi/README.md`）：

```powershell
Set-Location 01-main-project\zi\server
Copy-Item .env.example .env
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe run.py
```

小程序：用微信开发者工具打开 `01-main-project\zi\WXapp`，在 `config/env.js` 配置后端地址。

> 注意：`server/` 下的 `venv`、`.uv-python`、`__pycache__` 等为本地运行缓存，可随时删除重建，不属于需要备份的内容。

## 02-design-reference / style-references

早期视觉方向探索，共 6 套：暖色信任、极简瑞士、活力渐变、玻璃拟态、玻璃新拟态、暗色奢华。含预览 HTML、3 张参考图和 `.design` 画布文件。

仅用于风格比对，**不是当前实现**。当前生效的视觉规范在 `01-main-project/zi/docs/design/样式规范详尽文档.md`。

## 03-archive

| 目录 | 内容 | 用途 |
|---|---|---|
| `legacy-ziold/` | 旧版 `client` 小程序、旧 `server`、PRD v1.0–v6.0、多套视觉方案（活力渐变、温润信任、Liquid Glass 等） | 追溯历史决策、找回旧版本文案 |
| `early-prototype-zijiaren/` | 6 个静态 HTML 页面 + 《自家人产品需求文档 PRD_v1.0.doc》 | 查看项目最初形态 |

归档内容**不要在其中继续开发**，也不要直接引用其中的业务规则——历史版本与 v6.2 存在冲突，以主项目 PRD 为准。

## 本次整理记录（2026-11-11）

删除的冗余内容：

- `zi0`、`zi1`：两份完全相同的项目副本（文件清单与大小逐一比对一致），各约 954 MB；
- `zioo`、`zi - 副本`：2026-08 的旧副本，内容已被主项目覆盖，仅多出 venv 与备份文件；
- `old`：内部嵌套的 `ziold`、`zi_副本`、`zjr` 三重旧备份；
- `zizi` 中除设计参考外的运行日志残留；
- 全目录 33,657 个 macOS 垃圾文件（`._*`、`.DS_Store`）。

整理前后：**4.06 GB / 186,672 个文件 → 0.45 GB / 16,048 个文件**。主项目未被修改，git 仓库与最新提交（`a2b32e1`）保持原样。
