<template>
  <div class="dashboard">

    <!-- Hero search -->
    <div class="hero">
      <div class="hero-eyebrow">Enterprise Knowledge Base</div>
      <h1 class="hero-title">
        Ask anything about your
        <span class="gradient-text">knowledge base</span>
      </h1>
      <div class="search-bar" :class="{ focused: searchFocused }">
        <el-icon class="search-icon"><search /></el-icon>
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="Ask a question or search documents..."
          @focus="searchFocused = true"
          @blur="searchFocused = false"
          @keydown.enter="handleSearch"
        />
        <button class="search-submit" @click="handleSearch" :disabled="searching">
          <span v-if="!searching">Ask AI</span>
          <span v-else class="searching-dots"><span/><span/><span/></span>
        </button>
      </div>
      <transition name="slide-up">
        <div v-if="aiAnswer" class="ai-result">
          <div class="ai-result-header">
            <div class="ai-badge"><el-icon><cpu /></el-icon> AI Answer</div>
            <button class="close-btn" @click="aiAnswer = ''">×</button>
          </div>
          <div class="ai-result-body" v-html="aiAnswer" />
        </div>
      </transition>
    </div>

    <!-- Bento Grid -->
    <div class="bento">

      <!-- Stats row -->
      <div class="bento-stats">
        <div class="stat-card" v-for="s in stats" :key="s.label">
          <div class="stat-icon-wrap" :style="{ '--c': s.color }">
            <el-icon><component :is="s.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
          <div class="stat-glow" :style="{ background: s.color }" />
        </div>
      </div>

      <!-- Main row -->
      <div class="bento-main">

        <!-- Collections card (wide) -->
        <div class="bento-card collections-card">
          <div class="bento-card-header">
            <span class="bento-card-title">Knowledge Bases</span>
            <button class="link-btn" @click="$emit('navigate', 'admin-collections')">
              View all <el-icon><arrow-right /></el-icon>
            </button>
          </div>
          <div class="collections-list">
            <div v-for="col in collections.slice(0, 5)" :key="col.collection_name"
              class="col-row" @click="$emit('navigate', 'admin-collections')">
              <div class="col-icon">
                <el-icon><data-analysis /></el-icon>
              </div>
              <div class="col-info">
                <div class="col-name">{{ col.collection_name }}</div>
                <div class="col-meta">{{ col.embedding_model || 'text-embedding-v3' }}</div>
              </div>
              <div class="col-tags">
                <span v-if="col.image_mode" class="mini-tag purple">图文</span>
                <span class="mini-tag blue">{{ col.metrics || 'cosine' }}</span>
              </div>
            </div>
            <div v-if="collections.length === 0" class="empty-state">
              <el-icon style="font-size:28px;opacity:0.2"><data-analysis /></el-icon>
              <span>No knowledge bases yet</span>
            </div>
          </div>
        </div>

        <!-- Right column -->
        <div class="bento-right">

          <!-- Quick actions -->
          <div class="bento-card actions-card">
            <div class="bento-card-header">
              <span class="bento-card-title">Quick Actions</span>
            </div>
            <div class="actions-grid">
              <button v-for="a in actions" :key="a.label"
                class="action-btn" :style="{ '--ac': a.color }"
                @click="$emit('navigate', a.route)">
                <div class="action-icon"><el-icon><component :is="a.icon" /></el-icon></div>
                <span>{{ a.label }}</span>
              </button>
            </div>
          </div>

          <!-- System status -->
          <div class="bento-card status-card">
            <div class="bento-card-header">
              <span class="bento-card-title">System</span>
              <div class="live-badge">
                <span class="live-dot" />LIVE
              </div>
            </div>
            <div class="status-rows">
              <div class="status-row" v-for="s in statusItems" :key="s.label">
                <span class="status-name">{{ s.label }}</span>
                <div class="status-indicator" :class="s.ok ? 'ok' : 'err'">
                  <span class="status-dot-sm" />
                  {{ s.ok ? 'Operational' : 'Degraded' }}
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, Cpu, DataAnalysis, FolderOpened, ChatDotRound, Setting, ArrowRight } from '@element-plus/icons-vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const emit = defineEmits(['navigate'])
const md = new MarkdownIt({ breaks: true, linkify: true })
const API = 'http://localhost:8000/api/v1'

const searchQuery = ref('')
const searchFocused = ref(false)
const searching = ref(false)
const aiAnswer = ref('')
const collections = ref([])

const stats = ref([
  { label: 'Knowledge Bases', value: '—', icon: 'DataAnalysis', color: 'rgba(79,142,247,0.6)' },
  { label: 'Categories',      value: '—', icon: 'FolderOpened',  color: 'rgba(45,212,160,0.6)' },
  { label: 'API Status',      value: '—', icon: 'Connection',    color: 'rgba(167,139,250,0.6)' },
  { label: 'Model',           value: '—', icon: 'Cpu',           color: 'rgba(245,200,66,0.6)' },
])

const actions = [
  { label: '智能对话',   route: 'chat',               icon: 'ChatDotRound', color: '#4f8ef7' },
  { label: '类目管理',   route: 'kb-categories',      icon: 'FolderOpened', color: '#2dd4a0' },
  { label: '知识库列表', route: 'admin-collections',  icon: 'DataAnalysis', color: '#a78bfa' },
  { label: '创建知识库', route: 'admin-create',        icon: 'Setting',      color: '#f5c842' },
]

const statusItems = ref([
  { label: 'API Service',  ok: false },
  { label: 'Backend',      ok: false },
  { label: 'API Key',      ok: false },
])

const handleSearch = async () => {
  if (!searchQuery.value.trim() || searching.value) return
  searching.value = true
  aiAnswer.value = ''
  try {
    const res = await axios.post(`${API}/knowledge/`, { query: searchQuery.value, session_id: 'dashboard' })
    aiAnswer.value = md.render(res.data?.answer || '未找到相关内容')
  } catch {
    aiAnswer.value = md.render('暂时无法连接知识库，请稍后重试。')
  } finally {
    searching.value = false
  }
}

onMounted(async () => {
  try {
    const [colRes, healthRes] = await Promise.allSettled([
      axios.get(`${API}/admin/collections`),
      axios.get(`${API}/health`),
    ])
    if (colRes.status === 'fulfilled') {
      collections.value = colRes.value.data?.data?.collections || []
      stats.value[0].value = collections.value.length
      statusItems.value[0].ok = true
    }
    if (healthRes.status === 'fulfilled') {
      const h = healthRes.value.data
      statusItems.value[1].ok = h?.status === 'healthy'
      statusItems.value[2].ok = h?.api_key_configured ?? false
      stats.value[2].value = h?.status === 'healthy' ? 'Online' : 'Offline'
      stats.value[3].value = h?.default_model || '—'
    }
    try {
      const catRes = await axios.get(`${API}/categories`)
      stats.value[1].value = catRes.data?.data?.total ?? '—'
    } catch {}
  } catch {}
})
</script>

<style scoped>
.dashboard { max-width: 1200px; }

/* ── Hero ── */
.hero { margin-bottom: 40px; }
.hero-eyebrow {
  font-size: 11px; font-weight: 600; letter-spacing: 2px;
  text-transform: uppercase; color: rgba(79,142,247,0.8);
  margin-bottom: 12px;
}
.hero-title {
  font-size: 36px; font-weight: 800; line-height: 1.15;
  color: #f0f4ff; margin-bottom: 24px;
  letter-spacing: -0.8px;
}
.gradient-text {
  background: linear-gradient(135deg, #7eb3ff 0%, #a78bfa 50%, #34d399 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}

/* ── Search bar ── */
.search-bar {
  display: flex; align-items: center; gap: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px; padding: 10px 14px;
  backdrop-filter: blur(20px);
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
  max-width: 680px;
}
.search-bar.focused {
  border-color: rgba(79,142,247,0.5);
  box-shadow: 0 0 0 4px rgba(79,142,247,0.12), 0 8px 32px rgba(0,0,0,0.3);
  background: rgba(255,255,255,0.06);
}
.search-icon { font-size: 18px; color: rgba(255,255,255,0.3); flex-shrink: 0; }
.search-input {
  flex: 1; background: transparent; border: none; outline: none;
  color: #f0f4ff; font-size: 15px; caret-color: #7eb3ff;
}
.search-input::placeholder { color: rgba(255,255,255,0.2); }
.search-submit {
  background: linear-gradient(135deg, #3b6fd4, #5b4fcf);
  border: none; border-radius: 10px; padding: 7px 18px;
  color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
  flex-shrink: 0; transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(59,111,212,0.4);
}
.search-submit:hover { box-shadow: 0 4px 20px rgba(59,111,212,0.6); transform: translateY(-1px); }
.search-submit:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.searching-dots { display: flex; gap: 3px; align-items: center; }
.searching-dots span {
  width: 4px; height: 4px; border-radius: 50%; background: #fff;
  animation: dot-bounce 1.2s infinite;
}
.searching-dots span:nth-child(2) { animation-delay: 0.2s; }
.searching-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }

/* ── AI Result ── */
.ai-result {
  margin-top: 14px; max-width: 680px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(79,142,247,0.2);
  border-radius: 14px; padding: 16px 20px;
  backdrop-filter: blur(20px);
}
.ai-result-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.ai-badge {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: #7eb3ff;
  text-transform: uppercase; letter-spacing: 0.8px;
}
.close-btn {
  background: none; border: none; color: rgba(255,255,255,0.3);
  font-size: 18px; cursor: pointer; line-height: 1; padding: 0;
  transition: color 0.2s;
}
.close-btn:hover { color: rgba(255,255,255,0.7); }
.ai-result-body { font-size: 14px; line-height: 1.7; color: #94a3b8; }
.ai-result-body :deep(p) { margin: 4px 0; }
.ai-result-body :deep(code) { background: rgba(255,255,255,0.08); border-radius: 4px; padding: 1px 5px; font-size: 13px; color: #7eb3ff; }

/* ── Bento ── */
.bento { display: flex; flex-direction: column; gap: 14px; }

/* Stats row */
.bento-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.stat-card {
  position: relative; overflow: hidden;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px; padding: 18px 20px;
  display: flex; align-items: center; gap: 14px;
  backdrop-filter: blur(20px);
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
  cursor: default;
}
.stat-card:hover {
  border-color: rgba(255,255,255,0.12);
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0,0,0,0.4);
}
.stat-icon-wrap {
  width: 42px; height: 42px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: #fff;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
}
.stat-value { font-size: 24px; font-weight: 800; color: #f0f4ff; line-height: 1; letter-spacing: -0.5px; }
.stat-label { font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat-glow {
  position: absolute; bottom: -20px; right: -20px;
  width: 80px; height: 80px; border-radius: 50%;
  filter: blur(30px); opacity: 0.15; pointer-events: none;
}

/* Main row */
.bento-main { display: grid; grid-template-columns: 1fr 340px; gap: 14px; }
.bento-right { display: flex; flex-direction: column; gap: 14px; }

/* Generic bento card */
.bento-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px; padding: 20px;
  backdrop-filter: blur(20px);
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
}
.bento-card:hover {
  border-color: rgba(255,255,255,0.11);
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
}
.bento-card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.bento-card-title {
  font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.4);
  text-transform: uppercase; letter-spacing: 1px;
}
.link-btn {
  display: flex; align-items: center; gap: 4px;
  background: none; border: none; color: #7eb3ff;
  font-size: 12px; cursor: pointer; padding: 0;
  transition: gap 0.2s;
}
.link-btn:hover { gap: 7px; }

/* Collections */
.collections-list { display: flex; flex-direction: column; gap: 6px; }
.col-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px; border-radius: 10px;
  cursor: pointer; transition: background 0.15s;
  border: 1px solid transparent;
}
.col-row:hover { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.06); }
.col-icon {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: rgba(79,142,247,0.1); border: 1px solid rgba(79,142,247,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: #7eb3ff;
}
.col-name { font-size: 13px; color: #e2e8f0; font-weight: 500; }
.col-meta { font-size: 11px; color: rgba(255,255,255,0.25); margin-top: 1px; }
.col-tags { display: flex; gap: 4px; margin-left: auto; flex-shrink: 0; }
.mini-tag {
  font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 5px;
  text-transform: uppercase; letter-spacing: 0.3px;
}
.mini-tag.blue { background: rgba(79,142,247,0.12); color: #7eb3ff; }
.mini-tag.purple { background: rgba(167,139,250,0.12); color: #a78bfa; }
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 32px 0; color: rgba(255,255,255,0.2); font-size: 13px;
}

/* Actions */
.actions-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.action-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 14px 8px; border-radius: 12px; cursor: pointer;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.5); font-size: 12px; font-weight: 500;
  transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
}
.action-btn:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.85);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.action-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; color: var(--ac);
  background: color-mix(in srgb, var(--ac) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--ac) 25%, transparent);
  transition: box-shadow 0.2s;
}
.action-btn:hover .action-icon { box-shadow: 0 0 16px color-mix(in srgb, var(--ac) 40%, transparent); }

/* Status */
.live-badge {
  display: flex; align-items: center; gap: 5px;
  font-size: 10px; font-weight: 700; color: #2dd4a0;
  text-transform: uppercase; letter-spacing: 1px;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #2dd4a0;
  animation: pulse-green 2s infinite;
  box-shadow: 0 0 0 0 rgba(45,212,160,0.4);
}
@keyframes pulse-green {
  0%   { box-shadow: 0 0 0 0 rgba(45,212,160,0.4); }
  70%  { box-shadow: 0 0 0 6px rgba(45,212,160,0); }
  100% { box-shadow: 0 0 0 0 rgba(45,212,160,0); }
}
.status-rows { display: flex; flex-direction: column; gap: 10px; }
.status-row { display: flex; align-items: center; justify-content: space-between; }
.status-name { font-size: 13px; color: rgba(255,255,255,0.4); }
.status-indicator {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 500;
}
.status-indicator.ok { color: #2dd4a0; }
.status-indicator.err { color: #f06b6b; }
.status-dot-sm { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }

/* Transitions */
.slide-up-enter-active { transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
.slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from { opacity: 0; transform: translateY(10px); }
.slide-up-leave-to { opacity: 0; transform: translateY(-5px); }

@media (max-width: 1024px) {
  .bento-stats { grid-template-columns: repeat(2, 1fr); }
  .bento-main { grid-template-columns: 1fr; }
  .hero-title { font-size: 28px; }
}
</style>
