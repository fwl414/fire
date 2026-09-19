import request from './core'

// 业务实体图谱：数据来自业务表现算（建筑/楼层/设备/告警/工单/巡检/隐患类型/知识条目）
export function kgOverview() {
  return request.get('/api/kg/overview')
}

export function kgGraph(params) {
  return request.get('/api/kg/graph', { params })
}

export function kgSubgraph(params) {
  return request.get('/api/kg/subgraph', { params })
}

export function kgSearch(params) {
  return request.get('/api/kg/search', { params })
}

// 学习知识图谱：数据来自题库与课程 JSON（已有接口）
export function learningKnowledgeGraph(params) {
  return request.get('/api/learning/knowledge-graph', { params })
}
