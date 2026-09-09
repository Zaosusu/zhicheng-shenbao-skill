# 江苏职称申报 · 实测走查记录

> 实测日期：2026-09-09 ｜ 环境：Windows + 本机 Microsoft Edge（Playwright `channel="msedge"`，CDP 接管）
> 结论：登录、导航、办件查询链路已跑通；申报表单页停留在「加载中」，未能完成自动填表验证。

---

## 一、实测路径（江苏人社网办大厅）

| 步骤 | URL / 操作 | 结果 |
|---|---|---|
| 1. 打开大厅 | `https://rs.jshrss.jiangsu.gov.cn/index/` | ✅ 正常打开 |
| 2. 选地区 | 弹出「请选择您的办事地区」对话框，选「省本级」 | ✅ 顶部显示「省本级」 |
| 3. 登录 | 右上角「您好！请登录」→ 扫码 / 实人认证 | ✅ 显示「\*翘 · 实人认证用户」 |
| 4. 个人中心 | `https://rs.jshrss.jiangsu.gov.cn/web/center/main` | ✅ 显示待提交/办理中/已办结统计 |
| 5. 我的办件 | `https://rs.jshrss.jiangsu.gov.cn/web/center/office?evaluationType=3` | ✅ 列出全部办件 |
| 6. 推荐收藏 | 个人中心「推荐收藏」区有「职称初定申报」入口 | ✅ 入口存在 |
| 7. 打开申报表单 | 点击「职称初定申报」 | ⚠️ 弹窗外壳出来了，内容区停在「加载中」 |

### 个人中心页面结构（实测）
左侧菜单：我的主页 / 我的信息 / 我的权益单 / **我的办件** / **我的证照** / **我的材料** / 我的考试 / 我的快递 / 账号设置

顶部统计卡片：待提交 / 办理中 / **已办结** / 待评价

> 「我的证照」即电子证书下载入口，与 SKILL.md 第八节一致（江苏初定通过不发纸质快递，平台即时生成电子证）。
> 「我的材料」可提前维护学历与工作经历，能减少正式申报时的录入量。

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

## 二、关键入口速查

```
登录页      https://rs.jshrss.jiangsu.gov.cn/index/
个人中心    https://rs.jshrss.jiangsu.gov.cn/web/center/main
我的办件    https://rs.jshrss.jiangsu.gov.cn/web/center/office?evaluationType=3
备用平台    江苏人才服务云平台 https://www.jssrcfwypt.org.cn（云办事 → 职称）
```

---

## 三、SPA 踩坑（重要）

该站点为单页应用，**大量元素不写 `href`，事件通过 JS 动态绑定**，常见的自动化定位方式会失效：

| 现象 | 原因 | 应对 |
|---|---|---|
| 点「个人办事」「我要评」URL 不变、无新标签页 | 事件由 `addEventListener` 绑定，非 `href`/`onclick` | 用真实鼠标点击（`locator.click()`），不要用 `JS .click()` |
| `a` 标签 `href` 为 `null` | 同上 | 用文本 / class 定位，而非 `a[href]` |
| 搜索框 `fill()` 超时 | 元素被浮层遮挡 | 先关闭弹层，或改用键盘输入 |
| `expect_popup()` 捕获不到 | 详情页非 `window.open`，疑似同页渲染或 iframe | 改用同页 DOM diff 检测内容变化 |
| **申报表单弹窗停在「加载中」** | 弹窗外壳已渲染（标题、姓名、证件号、暂存/确认提交按钮都在），但内容区数据接口未返回；疑似接口慢或被拦截 | 重启 `serve` 后**提前挂网络监听**抓具体请求定位；本次未完成验证 |
| **调试端口 9222 失效，CDP 连不上** | 打开表单弹窗后 Edge 实例异常，端口不再监听（Edge 进程仍在） | `TaskStop` 停掉 serve → 重新 `steer.py serve`。**登录态可能随之丢失，需重新扫码** |

**已验证可用的定位方式**：
- `page.get_by_text('xxx').click()` —— 文本精确定位，可用
- `page.evaluate()` 提取 `document.body.innerText` —— 读取页面内容最可靠
- 按 `class` 定位，如 `a.wdbn-banjianxiangqing`（查看办件详情）、`a.wdbn-chakanjindu`（查看进度）

---

## 四、待办 / 可扩展

1. **表单字段补全**：本次未进入可填写的申报表单（且同一业务不可重复申报，账号已办结初定）。
   下次可在可申报层级（如中级）时走一次完整流程，把真实字段名回填进 `auto_apply.py` 的 `FIELD_KEYWORDS`。
2. **网络监听**：下次打开表单前先挂 `page.on('response')` / `requestfailed`，定位「加载中」到底是哪个接口失败。
3. **DOM diff 检测**：SPA 点击后 URL 不变，应改为比对点击前后的 `innerText` 差异来判断是否进入新环节。
