<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand-block">
        <div class="logo">消</div>
        <h1>消防安全综合管理平台</h1>
        <p>登录后按角色展示菜单、待办提醒、巡检档案、整改工单和报告验真。</p>
      </div>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="submit"
      >
        <el-form-item label="账号" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入系统账号"
            :disabled="loading"
            clearable
            @input="clearLoginError"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            ref="passwordRef"
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
            :disabled="loading"
            @input="clearLoginError"
          />
        </el-form-item>

        <!-- 登录失败常是账号/密码不匹配、账号被锁等，文案较长；
             固定展示在按钮上方，比一闪而过的提示条更容易看清 -->
        <div v-if="loginError" class="login-error" role="alert">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ loginError }}</span>
        </div>

        <el-button type="primary" size="large" style="width:100%" @click="submit" :loading="loading">登录系统</el-button>
      </el-form>
      <div v-if="accounts.length" class="accounts">
        <div v-for="a in accounts" :key="a.username" class="account" @click="quick(a)">
          <strong>{{ a.displayName }}</strong>
          <span>{{ a.username }} / {{ a.password }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import { demoAccounts, login } from '../auth'

const route = useRoute()
const router = useRouter()
const accounts = demoAccounts
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const formRef = ref(null)
const passwordRef = ref(null)
// 登录失败的原因（账号密码不匹配、账号被锁等），固定显示在按钮上方
const loginError = ref('')

// 只做必填校验：登录框不该比后端更严格，否则历史短密码账号会被前端直接挡住。
// 账号密码是否正确由后端判定，失败原因展示在按钮上方。
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function quick(a) {
  form.username = a.username
  form.password = a.password
  clearLoginError()
}

function clearLoginError() {
  if (loginError.value) loginError.value = ''
}

async function submit() {
  if (loading.value) return
  loginError.value = ''

  try {
    await formRef.value.validate()
  } catch (e) {
    // 校验未通过：字段下方已有提示，这里不再重复打扰
    return
  }

  loading.value = true
  try {
    const res = await login(form.username.trim(), form.password)
    if (!res.ok) {
      // 后端文案已经说明了原因和剩余尝试次数，原样展示
      loginError.value = res.message || '登录失败，请检查账号和密码'
      form.password = ''
      await nextTick()
      passwordRef.value?.focus()
      return
    }
    ElMessage.success(`登录成功：${res.user.roleName || res.user.displayName}`)
    router.replace(route.query.redirect || '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height:100vh; display:flex; align-items:center; justify-content:center; background:radial-gradient(circle at 20% 10%,#dbeafe,#f8fafc 34%,#eef2ff); padding:24px; }
.login-card { width:420px; background:#fff; border:1px solid #e2e8f0; border-radius:24px; box-shadow:0 24px 60px rgba(15,23,42,.12); padding:28px; }
.brand-block { text-align:center; margin-bottom:24px; }
.logo { width:58px; height:58px; border-radius:20px; margin:0 auto 12px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#2563eb,#60a5fa); color:white; font-size:26px; font-weight:900; }
h1 { margin:0 0 8px; font-size:24px; }
p { color:#64748b; line-height:1.7; margin:0; }
.accounts { margin-top:18px; display:grid; gap:8px; }
.account { border:1px solid #e2e8f0; border-radius:14px; padding:10px; cursor:pointer; background:#f8fafc; }
.account:hover { border-color:#2563eb; background:#eff6ff; }
.account strong { display:block; color:#0f172a; }
.account span { color:#64748b; font-size:12px; }
/* 深红字 + 浅红底，保证较长文案也能看清 */
.login-error { display:flex; align-items:flex-start; gap:8px; margin:0 0 16px; padding:10px 12px; border:1px solid #fecaca; border-radius:10px; background:#fef2f2; color:#b91c1c; font-size:13px; line-height:1.6; }
.login-error .el-icon { flex:none; margin-top:2px; font-size:15px; }
</style>
