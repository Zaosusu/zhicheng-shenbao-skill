#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人机协同申报驱动器（CDP 模式）

思路：
  serve  → 启动一个带调试端口的 Edge（持久化会话，保持打开），人在这个窗口里登录
  text   → 读取页面纯文本，判断当前在哪个环节（SPA 站点最可靠）
  shot   → 截图存档
  dom    → 提取页面上的表单/按钮结构，用于定位该点哪、该填什么
  click  → 按文本点击元素（链接/按钮/菜单）
  fill   → 按关键词填充输入框
  url    → 打开指定网址 / 查看当前网址

这样人负责"登录 + 做决策 + 提交"，助手负责"看页面 + 填表 + 点下一步"，
全程共用同一个浏览器窗口，登录态不丢。

典型流程：
  python steer.py serve 江苏          # 浏览器打开申报大厅
  （人工扫码登录）
  python steer.py text                # 看一眼登录后页面
  python steer.py dom                 # 看表单结构
  python steer.py click "职称初定"     # 点进申报入口
  python steer.py fill 姓名 张三       # 填表
"""

import sys
import os
import json
import time
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from zc import find  # noqa: E402

SHOT_DIR = os.path.join(HERE, ".shots")


def session_dir(region_name):
    d = os.path.join(HERE, ".session", region_name)
    os.makedirs(d, exist_ok=True)
    return d


def cmd_serve(a):
    hits = find(a.region)
    if not hits:
        print(f"未找到「{a.region}」")
        return 1
    if len(hits) > 1:
        print("匹配到多个：", "、".join(p["n"] for p in hits))
        return 1
    p = hits[0]
    sd = session_dir(p["n"])

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=sd,
                channel="msedge",
                headless=False,
                no_viewport=True,
                args=[f"--remote-debugging-port={a.port}", "--start-maximized"],
            )
        except Exception as e:
            print(f"启动 Edge 失败：{type(e).__name__}: {str(e)[:200]}")
            print("若该会话目录已被其他 Edge 实例占用，请先关闭该窗口后重试。")
            return 1
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(p["u"], wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"打开失败：{type(e).__name__}: {str(e)[:150]}")
        print(f"READY url={page.url}", flush=True)
        print(f"TITLE {page.title()[:80]}", flush=True)
        print(f"SESSION {sd}", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("正在关闭并保存登录态...", flush=True)
        ctx.close()
    return 0


def _connect(port):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    except Exception as e:
        pw.stop()
        raise SystemExit(
            f"连不上调试端口 {port}：{type(e).__name__}\n"
            f"通常是浏览器实例异常导致端口失效。请停掉 serve 后重新运行 steer.py serve <地区>。"
        )
    ctx = browser.contexts[0]
    page = None
    for pg in ctx.pages:
        if pg.url and not pg.url.startswith("devtools://"):
            page = pg
            break
    if page is None:
        page = ctx.new_page()
    return pw, browser, page


def cmd_text(a):
    """输出页面纯文本 —— SPA 站点判断页面状态最可靠的方式（比截图更准）"""
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        txt = page.evaluate("() => document.body.innerText")
        print(f"URL   {page.url}")
        print(f"TITLE {page.title()[:80]}")
        print("-" * 55)
        print(txt[: a.limit])
    finally:
        browser.close()
        pw.stop()
    return 0


def cmd_shot(a):
    os.makedirs(SHOT_DIR, exist_ok=True)
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        out = a.out or os.path.join(SHOT_DIR, f"shot_{int(time.time())}.png")
        page.screenshot(path=out, full_page=a.full)
        print(f"URL   {page.url}")
        print(f"TITLE {page.title()[:80]}")
        print(f"SHOT  {out}")
    finally:
        browser.close()
        pw.stop()
    return 0


def cmd_dom(a):
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        js = """() => {
          const out = [];
          const sel = 'input,select,textarea,button,a,[role=button]';
          document.querySelectorAll(sel).forEach((e) => {
            const r = e.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) return;
            const st = getComputedStyle(e);
            if (st.visibility === 'hidden' || st.display === 'none') return;
            const lab = (e.labels && e.labels[0]) ? e.labels[0].innerText : '';
            out.push({
              tag: e.tagName.toLowerCase(),
              type: e.type || '',
              name: e.name || '',
              id: e.id || '',
              ph: e.placeholder || '',
              lab: (lab || '').trim().slice(0, 30),
              txt: (e.innerText || e.value || '').trim().slice(0, 40)
            });
          });
          return out;
        }"""
        els = page.evaluate(js)
        print(f"URL   {page.url}")
        print(f"TITLE {page.title()[:80]}")
        print(f"共 {len(els)} 个可见可交互元素：\n")
        for i, e in enumerate(els[: a.limit]):
            bits = [e["tag"]]
            if e["type"]:
                bits.append(f"type={e['type']}")
            if e["name"]:
                bits.append(f"name={e['name']}")
            if e["id"]:
                bits.append(f"id={e['id']}")
            if e["lab"]:
                bits.append(f"label={e['lab']}")
            if e["ph"]:
                bits.append(f"ph={e['ph']}")
            if e["txt"]:
                bits.append(f"「{e['txt']}」")
            print(f"[{i:>3}] " + " | ".join(bits))
    finally:
        browser.close()
        pw.stop()
    return 0


def cmd_click(a):
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        text = a.text.strip()
        for strategy in ["text", "partial"]:
            try:
                if strategy == "text":
                    loc = page.get_by_text(text, exact=True).first
                else:
                    loc = page.get_by_text(text).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=5000)
                    print(f"已点击：「{text}」")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    time.sleep(1)
                    print(f"URL   {page.url}")
                    print(f"TITLE {page.title()[:80]}")
                    return 0
            except Exception:
                continue
        for role in ["button", "link"]:
            try:
                loc = page.get_by_role(role, name=text).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=5000)
                    print(f"已点击（{role}）：「{text}」")
                    time.sleep(1)
                    print(f"URL   {page.url}")
                    return 0
            except Exception:
                continue
        print(f"没找到可点击的「{text}」，先用 steer.py dom / text 看看页面上有什么")
        return 1
    finally:
        browser.close()
        pw.stop()


def cmd_fill(a):
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        kw, val = a.keyword, a.value
        sels = [
            f"input[name*='{kw}' i]", f"input[id*='{kw}' i]", f"input[placeholder*='{kw}' i]",
            f"textarea[name*='{kw}' i]", f"textarea[id*='{kw}' i]", f"textarea[placeholder*='{kw}' i]",
        ]
        for sel in sels:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.fill(val)
                    print(f"已填：{sel} = {val}")
                    return 0
            except Exception:
                continue
        try:
            loc = page.get_by_label(kw).first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(val)
                print(f"已填（label）：{kw} = {val}")
                return 0
        except Exception:
            pass
        print(f"没找到匹配「{kw}」的输入框，先用 steer.py dom 看表单结构")
        return 1
    finally:
        browser.close()
        pw.stop()


def cmd_url(a):
    pw, browser, page = _connect(a.port)
    try:
        page.bring_to_front()
        if a.target:
            page.goto(a.target, wait_until="domcontentloaded", timeout=45000)
            print(f"已打开 {a.target}")
        print(f"URL   {page.url}")
        print(f"TITLE {page.title()[:80]}")
    finally:
        browser.close()
        pw.stop()
    return 0


def main():
    ap = argparse.ArgumentParser(description="人机协同申报驱动器（CDP）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("serve", help="启动浏览器（保持打开，供人工登录）")
    p.add_argument("region")
    p.add_argument("--port", type=int, default=9222)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("text", help="输出页面纯文本（判断状态最可靠）")
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--limit", type=int, default=3000)
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("shot", help="截图当前页面")
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--out", help="输出路径")
    p.add_argument("--full", action="store_true", help="整页截图")
    p.set_defaults(func=cmd_shot)

    p = sub.add_parser("dom", help="提取页面表单/按钮结构")
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(func=cmd_dom)

    p = sub.add_parser("click", help="按文本点击")
    p.add_argument("text")
    p.add_argument("--port", type=int, default=9222)
    p.set_defaults(func=cmd_click)

    p = sub.add_parser("fill", help="填充输入框")
    p.add_argument("keyword")
    p.add_argument("value")
    p.add_argument("--port", type=int, default=9222)
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser("url", help="打开网址 / 查看当前网址")
    p.add_argument("target", nargs="?")
    p.add_argument("--port", type=int, default=9222)
    p.set_defaults(func=cmd_url)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
