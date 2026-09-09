# 职称申报 Skill（zhicheng-shenbao-skill）

全国通用的**专业技术资格申报**辅助 skill —— 帮你判断走哪条路、核对条件、备材料、找到官方入口、填表、盯进度、领电子证、分享时脱敏。
覆盖 **助理工程师 / 工程师 / 高级工程师** 全流程，内置 **31 个省级行政区 + 新疆兵团** 的官方申报入口。

> **定位边界（先读）**：本 skill 的目标是**「跟人配合把申报办成」**，不是全自动。
> 政务申报涉及实名登录、单位审核、材料真实性承诺 —— **全自动既做不到，也不该做**。
> 分工是：**人负责登录、上传佐证、复核提交；助手负责找入口、读页面、分析、填表、盯进度。**

---

## ✨ 亮点

- **全国入口直达**：内置 32 个地区官方申报入口（导航页 + CLI 双通道），不用再满网搜"XX省职称申报系统"，也不用担心点进培训机构广告页。
- **域名风险分级**：官方域名 / http 非加密 / 非 gov 域名 / IP 直连 四类标注，IP 型系统额外提供省人社厅官网兜底，链接失效也不至于抓瞎。
- **人机协同自动化**：通过 CDP 接管你本机的 **Edge**（无需下载 Chromium 内核），助手能读页面、点按钮、填表单，你只需扫码登录和最后点提交。
- **登录态持久化**：扫一次码，之后免登录（政务站最大的时间浪费就是反复登录）。
- **绝对不代提交**：脚本明确不碰提交按钮 —— 申报要签诚信承诺，材料真实性只能本人负责。
- **隐私默认安全**：`profile.json`（身份证号）、`.session/`（登录 Cookie）、`.shots/`（页面截图，含姓名证件号）全部已在 `.gitignore` 排除。

---

## 目录结构

```
├── SKILL.md                          # 技能主文档（16 节，申报全流程 + 自动化 + 人机协同）
├── README.md                         # 本文件
├── LICENSE                           # MIT
├── references/
│   ├── national-portals.html         # 全国申报入口导航页（按大区分组、带搜索与风险筛选）
│   └── jiangsu-walkthrough.md        # 江苏实测走查（路径、页面结构、SPA 踩坑清单）
└── scripts/
    ├── zc.py                         # 零依赖 CLI：list / info / open / search
    ├── cdp.py                        # 原生 Edge + 纯 CDP 接管（唯一自动化方式）：launch/nav/text/click/frames/fields/fill/eval/shot/tabs
    └── profile.example.json          # 个人信息模板（复制为 profile.json 后填写）
```

---

## 快速开始

### 1. 只想找到官方入口 → 打开导航页

直接用浏览器打开 `references/national-portals.html`，点你所在省份即可直达。

或者用命令行（零依赖，不需要装任何东西）：

```bash
cd scripts
python zc.py list                  # 列出全部 32 个地区
python zc.py list --region 华东     # 按大区筛选
python zc.py info 广东              # 查看某地区详情（系统名 / 网址 / 备注）
python zc.py open 江苏              # 直接打开该地区申报入口
python zc.py open 河北 --backup      # 打开兜底的人社厅官网
python zc.py search 工程师           # 关键词搜索
```

### 2. 想让助手帮你填表 → 人机协同

> ⚠️ **关键前提**：浏览器必须**原生启动**（系统 Edge + `--remote-debugging-port`，不带任何自动化参数）。
> 用 Playwright/Selenium 启动会触发 `navigator.webdriver` 检测，申报表单永远停在「加载中」。详见 SKILL.md 第十五节。

```bash
pip install websocket-client   # 唯一依赖：纯 CDP 客户端，不引入 Playwright/Selenium
cp scripts/profile.example.json scripts/profile.json   # 填好个人信息（已被 .gitignore 排除）

# 下面这些由助手执行，你只管登录和最后提交
python cdp.py launch 江苏     # 原生启动 Edge 并打开申报入口（保持等待）
# → 你在弹出的浏览器里扫码登录
python cdp.py text            # 助手读页面判断是否登录成功
python cdp.py click "在线办理"
python cdp.py fields          # 助手读取表单字段
python cdp.py fill "电子邮箱" "x@x.com"
# → 你复核后手动点提交
```

> 以上入口/字段是**江苏省**实测结果，详见 `references/jiangsu-walkthrough.md`；换省份需重新踩点，不能套用。

### 3. 只想了解申报政策 → 读 SKILL.md

`SKILL.md` 共 16 节，核心是这几块：

| 章节 | 内容 |
|------|------|
| 一~二 | 职称等级体系（3 层次 / 5 级别 / 30 系列）、三条申报路径（初定 / 评审 / 以考代评） |
| 三~五 | 四大硬件自查、学历年限对照、申报时间轴 |
| 六~八 | 材料清单与 Word 复刻、在线提交、电子证书领取 |
| 九 | **脱敏**（PyMuPDF 原生遮盖身份证/出生日期/二维码，而非白块覆盖） |
| 十~十三 | 软考 vs 初定、常见坑与 Fix、关键网址、政策依据 |
| 十四 | 全国各省市申报入口（导航页 + CLI） |
| 十五~十六 | 浏览器自动化、**人机协同工作流与分工边界** |

---

## 覆盖地区

华北 5 · 东北 3 · 华东 7 · 华中 3 · 华南 3 · 西南 5 · 西北 6 = **32 个入口**

（31 个省级行政区 + 新疆生产建设兵团；辽宁未公布全省统一系统，按评委会分散，仅提供省人社厅官网兜底。）

**入口可信度分级**：

| 级别 | 说明 |
|------|------|
| 官方域名 `.gov.cn` | 最稳，直接放系统 URL |
| http 非加密 | 域名仍是 gov.cn，协议为 http，遇拦截改 https 或从通知页进入 |
| 非 gov 域名 | 由政府通知指定但非政府域名，建议同时收藏兜底官网 |
| IP + 端口 | 易变动，**务必同时提供省人社厅官网兜底** |

> 各省系统每年可能更换域名或改版。发现失效链接时更新 `scripts/zc.py` 的 `PORTALS`（CLI 与自动化共用同一数据源），并同步 `references/national-portals.html` 的 `PORTALS` 数组。

---

## 隐私红线

- `profile.json`、`.session/`、`.shots/` **已在 `.gitignore` 排除**，切勿提交或分享。
- 对外分享职称证书时必须脱敏：身份证号、出生日期、二维码一律遮盖。
- 用 PyMuPDF 原生 `add_redact_annot` 遮盖，**不要用白块覆盖** —— 白块下的原文可被复制提取。

---

## 免责声明

本 skill 汇总的申报条件、年限、材料要求来自公开政策整理，**仅供参照**。
一切以**当年评委会正式通知**与**当地人社部门官方解释**为准；地方人才补贴政策动态调整，勿参考旧网文。

本 skill 不代理申报、不代提交、不承诺通过。

---

## License

[MIT](LICENSE) © 2026 Zaosusu
