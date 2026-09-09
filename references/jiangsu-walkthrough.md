# 江苏职称申报 · 实测走查记录

> 实测日期：2026-09-09 ｜ 环境：Windows + 本机 Microsoft Edge（**原生启动 + 纯 CDP 接管**，不装浏览器内核）
> 适用范围：**仅限江苏省**（江苏省人才服务云平台 / 江苏人社网办大厅）。其他省份平台完全不同，不可套用本节任何入口或字段名，需各自重新踩点。
> 结论：登录、导航、办件查询链路跑通；**用原生 Edge + CDP 后申报表单可正常渲染并填表**（此前 Playwright 启动浏览器导致表单停「加载中」是误判，根因见第三节）。

---

## 一、实测路径（江苏省人才服务云平台，推荐）

直接在「江苏人社网办大厅」点「职称初定申报」推荐卡片**不会跳转**（SPA 无 `href`），实测可用的入口是人才服务云平台：

| 步骤 | 操作 | 结果 |
|---|---|---|
| 1. 打开云平台 | `https://www.jssrcfwypt.org.cn/web/cdsu/rcbs/zc?areaCode=null` | ✅ |
| 2. 选分类 | 点分类「**职称**」 | ✅ |
| 3. 在线办理 | 在「职称初定申报」卡片点「**在线办理**」 | ✅ 触发 `openServiceItem('RCRS_0014','1')` |
| 4. SSO 跳转 | 经 SSO 跳 `rs.jshrss.jiangsu.gov.cn/web/functionAuth?...` | ✅ |
| 5. 嵌套 iframe | 授权页内嵌 `tobusiness?code=...` → 再内嵌 `UTP?utcName=Cd_TitleDeclarationApply` | ✅ |
| 6. 表单渲染 | 真实表单内容在第 **2 层** iframe，用 `cdp.py frames` 看到 `UTP` 帧即渲染成功 | ✅ |

> SSO 后可能弹出**腾讯滑块验证码 iframe**：安全策略，非脚本问题，人工过一下即可。

### 个人中心（江苏人社网办大厅）页面结构
左侧菜单：我的主页 / 我的信息 / 我的权益单 / **我的办件** / **我的证照** / **我的材料** / 我的考试 / 我的快递 / 账号设置
顶部统计：待提交 / 办理中 / **已办结** / 待评价

> 「我的证照」= 电子证书下载入口（江苏初定通过不发纸质快递，平台即时生成电子证，与 SKILL.md 第八节一致）。
> 「我的材料」可提前维护学历与工作经历，减少正式申报录入量。

### 办件列表字段（实测）
```
业务名称：职称初定申报
状态    ：已办结
办件编号：2608********53（已脱敏）
申请时间：2026-08-26 17:49:32
当前状态：业务审核:通过
操作    ：查看进度 ｜ 查看办件详情
```

---

## 二、关键入口速查（江苏）

```
申报入口  江苏省人才服务云平台  https://www.jssrcfwypt.org.cn（云办事 → 职称 → 职称初定申报 → 在线办理）
人社网办  https://rs.jshrss.jiangsu.gov.cn/index/
个人中心  https://rs.jshrss.jiangsu.gov.cn/web/center/main
我的办件  https://rs.jshrss.jiangsu.gov.cn/web/center/office?evaluationType=3
```

---

## 三、头号踩坑（重要）：自动化框架启动的浏览器表单不会渲染

**现象**：用 Playwright / Selenium 启动 Edge 后打开申报表单，弹窗外壳出来了（标题、姓名、暂存/确认提交按钮都在），但内容区永远停在「加载中」。

**错误归因（已纠正）**：最初以为「数据接口慢/被拦截」，实测不是。根因是：

- Playwright / Selenium 启动的实例带 `--enable-automation` → `navigator.webdriver === true`
- 政务申报站**检测该标记并拒绝渲染表单内容** → 表现就是「加载中」卡死
- 这与「浏览器坏了」「申报过了不让报」**无关**

**正确解法：原生 Edge + 纯 CDP 客户端（不带任何自动化参数）**：

```bash
# 1. 系统原生启动 Edge（头号原则：不要带 --enable-automation 类参数）
msedge.exe --remote-debugging-port=9222 --user-data-dir=<专用目录>

# 2. 用 cdp.py 当"遥控器"连上去（navigator.webdriver 保持 false）
python cdp.py launch 江苏
```

> 一句话：**浏览器必须人肉/脚本原生启动，脚本只连上去当遥控器，绝不能让框架去"启动"浏览器。**

---

## 四、SPA 操作要点（实测有效）

该站点为单页应用，大量元素不写 `href`、事件 JS 动态绑定，常见定位方式会失效：

| 现象 | 应对 |
|---|---|
| 点「职称初定申报」URL 不变、无新标签页 | 用**真实鼠标事件**按文本点击（`cdp.py click`），不要用 `JS .click()` |
| 判断页面是否进入新环节 | 比对 `cdp.py text` 输出的 `innerText` 差异，而非看 URL |
| 表单埋在多层 iframe | 用 `cdp.py frames` 看 iframe 列表；用 `cdp.py fields` 下钻到最深层表单 |
| `fill` 无反应 | 元素被浮层遮挡 → 先关弹层；或是下拉选择器（见第五节） |
| 调试端口 9222 失效、CDP 连不上 | 关掉 Edge → 重新 `cdp.py launch`（登录态可能随之丢失，重新登录即可） |

---

## 五、表单字段（江苏初定 · 基本信息层，实测 28 个字段节选）

`cdp.py fields` 下钻到最深层表单 iframe 后可见，例如：

| 字段标签 | 元素 id | 类型 |
|---|---|---|
| 姓名 | `jbxx_aac003` | text（只读/已预填） |
| 移动电话 | `jbxx_aac067` | text |
| 电子邮箱 | `jbxx_aae159` | text |
| 政治面貌 | `jbxx_aac024` | select（下拉） |
| 现从事专业 | `jbxx_bgc205` | search（下拉选择器） |
| 申报级别 | `sbxx_age278` | search（下拉选择器） |
| 申报专业 | `sbxx_aac183` | search（下拉选择器） |

`cdp.py fill "电子邮箱" "x@x.com"` 流程：下钻最深层 iframe → 按 label/id/name 模糊匹配 → `focus` + `Ctrl+A` → 逐字符发 `keyDown/char/keyUp` 事件 → React 受控组件可正确识别并更新 value。

> 普通 `text` 框用 `fill` 直接写入即可；`search`/`select` 等**下拉选择器**建议先用 `cdp.py fields` 确认类型，再人工点开选择，避免写入无效值。

---

## 六、人机协同流程（江苏示例）

```bash
# 1. 助手：确认入口
python zc.py info 江苏

# 2. 助手：原生启动 Edge 并打开申报入口（保持等待，不代登录）
python cdp.py launch 江苏

# 3. 人：在弹出 Edge 里扫码/账号登录（登录态持久化，后续免登录）

# 4. 助手：读页面、找入口
python cdp.py text
python cdp.py click "在线办理"

# 5. 助手：下钻表单、填字段（绝不点提交）
python cdp.py frames
python cdp.py fields
python cdp.py fill "电子邮箱" "x@x.com"

# 6. 人：逐项复核 → 手动点击提交（诚信承诺必须本人操作）
```

---

## 七、已知坑（实测记录）

1. **表单「加载中」= webdriver 检测**：见第三节，务必用原生 Edge + CDP，别用框架启动浏览器。
2. **SPA 点击不跳转**：用 `cdp.py click`（真实鼠标事件），判断变化看 DOM/iframe 而非 URL。
3. **登录态可能丢失**：浏览器异常退出导致 session 未落盘，重启需重扫码。正常现象。
4. **调试端口失效**：打开某些弹窗后 9222 可能失效，关 Edge 重 `cdp.py launch`。
5. **同一业务不可重复申报**：已办结的职称初定无法再次发起；测新表单需换可申报层级（如中级）。
6. **跨省份不可套用字段**：各省表单字段名、iframe 结构完全不同，换省必须重新踩点。
