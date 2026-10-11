package com.contest;

import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

/**
 * 登录相关静态脚本禁止浏览器强缓存，避免外置浏览器仍用旧 JS 导致无法跳转学生主页。
 */
@Component
@Order(5)
public class NoCacheAuthAssetsFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (path != null) {
            String clean = path.contains("?") ? path.substring(0, path.indexOf('?')) : path;
            if ("/app.js".equals(clean) || "/auth-pages.js".equals(clean)
                    || clean.endsWith("/student/login.html")
                    || clean.endsWith("/student/register.html")) {
                response.setHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
                response.setHeader("Pragma", "no-cache");
                response.setDateHeader("Expires", 0);
            }
        }
        filterChain.doFilter(request, response);
    }
}
