package com.contest;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.MultipartConfigFactory;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.util.unit.DataSize;

import javax.servlet.MultipartConfigElement;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.util.HashMap;
import java.util.Map;

/**
 * 智课共生启动类
 */
@SpringBootApplication
public class AiTeacherApplication {
    private static final int DEFAULT_PORT = 8082;
    private static final int[] FALLBACK_PORTS = {18082, 8083, 8084, 18083};

    public static void main(String[] args) {
        SpringApplication application = new SpringApplication(AiTeacherApplication.class);
        String selectedPort = choosePort(args);
        if (selectedPort != null) {
            Map<String, Object> defaultProperties = new HashMap<>();
            defaultProperties.put("server.port", selectedPort);
            application.setDefaultProperties(defaultProperties);
            System.setProperty("server.port", selectedPort);
        }

        ConfigurableApplicationContext context = application.run(args);
        String port = context.getEnvironment().getProperty("local.server.port",
                context.getEnvironment().getProperty("server.port", "8082"));
        System.out.println("====================================");
        System.out.println("✅ 智课共生启动成功");
        System.out.println("🌐 登录地址：http://localhost:" + port + "/login.html");
        System.out.println("🌐 工作台：http://localhost:" + port + "/workspace.html");
        System.out.println("====================================");
    }

    private static String choosePort(String[] args) {
        if (hasExplicitPort(args)) {
            return null;
        }
        if (isPortAvailable(DEFAULT_PORT)) {
            return null;
        }
        for (int port : FALLBACK_PORTS) {
            if (isPortAvailable(port)) {
                System.out.println("⚠️ 端口 " + DEFAULT_PORT + " 已被占用，自动切换到 " + port);
                return String.valueOf(port);
            }
        }
        return String.valueOf(DEFAULT_PORT);
    }

    private static boolean hasExplicitPort(String[] args) {
        if (System.getProperty("server.port") != null) {
            return true;
        }
        if (System.getenv("SERVER_PORT") != null && !System.getenv("SERVER_PORT").trim().isEmpty()) {
            return true;
        }
        if (args == null) {
            return false;
        }
        for (String arg : args) {
            if (arg != null && (arg.startsWith("--server.port=") || arg.startsWith("--server.port "))) {
                return true;
            }
        }
        return false;
    }

    private static boolean isPortAvailable(int port) {
        try (ServerSocket socket = new ServerSocket()) {
            socket.setReuseAddress(false);
            socket.bind(new InetSocketAddress(port));
            return true;
        } catch (IOException ex) {
            return false;
        }
    }

    // 文件上传大小配置
    @Bean
    public MultipartConfigElement multipartConfigElement() {
        MultipartConfigFactory factory = new MultipartConfigFactory();
        factory.setMaxFileSize(DataSize.ofMegabytes(100));
        factory.setMaxRequestSize(DataSize.ofMegabytes(100));
        return factory.createMultipartConfig();
    }
}
