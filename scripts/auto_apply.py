#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职称申报 · 浏览器自动化辅助（半自动）

设计原则：
  1. 登录一次，长期复用 —— 用持久化会话目录保存 Cookie/登录态，
     下次运行免登录（各省政务系统普遍要扫码登录，这是最大痛点）。
  2. 自动填表 —— 从 profile.json 读取个人信息，自动填入表单常见字段。
  3. 绝不自动提交 —— 申报涉及本人诚信承诺，提交前必须本人逐项复核后手动点击。

前置：
  pip install playwright          （浏览器内核不用下载，复用本机 Edge）

用法：
  python auto_apply.py 江苏                 打开江苏申报入口（持久化会话）
  python auto_apply.py 江苏 --fill          打开后自动填入 profile.json 的信息
  python auto_apply.py 江苏 --fill --hold    填完不关闭浏览器，等你人工复核
  python auto_apply.py 江苏 --reset          清除登录态，重新登录
  python auto_apply.py 江苏 --headless       无界面模式（部分政务站点会拦截）

会话目录：./.session/<地区>/   （含登录 Cookie，请勿上传或分享）

注意：若需要与已打开的浏览器实时协同（人登录、助手读写），请用 steer.py。
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

from zc import find  # noqa: E402  （复用入口数据与地区匹配）

# profile.json 字段 -> 页面上可能出现的 name/id/placeholder/label 关键词
FIELD_KEYWORDS = {
    "姓名":        ["name", "xm", "xingming", "realname", "userName", "personName"],
    "身份证号":    ["idcard", "idCard", "sfzh", "identity", "idNo", "certNo"],
    "手机号":      ["phone", "mobile", "tel", "sjhm", "shouji", "contact"],
    "邮箱":        ["email", "mail", "youxiang", "yx"],
    "工作单位":    ["company", "unit", "danwei", "workUnit", "orgName", "gzdw"],
    "现从事专业":  ["major", "zhuanye", "specialty", "profession", "zy"],
    "毕业院校":    ["school", "university", "byyx", "graduate", "college"],
    "所学专业":    ["major", "zhuanye", "sxzy", "specialty"],
    "学历":        ["education", "xueli", "degree", "xl"],
    "学位":        ["degree", "xuewei", "xw"],
    "毕业时间":    ["graduate", "biyeshijian", "byDate", "gradDate"],
    "参加工作时间": ["workDate", "gzsj", "workTime", "joinWork", "canjiagongzuo"],
    "现职称":      ["title", "zhicheng", "currentTitle", "nowTitle"],
    "申报职称":    ["apply", "shenbao", "targetTitle", "applyTitle", "declare"],
    "申报系列":    ["series", "xilie", "category", "professionSeries"],
    "通讯地址":    ["address", "dizhi", "addr", "txdz"],
    "邮政编码":    ["zip", "postcode", "youbian", "yb"],
}


def load_profile(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fill_form(page, profile):
    """尽力而为地填充表单。返回 (已填字段, 未匹配字段)。"""
    filled, missed = [], []

    for field, value in profile.items():
        if not value or field.startswith("_"):
            continue
        keywords = FIELD_KEYWORDS.get(field, [field])
        ok = False
        for kw in keywords:
            if ok:
                break
            selectors = [
                f"input[name*='{kw}' i]",
                f"input[id*='{kw}' i]",
                f"input[placeholder*='{kw}' i]",
                f"textarea[name*='{kw}' i]",
                f"textarea[id*='{kw}' i]",
                f"select[name*='{kw}' i]",
                f"select[id*='{kw}' i]",
            ]
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.count() == 0 or not loc.is_visible():
                        continue
                    tag = loc.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        try:
                            loc.select_option(label=str(value))
                        except Exception:
                            continue
                    else:
                        loc.fill(str(value))
                    filled.append(f"{field} ← {sel}")
                    ok = True
                    break
                except Exception:
                    continue
            if ok:
                break
        if not ok:
            missed.append(field)

    return filled, missed


def main():
    ap = argparse.ArgumentParser(
        description="职称申报浏览器自动化辅助（半自动，不代提交）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("region", help="地区名，如 江苏 / 广东 / 浙江")
    ap.add_argument("--fill", action="store_true", help="自动填入 profile.json 中的信息")
    ap.add_argument("--hold", action="store_true", help="操作完成后保持浏览器打开，等待人工复核")
    ap.add_argument("--reset", action="store_true", help="清除登录态重新登录")
    ap.add_argument("--headless", action="store_true", help="无界面模式")
    ap.add_argument("--profile", default=os.path.join(HERE, "profile.json"), help="个人信息 JSON 路径")
    args = ap.parse_args()

    hits = find(args.region)
    if not hits:
        print(f"未找到「{args.region}」，用 zc.py list 查看全部地区")
        return
    if len(hits) > 1:
        print("匹配到多个地区，请输得更精确：", "、".join(p["n"] for p in hits))
        return

    p = hits[0]
    session_dir = os.path.join(HERE, ".session", p["n"])
    os.makedirs(session_dir, exist_ok=True)

    if args.reset:
        print(f"[reset] 会话目录保留，将重新登录：{session_dir}")

    print("=" * 60)
    print(f"地区   ：{p['n']}")
    print(f"系统   ：{p['s']}")
    print(f"入口   ：{p['u']}")
    print(f"会话   ：{session_dir}")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n缺少 playwright，请先安装：pip install playwright")
        print("（浏览器内核无需下载，本脚本复用本机 Edge）")
        return

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=session_dir,
                channel="msedge",
                headless=args.headless,
                no_viewport=True,
                args=["--start-maximized"],
            )
        except Exception as e:
            print(f"\n启动 Edge 失败：{type(e).__name__}: {str(e)[:200]}")
            print("若 Edge 正在运行且占用了配置目录，请先关闭 Edge 后重试。")
            return

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            page.goto(p["u"], timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"\n打开页面超时或失败：{type(e).__name__}: {str(e)[:200]}")
            print("政务站点偶发较慢，可重试；若持续失败请检查网络或用 zc.py open 手动打开。")
            if not args.hold:
                ctx.close()
            return

        print(f"\n已打开：{page.title()[:60]}")

        if p["k"] in ("ip", "nongov"):
            print("注意：该入口非标准 gov.cn 域名，浏览器可能提示证书风险，请确认后继续。")

        if args.fill:
            profile = load_profile(args.profile)
            if not profile:
                print(f"\n未找到 {args.profile}")
                print("请先复制 profile.example.json 为 profile.json 并填写个人信息。")
            else:
                print("\n提示：如尚未登录，请先在浏览器里完成登录（扫码/账号），")
                print("      登录后回到命令行按回车，脚本将开始填表。")
                try:
                    input("  >>> 登录完成后按回车继续（或直接回车跳过等待）：")
                except EOFError:
                    pass
                print("\n开始填表...")
                filled, missed = fill_form(page, profile)
                print(f"\n已填充 {len(filled)} 项：")
                for f_ in filled:
                    print("  ✓", f_)
                if missed:
                    print(f"\n以下 {len(missed)} 项未自动匹配到输入框，请手动填写：")
                    for m in missed:
                        print("  ·", m)

        print("\n" + "!" * 60)
        print("重要：本脚本【不会】自动点击提交。")
        print("      申报材料须本人逐项核对，并签署诚信承诺后再手动提交。")
        print("!" * 60)

        if args.hold:
            print("\n浏览器保持打开，请人工复核后手动提交。")
            print("完成后回到命令行按 Ctrl+C 结束。")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n已结束。登录态已保存，下次运行免登录。")
        else:
            print("\n将在 3 秒后关闭浏览器（登录态已保存）。")
            print("如需停留复核，请加 --hold 参数。")
            time.sleep(3)

        ctx.close()


if __name__ == "__main__":
    main()
