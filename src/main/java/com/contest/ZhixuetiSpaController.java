package com.contest;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * 智学体 Vue SPA History 模式回退：浏览器访问 /student/** 等路径时落到 SPA 入口页。
 * 学生主登录入口仍为宿主静态页 /student/login.html；/login|/register 重定向到原登录/注册。
 * 教师端入口仍由 AiTeacherController 的 / → /login.html 负责。
 */
@Controller
public class ZhixuetiSpaController {

    private static final String SPA = "forward:/zhixueti-spa.html";

    /** 智学体 /login|/register 不再作为对外主登录入口 */
    @GetMapping("/login")
    public String redirectStudentLogin() {
        return "redirect:/student/login.html";
    }

    @GetMapping("/register")
    public String redirectStudentRegister() {
        return "redirect:/student/register.html";
    }

    /**
     * 管理员端只保留一套（SPA）。多页版旧地址统一重定向，避免出现"两个管理员端"。
     * 旧书签、旧链接都不会再进入第二套界面。
     */
    @GetMapping({
            "/admin/login.html",
            "/admin/index.html"
    })
    public String redirectLegacyAdminLogin() {
        return "redirect:/admin/login";
    }

    @GetMapping("/admin/home.html")
    public String redirectLegacyAdminHome() {
        return "redirect:/admin/dashboard?from=legacy";
    }

    @GetMapping("/admin/users.html")
    public String redirectLegacyAdminUsers() {
        return "redirect:/admin/users?from=legacy";
    }

    @GetMapping("/admin/admins.html")
    public String redirectLegacyAdminAdmins() {
        return "redirect:/admin/admins?from=legacy";
    }

    @GetMapping("/admin/content.html")
    public String redirectLegacyAdminContent() {
        return "redirect:/admin/content-audit?from=legacy";
    }

    @GetMapping("/admin/audit.html")
    public String redirectLegacyAdminAudit() {
        return "redirect:/admin/operation-logs?from=legacy";
    }

    @GetMapping("/admin/system.html")
    public String redirectLegacyAdminSystem() {
        return "redirect:/admin/settings?from=legacy";
    }

    /** 密码重置队列已并入 SPA「用户管理」页，旧地址跳到同一处 */
    @GetMapping("/admin/resets.html")
    public String redirectLegacyAdminResets() {
        return "redirect:/admin/users?resets=1";
    }

    /** 兼容旧路径：/admin/system 统一落到 SPA 系统设置页，避免 Whitelabel 404 */
    @GetMapping("/admin/system")
    public String redirectAdminSystem() {
        return "redirect:/admin/settings";
    }

    @GetMapping({
            "/student",
            "/student/",
            "/student/home",
            "/student/course-center",
            "/student/course-study",
            "/student/profile-dialogue",
            "/student/profile-voice-call",
            "/student/resources",
            "/student/resources/square",
            "/student/resources/graph",
            "/student/path",
            "/student/tutor",
            "/student/dashboard",
            "/student/center",
            "/student/homework",
            "/student/tutor/lecture/generate"
    })
    public String spaFixed() {
        return SPA;
    }

    @GetMapping({
            "/student/class/{classId}",
            "/student/resources/{id}",
            "/student/tutor/lecture/{lectureId}",
            "/admin/login",
            "/admin",
            "/admin/",
            "/admin/dashboard",
            "/admin/console",
            "/admin/users",
            "/admin/users/{id}",
            "/admin/admins",
            "/admin/menus",
            "/admin/resources",
            "/admin/profile-config",
            "/admin/learning-paths",
            "/admin/generated-content",
            "/admin/documents",
            "/admin/content-audit",
            "/admin/agents",
            "/admin/settings",
            "/admin/operation-logs",
            "/admin/exception-monitor",
            "/admin/forbidden"
    })
    public String spaAdminAndDetail() {
        return SPA;
    }
}
