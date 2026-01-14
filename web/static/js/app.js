/**
 * TG 资源爬虫 - 前端应用
 */

const { createApp, ref, computed, onMounted, watch } = Vue;

createApp({
    setup() {
        // 状态
        const token = ref(localStorage.getItem('token') || '');
        const username = ref(localStorage.getItem('username') || '');
        const currentPage = ref('dashboard');
        const loading = ref(false);
        const error = ref('');
        const isDark = ref(localStorage.getItem('theme') !== 'light');

        // 侧边栏状态
        const sidebarOpen = ref(false);
        const sidebarCollapsed = ref(localStorage.getItem('sidebarCollapsed') === 'true');

        // 登录表单
        const loginForm = ref({ username: '', password: '' });

        // 数据
        const dashboard = ref({ channels: [], total_resources: 0, total_parsed: 0, sync_status: {} });
        const channels = ref([]);
        const searchQuery = ref('');
        const searchChannel = ref('');
        const searchResults = ref([]);
        const searchPerformed = ref(false);
        const searchHistory = ref(JSON.parse(localStorage.getItem('searchHistory') || '[]'));
        const resourceChannel = ref('lsp115');
        const resourcePage = ref(1);
        const resourceTotalPages = ref(1);
        const resources = ref([]);
        const syncChannel = ref('all');
        const syncStatus = ref({ running: false, message: '' });

        // 定时任务
        const tasks = ref([]);
        const newTask = ref({ channel: 'all', mode: 'incremental', interval: 6 });

        // 日志
        const logs = ref([]);
        const logFilter = ref('');

        // 原始卡片预览
        const showCardModal = ref(false);
        const cardModalHtml = ref('');

        const isLoggedIn = computed(() => !!token.value);
        const syncRunning = computed(() => syncStatus.value.running);

        // 保存侧边栏状态
        watch(sidebarCollapsed, (val) => {
            localStorage.setItem('sidebarCollapsed', val);
        });

        // 主题切换
        function toggleTheme() {
            isDark.value = !isDark.value;
            document.documentElement.classList.toggle('dark', isDark.value);
            localStorage.setItem('theme', isDark.value ? 'dark' : 'light');
        }

        function initTheme() {
            document.documentElement.classList.toggle('dark', isDark.value);
        }

        // API 请求
        async function api(url, options = {}) {
            const headers = { 'Content-Type': 'application/json', ...options.headers };
            if (token.value) headers['Authorization'] = `Bearer ${token.value}`;

            const response = await fetch(`/api${url}`, { ...options, headers });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '请求失败');
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

        function logout() {
            token.value = '';
            username.value = '';
            localStorage.removeItem('token');
            localStorage.removeItem('username');
        }

        async function loadDashboard() {
            try {
                dashboard.value = await api('/dashboard');
            } catch (e) {
                console.error('加载失败:', e);
            }
        }

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

        async function doSearch(query = null) {
            const q = query || searchQuery.value.trim();
            if (!q) return;
            searchQuery.value = q;
            loading.value = true;
            searchPerformed.value = true;
            try {
                let url = `/search?q=${encodeURIComponent(q)}`;
                if (searchChannel.value) url += `&channel=${searchChannel.value}`;
                const data = await api(url);
                searchResults.value = data.resources;
                // 保存到历史记录
                addToHistory(q);
            } catch (e) {
                searchResults.value = [];
            } finally {
                loading.value = false;
            }
        }

        function addToHistory(query) {
            const history = searchHistory.value.filter(h => h !== query);
            history.unshift(query);
            searchHistory.value = history.slice(0, 10); // 最多保存10条
            localStorage.setItem('searchHistory', JSON.stringify(searchHistory.value));
        }

        function removeFromHistory(query) {
            searchHistory.value = searchHistory.value.filter(h => h !== query);
            localStorage.setItem('searchHistory', JSON.stringify(searchHistory.value));
        }

        function clearHistory() {
            searchHistory.value = [];
            localStorage.removeItem('searchHistory');
        }

        async function loadResources() {
            try {
                const data = await api(`/resources?channel=${resourceChannel.value}&page=${resourcePage.value}`);
                resources.value = data.resources;
                resourceTotalPages.value = data.total_pages;
            } catch (e) {
                console.error('加载资源失败:', e);
            }
        }

        function copyLink(url) {
            navigator.clipboard.writeText(url).then(() => {
                alert('链接已复制到剪贴板');
            }).catch(() => {
                const input = document.createElement('input');
                input.value = url;
                document.body.appendChild(input);
                input.select();
                document.execCommand('copy');
                document.body.removeChild(input);
                alert('链接已复制到剪贴板');
            });
        }

        async function syncNow(mode) {
            try {
                if (syncChannel.value === 'all') {
                    await api('/sync/all', {
                        method: 'POST',
                        body: JSON.stringify({ full: mode === 'full' })
                    });
                } else {
                    await api('/sync', {
                        method: 'POST',
                        body: JSON.stringify({ channel: syncChannel.value, mode })
                    });
                }
                pollSyncStatus();
            } catch (e) {
                alert('同步失败: ' + e.message);
            }
        }

        async function pollSyncStatus() {
            try {
                syncStatus.value = await api('/sync/status');
                if (syncStatus.value.running) {
                    setTimeout(pollSyncStatus, 2000);
                } else {
                    loadDashboard();
                }
            } catch (e) {
                console.error('获取状态失败:', e);
            }
        }

        // 定时任务
        async function loadTasks() {
            try {
                const data = await api('/tasks');
                tasks.value = data.tasks;
            } catch (e) {
                console.error('加载任务失败:', e);
            }
        }

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
                alert('添加失败: ' + e.message);
            }
        }

        async function deleteTask(jobId) {
            if (!confirm('确定删除此任务？')) return;
            try {
                await api(`/tasks/${jobId}`, { method: 'DELETE' });
                loadTasks();
            } catch (e) {
                alert('删除失败: ' + e.message);
            }
        }

        function formatDate(isoString) {
            if (!isoString) return '-';
            return new Date(isoString).toLocaleString('zh-CN');
        }

        // 日志
        async function loadLogs() {
            try {
                let url = '/logs?limit=100';
                if (logFilter.value) url += `&type=${logFilter.value}`;
                const data = await api(url);
                logs.value = data.logs;
            } catch (e) {
                console.error('加载日志失败:', e);
            }
        }

        async function clearLogs() {
            if (!confirm('确定清空所有日志？')) return;
            try {
                await api('/logs', { method: 'DELETE' });
                logs.value = [];
            } catch (e) {
                alert('清空失败: ' + e.message);
            }
        }

        onMounted(() => {
            initTheme();
            if (isLoggedIn.value) {
                loadDashboard();
                loadChannels();
                pollSyncStatus();
            }
        });

        return {
            isLoggedIn, username, currentPage, loading, error, loginForm, isDark,
            sidebarOpen, sidebarCollapsed,
            dashboard, channels, searchQuery, searchChannel, searchResults, searchPerformed,
            searchHistory, removeFromHistory, clearHistory,
            resourceChannel, resourcePage, resourceTotalPages, resources,
            syncChannel, syncStatus, syncRunning,
            tasks, newTask,
            logs, logFilter, loadLogs, clearLogs,
            showCardModal, cardModalHtml,
            toggleTheme, login, logout, loadDashboard, doSearch, loadResources, copyLink, syncNow,
            loadTasks, addTask, deleteTask, formatDate,
            openCardPreview: (html) => { cardModalHtml.value = html; showCardModal.value = true; },
            closeCardPreview: () => { showCardModal.value = false; cardModalHtml.value = ''; }
        };
    }
}).mount('#app');
