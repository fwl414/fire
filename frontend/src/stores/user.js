import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(sessionStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(sessionStorage.getItem('userInfo') || 'null'))
  const permissions = ref([])
  const roles = ref([])

  const isLoggedIn = computed(() => {
    return token.value && token.value.length > 0
  })

  const hasPermission = computed(() => (perm) => {
    if (!perm) return true
    if (roles.value.includes('admin')) return true
    return permissions.value.includes(perm)
  })

  const hasRole = computed(() => (role) => {
    return roles.value.includes(role)
  })

  function setToken(newToken) {
    token.value = newToken
    sessionStorage.setItem('token', newToken)
  }

  function setUserInfo(info) {
    userInfo.value = info
    if (info) {
      sessionStorage.setItem('userInfo', JSON.stringify(info))
      permissions.value = info.permissions || []
      roles.value = info.roles || []
    } else {
      sessionStorage.removeItem('userInfo')
      permissions.value = []
      roles.value = []
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    permissions.value = []
    roles.value = []
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('userInfo')
  }

  return {
    token,
    userInfo,
    permissions,
    roles,
    isLoggedIn,
    hasPermission,
    hasRole,
    setToken,
    setUserInfo,
    logout
  }
})