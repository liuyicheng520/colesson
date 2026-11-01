<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type AdminMenuConfigItem } from '@/api/admin'
import { hasPerm } from '@/utils/permission'
import { usePermissionStore } from '@/stores/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const permissionStore = usePermissionStore()
const loading = ref(false)
const menus = ref<AdminMenuConfigItem[]>([])

const dialogVisible = ref(false)
const editing = reactive({ perm_code: '', title: '', sort: 0 })

async function loadMenus() {
  loading.value = true
  try {
    menus.value = await adminApi.listMenus()
  } finally {
    loading.value = false
  }
}

function openEdit(row: AdminMenuConfigItem) {
  editing.perm_code = row.perm_code
  editing.title = row.title
  editing.sort = row.sort
  dialogVisible.value = true
}

async function submitEdit() {
  if (!editing.title.trim()) {
    ElMessage.warning('菜单名称不能为空')
    return
  }
  await ElMessageBox.confirm(
    `确定将「${editing.perm_code}」更新为「${editing.title}」、排序 ${editing.sort} 吗？`,
    '二次确认',
    { type: 'warning' },
  )
  await adminApi.updateMenu(editing.perm_code, {
    title: editing.title.trim(),
    sort: editing.sort,
  })
  ElMessage.success('菜单已更新')
  dialogVisible.value = false
  await loadMenus()
  await permissionStore.loadAdminContext(true)
}

onMounted(loadMenus)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="menus" />
    <div class="card table-wrap">
      <div class="toolbar">
        <div>
          <h3>菜单配置</h3>
          <p class="hint">可调整侧边栏菜单显示名称与排序；路由路径与图标由系统内置，修改后刷新菜单立即生效。</p>
        </div>
      </div>

      <el-table v-loading="loading" :data="menus" stripe>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column prop="title" label="菜单名称" min-width="140" />
        <el-table-column prop="path" label="路由路径" min-width="180" />
        <el-table-column prop="perm_code" label="权限码" min-width="160" />
        <el-table-column prop="icon" label="图标" width="100" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="hasPerm('btn:menu:edit')"
              text
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="编辑菜单" width="440px">
      <el-form label-width="90px">
        <el-form-item label="权限码">
          <el-input :model-value="editing.perm_code" disabled />
        </el-form-item>
        <el-form-item label="菜单名称" required>
          <el-input v-model="editing.title" maxlength="32" show-word-limit />
        </el-form-item>
        <el-form-item label="排序" required>
          <el-input-number v-model="editing.sort" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; }
.toolbar {
  margin-bottom: 20px;
  h3 { margin-bottom: 6px; }
  .hint { color: $text-secondary; font-size: 13px; margin: 0; }
}
</style>
