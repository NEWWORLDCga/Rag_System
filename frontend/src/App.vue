<template>
  <div id="app">
    <!-- Aurora background blobs -->
    <div class="aurora-bg" aria-hidden="true">
      <div class="blob blob-1" />
      <div class="blob blob-2" />
      <div class="blob blob-3" />
      <div class="noise" />
    </div>

    <div class="app-layout">
      <!-- Icon sidebar -->
      <aside class="sidebar">
        <div class="sidebar-logo">
          <div class="logo-mark">
            <el-icon><cpu /></el-icon>
          </div>
        </div>

        <nav class="nav-list">
          <el-tooltip v-for="item in navItems" :key="item.key"
            :content="item.label" placement="right" effect="dark">
            <button
              class="nav-item"
              :class="{ active: activeMenu === item.key || (item.match && activeMenu.startsWith(item.match)) }"
              @click="handleMenuSelect(item.key)"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span v-if="activeMenu === item.key || (item.match && activeMenu.startsWith(item.match))" class="nav-active-dot" />
            </button>
          </el-tooltip>
        </nav>

        <div class="sidebar-bottom">
          <el-tooltip content="系统管理" placement="right" effect="dark">
            <button class="nav-item" :class="{ active: activeMenu.startsWith('admin') }"
              @click="handleMenuSelect('admin-collections')">
              <el-icon><setting /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </aside>

      <!-- Main -->
      <div class="main-wrap">
        <!-- Topbar -->
        <header class="topbar">
          <div class="topbar-left">
            <span class="page-title">{{ pageTitle }}</span>
            <span v-if="pageSubtitle" class="page-subtitle">{{ pageSubtitle }}</span>
          </div>
          <div class="topbar-right">
            <div class="model-select-wrap">
              <el-icon class="model-icon"><cpu /></el-icon>
              <el-select v-model="selectedModel" size="small" style="width:160px" placeholder="模型">
                <el-option v-for="m in availableModels" :key="m.name" :label="m.name" :value="m.name" />
              </el-select>
            </div>
            <div class="status-pill" :class="apiStatus ? 'online' : 'offline'">
              <span class="pulse-dot" />
              {{ apiStatus ? 'Connected' : 'Offline' }}
            </div>
          </div>
        </header>

        <!-- Content -->
        <main class="content">
          <div v-show="activeMenu === 'dashboard'"><DashboardView @navigate="handleMenuSelect" /></div>
          <div v-show="activeMenu === 'chat'"><SimpleChat :model="selectedModel" /></div>
          <div v-show="activeMenu === 'kb-categories'"><CategoryManager /></div>
          <div v-show="activeMenu.startsWith('admin')"><AdminPanel :active-tab="adminTab" /></div>
          <div v-show="activeMenu === 'devtools'"><DevTools /></div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiService } from './services/api'
import SimpleChat from './components/SimpleChat.vue'
import CategoryManager from './components/doc/CategoryManager.vue'
import AdminPanel from './components/AdminPanel.vue'
import DevTools from './components/DevTools.vue'
import DashboardView from './views/DashboardView.vue'

const activeMenu = ref('dashboard')
const selectedModel = ref('qwen-turbo')
const availableModels = ref([])
const apiStatus = ref(false)

const navItems = [
  { key: 'dashboard', label: 'Dashboard', icon: 'HomeFilled' },
  { key: 'chat', label: '智能对话', icon: 'ChatDotRound' },
  { key: 'kb-categories', label: '类目管理', icon: 'FolderOpened' },
  { key: 'admin-collections', label: '知识库', icon: 'DataAnalysis', match: 'admin' },
  { key: 'devtools', label: '开发工具', icon: 'Monitor' },
]

const adminTabMap = { 'admin-collections': 'collections', 'admin-create': 'create', 'admin-config': 'config' }
const adminTab = computed(() => adminTabMap[activeMenu.value] || 'namespace')

const pageMeta = {
  dashboard:          { title: 'Dashboard', sub: 'Enterprise Knowledge Base' },
  chat:               { title: '智能对话', sub: 'AI-powered conversation' },
  'kb-categories':    { title: '类目管理', sub: 'Document categories' },
  'admin-collections':{ title: '知识库列表', sub: 'Vector collections' },
  'admin-create':     { title: '创建知识库', sub: 'New collection' },
  'admin-config':     { title: '配置信息', sub: 'System configuration' },
  devtools:           { title: '开发工具', sub: 'API & debugging' },
}
const pageTitle    = computed(() => pageMeta[activeMenu.value]?.title || '')
const pageSubtitle = computed(() => pageMeta[activeMenu.value]?.sub || '')

const handleMenuSelect = (key) => { activeMenu.value = key }

onMounted(async () => {
  try {
    const res = await apiService.getModels()
    availableModels.value = res.models
    selectedModel.value = res.default_model
    apiStatus.value = true
  } catch {
    availableModels.value = [
      { name: 'qwen-turbo' }, { name: 'qwen-plus' }, { name: 'qwen-max' }
    ]
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d1117; }
</style>

<style scoped>
/* ── Aurora background ── */
.aurora-bg {
  position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none;
}
.blob {
  position: absolute; border-radius: 50%;
  filter: blur(90px); opacity: 0.28;
  animation: drift 20s ease-in-out infinite alternate;
}
.blob-1 {
  width: 650px; height: 650px; top: -220px; left: -120px;
  background: radial-gradient(circle, #4f8ef7 0%, #7c3aed 50%, transparent 100%);
  animation-duration: 22s;
}
.blob-2 {
  width: 550px; height: 550px; bottom: -180px; right: -120px;
  background: radial-gradient(circle, #06b6d4 0%, #34d399 50%, transparent 100%);
  animation-duration: 18s; animation-delay: -8s;
}
.blob-3 {
  width: 480px; height: 480px; top: 35%; left: 45%;
  background: radial-gradient(circle, #a78bfa 0%, #f472b6 50%, transparent 100%);
  animation-duration: 25s; animation-delay: -14s; opacity: 0.22;
}
.noise {
  position: absolute; inset: 0; opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  background-size: 200px 200px;
}
@keyframes drift {
  0%   { transform: translate(0, 0) scale(1); }
  33%  { transform: translate(40px, -30px) scale(1.05); }
  66%  { transform: translate(-20px, 40px) scale(0.97); }
  100% { transform: translate(30px, 20px) scale(1.03); }
}

/* ── Layout ── */
#app { height: 100vh; overflow: hidden; }
.app-layout {
  position: relative; z-index: 1;
  display: flex; height: 100vh; overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 60px; flex-shrink: 0;
  display: flex; flex-direction: column; align-items: center;
  background: rgba(13,17,23,0.75);
  backdrop-filter: blur(28px);
  border-right: 1px solid rgba(255,255,255,0.08);
  padding: 0;
}
.sidebar-logo {
  height: 60px; display: flex; align-items: center; justify-content: center;
  width: 100%; border-bottom: 1px solid rgba(255,255,255,0.05);
}
.logo-mark {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, #3b6fd4, #5b4fcf);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; color: #fff;
  box-shadow: 0 4px 14px rgba(59,111,212,0.5);
}
.nav-list {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; padding: 12px 0; gap: 4px; width: 100%;
}
.nav-item {
  position: relative;
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: rgba(255,255,255,0.3); font-size: 17px;
  background: transparent; border: none; outline: none;
  transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
}
.nav-item:hover { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.7); }
.nav-item.active {
  background: rgba(79,142,247,0.15);
  color: #7eb3ff;
  box-shadow: 0 0 0 1px rgba(79,142,247,0.3);
}
.nav-active-dot {
  position: absolute; right: -1px; top: 50%; transform: translateY(-50%);
  width: 3px; height: 16px; border-radius: 99px;
  background: linear-gradient(180deg, #7eb3ff, #a78bfa);
  box-shadow: 0 0 8px rgba(79,142,247,0.8);
}
.sidebar-bottom {
  padding: 12px 0; border-top: 1px solid rgba(255,255,255,0.05);
  width: 100%; display: flex; justify-content: center;
}

/* ── Main wrap ── */
.main-wrap {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}

/* ── Topbar ── */
.topbar {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 28px;
  background: rgba(13,17,23,0.65);
  backdrop-filter: blur(28px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.topbar-left { display: flex; align-items: baseline; gap: 10px; }
.page-title { font-size: 15px; font-weight: 700; color: #f0f4ff; letter-spacing: -0.2px; }
.page-subtitle { font-size: 12px; color: rgba(255,255,255,0.25); }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.model-select-wrap { display: flex; align-items: center; gap: 6px; }
.model-icon { color: rgba(255,255,255,0.3); font-size: 14px; }

.status-pill {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 99px;
  font-size: 11px; font-weight: 500; letter-spacing: 0.3px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.4);
}
.status-pill.online { color: #2dd4a0; border-color: rgba(45,212,160,0.25); background: rgba(45,212,160,0.06); }
.pulse-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: rgba(255,255,255,0.3);
}
.status-pill.online .pulse-dot {
  background: #2dd4a0;
  box-shadow: 0 0 0 0 rgba(45,212,160,0.4);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 rgba(45,212,160,0.4); }
  70%  { box-shadow: 0 0 0 6px rgba(45,212,160,0); }
  100% { box-shadow: 0 0 0 0 rgba(45,212,160,0); }
}

/* ── Content ── */
.content {
  flex: 1; overflow-y: auto; padding: 28px 32px;
}
.content::-webkit-scrollbar { width: 4px; }
.content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 99px; }
</style>
