/**
 * RuleCrawl 节点流程图可视化
 */

/** 渲染左侧流程面板中的节点链 */
function renderFlowPanel(nodes) {
    const panel = document.getElementById('flowPanel');
    panel.innerHTML = '';

    if (!nodes || nodes.length === 0) {
        panel.innerHTML = `<div class="empty-state"><div class="icon">🕸️</div><p>暂无节点，请在右侧标签页中添加</p></div>`;
        return;
    }

    nodes.forEach((node, index) => {
        // 节点卡片
        const el = document.createElement('div');
        el.className = `flow-node${app.state.activeNodeId === node._id ? ' active' : ''}`;
        el.onclick = () => selectNode(node);

        const callbackName = node.callback_node_id
            ? (nodes.find(n => n._id === node.callback_node_id)?.name || '未知')
            : '';

        el.innerHTML = `
            <div class="flow-node-header">
                <span class="flow-node-badge ${node.node_type}">${NODE_TYPE_LABELS[node.node_type]}</span>
                <span class="flow-node-name">${node.name}</span>
                <div style="margin-left:auto;display:flex;gap:4px;">
                    ${(!node.callback_node_id && node.node_type !== 'detail')
                ? `<button class="flow-node-add" onclick="event.stopPropagation(); showAddChildNode('${node._id}')" title="添加后续节点">➕</button>`
                : ''}
                    <button class="flow-node-delete" onclick="event.stopPropagation(); deleteNodeFlow('${node._id}', '${node.name}')" title="删除">✕</button>
                </div>
            </div>
            ${callbackName ? `<div style="font-size:11px;color:var(--text-dim);margin-top:4px;">→ ${callbackName}</div>` : ''}
        `;
        panel.appendChild(el);

        // 箭头（不在最后一个节点后显示）
        if (index < nodes.length - 1) {
            const arrow = document.createElement('div');
            arrow.className = 'flow-arrow';
            arrow.textContent = '↓';
            panel.appendChild(arrow);
        }
    });

    // 如果还没有 start 节点，显示添加 Start 按钮
    if (nodes.length === 0) {
        const addBtn = document.createElement('button');
        addBtn.className = 'flow-add-btn';
        addBtn.textContent = '🚀 初始化起始页';
        addBtn.onclick = () => {
            switchTab('tab-start');
            newNode('start');
        };
        panel.appendChild(addBtn);
    }
}

/** 选中节点 → 跳转到对应标签页并加载数据 */
function selectNode(node) {
    app.state.activeNodeId = node._id;
    // 切换到对应标签页
    const tabMap = {
        start: 'tab-start',
        intermediate: 'tab-intermediate',
        list: 'tab-list',
        next: 'tab-next',
        detail: 'tab-detail',
    };
    const tabId = tabMap[node.node_type];
    if (tabId) {
        switchTab(tabId);
        loadNodeToForm(node);
    }
    renderFlowPanel(app.state.nodes);
}

/** 删除节点 */
async function deleteNodeFlow(nodeId, nodeName) {
    if (!confirm(`确定要删除节点 "${nodeName}" 吗？`)) return;
    try {
        await api.deleteNode(nodeId);
        showToast(`节点 "${nodeName}" 已删除`, 'success');
        await refreshNodes();
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

/** 从流程面板添加节点 */
function showAddNodeFromFlow() {
    // 切换到起始页标签（如果还没有 start 节点）
    const hasStart = app.state.nodes.some(n => n.node_type === 'start');
    if (!hasStart) {
        switchTab('tab-start');
    } else {
        switchTab('tab-list');
    }
    showToast('请在右侧标签页中配置并保存节点', 'info');
}
