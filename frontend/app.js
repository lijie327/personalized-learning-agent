// 教育平台前端应用
class EduPlatform {
    constructor() {
        this.currentSubject = 'python';
        // 持久化 session_id：整个页面生命周期内复用，使短期记忆生效
        this.sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
        // 前端科目名 → 后端科目名映射
        this.subjectMapping = {
            'python': 'python',
            'algorithm': 'data_structures',
            'math': 'math',
        };
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.knowledgeTree = document.getElementById('knowledgeTree');
        this.reviewList = document.getElementById('reviewList');
        this.codeModal = document.getElementById('codeModal');
        this.modalCode = document.getElementById('modalCode');
        this.codeOutput = document.getElementById('codeOutput');
        this.closeModal = document.getElementById('closeModal');
        this.quickSubjectSelect = document.getElementById('quickSubjectSelect');
        // 内联代码编辑器
        this.inlineCodeEditor = document.getElementById('inlineCodeEditor');
        this.codeEditorInput = document.getElementById('codeEditorInput');
        this.toggleCodeEditorBtn = document.getElementById('toggleCodeEditor');
        this.runCodeBtn = document.getElementById('runCodeBtn');
        this.clearCodeBtn = document.getElementById('clearCodeBtn');

        this.knowledgeData = {
            python: [
                { id: 'py-basic', name: '基础语法', icon: '📝', children: [
                    { id: 'py-var', name: '变量与类型', icon: '🔤' },
                    { id: 'py-op', name: '运算符', icon: '➕' },
                    { id: 'py-io', name: '输入输出', icon: '📥' }
                ]},
                { id: 'py-control', name: '流程控制', icon: '🔄', children: [
                    { id: 'py-if', name: '条件语句', icon: '❓' },
                    { id: 'py-loop', name: '循环语句', icon: '🔁' }
                ]},
                { id: 'py-func', name: '函数', icon: '📦', children: [
                    { id: 'py-def', name: '函数定义', icon: '🎯' },
                    { id: 'py-args', name: '参数传递', icon: '📋' },
                    { id: 'py-recursion', name: '递归', icon: '🔄', weak: true }
                ]},
                { id: 'py-data', name: '数据结构', icon: '📚', children: [
                    { id: 'py-list', name: '列表', icon: '📃' },
                    { id: 'py-dict', name: '字典', icon: '🗝️' },
                    { id: 'py-tuple', name: '元组', icon: '🔒' }
                ]}
            ],
            algorithm: [
                { id: 'alg-basic', name: '算法基础', icon: '🧮', children: [
                    { id: 'alg-complexity', name: '复杂度分析', icon: '📊' },
                    { id: 'alg-recursion', name: '递归思想', icon: '🔄' }
                ]},
                { id: 'alg-linear', name: '线性结构', icon: '📏', children: [
                    { id: 'alg-array', name: '数组', icon: '🔢' },
                    { id: 'alg-linked', name: '链表', icon: '🔗', weak: true },
                    { id: 'alg-stack', name: '栈', icon: '🥞' },
                    { id: 'alg-queue', name: '队列', icon: '🎫' }
                ]},
                { id: 'alg-tree', name: '树形结构', icon: '🌲', children: [
                    { id: 'alg-bst', name: '二叉树', icon: '🌳' },
                    { id: 'alg-heap', name: '堆', icon: '🔺' },
                    { id: 'alg-btree', name: 'B树', icon: '🌴' }
                ]},
                { id: 'alg-graph', name: '图算法', icon: '🕸️', children: [
                    { id: 'alg-dfs', name: '深度优先', icon: '🔍' },
                    { id: 'alg-bfs', name: '广度优先', icon: '🌊' }
                ]}
            ],
            math: [
                { id: 'math-calc', name: '微积分', icon: '📐', children: [
                    { id: 'math-limit', name: '极限', icon: '➡️' },
                    { id: 'math-derivative', name: '导数', icon: '📉', weak: true },
                    { id: 'math-integral', name: '积分', icon: '📈' }
                ]},
                { id: 'math-linear', name: '线性代数', icon: '🔲', children: [
                    { id: 'math-matrix', name: '矩阵', icon: '⬛' },
                    { id: 'math-vector', name: '向量', icon: '➡️' }
                ]},
                { id: 'math-prob', name: '概率统计', icon: '🎲', children: [
                    { id: 'math-prob-basic', name: '概率基础', icon: '🎯' },
                    { id: 'math-dist', name: '分布', icon: '📊' }
                ]}
            ]
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.renderKnowledgeTree();
        this.initKnowledgeGraph();
        this.loadInitialMessages();
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        document.querySelectorAll('.subject-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchSubject(e.currentTarget.dataset.subject);
            });
        });

        this.quickSubjectSelect.addEventListener('change', (e) => {
            this.switchSubject(e.target.value);
        });

        // 内联代码编辑器：切换显示/隐藏
        this.toggleCodeEditorBtn.addEventListener('click', () => {
            this.toggleCodeEditor();
        });

        // 代码编辑器中的运行按钮
        this.runCodeBtn.addEventListener('click', () => {
            this.runCodeFromEditor();
        });

        // 代码编辑器中的清空按钮
        this.clearCodeBtn.addEventListener('click', () => {
            this.codeEditorInput.value = '';
            this.codeEditorInput.focus();
        });

        // 代码编辑器中 Ctrl+Enter 快速运行
        this.codeEditorInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                this.runCodeFromEditor();
            }
        });

        document.getElementById('uploadImage').addEventListener('click', () => {
            this.handleImageUpload();
        });

        this.closeModal.addEventListener('click', () => {
            this.codeModal.classList.remove('active');
        });

        this.codeModal.addEventListener('click', (e) => {
            if (e.target === this.codeModal) {
                this.codeModal.classList.remove('active');
            }
        });

        // ===== 事件委托：统一处理聊天区所有动态按钮 =====
        this.chatMessages.addEventListener('click', (e) => {
            const target = e.target;
            console.log('[Chat Click]', target.tagName, target.className, target.dataset?.code ? '(has code)' : '');

            // ▶ 运行 按钮
            if (target.classList.contains('run-code-btn')) {
                console.log('[Run Code] clicked, fetching code from dataset...');
                const code = target.dataset.code;
                console.log('[Run Code] code length:', code ? code.length : 0);
                if (code) this.runCode(code, target);
                return;
            }

            // 📋 复制 按钮（聊天消息中的代码块 + 代码执行结果）
            if (target.classList.contains('copy-code-btn')) {
                console.log('[Copy Code] clicked');
                const code = target.dataset.code;
                if (code) {
                    navigator.clipboard.writeText(code).then(() => {
                        const origText = target.textContent;
                        target.textContent = '已复制 ✓';
                        setTimeout(() => { target.textContent = origText; }, 2000);
                    }).catch(() => {
                        target.textContent = '复制失败';
                        setTimeout(() => { target.textContent = '📋 复制'; }, 2000);
                    });
                }
                return;
            }

            // 🔄 重新运行 按钮（代码执行结果消息中）
            if (target.classList.contains('retry-code-btn')) {
                console.log('[Retry Code] clicked');
                const messageEl = target.closest('.message');
                const code = messageEl ? messageEl.dataset.code : '';
                console.log('[Retry Code] code length:', code ? code.length : 0);
                if (code) this.runCode(code, target);
                return;
            }
        });
    }

    loadInitialMessages() {
        this.addAIMessage({
            content: `你好！我是你的AI学习助手，有什么问题直接问我，我会为你详细解答！💡\n\n你可以问我：\n- Python基础语法\n- 数据结构与算法\n- 数学微积分\n\n试试看吧！`,
            mode: 'direct'
        });
    }

    switchSubject(subject) {
        this.currentSubject = subject;

        document.querySelectorAll('.subject-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.subject === subject);
        });

        this.quickSubjectSelect.value = subject;

        const subjectNames = {
            python: 'Python基础',
            algorithm: '数据结构',
            math: '数学'
        };
        document.querySelector('.current-subject').textContent = `当前: ${subjectNames[subject]}`;

        this.renderKnowledgeTree();
        this.initKnowledgeGraph();

        this.addAIMessage({
            content: `已切换到${subjectNames[subject]}课程，有什么问题尽管问！📚`,
            mode: 'direct'
        });
    }

    renderKnowledgeTree() {
        const data = this.knowledgeData[this.currentSubject] || [];
        this.knowledgeTree.innerHTML = '';

        data.forEach(node => {
            const li = this.createTreeNode(node);
            this.knowledgeTree.appendChild(li);
        });
    }

    createTreeNode(node) {
        const li = document.createElement('li');
        li.className = 'tree-item';

        const nodeEl = document.createElement('div');
        nodeEl.className = 'tree-node';

        const hasChildren = node.children && node.children.length > 0;

        nodeEl.innerHTML = `
            ${hasChildren ? '<span class="tree-toggle">▶</span>' : '<span style="width:20px"></span>'}
            <span class="tree-icon">${node.icon}</span>
            <span class="tree-label">${node.name}</span>
            ${node.weak ? '<span style="color:var(--weak-point);margin-left:4px;">⚠️</span>' : ''}
        `;

        li.appendChild(nodeEl);

        if (hasChildren) {
            const childrenUl = document.createElement('ul');
            childrenUl.className = 'tree-children';

            node.children.forEach(child => {
                childrenUl.appendChild(this.createTreeNode(child));
            });

            li.appendChild(childrenUl);

            const toggle = nodeEl.querySelector('.tree-toggle');
            if (toggle) {
                toggle.addEventListener('click', (e) => {
                    e.stopPropagation();
                    childrenUl.classList.toggle('expanded');
                    toggle.classList.toggle('expanded');
                    toggle.textContent = childrenUl.classList.contains('expanded') ? '▼' : '▶';
                });
            }
        }

        nodeEl.addEventListener('click', () => {
            document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active'));
            nodeEl.classList.add('active');
            this.onKnowledgeNodeClick(node);
        });

        return li;
    }

    onKnowledgeNodeClick(node) {
        this.messageInput.value = `请详细讲解${node.name}的概念和原理，并给出代码示例`;
        this.sendMessage();
    }

    sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content) return;

        this.addUserMessage(content);
        this.messageInput.value = '';

        this.streamAIResponse(content);
    }

    addUserMessage(content) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message user-message';
        messageEl.innerHTML = `
            <div class="avatar">👤</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">我</span>
                </div>
                <div class="message-body">
                    <p>${this.escapeHtml(content)}</p>
                </div>
                <div class="message-footer">
                    <span class="timestamp">刚刚</span>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }

    addAIMessage({ content, mode = 'direct', sources = [], code = false }) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message ai-message';

        const modeText = '直接教学';

        let processedContent = this.processMessageContent(content);

        let sourcesHtml = '';
        if (sources.length > 0) {
            sourcesHtml = `
                <div class="source-citation">
                    <div class="source-title">📚 知识来源</div>
                    <ul class="source-list">
                        ${sources.map(s => `<li>${this.escapeHtml(s)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        messageEl.innerHTML = `
            <div class="avatar">🤖</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">AI助教</span>
                    <span class="teaching-mode mode-direct">${modeText}</span>
                </div>
                <div class="message-body">
                    ${processedContent}
                </div>
                ${sourcesHtml}
                <div class="message-footer">
                    <span class="timestamp">刚刚</span>
                </div>
            </div>
        `;

        this.chatMessages.appendChild(messageEl);

        // 注意：按钮事件通过 chatMessages 上的事件委托统一处理
        // 不需要在此处单独绑定，避免流式消息中的按钮无效

        this.scrollToBottom();
    }

    processMessageContent(content) {
        // -- 将 Markdown 代码块转为与正文一致的纯文本格式 --
        //    不单独成块，不使用特殊背景色，保持和普通文字一样的视觉风格
        content = content.replace(/```\s*(\w+)?\s*\r?\n([\s\S]*?)```/g, (match, lang, code) => {
            const codeTrimmed = code.trim();
            const escapedCode = this.escapeHtml(codeTrimmed);
            // 用 <pre> 保留换行，但不加特殊样式类，与正文融为一体
            return `<pre class="inline-code">${escapedCode}</pre>`;
        });

        // 处理行内代码: `code`
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        // 处理粗体: **text**
        content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // 保护 pre 内部的 \n\n，防止段落分割时被切断
        content = content.replace(/(<pre[^>]*>)([\s\S]*?)(<\/pre>)/g, (m, open, code, close) => {
            return open + code.replace(/\n\n/g, '\n__P__') + close;
        });

        const paragraphs = content.split('\n\n').map(p => {
            // 还原被保护的 \n\n
            const restored = p.replace(/__P__/g, '\n');
            // pre 标签不在 p 内嵌套，直接原样输出（保持与普通文字相同的视觉层级）
            if (restored.trim().startsWith('<pre')) return restored;
            return `<p>${restored.replace(/\n/g, '<br>')}</p>`;
        });

        return paragraphs.join('');
    }

    // ========== 真实 API 流式响应 ==========
    async streamAIResponse(userMessage) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message ai-message streaming';
        const contentId = 'streaming-' + Date.now();
        messageEl.innerHTML = `
            <div class="avatar">🤖</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">AI助教</span>
                    <span class="teaching-mode mode-direct">思考中...</span>
                </div>
                <div class="message-body" id="${contentId}">
                    <span class="typing">思考中<span class="dots">...</span></span>
                </div>
                <div class="message-footer">
                    <span class="timestamp">刚刚</span>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();

        const contentEl = document.getElementById(contentId);
        const modeSpan = messageEl.querySelector('.teaching-mode');
        let fullContent = '';
        let allSources = [];

        try {
            const response = await fetch('/api/tutor', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: userMessage,
                    subject: this.subjectMapping[this.currentSubject] || this.currentSubject,
                    student_id: 'student_001',
                    session_id: this.sessionId,
                    mode: 'direct'
                })
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText || '请求失败');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'token' && data.token) {
                                fullContent += data.token;
                                contentEl.innerHTML = this.processMessageContent(fullContent);
                                this.scrollToBottom();
                            }

                            if (data.type === 'sources' && Array.isArray(data.sources)) {
                                allSources = allSources.concat(data.sources);
                            }

                            if (data.type === 'route' && data.agent) {
                                modeSpan.textContent = data.agent;
                            }

                            if (data.type === 'done') {
                                messageEl.classList.remove('streaming');
                                modeSpan.textContent = '直接教学';
                                // 显示 RAG 知识来源（如果有）
                                if (allSources.length > 0) {
                                    const sourcesHtml = `
                                        <div class="source-citation">
                                            <div class="source-title">📚 知识来源</div>
                                            <ul class="source-list">
                                                ${allSources.map(s => `<li>${this.escapeHtml((s.topic ? s.topic + '：' : '') + (s.content || ''))}</li>`).join('')}
                                            </ul>
                                        </div>`;
                                    contentEl.insertAdjacentHTML('beforeend', sourcesHtml);
                                }
                                // 显示代码验证警告（如果有）
                                if (messageEl._codeValidation) {
                                    const v = messageEl._codeValidation;
                                    let warningHtml = '<div class="code-validation-warning" style="margin-top:12px;padding:10px;background:#fff8e1;border-left:3px solid #ffa726;border-radius:4px;font-size:13px;">';
                                    warningHtml += '<div style="font-weight:600;color:#e65100;margin-bottom:6px;">⚠️ 代码完整性提示</div>';
                                    if (v.fixes.length > 0) {
                                        warningHtml += '<div style="color:#6d4c41;margin-bottom:4px;">🔧 已自动修复：</div>';
                                        warningHtml += '<ul style="margin:4px 0;padding-left:20px;">';
                                        v.fixes.forEach(f => { warningHtml += `<li>${this.escapeHtml(f)}</li>`; });
                                        warningHtml += '</ul>';
                                    }
                                    if (v.issues.length > 0) {
                                        warningHtml += '<div style="color:#6d4c41;margin-bottom:4px;">💡 建议检查：</div>';
                                        warningHtml += '<ul style="margin:4px 0;padding-left:20px;">';
                                        v.issues.forEach(issue => { warningHtml += `<li>${this.escapeHtml(issue)}</li>`; });
                                        warningHtml += '</ul>';
                                    }
                                    warningHtml += '<div style="color:#bf360c;font-size:12px;margin-top:4px;">请在运行代码前确认其完整性和正确性。</div>';
                                    warningHtml += '</div>';
                                    contentEl.insertAdjacentHTML('beforeend', warningHtml);
                                }
                            }

                            if (data.type === 'code_validation' && data.has_issues) {
                                // 代码验证发现问题，在消息底部添加提示
                                const issues = data.issues || [];
                                if (issues.length > 0) {
                                    const allIssues = issues.flatMap(i => i.issues || []);
                                    const allFixes = issues.flatMap(i => i.fixes_applied || []).filter(Boolean);
                                    // 保存验证信息，在 done 事件后显示
                                    messageEl._codeValidation = {
                                        issues: allIssues,
                                        fixes: allFixes,
                                        message: data.message || '',
                                    };
                                }
                            }

                            if (data.type === 'error') {
                                contentEl.innerHTML = `<p style="color:#ff6b6b;">${data.error}</p>`;
                                messageEl.classList.remove('streaming');
                            }
                        } catch (e) {}
                    }
                }
            }
        } catch (error) {
            contentEl.innerHTML = `<p style="color:#ff6b6b;">连接失败: ${error.message}</p>`;
            messageEl.classList.remove('streaming');
        }
    }

    async runCode(code, btnElement = null) {
        console.log('[runCode] called, code length:', code ? code.length : 0);
        // 在聊天中显示"正在运行..."的临时消息
        const runningMsg = this.addCodeRunningMessage(code);

        try {
            const response = await fetch('/api/execute-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language: 'python', timeout: 30 })
            });

            const result = await response.json();

            // 移除"运行中"的临时消息
            if (runningMsg) runningMsg.remove();

            // 以内联消息形式展示结果
            this.addCodeResultMessage(code, result);

            // 同时更新模态框（如果打开的话）
            this.modalCode.textContent = code;
            hljs.highlightElement(this.modalCode);
            if (result.success) {
                this.codeOutput.innerHTML = `<span style="color:#aed581">${this.escapeHtml(result.output || '(无输出)')}</span>`;
                if (result.execution_time) {
                    this.codeOutput.innerHTML += `\n\n<span style="color:#90a4ae"># 执行时间: ${result.execution_time}ms</span>`;
                }
            } else {
                this.codeOutput.innerHTML = `<span style="color:#ff6b6b">${this.escapeHtml(result.error || '未知错误')}</span>`;
            }
        } catch (error) {
            // 移除"运行中"的临时消息
            if (runningMsg) runningMsg.remove();
            // 以内联错误消息展示
            this.addCodeResultMessage(code, {
                success: false,
                error: `连接失败: ${error.message}`,
                output: '',
                execution_time: 0
            });
        }
    }

    addCodeRunningMessage(code) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message ai-message';
        messageEl.id = 'code-running-' + Date.now();

        const preview = code.length > 100 ? code.substring(0, 100) + '...' : code;

        messageEl.innerHTML = `
            <div class="avatar">⚡</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">代码执行器</span>
                </div>
                <div class="message-body code-result-body">
                    <div class="code-result-header running">
                        <span>⏳ 正在执行代码...</span>
                    </div>
                    <div class="code-preview">${this.escapeHtml(preview)}</div>
                </div>
                <div class="message-footer">
                    <span class="timestamp">刚刚</span>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
        return messageEl;
    }

    addCodeResultMessage(code, result) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message ai-message';

        const success = result.success;
        const output = result.output || '';
        const error = result.error || '';
        const execTime = result.execution_time;

        const statusIcon = success ? '✅' : '❌';
        const statusText = success ? '执行成功' : '执行失败';
        const statusClass = success ? 'success' : 'error';

        // 用 data 属性存储代码，方便重试
        messageEl.dataset.code = code;

        messageEl.innerHTML = `
            <div class="avatar">⚡</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">代码执行器</span>
                    <span class="teaching-mode ${success ? 'mode-direct' : 'mode-socratic'}">${statusIcon} ${statusText}</span>
                </div>
                <div class="message-body code-result-body">
                    <div class="code-result-header ${statusClass}">
                        <span>${statusIcon} ${statusText}</span>
                        ${execTime ? `<span class="exec-time">${execTime}ms</span>` : ''}
                    </div>
                    <div class="code-block">
                        <div class="code-header">
                            <span class="code-lang">📝 源代码</span>
                            <div class="code-actions">
                                <button class="code-btn copy-code-btn" data-code="${this.escapeAttr(code)}">📋 复制</button>
                                <button class="code-btn run-code-btn" data-code="${this.escapeAttr(code)}">▶ 运行</button>
                            </div>
                        </div>
                        <pre><code class="language-python">${this.escapeHtml(code)}</code></pre>
                    </div>
                    ${success ? `
                        <div class="code-output-section">
                            <div class="output-label">📤 输出结果</div>
                            <pre class="output-content success-output">${this.escapeHtml(output) || '(无输出)'}</pre>
                        </div>
                    ` : `
                        <div class="code-output-section">
                            <div class="output-label">⚠️ 错误信息</div>
                            <pre class="output-content error-output">${this.escapeHtml(error)}</pre>
                        </div>
                    `}
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageEl);

        // 代码高亮
        messageEl.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });

        this.scrollToBottom();
        return messageEl;
    }

    retryCodeRun(code) {
        this.runCode(code);
    }

    escapeAttr(text) {
        return text.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
    }

    submitExercise(btn) {
        const answer = prompt('请输入你的答案（代码或文字说明）：');
        if (answer === null) return;

        if (answer.trim()) {
            this.addUserMessage(`我的答案：\n${answer}`);
            setTimeout(() => {
                this.addAIMessage({
                    content: `收到你的答案！让我分析一下...\n\n💡 **反馈：**\n- ✅ 基础概念理解正确\n- ⚠️ 注意边界条件的处理\n- 🎯 可以尝试更简洁的实现方式\n\n需要我详细讲解一下吗？`,
                    mode: 'direct'
                });
                this.refreshLearningStats();
            }, 1000);
        }
    }

    // ========== 内联代码编辑器 ==========

    toggleCodeEditor() {
        const isVisible = this.inlineCodeEditor.style.display !== 'none';
        if (isVisible) {
            this.inlineCodeEditor.style.display = 'none';
            this.toggleCodeEditorBtn.classList.remove('active');
        } else {
            this.inlineCodeEditor.style.display = 'block';
            this.toggleCodeEditorBtn.classList.add('active');
            // 如果编辑器为空，填入模板代码
            if (!this.codeEditorInput.value.trim()) {
                this.codeEditorInput.value = `# 在这里编写 Python 代码\n# 点击 ▶ 运行 或按 Ctrl+Enter 立即执行\n\ndef greeting(name):\n    """打个招呼"""\n    return f"你好, {name}!"\n\nprint(greeting("世界"))\n`;
            }
            this.codeEditorInput.focus();
        }
    }

    runCodeFromEditor() {
        const code = this.codeEditorInput.value.trim();
        if (!code) {
            // 编辑器为空，提示用户
            this.codeEditorInput.focus();
            this.codeEditorInput.style.border = '1px solid #ff6b6b';
            setTimeout(() => { this.codeEditorInput.style.border = ''; }, 1500);
            return;
        }
        // 直接调用执行，结果内联显示在对话中
        this.runCode(code);
    }

    // 保留旧方法作为兼容（被知识点点击等处调用）
    insertCodeTemplate() {
        this.toggleCodeEditor();
    }

    handleImageUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // 在聊天中显示预览消息
            const reader = new FileReader();
            reader.onload = (ev) => {
                this.addUserMessageWithImage(
                    `[上传图片: ${file.name}]`,
                    ev.target.result
                );
            };
            reader.readAsDataURL(file);

            // 上传到后端
            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('student_id', 'student_001');

                const response = await fetch('/api/upload-image', {
                    method: 'POST',
                    body: formData,
                });

                const result = await response.json();

                if (result.success) {
                    // 构建回复消息
                    let replyContent = '';
                    if (result.analyzed_content) {
                        replyContent = `✅ 图片上传成功！已识别图片内容如下：\n\n---\n\n${result.analyzed_content}\n\n---\n\n💡 你可以继续提问关于图片内容的问题，我会结合分析结果为你解答。`;
                    } else {
                        const errorHint = result.content_error ? `\n（分析失败: ${result.content_error}）` : '';
                        replyContent = `✅ 图片上传成功！\n\n已收到你的图片 **${file.name}**（${(result.size / 1024).toFixed(1)} KB）。${errorHint}\n\n请告诉我你想问关于这张图片的什么问题？我会结合图片内容为你解答。`;
                    }

                    this.addAIMessage({
                        content: replyContent,
                        mode: 'direct'
                    });
                } else {
                    this.addAIMessage({
                        content: `❌ 图片上传失败，请重试。`,
                        mode: 'direct'
                    });
                }
            } catch (error) {
                this.addAIMessage({
                    content: `❌ 上传失败: ${error.message}`,
                    mode: 'direct'
                });
            }
        };
        input.click();
    }

    addUserMessageWithImage(content, imageDataUrl) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message user-message';
        messageEl.innerHTML = `
            <div class="avatar">👤</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">我</span>
                </div>
                <div class="message-body">
                    <p>${this.escapeHtml(content)}</p>
                    <img src="${imageDataUrl}" alt="上传图片"
                         style="max-width:200px;max-height:200px;border-radius:8px;margin-top:8px;border:1px solid #e0e7ef;" />
                </div>
                <div class="message-footer">
                    <span class="timestamp">刚刚</span>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }

    async initKnowledgeGraph() {
        const container = document.getElementById('knowledgeGraph');
        if (!container) return;

        container.innerHTML = '';

        // 从后端 API 获取真实知识图谱数据
        let graphData;
        try {
            const response = await fetch(`/api/student/student_001/knowledge-graph`);
            if (response.ok) {
                const data = await response.json();
                graphData = { nodes: data.nodes || [], links: data.links || [] };
            } else {
                graphData = this.generateKnowledgeGraphFallback();
            }
        } catch (e) {
            // API 不可用时回退到本地生成
            graphData = this.generateKnowledgeGraphFallback();
        }

        if (!graphData.nodes || graphData.nodes.length === 0) {
            container.innerHTML = '<div style="text-align:center;color:#999;padding-top:40px;">暂无知识图谱数据</div>';
            return;
        }

        const width = container.clientWidth;
        const height = container.clientHeight;

        const svg = d3.select('#knowledgeGraph')
            .append('svg')
            .attr('width', width)
            .attr('height', height);

        const simulation = d3.forceSimulation(graphData.nodes)
            .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(40))
            .force('charge', d3.forceManyBody().strength(-100))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(20));

        const links = svg.append('g')
            .selectAll('line')
            .data(graphData.links)
            .enter()
            .append('line')
            .attr('stroke', '#ccc')
            .attr('stroke-width', 1.5);

        const nodes = svg.append('g')
            .selectAll('circle')
            .data(graphData.nodes)
            .enter()
            .append('circle')
            .attr('r', d => d.size || 8)
            .attr('fill', d => d.weak ? '#ff6b6b' : d.mastered ? '#81c784' : d.unstudied ? '#cfd8dc' : '#ffd54f')
            .attr('stroke', '#fff')
            .attr('stroke-width', d => d.unstudied ? 1 : 2)
            .attr('opacity', d => d.unstudied ? 0.5 : 1.0)
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }));

        const labels = svg.append('g')
            .selectAll('text')
            .data(graphData.nodes)
            .enter()
            .append('text')
            .text(d => d.label)
            .attr('font-size', '10px')
            .attr('fill', '#546e7a')
            .attr('text-anchor', 'middle')
            .attr('dy', -12);

        simulation.on('tick', () => {
            links
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            nodes
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);

            labels
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });

        nodes.append('title')
            .text(d => {
                if (d.unstudied) return `${d.label} - 未学习`;
                return `${d.label} - 掌握度: ${Math.round((d.mastery || 0) * 100)}% (${d.weak ? '薄弱' : d.mastered ? '已掌握' : '学习中'})`;
            });
    }

    generateKnowledgeGraphFallback() {
        // API 不可用时的本地回退数据
        const subjects = {
            python: ['变量', '循环', '函数', '列表', '字典', '类', '文件', '异常'],
            algorithm: ['数组', '链表', '栈', '队列', '树', '图', '排序', '查找'],
            math: ['极限', '导数', '积分', '矩阵', '向量', '概率', '分布', '统计']
        };

        const currentTopics = subjects[this.currentSubject] || subjects.python;

        const nodes = currentTopics.map((topic, i) => ({
            id: this.currentSubject + '_' + i,
            label: topic,
            mastered: false,
            weak: false,
            learning: true,
            size: 8,
        }));

        const links = [];
        for (let i = 0; i < nodes.length - 1; i++) {
            links.push({ source: nodes[i].id, target: nodes[i + 1].id, weight: 0.3 });
        }

        return { nodes, links };
    }

    refreshLearningStats() {
        document.querySelectorAll('.progress-fill').forEach(bar => {
            const currentWidth = parseInt(bar.style.width) || 0;
            const newWidth = Math.min(currentWidth + Math.floor(Math.random() * 5), 100);
            bar.style.width = newWidth + '%';
            bar.nextElementSibling.textContent = newWidth + '%';
        });

        document.querySelectorAll('.stat-value').forEach(stat => {
            const current = parseInt(stat.textContent);
            stat.textContent = current + Math.floor(Math.random() * 2) + 1;
        });

        setTimeout(() => this.initKnowledgeGraph(), 500);
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const eduPlatform = new EduPlatform();