/**
 * BimBam Buy AI PDF Reader - Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Element References
    const documentList = document.getElementById('documentList');
    const docCountBadge = document.getElementById('docCountBadge');
    const activeSourcesCountLabel = document.getElementById('activeSourcesCountLabel');
    const selectAllSourcesBtn = document.getElementById('selectAllSourcesBtn');

    const dropZone = document.getElementById('dropZone');
    const pdfFileInput = document.getElementById('pdfFileInput');
    const uploadLoader = document.getElementById('uploadLoader');

    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const userQuery = document.getElementById('userQuery');
    const sendBtn = document.getElementById('sendBtn');

    // State Variables
    let documents = [];
    let activeSourceNames = new Set();
    let chatHistory = [];
    let isAllSelected = true;

    // --- 1. INITIALIZATION & STATUS CHECK ---
    async function checkStatus() {
        try {
            await fetchDocuments();
        } catch (err) {
            console.error('Error al conectar con backend:', err);
        }
    }

    // --- 2. DOCUMENT MANAGEMENT & SIDEBAR ---
    async function fetchDocuments() {
        try {
            const res = await fetch('/api/documents');
            const data = await res.json();

            if (data.success) {
                documents = data.documents;
                
                // Por defecto, seleccionar todas las fuentes al cargar si es primera vez
                if (activeSourceNames.size === 0 && documents.length > 0) {
                    documents.forEach(doc => activeSourceNames.add(doc.source));
                }

                renderDocuments();
            }
        } catch (err) {
            console.error('Error al cargar documentos:', err);
        }
    }

    function renderDocuments() {
        docCountBadge.textContent = documents.length;

        if (documents.length === 0) {
            documentList.innerHTML = `
                <div class="empty-docs">
                    <i class="fa-solid fa-folder-open" style="font-size: 1.8rem; margin-bottom: 8px;"></i>
                    <p>No hay fuentes disponibles.<br>Sube un archivo PDF para comenzar.</p>
                </div>
            `;
            updateActiveSourcesLabel();
            return;
        }

        documentList.innerHTML = '';
        documents.forEach(doc => {
            const isChecked = activeSourceNames.has(doc.source);
            const card = document.createElement('div');
            card.className = `doc-card ${isChecked ? 'active' : ''}`;

            card.innerHTML = `
                <input 
                    type="checkbox" 
                    class="doc-checkbox" 
                    data-source="${doc.source}" 
                    ${isChecked ? 'checked' : ''}
                >
                <i class="fa-solid fa-file-pdf doc-icon"></i>
                <div class="doc-info">
                    <div class="doc-name" title="${doc.source}">${doc.source}</div>
                    <div class="doc-meta">
                        <span>${doc.total_pages} pág.</span> • 
                        <span>${doc.total_chunks} fragmentos</span>
                        <span class="doc-tag ${doc.is_preset ? 'preset' : 'custom'}">
                            ${doc.is_preset ? 'BimBam Buy' : 'Usuario'}
                        </span>
                    </div>
                </div>
            `;

            // Checkbox event
            const checkbox = card.querySelector('.doc-checkbox');
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation();
                if (checkbox.checked) {
                    activeSourceNames.add(doc.source);
                    card.classList.add('active');
                } else {
                    activeSourceNames.delete(doc.source);
                    card.classList.remove('active');
                }
                updateActiveSourcesLabel();
            });

            // Card click toggle
            card.addEventListener('click', (e) => {
                if (e.target.tagName !== 'INPUT') {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            });

            documentList.appendChild(card);
        });

        updateActiveSourcesLabel();
    }

    function updateActiveSourcesLabel() {
        const count = activeSourceNames.size;
        activeSourcesCountLabel.textContent = `${count} de ${documents.length} políticas activas`;
    }

    // Select/Deselect All Sources
    selectAllSourcesBtn.addEventListener('click', () => {
        if (isAllSelected) {
            activeSourceNames.clear();
            isAllSelected = false;
            selectAllSourcesBtn.textContent = 'Seleccionar Todos';
        } else {
            documents.forEach(doc => activeSourceNames.add(doc.source));
            isAllSelected = true;
            selectAllSourcesBtn.textContent = 'Deseleccionar Todos';
        }
        renderDocuments();
    });

    // --- 3. FILE UPLOAD (DRAG & DROP) ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'));
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'));
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) handleFileUpload(files[0]);
    });

    pdfFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (!file.name.lower().endsWith('.pdf')) {
            alert('Por favor selecciona únicamente archivos con extensión .pdf');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadLoader.classList.remove('hidden');

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (data.success) {
                activeSourceNames.add(data.document.source);
                await fetchDocuments();
            } else {
                alert(data.error || 'Error al subir el archivo');
            }
        } catch (err) {
            console.error('Error uploading PDF:', err);
            alert('Fallo de conexión al subir el PDF.');
        } finally {
            uploadLoader.classList.add('hidden');
            pdfFileInput.value = '';
        }
    }

    // --- 4. CHAT FUNCTIONALITY & RAG INTERACTION ---
    
    // Auto-expand textarea
    userQuery.addEventListener('input', () => {
        userQuery.style.height = 'auto';
        userQuery.style.height = (userQuery.scrollHeight) + 'px';
    });

    // Submit via Enter (without Shift)
    userQuery.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Handle Quick Prompts Click
    document.addEventListener('click', (e) => {
        const chip = e.target.closest('.prompt-chip');
        if (chip) {
            const promptText = chip.getAttribute('data-prompt');
            userQuery.value = promptText;
            userQuery.style.height = 'auto';
            userQuery.style.height = (userQuery.scrollHeight) + 'px';
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = userQuery.value.strip ? userQuery.value.strip() : userQuery.value.trim();
        if (!query) return;

        // Ocultar card de bienvenida al enviar primer mensaje
        const welcomeCard = document.querySelector('.welcome-card');
        if (welcomeCard) welcomeCard.remove();

        // Render User Message
        appendMessage('user', query);
        userQuery.value = '';
        userQuery.style.height = 'auto';

        // Add Bot Thinking Indicator
        const thinkingId = appendThinkingIndicator();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: query,
                    active_sources: Array.from(activeSourceNames),
                    history: chatHistory
                })
            });

            const data = await res.json();
            removeThinkingIndicator(thinkingId);

            if (data.success) {
                appendMessage('bot', data.answer, data.sources);
                chatHistory.push({ role: 'user', content: query });
                chatHistory.push({ role: 'assistant', content: data.answer });
            } else {
                appendMessage('bot', `⚠️ ${data.error || 'Ocurrió un error al procesar la respuesta.'}`);
            }
        } catch (err) {
            console.error('Error en consulta chat:', err);
            removeThinkingIndicator(thinkingId);
            appendMessage('bot', '❌ Error de comunicación con el servidor de la IA.');
        }
    });

    function appendMessage(role, text, sources = []) {
        const row = document.createElement('div');
        row.className = `message-row ${role}`;

        const avatarIcon = role === 'user' ? 'fa-user' : 'fa-robot';
        
        let formattedText = formatMarkdown(text);

        let citationsHtml = '';
        if (sources && sources.length > 0) {
            citationsHtml = `
                <div class="citation-container">
                    <div class="citation-header">
                        <i class="fa-solid fa-bookmark"></i> Políticas Oficiales Consultadas:
                    </div>
                    <div class="citation-list">
                        ${sources.map(s => `
                            <div class="citation-badge" title="${escapeHtml(s.snippet)}">
                                <i class="fa-solid fa-shield-check"></i>
                                <span>${escapeHtml(s.source)} (Pág. ${s.page})</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        row.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid ${avatarIcon}"></i>
            </div>
            <div class="message-content">
                <div>${formattedText}</div>
                ${citationsHtml}
            </div>
        `;

        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendThinkingIndicator() {
        const id = 'thinking-' + Date.now();
        const row = document.createElement('div');
        row.className = 'message-row bot';
        row.id = id;
        row.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid fa-headset"></i>
            </div>
            <div class="message-content">
                <p><i class="fa-solid fa-circle-notch fa-spin"></i> Consultando las políticas oficiales de BimBam Buy...</p>
            </div>
        `;
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function removeThinkingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Basic Markdown Formatter for Assistant Responses
    function formatMarkdown(str) {
        if (!str) return '';
        let html = str;

        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Bullet list lines
        html = html.replace(/^[•\-\*]\s+(.*)$/gmd, '<ul><li>$1</li></ul>');
        // Line breaks
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        return `<p>${html}</p>`;
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initial load
    checkStatus();
});
