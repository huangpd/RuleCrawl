/**
 * RuleCrawl 标签页管理
 * 处理 5 个标签页的表单渲染、数据加载和保存
 */

/** 切换标签页 */
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${tabId}"]`);
    const pane = document.getElementById(tabId);
    if (btn) btn.classList.add('active');
    if (pane) pane.classList.add('active');
}

/** 加载节点数据到对应表单 */
function loadNodeToForm(node) {
    const type = node.node_type;
    const rc = node.request_config || {};
    const pr = node.parse_rules || {};
    const pg = node.pagination || {};

    // 通用字段
    const nameEl = document.getElementById(`${type}-name`);
    if (nameEl) nameEl.value = node.name || '';

    // 请求配置
    const urlEl = document.getElementById(`${type}-url`);
    if (urlEl) urlEl.value = rc.url || '';

    const methodEl = document.getElementById(`${type}-method`);
    if (methodEl) methodEl.value = rc.method || 'GET';

    const headersEl = document.getElementById(`${type}-headers`);
    if (headersEl) {
        // Headers as JSON string
        try {
            headersEl.value = rc.headers ? JSON.stringify(rc.headers, null, 2) : '';
        } catch (e) {
            headersEl.value = '';
        }
    }

    // Removed cookiesEl handling

    const bodyEl = document.getElementById(`${type}-body`);
    if (bodyEl) bodyEl.value = rc.body || '';

    // 解析规则
    // parser_type 默认为 xpath，不再从 UI 读取

    const itemSelectorEl = document.getElementById(`${type}-item-selector`);
    if (itemSelectorEl) itemSelectorEl.value = pr.item_selector || '';

    const itemSelectorTypeEl = document.getElementById(`${type}-item-selector-type`);
    if (itemSelectorTypeEl) itemSelectorTypeEl.value = pr.item_selector_type || 'xpath';

    const linkSelectorEl = document.getElementById(`${type}-link-selector`);
    if (linkSelectorEl) linkSelectorEl.value = pr.link_selector || '';

    const linkSelectorTypeEl = document.getElementById(`${type}-link-selector-type`);
    if (linkSelectorTypeEl) linkSelectorTypeEl.value = pr.link_selector_type || 'xpath';

    // 翻页
    const pgSelectorEl = document.getElementById(`${type}-pg-selector`);
    if (pgSelectorEl) pgSelectorEl.value = pg.selector || '';

    const pgTypeEl = document.getElementById(`${type}-pg-selector-type`);
    if (pgTypeEl) pgTypeEl.value = pg.selector_type || 'xpath';

    const pgMaxEl = document.getElementById(`${type}-pg-max`);
    if (pgMaxEl) pgMaxEl.value = pg.max_pages || 10;

    // 回调选择器
    const cbEl = document.getElementById(`${type}-callback`);
    if (cbEl) {
        updateCallbackOptions(cbEl, node._id);
        cbEl.value = node.callback_node_id || '';
    }

    // 渲染下一步操作区
    renderNextStepSection(type, node.callback_node_id);

    // 详情页字段
    if (type === 'detail') {
        renderDetailFields(pr.fields || []);

        // 去重配置回显
        const dedupTypeEl = document.getElementById('detail-dedup-type');
        if (dedupTypeEl) {
            dedupTypeEl.value = pr.deduplication_type || 'none';
            toggleDedupField();
        }
        const dedupFieldEl = document.getElementById('detail-dedup-field');
        if (dedupFieldEl) {
            dedupFieldEl.value = pr.deduplication_field || '';
        }
    }

    // 标记当前编辑的节点 ID
    app.state.editingNodeId = node._id;
    app.state.editingNodeType = type;
}

/** 更新回调下拉选项 */
function updateCallbackOptions(selectEl, excludeId) {
    const current = selectEl.value;
    selectEl.innerHTML = '<option value="">无（终点）</option>';
    app.state.nodes.forEach(n => {
        if (n._id !== excludeId) {
            const opt = document.createElement('option');
            opt.value = n._id;
            opt.textContent = `${NODE_TYPE_LABELS[n.node_type]} - ${n.name}`;
            selectEl.appendChild(opt);
        }
    });
    selectEl.value = current;
}

/** 更新所有标签页中的回调下拉选项 */
function updateAllCallbacks() {
    ['start', 'intermediate', 'list', 'next'].forEach(type => {
        const cbEl = document.getElementById(`${type}-callback`);
        if (cbEl) {
            updateCallbackOptions(cbEl, app.state.editingNodeId);
        }
    });
}

/** 从表单收集节点数据 */
function collectNodeData(type) {
    const data = {
        node_type: type,
        name: document.getElementById(`${type}-name`)?.value || `${NODE_TYPE_LABELS[type]}`,
        request_config: {
            url: document.getElementById(`${type}-url`)?.value || '',
            method: document.getElementById(`${type}-method`)?.value || 'GET',
            headers: parseJSONHeaders(document.getElementById(`${type}-headers`)?.value),
            // cookies removed
            body: document.getElementById(`${type}-body`)?.value || null,
        },
        parse_rules: {
            parser_type: 'xpath', // 默认值
            item_selector: document.getElementById(`${type}-item-selector`)?.value || null,
            item_selector_type: document.getElementById(`${type}-item-selector-type`)?.value || 'xpath',
            link_selector: document.getElementById(`${type}-link-selector`)?.value || null,
            link_selector_type: document.getElementById(`${type}-link-selector-type`)?.value || null,
            fields: [],
        },
        callback_node_id: document.getElementById(`${type}-callback`)?.value || null,
    };

    // 翻页配置
    const pgSelector = document.getElementById(`${type}-pg-selector`)?.value;
    if (pgSelector) {
        data.pagination = {
            selector: pgSelector,
            selector_type: document.getElementById(`${type}-pg-selector-type`)?.value || 'xpath',
            max_pages: parseInt(document.getElementById(`${type}-pg-max`)?.value) || 10,
        };
    }

    // 详情页字段
    if (type === 'detail') {
        data.parse_rules.fields = collectDetailFields();
        data.parse_rules.deduplication_type = document.getElementById('detail-dedup-type')?.value || 'none';
        data.parse_rules.deduplication_field = document.getElementById('detail-dedup-field')?.value || null;
    }

    return data;
}

/** 保存节点（创建或更新） */
async function saveNode(type) {
    if (!app.state.currentProjectId) {
        showToast('请先选择或创建项目', 'error');
        return;
    }

    const data = collectNodeData(type);
    if (!data.name.trim()) {
        showToast('请输入节点名称', 'error');
        return;
    }

    try {
        let nodeId = app.state.editingNodeId;

        if (nodeId && app.state.editingNodeType === type) {
            // 更新
            await api.updateNode(nodeId, data);
            showToast(`节点 "${data.name}" 已更新`, 'success');
        } else {
            // 创建
            const result = await api.createNode(app.state.currentProjectId, data);
            nodeId = result._id;
            app.state.editingNodeId = nodeId;
            app.state.editingNodeType = type;
            showToast(`节点 "${data.name}" 已创建`, 'success');

            // 如果是从父节点添加的，自动建立关联
            if (app.state.pendingParentId) {
                await api.setCallback(app.state.pendingParentId, nodeId);
                app.state.pendingParentId = null; // 清除状态
                showToast('已自动关联到父节点', 'success');
            }
        }
        await refreshNodes();
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

/** 清空表单开始新建 */
function newNode(type) {
    app.state.editingNodeId = null;
    app.state.editingNodeType = null;
    // 清空表单
    const form = document.getElementById(`tab-${type}`);
    if (form) {
        form.querySelectorAll('input, textarea').forEach(el => el.value = '');
        form.querySelectorAll('select').forEach(el => el.selectedIndex = 0);
    }
    if (type === 'detail') {
        renderDetailFields([]);
    }
    showToast('已切换到新建模式', 'info');
}

// ============ 详情页字段管理 ============

/** 渲染详情页字段列表 */
function renderDetailFields(fields) {
    const container = document.getElementById('detail-fields');
    container.innerHTML = '';
    if (!fields || fields.length === 0) {
        addDetailField();
        return;
    }
    fields.forEach(f => addDetailField(f));
}

/** 添加一个字段行 */
function addDetailField(fieldData = null) {
    const container = document.getElementById('detail-fields');
    const row = document.createElement('div');
    row.className = 'field-row';
    row.innerHTML = `
        <input class="form-input field-name" placeholder="字段名">
        <select class="form-select field-type">
            <option value="xpath">XPath</option>
            <option value="css">CSS</option>
            <option value="jsonpath">JsonPath</option>
            <option value="regex">Regex</option>
        </select>
        <input class="form-input field-selector" placeholder="选择器表达式">
        <button class="field-remove-btn" onclick="this.parentElement.remove()">✕</button>
    `;

    if (fieldData) {
        row.querySelector('.field-name').value = fieldData.name || '';
        row.querySelector('.field-type').value = fieldData.selector_type || 'xpath';
        row.querySelector('.field-selector').value = fieldData.selector || '';
    }

    container.appendChild(row);
}

/** 收集详情页字段 */
function collectDetailFields() {
    const fields = [];
    document.querySelectorAll('#detail-fields .field-row').forEach(row => {
        const name = row.querySelector('.field-name')?.value?.trim();
        const selector = row.querySelector('.field-selector')?.value?.trim();
        const selectorType = row.querySelector('.field-type')?.value;
        if (name && selector) {
            fields.push({ name, selector, selector_type: selectorType });
        }
    });
    return fields;
}

// ============ 节点类型模态框 ============

/** 显示添加子节点模态框 */
function showAddChildNode(parentNodeId) {
    app.state.pendingParentId = parentNodeId;
    document.getElementById('nodeTypeModal').style.display = 'flex';
}

/** 选择节点类型（从模态框） */
function selectNodeType(type) {
    closeNodeTypeModal();
    const tabMap = {
        'list': 'tab-list',
        'detail': 'tab-detail',
        'next': 'tab-next',
        'intermediate': 'tab-intermediate'
    };
    switchTab(tabMap[type]);
    newNode(type);
    showToast('请配置新节点', 'info');
}

/** 关闭模态框 */
function closeNodeTypeModal() {
    document.getElementById('nodeTypeModal').style.display = 'none';
    if (!app.state.editingNodeId) {
        // 如果没有正在编辑的节点（取消操作），可能需要清理 pendingParentId
        app.state.pendingParentId = null;
    }
}

// ============ 下一步操作区渲染 ============

/** 渲染下一步操作区 */
function renderNextStepSection(nodeType, callbackNodeId) {
    const container = document.getElementById(`${nodeType}-next-step`);
    if (!container) return;

    if (callbackNodeId) {
        const targetNode = app.state.nodes.find(n => n._id === callbackNodeId);
        const targetName = targetNode ? targetNode.name : '未知节点';
        const targetType = targetNode ? NODE_TYPE_LABELS[targetNode.node_type] : '';
        const targetBadgeClass = targetNode ? targetNode.node_type : '';

        container.innerHTML = `
            <div class="next-step-card">
                <span class="label">下一步骤：</span>
                <span class="value flow-node-badge ${targetBadgeClass}">${targetType}</span>
                <span style="font-size:13px;font-weight:500;margin-right:auto;margin-left:8px;">${targetName}</span>
                <div class="actions">
                    <button onclick="selectNodeById('${callbackNodeId}')">✏️ 编辑</button>
                    <button onclick="unlinkNode('${nodeType}')" class="text-danger">❌ 断开</button>
                </div>
            </div>
        `;
    } else {
        // 详情页没有下一步
        if (nodeType === 'detail') {
            container.innerHTML = `<div style="font-size:12px;color:var(--text-dim);text-align:center;">（终点节点）</div>`;
            return;
        }

        container.innerHTML = `
            <button class="btn btn-outline btn-block btn-dashed" onclick="showAddChildNode(app.state.editingNodeId)">
                ➕ 添加/选择 下一步骤
            </button>
        `;
    }
}

/** 通过 ID 选中节点 */
function selectNodeById(nodeId) {
    const node = app.state.nodes.find(n => n._id === nodeId);
    if (node) selectNode(node);
}

/** 断开节点关联 */
async function unlinkNode(nodeType) {
    if (!confirm('确定要断开与下一步骤的关联吗？')) return;
    try {
        await api.setCallback(app.state.editingNodeId, '');
        await refreshNodes();

        const updatedNode = app.state.nodes.find(n => n._id === app.state.editingNodeId);
        if (updatedNode) {
            loadNodeToForm(updatedNode);
            showToast('关联已断开', 'success');
        }
    } catch (e) {
        showToast('操作失败: ' + e.message, 'error');
    }
}

/** 切换去重字段输入框显示状态 */
function toggleDedupField() {
    const type = document.getElementById('detail-dedup-type')?.value;
    const group = document.getElementById('detail-dedup-field-group');
    if (group) {
        group.style.display = (type === 'field') ? 'block' : 'none';
    }
}

/** 解析 JSON Headers (支持宽松模式/Python字典) */
function parseJSONHeaders(text) {
    if (!text || !text.trim()) return {};

    // 1. 尝试标准 JSON
    try {
        return JSON.parse(text);
    } catch (e) {
        // 忽略标准错误，尝试宽松模式
    }

    // 2. 尝试宽松执行 (支持单引号, None, True, False, 尾随逗号)
    // 注意：使用 new Function 存在一定安全风险，但在开发者工具场景下通常可接受
    try {
        const fn = new Function('None', 'True', 'False', `return (${text});`);
        const result = fn(null, true, false);

        if (typeof result === 'object' && result !== null) {
            return result;
        }
    } catch (e2) {
        throw new Error("格式错误: 请提供有效的 JSON 或 Python 字典 ({'key': 'value'})");
    }

    throw new Error("格式错误: 结果必须是对象");
}
