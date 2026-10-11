package com.contest;

import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.regex.Pattern;

/**
 * HTML 入口禁用强缓存。
 *
 * 背景：SPA 入口页与教师端多页共用静态 HTML，而 JS/CSS 带内容哈希。
 * 若浏览器缓存了旧 HTML，用户会一直加载旧 bundle——改了 bug 也“看起来没修好”
 * （典型表现：点击无反应、页面白屏）。这里只对 HTML 文档禁用缓存，
 * 带哈希的 /assets/* 仍走强缓存，不影响性能。
 */
@Component
@Order(5)
public class HtmlNoCacheFilter extends OncePerRequestFilter {

    private static final Pattern HTML = Pattern.compile(".*\\.html$", Pattern.CASE_INSENSITIVE);

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        boolean isSpaEntry = "/student".equals(path) || "/student/".equals(path)
                || "/admin".equals(path) || "/admin/".equals(path)
                || "/admin/login".equals(path) || "/zhixueti-spa.html".equals(path);
        if (HTML.matcher(path).matches() || isSpaEntry) {
            response.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
            response.setHeader("Pragma", "no-cache");
            response.setDateHeader("Expires", 0);
        }
        chain.doFilter(request, response);
    }
}
