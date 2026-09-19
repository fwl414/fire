<template>
  <el-result icon="warning" title="无权限访问" sub-title="当前角色没有访问该页面的权限。">
    <template #extra>
      <el-button type="primary" @click="$router.push('/dashboard')">返回首页</el-button>
    </template>
  </el-result>
</template>
