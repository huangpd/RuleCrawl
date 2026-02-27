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

        // 兼容旧 API 返回数组的情况
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
        container = document.createElement('div');
        container.id = 'projectPagination';
        container.className = 'pagination';
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
    if (target) {
        target.style.display = 'flex';
        setTimeout(() => target.classList.add('active'), 10);
    }

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

        const createdDate = formatDate(p.created_at);
        const statusText = p.status === 'running' ? '运行中' : '空闲';
        const statusClass = p.status === 'running' ? 'running' : 'completed';

        tr.innerHTML = `
            <td style="font-weight:500; color:var(--text-primary)">${escapeHtml(p.name)}</td>
            <td style="color:var(--text-dim); font-size:13px">${escapeHtml(p.description || '-')}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td style="color:var(--text-dim); font-size:13px">${createdDate}</td>
            <td>
                <button class="btn btn-ghost btn-xs" style="margin-right:8px" onclick="event.stopPropagation(); selectProjectById('${p._id}')">打开</button>
                <button class="btn btn-ghost btn-xs" style="color:#ef4444" onclick="event.stopPropagation(); deleteProject('${p._id}', '${p.name}')">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableWrap.appendChild(table);
    container.appendChild(tableWrap);
}

/** 选择项目辅助函数 */
async function selectProjectById(id) {
    try {
        const project = await api.getProject(id);
        selectProject(project);
    } catch (e) {
        showToast('获取项目详情失败', 'error');
    }
}

/** 选择项目 */
async function selectProject(project) {
    app.state.currentProjectId = project._id;
    app.state.currentProjectName = project.name;

    // ── 修复状态污染：切换项目前清空上一个任务的统计显示 ──
    resetTaskUI();

    document.getElementById('workspaceProjectName').textContent = project.name;
    switchView('view-workspace');

    await refreshNodes();
    showToast(`已打开项目: ${project.name}`, 'success');

    if (app.state.nodes.length > 0) {
        selectNode(app.state.nodes[0]);
    } else {
        switchTab('tab-start');
        newNode('start');
    }
}

/** 重置任务相关的 UI 显示 */
function resetTaskUI() {
    const statusEl = document.getElementById('taskStatus');
    const statsEl = document.getElementById('taskStats');
    if (statusEl) statusEl.innerHTML = '';
    if (statsEl) statsEl.textContent = '';
    app.state.currentTaskId = null; // 清除当前任务 ID 引用
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

// ============ 节点管理 ============

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

async function stopTask() {
    if (!app.state.currentTaskId) return;
    try {
        await api.stopTask(app.state.currentTaskId);
        showToast('⏹ 任务已停止', 'info');
    } catch (e) {
        showToast('停止失败: ' + e.message, 'error');
    }
}

function pollTaskStatus(taskId) {
    const statusEl = document.getElementById('taskStatus');
    const statsEl = document.getElementById('taskStats');
    const interval = setInterval(async () => {
        // ── 安全检查：如果项目已切换，停止该任务的轮询 ──
        if (!app.state.currentProjectId) {
            clearInterval(interval);
            return;
        }

        try {
            const task = await api.getTaskStatus(taskId);
            
            // ── 安全检查：如果返回的任务项目 ID 与当前项目不匹配，停止轮询 ──
            if (task.project_id !== app.state.currentProjectId) {
                clearInterval(interval);
                return;
            }

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

    const searchField = document.getElementById('dataSearchField')?.value || '';
    const keyword = document.getElementById('dataSearchKeyword')?.value?.trim() || '';

    try {
        const result = await api.listData(app.state.currentProjectId, page, 20, searchField, keyword);
        if (result.items && result.items.length > 0) {
            updateDataSearchFields(result.items);
        }
        renderDataTable(result);
    } catch (e) {
        showToast('加载数据失败', 'error');
    }
}

function updateDataSearchFields(items) {
    const select = document.getElementById('dataSearchField');
    if (!select) return;

    const currentVal = select.value;
    const fields = new Set();
    items.forEach(item => {
        if (item.data) Object.keys(item.data).forEach(k => fields.add(k));
    });

    if (fields.size === 0) return;

    const existingOptions = Array.from(select.options).map(o => o.value);
    fields.forEach(f => {
        if (!existingOptions.includes(f)) {
            const opt = document.createElement('option');
            opt.value = f;
            opt.textContent = f;
            select.appendChild(opt);
        }
    });
    if (currentVal) select.value = currentVal;
}

async function deleteSingleData(dataId) {
    if (!confirm('确定要删除这条采集记录吗？')) return;
    try {
        await api.deleteData(dataId);
        showToast('数据已删除', 'success');
        loadData(app.state.dataPage);
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

function renderDataTable(result) {
    const container = document.getElementById('dataTableContainer');
    if (!result.items || result.items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无采集数据</p></div>';
        return;
    }

    const allKeys = new Set();
    result.items.forEach(item => {
        if (item.data) Object.keys(item.data).forEach(k => allKeys.add(k));
    });
    const keys = Array.from(allKeys);

    let html = '<div class="data-table-wrap"><table class="data-table"><thead><tr>';
    html += '<th style="width:50px">#</th><th>来源 URL</th>';
    keys.forEach(k => { html += `<th>${k}</th>`; });
    html += '<th style="width:140px">时间</th><th style="width:80px">操作</th></tr></thead><tbody>';

    result.items.forEach((item, i) => {
        html += '<tr>';
        html += `<td>${(result.page - 1) * result.page_size + i + 1}</td>`;
        const cleanUrl = (item.source_url || '');
        html += `<td><a href="${cleanUrl}" target="_blank" title="${cleanUrl}">${cleanUrl.substring(0, 50)}...</a></td>`;
        keys.forEach(k => {
            const val = escapeHtml(item.data?.[k] || '');
            html += `<td title="${val}">${val.substring(0, 80)}</td>`;
        });
        html += `<td>${formatDate(item.crawl_time)}</td>`;
        html += `<td><button class="btn btn-ghost btn-xs" style="color:var(--accent-red)" onclick="deleteSingleData('${item.id}')">删除</button></td>`;
        html += '</tr>';
    });
    html += '</tbody></table></div>';

    const totalPages = Math.ceil(result.total / result.page_size);
    html += '<div class="pagination">';
    html += `<button class="btn btn-ghost btn-sm" onclick="loadData(${Math.max(1, result.page - 1)})" ${result.page <= 1 ? 'disabled' : ''}>◀</button>`;
    html += `<span class="pagination-info">第 ${result.page} / ${totalPages} 页 (共 ${result.total} 条)</span>`;
    html += `<button class="btn btn-ghost btn-sm" onclick="loadData(${Math.min(totalPages, result.page + 1)})" ${result.page >= totalPages ? 'disabled' : ''}>▶</button>`;
    html += '</div>';

    container.innerHTML = html;
}

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
