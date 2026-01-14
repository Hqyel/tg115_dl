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
        const isDark = ref(localStorage.getItem('theme') === 'dark' || !localStorage.getItem('theme'));

        // 登录表单
        const loginForm = ref({ username: '', password: '' });

        // 数据
        const dashboard = ref({ channels: [], total_resources: 0, total_parsed: 0, sync_status: {} });
        const channels = ref([]);
        const searchQuery = ref('');
        const searchChannel = ref('');
        const searchResults = ref([]);
        const searchPerformed = ref(false);
        const resourceChannel = ref('lsp115');
        const resourcePage = ref(1);
        const resourceTotalPages = ref(1);
        const resources = ref([]);
        const syncChannel = ref('all');
        const syncStatus = ref({ running: false, message: '' });

        const isLoggedIn = computed(() => !!token.value);
        const syncRunning = computed(() => syncStatus.value.running);

        // 主题切换
        function toggleTheme() {
            isDark.value = !isDark.value;
            document.documentElement.classList.toggle('dark', isDark.value);
            localStorage.setItem('theme', isDark.value ? 'dark' : 'light');
        }

        // 初始化主题
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

        async function doSearch() {
            if (!searchQuery.value.trim()) return;
            loading.value = true;
            searchPerformed.value = true;
            try {
                let url = `/search?q=${encodeURIComponent(searchQuery.value)}`;
                if (searchChannel.value) url += `&channel=${searchChannel.value}`;
                const data = await api(url);
                searchResults.value = data.resources;
            } catch (e) {
                searchResults.value = [];
            } finally {
                loading.value = false;
            }
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
            dashboard, channels, searchQuery, searchChannel, searchResults, searchPerformed,
            resourceChannel, resourcePage, resourceTotalPages, resources,
            syncChannel, syncStatus, syncRunning,
            toggleTheme, login, logout, loadDashboard, doSearch, loadResources, copyLink, syncNow
        };
    }
}).mount('#app');
