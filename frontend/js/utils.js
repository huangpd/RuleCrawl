/**
 * RuleCrawl 工具函数
 */

/** Toast 通知 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

/** 节点类型中文名 */
const NODE_TYPE_LABELS = {
    start: '起始页',
    intermediate: '中间页',
    list: '列表页',
    next: '下一页',
    detail: '详情页',
};

/** 节点类型图标 */
const NODE_TYPE_ICONS = {
    start: '🚀',
    intermediate: '🔗',
    list: '📋',
    next: '⏭️',
    detail: '📄',
};

/** 格式化日期 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleString('zh-CN');
}

/** 解析 Headers 文本 (key: value 格式) */
function parseHeaders(text) {
    const headers = {};
    if (!text) return headers;
    text.split('\n').forEach(line => {
        line = line.trim();
        if (!line) return;
        const idx = line.indexOf(':');
        if (idx > 0) {
            headers[line.substring(0, idx).trim()] = line.substring(idx + 1).trim();
        }
    });
    return headers;
}

/** 将 Headers 对象序列化为文本 */
function serializeHeaders(headers) {
    if (!headers || typeof headers !== 'object') return '';
    return Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join('\n');
}

/** 解析 Cookies 文本 (key=value 格式) */
function parseCookies(text) {
    const cookies = {};
    if (!text) return cookies;
    text.split('\n').forEach(line => {
        line = line.trim();
        if (!line) return;
        const idx = line.indexOf('=');
        if (idx > 0) {
            cookies[line.substring(0, idx).trim()] = line.substring(idx + 1).trim();
        }
    });
    return cookies;
}

/** 将 Cookies 对象序列化为文本 */
function serializeCookies(cookies) {
    if (!cookies || typeof cookies !== 'object') return '';
    return Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join('\n');
}

/** HTML 转义 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
