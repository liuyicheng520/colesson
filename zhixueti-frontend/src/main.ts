import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
// @ts-expect-error element-plus 未随 locale 产物提供类型声明
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api/request'
import { useUserStore } from './stores/user'
import { HOST_STUDENT_LOGIN } from './utils/hostAuth'
import { installButtonRipple } from './utils/ripple'
import './assets/styles/global.scss'
import './assets/styles/motion.scss'
import './assets/styles/admin.scss'

const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
// 清理旧版 Pinia token 持久化，避免与 edunexus_token 冲突
localStorage.removeItem('user')
setUnauthorizedHandler(() => {
  const userStore = useUserStore()
  userStore.logout()
  const path = window.location.pathname
  if (path.startsWith('/admin') && !path.startsWith('/admin/login')) {
    window.location.replace('/admin/login')
    return
  }
  if (!path.startsWith(HOST_STUDENT_LOGIN) && !path.startsWith('/student/login')) {
    window.location.replace(HOST_STUDENT_LOGIN)
  }
})
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')

// 按钮涟漪（鸿蒙风格）；点击烟花粒子特效已按需求停用
installButtonRipple()
