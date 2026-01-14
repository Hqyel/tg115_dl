/**
 * TG 资源爬虫 - 前端应用
 */

const { createApp, ref, computed, onMounted } = Vue;

createApp({
  setup() {
    // 状态
    const token = ref(localStorage.getItem('token') || '');
    const username = ref(localStorage.getItem('username') || '');
    const currentPage = ref('dashboard');
    const loading = ref(false);
    const error = ref('');

    // 登录表单
    const loginForm = ref({
      username: '',
      password: ''
    });

    // 仪表盘数据
    const dashboard = ref({
      channels: [],
      total_resources: 0,
      total_parsed: 0,
      sync_status: {}
    });

    // 频道列表
    const channels = ref([]);

    // 搜索
    const searchQuery = ref('');
    const searchChannel = ref('');
    const searchResults = ref([]);
    const searchPerformed = ref(false);

    // 资源列表
    const resourceChannel = ref('lsp115');
    const resourcePage = ref(1);
    const resourceTotalPages = ref(1);
    const resources = ref([]);

    // 同步
    const syncChannel = ref('all');
    const syncStatus = ref({ running: false, message: '' });
    const syncRunning = computed(() => syncStatus.value.running);

    // 定时任务
    const tasks = ref([]);
    const newTask = ref({
      channel: 'all',
      mode: 'incremental',
      interval: 6
    });

    // 计算属性
    const isLoggedIn = computed(() => !!token.value);

    // API 请求
    async function api(url, options = {}) {
      const headers = {
        'Content-Type': 'application/json',
        ...options.headers
      };

      if (token.value) {
        headers['Authorization'] = `Bearer ${token.value}`;
      }

      const response = await fetch(`/api${url}`, {
        ...options,
        headers
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || '请求失败');
      }

      return data;
    }

    // 登录
    async function login() {
      loading.value = true;
      error.value = '';

      try {
        const data = await api('/auth/login', {
          method: 'POST',
          body: JSON.stringify(loginForm.value)
        });

        token.value = data.token;
        username.value = data.username;
        localStorage.setItem('token', data.token);
        localStorage.setItem('username', data.username);

        loginForm.value = { username: '', password: '' };
        loadDashboard();
        loadChannels();
      } catch (e) {
        error.value = e.message;
      } finally {
        loading.value = false;
      }
    }

    // 登出
    function logout() {
      token.value = '';
      username.value = '';
      localStorage.removeItem('token');
      localStorage.removeItem('username');
    }

    // 加载仪表盘
    async function loadDashboard() {
      try {
        dashboard.value = await api('/dashboard');
      } catch (e) {
        console.error('加载仪表盘失败:', e);
      }
    }

    // 加载频道列表
    async function loadChannels() {
      try {
        const data = await api('/channels');
        channels.value = data.channels;
        if (channels.value.length > 0) {
          resourceChannel.value = channels.value[0].id;
        }
      } catch (e) {
        console.error('加载频道失败:', e);
      }
    }

    // 搜索
    async function doSearch() {
      if (!searchQuery.value.trim()) return;

      loading.value = true;
      searchPerformed.value = true;

      try {
        let url = `/search?q=${encodeURIComponent(searchQuery.value)}`;
        if (searchChannel.value) {
          url += `&channel=${searchChannel.value}`;
        }
        const data = await api(url);
        searchResults.value = data.resources;
      } catch (e) {
        console.error('搜索失败:', e);
        searchResults.value = [];
      } finally {
        loading.value = false;
      }
    }

    // 加载资源列表
    async function loadResources() {
      try {
        const data = await api(`/resources?channel=${resourceChannel.value}&page=${resourcePage.value}`);
        resources.value = data.resources;
        resourceTotalPages.value = data.total_pages;
      } catch (e) {
        console.error('加载资源失败:', e);
      }
    }

    // 复制链接
    function copyLink(url) {
      navigator.clipboard.writeText(url).then(() => {
        alert('链接已复制到剪贴板');
      }).catch(() => {
        // 备用方案
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        alert('链接已复制到剪贴板');
      });
    }

    // 同步
    async function syncNow(mode) {
      try {
        let url = mode === 'full' ? '/sync/full' : '/sync/incremental';
        
        if (syncChannel.value === 'all') {
          url = '/sync/all';
          await api(url, {
            method: 'POST',
            body: JSON.stringify({ full: mode === 'full' })
          });
        } else {
          await api(url, {
            method: 'POST',
            body: JSON.stringify({ channel: syncChannel.value })
          });
        }
        
        pollSyncStatus();
      } catch (e) {
        alert('启动同步失败: ' + e.message);
      }
    }

    // 轮询同步状态
    async function pollSyncStatus() {
      try {
        syncStatus.value = await api('/sync/status');
        
        if (syncStatus.value.running) {
          setTimeout(pollSyncStatus, 2000);
        } else {
          loadDashboard();
        }
      } catch (e) {
        console.error('获取同步状态失败:', e);
      }
    }

    // 加载定时任务
    async function loadTasks() {
      try {
        const data = await api('/tasks');
        tasks.value = data.tasks;
      } catch (e) {
        console.error('加载任务失败:', e);
      }
    }

    // 添加定时任务
    async function addTask() {
      try {
        await api('/tasks', {
          method: 'POST',
          body: JSON.stringify({
            channel: newTask.value.channel,
            mode: newTask.value.mode,
            interval_hours: parseInt(newTask.value.interval)
          })
        });
        loadTasks();
        alert('任务已添加');
      } catch (e) {
        alert('添加任务失败: ' + e.message);
      }
    }

    // 删除定时任务
    async function deleteTask(jobId) {
      if (!confirm('确定要删除这个任务吗？')) return;

      try {
        await api(`/tasks/${jobId}`, { method: 'DELETE' });
        loadTasks();
      } catch (e) {
        alert('删除任务失败: ' + e.message);
      }
    }

    // 格式化日期
    function formatDate(isoString) {
      if (!isoString) return '-';
      const date = new Date(isoString);
      return date.toLocaleString('zh-CN');
    }

    // 初始化
    onMounted(() => {
      if (isLoggedIn.value) {
        loadDashboard();
        loadChannels();
        loadTasks();
        pollSyncStatus();
      }
    });

    return {
      // 状态
      isLoggedIn,
      username,
      currentPage,
      loading,
      error,
      loginForm,
      dashboard,
      channels,
      searchQuery,
      searchChannel,
      searchResults,
      searchPerformed,
      resourceChannel,
      resourcePage,
      resourceTotalPages,
      resources,
      syncChannel,
      syncStatus,
      syncRunning,
      tasks,
      newTask,

      // 方法
      login,
      logout,
      loadDashboard,
      doSearch,
      loadResources,
      copyLink,
      syncNow,
      loadTasks,
      addTask,
      deleteTask,
      formatDate
    };
  }
}).mount('#app');
