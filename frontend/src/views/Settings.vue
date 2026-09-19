
<template>
  <div>
    <div class="page-title">系统设置</div>
    <el-tabs v-model="tab">
      <el-tab-pane label="智能模型配置" name="models">
        <el-card class="card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <strong>模型配置列表</strong>
              <el-button type="primary" @click="openCreate">新增配置</el-button>
            </div>
          </template>

          <el-table :data="configs" border>
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column prop="provider" label="供应商" width="110" />
            <el-table-column prop="base_url" label="服务地址" min-width="220" />
            <el-table-column prop="text_model" label="文本模型" width="150" />
            <el-table-column prop="vision_model" label="视觉模型" width="160" />
            <el-table-column label="密钥" width="130">
              <template #default="{ row }">{{ row.api_key_preview || "未配置" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="190">
              <template #default="{ row }">
                <el-tag v-if="row.is_active_text" type="success">文本启用</el-tag>
                <el-tag v-if="row.is_active_vision" type="warning" style="margin-left:4px">视觉启用</el-tag>
                <el-tag v-if="!row.enabled" type="info">禁用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="320" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="edit(row)">编辑</el-button>
                <el-button size="small" type="success" :disabled="!row.ready_text" @click="activate(row, 'text')">启用文本</el-button>
                <el-button size="small" type="warning" :disabled="!row.ready_vision" @click="activate(row, 'vision')">启用视觉</el-button>
                <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="card">
          <template #header>主流模型供应商模板</template>
          <el-table :data="providers" border>
            <el-table-column prop="name" label="供应商" width="180" />
            <el-table-column prop="base_url" label="服务地址" />
            <el-table-column label="文本模型">
              <template #default="{ row }">{{ row.text_models.join(" / ") || "-" }}</template>
            </el-table-column>
            <el-table-column label="视觉模型">
              <template #default="{ row }">{{ row.vision_models.join(" / ") || "-" }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" @click="useTemplate(row)">套用</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="连通性测试" name="test">
        <el-card>
          <template #header>模型连通性测试</template>
          <el-form label-width="120px">
            <el-form-item label="测试配置">
              <el-select v-model="test.config_id" placeholder="选择配置" style="width:360px">
                <el-option v-for="c in configs" :key="c.id" :label="`${c.name} - ${c.provider}`" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="测试模式">
              <el-radio-group v-model="test.mode">
                <el-radio-button label="text">文本模型</el-radio-button>
                <el-radio-button label="vision">视觉模型</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="测试提示词">
              <el-input v-model="test.prompt" type="textarea" rows="3" />
            </el-form-item>
            <el-form-item v-if="test.mode === 'vision'" label="测试图片">
              <el-upload :auto-upload="false" :limit="1" accept="image/*" :on-change="f => testFile = f.raw">
                <el-button>选择图片</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="testing" @click="runTest">开始测试</el-button>
            </el-form-item>
          </el-form>

          <el-alert v-if="testResult" :type="testResult?.result?.ok ? 'success' : 'error'" :title="testResult?.result?.ok ? '调用成功' : '调用失败'" show-icon />
          <pre v-if="testResult" class="result-box">{{ testResult }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="系统说明" name="info">
        <el-card>
          <h3>当前支持方式</h3>
          <p>支持主流智能模型服务。智谱清言、阿里云百炼、DeepSeek、OpenAI、Moonshot Kimi、OpenRouter 等均可通过设置页配置。</p>
          <p>视觉能力取决于供应商和模型本身是否支持 image_url 输入。DeepSeek、Kimi 当前默认作为文本模型使用。</p>
          <p>智能巡检会使用“启用视觉”的配置；消防问答和报告生成后续可切换为“启用文本”的配置。</p>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialog" title="模型配置" width="720px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="form.provider" style="width:100%">
            <el-option label="智谱清言" value="zhipu" />
            <el-option label="阿里云百炼" value="dashscope" />
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="OpenAI" value="openai" />
            <el-option label="Moonshot Kimi" value="moonshot" />
            <el-option label="OpenRouter" value="openrouter" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务地址"><el-input v-model="form.base_url" placeholder="例如 https://open.bigmodel.cn/api/paas/v4" /></el-form-item>
        <el-form-item label="访问密钥"><el-input v-model="form.api_key" type="password" show-password placeholder="请输入服务访问密钥" /></el-form-item>
        <el-form-item label="文本模型"><el-input v-model="form.text_model" placeholder="例如 glm-4-flash / qwen-plus / deepseek-chat" /></el-form-item>
        <el-form-item label="视觉模型"><el-input v-model="form.vision_model" placeholder="例如 glm-4v-flash / qwen-vl-plus / gpt-4o-mini" /></el-form-item>
        <el-form-item label="能力">
          <el-checkbox v-model="form.supports_text">支持文本</el-checkbox>
          <el-checkbox v-model="form.supports_vision">支持视觉</el-checkbox>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import request from "../api"

const tab = ref("models")
const configs = ref([])
const providers = ref([])
const dialog = ref(false)
const editingId = ref(null)
const form = ref({})
const testing = ref(false)
const testResult = ref(null)
const testFile = ref(null)
const test = ref({
  config_id: null,
  mode: "text",
  prompt: "请回复：智慧消防系统连接正常。"
})

const emptyForm = () => ({
  name: "自定义模型配置",
  provider: "custom",
  base_url: "",
  api_key: "",
  text_model: "",
  vision_model: "",
  supports_text: true,
  supports_vision: false,
  enabled: true,
  remark: ""
})

const load = async () => {
  configs.value = (await request.get("/api/settings/model-configs")).data
  providers.value = (await request.get("/api/settings/model-providers")).data
}

const openCreate = () => {
  editingId.value = null
  form.value = emptyForm()
  dialog.value = true
}

const edit = async (row) => {
  const res = await request.get(`/api/settings/model-configs/${row.id}`)
  editingId.value = row.id
  form.value = { ...res.data }
  dialog.value = true
}

const useTemplate = (row) => {
  editingId.value = null
  form.value = {
    name: row.name,
    provider: row.provider,
    base_url: row.base_url,
    api_key: "",
    text_model: row.text_models[0] || "",
    vision_model: row.vision_models[0] || "",
    supports_text: row.supports_text,
    supports_vision: row.supports_vision,
    enabled: true,
    remark: "由供应商模板创建"
  }
  dialog.value = true
}

const save = async () => {
  if (editingId.value) {
    await request.put(`/api/settings/model-configs/${editingId.value}`, form.value)
  } else {
    await request.post("/api/settings/model-configs", form.value)
  }
  ElMessage.success("保存成功")
  dialog.value = false
  await load()
}

const activate = async (row, mode) => {
  const fd = new FormData()
  fd.append("mode", mode)
  await request.post(`/api/settings/model-configs/${row.id}/activate`, fd)
  ElMessage.success(mode === "vision" ? "已启用为视觉模型" : "已启用为文本模型")
  await load()
}

const remove = async (row) => {
  await ElMessageBox.confirm("确认删除该模型配置？", "提示")
  await request.delete(`/api/settings/model-configs/${row.id}`)
  ElMessage.success("已删除")
  await load()
}

const runTest = async () => {
  if (!test.value.config_id) {
    ElMessage.warning("请选择模型配置")
    return
  }
  if (test.value.mode === "vision" && !testFile.value) {
    ElMessage.warning("视觉测试需要上传图片")
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const fd = new FormData()
    fd.append("config_id", String(test.value.config_id))
    fd.append("mode", test.value.mode)
    fd.append("prompt", test.value.prompt)
    if (test.value.mode === "vision") fd.append("file", testFile.value)
    const res = await request.post("/api/settings/model-test", fd)
    testResult.value = res.data
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.result-box {
  margin-top: 16px;
  padding: 16px;
  background: #0f172a;
  color: #e5e7eb;
  border-radius: 8px;
}
</style>
