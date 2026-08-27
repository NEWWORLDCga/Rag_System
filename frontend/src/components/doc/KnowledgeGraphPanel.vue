<template>
  <div class="kg-panel">
    <!-- 头部：返回 + 标题 -->
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <el-button :icon="ArrowLeft" circle size="small" @click="$emit('back')" />
      <span style="font-size:16px;font-weight:600">知识图谱 — {{ kbName }}</span>
      <el-tag type="warning" size="small">🔗 Knowledge Graph</el-tag>
    </div>

    <el-alert
      v-if="!graphData || graphData.total_files === 0"
      type="info" :closable="false" show-icon
      title="暂无同步到知识图谱的文件"
      description="在上传文档时开启「同步到知识图谱」选项，向量化完成后会自动生成图谱三元组"
      style="margin-bottom:16px"
    />

    <template v-else>
      <!-- 统计卡片 -->
      <div style="display:flex;gap:12px;margin-bottom:16px">
        <el-card shadow="never" style="flex:1;text-align:center">
          <div style="font-size:28px;font-weight:700;color:#7eb3ff">{{ graphData.total_files }}</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.4);margin-top:4px">已同步文件</div>
        </el-card>
        <el-card shadow="never" style="flex:1;text-align:center">
          <div style="font-size:28px;font-weight:700;color:#a78bfa">{{ graphData.total_triples }}</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.4);margin-top:4px">图谱三元组</div>
        </el-card>
      </div>

      <!-- 文件列表 -->
      <el-card shadow="never" style="margin-bottom:12px">
        <template #header>
          <span style="font-size:13px;font-weight:600">文件图谱</span>
        </template>
        <el-table :data="graphData.files" v-loading="loading" empty-text="暂无数据">
          <el-table-column prop="file_name" label="文件名" min-width="180" show-overflow-tooltip />
          <el-table-column label="图谱三元组数" width="130" align="center">
            <template #default="{ row }">
              <el-tag type="warning" size="small">{{ row.triples_count }} 条</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="viewTriples(row)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 三元组详情 Dialog -->
      <el-dialog
        v-model="triplesDialogVisible"
        :title="`📊 ${selectedFile?.file_name} — 图谱三元组`"
        width="800px"
        destroy-on-close
      >
        <el-alert
          v-if="!selectedFileTriples.length"
          type="info" :closable="false"
          title="该文件暂无图谱三元组"
          style="margin-bottom:12px"
        />
        <div v-else style="max-height:500px;overflow-y:auto">
          <el-table :data="selectedFileTriples" stripe style="width:100%">
            <el-table-column label="头节点（Chunk）" min-width="200">
              <template #default="{ row }">
                <div style="font-size:12px;color:#94a3b8;margin-bottom:2px">
                  ID: {{ row.head_chunk_id?.slice(0, 8) }}...
                </div>
                <div style="font-size:13px;line-height:1.5">{{ row.head_content }}</div>
              </template>
            </el-table-column>
            <el-table-column label="关系" width="120" align="center">
              <template #default="{ row }">
                <el-tag type="primary" size="small">{{ row.relation }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="尾节点（Chunk）" min-width="200">
              <template #default="{ row }">
                <div style="font-size:12px;color:#94a3b8;margin-bottom:2px">
                  ID: {{ row.tail_chunk_id?.slice(0, 8) }}...
                </div>
                <div style="font-size:13px;line-height:1.5">{{ row.tail_content }}</div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <template #footer>
          <el-button @click="triplesDialogVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  kbName: { type: String, required: true }
})
const emit = defineEmits(['back'])

const loading = ref(false)
const graphData = ref(null)
const triplesDialogVisible = ref(false)
const selectedFile = ref(null)
const selectedFileTriples = ref([])

const loadGraph = async () => {
  loading.value = true
  try {
    const { data } = await axios.get(`http://localhost:8000/api/v1/knowledge-graph/kb/${props.kbName}`)
    if (data.success) {
      graphData.value = data.data
    }
  } catch (e) {
    ElMessage.error('加载图谱失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

const viewTriples = (file) => {
  selectedFile.value = file
  selectedFileTriples.value = file.triples || []
  triplesDialogVisible.value = true
}

onMounted(loadGraph)
</script>

<style scoped>
.kg-panel { padding: 0; }
</style>
