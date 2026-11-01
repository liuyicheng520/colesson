<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'
import type { AgentDefinition } from '@/types'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const agents = ref<AgentDefinition[]>([])
const loading = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const editForm = ref<Partial<AgentDefinition & { prompt_template: string }>>({})

async function load() {
  loading.value = true
  try {
    agents.value = await agentApi.listDefinitions()
  } finally {
    loading.value = false
  }
}

function openEdit(row: AgentDefinition) {
  editForm.value = { ...row, prompt_template: '' }
  editVisible.value = true
}

async function saveEdit() {
  const code = editForm.value.agent_code
  if (!code || saving.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      agent_name: (editForm.value.agent_name || '').trim(),
      default_model: editForm.value.default_model,
      status: editForm.value.status ?? 1,
    }
    if (!payload.agent_name) {
      ElMessage.warning('请填写 Agent 名称')
      return
    }
    const desc = (editForm.value.description || '').trim()
    if (desc) payload.description = desc
    const tpl = (editForm.value.prompt_template || '').trim()
    if (tpl) payload.prompt_template = tpl
    const updated = await agentApi.updateDefinition(code, payload)
    const idx = agents.value.findIndex((a) => a.agent_code === code)
    if (idx >= 0) agents.value[idx] = updated
    ElMessage.success('配置已保存')
    editVisible.value = false
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="agents" />
    <div class="card table-wrap">
      <h3>智能体配置</h3>
      <el-table v-loading="loading" :data="agents" stripe style="margin-top:16px">
        <el-table-column prop="agent_code" label="编码" width="140" />
        <el-table-column prop="agent_name" label="名称" width="160" />
        <el-table-column prop="agent_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.agent_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="default_model" label="默认模型" width="160" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 1" disabled />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">配置</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="editVisible" title="智能体配置" width="600px">
      <el-form label-width="100px">
        <el-form-item label="Agent编码">
          <el-input :model-value="editForm.agent_code" disabled />
        </el-form-item>
        <el-form-item label="Agent名称"><el-input v-model="editForm.agent_name" maxlength="128" /></el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="默认模型">
          <el-select v-model="editForm.default_model" style="width:100%">
            <el-option label="spark-pro" value="spark-pro" />
            <el-option label="spark-ultra" value="spark-ultra" />
            <el-option label="deepseek-coder" value="deepseek-coder" />
            <el-option label="qwen-plus" value="qwen-plus" />
            <el-option label="mock-v1" value="mock-v1" />
          </el-select>
        </el-form-item>
        <el-form-item label="Prompt模板">
          <el-input v-model="editForm.prompt_template" type="textarea" :rows="6" placeholder="留空则不修改现有模板" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="editForm.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; }
</style>
