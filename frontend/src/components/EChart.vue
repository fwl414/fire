<template>
  <div ref="chartRef" :style="{ width: width, height: height }" class="echart-container"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: {
    type: Object,
    required: true
  },
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '300px'
  },
  autoResize: {
    type: Boolean,
    default: true
  }
})

// 把 ECharts 的点击事件透出去（图谱点击节点下钻要用），其余用法不受影响
const emit = defineEmits(['click'])

const chartRef = ref(null)
let chartInstance = null

const initChart = () => {
  if (!chartRef.value) return
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(props.option)
  chartInstance.on('click', params => emit('click', params))
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  nextTick(() => {
    initChart()
    if (props.autoResize) {
      window.addEventListener('resize', handleResize)
    }
  })
})

onUnmounted(() => {
  if (props.autoResize) {
    window.removeEventListener('resize', handleResize)
  }
  chartInstance?.dispose()
})

watch(() => props.option, () => {
  nextTick(() => {
    if (chartInstance) {
      chartInstance.setOption(props.option, true)
    } else {
      initChart()
    }
  })
}, { deep: true })
</script>

<style scoped>
.echart-container {
  min-height: 200px;
}
</style>