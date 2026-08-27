<template>
  <el-dialog v-model="visible" title="上传任务" width="900px" @open="load">
    <div style="margin-bottom:12px;text-align:right">
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-table :data="jobs" v-loading="loading" max-height="460" style="width:100%">
      <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column prop="job_id" label="Job ID" min-width="220" show-overflow-tooltip />
      <el-table-column prop="splitting_method" label="切分方式" width="90" align="center" />
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status || 'queued' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" show-overflow-tooltip />
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="refresh(row)">刷新</el-button>
          <el-button
            size="small" link type="success"
            :disabled="row.vectorized || !isCompleted(row.status)"
            @click="upsert(row)"
            :loading="row._upserting"
          >向量化</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { docApi } from '@/services/docApi'

const props = defineProps({ modelValue: Boolean, kbName: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'chunks-fetched'])

const visible = ref(props.modelValue)
watch(() => props.modelValue, v => { visible.value = v })
watch(visible, v => emit('update:modelValue', v))

const jobs = ref([])
const loading = ref(false)
let pollTimer = null

// 新状态：done
const isCompleted = (s) => ['done', 'success'].includes((s || '').toLowerCase())

watch(visible, (v) => {
  if (v) { load(); startPoll() }
  else stopPoll()
})

const load = async () => {
  loading.value = true
  try {
    const res = await docApi.listJobs(props.kbName || '')
    jobs.value = (res.data.data.jobs || []).map(j => ({ ...j, _upserting: false }))
  } catch (e) {
    ElMessage.error('加载任务失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

const refresh = async (job) => {
  try {
    const res = await docApi.getJob(job.job_id || job.id)
    const updated = res.data.data.job
    const idx = jobs.value.findIndex(j => j.job_id === job.job_id)
    if (idx >= 0) jobs.value[idx] = { ...jobs.value[idx], ...updated }
    ElMessage.success('已刷新')
  } catch (e) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message))
  }
}

const upsert = async (job) => {
  job._upserting = true
  try {
    await docApi.upsertJob(job.job_id || job.id)
    ElMessage.success('向量化完成')
    await load()
  } catch (e) {
    ElMessage.error('向量化失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    job._upserting = false
  }
}

const canCancel = (job) => ['queued', 'running', 'start', 'pending'].includes((job.status || '').toLowerCase())
const statusType = (s) => {
  const lower = (s || '').toLowerCase()
  if (['done', 'success'].includes(lower)) return 'success'
  if (['failed', 'error'].includes(lower)) return 'danger'
  if (['chunking', 'embedding', 'running', 'start', 'pending'].includes(lower)) return 'warning'
  return 'info'
}

const startPoll = () => {
  if (pollTimer) return
  pollTimer = setInterval(load, 5000)
}
const stopPoll = () => {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}
</script>
