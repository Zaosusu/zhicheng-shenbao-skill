#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯 CDP 浏览器驱动（不依赖 Playwright / Selenium）

为什么不用 Playwright 启动浏览器：
  Playwright 启动的实例会带 --enable-automation，导致 navigator.webdriver === true，
  政务申报站检测到后表单不渲染（永远停在「加载中」）。

本脚本的做法：
  1. 用系统原生 Edge 启动（只加 --remote-debugging-port，不传任何自动化参数）
     msedge.exe --remote-debugging-port=9222 --user-data-dir=<某个专用目录>
  2. 本脚本通过 CDP 协议连上去，作为"遥控器"驱动它。

浏览器侧因此保持 navigator.webdriver === false，与真人操作完全一致。

依赖：websocket-client（pip install websocket-client）

命令：
  python cdp.py launch [<地区>]      # 启动原生 Edge（可选顺便打开某地区申报入口）
  python cdp.py nav <url>            # 打开网址
  python cdp.py text [n]             # 输出页面纯文本（默认 1500 字）
  python cdp.py click <文本>          # 按文本找元素，真实鼠标事件点击（SPA 必需）
  python cdp.py frames               # 列出所有 iframe（判断申报表单是否渲染出来）
  python cdp.py fields               # 下钻到最深 iframe，列出所有可填字段
  python cdp.py fill "标签关键字" "值"   # 在表单 iframe 里填一个字段
  python cdp.py eval <js>            # 执行任意 JS
  python cdp.py shot [文件名]         # 截图存档
  python cdp.py tabs                 # 列出所有标签页
"""

import sys
import os
import io
import json
import time
import base64
import argparse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(HERE, ".shots")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
USER_DATA = os.path.join(HERE, ".session", "native-edge")


def http_json(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_ws(port):
    """取当前活动标签页的 WebSocket 调试地址"""
    targets = http_json(f"http://127.0.0.1:{port}/json/list")
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise SystemExit(f"没有可连接的标签页（Edge 是否已在 {port} 端口启动？）")
    return pages[0], targets


class CDP:
    def __init__(self, ws_url):
        import websocket
        # suppress_origin: Edge 较新版本会校验 Origin，带 Origin 头会被 403 拒绝
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})

    def eval(self, expr, timeout=30):
        r = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
            "userGesture": True,
        })
        return r.get("result", {}).get("value")

    def mouse_click(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", {
                "type": t, "x": x, "y": y,
                "button": "left", "clickCount": 1, "buttons": 1 if t == "mousePressed" else 0,
            })

    def key_text(self, text):
        """Input.dispatchKeyEvent 发送真实字符"""
        for ch in text:
            for t in ("keyDown", "keyUp"):
                self.send("Input.dispatchKeyEvent", {
                    "type": t,
                    "text": ch,
                    "unmodifiedText": ch,
                    "key": ch,
                })

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def connect(port):
    page, _ = get_ws(port)
    return CDP(page["webSocketDebuggerUrl"])


# 点击：先滚动到视口，再取几何中心
JS_RECT = r"""(txt) => {
  let el = null;
  document.querySelectorAll('li,a,span,div,button,td,label').forEach(e => {
    if ((e.innerText || '').trim() === txt && !el) el = e;
  });
  if (!el) return null;
  el.scrollIntoView({block: 'center'});
  const b = el.getBoundingClientRect();
  if (b.width < 2 || b.height < 2) return null;
  return {tag: el.tagName, x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2)};
}"""

# 表单探测：政务申报表单通常埋在多层 iframe 里（例如 江苏是
# 主页 → tobusiness → UTP(Cd_TitleDeclarationApply)），
# 这里自动下钻到"含有最多输入控件"的那一层文档。
JS_FORM_DOC = r"""function __formDoc() {
  let best = document, bestN = 0;
  function walk(d, depth) {
    if (depth > 5) return;
    Array.from(d.querySelectorAll('iframe')).forEach(f => {
      let sd = null;
      try { sd = f.contentDocument; } catch (e) { sd = null; }
      if (!sd) return;
      let n = 0;
      try { n = sd.querySelectorAll('input,select,textarea').length; } catch (e) { n = 0; }
      if (n > bestN) { bestN = n; best = sd; }
      walk(sd, depth + 1);
    });
  }
  walk(document, 0);
  return best;
}"""


def cmd_launch(a):
    hits = []
    url = a.url
    if a.region:
        sys.path.insert(0, HERE)
        from zc import find  # noqa: E402
        hits = find(a.region)
        if not hits:
            print(f"未找到「{a.region}」")
            return 1
        if len(hits) > 1:
            print("匹配到多个：", "、".join(p["n"] for p in hits))
            return 1
        url = hits[0]["u"]
    if not url:
        url = "https://rs.jshrss.jiangsu.gov.cn/index/"
    os.makedirs(USER_DATA, exist_ok=True)
    try:
        http_json(f"http://127.0.0.1:{a.port}/json/version", timeout=3)
        print(f"已在运行（端口 {a.port}），直接导航")
        c = connect(a.port)
        c.send("Page.navigate", {"url": url})
        c.close()
        return 0
    except Exception:
        pass
    if not os.path.exists(EDGE):
        print(f"找不到 Edge：{EDGE}")
        return 1
    import subprocess
    subprocess.Popen([EDGE, f"--remote-debugging-port={a.port}",
                      f"--user-data-dir={USER_DATA}", url])
    for _ in range(20):
        time.sleep(1)
        try:
            http_json(f"http://127.0.0.1:{a.port}/json/version", timeout=2)
            print(f"原生 Edge 已启动，调试端口 {a.port}")
            print(f"已打开：{url}")
            return 0
        except Exception:
            continue
    print("启动超时：调试端口未就绪")
    return 1


def cmd_nav(a):
    c = connect(a.port)
    c.send("Page.navigate", {"url": a.url})
    time.sleep(3)
    print("→", a.url)
    print("TITLE", c.eval("document.title"))
    c.close()
    return 0


def cmd_click(a):
    c = connect(a.port)
    before = c.eval("location.href")
    r = c.eval(f"({JS_RECT})({json.dumps(a.text, ensure_ascii=False)})")
    if not r:
        print(f"页面上看不到「{a.text}」")
        print("提示：先 cdp.py nav 到正确页面，或用 cdp.py text 看页面上到底有什么")
        c.close()
        return 1
    c.mouse_click(r["x"], r["y"])
    time.sleep(a.wait)
    after = c.eval("location.href")
    print(f"点击 <{r['tag']}> ({r['x']},{r['y']})")
    print(f"URL: {before}  ->  {after}")
    if before == after:
        n = c.eval("Array.from(document.querySelectorAll('iframe')).map(f=>f.src).length")
        print(f"（SPA 同页更新，URL 不变；当前 iframe 数 {n}）")
    c.close()
    return 0


def cmd_text(a):
    c = connect(a.port)
    print("URL  ", c.eval("location.href"))
    print("TITLE", c.eval("document.title"))
    print("-" * 55)
    print((c.eval(f"document.body.innerText.slice(0,{a.limit})") or "").strip())
    c.close()
    return 0


def cmd_frames(a):
    c = connect(a.port)
    fs = c.eval("() => Array.from(document.querySelectorAll('iframe')).map(f=>f.src)")
    print(f"iframe 数：{len(fs or [])}")
    for f in fs or []:
        print("  ", f[:130])
        if any(k in f for k in ("UTP", "business", "loading")):
            print("      ↑ 申报表单容器")
    c.close()
    return 0


def cmd_fields(a):
    """列出最深 iframe 里的可填字段"""
    c = connect(a.port)
    data = c.eval(f"""
        (() => {{
          {JS_FORM_DOC}
          const d = __formDoc();
          const out = [];
          d.querySelectorAll('input,select,textarea').forEach(e => {{
            const r = e.getBoundingClientRect();
            if (r.width < 2 && r.height < 2) return;
            const ph = (e.getAttribute('placeholder') || '');
            const id = e.id || '';
            const nm = e.name || '';
            let label = '';
            const item = e.closest('.ant-form-item, li, td, .form-item');
            if (item) {{
              const all = Array.from(item.querySelectorAll('*'));
              const lbl = all.find(x => x !== e && /^label$/i.test(x.tagName) && (x.innerText||'').trim());
              if (lbl) label = (lbl.innerText || '').trim();
            }}
            if (!label) {{
              const all = Array.from(d.querySelectorAll('label'));
              const lbl = all.find(x => x.getAttribute('for') && (x.getAttribute('for') === id));
              if (lbl) label = (lbl.innerText || '').trim();
            }}
            out.push({{
              tag: e.tagName.toLowerCase(),
              type: e.type || '',
              id: id,
              name: nm,
              placeholder: ph,
              label: label.slice(0, 30),
              value: (e.value || '').slice(0, 30),
              empty: !(e.value || '').trim(),
            }});
          }});
          return out.slice(0, {a.limit});
        }})()
    """)
    print(f"最深表单层字段数：{len(data or [])}")
    for f in data or []:
        star = " *" if not f["empty"] else ""
        print(f"  [{f['tag']:<7} {f['type']:<10}] id={f['id']:<24} name={f['name']:<22} label={f['label']:<16} placeholder={f['placeholder']:<16}{star}")
    c.close()
    return 0


def cmd_fill(a):
    """按 label/placeholder/id/name 关键字匹配一个字段，模拟人工输入"""
    c = connect(a.port)
    needle = json.dumps(a.key, ensure_ascii=False)
    value = a.value
    r = c.eval(f"""
        (() => {{
          {JS_FORM_DOC}
          const d = __formDoc();
          const want = {needle};
          function score(e) {{
            const id = (e.id || '').toLowerCase();
            const nm = (e.name || '').toLowerCase();
            const ph = (e.getAttribute('placeholder') || '').toLowerCase();
            let label = '';
            const item = e.closest('.ant-form-item, li, td, .form-item');
            if (item) {{
              const all = Array.from(item.querySelectorAll('*'));
              const lbl = all.find(x => x !== e && /^label$/i.test(x.tagName) && (x.innerText||'').trim());
              if (lbl) label = (lbl.innerText || '').trim().toLowerCase();
            }}
            if (!label) {{
              const all = Array.from(d.querySelectorAll('label'));
              const lbl = all.find(x => x.getAttribute('for') && x.getAttribute('for') === e.id);
              if (lbl) label = (lbl.innerText || '').trim().toLowerCase();
            }}
            const hay = [id, nm, ph, label].join(' ');
            return hay.includes(want.toLowerCase()) ? (label.includes(want.toLowerCase()) ? 3 : 2) : 0;
          }}
          let best = null, bestS = 0;
          d.querySelectorAll('input,select,textarea').forEach(e => {{
            const r = e.getBoundingClientRect();
            if (r.width < 2 && r.height < 2) return;
            const s = score(e);
            if (s > bestS) {{ bestS = s; best = e; }}
          }});
          if (!best) return {{err: '找不到含 "' + want + '" 的字段'}};
          best.scrollIntoView({{block: 'center'}});
          const b = best.getBoundingClientRect();
          const x = Math.round(b.x + b.width/2), y = Math.round(b.y + b.height/2);
          // 返回匹配信息，但不在这里修改值（CDP 通过 Input.dispatchKeyEvent 输入）
          return {{
            tag: best.tagName.toLowerCase(),
            type: best.type || '',
            id: best.id || '',
            name: best.name || '',
            x: x, y: y,
            old: best.value || '',
          }};
        }})()
    """)
    if not r or r.get("err"):
        print(r.get("err", "未找到字段"))
        c.close()
        return 1
    print(f"匹配字段 <{r['tag']} type={r['type']}> id={r['id']} @ ({r['x']},{r['y']})")
    if r.get("tag") == "select":
        # select 通过 JS 设置并触发 change
        c.eval(f"""
          (() => {{
            {JS_FORM_DOC}
            const el = __formDoc().querySelector('#{r['id']}');
            if (!el) return 'missing';
            const v = {json.dumps(value, ensure_ascii=False)};
            let opt = Array.from(el.options).find(o => o.text.trim() === v || o.value === v);
            if (!opt) opt = Array.from(el.options).find(o => o.text.includes(v));
            if (opt) {{ el.value = opt.value; el.dispatchEvent(new Event('change', {{bubbles:true}})); return 'set '+opt.value; }}
            return 'options: '+Array.from(el.options).map(o=>o.text).join(', ');
          }})()
        """)
        print(f"已设置 select 值：{value}")
    else:
        # 聚焦 + 全选 + 用完整 keyDown/char/keyUp 序列输入（React 受控组件可识别）
        c.eval(f"""
          (() => {{
            {JS_FORM_DOC}
            const el = __formDoc().querySelector('#{r['id']}');
            if (el) {{ el.focus(); el.select && el.select(); }}
            return el ? 'focused' : 'missing';
          }})()
        """)
        time.sleep(0.3)
        # Ctrl+A
        for t in ("keyDown", "keyUp"):
            c.send("Input.dispatchKeyEvent", {
                "type": t, "key": "a", "code": "KeyA",
                "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                "modifiers": 2 if t == "keyDown" else 0,
            })
        time.sleep(0.2)
        if value == "":
            # 清空：Delete
            for t in ("keyDown", "keyUp"):
                c.send("Input.dispatchKeyEvent", {
                    "type": t, "key": "Delete", "code": "Delete",
                    "windowsVirtualKeyCode": 46, "nativeVirtualKeyCode": 46,
                })
            time.sleep(0.3)
            print("已清空字段")
            c.close()
            return 0
        for ch in value:
            # 受控组件：keyDown 不带 text（避免重复），char 带 text 产生字符，keyUp 收尾
            vk = ord(ch.upper()) if ch.isalpha() else (ord(ch) if ord(ch) < 128 else 0)
            code = f"Key{ch.upper()}" if ch.isalpha() and ord(ch) < 128 else ""
            # keyDown
            params_down = {"type": "keyDown", "key": ch, "code": code}
            if vk:
                params_down["windowsVirtualKeyCode"] = vk
                params_down["nativeVirtualKeyCode"] = vk
            c.send("Input.dispatchKeyEvent", params_down)
            # char（真正输入）
            c.send("Input.dispatchKeyEvent", {"type": "char", "text": ch, "key": ch,
                                             "unmodifiedText": ch})
            # keyUp
            params_up = {"type": "keyUp", "key": ch, "code": code}
            if vk:
                params_up["windowsVirtualKeyCode"] = vk
                params_up["nativeVirtualKeyCode"] = vk
            c.send("Input.dispatchKeyEvent", params_up)
            time.sleep(0.02)
        time.sleep(0.3)
        print(f"已键入：{value[:80]}{'...' if len(value) > 80 else ''}")
    c.close()
    return 0


def cmd_eval(a):
    c = connect(a.port)
    print(json.dumps(c.eval(a.js), ensure_ascii=False, indent=2)[:4000])
    c.close()
    return 0


def cmd_shot(a):
    c = connect(a.port)
    r = c.send("Page.captureScreenshot", {"format": "png"})
    os.makedirs(SHOT_DIR, exist_ok=True)
    name = a.name or f"cdp_{int(time.time())}.png"
    if not name.endswith(".png"):
        name += ".png"
    p = os.path.join(SHOT_DIR, name)
    with open(p, "wb") as f:
        f.write(base64.b64decode(r["data"]))
    print("截图：", p)
    print("注意：截图含姓名/证件号，已存在被 gitignore 的 .shots/ 目录")
    c.close()
    return 0


def cmd_tabs(a):
    _, targets = get_ws(a.port)
    for t in targets:
        if t.get("type") == "page":
            print(f"  {t.get('title','')[:30]:<32} {t.get('url','')[:100]}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="纯 CDP 浏览器驱动（不带自动化标记）")
    ap.add_argument("--port", type=int, default=9222)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("launch", help="启动原生 Edge")
    p.add_argument("region", nargs="?")
    p.add_argument("--url")
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("nav", help="打开网址")
    p.add_argument("url")
    p.set_defaults(func=cmd_nav)

    p = sub.add_parser("text", help="页面纯文本")
    p.add_argument("--limit", type=int, default=1500)
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("click", help="按文本点击（真实鼠标事件）")
    p.add_argument("text")
    p.add_argument("--wait", type=float, default=4.0)
    p.set_defaults(func=cmd_click)

    p = sub.add_parser("frames", help="列出 iframe")
    p.set_defaults(func=cmd_frames)

    p = sub.add_parser("fields", help="列出最深表单层的可填字段")
    p.add_argument("--limit", type=int, default=80)
    p.set_defaults(func=cmd_fields)

    p = sub.add_parser("fill", help="填写一个字段（不提交）")
    p.add_argument("key", help="label/placeholder/id/name 关键字")
    p.add_argument("value", help="要填入的值")
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser("eval", help="执行 JS")
    p.add_argument("js")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("shot", help="截图")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_shot)

    p = sub.add_parser("tabs", help="列出标签页")
    p.set_defaults(func=cmd_tabs)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
