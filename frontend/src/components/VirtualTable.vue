<template>
  <div class="virtual-table-container">
    <el-table
      :data="displayData"
      :height="tableHeight"
      v-loading="loading"
      border
      stripe
      :scroll="{ x: scrollX }"
      :row-key="rowKey"
    >
      <slot></slot>
    </el-table>
    <div v-if="total > pageSize && !loading" class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  total: {
    type: Number,
    default: 0
  },
  loading: {
    type: Boolean,
    default: false
  },
  tableHeight: {
    type: Number,
    default: 500
  },
  pageSize: {
    type: Number,
    default: 50
  },
  scrollX: {
    type: String,
    default: ''
  },
  rowKey: {
    type: String,
    default: 'id'
  }
})

const emit = defineEmits(['update:pageSize', 'page-change'])

const currentPage = ref(1)

const displayData = computed(() => {
  const source = Array.isArray(props.data) ? props.data : []
  const start = (currentPage.value - 1) * props.pageSize
  const end = start + props.pageSize
  return source.slice(start, end)
})

const handleSizeChange = (val) => {
  emit('update:pageSize', val)
  currentPage.value = 1
  emit('page-change', { page: 1, pageSize: val })
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  emit('page-change', { page: val, pageSize: props.pageSize })
}

watch(() => props.total, (newTotal) => {
  const maxPage = Math.ceil(newTotal / props.pageSize)
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage || 1
  }
})
</script>

<style scoped>
.virtual-table-container {
  position: relative;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0;
}
</style>