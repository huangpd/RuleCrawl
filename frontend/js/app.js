/**
 * RuleCrawl 主应用入口
 * 全局状态管理、初始化、项目管理
 */

const app = {
    state: {
        currentProjectId: null,
        currentProjectName: '',
        nodes: [],
        activeNodeId: null,
        editingNodeId: null,
        editingNodeType: null,
        currentTaskId: null,
        dataPage: 1,
        // 项目列表状态
        projectPage: 1,
        projectKeyword: '',
    },
};

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', () => {
    initTabButtons();
    // 默认显示项目列表
    switchView('view-project-list');
});

/** 初始化标签页按钮 */
function initTabButtons() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
}

// ============ 项目管理 ============

/** 加载项目列表 */
async function loadProjects() {
    try {
        const result = await api.listProjects(app.state.projectPage, 20, app.state.projectKeyword);

        // 兼容旧 API 返回数组的情况（虽然已更新，但为了稳健性）
        const items = Array.isArray(result) ? result : (result.items || []);
        renderProjectList(items);

        if (!Array.isArray(result)) {
            renderProjectPagination(result);
        }
    } catch (e) {
        showToast('加载项目列表失败', 'error');
        console.error(e);
    }
}

/** 搜索项目 */
function searchProjects() {
    const keyword = document.getElementById('projectSearchInput')?.value?.trim() || '';
    app.state.projectKeyword = keyword;
    app.state.projectPage = 1; // 重置第一页
    loadProjects();
}

/** 切换项目页码 */
function changeProjectPage(page) {
    app.state.projectPage = page;
    loadProjects();
}

/** 渲染项目分页 */
function renderProjectPagination(result) {
    let container = document.getElementById('projectPagination');
    if (!container) {
        // 如果不存在，创建它并添加到 projectGrid 之后
        container = document.createElement('div');
        container.id = 'projectPagination';
        container.className = 'pagination';
        // 插入到 projectGrid 后面
        const grid = document.getElementById('projectGrid');
        if (grid && grid.parentNode) {
            grid.parentNode.appendChild(container);
        }
    }

    const totalPages = result.total_pages || 1;
    const page = result.page || 1;
    const total = result.total || 0;

    if (total === 0) {
        container.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="btn btn-ghost btn-sm" onclick="changeProjectPage(${Math.max(1, page - 1)})" ${page <= 1 ? 'disabled' : ''}>◀</button>`;
    html += `<span class="pagination-info">第 ${page} / ${totalPages} 页 (共 ${total} 条)</span>`;
    html += `<button class="btn btn-ghost btn-sm" onclick="changeProjectPage(${Math.min(totalPages, page + 1)})" ${page >= totalPages ? 'disabled' : ''}>▶</button>`;

    container.innerHTML = html;
}

/** 切换视图 */
function switchView(viewId) {
    document.querySelectorAll('.view-page').forEach(el => {
        el.style.display = 'none';
        el.classList.remove('active');
    });
    const target = document.getElementById(viewId);
    target.style.display = 'flex';
    // 强制重绘以触发 transition
    setTimeout(() => target.classList.add('active'), 10);

    if (viewId === 'view-project-list') {
        loadProjects();
    }
}

/** 返回项目列表 */
function backToProjects() {
    app.state.currentProjectId = null;
    app.state.currentProjectName = '';
    switchView('view-project-list');
}

/** 渲染项目列表 (表格形式) */
function renderProjectList(projects) {
    const container = document.getElementById('projectGrid');
    container.innerHTML = '';

    // 如果没有项目
    if (!projects.length) {
        container.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center;"><p style="color:var(--text-secondary)">暂无项目，点击右上角新建</p></div>';
        return;
    }

    const tableWrap = document.createElement('div');
    tableWrap.className = 'data-table-wrap';

    const table = document.createElement('table');
    table.className = 'data-table';
    table.innerHTML = `<thead><tr>
        <th style="width:20%">项目名称</th>
        <th style="width:35%">描述</th>
        <th style="width:10%">状态</th>
        <th style="width:15%">创建时间</th>
        <th style="width:20%">操作</th>
    </tr></thead>`;

    const tbody = document.createElement('tbody');

    projects.forEach(p => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => selectProject(p);

        const createdDate = new Date(p.created_at || Date.now()).toLocaleDateString();
        const statusText = p.status === 'running' ? '运行中' : '空闲';
        const statusClass = p.status === 'running' ? 'running' : 'completed';

        // Name
        const tdName = document.createElement('td');
        tdName.style.fontWeight = '500';
        tdName.style.color = 'var(--text-primary)';
        tdName.textContent = p.name;
        tr.appendChild(tdName);

        // Desc
        const tdDesc = document.createElement('td');
        tdDesc.style.color = 'var(--text-dim)';
        tdDesc.style.fontSize = '13px';
        tdDesc.textContent = p.description || '-';
        tr.appendChild(tdDesc);

        // Status
        const tdStatus = document.createElement('td');
        tdStatus.innerHTML = `<span class="status-badge ${statusClass}">${statusText}</span>`;
        tr.appendChild(tdStatus);

        // Time
        const tdTime = document.createElement('td');
        tdTime.style.color = 'var(--text-dim)';
        tdTime.style.fontSize = '13px';
        tdTime.textContent = createdDate;
        tr.appendChild(tdTime);

        // Actions
        const tdActions = document.createElement('td');

        const btnOpen = document.createElement('button');
        btnOpen.className = 'btn btn-ghost btn-xs';
        btnOpen.style.marginRight = '8px';
        btnOpen.textContent = '打开';
        btnOpen.onclick = (e) => {
            e.stopPropagation();
            selectProject(p);
        };
        tdActions.appendChild(btnOpen);

        // Data Button
        const btnData = document.createElement('button');
        btnData.className = 'btn btn-ghost btn-xs';
        btnData.style.marginRight = '8px';
        btnData.style.color = 'var(--accent-cyan)';
        btnData.textContent = '数据';
        btnData.onclick = (e) => {
            e.stopPropagation();
            openDataViewModal(p);
        };
        tdActions.appendChild(btnData);

        const btnDelete = document.createElement('button');
        btnDelete.className = 'btn btn-ghost btn-xs';
        btnDelete.style.color = '#ef4444'; // Red
        btnDelete.textContent = '删除';
        btnDelete.onclick = (e) => {
            e.stopPropagation();
            deleteProject(p._id, p.name);
        };
        tdActions.appendChild(btnDelete);

        tr.appendChild(tdActions);
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableWrap.appendChild(table);
    container.appendChild(tableWrap);
}

/** 渲染项目分页 */
function renderProjectPagination(result) {
    let container = document.getElementById('projectPagination');
    if (!container) {
        // 如果不存在，创建它并添加到 projectGrid 之后
        container = document.createElement('div');
        container.id = 'projectPagination';
        container.className = 'pagination';
        // 插入到 projectGrid 后面
        const grid = document.getElementById('projectGrid');
        if (grid && grid.parentNode) {
            grid.parentNode.appendChild(container); // Append to parent (container)
        }
    }

    const totalPages = result.total_pages || 1;
    const page = result.page || 1;
    const total = result.total || 0;

    if (total === 0) {
        container.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="btn btn-ghost btn-sm" onclick="changeProjectPage(${Math.max(1, page - 1)})" ${page <= 1 ? 'disabled' : ''}>◀</button>`;
    html += `<span class="pagination-info">第 ${page} / ${totalPages} 页 (共 ${total} 条)</span>`;
    html += `<button class="btn btn-ghost btn-sm" onclick="changeProjectPage(${Math.min(totalPages, page + 1)})" ${page >= totalPages ? 'disabled' : ''}>▶</button>`;

    container.innerHTML = html;
}

/** 选择项目 */
async function selectProject(project) {
    app.state.currentProjectId = project._id;
    app.state.currentProjectName = project.name;

    // 更新工作区顶部信息
    document.getElementById('workspaceProjectName').textContent = project.name;

    // 切换到工作区视图
    switchView('view-workspace');

    await refreshNodes();
    showToast(`已打开项目: ${project.name}`, 'success');

    // 自动选择第一个节点，或者进入初始化模式
    if (app.state.nodes.length > 0) {
        selectNode(app.state.nodes[0]);
    } else {
        switchTab('tab-start');
        newNode('start');
    }
}

// ============ 模态框逻辑 ============

function showCreateProjectModal() {
    document.getElementById('createProjectModal').style.display = 'flex';
    document.getElementById('modalProjectName').focus();
}

function closeCreateProjectModal() {
    document.getElementById('createProjectModal').style.display = 'none';
    document.getElementById('modalProjectName').value = '';
    document.getElementById('modalProjectDesc').value = '';
}

async function confirmCreateProject() {
    const name = document.getElementById('modalProjectName').value.trim();
    const desc = document.getElementById('modalProjectDesc').value.trim();

    if (!name) {
        showToast('请输入项目名称', 'error');
        return;
    }

    try {
        const project = await api.createProject(name, desc);
        closeCreateProjectModal();
        showToast(`项目 "${name}" 创建成功`, 'success');
        selectProject(project);
    } catch (e) {
        showToast('创建失败: ' + e.message, 'error');
    }
}

/** 删除项目 */
async function deleteProject(id, name) {
    if (!confirm(`确定要删除项目 "${name}" 吗？`)) return;
    try {
        await api.deleteProject(id);
        showToast('项目已删除', 'success');
        loadProjects();
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

/** 删除当前项目 (保留接口，暂未使用) */
async function deleteCurrentProject() {
    // 此功能暂未在 UI 显式入口调用，保留逻辑或移至项目卡片
}

// ============ 节点管理 ============

/** 刷新节点列表 */
async function refreshNodes() {
    if (!app.state.currentProjectId) return;
    try {
        app.state.nodes = await api.listNodes(app.state.currentProjectId);
        renderFlowPanel(app.state.nodes);
        updateAllCallbacks();
    } catch (e) {
        showToast('加载节点失败', 'error');
    }
}

// ============ 任务运行 ============

/** 启动任务 */
async function runTask() {
    if (!app.state.currentProjectId) {
        showToast('请先选择项目', 'error');
        return;
    }
    try {
        const result = await api.runProject(app.state.currentProjectId);
        if (result.task_id) {
            app.state.currentTaskId = result.task_id;
            showToast('🚀 任务已启动', 'success');
            pollTaskStatus(result.task_id);
        } else if (result.detail) {
            const errors = result.detail.errors || [result.detail];
            showToast('启动失败: ' + errors.join('; '), 'error');
        }
    } catch (e) {
        showToast('启动失败: ' + e.message, 'error');
    }
}

/** 停止任务 */
async function stopTask() {
    if (!app.state.currentTaskId) return;
    try {
        await api.stopTask(app.state.currentTaskId);
        showToast('⏹ 任务已停止', 'info');
    } catch (e) {
        showToast('停止失败: ' + e.message, 'error');
    }
}

/** 轮询任务状态 */
function pollTaskStatus(taskId) {
    const statusEl = document.getElementById('taskStatus');
    const statsEl = document.getElementById('taskStats');
    const interval = setInterval(async () => {
        try {
            const task = await api.getTaskStatus(taskId);
            if (statusEl) {
                statusEl.innerHTML = `<span class="status-badge ${task.status}">${task.status}</span>`;
            }
            if (statsEl && task.stats) {
                statsEl.textContent = `请求: ${task.stats.total_requests} | 采集: ${task.stats.total_items} | 错误: ${task.stats.errors}`;
            }
            if (['completed', 'failed', 'stopped'].includes(task.status)) {
                clearInterval(interval);
                await loadProjects();
                if (task.status === 'completed') {
                    showToast('✅ 任务完成！', 'success');
                } else if (task.status === 'failed') {
                    showToast('❌ 任务失败: ' + (task.error_message || ''), 'error');
                }
            }
        } catch (e) {
            clearInterval(interval);
        }
    }, 2000);
}

// ============ 数据展示 ============

/** 加载采集数据 */
async function loadData(page = 1) {
    if (!app.state.currentProjectId) {
        showToast('请先选择项目', 'error');
        return;
    }
    app.state.dataPage = page;
    try {
        const result = await api.listData(app.state.currentProjectId, page, 20);
        renderDataTable(result);
    } catch (e) {
        showToast('加载数据失败', 'error');
    }
}

/** 渲染数据表格 */
function renderDataTable(result) {
    const container = document.getElementById('dataTableContainer');
    if (!result.items || result.items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无采集数据</p></div>';
        return;
    }

    // 收集所有字段名
    const allKeys = new Set();
    result.items.forEach(item => {
        if (item.data) Object.keys(item.data).forEach(k => allKeys.add(k));
    });
    const keys = Array.from(allKeys);

    let html = '<div class="data-table-wrap"><table class="data-table"><thead><tr>';
    html += '<th>#</th><th>来源 URL</th>';
    keys.forEach(k => { html += `<th>${k}</th>`; });
    html += '<th>时间</th></tr></thead><tbody>';

    result.items.forEach((item, i) => {
        html += '<tr>';
        html += `<td>${(result.page - 1) * result.page_size + i + 1}</td>`;
        html += `<td><a href="${item.source_url}" target="_blank" title="${item.source_url}">${item.source_url?.substring(0, 50)}...</a></td>`;
        keys.forEach(k => {
            const val = item.data?.[k] || '';
            html += `<td title="${val}">${val.substring(0, 80)}</td>`;
        });
        html += `<td>${formatDate(item.crawl_time)}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';

    // 分页
    const totalPages = Math.ceil(result.total / result.page_size);
    html += '<div class="pagination">';
    html += `<button class="btn btn-ghost btn-sm" onclick="loadData(${Math.max(1, result.page - 1)})" ${result.page <= 1 ? 'disabled' : ''}>◀</button>`;
    html += `<span class="pagination-info">第 ${result.page} / ${totalPages} 页 (共 ${result.total} 条)</span>`;
    html += `<button class="btn btn-ghost btn-sm" onclick="loadData(${Math.min(totalPages, result.page + 1)})" ${result.page >= totalPages ? 'disabled' : ''}>▶</button>`;
    html += '</div>';

    container.innerHTML = html;
}

/** 清空数据 */
async function clearData() {
    if (!app.state.currentProjectId) return;
    if (!confirm('确定要清空所有采集数据吗？')) return;
    try {
        await api.clearData(app.state.currentProjectId);
        showToast('数据已清空', 'success');
        loadData(1);
    } catch (e) {
        showToast('清空失败: ' + e.message, 'error');
    }
}

// ============ 数据查看模态框逻辑 ============

app.state.viewingProjectId = null;
app.state.viewingDataPage = 1;

function openDataViewModal(project) {
    app.state.viewingProjectId = project._id;
    app.state.viewingDataPage = 1;

    document.getElementById('dataModalTitle').textContent = `项目数据: ${project.name}`;
    document.getElementById('dataModalTotal').textContent = '0';
    document.getElementById('modalDataTableContainer').innerHTML = '<div class="empty-state"><p>正在加载...</p></div>';
    document.getElementById('modalDataPagination').innerHTML = '';

    document.getElementById('dataViewModal').style.display = 'flex';

    loadModalData(1);
}

function closeDataViewModal() {
    document.getElementById('dataViewModal').style.display = 'none';
    app.state.viewingProjectId = null;
}

async function loadModalData(page = 1) {
    if (!app.state.viewingProjectId) return;
    app.state.viewingDataPage = page;

    const container = document.getElementById('modalDataTableContainer');
    container.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';

    try {
        const result = await api.listData(app.state.viewingProjectId, page, 10); // 每页 10 条

        document.getElementById('dataModalTotal').textContent = result.total;
        renderModalDataTable(result);
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p style="color:red">加载失败: ${e.message}</p></div>`;
    }
}

function renderModalDataTable(result) {
    const container = document.getElementById('modalDataTableContainer');

    if (!result.items || result.items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无采集数据</p></div>';
        document.getElementById('modalDataPagination').innerHTML = '';
        return;
    }

    let html = '<table class="data-table" style="width:100%; border-collapse: collapse;">';
    html += '<thead style="position:sticky; top:0; background:rgba(30,30,40,0.95); z-index:1;"><tr>';
    html += '<th style="width:60px;">#</th><th style="width:160px;">采集时间</th><th>Data 字段内容 (JSON)</th>';
    html += '</tr></thead><tbody>';

    result.items.forEach((item, i) => {
        const idx = (result.page - 1) * result.page_size + i + 1;
        const timeStr = formatDate(item.crawl_time);
        // 格式化 JSON，缩进 2 空格
        const jsonStr = JSON.stringify(item.data, null, 2);

        html += '<tr>';
        html += `<td style="vertical-align:top; color:var(--text-dim);">${idx}</td>`;
        html += `<td style="vertical-align:top; font-size:12px; color:var(--text-dim); white-space:nowrap;">${timeStr}</td>`;
        html += `<td style="font-family:monospace; font-size:12px; white-space:pre-wrap; word-break:break-all; color:var(--accent-cyan);">${jsonStr}</td>`;
        html += '</tr>';
    });
    html += '</tbody></table>';

    container.innerHTML = html;

    // 分页
    const totalPages = Math.ceil(result.total / result.page_size);
    const page = result.page;
    let pagHtml = '';

    pagHtml += `<button class="btn btn-ghost btn-sm" onclick="loadModalData(${Math.max(1, page - 1)})" ${page <= 1 ? 'disabled' : ''}>◀</button>`;
    pagHtml += `<span class="pagination-info" style="margin:0 8px;">第 ${page} / ${totalPages} 页</span>`;
    pagHtml += `<button class="btn btn-ghost btn-sm" onclick="loadModalData(${Math.min(totalPages, page + 1)})" ${page >= totalPages ? 'disabled' : ''}>▶</button>`;

    document.getElementById('modalDataPagination').innerHTML = pagHtml;
}
