#!/usr/bin/env python3
"""线上部署冒烟验证：对目标主机跑页面状态码 + 核心接口检查。

用法：python deploy/verify_online.py [base_url]
默认：http://47.120.18.218:8082
"""
import sys

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://47.120.18.218:8082").rstrip("/")

PAGES = [
    "/login.html", "/index.html", "/classes.html", "/projects.html",
    "/student/login.html", "/student", "/student/course-center",
    "/student/resources/square", "/student/tutor", "/student/dashboard",
    "/admin/login.html", "/admin/home.html", "/admin/system.html",
    "/admin", "/admin/dashboard", "/admin/settings", "/admin/agents", "/admin/system",
]


def main() -> int:
    print(f"== 线上冒烟：{BASE} ==")
    bad = []
    for p in PAGES:
        try:
            r = requests.get(BASE + p, timeout=12, allow_redirects=False)
            ok = r.status_code in (200, 302)
            print(f"  {'OK ' if ok else 'BAD'} {r.status_code} {p}")
            if not ok:
                bad.append((p, r.status_code))
        except Exception as e:  # noqa: BLE001
            print(f"  ERR     {p}: {str(e)[:60]}")
            bad.append((p, "ERR"))

    # 桥接：学生端登录接口经宿主代理
    try:
        r = requests.post(
            BASE + "/api/v1/auth/login",
            json={"username": "__probe__", "password": "__probe__"},
            timeout=12,
        )
        # 预期业务失败（code!=0）但 HTTP 200/400 均可，证明代理链路通
        print(f"  PROXY /api/v1/auth/login -> HTTP {r.status_code}")
        if r.status_code >= 500:
            bad.append(("/api/v1/auth/login", r.status_code))
    except Exception as e:  # noqa: BLE001
        print(f"  ERR proxy: {str(e)[:60]}")
        bad.append(("proxy", "ERR"))

    print("== 结果：", "全部通过" if not bad else f"异常 {bad}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
