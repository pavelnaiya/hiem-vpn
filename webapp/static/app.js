const { listen } = window.__TAURI__ ? window.__TAURI__.event : { listen: () => {} };
const { readTextFile, BaseDirectory } = window.__TAURI__ ? window.__TAURI__.fs : { readTextFile: null };

document.addEventListener('DOMContentLoaded', async () => {
    // --- UI Elements ---
    const viewHome = document.getElementById('viewHome');
    const viewSettings = document.getElementById('viewSettings');
    const navSettingsBtn = document.getElementById('navSettingsBtn');
    const navBackBtn = document.getElementById('navBackBtn');
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const homeLink = document.getElementById('homeLink');
    const mainConnectBtn = document.getElementById('mainConnectBtn');
    const proxyStatus = document.getElementById('proxyStatus');
    const statusText = proxyStatus.querySelector('.text');
    const activeConnectionPanel = document.getElementById('activeConnectionPanel');
    const currentIpEl = document.getElementById('currentIp');
    const locationEl = document.getElementById('currentLocation');
    const flagIconEl = document.getElementById('flagIcon');
    const rotateBtn = document.getElementById('rotateBtn');
    const homeExitNode = document.getElementById('homeExitNode');
    const homeKillSwitch = document.getElementById('homeKillSwitch');
    
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    const settingStartLaunch = document.getElementById('settingStartLaunch');
    const settingAutoConnect = document.getElementById('settingAutoConnect');
    const freqInput = document.getElementById('rotationFrequency');
    const freqDisplay = document.getElementById('frequencyValue');
    const settingRotationJitter = document.getElementById('settingRotationJitter');
    
    // Routing Cards
    const routingModeInput = document.getElementById('routingMode');
    const routingCards = document.querySelectorAll('.routing-card');
    const routingDomainsWhitelist = document.getElementById('routingDomainsWhitelist');
    const routingDomainsBlacklist = document.getElementById('routingDomainsBlacklist');
    
    const settingAutoWifi = document.getElementById('settingAutoWifi');
    const settingKillSwitch = document.getElementById('settingKillSwitch');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
    const settingsMsg = document.getElementById('settingsMsg');
    const appLogo = document.getElementById('appLogo');

    // --- State ---
    let currentState = 'Disconnected';
    let isRotating = false;
    let apiToken = '';
    const API_URL = 'http://127.0.0.1:8080/api/v1';

    // --- Boot & Auth ---
    async function loadApiToken() {
        if (readTextFile) {
            try {
                apiToken = await readTextFile('.hiem/api_token', { dir: BaseDirectory.Home });
                console.log("Loaded API Token from filesystem");
            } catch (err) {
                console.error("Failed to load API Token", err);
            }
        } else {
            console.warn("Running outside Tauri. Using 'dev' token for local testing.");
            apiToken = 'dev';
        }
    }

    const authHeaders = () => {
        return {
            'Content-Type': 'application/json',
            ...(apiToken && { 'Authorization': `Bearer ${apiToken}` })
        };
    };

    // --- Theme Logic ---
    const getSystemTheme = () => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    const currentTheme = localStorage.getItem('theme') || getSystemTheme();
    
    if (currentTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        themeToggleBtn.innerHTML = '<i data-lucide="moon"></i>';
    } else {
        document.documentElement.removeAttribute('data-theme');
        themeToggleBtn.innerHTML = '<i data-lucide="sun"></i>';
    }
    lucide.createIcons();
    
    themeToggleBtn.addEventListener('click', () => {
        const theme = document.documentElement.getAttribute('data-theme');
        if (theme === 'light') {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('theme', 'dark');
            themeToggleBtn.innerHTML = '<i data-lucide="sun"></i>';
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
            localStorage.setItem('theme', 'light');
            themeToggleBtn.innerHTML = '<i data-lucide="moon"></i>';
        }
        lucide.createIcons();
    });

    // --- Navigation ---
    let inSettings = false;
    function toggleSettingsView() {
        if (!inSettings) {
            viewHome.style.display = 'none';
            viewSettings.style.display = 'block';
            navSettingsBtn.innerHTML = '<i data-lucide="x"></i>';
            inSettings = true;
        } else {
            viewSettings.style.display = 'none';
            viewHome.style.display = 'block';
            navSettingsBtn.innerHTML = '<i data-lucide="settings"></i>';
            inSettings = false;
            fetchSettings(); // reset unsaved
        }
        lucide.createIcons();
    }

    navSettingsBtn.addEventListener('click', toggleSettingsView);
    
    if(homeLink) {
        homeLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (inSettings) toggleSettingsView();
        });
    }
    const resetSettingsBtn = document.getElementById('resetSettingsBtn');
    
    if(navBackBtn) navBackBtn.addEventListener('click', toggleSettingsView);
    if(cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', toggleSettingsView);
    
    if(resetSettingsBtn) {
        const dialog = document.getElementById('resetConfirmDialog');
        const confirmBtn = document.getElementById('dialogConfirmBtn');
        const cancelBtn = document.getElementById('dialogCancelBtn');

        resetSettingsBtn.addEventListener('click', () => {
            if (dialog) dialog.showModal();
        });

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                if (dialog) dialog.close();
            });
        }

        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => {
                if (dialog) dialog.close();
                
                freqInput.value = 0;
                homeExitNode.value = "Any";
                updateDropdownUI("Any");
                
                routingModeInput.value = "all";
                routingDomainsWhitelist.value = "";
                routingDomainsBlacklist.value = "";
                
                homeKillSwitch.checked = false;
                settingKillSwitch.checked = false;
                settingStartLaunch.checked = false;
                settingAutoConnect.checked = false;
                settingAutoWifi.checked = false;
                settingRotationJitter.checked = false;
                
                updateFrequencyDisplay();
                updateRoutingCardStates();
                saveSettings(true);
                lucide.createIcons();
            });
        }
    }
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(n => n.classList.remove('active'));
            tabPanes.forEach(t => t.style.display = 'none');
            item.classList.add('active');
            document.getElementById(item.getAttribute('data-tab')).style.display = 'block';
        });
    });

    // --- UI Updaters ---
    function updateFrequencyDisplay() {
        const val = parseInt(freqInput.value);
        if (val === 0) freqDisplay.textContent = 'Never';
        else if (val < 60) freqDisplay.textContent = `${val}s`;
        else freqDisplay.textContent = `${Math.floor(val/60)}m ${val%60}s`;
        
        const max = parseInt(freqInput.max) || 1800;
        const progress = (val / max) * 100;
        freqInput.style.setProperty('--slider-progress', `${progress}%`);
    }
    
    function updateRoutingCardStates() {
        const val = routingModeInput.value;
        routingCards.forEach(card => {
            if (card.getAttribute('data-mode') === val) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
                card.classList.remove('open');
                const body = card.querySelector('.routing-card-body');
                if (body) body.style.display = 'none';
            }
            
            // Update domain counts
            const textarea = card.querySelector('textarea');
            const countSpan = card.querySelector('.domain-count');
            if (textarea && countSpan) {
                const count = textarea.value.split(',').filter(d => d.trim().length > 0).length;
                countSpan.textContent = count;
            }
        });
    }

    routingCards.forEach(card => {
        const header = card.querySelector('.routing-card-header');
        const action = card.querySelector('.routing-card-action');
        const textarea = card.querySelector('textarea');
        
        header.addEventListener('click', () => {
            routingModeInput.value = card.getAttribute('data-mode');
            updateRoutingCardStates();
            saveSettings(true);
        });
        
        if (action) {
            action.addEventListener('click', () => {
                const body = card.querySelector('.routing-card-body');
                const isOpen = card.classList.contains('open');
                if (isOpen) {
                    card.classList.remove('open');
                    body.style.display = 'none';
                } else {
                    card.classList.add('open');
                    body.style.display = 'flex';
                }
            });
        }
        
        if (textarea) {
            textarea.addEventListener('input', () => {
                const countSpan = card.querySelector('.domain-count');
                const count = textarea.value.split(',').filter(d => d.trim().length > 0).length;
                countSpan.textContent = count;
            });
            textarea.addEventListener('blur', () => saveSettings(true));
        }
    });

    freqInput.addEventListener('input', updateFrequencyDisplay);
    freqInput.addEventListener('change', () => saveSettings(true));
    homeKillSwitch.addEventListener('change', () => { settingKillSwitch.checked = homeKillSwitch.checked; saveSettings(true); });
    settingKillSwitch.addEventListener('change', () => { homeKillSwitch.checked = settingKillSwitch.checked; saveSettings(true); });
    settingStartLaunch.addEventListener('change', () => saveSettings(true));
    settingAutoConnect.addEventListener('change', () => saveSettings(true));
    settingAutoWifi.addEventListener('change', () => saveSettings(true));
    settingRotationJitter.addEventListener('change', () => saveSettings(true));

    // --- Server-Sent Events (SSE) ---
    let eventSource = null;

    function connectEventSource() {
        if (eventSource) eventSource.close();
        
        eventSource = new EventSource(`${API_URL}/events?token=${apiToken}`);
        
        eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                handleServerEvent(data);
            } catch (err) {
                console.error("SSE parse error", err);
            }
        };

        eventSource.onerror = (e) => {
            console.error("SSE Connection Error", e);
            eventSource.close();
        };
    }

    function handleServerEvent(data) {
        if (data.type === 'ping') return;
        
        if (data.type === 'bootstrap') {
            updateUIState('Bootstrapping', data.progress);
        } else if (data.type === 'status') {
            updateUIState(data.status, null, data);
        } else if (data.type === 'error') {
            updateUIState('Error');
            console.error("Backend Error:", data.message);
        } else if (data.type === 'state_transition') {
            updateUIState(data.state);
        }
    }

    function updateUIState(state, progress = null, meta = null) {
        currentState = state;
        
        if (state === 'Disconnected') {
            mainConnectBtn.className = 'connect-btn';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Connect';
            proxyStatus.className = 'status-badge error';
            proxyStatus.style.borderColor = '';
            statusText.textContent = 'Disconnected';
            activeConnectionPanel.style.opacity = '0';
            activeConnectionPanel.style.transform = 'translateY(10px)';
            setTimeout(() => activeConnectionPanel.style.display = 'none', 300);
            
        } else if (state === 'Connecting') {
            mainConnectBtn.className = 'connect-btn connecting';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Cancel';
            proxyStatus.className = 'status-badge working';
            proxyStatus.style.borderColor = 'var(--primary)';
            statusText.textContent = meta && meta.message ? meta.message : 'Connecting...';
            
        } else if (state === 'Bootstrapping') {
            mainConnectBtn.className = 'connect-btn connecting';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Cancel';
            proxyStatus.className = 'status-badge working';
            proxyStatus.style.borderColor = 'var(--primary)';
            statusText.textContent = `Bootstrapping (${progress}%)...`;
            
        } else if (state === 'Working' || state === 'Connected') {
            mainConnectBtn.className = 'connect-btn connected';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Connected';
            proxyStatus.className = 'status-badge working';
            proxyStatus.style.borderColor = '';
            statusText.textContent = 'Active & Secure';
            activeConnectionPanel.style.display = 'block';
            setTimeout(() => {
                activeConnectionPanel.style.opacity = '1';
                activeConnectionPanel.style.transform = 'translateY(0)';
            }, 50);
            
            if (meta) {
                currentIpEl.innerHTML = meta.ip;
                locationEl.textContent = `${meta.country}`;
                if (meta.countryCode) {
                    flagIconEl.src = `https://flagcdn.com/24x18/${meta.countryCode.toLowerCase()}.png`;
                    flagIconEl.style.display = 'inline';
                }
            }
            
        } else if (state === 'Disconnecting') {
            mainConnectBtn.className = 'connect-btn connecting';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Cancel';
            proxyStatus.className = 'status-badge working';
            statusText.textContent = 'Disconnecting...';
            
        } else if (state === 'Error') {
            mainConnectBtn.className = 'connect-btn';
            mainConnectBtn.querySelector('.btn-text').textContent = 'Connect';
            proxyStatus.className = 'status-badge error';
            statusText.textContent = 'Connection Error';
            activeConnectionPanel.style.opacity = '0';
            setTimeout(() => activeConnectionPanel.style.display = 'none', 300);
        }
    }

    // --- Custom Dropdown Logic ---
    const customDropdownTrigger = document.getElementById('customLocationDropdownTrigger');
    const customDropdownMenu = document.getElementById('customLocationDropdownMenu');
    const dropdownTriggerTitle = document.getElementById('dropdownTriggerTitle');
    const dropdownTriggerFlag = document.getElementById('dropdownTriggerFlag');
    const dropdownItems = customDropdownMenu.querySelectorAll('.dropdown-item');
    
    function updateDropdownUI(value) {
        dropdownItems.forEach(i => i.classList.remove('selected'));
        const selectedItem = Array.from(dropdownItems).find(i => i.getAttribute('data-value') === value);
        if (selectedItem) {
            selectedItem.classList.add('selected');
            homeExitNode.value = value;
            dropdownTriggerTitle.textContent = selectedItem.getAttribute('data-name');
            dropdownTriggerFlag.src = `https://flagcdn.com/24x18/${selectedItem.getAttribute('data-flag')}.png`;
        }
    }

    customDropdownTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        customDropdownTrigger.classList.toggle('open');
        customDropdownMenu.parentElement.classList.toggle('open');
    });

    dropdownItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            const value = item.getAttribute('data-value');
            updateDropdownUI(value);
            customDropdownTrigger.classList.remove('open');
            customDropdownMenu.parentElement.classList.remove('open');
            saveSettings(true); // Auto-save on selection
        });
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
        customDropdownTrigger.classList.remove('open');
        customDropdownMenu.parentElement.classList.remove('open');
    });

    // --- API Interactions ---
    async function fetchSettings() {
        try {
            const res = await fetch(`${API_URL}/settings`, { headers: authHeaders() });
            if (!res.ok) throw new Error("Unauthorized");
            const data = await res.json();
            
            freqInput.value = data.frequency_seconds;
            homeExitNode.value = data.active_profile.exit_node;
            updateDropdownUI(data.active_profile.exit_node); // Update the visual UI of the dropdown
            
            routingModeInput.value = data.active_profile.routing_mode;
            
            if (data.active_profile.routing_mode === 'whitelist') {
                routingDomainsWhitelist.value = data.active_profile.routing_domains;
            } else if (data.active_profile.routing_mode === 'blacklist') {
                routingDomainsBlacklist.value = data.active_profile.routing_domains;
            }
            
            homeKillSwitch.checked = data.kill_switch;
            settingKillSwitch.checked = data.kill_switch;
            settingStartLaunch.checked = data.start_on_launch;
            settingAutoConnect.checked = data.auto_connect;
            settingAutoWifi.checked = data.auto_wifi || false;
            settingRotationJitter.checked = data.rotation_jitter || false;
            
            updateFrequencyDisplay();
            updateRoutingCardStates();
            lucide.createIcons();
        } catch (err) {
            console.error("Failed to load settings", err);
        }
    }

    async function toggleConnection() {
        if (currentState === 'Connecting' || currentState === 'Bootstrapping' || currentState === 'Connected') {
            updateUIState('Disconnecting');
            try { await fetch(`${API_URL}/disconnect`, { method: 'POST', headers: authHeaders() }); } catch(e) {}
        } else {
            updateUIState('Connecting');
            try { await fetch(`${API_URL}/connect`, { method: 'POST', headers: authHeaders() }); } catch(e) {}
        }
    }
    
    mainConnectBtn.addEventListener('click', toggleConnection);

    async function forceRotate() {
        if (currentState !== 'Connected' && currentState !== 'Working' || isRotating) return;
        isRotating = true;
        rotateBtn.classList.add('spinning');
        rotateBtn.disabled = true;
        currentIpEl.innerHTML = '<span style="font-size: 1.2rem; color: var(--text-secondary);">Acquiring new IP...</span>';
        
        try {
            await fetch(`${API_URL}/rotate`, { method: 'POST', headers: authHeaders() });
        } catch (err) {}
        setTimeout(() => {
            rotateBtn.classList.remove('spinning');
            rotateBtn.disabled = false;
            isRotating = false;
        }, 1000);
    }
    rotateBtn.addEventListener('click', forceRotate);

    async function saveSettings(silent = false) {
        if(!silent) {
            saveSettingsBtn.innerHTML = '<i data-lucide="loader" class="lucide spinning"></i> Saving...';
            saveSettingsBtn.disabled = true;
            lucide.createIcons();
        }
        
        const payload = {
            version: 1,
            frequency_seconds: parseInt(freqInput.value),
            kill_switch: settingKillSwitch.checked,
            start_on_launch: settingStartLaunch.checked,
            auto_connect: settingAutoConnect.checked,
            auto_wifi: settingAutoWifi.checked,
            rotation_jitter: settingRotationJitter.checked,
            active_profile: {
                name: "Default",
                exit_node: homeExitNode.value,
                routing_mode: routingModeInput.value,
                routing_domains: routingModeInput.value === 'whitelist' ? routingDomainsWhitelist.value : (routingModeInput.value === 'blacklist' ? routingDomainsBlacklist.value : '')
            }
        };

        try {
            const res = await fetch(`${API_URL}/settings`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (!silent && data.success) {
                settingsMsg.textContent = 'Settings saved successfully!';
                settingsMsg.className = 'success-msg show';
                setTimeout(() => settingsMsg.className = 'success-msg', 3000);
            }
            
            if (window.__TAURI__) {
                const { enable, disable } = window.__TAURI__.autostart;
                payload.start_on_launch ? await enable() : await disable();
            }
        } catch (err) {
            console.error(err);
        } finally {
            if(!silent) {
                saveSettingsBtn.innerHTML = '<i data-lucide="save"></i> Save Settings';
                saveSettingsBtn.disabled = false;
                lucide.createIcons();
            }
        }
    }
    saveSettingsBtn.addEventListener('click', () => saveSettings(false));

    // --- Tauri Rust Event Listeners ---
    if (window.__TAURI__) {
        listen('backend-crashed', (e) => {
            console.warn(`Backend crashed (${e.payload} times). Waiting for Rust core to respawn sidecar...`);
            if (eventSource) eventSource.close();
            setTimeout(connectEventSource, 4000); // Reconnect SSE stream after respawn
            updateUIState('Disconnected');
        });

        listen('backend-fatal', () => {
            alert("FATAL ERROR: The backend proxy engine has crashed continuously and cannot be restarted. Please check the logs.");
            updateUIState('Error');
        });
    }

    // --- Init ---
    await loadApiToken();
    connectEventSource();
    fetchSettings();
});
