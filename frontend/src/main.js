// Element Plus 基础样式必须显式引入，放在所有 import 之前：
// 1) 按需注入只覆盖"模板里用到的组件"，而 ElMessage / ElMessageBox / ElNotification /
//    ElLoading 是在 JS 里程序化调用的，拿不到样式——缺了这份 CSS 它们会渲染成没有定位、
//    没有背景、白字看不清的裸容器（弹窗会贴在左上角）。
// 2) 放最前是为了让项目自己的全局样式在层叠中位于其后，能正常覆盖基础样式。
import 'element-plus/dist/index.css'

// 项目全局样式。
// 两者都是早期遗留的公共样式表，且有多处同名类互相冲突（.page-title/.card/.report-box/
// .stat-value 等），靠引入顺序决定谁生效：
//   - style.css 在前：它独有的 .sidebar/.app-shell/.menu/.grid-4/.grid-2 已无任何引用
//   - styles.css 在后：它定义的 .stat-grid/.stat-card/.page-subtitle 等被 37 个页面引用，
//     是实际在用的那一份，因此让它覆盖前者
import './style.css'
import './styles.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia).use(router).mount('#app')
