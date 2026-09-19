import request from './core'

// 消防培训：培训计划 / 考试场次 / 培训档案
// 注：项目里的 axios 实例返回完整 response，业务数据在 .data

// 概览统计（course_count 来自学习模块的课程数据）
export function trainingStats() {
  return request.get('/api/training/stats')
}

// 培训课程只读展示：课程内容由学习模块统一维护，这里不另存一份
export function trainingCourses(category = '') {
  return request.get('/api/learning/courses', { params: { category } })
}

export function trainingPlans(params = {}) {
  return request.get('/api/training/plans', { params })
}

export function createTrainingPlan(payload) {
  return request.post('/api/training/plans', payload)
}

export function updateTrainingPlan(planId, payload) {
  return request.put(`/api/training/plans/${planId}`, payload)
}

export function deleteTrainingPlan(planId) {
  return request.delete(`/api/training/plans/${planId}`)
}

export function trainingExams(params = {}) {
  return request.get('/api/training/exams', { params })
}

export function createTrainingExam(payload) {
  return request.post('/api/training/exams', payload)
}

export function updateTrainingExam(examId, payload) {
  return request.put(`/api/training/exams/${examId}`, payload)
}

export function deleteTrainingExam(examId) {
  return request.delete(`/api/training/exams/${examId}`)
}

export function trainingRecords(params = {}) {
  return request.get('/api/training/records', { params })
}

export function createTrainingRecord(payload) {
  return request.post('/api/training/records', payload)
}

export function updateTrainingRecord(recordId, payload) {
  return request.put(`/api/training/records/${recordId}`, payload)
}

export function deleteTrainingRecord(recordId) {
  return request.delete(`/api/training/records/${recordId}`)
}

// 导出档案：按当前筛选条件取回 CSV 二进制，由调用方触发下载
export function exportTrainingRecords(params = {}) {
  return request.get('/api/training/records/export', { params, responseType: 'blob' })
}
