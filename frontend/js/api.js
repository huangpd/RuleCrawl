/**
 * RuleCrawl API 客户端
 * 封装所有后端 API 调用
 */

const API_BASE = '/api/v1';

const api = {
    // ============ 项目 ============
    async createProject(name, description = '') {
        const res = await fetch(`${API_BASE}/projects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description }),
        });
        return res.json();
    },

    async listProjects(page = 1, pageSize = 20, keyword = '') {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (keyword) params.append('keyword', keyword);
        const res = await fetch(`${API_BASE}/projects?${params}`);
        if (!res.ok) throw new Error('获取项目列表失败');
        return res.json();
    },

    async getProject(id) {
        const res = await fetch(`${API_BASE}/projects/${id}`);
        return res.json();
    },

    async updateProject(id, data) {
        const res = await fetch(`${API_BASE}/projects/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async deleteProject(id) {
        const res = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
        return res.json();
    },

    // ============ 节点 ============
    async createNode(projectId, nodeData) {
        const res = await fetch(`${API_BASE}/projects/${projectId}/nodes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(nodeData),
        });
        return res.json();
    },

    async listNodes(projectId) {
        const res = await fetch(`${API_BASE}/projects/${projectId}/nodes`);
        return res.json();
    },

    async updateNode(nodeId, data) {
        const res = await fetch(`${API_BASE}/nodes/${nodeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async deleteNode(nodeId) {
        const res = await fetch(`${API_BASE}/nodes/${nodeId}`, { method: 'DELETE' });
        return res.json();
    },

    async setCallback(nodeId, targetNodeId) {
        const res = await fetch(
            `${API_BASE}/nodes/${nodeId}/set-callback?target_node_id=${targetNodeId || ''}`,
            { method: 'POST' }
        );
        return res.json();
    },

    // ============ 任务 ============
    async runProject(projectId) {
        const res = await fetch(`${API_BASE}/projects/${projectId}/run`, { method: 'POST' });
        return res.json();
    },

    async getTaskStatus(taskId) {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/status`);
        return res.json();
    },

    async stopTask(taskId) {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/stop`, { method: 'POST' });
        return res.json();
    },

    async listTasks(projectId) {
        const res = await fetch(`${API_BASE}/projects/${projectId}/tasks`);
        return res.json();
    },

    // ============ 数据 ============
    async listData(projectId, page = 1, pageSize = 20) {
        const res = await fetch(
            `${API_BASE}/projects/${projectId}/data?page=${page}&page_size=${pageSize}`
        );
        return res.json();
    },

    async clearData(projectId) {
        const res = await fetch(`${API_BASE}/projects/${projectId}/data`, { method: 'DELETE' });
        return res.json();
    },
};
