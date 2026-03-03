/**
 * RuleCrawl 标签页管理 - 纯净 JSON 版
 * 统一所有结构化请求参数为 JSON 录入，URL 保持列表模式。
 */

// ============ 全局工具函数 ============

/** 解析宽松 JSON (支持单引号, Python 格式) */
function parseRelaxedJSON(text) {
    if (!text || !text.trim()) return {};
    try { return JSON.parse(text); } catch (e) {}
    try {
        const fn = new Function('None', 'True', 'False', `return (${text});`);
        const result = fn(null, true, false);
        return (typeof result === 'object' && result !== null) ? result : {};
    } catch (e2) {
        throw new Error("JSON 格式错误，请检查输入是否为有效的对象格式 {}");
    }
}

/** 格式化显示 JSON */
function safeStringify(obj) {
    if (!obj || typeof obj !== 'object') return '';
    try { return JSON.stringify(obj, null, 2); } catch (e) { return ''; }
}

/** 添加起始 URL 行 */
window.addStartUrlRow = function(url = '') {
    const container = document.getElementById('start-url-list');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'field-row url-row';
    row.style.gridTemplateColumns = '1fr 40px';
    row.style.marginBottom = '4px';
    row.innerHTML = `<input class="form-input" placeholder="https://..." style="flex:1" value="${url}"><button type="button" class="field-remove-btn" onclick="this.parentElement.remove()">✕</button>`;
    container.appendChild(row);
};

// ============ 内部逻辑 ============

app.state.currentEditingFieldRow = null;
app.state.tempCleanRules = [];

function openCleanRulesModal(btn) {
    const row = btn.closest('.field-row');
    app.state.currentEditingFieldRow = row;
    const rulesData = row.dataset.cleanRules;
    try { app.state.tempCleanRules = rulesData ? JSON.parse(rulesData) : []; } catch (e) { app.state.tempCleanRules = []; }
    renderCleanRulesList();
    document.getElementById('cleanRulesModal').style.display = 'flex';
}

function closeCleanRulesModal() { document.getElementById('cleanRulesModal').style.display = 'none'; }

function renderCleanRulesList() {
    const container = document.getElementById('cleanRulesList');
    container.innerHTML = '';
    if (app.state.tempCleanRules.length === 0) { container.innerHTML = '<div class="empty-state">暂无规则</div>'; return; }
    app.state.tempCleanRules.forEach((rule, index) => {
        const row = document.createElement('div');
        row.className = 'field-row clean-rule-row';
        let inputsHtml = '';
        if (rule.type === 'trim') { inputsHtml = '<span style="flex:1; font-size:12px; color:var(--text-dim);">删除前后空格</span>'; }
        else if (rule.type === 'replace' || rule.type === 'regex_sub') {
            inputsHtml = `<input class="form-input rule-old" style="flex:1" placeholder="查找" value="${rule.old || ''}"><input class="form-input rule-new" style="flex:1" placeholder="替换" value="${rule.new || ''}">`;
        } else if (rule.type === 'prefix' || rule.type === 'suffix') {
            inputsHtml = `<input class="form-input rule-value" style="flex:1" placeholder="内容" value="${rule.value || ''}">`;
        }
        row.innerHTML = `<span class="flow-node-badge">${rule.type.toUpperCase()}</span>${inputsHtml}<button type="button" onclick="removeCleanRuleRow(${index})">✕</button>`;
        container.appendChild(row);
    });
}

function addCleanRuleRow(type) { syncCleanRulesFromUI(); app.state.tempCleanRules.push({ type }); renderCleanRulesList(); }
function removeCleanRuleRow(index) { syncCleanRulesFromUI(); app.state.tempCleanRules.splice(index, 1); renderCleanRulesList(); }
function syncCleanRulesFromUI() {
    const rows = document.querySelectorAll('#cleanRulesList .clean-rule-row');
    rows.forEach((row, index) => {
        const rule = app.state.tempCleanRules[index];
        if (!rule) return;
        if (rule.type === 'replace' || rule.type === 'regex_sub') {
            rule.old = row.querySelector('.rule-old')?.value;
            rule.new = row.querySelector('.rule-new')?.value;
        } else if (rule.type === 'prefix' || rule.type === 'suffix') {
            rule.value = row.querySelector('.rule-value')?.value;
        }
    });
}

function confirmSaveCleanRules() {
    syncCleanRulesFromUI();
    if (app.state.currentEditingFieldRow) {
        app.state.currentEditingFieldRow.dataset.cleanRules = JSON.stringify(app.state.tempCleanRules);
        const btn = app.state.currentEditingFieldRow.querySelector('.field-clean-btn');
        if (btn) btn.textContent = `✨ 清洗(${app.state.tempCleanRules.length})`;
    }
    closeCleanRulesModal();
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${tabId}"]`);
    if (btn) btn.classList.add('active');
    const pane = document.getElementById(tabId);
    if (pane) pane.classList.add('active');
}

/** 加载节点数据到表单 */
function loadNodeToForm(node) {
    const type = node.node_type;
    const rc = node.request_config || {};
    const pr = node.parse_rules || {};
    const pg = node.pagination || {};

    const nameEl = document.getElementById(`${type}-name`);
    if (nameEl) nameEl.value = node.name || '';

    // 起始页加载
    if (type === 'start') {
        const urls = Array.isArray(rc.url) ? rc.url : (rc.url || '').split('\n').filter(u => u.trim());
        renderStartUrlList(urls);
        // 全 JSON 文本框回显
        document.getElementById('start-params').value = safeStringify(rc.params);
        document.getElementById('start-headers').value = safeStringify(rc.headers);
        document.getElementById('start-cookies').value = safeStringify(rc.cookies);
        document.getElementById('start-body').value = rc.body || '';
        document.getElementById('start-body-type').value = rc.body_type || 'json';
    } else {
        const urlEl = document.getElementById(`${type}-url`);
        if (urlEl) urlEl.value = Array.isArray(rc.url) ? (rc.url[0] || '') : (rc.url || '');
    }

    const methodEl = document.getElementById(`${type}-method`);
    if (methodEl) methodEl.value = rc.method || 'GET';
    const bodyEl = document.getElementById(`${type}-body`);
    if (bodyEl) bodyEl.value = rc.body || '';

    const itemSelectorEl = document.getElementById(`${type}-item-selector`);
    if (itemSelectorEl) itemSelectorEl.value = pr.item_selector || '';
    const itemSelectorTypeEl = document.getElementById(`${type}-item-selector-type`);
    if (itemSelectorTypeEl) itemSelectorTypeEl.value = pr.item_selector_type || 'xpath';
    const linkSelectorEl = document.getElementById(`${type}-link-selector`);
    if (linkSelectorEl) linkSelectorEl.value = pr.link_selector || '';
    const linkSelectorTypeEl = document.getElementById(`${type}-link-selector-type`);
    if (linkSelectorTypeEl) linkSelectorTypeEl.value = pr.link_selector_type || 'xpath';

    const pgSelectorEl = document.getElementById(`${type}-pg-selector`);
    if (pgSelectorEl) pgSelectorEl.value = pg.selector || '';
    const pgTypeEl = document.getElementById(`${type}-pg-selector-type`);
    if (pgTypeEl) pgTypeEl.value = pg.selector_type || 'xpath';
    const pgMaxEl = document.getElementById(`${type}-pg-max`);
    if (pgMaxEl) pgMaxEl.value = pg.max_pages || 10;

    const cbEl = document.getElementById(`${type}-callback`);
    if (cbEl) { updateCallbackOptions(cbEl, node._id); cbEl.value = node.callback_node_id || ''; }

    renderNextStepSection(type, node.callback_node_id);

    if (type === 'detail') {
        renderDetailFields(pr.fields || []);
        const dedupTypeEl = document.getElementById('detail-dedup-type');
        if (dedupTypeEl) { dedupTypeEl.value = pr.deduplication_type || 'none'; toggleDedupField(); }
        refreshDedupFieldList();
        const dedupFieldEl = document.getElementById('detail-dedup-field');
        if (dedupFieldEl) dedupFieldEl.value = pr.deduplication_field || '';
    }
    if (type === 'list') renderListFields(pr.fields || []);

    app.state.editingNodeId = node._id;
    app.state.editingNodeType = type;
}

function renderStartUrlList(urls) {
    const container = document.getElementById('start-url-list');
    if (!container) return;
    container.innerHTML = '';
    if (!urls || urls.length === 0) { window.addStartUrlRow(); return; }
    urls.forEach(url => window.addStartUrlRow(url));
}

function refreshDedupFieldList() {
    const select = document.getElementById('detail-dedup-field');
    if (!select) return;
    const currentVal = select.value;
    const fields = collectDetailFields();
    select.innerHTML = '<option value="">-- 请选择去重字段 --</option>';
    fields.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.name; opt.textContent = f.name;
        select.appendChild(opt);
    });
    select.value = currentVal;
}

function updateCallbackOptions(selectEl, excludeId) {
    const current = selectEl.value;
    selectEl.innerHTML = '<option value="">无（终点）</option>';
    app.state.nodes.forEach(n => {
        if (n._id !== excludeId) {
            const opt = document.createElement('option');
            opt.value = n._id; opt.textContent = `${NODE_TYPE_LABELS[n.node_type]} - ${n.name}`;
            selectEl.appendChild(opt);
        }
    });
    selectEl.value = current;
}

function updateAllCallbacks() {
    ['start', 'list'].forEach(type => {
        const cbEl = document.getElementById(`${type}-callback`);
        if (cbEl) updateCallbackOptions(cbEl, app.state.editingNodeId);
    });
}

function collectNodeData(type) {
    let urlValue = [];
    let requestConfig = {};
    if (type === 'start') {
        const urlInputs = document.querySelectorAll('#start-url-list .url-row input');
        urlValue = Array.from(urlInputs).map(i => i.value.trim()).filter(v => v);
        
        try {
            requestConfig = {
                params: parseRelaxedJSON(document.getElementById('start-params').value),
                headers: parseRelaxedJSON(document.getElementById('start-headers').value),
                cookies: parseRelaxedJSON(document.getElementById('start-cookies').value),
                body: document.getElementById('start-body').value || null,
                body_type: document.getElementById('start-body-type').value || 'json'
            };
        } catch (e) {
            showToast(e.message, 'error');
            throw e;
        }
    } else {
        const val = document.getElementById(`${type}-url`)?.value?.trim();
        urlValue = val ? [val] : [];
    }

    const data = {
        node_type: type,
        name: document.getElementById(`${type}-name`)?.value || `${NODE_TYPE_LABELS[type]}`,
        request_config: {
            url: urlValue,
            method: document.getElementById(`${type}-method`)?.value || 'GET',
            params: type === 'start' ? requestConfig.params : {},
            headers: type === 'start' ? requestConfig.headers : {},
            cookies: type === 'start' ? requestConfig.cookies : {},
            body: type === 'start' ? requestConfig.body : (document.getElementById(`${type}-body`)?.value || null),
            body_type: type === 'start' ? requestConfig.body_type : 'json'
        },
        parse_rules: {
            parser_type: 'xpath', 
            item_selector: document.getElementById(`${type}-item-selector`)?.value || null,
            item_selector_type: document.getElementById(`${type}-item-selector-type`)?.value || 'xpath',
            link_selector: document.getElementById(`${type}-link-selector`)?.value || null,
            link_selector_type: document.getElementById(`${type}-link-selector-type`)?.value || null,
            fields: (type === 'list') ? collectListFields() : [],
        },
        callback_node_id: document.getElementById(`${type}-callback`)?.value || null,
    };
    const pgSelector = document.getElementById(`${type}-pg-selector`)?.value;
    if (pgSelector) {
        data.pagination = {
            selector: pgSelector,
            selector_type: document.getElementById(`${type}-pg-selector-type`)?.value || 'xpath',
            max_pages: parseInt(document.getElementById(`${type}-pg-max`)?.value) || 10,
        };
    }
    if (type === 'detail') {
        data.parse_rules.fields = collectDetailFields();
        data.parse_rules.deduplication_type = document.getElementById('detail-dedup-type')?.value || 'none';
        data.parse_rules.deduplication_field = document.getElementById('detail-dedup-field')?.value || null;
    }
    return data;
}

async function saveNode(type) {
    if (!app.state.currentProjectId) return;
    try {
        const data = collectNodeData(type);
        let nodeId = app.state.editingNodeId;
        if (nodeId && app.state.editingNodeType === type) {
            await api.updateNode(nodeId, data);
            showToast(`节点已更新`, 'success');
        } else {
            const result = await api.createNode(app.state.currentProjectId, data);
            nodeId = result._id;
            app.state.editingNodeId = nodeId; app.state.editingNodeType = type;
            showToast(`节点已创建`, 'success');
            if (app.state.pendingParentId) { await api.setCallback(app.state.pendingParentId, nodeId); app.state.pendingParentId = null; }
        }
        await refreshNodes();
    } catch (e) { showToast('保存失败: ' + e.message, 'error'); }
}

function newNode(type) {
    app.state.editingNodeId = null; app.state.editingNodeType = null;
    const form = document.getElementById(`tab-${type}`);
    if (form) { form.querySelectorAll('input, textarea').forEach(el => el.value = ''); form.querySelectorAll('select').forEach(el => el.selectedIndex = 0); }
    if (type === 'detail') renderDetailFields([]);
    if (type === 'list') renderListFields([]);
    if (type === 'start') { 
        renderStartUrlList([]); 
        document.getElementById('start-params').value = '';
        document.getElementById('start-headers').value = '';
        document.getElementById('start-cookies').value = '';
    }
}

function renderDetailFields(fields) {
    const container = document.getElementById('detail-fields');
    container.innerHTML = '';
    if (!fields || fields.length === 0) { addDetailField(); return; }
    fields.forEach(f => addDetailField(f));
}

function addDetailField(fieldData = null) {
    const container = document.getElementById('detail-fields');
    const row = document.createElement('div');
    row.className = 'field-row';
    const cleanRulesJson = fieldData && fieldData.clean_rules ? JSON.stringify(fieldData.clean_rules) : '[]';
    row.dataset.cleanRules = cleanRulesJson;
    row.innerHTML = `
        <input class="form-input field-name" placeholder="字段名" oninput="refreshDedupFieldList()">
        <select class="form-select field-type">
            <option value="xpath">XPath</option><option value="css">CSS</option><option value="jsonpath">JsonPath</option><option value="regex">Regex</option><option value="text">Text</option>
        </select>
        <input class="form-input field-selector" placeholder="选择器表达式">
        <div style="display:flex; align-items:center; gap:8px; justify-content: flex-end;">
            <label class="form-checkbox-label" style="white-space:nowrap;"><input type="checkbox" class="field-required"> 必填</label>
            <button class="btn btn-ghost btn-xs field-clean-btn" onclick="openCleanRulesModal(this)" style="min-width:65px;">✨ 清洗</button>
            <button class="field-remove-btn" onclick="this.parentElement.parentElement.remove(); refreshDedupFieldList();">✕</button>
        </div>
    `;
    if (fieldData) {
        row.querySelector('.field-name').value = fieldData.name || '';
        row.querySelector('.field-type').value = fieldData.selector_type || 'xpath';
        row.querySelector('.field-selector').value = fieldData.selector || '';
        row.querySelector('.field-required').checked = !!fieldData.required;
    }
    container.appendChild(row);
    refreshDedupFieldList();
}

function collectDetailFields() {
    const fields = [];
    document.querySelectorAll('#detail-fields .field-row').forEach(row => {
        const name = row.querySelector('.field-name')?.value?.trim();
        const selector = row.querySelector('.field-selector')?.value?.trim();
        const selectorType = row.querySelector('.field-type')?.value;
        const isRequired = !!row.querySelector('.field-required')?.checked;
        const cleanRulesJson = row.dataset.cleanRules;
        let cleanRules = []; try { cleanRules = cleanRulesJson ? JSON.parse(cleanRulesJson) : []; } catch (e) { }
        if (name && selector) fields.push({ name, selector, selector_type: selectorType, required: isRequired, clean_rules: cleanRules });
    });
    return fields;
}

function renderListFields(fields) {
    const container = document.getElementById('list-fields');
    if (!container) return;
    container.innerHTML = ''; (fields || []).forEach(f => addListField(f));
}

function addListField(fieldData = null) {
    const container = document.getElementById('list-fields');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'field-row';
    const cleanRulesJson = fieldData && fieldData.clean_rules ? JSON.stringify(fieldData.clean_rules) : '[]';
    row.dataset.cleanRules = cleanRulesJson;
    row.innerHTML = `
        <input class="form-input field-name" placeholder="字段名 (如 author)">
        <select class="form-select field-type">
            <option value="xpath">XPath</option><option value="css">CSS</option><option value="jsonpath">JsonPath</option><option value="regex">Regex</option><option value="text">Text</option>
        </select>
        <input class="form-input field-selector" placeholder="选择器表达式">
        <div style="display:flex; align-items:center; gap:8px; justify-content: flex-end;">
            <label class="form-checkbox-label" style="white-space:nowrap;"><input type="checkbox" class="field-required"> 必填</label>
            <button class="btn btn-ghost btn-xs field-clean-btn" onclick="openCleanRulesModal(this)" style="min-width:65px;">清洗</button>
            <button class="field-remove-btn" onclick="this.parentElement.parentElement.remove()">✕</button>
        </div>
    `;
    if (fieldData) {
        row.querySelector('.field-name').value = fieldData.name || '';
        row.querySelector('.field-type').value = fieldData.selector_type || 'xpath';
        row.querySelector('.field-selector').value = fieldData.selector || '';
        row.querySelector('.field-required').checked = !!fieldData.required;
    }
    container.appendChild(row);
}

function collectListFields() {
    const fields = [];
    document.querySelectorAll('#list-fields .field-row').forEach(row => {
        const name = row.querySelector('.field-name')?.value?.trim();
        const selector = row.querySelector('.field-selector')?.value?.trim();
        const selectorType = row.querySelector('.field-type')?.value;
        const isRequired = !!row.querySelector('.field-required')?.checked;
        const cleanRulesJson = row.dataset.cleanRules;
        let cleanRules = []; try { cleanRules = cleanRulesJson ? JSON.parse(cleanRulesJson) : []; } catch (e) { }
        if (name && selector) fields.push({ name, selector, selector_type: selectorType, required: isRequired, clean_rules: cleanRules });
    });
    return fields;
}

function showAddChildNode(parentNodeId) { app.state.pendingParentId = parentNodeId; document.getElementById('nodeTypeModal').style.display = 'flex'; }
function selectNodeType(type) { closeNodeTypeModal(); const tabMap = { 'list': 'tab-list', 'detail': 'tab-detail' }; switchTab(tabMap[type]); newNode(type); }
function closeNodeTypeModal() { document.getElementById('nodeTypeModal').style.display = 'none'; }

function renderNextStepSection(nodeType, callbackNodeId) {
    const container = document.getElementById(`${nodeType}-next-step`);
    if (!container) return;
    if (callbackNodeId) {
        const targetNode = app.state.nodes.find(n => n._id === callbackNodeId);
        if (!targetNode) return;
        container.innerHTML = `<div class="next-step-card"><span class="label">下一步骤：</span><span class="value flow-node-badge ${targetNode.node_type}">${NODE_TYPE_LABELS[targetNode.node_type]}</span><span style="font-size:13px;font-weight:500;margin-right:auto;margin-left:8px;">${targetNode.name}</span><div class="actions"><button onclick="selectNodeById('${callbackNodeId}')">✏️ 编辑</button><button onclick="unlinkNode('${nodeType}')" class="text-danger">❌ 断开</button></div></div>`;
    } else {
        if (nodeType === 'detail') { container.innerHTML = `<div style="font-size:12px;color:var(--text-dim);text-align:center;">（终点节点）</div>`; return; }
        container.innerHTML = `<button class="btn btn-outline btn-block btn-dashed" onclick="showAddChildNode(app.state.editingNodeId)">➕ 选择 下一步骤</button>`;
    }
}

function selectNodeById(nodeId) { const node = app.state.nodes.find(n => n._id === nodeId); if (node) selectNode(node); }
async function unlinkNode(nodeType) {
    if (!confirm('确定要断开吗？')) return;
    try { await api.setCallback(app.state.editingNodeId, ''); await refreshNodes(); const updatedNode = app.state.nodes.find(n => n._id === app.state.editingNodeId); if (updatedNode) loadNodeToForm(updatedNode); } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
}

function toggleDedupField() {
    const type = document.getElementById('detail-dedup-type')?.value;
    const fieldSelect = document.getElementById('detail-dedup-field');
    if (fieldSelect) { fieldSelect.style.display = (type === 'field') ? 'inline-block' : 'none'; if (type === 'field') refreshDedupFieldList(); }
}
