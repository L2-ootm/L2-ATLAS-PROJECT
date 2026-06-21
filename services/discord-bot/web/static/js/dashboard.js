// ═══════════════════════════════════════════════════════════════
// L2 BOT DASHBOARD — v1.1
// ═══════════════════════════════════════════════════════════════

// ── PANEL ROUTER (NAV-01) ───────────────────────────────────────

window.activeGuild = null;

function navigateTo(panelId) {
    // Deactivate all panels
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    // Activate target panel
    const target = document.getElementById(panelId);
    if (target) target.classList.add('active');
    // Update nav item active states
    document.querySelectorAll('.nav-item[data-panel]').forEach(n => {
        const isActive = n.dataset.panel === panelId;
        n.classList.toggle('active', isActive);
        n.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
    // Persist selection
    sessionStorage.setItem('l2_active_panel', panelId);
}

function initPanelRouter() {
    document.querySelectorAll('.nav-item[data-panel]').forEach(item => {
        item.addEventListener('click', () => navigateTo(item.dataset.panel));
        // Keyboard accessibility
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                navigateTo(item.dataset.panel);
            }
        });
    });
    // Restore last visited panel (or default to overview)
    const saved = sessionStorage.getItem('l2_active_panel') || 'panel-overview';
    navigateTo(saved);
}

// ── GUILD SWITCHER (NAV-02) ─────────────────────────────────────

async function loadGuilds() {
    try {
        const res = await fetch('/api/guilds');
        if (!res.ok) {
            console.warn('Failed to fetch guilds:', res.status);
            updateGuildDisplay({ name: 'No server', icon: null });
            return;
        }
        const guilds = await res.json();
        if (!Array.isArray(guilds) || guilds.length === 0) {
            updateGuildDisplay({ name: 'No servers', icon: null });
            return;
        }
        // Auto-select the first guild
        selectGuild(guilds[0]);
        // Populate dropdown
        renderGuildDropdown(guilds);
    } catch (e) {
        console.error('Guild load error:', e);
        updateGuildDisplay({ name: 'Error', icon: null });
    }
}

function selectGuild(guild) {
    window.activeGuild = guild;
    updateGuildDisplay(guild);

    // Mark active in dropdown
    document.querySelectorAll('.guild-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.guildId === String(guild.id));
    });

    // Close dropdown
    const switcher = document.getElementById('guild-switcher');
    if (switcher) switcher.classList.remove('open');

    // Sync the embed form's guild-select if the Manual Controls panel has it loaded
    const guildSelect = document.getElementById('guild-select');
    if (guildSelect) {
        // Check if the option exists before setting value
        const existingOption = guildSelect.querySelector(`option[value="${guild.id}"]`);
        if (existingOption) {
            guildSelect.value = guild.id;
            guildSelect.dispatchEvent(new Event('change'));
        }
    }

    // Fire custom event so Phase 5+ components can react
    document.dispatchEvent(new CustomEvent('guildChanged', { detail: guild }));
}

function updateGuildDisplay(guild) {
    const nameEl = document.getElementById('guild-name');
    const iconEl = document.getElementById('guild-icon');

    if (nameEl) nameEl.textContent = guild.name || 'Unknown';

    if (iconEl && guild.icon) {
        // Replace placeholder div with img element
        const img = document.createElement('img');
        img.className = 'guild-icon';
        img.src = `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png?size=64`;
        img.alt = guild.name || 'Server icon';
        img.onerror = () => {
            // Fallback to placeholder if image fails to load
            const placeholder = document.createElement('div');
            placeholder.className = 'guild-icon-placeholder';
            placeholder.id = 'guild-icon';
            placeholder.textContent = (guild.name || '?')[0].toUpperCase();
            img.replaceWith(placeholder);
        };
        iconEl.replaceWith(img);
    } else if (iconEl) {
        iconEl.textContent = (guild.name || '?')[0].toUpperCase();
    }
}

function renderGuildDropdown(guilds) {
    const dropdown = document.getElementById('guild-dropdown');
    if (!dropdown) return;

    dropdown.innerHTML = guilds.map(g => {
        const iconHtml = g.icon
            ? `<img class="guild-icon" src="https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=32" alt="${g.name}">`
            : `<div class="guild-icon-placeholder" style="font-size:0.65rem">${(g.name || '?')[0].toUpperCase()}</div>`;
        return `
            <div class="guild-option" data-guild-id="${g.id}" role="option" tabindex="0" aria-label="${g.name}">
                ${iconHtml}
                <span>${g.name}</span>
            </div>`;
    }).join('');

    dropdown.querySelectorAll('.guild-option').forEach(opt => {
        opt.addEventListener('click', () => {
            const guild = guilds.find(g => String(g.id) === opt.dataset.guildId);
            if (guild) selectGuild(guild);
        });
        opt.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                opt.click();
            }
        });
    });
}

function initGuildSwitcher() {
    const btn = document.getElementById('guild-switcher-btn');
    const switcher = document.getElementById('guild-switcher');
    if (!btn || !switcher) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        switcher.classList.toggle('open');
    });

    // Close dropdown when clicking anywhere outside
    document.addEventListener('click', (e) => {
        if (!switcher.contains(e.target)) {
            switcher.classList.remove('open');
        }
    });

    // Keyboard: Escape closes dropdown
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') switcher.classList.remove('open');
    });
}

// ── OVERVIEW STATS ───────────────────────────────────────────────

async function loadOverviewStats(guild) {
    if (!guild) return;
    try {
        const res = await fetch(`/api/guilds/${guild.id}/channels`);
        if (!res.ok) return;
        const categories = await res.json();

        let channelCount = 0;
        categories.forEach(cat => { channelCount += (cat.channels || []).length; });

        const channelEl = document.getElementById('stat-channels');
        if (channelEl) channelEl.textContent = channelCount;
    } catch (e) {
        console.warn('Could not load overview stats:', e);
    }
}

// Update stats when guild changes
document.addEventListener('guildChanged', (e) => {
    loadOverviewStats(e.detail);
});

// ── EMBED CONSTRUCTOR (v1.0 — preserved) ────────────────────────

async function fetchGuilds() {
    const guildSelect = document.getElementById('guild-select');
    if (!guildSelect) return;
    try {
        const response = await fetch('/api/guilds');
        if (!response.ok) throw new Error('Failed to fetch servers.');
        const guilds = await response.json();

        guildSelect.innerHTML = '<option value="">Select a server</option>';
        guilds.forEach(guild => {
            const option = document.createElement('option');
            option.value = guild.id;
            option.textContent = guild.name;
            guildSelect.appendChild(option);
        });

        // Sync with active guild from sidebar switcher
        if (window.activeGuild) {
            const match = guildSelect.querySelector(`option[value="${window.activeGuild.id}"]`);
            if (match) {
                guildSelect.value = window.activeGuild.id;
                fetchChannels(window.activeGuild.id);
            }
        }
    } catch (error) {
        if (guildSelect) guildSelect.innerHTML = `<option value="">${error.message}</option>`;
    }
}

async function fetchChannels(guildId) {
    const channelSelect = document.getElementById('channel-select');
    if (!channelSelect) return;

    channelSelect.innerHTML = '<option value="">Loading channels...</option>';
    channelSelect.disabled = true;

    if (!guildId) {
        channelSelect.innerHTML = '<option value="">Select a server first</option>';
        return;
    }
    try {
        const response = await fetch(`/api/guilds/${guildId}/channels`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch channels.');
        }
        const categories = await response.json();

        channelSelect.innerHTML = '<option value="">Select a channel</option>';
        categories.forEach(category => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = category.category_name;
            category.channels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.id;
                option.textContent = `#${channel.name}`;
                optgroup.appendChild(option);
            });
            channelSelect.appendChild(optgroup);
        });
        channelSelect.disabled = false;
    } catch (error) {
        channelSelect.innerHTML = `<option value="">Error loading channels</option>`;
        showNotification(error.message, 'error');
    }
}

function updatePreview() {
    const previewTitle       = document.getElementById('preview-title');
    const previewDescription = document.getElementById('preview-description');
    const previewFooter      = document.getElementById('preview-footer');
    const embedPreview       = document.getElementById('embed-preview');
    if (!previewTitle) return;

    const title       = document.getElementById('embed-title')?.value || '';
    const description = document.getElementById('embed-description')?.value || '';
    const footer      = document.getElementById('embed-footer')?.value || '';
    const color       = document.getElementById('embed-color')?.value || '#4f545c';

    previewTitle.textContent = title || 'Embed Title';

    if (description) {
        if (typeof marked !== 'undefined' && marked.parse) {
            try {
                previewDescription.innerHTML = marked.parse(description);
            } catch (e) {
                previewDescription.textContent = description;
            }
        } else {
            previewDescription.textContent = description;
        }
    } else {
        previewDescription.innerHTML = 'This is where the description will go. You can use <b>markdown</b> here!';
    }

    previewFooter.textContent = footer || 'Footer text';
    if (embedPreview) embedPreview.style.borderColor = color;
}

// ── TEMPLATE MANAGER (v1.0 — preserved) ─────────────────────────

function loadTemplates() {
    const templateSelect = document.getElementById('template-select');
    if (!templateSelect) return;

    const templates = JSON.parse(localStorage.getItem('discord_embed_templates') || '{}');
    templateSelect.innerHTML = '<option value="">Select a template...</option>';
    Object.keys(templates).forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        templateSelect.appendChild(option);
    });
}

function saveTemplate() {
    const name = prompt('Enter a name for this template:');
    if (!name) return;

    const templateData = {
        title:       document.getElementById('embed-title')?.value || '',
        description: document.getElementById('embed-description')?.value || '',
        color:       document.getElementById('embed-color')?.value || '#4f545c',
        footer:      document.getElementById('embed-footer')?.value || ''
    };

    const templates = JSON.parse(localStorage.getItem('discord_embed_templates') || '{}');
    templates[name] = templateData;
    localStorage.setItem('discord_embed_templates', JSON.stringify(templates));

    showNotification(`Template "${name}" saved!`, 'success');
    loadTemplates();
    const templateSelect = document.getElementById('template-select');
    if (templateSelect) templateSelect.value = name;
}

function applyTemplate(name) {
    if (!name) return;
    const templates = JSON.parse(localStorage.getItem('discord_embed_templates') || '{}');
    const data = templates[name];
    if (data) {
        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        setVal('embed-title', data.title);
        setVal('embed-description', data.description);
        setVal('embed-color', data.color || '#4f545c');
        setVal('embed-footer', data.footer);
        updatePreview();
        showNotification(`Template "${name}" loaded.`, 'success');
    }
}

function clearForm() {
    if (!confirm('Are you sure you want to clear the form?')) return;
    ['embed-title', 'embed-description', 'embed-footer'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const colorEl = document.getElementById('embed-color');
    if (colorEl) colorEl.value = '#4f545c';
    const templateSelect = document.getElementById('template-select');
    if (templateSelect) templateSelect.value = '';
    updatePreview();
    showNotification('Form cleared.', 'success');
}

// ── NOTIFICATION TOAST (v1.0 — preserved) ───────────────────────

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    if (!notification) return;
    notification.textContent = message;
    notification.className = `notification show ${type}`;
    setTimeout(() => { notification.className = 'notification'; }, 3000);
}

// ── SYSTEM LOG STREAM (v1.0 — preserved) ────────────────────────

function initLogStream() {
    const logsContainer = document.getElementById('logs-container');
    if (!logsContainer) return;

    const eventSource = new EventSource('/api/logs/stream');

    eventSource.onmessage = (event) => {
        try {
            const log = JSON.parse(event.data);
            appendLogEntry(log);
        } catch (err) {
            console.error('Failed to parse log data:', err);
        }
    };

    eventSource.onerror = () => {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'log-entry system-error';
        errorDiv.innerHTML = `<span class="log-time">[${new Date().toLocaleTimeString()}]</span> ⚠️ Telemetry stream disconnected. Reconnecting...`;
        logsContainer.appendChild(errorDiv);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    };
}

function appendLogEntry(log) {
    const logsContainer = document.getElementById('logs-container');
    if (!logsContainer) return;

    const timeStr   = new Date(log.created_at).toLocaleTimeString();
    const eventType = log.event_type || 'INFO';
    const badgeClass = `badge-${eventType.toLowerCase()}`;
    const actor     = log.actor_id || 'System';

    let message = log.payload?.message;
    if (!message) {
        const payloadCopy = { ...log.payload };
        message = Object.keys(payloadCopy).length > 0 ? JSON.stringify(payloadCopy) : 'No payload details';
    }

    const entryDiv = document.createElement('div');
    entryDiv.className = 'log-entry';
    entryDiv.innerHTML = `
        <span class="log-time">[${timeStr}]</span>
        <span class="badge ${badgeClass}">${eventType}</span>
        <span class="log-actor">&lt;${actor}&gt;</span>
        <span class="log-msg">${message}</span>
        <pre class="log-payload-raw">${JSON.stringify(log, null, 2)}</pre>
    `;

    entryDiv.addEventListener('click', (e) => {
        if (e.target.closest('.log-payload-raw')) return;
        const raw = entryDiv.querySelector('.log-payload-raw');
        if (raw) raw.style.display = raw.style.display === 'none' ? 'block' : 'none';
    });

    logsContainer.appendChild(entryDiv);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// ── SERVER VISUALIZER (VIZ-01..04) ──────────────────────────────

let vizNodeCache = {};

const PERMISSIONS = {
    0x8:        'Administrator',
    0x20:       'Manage Server',
    0x10:       'Manage Channels',
    0x10000000: 'Manage Roles',
    0x400:      'View Channel',
    0x800:      'Send Messages',
    0x4000:     'Manage Messages',
    0x2000:     'Manage Webhooks',
    0x2:        'Kick Members',
    0x4:        'Ban Members',
    0x40:       'Add Reactions',
    0x100000:   'Connect',
    0x200000:   'Speak',
    0x4000000:  'Change Nickname',
    0x10000:    'Read Message History',
};

function decodePermissions(bitfield) {
    const names = [];
    for (const [bit, name] of Object.entries(PERMISSIONS)) {
        if ((bitfield & Number(bit)) !== 0) names.push(name);
    }
    return names;
}

function abbreviateRole(name) {
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) return words.map(w => w[0]).join('').toUpperCase().slice(0, 4);
    return name.slice(0, 4);
}

function channelIcon(type) {
    const icons = { text: '#', voice: '🔊', forum: '💬', stage: '🎙️', announcement: '📢' };
    return icons[type] || '#';
}

function buildBadges(overwrites) {
    const filtered = overwrites.filter(ow => ow.allow !== 0 || ow.deny !== 0);
    if (filtered.length === 0) return '';

    const visible = filtered.slice(0, 3);
    const hidden  = filtered.slice(3);

    let html = '';
    for (const ow of visible) {
        const cls = ow.allow !== 0 ? 'viz-badge--allow' : (ow.deny !== 0 ? 'viz-badge--deny' : 'viz-badge--inherited');
        html += `<span class="viz-badge ${cls}" title="${ow.role_name}">${abbreviateRole(ow.role_name)}</span>`;
    }
    if (hidden.length > 0) {
        let extras = '';
        for (const ow of hidden) {
            const cls = ow.allow !== 0 ? 'viz-badge--allow' : (ow.deny !== 0 ? 'viz-badge--deny' : 'viz-badge--inherited');
            extras += `<span class="viz-badge ${cls}" title="${ow.role_name}">${abbreviateRole(ow.role_name)}</span>`;
        }
        html += `<span class="viz-badge viz-badge--overflow">+${hidden.length} more</span>`;
        html += `<span class="viz-badge-extras">${extras}</span>`;
    }
    return html;
}

function renderVizTree(data, col) {
    vizNodeCache = {};
    const frag = document.createDocumentFragment();

    // Categories + their channels
    for (const cat of data.categories) {
        vizNodeCache['category:' + cat.id] = cat;
        const details = document.createElement('details');
        details.className = 'viz-node viz-node--category';
        details.open = true;
        details.dataset.nodeType = 'category';
        details.dataset.nodeId = cat.id;

        const summary = document.createElement('summary');
        summary.textContent = '📁 ' + cat.name;
        details.appendChild(summary);

        for (const ch of cat.channels) {
            vizNodeCache['channel:' + ch.id] = ch;
            const row = document.createElement('div');
            row.className = 'viz-node viz-node--channel';
            row.dataset.nodeType = 'channel';
            row.dataset.nodeId = ch.id;
            row.innerHTML = `${channelIcon(ch.type)} ${ch.name}${buildBadges(ch.permission_overwrites)}`;
            details.appendChild(row);
        }
        frag.appendChild(details);
    }

    // Uncategorized
    if (data.uncategorized.length > 0) {
        const details = document.createElement('details');
        details.className = 'viz-node viz-node--category';
        details.open = true;
        details.dataset.nodeType = 'category';
        details.dataset.nodeId = 'uncategorized';
        vizNodeCache['category:uncategorized'] = { id: 'uncategorized', name: 'Uncategorized', position: -1, channels: data.uncategorized };

        const summary = document.createElement('summary');
        summary.textContent = '📁 Uncategorized';
        details.appendChild(summary);

        for (const ch of data.uncategorized) {
            vizNodeCache['channel:' + ch.id] = ch;
            const row = document.createElement('div');
            row.className = 'viz-node viz-node--channel';
            row.dataset.nodeType = 'channel';
            row.dataset.nodeId = ch.id;
            row.innerHTML = `${channelIcon(ch.type)} ${ch.name}${buildBadges(ch.permission_overwrites)}`;
            details.appendChild(row);
        }
        frag.appendChild(details);
    }

    // Empty channels notice
    if (data.categories.length === 0 && data.uncategorized.length === 0) {
        const p = document.createElement('p');
        p.className = 'viz-loading';
        p.textContent = 'No channels found.';
        frag.appendChild(p);
    }

    // Roles section
    if (data.roles.length > 0) {
        const details = document.createElement('details');
        details.className = 'viz-node viz-node--category';
        details.open = true;

        const summary = document.createElement('summary');
        summary.textContent = 'Roles';
        details.appendChild(summary);

        for (const r of data.roles) {
            vizNodeCache['role:' + r.id] = r;
            const row = document.createElement('div');
            row.className = 'viz-node viz-node--role';
            row.dataset.nodeType = 'role';
            row.dataset.nodeId = r.id;
            row.innerHTML = `<span class="viz-role-swatch" style="background:${r.color}"></span>${r.name}`;
            details.appendChild(row);
        }
        frag.appendChild(details);
    }

    col.innerHTML = '';
    col.appendChild(frag);
}

function renderDetailPane(nodeType, nodeId) {
    const pane = document.getElementById('viz-detail-pane');
    if (!pane) return;
    const node = vizNodeCache[nodeType + ':' + nodeId];
    if (!node) {
        pane.innerHTML = '<p class="viz-detail-placeholder">Select a node to inspect</p>';
        return;
    }

    if (nodeType === 'channel') {
        const ch = node;
        let owRows = '';
        for (const ow of ch.permission_overwrites) {
            const allowNames = decodePermissions(ow.allow);
            const denyNames  = decodePermissions(ow.deny);
            const allowStr   = allowNames.length ? allowNames.join(', ') : '—';
            const denyStr    = denyNames.length  ? denyNames.join(', ')  : '—';
            owRows += `<div class="viz-prop-row"><span class="viz-prop-label">${ow.role_name}</span><span class="viz-prop-value">Allow: ${allowStr}<br>Deny: ${denyStr}</span></div>`;
        }
        pane.innerHTML = `
            <h3 class="viz-detail-title"></h3>
            <div class="viz-prop-row"><span class="viz-prop-label">Type</span><span class="viz-prop-value">${ch.type}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Position</span><span class="viz-prop-value">${ch.position}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Topic</span><span class="viz-prop-value" id="viz-detail-topic"></span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Category</span><span class="viz-prop-value">${ch.category_name || 'Uncategorized'}</span></div>
            ${owRows ? '<div class="viz-prop-row"><span class="viz-prop-label">Overwrites</span><span class="viz-prop-value"></span></div>' + owRows : ''}
        `;
        pane.querySelector('.viz-detail-title').textContent = ch.name;
        const topicEl = pane.querySelector('#viz-detail-topic');
        if (topicEl) topicEl.textContent = ch.topic || '—';

    } else if (nodeType === 'role') {
        const r = node;
        const permNames = decodePermissions(r.permissions);
        pane.innerHTML = `
            <h3 class="viz-detail-title"></h3>
            <div class="viz-prop-row"><span class="viz-prop-label">Color</span><span class="viz-prop-value"><span class="viz-role-swatch" style="background:${r.color}"></span> <span id="viz-detail-color"></span></span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Position</span><span class="viz-prop-value">${r.position}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Hoist</span><span class="viz-prop-value">${r.hoist ? 'Yes' : 'No'}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Mentionable</span><span class="viz-prop-value">${r.mentionable ? 'Yes' : 'No'}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Permissions</span><span class="viz-prop-value">${permNames.length ? permNames.join(', ') : 'None'}</span></div>
        `;
        pane.querySelector('.viz-detail-title').textContent = r.name;
        const colorEl = pane.querySelector('#viz-detail-color');
        if (colorEl) colorEl.textContent = r.color;

    } else if (nodeType === 'category') {
        const cat = node;
        const channelCount = Array.isArray(cat.channels) ? cat.channels.length : 0;
        pane.innerHTML = `
            <h3 class="viz-detail-title"></h3>
            <div class="viz-prop-row"><span class="viz-prop-label">Position</span><span class="viz-prop-value">${cat.position}</span></div>
            <div class="viz-prop-row"><span class="viz-prop-label">Channels</span><span class="viz-prop-value">${channelCount}</span></div>
        `;
        pane.querySelector('.viz-detail-title').textContent = cat.name;
    }
}

async function fetchAndRenderStructure(guildId) {
    if (!guildId) return;
    const col = document.getElementById('viz-tree-col');
    const btn = document.getElementById('viz-refresh-btn');
    if (!col) return;

    if (btn) { btn.disabled = true; btn.textContent = '⟳ Loading...'; }
    col.innerHTML = '<p class="viz-loading">Loading structure...</p>';

    try {
        const res = await fetch('/api/guilds/' + guildId + '/structure');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        renderVizTree(data, col);
        const pane = document.getElementById('viz-detail-pane');
        if (pane) pane.innerHTML = '<p class="viz-detail-placeholder">Select a node to inspect</p>';
    } catch (err) {
        col.innerHTML = `<div class="viz-error"><p>Failed to load server structure.</p><button class="secondary-btn" type="button" onclick="fetchAndRenderStructure('${guildId}')">Retry</button></div>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '↺ Refresh'; }
    }
}

function initVisualizer() {
    if (!document.getElementById('panel-visualizer')) return;

    document.addEventListener('guildChanged', (e) => {
        fetchAndRenderStructure(e.detail.id);
    });

    document.getElementById('nav-visualizer')?.addEventListener('click', () => {
        if (window.activeGuild) fetchAndRenderStructure(window.activeGuild.id);
    });

    const refreshBtn = document.getElementById('viz-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            if (window.activeGuild) fetchAndRenderStructure(window.activeGuild.id);
        });
    }

    document.addEventListener('mutationApplied', () => {
        if (window.activeGuild) fetchAndRenderStructure(window.activeGuild.id);
    });

    const treeCol = document.getElementById('viz-tree-col');
    if (treeCol) {
        treeCol.addEventListener('click', (e) => {
            // Badge overflow toggle
            const overflowBadge = e.target.closest('.viz-badge--overflow');
            if (overflowBadge) {
                const channelNode = overflowBadge.closest('.viz-node--channel');
                if (channelNode) channelNode.classList.toggle('expanded');
                return;
            }

            // Node selection
            const node = e.target.closest('[data-node-type]');
            if (!node) return;

            // Active state
            document.querySelectorAll('.viz-node').forEach(n => n.classList.remove('active'));
            node.classList.add('active');

            renderDetailPane(node.dataset.nodeType, node.dataset.nodeId);
        });
    }
}

// ── EMBED FORM EVENT WIRING ─────────────────────────────────────

function initEmbedForm() {
    const guildSelect    = document.getElementById('guild-select');
    const embedForm      = document.getElementById('embed-form');
    const templateSelect = document.getElementById('template-select');
    const saveTemplateBtn = document.getElementById('save-template-btn');
    const clearFormBtn   = document.getElementById('clear-form-btn');

    if (guildSelect) guildSelect.addEventListener('change', () => fetchChannels(guildSelect.value));
    if (embedForm)   embedForm.addEventListener('input', updatePreview);
    if (saveTemplateBtn) saveTemplateBtn.addEventListener('click', saveTemplate);
    if (templateSelect)  templateSelect.addEventListener('change', (e) => applyTemplate(e.target.value));
    if (clearFormBtn)    clearFormBtn.addEventListener('click', clearForm);

    if (embedForm) {
        embedForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const channelIds = [...document.querySelectorAll('.broadcast-channel-cb:checked')].map(cb => cb.value);
            if (channelIds.length === 0) {
                showToast('Select at least one channel.', 'error');
                return;
            }
            const embed = {
                title:       document.getElementById('embed-title')?.value || '',
                description: document.getElementById('embed-description')?.value || '',
                color:       parseInt((document.getElementById('embed-color')?.value || '#4f545c').substring(1), 16),
                footer:      { text: document.getElementById('embed-footer')?.value || '' }
            };
            const resultsDiv = document.getElementById('broadcast-results');
            if (resultsDiv) resultsDiv.innerHTML = '';
            for (const channelId of channelIds) {
                try {
                    const res = await fetch('/api/channels/' + channelId + '/messages', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ embed })
                    });
                    const data = await res.json();
                    const name = data.channel_name || channelId;
                    appendBroadcastResult(channelId, res.ok, name, data.error);
                    if (res.ok) showToast('Sent to #' + name + '.', 'success');
                } catch (e) {
                    appendBroadcastResult(channelId, false, channelId, e.message);
                }
            }
        });
    }
}

// ── MANUAL CONTROLS (Phase 6) ────────────────────────────────────

/**
 * showToast(message, type)
 * Renders a glassmorphic toast notification in #toast-container.
 * type: 'success' | 'error'
 * Auto-dismisses after 3000ms + 150ms slide-out animation.
 * textContent used (not innerHTML) — XSS mitigation per T-6-00-XSS.
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast toast--' + type;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast--dismissing');
        setTimeout(() => {
            toast.remove();
        }, 150);
    }, 3000);
}

/**
 * switchManualTab(tabId)
 * Activates the manual sub-tab panel with id=tabId and updates button states.
 */
function switchManualTab(tabId) {
    document.querySelectorAll('.manual-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.querySelectorAll('.manual-tab-btn').forEach(btn => {
        btn.classList.remove('manual-tab-btn--active');
        btn.setAttribute('aria-selected', 'false');
    });

    const targetPanel = document.getElementById(tabId);
    if (targetPanel) {
        targetPanel.classList.add('active');
    }

    const targetBtn = document.querySelector('.manual-tab-btn[data-tab="' + tabId + '"]');
    if (targetBtn) {
        targetBtn.classList.add('manual-tab-btn--active');
        targetBtn.setAttribute('aria-selected', 'true');
    }
}

/**
 * fetchStructureAndPopulate(guildId)
 * Fetches the guild structure from /api/guilds/{guildId}/structure and caches
 * the result in window.currentStructure for slice plans to consume.
 */
async function fetchStructureAndPopulate(guildId) {
    if (!guildId) return;
    try {
        const res = await fetch('/api/guilds/' + guildId + '/structure');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        window.currentStructure = await res.json();
        // slice plans add populate* calls here
        populateChannelDropdowns(window.currentStructure);
        populateRoleDropdowns().catch(err => console.error('[ManualControls] populateRoleDropdowns error:', err));
        populatePermissionDropdowns(window.currentStructure);
        populateBroadcastCheckboxList();
    } catch (err) {
        console.error('[ManualControls] fetchStructureAndPopulate error:', err);
    }
}

/**
 * initManualControls()
 * Initialises the Manual Controls panel: tab switching, keyboard support,
 * guildChanged/mutationApplied event listeners, and initial structure fetch.
 */
function initManualControls() {
    if (!document.getElementById('panel-manual')) return;

    // Wire tab button clicks
    document.querySelectorAll('.manual-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchManualTab(btn.dataset.tab);
        });

        // Keyboard accessibility: Enter and Space activate the tab
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                switchManualTab(btn.dataset.tab);
            }
        });
    });

    // Re-fetch structure whenever the selected guild changes
    document.addEventListener('guildChanged', (e) => {
        fetchStructureAndPopulate(e.detail.id);
    });

    // Re-fetch structure whenever a mutation is applied (keeps cache fresh)
    document.addEventListener('mutationApplied', () => {
        if (window.activeGuild) fetchStructureAndPopulate(window.activeGuild.id);
    });

    // If a guild is already selected when the page loads, fetch immediately
    if (window.activeGuild) {
        fetchStructureAndPopulate(window.activeGuild.id);
    }
}

// ── CHANNEL MANAGER (Phase 6 — Plan 06-01) ──────────────────────

/**
 * populateChannelDropdowns(structure)
 * Fills all channel-related <select> dropdowns in the Channels tab
 * from the guild structure object. Called from fetchStructureAndPopulate.
 */
function populateChannelDropdowns(structure) {
    if (!structure) return;

    const categories = structure.categories || [];
    const uncategorized = structure.uncategorized || [];

    // --- #chan-create-category: categories only + "No category" ---
    const createCat = document.getElementById('chan-create-category');
    if (createCat) {
        const savedVal = createCat.value;
        createCat.innerHTML = '<option value="">No category</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.id;
            opt.textContent = cat.name;
            createCat.appendChild(opt);
        });
        if (savedVal) createCat.value = savedVal;
    }

    // --- #chan-edit-category: categories + "No change" ---
    const editCat = document.getElementById('chan-edit-category');
    if (editCat) {
        editCat.innerHTML = '<option value="">No change</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.id;
            opt.textContent = cat.name;
            editCat.appendChild(opt);
        });
    }

    // Collect all channels for edit/delete selects
    const allChannels = [];
    categories.forEach(cat => {
        (cat.channels || []).forEach(ch => allChannels.push(ch));
    });
    uncategorized.forEach(ch => allChannels.push(ch));

    // --- #chan-edit-select: all channels ---
    const editSel = document.getElementById('chan-edit-select');
    if (editSel) {
        editSel.innerHTML = '<option value="">Select a channel...</option>';
        allChannels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch.id;
            opt.textContent = '#' + ch.name;
            editSel.appendChild(opt);
        });
    }

    // --- #chan-delete-select: all channels ---
    const delSel = document.getElementById('chan-delete-select');
    if (delSel) {
        delSel.innerHTML = '<option value="">Select a channel...</option>';
        allChannels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch.id;
            opt.textContent = '#' + ch.name;
            delSel.appendChild(opt);
        });
    }
}

/**
 * initChannelManager()
 * Wires form-mode strip, topic visibility toggle, and submit handlers
 * for the Channels tab Create / Edit / Delete forms.
 */
function initChannelManager() {
    if (!document.getElementById('manual-tab-channels')) return;

    // --- Form mode strip ---
    const strip = document.getElementById('channel-mode-strip');
    if (strip) {
        strip.addEventListener('click', (e) => {
            const btn = e.target.closest('.form-mode-btn');
            if (!btn) return;
            const mode = btn.dataset.mode;

            // Update active button
            strip.querySelectorAll('.form-mode-btn').forEach(b => {
                b.classList.remove('form-mode-btn--active');
            });
            btn.classList.add('form-mode-btn--active');

            // Show matching form, hide siblings; clear inputs in hidden forms
            ['create', 'edit', 'delete'].forEach(m => {
                const form = document.getElementById('channel-form-' + m);
                if (!form) return;
                if (m === mode) {
                    form.style.display = '';
                } else {
                    form.style.display = 'none';
                    // Clear inputs when hiding
                    form.querySelectorAll('input, textarea').forEach(el => { el.value = ''; });
                    form.querySelectorAll('select').forEach(el => { el.selectedIndex = 0; });
                }
            });
        });
    }

    // --- Topic visibility: show only for text and forum ---
    const typeSelect = document.getElementById('chan-create-type');
    const topicWrap = document.getElementById('chan-create-topic-wrap');
    function updateTopicVisibility() {
        if (!topicWrap || !typeSelect) return;
        const t = typeSelect.value;
        topicWrap.style.display = (t === 'text' || t === 'forum') ? '' : 'none';
    }
    if (typeSelect) {
        typeSelect.addEventListener('change', updateTopicVisibility);
        updateTopicVisibility();
    }

    // --- Create Channel submit ---
    const createSubmit = document.getElementById('chan-create-submit');
    if (createSubmit) {
        createSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const name = (document.getElementById('chan-create-name')?.value || '').trim();
            if (!name) {
                showToast('Channel name is required.', 'error');
                return;
            }
            const type = document.getElementById('chan-create-type')?.value || 'text';
            const categoryId = document.getElementById('chan-create-category')?.value || '';
            const topic = document.getElementById('chan-create-topic')?.value || '';

            const payload = { name, type };
            if (categoryId) payload.category_id = categoryId;
            if (topic && (type === 'text' || type === 'forum')) payload.topic = topic;

            try {
                const res = await fetch(`/api/guilds/${window.activeGuild.id}/channels`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Channel created successfully.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: window.activeGuild.id, type: 'channel_create' }
                }));
                // Clear form
                document.getElementById('chan-create-name').value = '';
                document.getElementById('chan-create-topic').value = '';
                const catSel = document.getElementById('chan-create-category');
                if (catSel) catSel.selectedIndex = 0;
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }

    // --- Edit (Update) Channel submit ---
    const editSubmit = document.getElementById('chan-edit-submit');
    if (editSubmit) {
        editSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const channelId = document.getElementById('chan-edit-select')?.value;
            if (!channelId) {
                showToast('Select a channel to edit.', 'error');
                return;
            }
            const newName = (document.getElementById('chan-edit-name')?.value || '').trim();
            const newCatId = document.getElementById('chan-edit-category')?.value || '';
            const newTopic = document.getElementById('chan-edit-topic')?.value || '';

            const payload = {};
            if (newName) payload.name = newName;
            if (newCatId) payload.category_id = newCatId;
            if (newTopic) payload.topic = newTopic;

            if (Object.keys(payload).length === 0) {
                showToast('No changes to apply.', 'error');
                return;
            }

            try {
                const gid = window.activeGuild.id;
                const res = await fetch(`/api/guilds/${gid}/channels/${channelId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Channel updated.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: gid, type: 'channel_edit' }
                }));
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }

    // --- Delete Channel submit ---
    const deleteSubmit = document.getElementById('chan-delete-submit');
    if (deleteSubmit) {
        deleteSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const channelId = document.getElementById('chan-delete-select')?.value;
            if (!channelId) {
                showToast('Select a channel to delete.', 'error');
                return;
            }

            try {
                const gid = window.activeGuild.id;
                const res = await fetch(`/api/guilds/${gid}/channels/${channelId}`, {
                    method: 'DELETE'
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Channel deleted.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: gid, type: 'channel_delete' }
                }));
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }
}

// ── ROLE MANAGER (Phase 6 — Plan 06-02) ─────────────────────────

/**
 * PERMISSION_BITS: curated map of 15 Discord permission flag names to their bit values.
 * Verified against discord.py 2.7.1 and Discord API docs (D-13).
 */
const PERMISSION_BITS = {
    administrator:        8,
    manage_guild:         32,
    manage_channels:      16,
    manage_roles:         268435456,
    manage_messages:      8192,
    kick_members:         2,
    ban_members:          4,
    view_channel:         1024,
    send_messages:        2048,
    read_message_history: 65536,
    manage_nicknames:     134217728,
    attach_files:         32768,
    embed_links:          16384,
    mention_everyone:     131072,
    add_reactions:        64,
};

/**
 * hasPermission(permInt, flag)
 * Returns true if the permission integer has the given flag set.
 * Single-bit checks are safe per Pitfall 6 in RESEARCH.md.
 */
function hasPermission(permInt, flag) {
    const b = PERMISSION_BITS[flag];
    return b ? (permInt & b) !== 0 : false;
}

/**
 * populateRoleDropdowns()
 * Fetches GET /api/guilds/{id}/roles, caches in window.currentRoles,
 * and fills #role-edit-select and #role-delete-select (excluding managed roles).
 * The GET endpoint already excludes @everyone.
 */
async function populateRoleDropdowns() {
    if (!window.activeGuild) return;
    try {
        const res = await fetch(`/api/guilds/${window.activeGuild.id}/roles`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const roles = await res.json();
        window.currentRoles = roles;

        // Filter out bot-managed roles for edit/delete dropdowns
        const editableRoles = roles.filter(r => !r.managed);

        const editSel = document.getElementById('role-edit-select');
        if (editSel) {
            editSel.innerHTML = '<option value="">Select a role...</option>';
            editableRoles.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r.id;
                opt.textContent = r.name;
                editSel.appendChild(opt);
            });
        }

        const delSel = document.getElementById('role-delete-select');
        if (delSel) {
            delSel.innerHTML = '<option value="">Select a role...</option>';
            editableRoles.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r.id;
                opt.textContent = r.name;
                delSel.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('[RoleManager] populateRoleDropdowns error:', err);
    }
}

/**
 * initRoleManager()
 * Wires form-mode strip, edit pre-population, and submit handlers
 * for the Roles tab Create / Edit / Delete forms.
 */
function initRoleManager() {
    if (!document.getElementById('manual-tab-roles')) return;

    // --- Form mode strip ---
    const strip = document.getElementById('role-mode-strip');
    if (strip) {
        strip.addEventListener('click', (e) => {
            const btn = e.target.closest('.form-mode-btn');
            if (!btn) return;
            const mode = btn.dataset.mode;

            strip.querySelectorAll('.form-mode-btn').forEach(b => {
                b.classList.remove('form-mode-btn--active');
            });
            btn.classList.add('form-mode-btn--active');

            ['create', 'edit', 'delete'].forEach(m => {
                const form = document.getElementById('role-form-' + m);
                if (!form) return;
                if (m === mode) {
                    form.style.display = '';
                } else {
                    form.style.display = 'none';
                    form.querySelectorAll('input[type="text"], input[type="color"]').forEach(el => {
                        el.value = el.type === 'color' ? '#000000' : '';
                    });
                    form.querySelectorAll('input[type="checkbox"]').forEach(el => { el.checked = false; });
                    form.querySelectorAll('select').forEach(el => { el.selectedIndex = 0; });
                }
            });
        });
    }

    // --- Edit: pre-populate from selected role ---
    const editSelect = document.getElementById('role-edit-select');
    if (editSelect) {
        editSelect.addEventListener('change', () => {
            const roleId = editSelect.value;
            if (!roleId || !window.currentRoles) return;

            const role = window.currentRoles.find(r => r.id === roleId);
            if (!role) return;

            const nameEl = document.getElementById('role-edit-name');
            const colorEl = document.getElementById('role-edit-color');
            const hoistEl = document.getElementById('role-edit-hoist');

            if (nameEl) nameEl.value = role.name;
            if (colorEl) colorEl.value = role.color || '#000000';
            if (hoistEl) hoistEl.checked = !!role.hoist;

            // Pre-populate 15 permission checkboxes
            const permsContainer = document.getElementById('role-edit-perms');
            if (permsContainer) {
                permsContainer.querySelectorAll('input[type="checkbox"][data-perm]').forEach(cb => {
                    cb.checked = hasPermission(role.permissions, cb.dataset.perm);
                });
            }
        });
    }

    // --- Create Role submit ---
    const createSubmit = document.getElementById('role-create-submit');
    if (createSubmit) {
        createSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const name = (document.getElementById('role-create-name')?.value || '').trim();
            if (!name) {
                showToast('Role name is required.', 'error');
                return;
            }
            const colorHex = document.getElementById('role-create-color')?.value || '#000000';
            const hoist = !!(document.getElementById('role-create-hoist')?.checked);

            // Build permissions dict from checked boxes only (unchecked = false baseline via build_permissions)
            const permissions = {};
            const createPerms = document.getElementById('role-create-perms');
            if (createPerms) {
                createPerms.querySelectorAll('input[type="checkbox"][data-perm]:checked').forEach(cb => {
                    permissions[cb.dataset.perm] = true;
                });
            }

            try {
                const res = await fetch(`/api/guilds/${window.activeGuild.id}/roles`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, color_hex: colorHex, hoist, permissions })
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Role created successfully.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: window.activeGuild.id, type: 'role_create' }
                }));
                // Clear form
                const nameEl = document.getElementById('role-create-name');
                if (nameEl) nameEl.value = '';
                const colorEl = document.getElementById('role-create-color');
                if (colorEl) colorEl.value = '#000000';
                const hoistEl = document.getElementById('role-create-hoist');
                if (hoistEl) hoistEl.checked = false;
                if (createPerms) {
                    createPerms.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
                }
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }

    // --- Edit (Update) Role submit ---
    const editSubmit = document.getElementById('role-edit-submit');
    if (editSubmit) {
        editSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const roleId = document.getElementById('role-edit-select')?.value;
            if (!roleId) {
                showToast('Select a role to edit.', 'error');
                return;
            }
            const name = (document.getElementById('role-edit-name')?.value || '').trim();
            const colorHex = document.getElementById('role-edit-color')?.value || '#000000';
            const hoist = !!(document.getElementById('role-edit-hoist')?.checked);

            // Build full permissions dict (all 15 flags, checked=true, unchecked=false)
            const permissions = {};
            const editPerms = document.getElementById('role-edit-perms');
            if (editPerms) {
                editPerms.querySelectorAll('input[type="checkbox"][data-perm]').forEach(cb => {
                    permissions[cb.dataset.perm] = cb.checked;
                });
            }

            const payload = { color_hex: colorHex, hoist, permissions };
            if (name) payload.name = name;

            try {
                const gid = window.activeGuild.id;
                const res = await fetch(`/api/guilds/${gid}/roles/${roleId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Role updated.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: gid, type: 'role_edit' }
                }));
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }

    // --- Delete Role submit ---
    const deleteSubmit = document.getElementById('role-delete-submit');
    if (deleteSubmit) {
        deleteSubmit.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const roleId = document.getElementById('role-delete-select')?.value;
            if (!roleId) {
                showToast('Select a role to delete.', 'error');
                return;
            }

            try {
                const gid = window.activeGuild.id;
                const res = await fetch(`/api/guilds/${gid}/roles/${roleId}`, {
                    method: 'DELETE'
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Role deleted.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: gid, type: 'role_delete' }
                }));
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }
}

// ── PERMISSION OVERRIDE MANAGER (Phase 6 — Plan 06-03) ──────────

/**
 * OVERRIDE_FLAGS: 10 curated Discord channel permission flags (D-17).
 */
const OVERRIDE_FLAGS = [
    'view_channel',
    'send_messages',
    'read_message_history',
    'manage_messages',
    'manage_channels',
    'attach_files',
    'embed_links',
    'add_reactions',
    'use_external_emojis',
    'mention_everyone',
];

// Extend PERMISSION_BITS with use_external_emojis if not already present
if (!PERMISSION_BITS.use_external_emojis) {
    PERMISSION_BITS.use_external_emojis = 262144;
}

/**
 * renderPermissionGrid(stateByFlag)
 * Builds one .permission-row per OVERRIDE_FLAG into #perm-grid.
 * stateByFlag: { flag: 'allow' | 'deny' | 'inherit' }
 */
function renderPermissionGrid(stateByFlag) {
    const grid = document.getElementById('perm-grid');
    if (!grid) return;

    const stateIcons = { allow: '✓', deny: '✗', inherit: '—' };

    grid.innerHTML = '';
    OVERRIDE_FLAGS.forEach(flag => {
        const state = (stateByFlag && stateByFlag[flag]) || 'inherit';
        const icon = stateIcons[state] || '—';

        const row = document.createElement('div');
        row.className = 'permission-row';
        row.dataset.flag = flag;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'perm-name';
        nameSpan.textContent = flag.replace(/_/g, ' ');

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'perm-state-btn';
        btn.dataset.state = state;
        btn.textContent = icon;
        btn.setAttribute('aria-label', flag + ': ' + state);

        row.appendChild(nameSpan);
        row.appendChild(btn);
        grid.appendChild(row);
    });
}

/**
 * populatePermissionDropdowns(structure)
 * Fills #perm-channel-select (all channels) and #perm-role-select (all roles)
 * from the guild structure. Called from fetchStructureAndPopulate.
 */
function populatePermissionDropdowns(structure) {
    if (!structure) return;

    const categories = structure.categories || [];
    const uncategorized = structure.uncategorized || [];
    const roles = structure.roles || [];

    // Collect all channels
    const allChannels = [];
    categories.forEach(cat => {
        (cat.channels || []).forEach(ch => allChannels.push(ch));
    });
    uncategorized.forEach(ch => allChannels.push(ch));

    const chanSel = document.getElementById('perm-channel-select');
    if (chanSel) {
        chanSel.innerHTML = '<option value="">Select a channel...</option>';
        allChannels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch.id;
            opt.textContent = '#' + ch.name;
            chanSel.appendChild(opt);
        });
    }

    const roleSel = document.getElementById('perm-role-select');
    if (roleSel) {
        roleSel.innerHTML = '<option value="">Select a role...</option>';
        roles.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.id;
            opt.textContent = r.name;
            roleSel.appendChild(opt);
        });
    }
}

/**
 * findChannelInStructure(structure, channelId)
 * Searches categories + uncategorized for a channel with the given id.
 */
function findChannelInStructure(structure, channelId) {
    if (!structure) return null;
    const categories = structure.categories || [];
    const uncategorized = structure.uncategorized || [];

    for (const cat of categories) {
        for (const ch of (cat.channels || [])) {
            if (ch.id === channelId) return ch;
        }
    }
    for (const ch of uncategorized) {
        if (ch.id === channelId) return ch;
    }
    return null;
}

/**
 * initPermissionManager()
 * Wires Load Permissions, state-cycle click, and Apply Overrides for the Permissions tab.
 */
function initPermissionManager() {
    if (!document.getElementById('manual-tab-perms')) return;

    // --- #perm-load-btn: load existing overrides for selected channel + role ---
    const loadBtn = document.getElementById('perm-load-btn');
    if (loadBtn) {
        loadBtn.addEventListener('click', () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const channelId = document.getElementById('perm-channel-select')?.value;
            const roleId = document.getElementById('perm-role-select')?.value;

            if (!channelId || !roleId) {
                showToast('Select a channel and role.', 'error');
                return;
            }

            const channel = findChannelInStructure(window.currentStructure, channelId);
            if (!channel) {
                showToast('Channel not found in structure.', 'error');
                return;
            }

            // Find overwrite for the selected role
            const overwrite = (channel.permission_overwrites || []).find(
                ow => ow.role_id === roleId
            );

            const allowInt = overwrite ? (overwrite.allow || 0) : 0;
            const denyInt  = overwrite ? (overwrite.deny  || 0) : 0;

            // Compute per-flag state
            const stateByFlag = {};
            OVERRIDE_FLAGS.forEach(flag => {
                const bit = PERMISSION_BITS[flag];
                if (!bit) {
                    stateByFlag[flag] = 'inherit';
                } else if (allowInt & bit) {
                    stateByFlag[flag] = 'allow';
                } else if (denyInt & bit) {
                    stateByFlag[flag] = 'deny';
                } else {
                    stateByFlag[flag] = 'inherit';
                }
            });

            renderPermissionGrid(stateByFlag);
        });
    }

    // --- Delegated .perm-state-btn click: cycle inherit -> allow -> deny -> inherit ---
    const grid = document.getElementById('perm-grid');
    if (grid) {
        grid.addEventListener('click', (e) => {
            const btn = e.target.closest('.perm-state-btn');
            if (!btn) return;

            const stateIcons = { allow: '✓', deny: '✗', inherit: '—' };
            const cycle = { inherit: 'allow', allow: 'deny', deny: 'inherit' };
            const currentState = btn.dataset.state || 'inherit';
            const nextState = cycle[currentState] || 'inherit';

            btn.dataset.state = nextState;
            btn.textContent = stateIcons[nextState];

            const row = btn.closest('.permission-row');
            const flag = row ? row.dataset.flag : '';
            btn.setAttribute('aria-label', (flag ? flag + ': ' : '') + nextState);
        });
    }

    // --- #perm-apply-btn: build allow/deny dicts and POST ---
    const applyBtn = document.getElementById('perm-apply-btn');
    if (applyBtn) {
        applyBtn.addEventListener('click', async () => {
            if (!window.activeGuild) {
                showToast('Select a server first.', 'error');
                return;
            }
            const channelId = document.getElementById('perm-channel-select')?.value;
            const roleId = document.getElementById('perm-role-select')?.value;

            if (!channelId || !roleId) {
                showToast('Select a channel and role.', 'error');
                return;
            }

            const permGrid = document.getElementById('perm-grid');
            if (!permGrid || permGrid.children.length === 0) {
                showToast('Load permissions first.', 'error');
                return;
            }

            // Build allow and deny dicts; inherit flags are omitted (D-19)
            const allow = {};
            const deny = {};
            permGrid.querySelectorAll('.permission-row').forEach(row => {
                const flag = row.dataset.flag;
                const btn = row.querySelector('.perm-state-btn');
                if (!flag || !btn) return;
                const state = btn.dataset.state;
                if (state === 'allow') allow[flag] = true;
                else if (state === 'deny') deny[flag] = true;
            });

            try {
                const gid = window.activeGuild.id;
                const res = await fetch(`/api/guilds/${gid}/channels/${channelId}/permissions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role_id: roleId, allow, deny })
                });
                const body = await res.json();
                if (!res.ok) {
                    showToast('Error: ' + (body.error || 'Unknown error'), 'error');
                    return;
                }
                showToast('Permission overrides applied.', 'success');
                document.dispatchEvent(new CustomEvent('mutationApplied', {
                    detail: { guildId: gid, type: 'permission_update' }
                }));
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        });
    }
}

// ── BROADCAST MANAGER (Phase 6 — Plan 06-04) ────────────────────

const TEXT_CAPABLE_TYPES = new Set(['text', 'announcement', 'forum']);

/**
 * populateBroadcastCheckboxList()
 * Populates #broadcast-channel-list with grouped <details> elements,
 * one per category, containing checkbox rows for text-capable channels.
 * Reads from window.currentStructure. Uses textContent for channel names (XSS mitigation T-6-04-XSS).
 */
function populateBroadcastCheckboxList() {
    const list = document.getElementById('broadcast-channel-list');
    if (!list) return;
    list.innerHTML = '';

    const structure = window.currentStructure;
    if (!structure) return;

    /**
     * buildGroup(name, channels)
     * Creates a <details class="channel-checkbox-group" open> element
     * for the given category name and filtered channel list.
     */
    function buildGroup(name, channels) {
        const textChannels = channels.filter(ch => TEXT_CAPABLE_TYPES.has(ch.type));
        if (textChannels.length === 0) return null;

        const details = document.createElement('details');
        details.className = 'channel-checkbox-group';
        details.open = true;

        const summary = document.createElement('summary');
        summary.className = 'group-header';
        summary.textContent = name.toUpperCase();
        details.appendChild(summary);

        textChannels.forEach(ch => {
            const label = document.createElement('label');

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'broadcast-channel-cb';
            cb.value = ch.id;

            const text = document.createTextNode(' #' + ch.name);

            label.appendChild(cb);
            label.appendChild(text);
            details.appendChild(label);
        });

        return details;
    }

    // Categorized channels
    (structure.categories || []).forEach(cat => {
        const group = buildGroup(cat.name, cat.channels || []);
        if (group) list.appendChild(group);
    });

    // Uncategorized channels
    if ((structure.uncategorized || []).length > 0) {
        const group = buildGroup('Uncategorized', structure.uncategorized);
        if (group) list.appendChild(group);
    }
}

/**
 * appendBroadcastResult(channelId, ok, name, error)
 * Appends a result row to #broadcast-results.
 * Uses textContent — XSS mitigation T-6-04-XSS (channel names are untrusted).
 */
function appendBroadcastResult(channelId, ok, name, error) {
    const container = document.getElementById('broadcast-results');
    if (!container) return;

    const row = document.createElement('div');
    row.className = ok ? 'broadcast-result-ok' : 'broadcast-result-err';
    if (ok) {
        row.textContent = '✓ #' + name;
    } else {
        row.textContent = '✗ #' + name + (error ? ': ' + error : '');
    }
    container.appendChild(row);
}

/**
 * initBroadcastManager()
 * Wires the #broadcast-select-all toggle for the Broadcast tab.
 */
function initBroadcastManager() {
    const selectAllBtn = document.getElementById('broadcast-select-all');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const checkboxes = [...document.querySelectorAll('.broadcast-channel-cb')];
            const anyUnchecked = checkboxes.some(cb => !cb.checked);
            checkboxes.forEach(cb => { cb.checked = anyUnchecked; });
            selectAllBtn.textContent = anyUnchecked ? 'Deselect All' : 'Select All';
        });
    }
}

// ── INIT ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // 1. Panel router (must be first)
    initPanelRouter();

    // 2. Guild switcher + load guilds from API
    initGuildSwitcher();
    loadGuilds();

    // Only run authenticated features if user is logged in
    const isLoggedIn = !!document.querySelector('.user-info img, .user-info span');

    if (isLoggedIn) {
        // 3. Embed constructor
        fetchGuilds();
        loadTemplates();
        updatePreview();
        initEmbedForm();

        // 4. SSE log stream
        initLogStream();

        // 5. Server visualizer
        initVisualizer();

        // 6. Manual controls (Phase 6)
        initManualControls();

        // 7. Channel manager (Phase 6 — Plan 06-01)
        initChannelManager();

        // 8. Role manager (Phase 6 — Plan 06-02)
        initRoleManager();

        // 9. Permission override manager (Phase 6 — Plan 06-03)
        initPermissionManager();

        // 10. Broadcast multi-channel manager (Phase 6 — Plan 06-04)
        initBroadcastManager();
    }
});
