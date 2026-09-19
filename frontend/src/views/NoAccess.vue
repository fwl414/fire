<template>
  <div class="no-access">
    <el-result icon="warning" title="无权限访问" sub-title="当前账号没有访问该模块的权限，请切换管理员账号或返回首页。">
      <template #extra>
        <el-button type="primary" @click="$router.push('/dashboard')">返回首页</el-button>
        <el-button @click="$router.push('/login')">切换账号</el-button>
      </template>
    </el-result>
  </div>
</template>
<style scoped>.no-access { min-height:100vh; display:flex; align-items:center; justify-content:center; background:#f8fafc; }</style>
