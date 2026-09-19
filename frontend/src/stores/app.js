import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const theme = ref('light')
  const locale = ref('zh-CN')
  const loading = ref(false)
  const notificationCount = ref(0)

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setLoading = (val) => {
    loading.value = val
  }

  const setNotificationCount = (count) => {
    notificationCount.value = count
  }

  const incrementNotification = () => {
    notificationCount.value++
  }

  const clearNotifications = () => {
    notificationCount.value = 0
  }

  return {
    sidebarCollapsed,
    theme,
    locale,
    loading,
    notificationCount,
    toggleSidebar,
    setLoading,
    setNotificationCount,
    incrementNotification,
    clearNotifications
  }
})