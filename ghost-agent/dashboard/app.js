document.addEventListener('DOMContentLoaded', () => {
    const logsGrid = document.getElementById('logs-grid');
    const loadingState = document.getElementById('loading');
    const errorState = document.getElementById('error-state');
    const emptyState = document.getElementById('empty-state');
    const totalActionsEl = document.getElementById('total-actions').querySelector('.stat-value');
    const refreshBtn = document.getElementById('refresh-btn');
    
    // Modal elements
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    const modalClose = document.getElementById('modal-close');
    const modalBackdrop = document.querySelector('.modal-backdrop');

    // Fetch and render logs
    async function fetchLogs() {
        try {
            loadingState.classList.remove('hidden');
            logsGrid.classList.add('hidden');
            errorState.classList.add('hidden');
            emptyState.classList.add('hidden');

            const response = await fetch('/api/logs');
            if (!response.ok) throw new Error('Network response was not ok');
            
            const logs = await response.json();
            
            loadingState.classList.add('hidden');
            
            totalActionsEl.textContent = logs.length;
            
            if (logs.length === 0) {
                emptyState.classList.remove('hidden');
                return;
            }

            renderLogs(logs);
            logsGrid.classList.remove('hidden');

        } catch (error) {
            console.error('Error fetching logs:', error);
            loadingState.classList.add('hidden');
            errorState.classList.remove('hidden');
        }
    }

    function renderLogs(logs) {
        logsGrid.innerHTML = ''; // Clear existing
        
        logs.forEach(log => {
            const card = document.createElement('div');
            card.className = 'log-card';
            
            const date = new Date(log.timestamp);
            const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            
            const statusClass = log.success ? 'success' : 'error';
            
            let visualHTML = '';
            if (log.screenshot) {
                visualHTML = `<img src="/screenshots/${log.screenshot}" alt="Page Screenshot" class="screenshot-img" loading="lazy">`;
            } else {
                visualHTML = `
                    <div class="no-image">
                        <svg viewBox="0 0 24 24" width="32" height="32" stroke="currentColor" stroke-width="1.5" fill="none">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            <circle cx="8.5" cy="8.5" r="1.5"/>
                            <polyline points="21 15 16 10 5 21"/>
                        </svg>
                        <span>No visual context</span>
                    </div>
                `;
            }

            let contentHTML = `
                <div class="log-header">
                    <div class="log-action">
                        <div class="status-dot ${statusClass}"></div>
                        <span class="action-name">${escapeHtml(log.action)}</span>
                    </div>
                    <span class="log-time">${timeString}</span>
                </div>
            `;

            if (log.error) {
                contentHTML += `
                    <div class="data-section">
                        <span class="section-label">Error</span>
                        <div class="code-block error">${escapeHtml(log.error)}</div>
                    </div>
                `;
            }

            if (log.extracted_text) {
                contentHTML += `
                    <div class="data-section">
                        <span class="section-label">Extracted Text (What Ghost saw)</span>
                        <div class="code-block">${escapeHtml(log.extracted_text)}</div>
                    </div>
                `;
            }

            if (log.generated_response) {
                contentHTML += `
                    <div class="data-section">
                        <span class="section-label">AI Generation (What Ghost did)</span>
                        <div class="code-block highlight">${escapeHtml(log.generated_response)}</div>
                    </div>
                `;
            }

            if (log.extra) {
                const extraString = typeof log.extra === 'object' ? JSON.stringify(log.extra, null, 2) : log.extra;
                contentHTML += `
                    <div class="data-section">
                        <span class="section-label">Extra Context</span>
                        <div class="code-block">${escapeHtml(extraString)}</div>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="log-visual">
                    ${visualHTML}
                </div>
                <div class="log-content">
                    ${contentHTML}
                </div>
            `;
            
            // Add click listener for images
            const img = card.querySelector('.screenshot-img');
            if (img) {
                img.addEventListener('click', () => openModal(img.src));
            }

            logsGrid.appendChild(card);
        });
    }

    // Modal Logic
    function openModal(src) {
        modalImg.src = src;
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden'; // Prevent scrolling under modal
    }

    function closeModal() {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
        setTimeout(() => { modalImg.src = ''; }, 200);
    }

    modalClose.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', closeModal);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });

    refreshBtn.addEventListener('click', () => {
        const icon = refreshBtn.querySelector('svg');
        icon.style.animation = 'spin 1s linear infinite';
        fetchLogs().finally(() => {
            setTimeout(() => { icon.style.animation = ''; }, 500);
        });
    });

    // Utility
    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
             .toString()
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    // Initial load
    fetchLogs();
    
    // Auto-refresh every 15 seconds
    setInterval(fetchLogs, 15000);
});
