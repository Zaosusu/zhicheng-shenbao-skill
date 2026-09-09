#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职称申报入口直达工具（零第三方依赖，仅用 Python 标准库）

用法：
    python zc.py list                 列出全部地区
    python zc.py list --region 华东    按大区筛选
    python zc.py open 江苏             用默认浏览器打开该地区申报入口
    python zc.py open 江苏 --backup    打开兜底的人社厅官网
    python zc.py info 江苏             查看该地区详情（系统名/网址/备注）
    python zc.py search 工程师          关键词搜索

说明：本工具只负责"准确打开官方入口"，不代填、不代提交。
      申报材料须本人如实填写并签署诚信承诺。
"""

import sys
import argparse
import webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 地区数据：r=大区 n=地区 s=系统名 u=申报入口 b=兜底官网 k=风险等级 t=备注
PORTALS = [
    dict(r="华北", n="北京市", s="北京市专业技术人员职称管理系统", u="https://rsj.beijing.gov.cn/", b="", k="gov",
         t="主入口在市人社局「个人办事 → 职称评审」；须先经单位账号审核推荐。2026 年窗口 7/7–7/30。"),
    dict(r="华北", n="天津市", s="天津市专业技术人才职称评审信息系统", u="http://rzc.hrss.tj.gov.cn:8081/zcpsqd/home", b="", k="http",
         t="全流程网办，通过后在线下载电子证书。域名为 gov.cn 但协议为 http 非加密。"),
    dict(r="华北", n="河北省", s="河北省专业技术职称申报评审信息系统", u="http://111.63.208.196:8080/zcpsqd/home", b="https://rst.hebei.gov.cn/", k="ip",
         t="须由单位先开户、逐级审核推荐。IP 直连，失效时走人社厅官网「职称评审」专栏。"),
    dict(r="华北", n="山西省", s="山西省专业技术人才综合服务平台", u="https://59.49.26.64:8750/zcpsqd/home", b="https://rst.shanxi.gov.cn", k="ip",
         t="经省人社厅「人社一体化公共服务平台」进入。住建、自然资源等行业另有独立系统。"),
    dict(r="华北", n="内蒙古自治区", s="内蒙古人才信息库", u="https://www.nmgrck.cn/", b="", k="nongov",
         t="自治区人社厅公告的全区唯一官方申报入口。须先注册、完善业绩档案并由单位审核通过。"),

    dict(r="东北", n="辽宁省", s="按评委会分散（未确认统一入口）", u="https://rst.ln.gov.cn/", b="", k="gov",
         t="分系列、分评委会组织，未公布全省统一系统网址。进入省人社厅官网后按申报系列查对应评委会通知。"),
    dict(r="东北", n="吉林省", s="吉林智慧人社网上办事大厅（职称申报评审及证书管理）", u="https://zhrs.hrss.jl.gov.cn/jlzhrs/util/toIndex.do", b="", k="gov",
         t="省人社厅公告的全省唯一官方渠道。证书在「我的证照」自行打印。警惕各类「代办」虚假宣传。"),
    dict(r="东北", n="黑龙江省", s="黑龙江省职称服务平台（龙江职称在线）", u="http://hljzc.renshenet.org.cn/", b="https://hrss.hlj.gov.cn", k="nongov",
         t="申报、审核、证书均须经此平台，结果上传人社部职称查询系统。建议同步收藏省人社厅官网。"),

    dict(r="华东", n="上海市", s="上海市职称服务系统", u="https://www.rsj.sh.gov.cn/zcps/zcpssb/index", b="", k="gov",
         t="随申办 APP 扫码登录。各评委会按年度发文、申报时间分散。"),
    dict(r="华东", n="江苏省", s="江苏人社网上办事服务大厅（职称初定/评审）", u="https://rs.jshrss.jiangsu.gov.cn/index/", b="https://www.jssrcfwypt.org.cn", k="gov",
         t="路径：个人办事 → 人才人事 → 专业技术人员管理服务 → 职称初定/评审。初定常年受理，通过后平台即时生成电子证。"),
    dict(r="华东", n="浙江省", s="浙江省专业技术职务任职资格申报与评审管理服务平台", u="https://zcps.rlsbt.zj.gov.cn/", b="", k="gov",
         t="省厅声明为唯一平台。个人/单位账号同浙江政务服务网；单位须公示不少于 5 个工作日。"),
    dict(r="华东", n="安徽省", s="安徽省专业技术人员综合管理服务平台", u="https://hrss.ah.gov.cn/", b="", k="gov",
         t="入口：省人社厅「专题专栏 → 专技人员综合管理服务平台 → 职称申报」，经安徽政务服务网登录。"),
    dict(r="华东", n="福建省", s="福建省职称申报评审管理平台", u="http://220.160.52.235:9080", b="", k="ip",
         t="网络申报 + 现场审核结合，经闽政通登录。逾期系统自动关闭，不补报。"),
    dict(r="华东", n="江西省", s="江西省专业技术人员职称申报评审系统", u="https://hr.jxhrss.gov.cn/zcxt/", b="", k="gov",
         t="申报、审查、缴费、评审、发证全流程网上办理。个人账号由所在单位创建。"),
    dict(r="华东", n="山东省", s="山东省专业技术人员管理服务平台", u="https://117.73.253.239:9000/sdzc-web-ui/business/login/login.html", b="", k="ip",
         t="全程网办，电子证书可在平台下载。也可从省人社厅官网「系统快捷入口」进入。"),

    dict(r="华中", n="河南省", s="河南省职称管理服务平台", u="http://222.143.33.99:8083/zcsb", b="", k="ip",
         t="单位账号分级创建，个人账号由单位创建。亦可从省人社厅官网「快捷通道 → 职称评审」进入。"),
    dict(r="华中", n="湖北省", s="湖北省职称评审管理信息系统", u="https://hbzcgl.hb12333.com/zcsh/app/home.html", b="", k="nongov",
         t="高/中/初级评审全部系统申报（中级初级认定暂走原渠道）。单位公示不少于 5 个工作日。"),
    dict(r="华中", n="湖南省", s="湖南人社公共服务网上服务大厅（职称评审）", u="https://ggfw.rst.hunan.gov.cn/hrss-pw-ui-hunan/", b="", k="gov",
         t="智慧人社 APP / 电子社保卡扫码登录。资格审查材料网上提交，业绩材料线下报送。"),

    dict(r="华南", n="广东省", s="广东省专业技术人才职称管理系统", u="https://ggfw.hrss.gd.gov.cn/gdweb/ggfw/web/pub/ggfwzyjs.do", b="", k="gov",
         t="每年一次评审，错过等一年；业绩截止 12/31。电子证在「粤省事」APP 下载，部分地市另设本地系统。"),
    dict(r="华南", n="广西壮族自治区", s="广西专业技术人员职称管理服务平台", u="https://my.gxrczc.com/Login", b="", k="nongov",
         t="全区统一入口，由自治区人才市场承办。需完成继续教育公需科目。"),
    dict(r="华南", n="海南省", s="海南省职称评审管理信息系统", u="https://202.100.247.254:8001/zcps/", b="", k="ip",
         t="线上线下同步。个人账号须在单位注册后由单位建号。"),

    dict(r="西南", n="重庆市", s="重庆市专业技术人员服务平台（渝才荟）", u="https://ggfw.rlsbj.cq.gov.cn/cqzyjsrcw/positional-portal-web/", b="https://rlsbj.cq.gov.cn/ywzl/zjrc/", k="gov",
         t="通过「渝才荟」应用、渝快办登录。按评委会分散，中初级由区县评委会另行通知。"),
    dict(r="西南", n="四川省", s="四川省职称评审信息系统", u="http://103.203.218.251:8081/zcpsqd/", b="https://rst.sc.gov.cn/", k="ip",
         t="按评委会分散（系统内选相应高评委），单位 + 个人双账号。成都、绵阳等部分市州有独立系统。"),
    dict(r="西南", n="贵州省", s="贵州省人才人事综合业务管理服务平台（职称评审子系统）", u="https://rcrs.gzsrs.cn:9999/", b="https://rst.guizhou.gov.cn/ztzl/tjgzxyfwgzrcgzzcyzsbl/", k="nongov",
         t="账号实人制，系统自动匹配评委会，扫码缴费。7/1 起开放填报。"),
    dict(r="西南", n="云南省", s="云南省专业技术人才管理服务信息平台", u="https://hrss.yn.gov.cn/zjgl/", b="", k="gov",
         t="个人须先绑定用人单位账号。按系列/评委会分散，全程在线申报评审。"),
    dict(r="西南", n="西藏自治区", s="西藏自治区专业技术人员公共服务平台", u="http://221.13.83.35:8001/ggfwpt/xz/home", b="https://hrss.xizang.gov.cn/", k="ip",
         t="线上申报 + 线下交纸质原件结合。按系列/评委会/地市分散。"),

    dict(r="西北", n="陕西省", s="陕西省职称网上申报系统", u="https://rszwfw.qinyunjiuye.cn/zcsb/", b="https://rst.shaanxi.gov.cn/", k="nongov",
         t="无统一省级入口，按评委会/地市分散组织。系统账号由单位或主管部门向省人社厅申请。"),
    dict(r="西北", n="甘肃省", s="甘肃省职称申报评审管理信息系统", u="https://gszcxt.rst.gansu.gov.cn/", b="https://rst.gansu.gov.cn/", k="gov",
         t="个人申报窗口 9/1 0:00 – 9/30 24:00。电子证书可下载。"),
    dict(r="西北", n="青海省", s="青海省「互联网+人事人才」职称申报评审系统", u="https://qhrsggfw.org.cn/rsrc/zcsb", b="https://rst.qinghai.gov.cn/", k="nongov",
         t="诚信承诺制，全程网办，线下结果一律不予认可。"),
    dict(r="西北", n="宁夏回族自治区", s="宁夏人社公共服务系统 — 职称评审", u="https://12333.hrss.nx.gov.cn/nxggfw/nxggfw/", b="", k="gov",
         t="2026 年全面启用新系统。线上填报 + 纸质材料报送，按系列/评委会分散。"),
    dict(r="西北", n="新疆维吾尔自治区", s="新疆专业技术人员管理平台", u="https://www.xjzcsq.com", b="", k="nongov",
         t="由自治区人才服务中心运营，全区通用。按评委会选择申报。"),
    dict(r="西北", n="新疆生产建设兵团", s="兵团专业技术人员服务网", u="http://rsrc.xjbthrss.cn:19001", b="", k="ip",
         t="全兵团统一系统，副高及以上须答辩。注册与查专业目录另走 xjbt.yxlearning.com。"),
]

RISK = {"gov": "官方域名", "http": "http非加密", "nongov": "非gov域名", "ip": "IP直连"}


def find(keyword):
    """按地区名模糊匹配，支持「江苏」匹配「江苏省」"""
    kw = keyword.strip()
    hits = [p for p in PORTALS if kw in p["n"]]
    if not hits:
        core = kw.replace("省", "").replace("市", "").replace("自治区", "").replace("维吾尔", "").replace("壮族", "").replace("回族", "")
        hits = [p for p in PORTALS if core and core in p["n"]]
    return hits


def cmd_list(args):
    items = [p for p in PORTALS if not args.region or p["r"] == args.region]
    if not items:
        print(f"没有属于「{args.region}」的地区")
        return
    cur = None
    for p in items:
        if p["r"] != cur:
            cur = p["r"]
            print(f"\n── {cur} ──")
        print(f"  {p['n']:<12} [{RISK[p['k']]}]  {p['s']}")
    print(f"\n共 {len(items)} 个地区")


def cmd_info(args):
    hits = find(args.name)
    if not hits:
        print(f"未找到「{args.name}」，用 zc.py list 查看全部地区")
        return
    for p in hits:
        print("=" * 62)
        print(f"地区   ：{p['n']}（{p['r']}）")
        print(f"系统   ：{p['s']}")
        print(f"入口   ：{p['u']}")
        if p["b"]:
            print(f"兜底   ：{p['b']}")
        print(f"域名   ：{RISK[p['k']]}")
        print(f"备注   ：{p['t']}")
    print("=" * 62)


def cmd_open(args):
    hits = find(args.name)
    if not hits:
        print(f"未找到「{args.name}」，用 zc.py list 查看全部地区")
        return
    if len(hits) > 1:
        print("匹配到多个地区，请输得更精确：")
        for p in hits:
            print("  -", p["n"])
        return
    p = hits[0]
    url = p["b"] if (args.backup and p["b"]) else p["u"]
    if args.backup and not p["b"]:
        print(f"「{p['n']}」没有单独的兜底官网，直接打开申报入口")
    print(f"正在打开：{p['n']} — {p['s']}")
    print(f"  {url}")
    webbrowser.open(url)
    print("\n提示：申报窗口多为年度开放，若页面提示未开放，请查当年人社厅通知。")


def cmd_search(args):
    kw = args.keyword.strip().lower()
    hits = [p for p in PORTALS if kw in (p["n"] + p["s"] + p["t"]).lower()]
    if not hits:
        print(f"没有匹配「{args.keyword}」的结果")
        return
    for p in hits:
        print(f"  {p['n']:<12} {p['s']}")
        print(f"       {p['u']}")
    print(f"\n共 {len(hits)} 条")


def main():
    ap = argparse.ArgumentParser(
        description="全国职称申报官方入口直达工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：zc.py open 江苏 ｜ zc.py list --region 华东 ｜ zc.py info 广东",
    )
    sub = ap.add_subparsers(dest="cmd")

    p1 = sub.add_parser("list", help="列出地区")
    p1.add_argument("--region", help="按大区筛选：华北/东北/华东/华中/华南/西南/西北")
    p1.set_defaults(func=cmd_list)

    p2 = sub.add_parser("open", help="打开某地区申报入口")
    p2.add_argument("name", help="地区名，如 江苏 / 广东")
    p2.add_argument("--backup", action="store_true", help="打开兜底的人社厅官网")
    p2.set_defaults(func=cmd_open)

    p3 = sub.add_parser("info", help="查看某地区详情")
    p3.add_argument("name", help="地区名")
    p3.set_defaults(func=cmd_info)

    p4 = sub.add_parser("search", help="关键词搜索")
    p4.add_argument("keyword", help="搜索词")
    p4.set_defaults(func=cmd_search)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
