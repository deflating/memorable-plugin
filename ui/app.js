/* ============================================
   Memorable — Application Logic
   ============================================ */

(function () {
  'use strict';

  // ---- Default options for toggle/switch sections ----
  // These are the built-in options. Users can add custom ones.
  const DEFAULT_COGNITIVE_OPTIONS = [
    { key: 'adhd', label: 'ADHD' },
    { key: 'autism', label: 'Autism' },
    { key: 'anxiety', label: 'Anxiety' },
    { key: 'depression', label: 'Depression' },
    { key: 'dyslexia', label: 'Dyslexia' },
    { key: 'ocd', label: 'OCD' },
    { key: 'ptsd', label: 'PTSD' },
    { key: 'bipolar', label: 'Bipolar' }
  ];

  const DEFAULT_COMMUNICATION_OPTIONS = [
    { key: 'beDirect', label: 'Be direct', desc: 'Don\'t soften or hedge unnecessarily' },
    { key: 'noSycophancy', label: 'No sycophancy', desc: 'Skip the "great question!" and "absolutely!"' },
    { key: 'matchEnergy', label: 'Match my energy', desc: 'Mirror tone and intensity' },
    { key: 'skipPreamble', label: 'Skip preamble', desc: 'Get to the point, skip disclaimers' },
    { key: 'challengeMe', label: 'Challenge me when I\'m wrong', desc: 'Push back on incorrect assumptions' },
    { key: 'admitUncertainty', label: 'Admit uncertainty', desc: 'Say "I\'m not sure" when appropriate' },
    { key: 'noEmojis', label: 'No emojis', desc: 'Keep responses text-only' },
    { key: 'shortWhenLow', label: 'Short replies when I\'m low', desc: 'Reduce verbosity when energy is low' }
  ];

  const DEFAULT_BEHAVIOR_OPTIONS = [
    { key: 'holdOwnViews', label: 'Hold your own views' },
    { key: 'uncertainWhenAppropriate', label: 'Be uncertain when appropriate' },
    { key: 'rememberContext', label: 'Remember context across conversation' },
    { key: 'askClarifyingQuestions', label: 'Ask clarifying questions' },
    { key: 'adaptToMood', label: 'Adapt to user\'s mood' },
    { key: 'useSharedVocabulary', label: 'Use shared vocabulary' },
    { key: 'showWorkingProcess', label: 'Show working/thinking process' },
    { key: 'provideSources', label: 'Provide sources when possible' }
  ];

  const DEFAULT_WHEN_LOW_OPTIONS = [
    { key: 'shorterReplies', label: 'Keep replies shorter', desc: 'Reduce output length' },
    { key: 'noReframing', label: 'Don\'t reframe or silver-lining', desc: 'Avoid turning negatives into positives' },
    { key: 'noForcedPositivity', label: 'No forced positivity', desc: 'Skip cheerfulness that isn\'t warranted' },
    { key: 'justAcknowledge', label: 'Just acknowledge, don\'t fix', desc: 'Sometimes people need to be heard' },
    { key: 'nameConstraints', label: 'Name constraints honestly', desc: 'Say what you can\'t do instead of deflecting' },
    { key: 'offerSpace', label: 'Offer space when needed', desc: 'Recognize when to step back' }
  ];

  const DEFAULT_TECH_STYLE_OPTIONS = [
    { key: 'avoidOverEngineering', label: 'Avoid over-engineering', desc: 'Keep solutions proportional to the problem' },
    { key: 'preferSimpleSolutions', label: 'Prefer simple solutions', desc: 'Simplicity over cleverness' },
    { key: 'explainTradeoffs', label: 'Explain tradeoffs', desc: 'Show what you\'re giving up with each choice' },
    { key: 'codeCommentsMinimal', label: 'Minimal code comments', desc: 'Code should be self-documenting' },
    { key: 'suggestTests', label: 'Suggest tests', desc: 'Recommend testing strategies' },
    { key: 'functionalStyle', label: 'Prefer functional style', desc: 'Favor immutability and pure functions' },
    { key: 'typeAnnotations', label: 'Include type annotations', desc: 'Add types to code examples' }
  ];

  const DEFAULT_TRAIT_OPTIONS = [
    { key: 'warmth', label: 'Warmth', endpoints: ['Clinical', 'Very warm'] },
    { key: 'directness', label: 'Directness', endpoints: ['Gentle', 'Blunt'] },
    { key: 'humor', label: 'Humor', endpoints: ['Serious', 'Playful'] },
    { key: 'formality', label: 'Formality', endpoints: ['Casual', 'Formal'] },
    { key: 'verbosity', label: 'Verbosity', endpoints: ['Terse', 'Detailed'] }
  ];

  // ---- Presets ----
  const PRESETS = {
    technical: {
      label: 'Technical / Coding',
      userSections: ['identity', 'about', 'communication', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'traits', 'behaviors', 'avoid', 'tech-style', 'agent-custom']
    },
    research: {
      label: 'Research / Academic',
      userSections: ['identity', 'about', 'values', 'communication', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'traits', 'behaviors', 'avoid', 'agent-custom']
    },
    personal: {
      label: 'Personal / Companion',
      userSections: ['identity', 'about', 'cognitive', 'values', 'communication', 'people', 'user-custom'],
      agentSections: ['agent-name', 'traits', 'behaviors', 'avoid', 'when-low', 'agent-custom']
    },
    custom: {
      label: 'Custom',
      userSections: ['identity', 'about', 'cognitive', 'values', 'communication', 'people', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'traits', 'behaviors', 'avoid', 'when-low', 'tech-style', 'agent-custom']
    }
  };

  // ---- Anchor Depth Levels ----
  const ANCHOR_DEPTHS = [
    { key: 'full', label: 'Full', desc: 'All content' },
    { key: 'detailed', label: 'Detailed', desc: 'Level 1 + 2 headings' },
    { key: 'summary', label: 'Summary', desc: 'Level 1 headings only' },
    { key: 'none', label: 'None', desc: 'Excluded from context' }
  ];

  // ---- Materiality: Content Density ----
  function getSectionDensity(sectionId) {
    const u = state.user;
    const a = state.agent;
    switch (sectionId) {
      case 'identity': {
        const filled = ['name', 'age', 'location', 'pronouns'].filter(k => u.identity[k] && u.identity[k].trim()).length;
        return filled === 0 ? 'sketch' : filled <= 2 ? 'forming' : 'substantial';
      }
      case 'about':
        return !u.about || !u.about.trim() ? 'sketch' : u.about.trim().length < 100 ? 'forming' : 'substantial';
      case 'cognitive': {
        const count = Object.values(u.cognitiveActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 2 ? 'forming' : 'substantial';
      }
      case 'values':
        return u.values.length === 0 ? 'sketch' : u.values.length <= 2 ? 'forming' : 'substantial';
      case 'communication': {
        const count = Object.values(u.communicationActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 3 ? 'forming' : 'substantial';
      }
      case 'people':
        return u.people.length === 0 ? 'sketch' : u.people.length <= 2 ? 'forming' : 'substantial';
      case 'projects':
        return u.projects.length === 0 ? 'sketch' : u.projects.length === 1 ? 'forming' : 'substantial';
      case 'user-custom':
        return u.customSections.length === 0 ? 'sketch' : u.customSections.length === 1 ? 'forming' : 'substantial';
      case 'agent-name':
        return !a.name || !a.name.trim() ? 'sketch' : 'forming';
      case 'traits': {
        const changed = a.traitOptions.filter(k => (a.traits[k] || 50) !== 50).length;
        return changed === 0 ? 'sketch' : changed <= 2 ? 'forming' : 'substantial';
      }
      case 'behaviors': {
        const count = Object.values(a.behaviorsActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 3 ? 'forming' : 'substantial';
      }
      case 'avoid':
        return a.avoid.length === 0 ? 'sketch' : a.avoid.length <= 2 ? 'forming' : 'substantial';
      case 'when-low': {
        const count = Object.values(a.whenLowActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 2 ? 'forming' : 'substantial';
      }
      case 'tech-style': {
        const count = Object.values(a.techStyleActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 2 ? 'forming' : 'substantial';
      }
      case 'agent-custom':
        return a.customSections.length === 0 ? 'sketch' : a.customSections.length === 1 ? 'forming' : 'substantial';
      default:
        return 'sketch';
    }
  }

  // Track whether we've done first-load animation
  let _firstLoadAnimated = false;

  function applySectionFadeIn(container) {
    if (_firstLoadAnimated) return;
    _firstLoadAnimated = true;
    const sections = container.querySelectorAll('.section');
    sections.forEach((section, i) => {
      section.classList.add('section-fade-in');
      section.style.animationDelay = (i * 80) + 'ms';
    });
  }

  // ---- Theme ----
  function applyTheme() {
    const pref = localStorage.getItem('memorable-theme') || 'auto';
    if (pref === 'dark' || (pref === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }
  applyTheme();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem('memorable-theme') || 'auto') === 'auto') applyTheme();
  });

  // ---- State ----
  const state = {
    activeFile: 'user',
    activeView: 'form',
    markdownSubMode: 'plain',
    preset: 'custom',
    // Context files
    files: [],          // [{id, name, content, anchorDepth, projectTag}]
    activeFileId: null,  // which file is selected in Files tab
    tokenBudgetExpanded: false,
    // Which sections are enabled (toggle on/off)
    enabledSections: {
      'identity': true, 'about': true, 'cognitive': true, 'values': true,
      'communication': true, 'people': true, 'projects': true, 'user-custom': true,
      'agent-name': true, 'traits': true, 'behaviors': true, 'avoid': true,
      'when-low': true, 'tech-style': true, 'agent-custom': true
    },
    collapsedSections: {},
    user: {
      identity: { name: '', age: '', location: '', pronouns: '' },
      about: '',
      // Now stores arrays: cognitiveOptions (all available) and cognitiveActive (which are on)
      cognitiveOptions: DEFAULT_COGNITIVE_OPTIONS.map(o => o.key),
      cognitiveLabels: {},  // custom key -> label mapping for non-default items
      cognitiveActive: {},
      values: [
        { higher: 'Accuracy', lower: 'Comfort' },
        { higher: 'Depth', lower: 'Breadth' },
        { higher: 'Clarity', lower: 'Reassurance' }
      ],
      communicationOptions: DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key),
      communicationLabels: {},
      communicationDescs: {},
      communicationActive: {},
      people: [],
      projects: [],
      customSections: []
    },
    agent: {
      name: '',
      traitOptions: DEFAULT_TRAIT_OPTIONS.map(o => o.key),
      traitLabels: {},
      traitEndpoints: {},
      traits: {
        warmth: 60, directness: 75, humor: 40, formality: 30, verbosity: 40
      },
      behaviorOptions: DEFAULT_BEHAVIOR_OPTIONS.map(o => o.key),
      behaviorLabels: {},
      behaviorsActive: {},
      avoid: [],
      whenLowOptions: DEFAULT_WHEN_LOW_OPTIONS.map(o => o.key),
      whenLowLabels: {},
      whenLowDescs: {},
      whenLowActive: {},
      techStyleOptions: DEFAULT_TECH_STYLE_OPTIONS.map(o => o.key),
      techStyleLabels: {},
      techStyleDescs: {},
      techStyleActive: {},
      customSections: []
    },
    // --- New app-level state ---
    activePage: 'dashboard',  // which page is shown: dashboard, configure, memories, settings
    memoriesSubTab: 'episodic', // memories sub-tab: episodic, working, semantic
    notesCache: [],           // cached session notes from API
    settingsCache: null,      // cached settings from API
    statusCache: null,        // cached status from API
    serverConnected: false,   // whether server is reachable
    onboardingStep: 1,        // dashboard onboarding wizard step
    seedSync: {
      deploymentKnown: false, // whether we have a deployed baseline to compare against
      deployedHash: "",       // hash-like fingerprint of deployed user+agent seeds
      deployedAt: "",         // local timestamp of most recent deploy action
    },
  };

  // Keep a markdown cache to track manual edits
  let markdownCache = { user: '', agent: '' };
  const CONFIG_HISTORY_LIMIT = 100;
  const configHistory = {
    undo: [],
    redo: [],
    current: null,
    applying: false
  };

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function _seedFingerprint(userMd, agentMd) {
    const u = String(userMd || "");
    const a = String(agentMd || "");
    return `${u.length}:${u}\n@@\n${a.length}:${a}`;
  }

  function _currentSeedFingerprint() {
    return _seedFingerprint(generateUserMarkdown(), generateAgentMarkdown());
  }

  function _hasPendingSeedDraft() {
    if (!state.seedSync || !state.seedSync.deploymentKnown) return false;
    return _currentSeedFingerprint() !== state.seedSync.deployedHash;
  }

  function _seedStatusMeta() {
    if (!state.seedSync || !state.seedSync.deploymentKnown) {
      return {
        className: 'seed-sync-draft',
        text: 'Draft only',
        title: 'No deployed baseline found yet. Deploy to apply seeds for session start.',
      };
    }
    if (_hasPendingSeedDraft()) {
      return {
        className: 'seed-sync-pending',
        text: 'Draft changes not deployed',
        title: 'Local draft differs from deployed seed files. Deploy to apply runtime changes.',
      };
    }
    if (state.seedSync.deployedAt) {
      const d = new Date(state.seedSync.deployedAt);
      const stamp = Number.isNaN(d.getTime())
        ? 'just now'
        : d.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit'
        });
      return {
        className: 'seed-sync-deployed',
        text: `Deployed ${stamp}`,
        title: 'Draft and deployed seeds are in sync.',
      };
    }
    return {
      className: 'seed-sync-deployed',
      text: 'Deployed',
      title: 'Draft and deployed seeds are in sync.',
    };
  }

  function buildConfigSnapshot() {
    return JSON.stringify({
      activeFile: state.activeFile,
      activeView: state.activeView,
      markdownSubMode: state.markdownSubMode,
      preset: state.preset,
      enabledSections: state.enabledSections,
      collapsedSections: state.collapsedSections,
      user: state.user,
      agent: state.agent
    });
  }

  function applyConfigSnapshot(serialized) {
    const next = JSON.parse(serialized);
    state.activeFile = next.activeFile || 'user';
    state.activeView = next.activeView || 'form';
    state.markdownSubMode = next.markdownSubMode || 'plain';
    state.preset = next.preset || 'custom';
    state.enabledSections = next.enabledSections ? cloneJson(next.enabledSections) : {};
    state.collapsedSections = next.collapsedSections ? cloneJson(next.collapsedSections) : {};
    if (next.user) state.user = cloneJson(next.user);
    if (next.agent) state.agent = cloneJson(next.agent);
    migrateState();
  }

  function updateHistoryControls() {
    const undoBtn = document.getElementById('seed-undo-btn');
    const redoBtn = document.getElementById('seed-redo-btn');
    if (undoBtn) {
      undoBtn.disabled = configHistory.undo.length === 0;
    }
    if (redoBtn) {
      redoBtn.disabled = configHistory.redo.length === 0;
    }
  }

  function resetConfigHistory() {
    configHistory.undo = [];
    configHistory.redo = [];
    configHistory.current = buildConfigSnapshot();
    updateHistoryControls();
  }

  function recordConfigHistory() {
    if (configHistory.applying) return;
    const current = buildConfigSnapshot();
    if (configHistory.current === null) {
      configHistory.current = current;
      updateHistoryControls();
      return;
    }
    if (current === configHistory.current) {
      updateHistoryControls();
      return;
    }

    configHistory.undo.push(configHistory.current);
    if (configHistory.undo.length > CONFIG_HISTORY_LIMIT) {
      configHistory.undo.shift();
    }
    configHistory.current = current;
    configHistory.redo = [];
    updateHistoryControls();
  }

  function undoConfigChange() {
    if (!configHistory.undo.length) return false;
    const previous = configHistory.undo.pop();
    const current = buildConfigSnapshot();
    configHistory.redo.push(current);
    if (configHistory.redo.length > CONFIG_HISTORY_LIMIT) {
      configHistory.redo.shift();
    }
    configHistory.current = previous;
    configHistory.applying = true;
    try {
      applyConfigSnapshot(previous);
      render();
    } finally {
      configHistory.applying = false;
    }
    updateHistoryControls();
    return true;
  }

  function redoConfigChange() {
    if (!configHistory.redo.length) return false;
    const next = configHistory.redo.pop();
    const current = buildConfigSnapshot();
    configHistory.undo.push(current);
    if (configHistory.undo.length > CONFIG_HISTORY_LIMIT) {
      configHistory.undo.shift();
    }
    configHistory.current = next;
    configHistory.applying = true;
    try {
      applyConfigSnapshot(next);
      render();
    } finally {
      configHistory.applying = false;
    }
    updateHistoryControls();
    return true;
  }

  function isEditableTarget(target) {
    if (!target) return false;
    if (target.isContentEditable) return true;
    const tag = target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    return !!target.closest('[contenteditable="true"]');
  }

  // ---- Helper: get label for any option key ----
  function getCognitiveLabel(key) {
    const def = DEFAULT_COGNITIVE_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.user.cognitiveLabels[key] || key;
  }

  function getCommLabel(key) {
    const def = DEFAULT_COMMUNICATION_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.user.communicationLabels[key] || key;
  }

  function getCommDesc(key) {
    const def = DEFAULT_COMMUNICATION_OPTIONS.find(o => o.key === key);
    if (def) return def.desc;
    return state.user.communicationDescs[key] || '';
  }

  function getBehaviorLabel(key) {
    const def = DEFAULT_BEHAVIOR_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.agent.behaviorLabels[key] || key;
  }

  function getWhenLowLabel(key) {
    const def = DEFAULT_WHEN_LOW_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.agent.whenLowLabels[key] || key;
  }

  function getWhenLowDesc(key) {
    const def = DEFAULT_WHEN_LOW_OPTIONS.find(o => o.key === key);
    if (def) return def.desc;
    return state.agent.whenLowDescs[key] || '';
  }

  function getTechLabel(key) {
    const def = DEFAULT_TECH_STYLE_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.agent.techStyleLabels[key] || key;
  }

  function getTechDesc(key) {
    const def = DEFAULT_TECH_STYLE_OPTIONS.find(o => o.key === key);
    if (def) return def.desc;
    return state.agent.techStyleDescs[key] || '';
  }

  function getTraitLabel(key) {
    const def = DEFAULT_TRAIT_OPTIONS.find(o => o.key === key);
    if (def) return def.label;
    return state.agent.traitLabels[key] || key;
  }

  function getTraitEndpoints(key) {
    const def = DEFAULT_TRAIT_OPTIONS.find(o => o.key === key);
    if (def) return def.endpoints;
    return state.agent.traitEndpoints[key] || ['Low', 'High'];
  }

  function isDefaultCognitive(key) { return DEFAULT_COGNITIVE_OPTIONS.some(o => o.key === key); }
  function isDefaultComm(key) { return DEFAULT_COMMUNICATION_OPTIONS.some(o => o.key === key); }
  function isDefaultBehavior(key) { return DEFAULT_BEHAVIOR_OPTIONS.some(o => o.key === key); }
  function isDefaultWhenLow(key) { return DEFAULT_WHEN_LOW_OPTIONS.some(o => o.key === key); }
  function isDefaultTech(key) { return DEFAULT_TECH_STYLE_OPTIONS.some(o => o.key === key); }
  function isDefaultTrait(key) { return DEFAULT_TRAIT_OPTIONS.some(o => o.key === key); }

  // ---- Debounce ----
  function debounce(fn, ms) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  // ---- Token Estimation ----
  function estimateTokens(text) {
    if (!text) return 0;
    return Math.ceil(text.length / 4);
  }

  function getFileTokens(file) {
    if (!file || !file.content) return 0;
    if (file.anchorDepth === 'none') return 0;
    if (file.anchorDepth === 'summary') {
      // Only level 1 headings
      const lines = file.content.split('\n');
      const kept = lines.filter(l => /^#(?!#)\s+/.test(l));
      return estimateTokens(kept.join('\n'));
    }
    if (file.anchorDepth === 'detailed') {
      // Level 1 + 2 headings and their immediate content
      const lines = file.content.split('\n');
      const kept = [];
      let include = false;
      let depth = 0;
      for (const line of lines) {
        if (/^#(?!#)\s+/.test(line)) { include = true; depth = 1; kept.push(line); }
        else if (/^##(?!#)\s+/.test(line)) { include = true; depth = 2; kept.push(line); }
        else if (/^###/.test(line)) { include = false; }
        else if (include) { kept.push(line); }
      }
      return estimateTokens(kept.join('\n'));
    }
    // full
    return estimateTokens(file.content);
  }

  function getTotalFileTokens() {
    return state.files.reduce((sum, f) => sum + getFileTokens(f), 0);
  }

  function generateFileId() {
    return 'f_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function formatTokens(n) {
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
  }

  function formatRelativeTime(iso) {
    if (!iso) return 'Never';
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return 'Unknown';
    const diffSec = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000));
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)}d ago`;
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  function formatDuration(seconds) {
    const s = Number(seconds || 0);
    if (!Number.isFinite(s) || s <= 0) return '0m';
    if (s < 60) return `${Math.round(s)}s`;
    if (s < 3600) return `${Math.round(s / 60)}m`;
    if (s < 86400) return `${Math.round(s / 3600)}h`;
    return `${Math.round(s / 86400)}d`;
  }

  // ---- Toast ----
  function showToast(message, type = '') {
    const el = document.getElementById('toast');
    el.textContent = message;
    el.className = 'toast' + (type ? ' ' + type : '');
    el.offsetHeight;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 2200);
  }

  // ---- Save Indicator ----
  let saveStateTimer = null;

  function setSaveState(newState) {
    document.querySelectorAll('.save-indicator').forEach(el => {
      clearTimeout(saveStateTimer);
      el.className = 'save-indicator save-state-' + newState;

      if (newState === 'idle') {
        el.innerHTML = '<span class="dot"></span> Auto-save on';
      } else if (newState === 'saving') {
        el.innerHTML = '<span class="dot saving-pulse"></span> Saving\u2026';
      } else if (newState === 'saved') {
        el.innerHTML = '<span class="dot saved-dot"></span> Saved';
        saveStateTimer = setTimeout(() => setSaveState('idle'), 2000);
      } else if (newState === 'error') {
        el.innerHTML = '<span class="dot error-dot"></span> Save failed <a href="#" class="save-retry-link" onclick="event.preventDefault(); window.memorableApp.retrySave();">Retry</a>';
      }
    });
  }

  // ---- Make a safe key from a label ----
  function labelToKey(label) {
    return label.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/(^_|_$)/g, '') || ('custom_' + Date.now());
  }

  // ---- Markdown Generation ----
  function generateUserMarkdown() {
    const u = state.user;
    const sec = state.enabledSections;
    let md = '';

    // Identity
    if (sec['identity']) {
      const hasIdentity = u.identity.name || u.identity.age || u.identity.location || u.identity.pronouns;
      if (hasIdentity) {
        md += `# ${u.identity.name || 'User Profile'}\n\n`;
        const details = [];
        if (u.identity.age) details.push(`**Age:** ${u.identity.age}`);
        if (u.identity.location) details.push(`**Location:** ${u.identity.location}`);
        if (u.identity.pronouns) details.push(`**Pronouns:** ${u.identity.pronouns}`);
        if (details.length) md += details.join(' | ') + '\n\n';
      } else {
        md += '# User Profile\n\n';
      }
    } else {
      md += '# User Profile\n\n';
    }

    // About
    if (sec['about'] && u.about.trim()) {
      md += `## About\n\n${u.about.trim()}\n\n`;
    }

    // Cognitive style
    if (sec['cognitive']) {
      const activeCog = u.cognitiveOptions.filter(k => u.cognitiveActive[k]).map(k => getCognitiveLabel(k));
      if (activeCog.length) {
        md += `## Cognitive Style\n\n${activeCog.join(', ')}\n\n`;
      }
    }

    // Values
    if (sec['values']) {
      const activeValues = u.values.filter(v => v.higher.trim() || v.lower.trim());
      if (activeValues.length) {
        md += '## Values\n\n';
        activeValues.forEach(v => {
          md += `- ${v.higher.trim() || '...'} > ${v.lower.trim() || '...'}\n`;
        });
        md += '\n';
      }
    }

    // Communication
    if (sec['communication']) {
      const commPrefs = u.communicationOptions.filter(k => u.communicationActive[k]).map(k => getCommLabel(k));
      if (commPrefs.length) {
        md += '## Communication Preferences\n\n';
        commPrefs.forEach(p => { md += `- ${p}\n`; });
        md += '\n';
      }
    }

    // People
    if (sec['people'] && u.people.length) {
      md += '## People\n\n';
      u.people.forEach(p => {
        md += `### ${p.name || 'Unnamed'}`;
        if (p.relationship) md += ` (${p.relationship})`;
        md += '\n';
        if (p.notes) md += `${p.notes}\n`;
        md += '\n';
      });
    }

    // Projects
    if (sec['projects'] && u.projects.length) {
      md += '## Projects\n\n';
      u.projects.forEach(p => {
        md += `### ${p.name || 'Unnamed'}`;
        if (p.status) md += ` [${p.status}]`;
        md += '\n';
        if (p.description) md += `${p.description}\n`;
        md += '\n';
      });
    }

    // Custom sections
    if (sec['user-custom']) {
      u.customSections.forEach(s => {
        if (s.title || s.content) {
          md += `## ${s.title || 'Untitled Section'}\n\n`;
          if (s.content) md += `${s.content}\n\n`;
        }
      });
    }

    return md.trimEnd() + '\n';
  }

  function generateAgentMarkdown() {
    const a = state.agent;
    const sec = state.enabledSections;
    let md = '';

    if (sec['agent-name']) {
      md += `# ${a.name || 'Agent Profile'}\n\n`;
    } else {
      md += '# Agent Profile\n\n';
    }

    // Character traits
    if (sec['traits']) {
      const traitEntries = a.traitOptions.filter(k => a.traits[k] !== undefined);
      if (traitEntries.length) {
        md += '## Character Traits\n\n';
        traitEntries.forEach(key => {
          const val = a.traits[key] || 50;
          const label = getTraitLabel(key);
          const desc = getTraitDescription(key, val);
          md += `- **${label}:** ${desc} (${val}/100)\n`;
        });
        md += '\n';
      }
    }

    // Behaviors
    if (sec['behaviors']) {
      const activeBehaviors = a.behaviorOptions.filter(k => a.behaviorsActive[k]).map(k => getBehaviorLabel(k));
      if (activeBehaviors.length) {
        md += '## Behaviors\n\n';
        activeBehaviors.forEach(b => { md += `- ${b}\n`; });
        md += '\n';
      }
    }

    // Avoid
    if (sec['avoid'] && a.avoid.length) {
      md += '## Avoid\n\n';
      a.avoid.forEach(item => { md += `- ${item}\n`; });
      md += '\n';
    }

    // When user is low
    if (sec['when-low']) {
      const lowPrefs = a.whenLowOptions.filter(k => a.whenLowActive[k]).map(k => getWhenLowLabel(k));
      if (lowPrefs.length) {
        md += '## When User Is Low\n\n';
        lowPrefs.forEach(p => { md += `- ${p}\n`; });
        md += '\n';
      }
    }

    // Technical style
    if (sec['tech-style']) {
      const techPrefs = a.techStyleOptions.filter(k => a.techStyleActive[k]).map(k => getTechLabel(k));
      if (techPrefs.length) {
        md += '## Technical Style\n\n';
        techPrefs.forEach(p => { md += `- ${p}\n`; });
        md += '\n';
      }
    }

    // Custom sections
    if (sec['agent-custom']) {
      a.customSections.forEach(s => {
        if (s.title || s.content) {
          md += `## ${s.title || 'Untitled Section'}\n\n`;
          if (s.content) md += `${s.content}\n\n`;
        }
      });
    }

    return md.trimEnd() + '\n';
  }

  // ---- Markdown Parsing (markdown -> state) ----
  function parseUserMarkdown(md) {
    const u = state.user;
    u.identity = { name: '', age: '', location: '', pronouns: '' };
    u.about = '';
    u.cognitiveActive = {};
    u.values = [];
    u.communicationActive = {};
    u.people = [];
    u.projects = [];
    u.customSections = [];

    const sections = splitMarkdownSections(md);

    if (sections._title && sections._title !== 'User Profile') {
      u.identity.name = sections._title;
    }

    if (sections._intro) {
      const intro = sections._intro;
      const ageMatch = intro.match(/\*\*Age:\*\*\s*(\d+)/);
      if (ageMatch) u.identity.age = ageMatch[1];
      const locMatch = intro.match(/\*\*Location:\*\*\s*([^|*\n]+)/);
      if (locMatch) u.identity.location = locMatch[1].trim();
      const proMatch = intro.match(/\*\*Pronouns:\*\*\s*([^|*\n]+)/);
      if (proMatch) u.identity.pronouns = proMatch[1].trim();
    }

    if (getSection(sections, 'About')) {
      u.about = getSection(sections, 'About').trim();
      state.enabledSections['about'] = true;
    }

    if (getSection(sections, 'Cognitive Style')) {
      state.enabledSections['cognitive'] = true;
      const cogText = getSection(sections, 'Cognitive Style');
      const items = cogText.split(',').map(s => s.trim()).filter(Boolean);
      items.forEach(item => {
        // Try to match to an existing option
        const existing = u.cognitiveOptions.find(k => getCognitiveLabel(k).toLowerCase() === item.toLowerCase());
        if (existing) {
          u.cognitiveActive[existing] = true;
        } else {
          // Add as custom
          const key = labelToKey(item);
          if (!u.cognitiveOptions.includes(key)) {
            u.cognitiveOptions.push(key);
            u.cognitiveLabels[key] = item;
          }
          u.cognitiveActive[key] = true;
        }
      });
    }

    if (getSection(sections, 'Values')) {
      state.enabledSections['values'] = true;
      const lines = getSection(sections, 'Values').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const match = line.match(/-\s*(.+?)\s*>\s*(.+)/);
        if (match) {
          u.values.push({ higher: match[1].trim(), lower: match[2].trim() });
        }
      });
    }
    if (u.values.length === 0) {
      u.values = [{ higher: '', lower: '' }];
    }

    if (getSection(sections, 'Communication Preferences')) {
      state.enabledSections['communication'] = true;
      const lines = getSection(sections, 'Communication Preferences').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const text = line.replace(/^-\s*/, '').trim();
        if (!text) return;
        const existing = u.communicationOptions.find(k => getCommLabel(k).toLowerCase() === text.toLowerCase());
        if (existing) {
          u.communicationActive[existing] = true;
        } else {
          const key = labelToKey(text);
          if (!u.communicationOptions.includes(key)) {
            u.communicationOptions.push(key);
            u.communicationLabels[key] = text;
            u.communicationDescs[key] = '';
          }
          u.communicationActive[key] = true;
        }
      });
    }

    if (getSection(sections, 'People')) {
      state.enabledSections['people'] = true;
      const peopleText = getSection(sections, 'People');
      const peopleParts = peopleText.split(/^###\s+/m).filter(Boolean);
      peopleParts.forEach(part => {
        const lines = part.split('\n');
        const firstLine = lines[0].trim();
        const relMatch = firstLine.match(/^(.+?)\s*\(([^)]+)\)/);
        const person = {
          name: relMatch ? relMatch[1].trim() : firstLine,
          relationship: relMatch ? relMatch[2].trim() : '',
          notes: lines.slice(1).join('\n').trim()
        };
        if (person.name) u.people.push(person);
      });
    }

    if (getSection(sections, 'Projects')) {
      state.enabledSections['projects'] = true;
      const projText = getSection(sections, 'Projects');
      const projParts = projText.split(/^###\s+/m).filter(Boolean);
      projParts.forEach(part => {
        const lines = part.split('\n');
        const firstLine = lines[0].trim();
        const statusMatch = firstLine.match(/^(.+?)\s*\[([^\]]+)\]/);
        const project = {
          name: statusMatch ? statusMatch[1].trim() : firstLine,
          status: statusMatch ? statusMatch[2].trim() : 'active',
          description: lines.slice(1).join('\n').trim()
        };
        if (project.name) u.projects.push(project);
      });
    }

    const knownSections = ['about', 'cognitive style', 'values', 'communication preferences', 'people', 'projects'];
    Object.entries(sections).forEach(([title, content]) => {
      if (title.startsWith('_')) return;
      if (knownSections.includes(title.toLowerCase())) return;
      u.customSections.push({ title, content: content.trim() });
    });
  }

  function parseAgentMarkdown(md) {
    const a = state.agent;
    a.name = '';
    a.behaviorsActive = {};
    a.avoid = [];
    a.whenLowActive = {};
    a.techStyleActive = {};
    a.customSections = [];

    const sections = splitMarkdownSections(md);

    if (sections._title && sections._title !== 'Agent Profile') {
      a.name = sections._title;
    }

    if (getSection(sections, 'Character Traits')) {
      state.enabledSections['traits'] = true;
      // Reset all traits to 50, then override
      a.traitOptions.forEach(k => { a.traits[k] = 50; });
      const lines = getSection(sections, 'Character Traits').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const match = line.match(/\*\*(.+?):\*\*.*?\((\d+)\/100\)/);
        if (match) {
          const label = match[1].trim();
          const val = parseInt(match[2], 10);
          const existing = a.traitOptions.find(k => getTraitLabel(k).toLowerCase() === label.toLowerCase());
          if (existing) {
            a.traits[existing] = val;
          } else {
            const key = labelToKey(label);
            if (!a.traitOptions.includes(key)) {
              a.traitOptions.push(key);
              a.traitLabels[key] = label;
              a.traitEndpoints[key] = ['Low', 'High'];
            }
            a.traits[key] = val;
          }
        }
      });
    }

    if (getSection(sections, 'Behaviors')) {
      state.enabledSections['behaviors'] = true;
      const lines = getSection(sections, 'Behaviors').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const text = line.replace(/^-\s*/, '').trim();
        if (!text) return;
        const existing = a.behaviorOptions.find(k => getBehaviorLabel(k).toLowerCase() === text.toLowerCase());
        if (existing) {
          a.behaviorsActive[existing] = true;
        } else {
          const key = labelToKey(text);
          if (!a.behaviorOptions.includes(key)) {
            a.behaviorOptions.push(key);
            a.behaviorLabels[key] = text;
          }
          a.behaviorsActive[key] = true;
        }
      });
    }

    if (getSection(sections, 'Avoid')) {
      state.enabledSections['avoid'] = true;
      a.avoid = getSection(sections, 'Avoid').split('\n')
        .filter(l => l.trim().startsWith('-'))
        .map(l => l.replace(/^-\s*/, '').trim())
        .filter(Boolean);
    }

    if (getSection(sections, 'When User Is Low')) {
      state.enabledSections['when-low'] = true;
      const lines = getSection(sections, 'When User Is Low').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const text = line.replace(/^-\s*/, '').trim();
        if (!text) return;
        const existing = a.whenLowOptions.find(k => getWhenLowLabel(k).toLowerCase() === text.toLowerCase());
        if (existing) {
          a.whenLowActive[existing] = true;
        } else {
          const key = labelToKey(text);
          if (!a.whenLowOptions.includes(key)) {
            a.whenLowOptions.push(key);
            a.whenLowLabels[key] = text;
            a.whenLowDescs[key] = '';
          }
          a.whenLowActive[key] = true;
        }
      });
    }

    if (getSection(sections, 'Technical Style')) {
      state.enabledSections['tech-style'] = true;
      const lines = getSection(sections, 'Technical Style').split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const text = line.replace(/^-\s*/, '').trim();
        if (!text) return;
        const existing = a.techStyleOptions.find(k => getTechLabel(k).toLowerCase() === text.toLowerCase());
        if (existing) {
          a.techStyleActive[existing] = true;
        } else {
          const key = labelToKey(text);
          if (!a.techStyleOptions.includes(key)) {
            a.techStyleOptions.push(key);
            a.techStyleLabels[key] = text;
            a.techStyleDescs[key] = '';
          }
          a.techStyleActive[key] = true;
        }
      });
    }

    const knownSections = ['character traits', 'behaviors', 'avoid', 'when user is low', 'technical style'];
    Object.entries(sections).forEach(([title, content]) => {
      if (title.startsWith('_')) return;
      if (knownSections.includes(title.toLowerCase())) return;
      a.customSections.push({ title, content: content.trim() });
    });
  }


  function getSection(sections, name) {
    if (sections[name] !== undefined) return sections[name];
    const lower = name.toLowerCase();
    for (const key of Object.keys(sections)) {
      if (key.toLowerCase() === lower) return sections[key];
    }
    return undefined;
  }

  function splitMarkdownSections(md) {
    const result = { _title: '', _intro: '' };
    const lines = md.split('\n');
    let currentSection = null;
    let buffer = [];
    let foundTitle = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const h1Match = line.match(/^#(?!#)\s+(.+)/);
      const h2Match = line.match(/^##(?!#)\s+(.+)/);

      if (h1Match && !foundTitle) {
        foundTitle = true;
        result._title = h1Match[1].trim();
        continue;
      }

      if (h2Match) {
        if (currentSection !== null) {
          result[currentSection] = buffer.join('\n');
        } else if (buffer.join('\n').trim()) {
          result._intro = buffer.join('\n').trim();
        }
        currentSection = h2Match[1].trim();
        buffer = [];
        continue;
      }

      buffer.push(line);
    }

    if (currentSection !== null) {
      result[currentSection] = buffer.join('\n');
    } else if (buffer.join('\n').trim() && !result._intro) {
      result._intro = buffer.join('\n').trim();
    }

    return result;
  }

  function getKnownImportSections(fileType) {
    if (fileType === 'user') {
      return ['About', 'Cognitive Style', 'Values', 'Communication Preferences', 'People', 'Projects'];
    }
    return ['Character Traits', 'Behaviors', 'Avoid', 'When User Is Low', 'Technical Style'];
  }

  function collectSectionTitles(md) {
    const sections = splitMarkdownSections(md || '');
    const titles = new Map();
    Object.keys(sections).forEach((key) => {
      if (!key || key.startsWith('_')) return;
      const clean = key.trim();
      if (!clean) return;
      const normalized = clean.toLowerCase();
      if (!titles.has(normalized)) {
        titles.set(normalized, clean);
      }
    });
    return titles;
  }

  function buildImportDiff(md, fileType) {
    const currentMd = fileType === 'user' ? generateUserMarkdown() : generateAgentMarkdown();
    const current = collectSectionTitles(currentMd);
    const incoming = collectSectionTitles(md);
    const known = new Set(getKnownImportSections(fileType).map(s => s.toLowerCase()));

    const replacedTitles = [];
    const addedTitles = [];
    const removedTitles = [];

    incoming.forEach((title, normalized) => {
      if (current.has(normalized)) replacedTitles.push(title);
      else addedTitles.push(title);
    });

    current.forEach((title, normalized) => {
      if (!incoming.has(normalized)) removedTitles.push(title);
    });

    const newCustomTitles = addedTitles.filter(title => !known.has(title.toLowerCase()));

    const byName = (a, b) => a.localeCompare(b);
    replacedTitles.sort(byName);
    addedTitles.sort(byName);
    removedTitles.sort(byName);
    newCustomTitles.sort(byName);

    return {
      replacedCount: replacedTitles.length,
      addedCount: addedTitles.length,
      removedCount: removedTitles.length,
      newCustomCount: newCustomTitles.length,
      replacedTitles,
      addedTitles,
      removedTitles,
      newCustomTitles
    };
  }

  // ---- Label Formatters ----
  function getTraitDescription(key, val) {
    const descs = {
      warmth: val < 30 ? 'Clinical' : val < 50 ? 'Reserved' : val < 70 ? 'Warm' : 'Very warm',
      directness: val < 30 ? 'Gentle' : val < 50 ? 'Balanced' : val < 70 ? 'Direct' : 'Blunt',
      humor: val < 30 ? 'Serious' : val < 50 ? 'Dry' : val < 70 ? 'Witty' : 'Playful',
      formality: val < 30 ? 'Casual' : val < 50 ? 'Relaxed' : val < 70 ? 'Professional' : 'Formal',
      verbosity: val < 30 ? 'Terse' : val < 50 ? 'Concise' : val < 70 ? 'Moderate' : 'Detailed'
    };
    if (descs[key]) return descs[key];
    // Generic for custom traits
    return val < 25 ? 'Very low' : val < 50 ? 'Low' : val < 75 ? 'Moderate' : 'High';
  }

  // ---- Utility ----
  function esc(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---- API Helper ----
  async function apiFetch(path, options = {}) {
    try {
      const resp = await fetch(path, options);
      if (!resp.ok) throw new Error(`API ${resp.status}`);
      return await resp.json();
    } catch (e) {
      console.warn('API fetch failed:', path, e);
      return null;
    }
  }

  function bindById(id, event, handler) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener(event, handler);
  }

  function bindAll(root, selector, event, handler) {
    root.querySelectorAll(selector).forEach((el) => {
      el.addEventListener(event, (ev) => handler(ev, el));
    });
  }

  // ---- Server Status ----
  async function checkServerStatus() {
    try {
      const resp = await fetch('/api/status');
      if (resp.ok) {
        state.serverConnected = true;
        state.statusCache = await resp.json();
      } else {
        state.serverConnected = false;
      }
    } catch (e) {
      state.serverConnected = false;
    }
    updateSidebarStatus();
    if (state.activePage === 'dashboard' || state.activePage === 'settings') {
      renderPage();
    }
  }

  function updateSidebarStatus() {
    const dot = document.querySelector('.top-nav-status-dot');
    const text = document.querySelector('.top-nav-status-text');
    if (!dot || !text) return;
    if (state.serverConnected) {
      dot.classList.add('online');
      dot.classList.remove('error');
      text.textContent = 'Connected';
    } else {
      dot.classList.remove('online');
      dot.classList.add('error');
      text.textContent = 'Offline';
    }
  }

  // ---- Main Render (page router) ----
  function render() {
    recordConfigHistory();
    renderTokenBudget();
    renderPage();
    saveToLocalStorage();
    updateHistoryControls();
  }

  function renderPage() {
    const container = document.getElementById('page-container');
    switch (state.activePage) {
      case 'dashboard': renderDashboard(container); break;
      case 'configure': renderSeedsPage(container); break;
      case 'memories': renderMemoriesPage(container); break;
      case 'settings': renderSettingsPage(container); break;
      // Legacy route names
      case 'backups': state.activePage = 'settings'; syncNavHighlight(); renderSettingsPage(container); break;
      case 'seeds': state.activePage = 'configure'; syncNavHighlight(); renderSeedsPage(container); break;
      case 'notes': case 'remember': state.activePage = 'memories'; syncNavHighlight(); renderMemoriesPage(container); break;
      default: renderDashboard(container);
    }
  }

  // ---- Top Navigation ----
  function syncNavHighlight() {
    document.querySelectorAll('#top-nav-links .top-nav-link').forEach(l => {
      l.classList.toggle('active', l.dataset.page === state.activePage);
    });
    const settingsBtn = document.getElementById('top-nav-settings');
    if (settingsBtn) {
      settingsBtn.classList.toggle('active', state.activePage === 'settings');
    }
  }

  function bindSidebarNav() {
    // Logo = dashboard
    const homeLink = document.getElementById('top-nav-home');
    if (homeLink) {
      homeLink.addEventListener('click', (e) => {
        e.preventDefault();
        state.activePage = 'dashboard';
        syncNavHighlight();
        render();
      });
    }

    // Nav links
    document.querySelectorAll('#top-nav-links .top-nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        if (page === state.activePage) return;
        state.activePage = page;
        syncNavHighlight();
        render();
      });
    });

    // Settings cog
    const settingsBtn = document.getElementById('top-nav-settings');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', () => {
        state.activePage = 'settings';
        syncNavHighlight();
        render();
      });
    }

    syncNavHighlight();
  }

  // ---- Dashboard Page ----
  function clampOnboardingStep(step) {
    const n = parseInt(step, 10);
    if (!Number.isFinite(n)) return 1;
    return Math.min(5, Math.max(1, n));
  }

  function renderOnboardingWizard() {
    const step = clampOnboardingStep(state.onboardingStep || 1);
    const u = state.user;
    const a = state.agent;
    let body = '';

    if (step === 1) {
      body = `
        <div class="wizard-step-fields">
          <label>Name</label>
          <input type="text" value="${esc(u.identity.name || '')}" placeholder="Your name" oninput="window.memorableApp.onboardingSetField('user.identity.name', this.value)">
          <label>Pronouns</label>
          <input type="text" value="${esc(u.identity.pronouns || '')}" placeholder="e.g. she/her, he/him, they/them" oninput="window.memorableApp.onboardingSetField('user.identity.pronouns', this.value)">
        </div>
      `;
    } else if (step === 2) {
      body = `
        <div class="wizard-step-fields">
          <label>About You</label>
          <textarea rows="5" placeholder="Share a short background, your goals, and what context helps most." oninput="window.memorableApp.onboardingSetField('user.about', this.value)">${esc(u.about || '')}</textarea>
        </div>
      `;
    } else if (step === 3) {
      const values = Array.isArray(u.values) && u.values.length ? u.values : [{ higher: '', lower: '' }];
      body = `
        <div class="wizard-step-fields">
          <label>Core Values</label>
          <p class="wizard-step-hint">Set your preference pairs. Left side means "prefer more."</p>
          <div class="wizard-values-list">
            ${values.map((v, idx) => `
              <div class="wizard-value-row">
                <input type="text" value="${esc(v.higher || '')}" placeholder="More important" oninput="window.memorableApp.onboardingSetValue(${idx}, 'higher', this.value)">
                <span>&gt;</span>
                <input type="text" value="${esc(v.lower || '')}" placeholder="Less important" oninput="window.memorableApp.onboardingSetValue(${idx}, 'lower', this.value)">
                <button class="btn btn-small btn-danger-ghost" onclick="window.memorableApp.onboardingRemoveValue(${idx})" ${values.length <= 1 ? 'disabled' : ''}>Remove</button>
              </div>
            `).join('')}
          </div>
          <button class="btn btn-small" onclick="window.memorableApp.onboardingAddValue()">Add pair</button>
        </div>
      `;
    } else if (step === 4) {
      const traitKeys = ['warmth', 'directness', 'humor', 'formality', 'verbosity'];
      body = `
        <div class="wizard-step-fields">
          <label>Agent Personality</label>
          <p class="wizard-step-hint">Tune core traits. You can refine these later in Configure.</p>
          <div class="wizard-traits">
            ${traitKeys.map((key) => {
              const val = parseInt(a.traits[key] || 50, 10);
              return `
                <div class="wizard-trait-row">
                  <div class="wizard-trait-head">
                    <span>${esc(getTraitLabel(key))}</span>
                    <span>${esc(getTraitDescription(key, val))}</span>
                  </div>
                  <input type="range" min="0" max="100" value="${val}" oninput="window.memorableApp.onboardingSetTrait('${key}', this.value)">
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    } else {
      const valueLines = (u.values || [])
        .filter(v => (v.higher || '').trim() || (v.lower || '').trim())
        .map(v => `${v.higher || '...'} > ${v.lower || '...'}`);
      body = `
        <div class="wizard-step-fields wizard-review">
          <h3>Review</h3>
          <p><strong>Name:</strong> ${esc(u.identity.name || 'Not set')}</p>
          <p><strong>Pronouns:</strong> ${esc(u.identity.pronouns || 'Not set')}</p>
          <p><strong>About:</strong> ${esc((u.about || '').trim() || 'Not set')}</p>
          <p><strong>Core values:</strong></p>
          <ul>
            ${valueLines.length ? valueLines.map(v => `<li>${esc(v)}</li>`).join('') : '<li>Not set</li>'}
          </ul>
          <p><strong>Agent traits:</strong> ${['warmth', 'directness', 'humor', 'formality', 'verbosity'].map(k => `${getTraitLabel(k)} ${a.traits[k] || 50}`).join(', ')}</p>
          <p class="wizard-step-hint">Save now to generate starter ` + "`user.md`, `agent.md`, and `now.md`." + `</p>
        </div>
      `;
    }

    return `
      <div class="onboarding-card onboarding-wizard">
        <div class="onboarding-icon"><img src="logo.png" alt="Memorable" style="width:64px;height:64px;"></div>
        <h2>Welcome to Memorable</h2>
        <div class="wizard-progress">
          <span>Step ${step} of 5</span>
          <div class="wizard-progress-track"><div class="wizard-progress-fill" style="width:${(step / 5) * 100}%"></div></div>
        </div>
        <div class="wizard-step-title">
          ${step === 1 ? 'Name + Pronouns' : step === 2 ? 'About You' : step === 3 ? 'Core Values' : step === 4 ? 'Agent Personality' : 'Review + Save'}
        </div>
        ${body}
        <div class="onboarding-actions wizard-actions">
          <button class="btn" onclick="window.memorableApp.onboardingSkip()">Skip for now</button>
          <div class="wizard-actions-right">
            ${step > 1 ? '<button class="btn" onclick="window.memorableApp.onboardingPrev()">Back</button>' : ''}
            ${step < 5
              ? '<button class="btn btn-primary" onclick="window.memorableApp.onboardingNext()">Next</button>'
              : '<button class="btn btn-primary" onclick="window.memorableApp.onboardingComplete()">Save & Open Configure</button>'}
          </div>
        </div>
      </div>
    `;
  }

  function renderDashboard(container) {
    const status = state.statusCache;
    const totalNotes = status ? (status.total_notes || 0) : '\u2014';
    const totalNotesCount = status ? Number(status.total_notes || 0) : 0;
    const totalSessions = status ? (status.total_sessions || 0) : '\u2014';
    const contextFileCount = status ? Number(status.file_count || 0) : '\u2014';
    const daemonRunning = status ? status.daemon_running : false;
    const seedsExist = status ? status.seeds_present : true;
    const daemonEnabled = status
      ? !!status.daemon_enabled
      : !!(((state.settingsCache || {}).daemon || {}).enabled);
    const daemonHealth = status && status.daemon_health ? status.daemon_health : null;
    const daemonIssues = daemonHealth && Array.isArray(daemonHealth.issues)
      ? daemonHealth.issues
      : [];
    const daemonLagSeconds = status && Number.isFinite(status.daemon_lag_seconds)
      ? Number(status.daemon_lag_seconds)
      : null;
    const lastNoteDate = status ? status.last_note_date : '';
    const lastTranscriptDate = status ? status.last_transcript_date : '';

    // Get recent notes (up to 5)
    const recentNotes = state.notesCache.slice(0, 5);

    // Last session summary
    const lastNote = recentNotes.length > 0 ? recentNotes[0] : null;

    let notesHtml = '';
    if (recentNotes.length > 0) {
      notesHtml = recentNotes.map(note => {
        const salience = note.salience || 0;
        const salienceColor = salience >= 1.5 ? 'var(--terracotta)' : salience >= 1.0 ? 'var(--ochre)' : salience >= 0.5 ? 'var(--sage)' : 'var(--warm-gray-light)';
        const tags = (note.tags || []).map(t => `<span class="note-tag">${esc(t)}</span>`).join('');
        const date = note.date ? new Date(note.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
        return `
          <div class="dashboard-note-card">
            <div class="dashboard-note-header">
              <span class="dashboard-note-date">${date}</span>
              <span class="dashboard-note-salience" style="background:${salienceColor};"></span>
            </div>
            <div class="dashboard-note-summary">${esc(note.summary || note.title || 'Untitled')}</div>
            <div class="dashboard-note-tags">${tags}</div>
          </div>
        `;
      }).join('');
    } else {
      notesHtml = `
        <div class="empty-state" style="padding:24px;">
          <div class="empty-state-icon">&#128221;</div>
          <h3>No session notes yet</h3>
          <p>Notes will appear here as sessions are recorded by the <span title="Background process that watches sessions and auto-generates notes.">daemon</span>.</p>
        </div>
      `;
    }

    let lastSessionHtml = '';
    if (lastNote) {
      lastSessionHtml = `
        <div class="dashboard-session-card">
          <div class="dashboard-session-header">
            <h3>Last Session</h3>
            <span class="dashboard-session-date">${lastNote.date ? new Date(lastNote.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
          </div>
          <div class="dashboard-session-body">
            <p>${esc(lastNote.summary || lastNote.content || 'No summary available')}</p>
          </div>
          ${(lastNote.tags || []).length ? `<div class="dashboard-session-tags">${(lastNote.tags || []).map(t => `<span class="note-tag">${esc(t)}</span>`).join('')}</div>` : ''}
        </div>
      `;
    }

    // Onboarding card (shown if no seeds exist)
    let onboardingHtml = '';
    if (!seedsExist) {
      onboardingHtml = renderOnboardingWizard();
    }

    const setupReady = !!status && !!state.settingsCache;
    const hasFirstNote = totalNotesCount > 0;
    const showSetupChecklist = setupReady && seedsExist && (!daemonEnabled || !hasFirstNote);
    let setupChecklistHtml = '';
    if (showSetupChecklist) {
      setupChecklistHtml = `
        <div class="dashboard-setup-card">
          <h2>Finish Setup</h2>
          <p>Complete these steps to start seeing useful memory right away.</p>
          <div class="dashboard-setup-list">
            <div class="dashboard-setup-item complete">
              <span class="setup-mark">&#10003;</span>
              <span>Seed files are created and available at session start.</span>
            </div>
            <div class="dashboard-setup-item ${daemonEnabled ? 'complete' : ''}">
              <span class="setup-mark">${daemonEnabled ? '&#10003;' : '&#9675;'}</span>
              <span>Enable daemon note capture.</span>
            </div>
            <div class="dashboard-setup-item ${hasFirstNote ? 'complete' : ''}">
              <span class="setup-mark">${hasFirstNote ? '&#10003;' : '&#9675;'}</span>
              <span>Capture your first session note.</span>
            </div>
          </div>
          <div class="dashboard-setup-actions">
            ${!daemonEnabled ? '<button class="btn btn-primary" onclick="window.memorableApp.enableDaemon()">Enable Daemon</button>' : ''}
            ${daemonEnabled && !hasFirstNote ? '<button class="btn" onclick="window.memorableApp.navigateTo(\'memories\')">Open Memories</button>' : ''}
            <button class="btn" onclick="window.memorableApp.navigateTo('settings')">Open Settings</button>
          </div>
        </div>
      `;
    }

    let daemonReliabilityHtml = '';
    if (status && daemonHealth && daemonHealth.state !== 'healthy') {
      const issueText = daemonIssues.map((issue) => {
        if (issue === 'daemon_not_running') return 'Daemon is enabled but not running.';
        if (issue === 'notes_lagging') return `Notes are lagging behind transcripts (${formatDuration(daemonLagSeconds)} behind).`;
        if (issue === 'no_notes_generated') return 'Transcripts exist, but no notes have been generated yet.';
        return issue;
      });
      let bodyText = '';
      if (daemonHealth.state === 'disabled') {
        bodyText = 'Daemon note capture is disabled. New sessions will not create notes until you enable it.';
      } else if (issueText.length) {
        bodyText = issueText.join(' ');
      } else {
        bodyText = 'Daemon is not fully healthy yet. Open settings to review capture configuration.';
      }

      daemonReliabilityHtml = `
        <div class="dashboard-daemon-health dashboard-daemon-health-${esc(daemonHealth.state || 'idle')}">
          <div class="dashboard-daemon-health-header">
            <h2>Daemon Reliability</h2>
            <span class="dashboard-daemon-health-badge">${esc((daemonHealth.state || 'idle').toUpperCase())}</span>
          </div>
          <p>${esc(bodyText)}</p>
          <div class="dashboard-daemon-health-meta">
            <span>Last note: ${esc(formatRelativeTime(lastNoteDate))}</span>
            <span>Last transcript: ${esc(formatRelativeTime(lastTranscriptDate))}</span>
          </div>
          <div class="dashboard-daemon-health-actions">
            ${!daemonEnabled ? '<button class="btn btn-primary" onclick="window.memorableApp.enableDaemon()">Enable Daemon</button>' : ''}
            ${daemonIssues.includes('notes_lagging') || daemonIssues.includes('no_notes_generated')
              ? '<button class="btn" onclick="window.memorableApp.navigateTo(\'memories\')">Open Memories</button>'
              : ''}
            <button class="btn" onclick="window.memorableApp.navigateTo('settings')">Open Settings</button>
          </div>
        </div>
      `;
    }

    const daemonStatSub = (() => {
      const noteText = `Last note ${formatRelativeTime(lastNoteDate)}`;
      if (daemonLagSeconds && daemonLagSeconds > 0) {
        return `${noteText} · Lag ${formatDuration(daemonLagSeconds)}`;
      }
      return noteText;
    })();

    container.innerHTML = `
      <div class="dashboard-page">
        <div class="page-header">
          <h1>Dashboard</h1>
          <p>Overview of your Memorable instance</p>
        </div>

        ${onboardingHtml}
        ${setupChecklistHtml}
        ${daemonReliabilityHtml}

        <div class="dashboard-stats">
          <div class="stat-card">
            <div class="stat-value">${totalNotes}</div>
            <div class="stat-label">Episodic Notes</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">${totalSessions}</div>
            <div class="stat-label">Sessions Tracked</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">${contextFileCount}</div>
            <div class="stat-label">Context Files</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">
              <span class="stat-dot ${daemonRunning ? 'stat-dot-active' : 'stat-dot-inactive'}"></span>
              ${daemonRunning ? 'Active' : 'Inactive'}
            </div>
            <div class="stat-label" title="Background process that watches sessions and auto-generates notes.">Daemon</div>
            <div class="stat-card-sub">${esc(daemonStatSub)}</div>
          </div>
        </div>

        ${lastSessionHtml}

        <div class="dashboard-section">
          <div class="dashboard-section-header">
            <h2>Recent Notes</h2>
            ${recentNotes.length > 0 ? `<button class="btn btn-small" onclick="window.memorableApp.navigateTo('memories')">View all</button>` : ''}
          </div>
          <div class="dashboard-notes-grid">
            ${notesHtml}
          </div>
        </div>

        <div class="dashboard-section">
          <h2>Quick Actions</h2>
          <div class="quick-actions">
            <button class="quick-action-btn" onclick="window.memorableApp.navigateTo('configure')">
              <span class="quick-action-icon">&#128196;</span>
              Edit Seeds
            </button>
            <button class="quick-action-btn" onclick="window.memorableApp.navigateTo('memories'); window.memorableApp.setMemoriesSubTab('semantic')">
              <span class="quick-action-icon">&#128193;</span>
              Semantic Memory
            </button>
            <button class="quick-action-btn" onclick="window.memorableApp.navigateTo('memories')">
              <span class="quick-action-icon">&#128269;</span>
              Search Sessions
            </button>
            <button class="quick-action-btn" onclick="window.memorableApp.navigateTo('settings')">
              <span class="quick-action-icon">&#9881;</span>
              Settings
            </button>
          </div>
        </div>
      </div>
    `;
  }


  // ==== PART 2: Notes Page, Settings Page, Seeds Page, Files Page ====

  // ---- Notes Page ----

  // Notes page state (persists across re-renders within the page)
  const notesState = {
    notes: [],
    tags: [],
    machines: [],
    insights: null,
    total: 0,
    offset: 0,
    pageSize: 50,
    search: '',
    tag: '',
    sort: 'date',
    machine: '',
    session: '',
    archived: 'exclude',
    fetchError: false,
    expandedIdx: null,
    actionBusy: false,
    loaded: false,
  };

  async function loadNotes() {
    const archivedParam = encodeURIComponent(notesState.archived || 'exclude');
    // Fetch tags, machines, and memory insights in parallel
    const [tagsData, machinesData, insightsData] = await Promise.all([
      apiFetch('/api/notes/tags?archived=' + archivedParam),
      apiFetch('/api/machines'),
      apiFetch('/api/memory/insights'),
    ]);
    notesState.tags = Array.isArray(tagsData && tagsData.tags) ? tagsData.tags : [];
    notesState.machines = Array.isArray(machinesData && machinesData.machines) ? machinesData.machines : [];
    notesState.insights = (insightsData && typeof insightsData === 'object') ? insightsData : null;
    notesState.fetchError = false;

    // Fetch first page of notes
    await fetchNotesPage(false);
    notesState.loaded = true;

    // Also update the old cache for dashboard
    state.notesCache = notesState.notes;
  }

  async function fetchNotesPage(append) {
    const params = new URLSearchParams({
      limit: String(notesState.pageSize),
      offset: String(append ? notesState.offset : 0),
      sort: notesState.sort,
      archived: notesState.archived || 'exclude',
    });
    if (notesState.search) params.set('search', notesState.search);
    if (notesState.tag) params.set('tag', notesState.tag);
    if (notesState.machine) params.set('machine', notesState.machine);
    if (notesState.session) params.set('session', notesState.session);

    const data = await apiFetch('/api/notes?' + params);
    if (!data) {
      notesState.fetchError = true;
      if (!append) {
        notesState.notes = [];
        notesState.total = 0;
        notesState.offset = 0;
      }
      return;
    }
    notesState.fetchError = false;

    const notes = Array.isArray(data.notes) ? data.notes : [];
    notesState.total = Number.isFinite(data.total) ? data.total : notes.length;
    if (append) {
      notesState.notes = notesState.notes.concat(notes);
    } else {
      notesState.notes = notes;
    }
    notesState.offset = notesState.notes.length;
  }

  async function mutateNoteReview(note, action, extra = {}) {
    if (!note || !note.id || !action) {
      return false;
    }
    if (notesState.actionBusy) {
      return false;
    }
    notesState.actionBusy = true;
    try {
      const result = await apiFetch('/api/notes/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: note.id,
          action,
          ...extra,
        }),
      });

      if (!result || result.ok !== true) {
        showToast('Could not update note', 'error');
        return false;
      }

      const messages = {
        pin: 'Pinned note',
        unpin: 'Unpinned note',
        archive: 'Archived note',
        restore: 'Restored note',
        promote: 'Increased salience',
        demote: 'Decreased salience',
        retag: 'Updated tags',
      };
      showToast(messages[action] || 'Note updated');
      await loadNotes();
      return true;
    } finally {
      notesState.actionBusy = false;
    }
  }

  function salienceColor(salience) {
    const maxSalience = 2.0;
    const warmth = Math.min(1, salience / maxSalience);
    const r = Math.round(194 * warmth + 180 * (1 - warmth));
    const g = Math.round(105 * warmth + 175 * (1 - warmth));
    const b = Math.round(79 * warmth + 200 * (1 - warmth));
    return `rgb(${r},${g},${b})`;
  }

  function salienceLevel(salience) {
    if (salience >= 1.5) return 'high';
    if (salience >= 0.8) return 'mid';
    return 'low';
  }

  function ageOpacity(dateStr) {
    if (!dateStr) return 0.7;
    const days = Math.max(0, (Date.now() - new Date(dateStr).getTime()) / 86400000);
    return Math.max(0.7, 1 - days * 0.003);
  }

  function groupNotesByTime(notes) {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekStart = new Date(todayStart);
    weekStart.setDate(weekStart.getDate() - todayStart.getDay());
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const groups = [
      { key: 'today', label: 'Today', entries: [] },
      { key: 'week', label: 'This Week', entries: [] },
      { key: 'month', label: 'This Month', entries: [] },
      { key: 'older', label: 'Older', entries: [] },
    ];
    notes.forEach((note, idx) => {
      const d = note.date ? new Date(note.date) : new Date(0);
      if (d >= todayStart) groups[0].entries.push({ note, idx });
      else if (d >= weekStart) groups[1].entries.push({ note, idx });
      else if (d >= monthStart) groups[2].entries.push({ note, idx });
      else groups[3].entries.push({ note, idx });
    });
    return groups.filter(g => g.entries.length > 0);
  }

  function truncateText(text, len) {
    if (!text) return '';
    // Strip markdown headings for summary display
    const stripped = text.replace(/^#+\s*/gm, '').replace(/\*\*/g, '').replace(/\n/g, ' ').trim();
    if (stripped.length <= len) return stripped;
    return stripped.slice(0, len) + '\u2026';
  }

  function renderNotesPage(container) {
    const ns = notesState;
    const mi = ns.insights;
    const status = state.statusCache || null;
    const daemonEnabled = status && typeof status.daemon_enabled === 'boolean'
      ? status.daemon_enabled
      : !!(((state.settingsCache || {}).daemon || {}).enabled);

    // Machine tabs
    let machineTabsHtml = '';
    if (ns.machines.length > 1) {
      const allActive = ns.machine === '' ? ' active' : '';
      machineTabsHtml = `<div class="notes-device-tabs">
        <span class="notes-device-tab${allActive}" data-machine="">All</span>
        ${ns.machines.map(m => {
          const short = m.split('.')[0];
          const active = ns.machine === m ? ' active' : '';
          return `<span class="notes-device-tab${active}" data-machine="${esc(m)}">${esc(short)}</span>`;
        }).join('')}
      </div>`;
    }

    // Tag filter dropdown
    let tagOptions = '<option value="">All tags</option>';
    for (const t of ns.tags) {
      const sel = ns.tag === t.name ? ' selected' : '';
      tagOptions += `<option value="${esc(t.name)}"${sel}>${esc(t.name)} (${t.count})</option>`;
    }

    // Note cards
    let notesHtml = '';
    if (ns.notes.length > 0) {
      const renderCard = (note, idx) => {
        const salience = note.salience || 0;
        const color = salienceColor(salience);
        const sLevel = salienceLevel(salience);
        const ageFade = ageOpacity(note.date);
        const isExpanded = ns.expandedIdx === idx;

        const visibleTags = (note.tags || []).slice(0, 4);
        const overflowCount = (note.tags || []).length - 4;
        const shouldNotTry = Array.isArray(note.should_not_try) ? note.should_not_try : [];
        const conflicts = Array.isArray(note.conflicts_with) ? note.conflicts_with : [];
        const pinAction = note.pinned ? 'unpin' : 'pin';
        const pinLabel = note.pinned ? 'Unpin' : 'Pin';
        const archiveAction = note.archived ? 'restore' : 'archive';
        const archiveLabel = note.archived ? 'Restore' : 'Archive';
        const tagsHtml = visibleTags.map(t => `<span class="note-tag">${esc(t)}</span>`).join('') +
          (note.pinned ? '<span class="note-review-chip pinned" title="Pinned notes receive extra retrieval weight.">Pinned</span>' : '') +
          (note.archived ? '<span class="note-review-chip archived" title="Archived notes are excluded by default.">Archived</span>' : '') +
          (overflowCount > 0 ? `<span class="note-tag">+${overflowCount}</span>` : '') +
          (shouldNotTry.length > 0 ? `<span class="note-antiforce-chip" title="Approaches marked as failed or unhelpful.">Avoid ${shouldNotTry.length}</span>` : '') +
          (conflicts.length > 0 ? `<span class="note-conflict-chip" title="This note may conflict with other notes.">Conflicts ${conflicts.length}</span>` : '');

        const date = note.date ? new Date(note.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : '';
        const msgCount = note.message_count ? `${note.message_count} msgs` : '';
        const wordCount = note.content ? note.content.split(/\s+/).length : 0;

        const metaParts = [date, msgCount, `${wordCount} words`].filter(Boolean).join(' \u00b7 ');

        const summaryText = truncateText(note.summary || note.content || '', 150);

        // Metadata footer (visible when expanded)
        let metaFooter = '';
        if (note.session) {
          metaFooter += `<span class="note-meta-item" style="font-family:'SF Mono',monospace;font-size:0.75rem">${esc(note.session.slice(0, 8))}</span>`;
        }
        if (note.machine) {
          metaFooter += `<span class="note-meta-item">${esc(note.machine)}</span>`;
        }

        const shouldNotTryHtml = shouldNotTry.length > 0 ? `
          <div class="note-card-antiforce">
            <div class="note-card-antiforce-label">Don't try again</div>
            <ul class="note-card-antiforce-list">
              ${shouldNotTry.map(item => `<li>${esc(item)}</li>`).join('')}
            </ul>
          </div>
        ` : '';

        const conflictsHtml = conflicts.length > 0 ? `
          <div class="note-card-conflicts">
            <div class="note-card-conflicts-label">Conflicts with</div>
            <div class="note-card-conflicts-list">
              ${conflicts.map(ref => `<span class="note-card-conflict-ref">${esc(ref)}</span>`).join('')}
            </div>
          </div>
        ` : '';

        const actionsHtml = `
          <div class="note-card-actions">
            <button type="button" class="note-action-btn ${note.pinned ? 'active' : ''}" data-note-idx="${idx}" data-action="${pinAction}">${pinLabel}</button>
            <button type="button" class="note-action-btn" data-note-idx="${idx}" data-action="promote">Promote</button>
            <button type="button" class="note-action-btn" data-note-idx="${idx}" data-action="demote">Demote</button>
            <button type="button" class="note-action-btn ${note.archived ? 'active' : ''}" data-note-idx="${idx}" data-action="${archiveAction}">${archiveLabel}</button>
            <button type="button" class="note-action-btn" data-note-idx="${idx}" data-action="retag">Retag</button>
          </div>
        `;

        return `
          <div class="note-card note-salience-${sLevel}${isExpanded ? ' expanded' : ''}${note.archived ? ' note-card-archived' : ''}${note.pinned ? ' note-card-pinned' : ''}" data-note-idx="${idx}" style="--age-factor:${ageFade.toFixed(2)}">
            <div class="note-card-header">
              <div class="note-card-salience-bar" style="background:${color}"></div>
              <div class="note-card-info">
                <div class="note-card-meta">${metaParts}</div>
                <div class="note-card-summary">${esc(summaryText)}</div>
                <div class="note-card-tags">${tagsHtml}</div>
              </div>
              <div class="note-card-salience" style="color:${color}">${salience.toFixed(2)}</div>
            </div>
            <div class="note-card-body">
              ${actionsHtml}
              ${shouldNotTryHtml}
              ${conflictsHtml}
              <div class="note-card-content">${markdownToHtml(note.content || 'No content')}</div>
              ${metaFooter ? `<div class="note-card-meta-footer">${metaFooter}</div>` : ''}
            </div>
          </div>
        `;
      };

      if (ns.sort === 'date') {
        const timeGroups = groupNotesByTime(ns.notes);
        notesHtml = timeGroups.map(group => {
          const cardsHtml = group.entries.map(({ note, idx }) => renderCard(note, idx)).join('');
          return `
            <div class="notes-time-group" data-time-group="${group.key}">
              <div class="notes-time-group-header">
                <span class="notes-time-group-dot"></span>
                <span class="notes-time-group-label">${group.label}</span>
                <span class="notes-time-group-count">${group.entries.length}</span>
              </div>
              <div class="notes-time-group-cards">${cardsHtml}</div>
            </div>
          `;
        }).join('');
      } else {
        notesHtml = ns.notes.map((note, idx) => renderCard(note, idx)).join('');
      }
    } else {
      if (ns.fetchError) {
        notesHtml = `
          <div class="notes-empty">
            <div class="notes-empty-icon">&#9888;</div>
            <h3>Could not load session notes</h3>
            <p>Memories may be unavailable while the local server is offline.</p>
            <div class="notes-empty-actions">
              <button class="btn btn-primary" id="notes-retry-btn">Retry</button>
              <button class="btn" id="notes-open-settings-btn">Open Settings</button>
            </div>
          </div>
        `;
      } else if (ns.search || ns.tag || ns.session || ns.machine || ns.archived !== 'exclude') {
        notesHtml = `
          <div class="notes-empty">
            <div class="notes-empty-icon">&#128221;</div>
            <h3>No notes match your filters</h3>
            <p>Try a different search term, tag, or clear active filters.</p>
          </div>
        `;
      } else if (!daemonEnabled) {
        notesHtml = `
          <div class="notes-empty">
            <div class="notes-empty-icon">&#128164;</div>
            <h3>Session notes are not capturing yet</h3>
            <p>Enable the <span title="Background process that watches sessions and auto-generates notes.">daemon</span> to start generating notes from new sessions.</p>
            <div class="notes-empty-actions">
              <button class="btn btn-primary" id="notes-enable-daemon-btn">Enable Daemon</button>
              <button class="btn" id="notes-open-settings-btn">Open Settings</button>
            </div>
          </div>
        `;
      } else {
        notesHtml = `
          <div class="notes-empty">
            <div class="notes-empty-icon">&#128221;</div>
            <h3>No session notes yet</h3>
            <p>Run one Claude session, then come back here to review what was captured.</p>
            <div class="notes-empty-actions">
              <button class="btn" id="notes-retry-btn">Refresh</button>
            </div>
          </div>
        `;
      }
    }

    // Load more button
    let loadMoreHtml = '';
    if (ns.notes.length < ns.total) {
      loadMoreHtml = `
        <div class="notes-load-more">
          <button class="notes-load-more-btn">${ns.notes.length} of ${ns.total} \u2014 Load more</button>
        </div>
      `;
    }

    let insightsHtml = '';
    if (mi && typeof mi === 'object') {
      const tracked = Number(mi.tracked_notes || 0);
      const loaded = Number(mi.total_loaded || 0);
      const referenced = Number(mi.total_referenced || 0);
      const refRate = Math.max(0, Math.min(100, Math.round(Number(mi.reference_rate || 0) * 100)));

      if (tracked > 0) {
        const top = Array.isArray(mi.top_referenced) ? mi.top_referenced : [];
        const low = Array.isArray(mi.high_load_low_reference) ? mi.high_load_low_reference : [];
        const suggestions = Array.isArray(mi.suggestions) ? mi.suggestions : [];
        const topRows = top.map((r) => {
          const session = String(r.session || '').trim();
          const active = session && ns.session.toLowerCase() === session.toLowerCase() ? ' active' : '';
          return `
            <button type="button" class="memory-insights-row-btn${active}" data-session="${esc(session)}">
              <span class="memory-insights-session">${esc(session || 'unknown')}</span>
              <span class="memory-insights-row-meta">${Number(r.referenced || 0)} / ${Number(r.loaded || 0)} refs</span>
            </button>
          `;
        }).join('');
        const lowRows = low.map((r) => {
          const session = String(r.session || '').trim();
          const active = session && ns.session.toLowerCase() === session.toLowerCase() ? ' active' : '';
          return `
            <button type="button" class="memory-insights-row-btn${active}" data-session="${esc(session)}">
              <span class="memory-insights-session">${esc(session || 'unknown')}</span>
              <span class="memory-insights-row-meta">${Number(r.loaded || 0)} loads, ${Math.round(Number(r.reference_rate || 0) * 100)}% yield</span>
            </button>
          `;
        }).join('');

        insightsHtml = `
          <div class="memory-insights-card">
            <div class="memory-insights-header">
              <h3>Memory Effectiveness</h3>
              <span class="memory-insights-sub">How often loaded notes are referenced later. Click a row to filter notes by session.</span>
            </div>
            <div class="memory-insights-metrics">
              <div class="memory-insights-metric">
                <span class="memory-insights-value">${loaded}</span>
                <span class="memory-insights-label">Loads</span>
              </div>
              <div class="memory-insights-metric">
                <span class="memory-insights-value">${referenced}</span>
                <span class="memory-insights-label">References</span>
              </div>
              <div class="memory-insights-metric">
                <span class="memory-insights-value">${refRate}%</span>
                <span class="memory-insights-label">Yield</span>
              </div>
            </div>
            <div class="memory-insights-columns">
              <div class="memory-insights-column">
                <h4>Top referenced</h4>
                ${topRows || '<p class="memory-insights-empty">No reference activity yet.</p>'}
              </div>
              <div class="memory-insights-column">
                <h4>High load, low yield</h4>
                ${lowRows || '<p class="memory-insights-empty">No low-yield notes detected.</p>'}
              </div>
            </div>
            ${suggestions.length ? `
              <div class="memory-insights-suggestions">
                ${suggestions.slice(0, 2).map(s => `<p>${esc(s)}</p>`).join('')}
              </div>
            ` : ''}
          </div>
        `;
      } else {
        insightsHtml = `
          <div class="memory-insights-card">
            <div class="memory-insights-header">
              <h3>Memory Effectiveness</h3>
              <span class="memory-insights-sub">Run a few sessions to collect usage data.</span>
            </div>
          </div>
        `;
      }
    }

    const sessionFilterHtml = ns.session ? `
      <div class="notes-active-filters">
        <button type="button" class="notes-filter-pill" id="notes-session-filter-clear" title="Clear session filter">
          Session ${esc(ns.session)} <span aria-hidden="true">&times;</span>
        </button>
      </div>
    ` : '';
    const hasActiveFilters = Boolean(
      ns.search
      || ns.tag
      || ns.machine
      || ns.session
      || ns.archived !== 'exclude'
      || ns.sort !== 'date'
    );
    const resetFiltersHtml = hasActiveFilters
      ? '<button type="button" class="notes-reset-btn" id="notes-reset-filters-btn">Reset filters</button>'
      : '';

    container.innerHTML = `
      <div class="notes-page">
        ${insightsHtml}
        <div class="notes-header-row">
          <span class="notes-count">${ns.total} note${ns.total !== 1 ? 's' : ''}</span>
        </div>
        ${machineTabsHtml}
        <div class="notes-toolbar">
          <div class="notes-search">
            <svg class="notes-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" class="notes-search-input" id="notes-search-input" placeholder="Search notes\u2026" value="${esc(ns.search)}">
          </div>
          <select class="notes-archive-filter" id="notes-archive-filter">
            <option value="exclude"${ns.archived === 'exclude' ? ' selected' : ''}>Active</option>
            <option value="only"${ns.archived === 'only' ? ' selected' : ''}>Archived</option>
            <option value="include"${ns.archived === 'include' ? ' selected' : ''}>All</option>
          </select>
          <select class="notes-tag-filter" id="notes-tag-filter">${tagOptions}</select>
          <div class="notes-sort">
            <button class="notes-sort-btn ${ns.sort === 'date' ? 'active' : ''}" data-sort="date">Newest</button>
            <button class="notes-sort-btn ${ns.sort === 'date_asc' ? 'active' : ''}" data-sort="date_asc">Oldest</button>
            <button class="notes-sort-btn ${ns.sort === 'salience' ? 'active' : ''}" data-sort="salience" title="How relevant/important a note is. Higher salience notes are more likely to be loaded.">Salience</button>
          </div>
          ${resetFiltersHtml}
        </div>
        ${sessionFilterHtml}
        <div class="notes-list">
          ${notesHtml}
        </div>
        ${loadMoreHtml}
      </div>
    `;

    const refreshNotes = () => fetchNotesPage(false).then(() => renderNotesPage(container));

    bindById('notes-search-input', 'input', debounce((event) => {
      ns.search = event.target.value.trim();
      ns.expandedIdx = null;
      refreshNotes();
    }, 300));

    bindById('notes-tag-filter', 'change', (event) => {
      ns.tag = event.target.value;
      ns.expandedIdx = null;
      refreshNotes();
    });

    bindById('notes-archive-filter', 'change', (event) => {
      ns.archived = event.target.value || 'exclude';
      ns.expandedIdx = null;
      loadNotes().then(() => renderNotesPage(container));
    });

    bindAll(container, '.notes-sort-btn', 'click', (_event, btn) => {
      ns.sort = btn.dataset.sort;
      ns.expandedIdx = null;
      refreshNotes();
    });

    bindAll(container, '.notes-device-tab', 'click', (_event, tab) => {
      ns.machine = tab.dataset.machine;
      ns.expandedIdx = null;
      refreshNotes();
    });

    bindAll(container, '.memory-insights-row-btn', 'click', (event, btn) => {
      event.stopPropagation();
      const session = String(btn.dataset.session || '').trim();
      if (!session) return;
      ns.session = ns.session.toLowerCase() === session.toLowerCase() ? '' : session;
      ns.expandedIdx = null;
      refreshNotes();
    });

    bindById('notes-session-filter-clear', 'click', () => {
      ns.session = '';
      ns.expandedIdx = null;
      refreshNotes();
    });

    bindById('notes-retry-btn', 'click', () => {
      refreshNotes();
    });

    bindById('notes-enable-daemon-btn', 'click', () => {
      window.memorableApp.enableDaemon();
    });

    bindById('notes-open-settings-btn', 'click', () => {
      window.memorableApp.navigateTo('settings');
    });

    bindById('notes-reset-filters-btn', 'click', () => {
      ns.search = '';
      ns.tag = '';
      ns.machine = '';
      ns.session = '';
      ns.archived = 'exclude';
      ns.sort = 'date';
      ns.expandedIdx = null;
      loadNotes().then(() => renderNotesPage(container));
    });

    bindAll(container, '.note-action-btn', 'click', async (event, btn) => {
      event.preventDefault();
      event.stopPropagation();
      if (notesState.actionBusy) return;

      const idx = Number.parseInt(btn.dataset.noteIdx || '', 10);
      if (!Number.isFinite(idx)) return;
      const note = ns.notes[idx];
      if (!note) return;

      const action = String(btn.dataset.action || '').trim();
      if (!action) return;

      const payload = {};
      if (action === 'retag') {
        const current = Array.isArray(note.tags) ? note.tags.join(', ') : '';
        const raw = window.prompt('Edit tags (comma-separated):', current);
        if (raw === null) return;
        payload.tags = raw
          .split(',')
          .map(t => t.trim())
          .filter(Boolean);
      }

      const ok = await mutateNoteReview(note, action, payload);
      if (ok) {
        ns.expandedIdx = null;
        renderNotesPage(container);
      }
    });

    bindAll(container, '.note-card', 'click', (event, card) => {
      if (event.target.closest('a')) return;
      const idx = Number.parseInt(card.dataset.noteIdx, 10);
      if (ns.expandedIdx === idx) {
        ns.expandedIdx = null;
        card.classList.remove('expanded');
        return;
      }
      const prev = container.querySelector('.note-card.expanded');
      if (prev) prev.classList.remove('expanded');
      ns.expandedIdx = idx;
      card.classList.add('expanded');
    });

    bindAll(container, '.notes-load-more-btn', 'click', async (_event, loadMoreBtn) => {
      loadMoreBtn.textContent = 'Loading\u2026';
      loadMoreBtn.disabled = true;
      await fetchNotesPage(true);
      renderNotesPage(container);
    });
  }

  // ---- Memories Page (with sub-tabs) ----

  function renderMemoriesPage(container) {
    const subTab = state.memoriesSubTab || 'episodic';
    const memoryKinds = {
      episodic: {
        label: 'Episodic',
        helper: 'Browse and search notes from past sessions.',
      },
      working: {
        label: 'Working',
        helper: 'Your current rolling context — what\'s on your mind right now.',
      },
      semantic: {
        label: 'Semantic',
        helper: 'Long-lived knowledge documents and their anchor depth.',
      },
    };
    const activeMemory = memoryKinds[subTab] || memoryKinds.episodic;

    // Sub-tab bar
    const subTabBar = `
      <div class="memories-sub-tabs">
        <button class="memories-sub-tab ${subTab === 'episodic' ? 'active' : ''}" data-subtab="episodic">Episodic</button>
        <button class="memories-sub-tab ${subTab === 'working' ? 'active' : ''}" data-subtab="working">Working</button>
        <button class="memories-sub-tab ${subTab === 'semantic' ? 'active' : ''}" data-subtab="semantic">Semantic</button>
      </div>
      <div class="memories-subtab-helper">
        <strong>${esc(activeMemory.label)}</strong>
        <span>${esc(activeMemory.helper)}</span>
      </div>
    `;

    // Render sub-tab content into a wrapper so we can insert the tab bar above
    const wrapper = document.createElement('div');
    wrapper.className = 'memories-page';

    // Page header + sub-tabs
    wrapper.innerHTML = `
      <div class="page-header">
        <h1>Memories</h1>
        <p>Episodic, working, and semantic memory</p>
      </div>
      ${subTabBar}
      <div class="memories-content" id="memories-content"></div>
    `;

    container.innerHTML = '';
    container.appendChild(wrapper);

    const contentEl = document.getElementById('memories-content');

    // Render the active sub-tab
    switch (subTab) {
      case 'episodic':
        renderNotesPage(contentEl);
        break;
      case 'working':
        renderWorkingMemory(contentEl);
        break;
      case 'semantic':
        renderSemanticMemory(contentEl);
        break;
    }

    // Bind sub-tab clicks
    wrapper.querySelectorAll('.memories-sub-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        state.memoriesSubTab = btn.dataset.subtab;
        renderMemoriesPage(container);
      });
    });
  }

  async function renderWorkingMemory(container) {
    container.innerHTML = '<div style="padding:20px;color:var(--text-muted);">Loading now.md...</div>';

    const data = await apiFetch('/api/seeds');
    if (!data || !data.files) {
      container.innerHTML = `
        <div class="notes-empty">
          <div class="notes-empty-icon">&#9888;</div>
          <h3>Could not load working memory</h3>
          <p>Make sure the local server is running, then retry.</p>
          <div class="notes-empty-actions">
            <button class="btn btn-primary" id="working-retry-btn">Retry</button>
            <button class="btn" id="working-open-settings-btn">Open Settings</button>
          </div>
        </div>
      `;
      const retryBtn = container.querySelector('#working-retry-btn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderWorkingMemory(container));
      const settingsBtn = container.querySelector('#working-open-settings-btn');
      if (settingsBtn) settingsBtn.addEventListener('click', () => window.memorableApp.navigateTo('settings'));
      return;
    }

    const nowContent = data.files['now.md'];
    if (!nowContent) {
      container.innerHTML = `
        <div class="notes-empty">
          <div class="notes-empty-icon">&#128203;</div>
          <h3>No working memory yet</h3>
          <p>The now.md file will be created automatically by the <span title="Background process that watches sessions and auto-generates notes.">daemon</span> as sessions are processed.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="working-memory-card">
        <div class="working-memory-header">
          <span class="working-memory-label">now.md</span>
          <span class="working-memory-hint">Auto-generated from session notes</span>
        </div>
        <div class="working-memory-content">${markdownToHtml(nowContent)}</div>
      </div>
    `;
  }

  async function renderSemanticMemory(container) {
    container.innerHTML = '<div style="padding:20px;color:var(--text-muted);">Loading files...</div>';

    // Fetch files and seeds in parallel
    const [filesData, seedsData] = await Promise.all([
      apiFetch('/api/files'),
      apiFetch('/api/seeds'),
    ]);

    if (!filesData || !seedsData) {
      container.innerHTML = `
        <div class="notes-empty" style="padding:24px;">
          <div class="notes-empty-icon">&#9888;</div>
          <h3>Could not load semantic memory</h3>
          <p>Check that the local server is running, then retry.</p>
          <div class="notes-empty-actions">
            <button class="btn btn-primary" id="semantic-retry-btn">Retry</button>
            <button class="btn" id="semantic-open-settings-btn">Open Settings</button>
          </div>
        </div>
      `;
      const retryBtn = container.querySelector('#semantic-retry-btn');
      if (retryBtn) retryBtn.addEventListener('click', () => renderSemanticMemory(container));
      const settingsBtn = container.querySelector('#semantic-open-settings-btn');
      if (settingsBtn) settingsBtn.addEventListener('click', () => window.memorableApp.navigateTo('settings'));
      return;
    }

    const files = Array.isArray(filesData && filesData.files) ? filesData.files : [];
    const seedFiles = (seedsData && typeof seedsData.files === 'object' && seedsData.files) ? seedsData.files : {};
    const seedNames = Object.keys(seedFiles).filter(n => n !== 'now.md').sort();

    // Identity files section (seeds)
    let seedsHtml = '';
    if (seedNames.length > 0) {
      seedsHtml = `
        <div class="semantic-section-header">Identity Files</div>
        <div class="semantic-seed-cards">
          ${seedNames.map(name => {
            const content = seedFiles[name] || '';
            const preview = content.split('\n').slice(0, 6).join('\n');
            const tokens = Math.ceil(content.length / 4);
            return `
              <div class="semantic-seed-card">
                <div class="semantic-seed-header">
                  <span class="semantic-seed-name">${esc(name)}</span>
                  <span class="semantic-seed-tokens">${tokens} tokens</span>
                </div>
                <div class="semantic-seed-preview">${markdownToHtml(preview)}</div>
                <button class="semantic-seed-configure-btn" onclick="window.memorableApp.navigateTo('configure')">Configure</button>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    // Upload zone
    const uploadHtml = `
      <div class="semantic-upload-zone" id="semantic-dropzone">
        <div class="semantic-upload-icon">&#128196;</div>
        <p>Drop a document here, or click to upload</p>
        <p class="semantic-upload-hint">Markdown, plain text, or any text document</p>
        <input type="file" id="semantic-file-input" accept=".md,.txt,.text,.markdown,.rst,.org" multiple style="display:none">
        <div class="semantic-upload-progress" id="semantic-upload-progress" hidden></div>
      </div>
    `;

    // Files list
    let filesHtml = '';
    if (files.length > 0) {
      filesHtml = `
        <div class="semantic-section-header">Knowledge Documents</div>
        <div class="semantic-files-list">
          ${files.map(f => {
            const statusClass = f.anchored ? 'status-anchored' : 'status-raw';
            const statusText = f.anchored ? 'Anchored' : 'Raw';
            const depthOptions = [0, 1, 2, 3].map(d =>
              `<option value="${d}" ${f.depth === d ? 'selected' : ''}>Depth ${d}</option>`
            ).join('') + `<option value="-1" ${f.depth === -1 ? 'selected' : ''}>Full</option>`;

            let depthInfo = '';
            if (f.tokens_by_depth) {
              const tbd = f.tokens_by_depth;
              depthInfo = `<div class="file-depth-info">Tokens: 0\u2192${tbd['0'] || '?'} &middot; 1\u2192${tbd['1'] || '?'} &middot; 2\u2192${tbd['2'] || '?'} &middot; 3\u2192${tbd['3'] || '?'}</div>`;
            }

            return `
              <div class="file-card ${f.anchored ? 'file-card-anchored' : ''}" data-filename="${esc(f.name)}">
                <div class="file-card-header">
                  <div class="file-card-info">
                    <span class="file-card-name">${esc(f.name)}</span>
                    <span class="file-status ${statusClass}">${statusText}</span>
                    <span class="file-card-meta">${f.tokens} tokens</span>
                  </div>
                  <div class="file-card-actions">
                    ${!f.anchored ? `<button class="btn btn-primary btn-sm file-process-btn" data-filename="${esc(f.name)}">Process</button>` : ''}
                    ${f.anchored ? `
                      <select class="file-depth-select" data-filename="${esc(f.name)}">${depthOptions}</select>
                    ` : ''}
                    <label class="file-enabled-label">
                      <input type="checkbox" class="file-enabled-toggle" data-filename="${esc(f.name)}" ${f.enabled ? 'checked' : ''}>
                      Load
                    </label>
                    <button class="btn btn-ghost btn-sm file-delete-btn" data-filename="${esc(f.name)}">Delete</button>
                  </div>
                </div>
                ${depthInfo}
                <div class="file-card-body" id="file-body-${esc(f.name).replace(/\./g, '-')}"></div>
              </div>
            `;
          }).join('')}
        </div>
      `;
    } else {
      filesHtml = `
        <div class="semantic-section-header">Knowledge Documents</div>
        <div class="notes-empty" style="padding:24px;">
          <div class="notes-empty-icon">&#128218;</div>
          <h3>No documents yet</h3>
          <p>Upload your first knowledge document to make long-lived context available at startup.</p>
          <div class="notes-empty-actions">
            <button class="btn btn-primary" id="semantic-upload-first-btn">Upload First Document</button>
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="semantic-memory-page">
        <div class="semantic-placeholder">
          <p>Upload knowledge documents. Process them with an LLM to create tiered anchors, then load them at the right depth during session start.</p>
        </div>
        ${uploadHtml}
        ${seedsHtml}
        ${filesHtml}
      </div>
    `;

    // --- Event bindings ---

    // Upload zone
    const dropzone = document.getElementById('semantic-dropzone');
    const fileInput = document.getElementById('semantic-file-input');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());
      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
      });
      dropzone.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        await handleSemanticUpload(e.dataTransfer.files, container);
      });
      fileInput.addEventListener('change', async () => {
        await handleSemanticUpload(fileInput.files, container);
        fileInput.value = '';
      });
    }

    const uploadFirstBtn = container.querySelector('#semantic-upload-first-btn');
    if (uploadFirstBtn && fileInput) {
      uploadFirstBtn.addEventListener('click', () => fileInput.click());
    }

    // Process buttons
    container.querySelectorAll('.file-process-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const filename = btn.dataset.filename;
        btn.textContent = 'Processing...';
        btn.disabled = true;
        try {
          const result = await apiFetch(`/api/files/${encodeURIComponent(filename)}/process`, {
            method: 'POST',
          });
          if (result && result.status === 'ok') {
            showToast(`Anchored ${filename} (${result.method})`, 'success');
          } else {
            showToast(`Processing issue: ${result && result.error || 'unknown'}`, 'error');
          }
          renderSemanticMemory(container);
        } catch (err) {
          showToast('Processing failed: ' + err.message, 'error');
          btn.textContent = 'Process';
          btn.disabled = false;
        }
      });
    });

    // Depth selectors
    container.querySelectorAll('.file-depth-select').forEach(sel => {
      sel.addEventListener('change', async (e) => {
        e.stopPropagation();
        const filename = sel.dataset.filename;
        const depth = parseInt(sel.value);
        const enabledToggle = container.querySelector(`.file-enabled-toggle[data-filename="${filename}"]`);
        const enabled = enabledToggle ? enabledToggle.checked : false;
        await apiFetch(`/api/files/${encodeURIComponent(filename)}/depth`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ depth, enabled }),
        });
        showToast('Depth updated', 'success');
      });
    });

    // Enabled toggles
    container.querySelectorAll('.file-enabled-toggle').forEach(toggle => {
      toggle.addEventListener('change', async (e) => {
        e.stopPropagation();
        const filename = toggle.dataset.filename;
        const enabled = toggle.checked;
        const depthSel = container.querySelector(`.file-depth-select[data-filename="${filename}"]`);
        const depth = depthSel ? parseInt(depthSel.value) : -1;
        await apiFetch(`/api/files/${encodeURIComponent(filename)}/depth`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ depth, enabled }),
        });
        showToast(enabled ? 'Will load at session start' : 'Disabled', 'success');
      });
    });

    // Delete buttons
    container.querySelectorAll('.file-delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const filename = btn.dataset.filename;
        if (!confirm('Delete ' + filename + '?')) return;
        try {
          await apiFetch(`/api/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
          });
          showToast('Deleted ' + filename, 'success');
          renderSemanticMemory(container);
        } catch (err) {
          showToast('Delete failed', 'error');
        }
      });
    });

    // Click to expand/preview
    container.querySelectorAll('.file-card').forEach(card => {
      card.addEventListener('click', async (e) => {
        // Don't toggle if clicking buttons/controls
        if (e.target.closest('.file-card-actions') || e.target.closest('.file-depth-info')) return;

        const filename = card.dataset.filename;
        const bodyId = 'file-body-' + filename.replace(/\./g, '-');
        const bodyEl = document.getElementById(bodyId);
        if (!bodyEl) return;

        const wasExpanded = card.classList.contains('expanded');

        // Collapse all others
        container.querySelectorAll('.file-card.expanded').forEach(c => {
          if (c !== card) {
            c.classList.remove('expanded');
          }
        });

        if (wasExpanded) {
          card.classList.remove('expanded');
          return;
        }

        card.classList.add('expanded');
        bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">Loading preview...</div>';

        // Show raw anchored content (with ⚓ tags) if anchored, otherwise raw file
        const isAnchored = card.classList.contains('file-card-anchored');
        const previewUrl = isAnchored
          ? `/api/files/${encodeURIComponent(filename)}/preview?raw=true`
          : `/api/files/${encodeURIComponent(filename)}/preview?depth=-1`;

        try {
          const data = await apiFetch(previewUrl);
          if (data && data.content) {
            const isRaw = isAnchored && data.depth === 'raw';
            bodyEl.innerHTML = `
              <div class="file-preview-content ${isRaw ? 'file-preview-raw' : 'rendered-md'}">${isRaw ? esc(data.content) : markdownToHtml(data.content)}</div>
              <div class="file-preview-meta">${data.tokens} tokens${isRaw ? ' (anchored)' : ''}</div>
            `;
          } else {
            bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">No content</div>';
          }
        } catch (err) {
          bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">Preview failed</div>';
        }
      });
    });
  }

  function uploadSemanticFileWithProgress(file, onProgress) {
    return new Promise((resolve, reject) => {
      const report = (percent, stage) => {
        const bounded = Math.max(0, Math.min(100, Number(percent) || 0));
        if (typeof onProgress === 'function') onProgress(bounded, stage);
      };

      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.onprogress = (evt) => {
        if (evt.lengthComputable && evt.total > 0) {
          const pct = Math.round((evt.loaded / evt.total) * 45);
          report(pct, 'Reading');
        }
      };
      reader.onload = () => {
        const content = typeof reader.result === 'string'
          ? reader.result
          : String(reader.result || '');
        const payload = JSON.stringify({ filename: file.name, content });
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/files/upload', true);
        xhr.setRequestHeader('Content-Type', 'application/json');

        xhr.upload.onprogress = (evt) => {
          if (evt.lengthComputable && evt.total > 0) {
            const pct = 45 + Math.round((evt.loaded / evt.total) * 50);
            report(pct, 'Uploading');
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            report(100, 'Done');
            resolve();
            return;
          }
          reject(new Error(`Upload failed (${xhr.status})`));
        };
        xhr.onerror = () => reject(new Error('Network error'));
        xhr.onabort = () => reject(new Error('Upload aborted'));

        report(50, 'Uploading');
        xhr.send(payload);
      };

      report(0, 'Reading');
      reader.readAsText(file);
    });
  }

  async function handleSemanticUpload(fileList, container) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;

    const dropzone = container.querySelector('#semantic-dropzone');
    const input = container.querySelector('#semantic-file-input');
    const progressRoot = container.querySelector('#semantic-upload-progress');

    if (dropzone) dropzone.classList.add('uploading');
    if (input) input.disabled = true;

    let rowByIndex = new Map();
    let progressByIndex = new Map();

    if (progressRoot) {
      const rows = files.map((file, index) => {
        const safeName = esc(file.name);
        return `
          <div class="semantic-upload-item" data-upload-index="${index}">
            <div class="semantic-upload-item-top">
              <span class="semantic-upload-item-name">${safeName}</span>
              <span class="semantic-upload-item-status">Queued</span>
            </div>
            <div class="semantic-upload-item-track">
              <div class="semantic-upload-item-fill" style="width:0%"></div>
            </div>
          </div>
        `;
      }).join('');

      progressRoot.innerHTML = `
        <div class="semantic-upload-summary">
          <span class="semantic-upload-summary-title">Uploading ${files.length} file${files.length > 1 ? 's' : ''}</span>
          <span class="semantic-upload-summary-percent">0%</span>
        </div>
        <div class="semantic-upload-summary-track">
          <div class="semantic-upload-summary-fill" style="width:0%"></div>
        </div>
        <div class="semantic-upload-items">${rows}</div>
      `;
      progressRoot.hidden = false;

      progressRoot.querySelectorAll('.semantic-upload-item').forEach((row) => {
        const idx = parseInt(row.dataset.uploadIndex, 10);
        if (!Number.isNaN(idx)) rowByIndex.set(idx, row);
      });
    }

    const updateOverallProgress = () => {
      if (!progressRoot || !files.length) return;
      let total = 0;
      files.forEach((_, index) => { total += progressByIndex.get(index) || 0; });
      const pct = Math.round(total / files.length);
      const pctEl = progressRoot.querySelector('.semantic-upload-summary-percent');
      const fillEl = progressRoot.querySelector('.semantic-upload-summary-fill');
      if (pctEl) pctEl.textContent = `${pct}%`;
      if (fillEl) fillEl.style.width = `${pct}%`;
    };

    const updateFileProgress = (index, percent, label) => {
      progressByIndex.set(index, percent);
      const row = rowByIndex.get(index);
      if (row) {
        const statusEl = row.querySelector('.semantic-upload-item-status');
        const fillEl = row.querySelector('.semantic-upload-item-fill');
        if (statusEl) statusEl.textContent = label ? `${label} ${percent}%` : `${percent}%`;
        if (fillEl) fillEl.style.width = `${percent}%`;
      }
      updateOverallProgress();
    };

    let successCount = 0;
    let failureCount = 0;

    for (const [index, file] of files.entries()) {
      progressByIndex.set(index, 0);
      const row = rowByIndex.get(index);
      if (row) row.classList.remove('error', 'done');

      try {
        await uploadSemanticFileWithProgress(file, (percent, stage) => {
          updateFileProgress(index, percent, stage || 'Uploading');
        });
        successCount += 1;
        updateFileProgress(index, 100, 'Done');
        if (row) row.classList.add('done');
      } catch (err) {
        failureCount += 1;
        updateFileProgress(index, 100, 'Failed');
        if (row) row.classList.add('error');
        showToast('Upload failed: ' + file.name, 'error');
      }
    }

    if (successCount > 0) {
      showToast(
        `Uploaded ${successCount} file${successCount > 1 ? 's' : ''}` +
        (failureCount > 0 ? ` (${failureCount} failed)` : ''),
        failureCount > 0 ? '' : 'success'
      );
    }

    if (dropzone) dropzone.classList.remove('uploading');
    if (input) input.disabled = false;
    renderSemanticMemory(container);
  }

  // ---- Settings Page ----
  async function loadSettings() {
    const data = await apiFetch('/api/settings');
    if (data && data.settings) {
      state.settingsCache = data.settings;
      if (state.activePage === 'dashboard' || state.activePage === 'settings') {
        renderPage();
      }
    }
  }

  async function loadDeployedSeeds(hadLocalDraft) {
    const data = await apiFetch('/api/seeds');
    if (!data || !data.files || typeof data.files !== 'object') return;

    const userMd = typeof data.files['user.md'] === 'string' ? data.files['user.md'] : '';
    const agentMd = typeof data.files['agent.md'] === 'string' ? data.files['agent.md'] : '';

    if (userMd || agentMd) {
      state.seedSync.deploymentKnown = true;
      state.seedSync.deployedHash = _seedFingerprint(userMd, agentMd);

      // Fresh session: initialize editor from deployed files.
      if (!hadLocalDraft) {
        if (userMd) parseUserMarkdown(userMd);
        if (agentMd) parseAgentMarkdown(agentMd);
      }
    }
  }

  function renderSettingsPage(container) {
    const s = state.settingsCache || {};
    const llm = s.llm_provider || {};
    const status = state.statusCache || {};
    const daemonHealth = status.daemon_health && typeof status.daemon_health === 'object'
      ? status.daemon_health
      : null;
    let daemonHealthHtml = '';
    if (daemonHealth) {
      const issues = Array.isArray(daemonHealth.issues) ? daemonHealth.issues : [];
      const issueLabels = issues.map((issue) => {
        if (issue === 'daemon_not_running') return 'Daemon process is not running.';
        if (issue === 'notes_lagging') return `Notes are lagging by ${formatDuration(status.daemon_lag_seconds || 0)}.`;
        if (issue === 'no_notes_generated') return 'No notes generated yet from available transcripts.';
        return issue;
      });
      let summary = '';
      if (daemonHealth.state === 'healthy') {
        summary = 'Daemon capture looks healthy.';
      } else if (daemonHealth.state === 'disabled') {
        summary = 'Daemon capture is disabled.';
      } else if (issueLabels.length) {
        summary = issueLabels.join(' ');
      } else {
        summary = 'Daemon needs attention.';
      }

      daemonHealthHtml = `
        <div class="settings-daemon-health settings-daemon-health-${esc(daemonHealth.state || 'idle')}">
          <div class="settings-daemon-health-header">
            <span class="settings-daemon-health-badge">${esc((daemonHealth.state || 'idle').toUpperCase())}</span>
            <span class="settings-daemon-health-summary">${esc(summary)}</span>
          </div>
          <div class="settings-daemon-health-meta">
            <span>Last note: ${esc(formatRelativeTime(status.last_note_date))}</span>
            <span>Last transcript: ${esc(formatRelativeTime(status.last_transcript_date))}</span>
          </div>
        </div>
      `;
    }
    const statusUnavailable = !state.serverConnected || !state.statusCache;
    const statusWarningHtml = statusUnavailable ? `
      <div class="settings-status-warning">
        <div class="settings-status-warning-header">
          <strong>Server status unavailable</strong>
          <span>Some live reliability indicators are hidden.</span>
        </div>
        <div class="settings-status-warning-actions">
          <button class="btn btn-primary btn-small" id="settings-retry-status-btn">Retry Status Check</button>
        </div>
      </div>
    ` : '';

    container.innerHTML = `
      <div class="settings-page">
        <div class="page-header">
          <h1>Settings</h1>
          <p>Configure your Memorable instance</p>
        </div>

        ${statusWarningHtml}

        <div class="settings-grid">
          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon ochre">&#9788;</div>
              <h3>Appearance</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Theme</div>
                  <div class="settings-row-desc">Choose light, dark, or follow your system setting</div>
                </div>
                <div class="settings-row-control">
                  <div class="theme-toggle" id="theme-toggle">
                    <button class="theme-toggle-btn" data-theme="light">Light</button>
                    <button class="theme-toggle-btn" data-theme="auto">Auto</button>
                    <button class="theme-toggle-btn" data-theme="dark">Dark</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon terracotta">&#9881;</div>
              <h3>LLM Provider</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">API Endpoint</div>
                  <div class="settings-row-desc">e.g. https://api.deepseek.com/v1</div>
                </div>
                <div class="settings-row-control">
                  <input type="text" id="settings-llm-endpoint" value="${esc(llm.endpoint || '')}" placeholder="https://api.deepseek.com/v1">
                </div>
              </div>
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">API Key</div>
                  <div class="settings-row-desc">Stored locally, never sent anywhere</div>
                </div>
                <div class="settings-row-control">
                  <input type="password" id="settings-llm-apikey" value="${esc(llm.api_key || '')}" placeholder="sk-...">
                </div>
              </div>
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Model</div>
                  <div class="settings-row-desc">e.g. deepseek-chat, gpt-4o-mini</div>
                </div>
                <div class="settings-row-control">
                  <input type="text" id="settings-llm-model" value="${esc(llm.model || '')}" placeholder="deepseek-chat">
                </div>
              </div>
            </div>
          </div>

          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon sage">&#9783;</div>
              <h3>Token Budget</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Budget Limit</div>
                  <div class="settings-row-desc" id="token-budget-display">${formatTokens(s.token_budget || 200000)} tokens</div>
                </div>
                <div class="settings-row-control" style="flex:1;max-width:400px;">
                  <input type="range" id="settings-token-budget" min="50000" max="500000" step="10000" value="${s.token_budget || 200000}" style="width:100%;">
                </div>
              </div>
            </div>
          </div>

          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon sand">&#9672;</div>
              <h3 title="Background process that watches sessions and auto-generates notes.">Daemon</h3>
            </div>
            <div class="settings-section-body">
              ${daemonHealthHtml}
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Daemon Enabled</div>
                  <div class="settings-row-desc">Watch sessions and auto-generate notes</div>
                </div>
                <div class="settings-row-control">
                  <label class="switch">
                    <input type="checkbox" id="settings-daemon-enabled" ${(s.daemon || {}).enabled !== false ? 'checked' : ''}>
                    <span class="switch-track"></span>
                  </label>
                </div>
              </div>
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Idle Threshold</div>
                  <div class="settings-row-desc">Seconds of inactivity before processing a session</div>
                </div>
                <div class="settings-row-control">
                  <input type="number" id="settings-idle-threshold" value="${(s.daemon || {}).idle_threshold || 300}" min="60" max="3600">
                </div>
              </div>
            </div>
          </div>

          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon ochre">&#128193;</div>
              <h3>Data</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Data Directory</div>
                  <div class="settings-row-desc">Where Memorable stores all local data</div>
                </div>
                <div class="settings-row-control">
                  <span class="settings-path-display">${esc(s.data_dir || '~/.memorable/data')}</span>
                </div>
              </div>
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Server Port</div>
                  <div class="settings-row-desc">Port for the web UI server</div>
                </div>
                <div class="settings-row-control">
                  <input type="number" id="settings-port" value="${s.server_port || 7777}" min="1024" max="65535">
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="settings-actions">
          <button class="btn btn-primary" id="settings-save-btn">Save Settings</button>
        </div>

        <div class="settings-grid" style="margin-top:20px;">
          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon sage">&#128268;</div>
              <h3>Backups</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Export All Data</div>
                  <div class="settings-row-desc">Download all seeds, notes, and settings as a ZIP archive</div>
                </div>
                <div class="settings-row-control">
                  <button class="btn btn-small" id="settings-export-btn">Export</button>
                </div>
              </div>
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Import Data</div>
                  <div class="settings-row-desc">Restore from a previous export</div>
                </div>
                <div class="settings-row-control">
                  <button class="btn btn-small" id="settings-import-btn">Import ZIP</button>
                  <input type="file" id="settings-import-input" accept=".zip,application/zip" style="display:none">
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="settings-grid" style="margin-top:20px;">
          <div class="settings-section settings-danger-zone">
            <div class="settings-section-header">
              <h3>Danger Zone</h3>
            </div>
            <div class="settings-section-body">
              <div class="settings-row">
                <div class="settings-row-info">
                  <div class="settings-row-label">Reset All Data</div>
                  <div class="settings-row-desc">Delete all local data and start fresh</div>
                </div>
                <div class="settings-row-control">
                  <button class="btn btn-small btn-danger-ghost" id="settings-reset-btn">Reset Everything</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      const current = localStorage.getItem('memorable-theme') || 'auto';
      themeToggle.querySelector(`[data-theme="${current}"]`).classList.add('active');
      themeToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('.theme-toggle-btn');
        if (!btn) return;
        themeToggle.querySelectorAll('.theme-toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        localStorage.setItem('memorable-theme', btn.dataset.theme);
        applyTheme();
      });
    }

    const retryStatusBtn = document.getElementById('settings-retry-status-btn');
    if (retryStatusBtn) {
      retryStatusBtn.addEventListener('click', async () => {
        await Promise.all([checkServerStatus(), loadSettings()]);
        showToast('Status refreshed', 'success');
      });
    }

    // Token budget slider
    const budgetSlider = document.getElementById('settings-token-budget');
    if (budgetSlider) {
      budgetSlider.addEventListener('input', () => {
        document.getElementById('token-budget-display').textContent = formatTokens(parseInt(budgetSlider.value)) + ' tokens';
      });
    }

    // Save
    const saveBtn = document.getElementById('settings-save-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        const settings = {
          llm_provider: {
            endpoint: document.getElementById('settings-llm-endpoint').value,
            api_key: document.getElementById('settings-llm-apikey').value,
            model: document.getElementById('settings-llm-model').value
          },
          token_budget: parseInt(document.getElementById('settings-token-budget').value),
          daemon: {
            enabled: document.getElementById('settings-daemon-enabled').checked,
            idle_threshold: parseInt(document.getElementById('settings-idle-threshold').value)
          },
          server_port: parseInt(document.getElementById('settings-port').value)
        };
        const result = await apiFetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings)
        });
        if (result) {
          state.settingsCache = { ...state.settingsCache, ...settings };
          showToast('Settings saved', 'success');
        } else {
          showToast('Failed to save settings (server offline?)', '');
        }
      });
    }

    // Export
    const exportBtn = document.getElementById('settings-export-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', async () => {
        try {
          const resp = await fetch('/api/export');
          if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
          const blob = await resp.blob();
          const cd = resp.headers.get('Content-Disposition') || '';
          const match = cd.match(/filename="([^"]+)"/i);
          const filename = match ? match[1] : 'memorable-export.zip';
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          showToast('Data exported as ZIP', 'success');
        } catch (err) {
          console.warn('Export failed:', err);
          // Fallback: export local state snapshot as JSON
          const blob = new Blob([JSON.stringify(state, null, 2)], {
            type: 'application/json'
          });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'memorable-export.json';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          showToast('Exported local data (server offline)', '');
        }
      });
    }

    // Import
    const importBtn = document.getElementById('settings-import-btn');
    const importInput = document.getElementById('settings-import-input');
    if (importBtn && importInput) {
      importBtn.addEventListener('click', () => importInput.click());
      importInput.addEventListener('change', async () => {
        const file = importInput.files && importInput.files[0];
        importInput.value = '';
        if (!file) return;

        const proceed = confirm(
          `Import data from "${file.name}"? This will replace your current local data.`
        );
        if (!proceed) return;

        const token = prompt('Type IMPORT to confirm restore.');
        if (token === null) return;
        if (token.trim() !== 'IMPORT') {
          showToast('Import canceled (token mismatch)', '');
          return;
        }

        try {
          const resp = await fetch('/api/import', {
            method: 'POST',
            headers: {
              'Content-Type': file.type || 'application/zip',
              'X-Confirmation-Token': token.trim(),
              'X-Filename': file.name
            },
            body: file
          });

          let data = null;
          try {
            data = await resp.json();
          } catch (_) {
            data = null;
          }

          if (!resp.ok) {
            const msg = (data && data.error && data.error.message)
              ? data.error.message
              : `Import failed (${resp.status})`;
            throw new Error(msg);
          }

          localStorage.removeItem('seedConfigurator');
          const restored = data && typeof data.restored_files === 'number'
            ? data.restored_files
            : 0;
          showToast(`Imported ${restored} files`, 'success');
          location.reload();
        } catch (err) {
          console.warn('Import failed:', err);
          showToast(`Import failed: ${err.message}`, 'error');
        }
      });
    }

    // Reset
    const resetBtn = document.getElementById('settings-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', async () => {
        if (confirm('Reset ALL data? This cannot be undone.')) {
          const token = prompt('Type RESET to confirm permanent deletion.');
          if (token === null) return;
          if (token.trim() !== 'RESET') {
            showToast('Reset canceled (token mismatch)', '');
            return;
          }

          const result = await apiFetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmation_token: token.trim() })
          });

          if (result && result.ok) {
            localStorage.removeItem('seedConfigurator');
            showToast('All data reset', 'success');
            location.reload();
          } else {
            showToast('Reset failed', '');
          }
        }
      });
    }
  }

  // ---- Seeds Page ----
  function renderSeedsPage(container) {
    container.innerHTML = `
      <div class="seeds-page">
        <div class="seeds-header">
          <div class="seeds-sub-nav">
            <button class="seeds-tab ${state.activeFile === 'user' ? 'active' : ''}" data-seed-file="user">
              <span class="tab-icon">&#9786;</span>user.md
            </button>
            <button class="seeds-tab ${state.activeFile === 'agent' ? 'active' : ''}" data-seed-file="agent">
              <span class="tab-icon">&#9881;</span>agent.md
            </button>
          </div>
          <div class="seeds-view-controls" id="seeds-view-controls"></div>
        </div>
        <div class="seeds-layout" id="seeds-layout">
          <div class="seeds-editor-panel" id="seeds-editor-panel"></div>
          <div class="seeds-preview-panel card" id="seeds-preview-panel">
            <div class="card-header">
              <h3>Preview</h3>
              <span style="font-size:0.78rem;color:var(--text-muted);">${state.activeFile}.md</span>
            </div>
            <div class="preview-content" id="preview-content"></div>
          </div>
        </div>
      </div>
    `;

    // Bind seed file tabs
    container.querySelectorAll('.seeds-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        state.activeFile = btn.dataset.seedFile;
        renderSeedsPage(container);
      });
    });

    // Render view controls
    renderSeedsViewControls();
    // Render editor content
    renderSeedsContent();
    // Render preview
    renderPreview();
  }

  function renderSeedsViewControls() {
    const controls = document.getElementById('seeds-view-controls');
    if (!controls) return;
    const file = state.activeFile;
    const seedStatus = _seedStatusMeta();

    controls.innerHTML = `
      <div class="view-toggle">
        <button class="view-toggle-btn ${state.activeView === 'form' ? 'active' : ''}" data-view="form">Form Editor</button>
        <button class="view-toggle-btn ${state.activeView === 'markdown' ? 'active' : ''}" data-view="markdown">Markdown</button>
      </div>
      <div class="action-buttons">
        <span class="seed-sync-indicator ${seedStatus.className}" title="${esc(seedStatus.title)}">
          <span class="dot"></span>${esc(seedStatus.text)}
        </span>
        <span class="save-indicator save-state-idle"><span class="dot"></span> Draft auto-save on</span>
        <div class="history-controls">
          <button class="btn btn-small" id="seed-undo-btn" title="Undo (Cmd/Ctrl+Z)">Undo</button>
          <button class="btn btn-small" id="seed-redo-btn" title="Redo (Cmd/Ctrl+Shift+Z / Ctrl+Y)">Redo</button>
        </div>
        <button class="btn btn-primary" id="seed-deploy-btn" title="Write current user.md and agent.md to deployed seed files">
          Deploy
        </button>
        <button class="btn" onclick="window.memorableApp.showImportModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Import
        </button>
        <button class="btn" onclick="window.memorableApp.copyToClipboard('${file}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          Copy
        </button>
        <button class="btn" onclick="window.memorableApp.download('${file}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download
        </button>
      </div>
    `;

    controls.querySelectorAll('.view-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.activeView = btn.dataset.view;
        controls.querySelectorAll('.view-toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.view === state.activeView));
        renderSeedsContent();
        renderPreview();
        saveToLocalStorage();
      });
    });

    const undoBtn = document.getElementById('seed-undo-btn');
    const redoBtn = document.getElementById('seed-redo-btn');
    if (undoBtn) {
      undoBtn.addEventListener('click', () => {
        if (!window.memorableApp.undo()) {
          showToast('Nothing to undo', '');
        }
      });
    }
    if (redoBtn) {
      redoBtn.addEventListener('click', () => {
        if (!window.memorableApp.redo()) {
          showToast('Nothing to redo', '');
        }
      });
    }

    const deployBtn = document.getElementById('seed-deploy-btn');
    if (deployBtn) {
      deployBtn.addEventListener('click', async () => {
        const files = {
          'user.md': generateUserMarkdown(),
          'agent.md': generateAgentMarkdown(),
        };

        deployBtn.disabled = true;
        deployBtn.textContent = 'Deploying...';
        try {
          const result = await apiFetch('/api/seeds', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files }),
          });
          if (!result || !result.ok) {
            throw new Error('Deploy failed');
          }

          state.seedSync.deploymentKnown = true;
          state.seedSync.deployedHash = _seedFingerprint(files['user.md'], files['agent.md']);
          state.seedSync.deployedAt = new Date().toISOString();
          if (state.statusCache) state.statusCache.seeds_present = true;
          showToast('Seed files deployed', 'success');
          render();
        } catch (err) {
          showToast(err && err.message ? err.message : 'Failed to deploy seeds', 'error');
          renderSeedsViewControls();
        }
      });
    }
    updateHistoryControls();
  }

  function renderSeedsContent() {
    const editorPanel = document.getElementById('seeds-editor-panel');
    const previewPanel = document.getElementById('seeds-preview-panel');
    const layout = document.getElementById('seeds-layout');
    if (!editorPanel) return;

    if (state.activeView === 'form') {
      if (layout) layout.classList.remove('full-width');
      if (previewPanel) previewPanel.style.display = '';
      if (state.activeFile === 'user') {
        renderUserForm(editorPanel);
      } else {
        renderAgentForm(editorPanel);
      }
    } else {
      if (layout) layout.classList.remove('full-width');
      if (previewPanel) previewPanel.style.display = '';
      renderMarkdownEditor(editorPanel);
    }
  }

  // ---- Files Page ----
  function renderFilesPage(container) {
    container.innerHTML = `
      <div class="files-page">
        <div class="page-header">
          <div style="display:flex;align-items:center;gap:12px;">
            <h1>Files</h1>
            <span style="font-size:0.88rem;color:var(--text-muted);">${state.files.length} file${state.files.length !== 1 ? 's' : ''}</span>
          </div>
          <div class="action-buttons">
            <span class="save-indicator save-state-idle"><span class="dot"></span> Auto-save on</span>
          </div>
        </div>
        <div class="files-content" id="files-content"></div>
      </div>
    `;
    renderFilesTab(document.getElementById('files-content'));
  }

  // ---- Files Tab ----
  function renderFilesTab(container) {
    const files = state.files;
    const activeFile = files.find(f => f.id === state.activeFileId);

    let sidebarItems = '';
    if (files.length > 0) {
      sidebarItems = files.map(f => {
        const tokens = getFileTokens(f);
        const depthLabel = ANCHOR_DEPTHS.find(d => d.key === (f.anchorDepth || 'full'))?.label || 'Full';
        return `
          <div class="file-list-item ${f.id === state.activeFileId ? 'active' : ''}" data-file-id="${f.id}">
            <span class="file-list-item-icon">&#128196;</span>
            <div class="file-list-item-info">
              <div class="file-list-item-name">${esc(f.name)}</div>
              <div class="file-list-item-meta">${formatTokens(tokens)} tokens &middot; ${depthLabel}</div>
            </div>
            ${f.projectTag ? `<span class="file-list-item-tag">${esc(f.projectTag)}</span>` : ''}
          </div>
        `;
      }).join('');
    } else {
      sidebarItems = `<div style="padding:20px 16px;text-align:center;color:var(--text-muted);font-size:0.82rem;">No files yet</div>`;
    }

    let mainContent = '';
    if (activeFile) {
      const tokens = getFileTokens(activeFile);
      const sizeBytes = new Blob([activeFile.content || '']).size;
      const projects = state.user.projects.filter(p => p.name);
      const projectOptions = projects.map(p => `<option value="${esc(p.name)}" ${activeFile.projectTag === p.name ? 'selected' : ''}>${esc(p.name)}</option>`).join('');

      mainContent = `
        <div class="file-detail-card">
          <div class="file-detail-header">
            <div class="file-detail-title">
              <span>&#128196;</span>
              <span>${esc(activeFile.name)}</span>
            </div>
            <div class="file-detail-actions">
              <button class="btn btn-small" onclick="window.seedApp.copyFileContent('${activeFile.id}')">Copy</button>
              <button class="btn btn-small btn-danger-ghost" onclick="window.seedApp.removeFile('${activeFile.id}')">Remove</button>
            </div>
          </div>
          <div class="file-detail-meta">
            <div class="file-meta-item">
              <span class="file-meta-label">Size</span>
              <span class="file-meta-value">${formatBytes(sizeBytes)}</span>
            </div>
            <div class="file-meta-item">
              <span class="file-meta-label">Tokens</span>
              <span class="file-meta-value">${formatTokens(tokens)}</span>
            </div>
            <div class="file-meta-item">
              <span class="file-meta-label" title="How much detail to include when loading this document. Higher depth uses more tokens.">Anchor Depth</span>
              <select data-file-depth="${activeFile.id}" class="file-meta-value" title="How much detail to include when loading this document. Higher depth uses more tokens.">
                ${ANCHOR_DEPTHS.map(d => `<option value="${d.key}" ${(activeFile.anchorDepth || 'full') === d.key ? 'selected' : ''}>${d.label} &mdash; ${d.desc}</option>`).join('')}
              </select>
            </div>
            <div class="file-meta-item">
              <span class="file-meta-label">Project</span>
              <select data-file-project="${activeFile.id}" class="file-meta-value">
                <option value="">None</option>
                ${projectOptions}
              </select>
            </div>
          </div>
          <div class="file-detail-body">
            <textarea id="file-content-editor" placeholder="File content...">${esc(activeFile.content || '')}</textarea>
          </div>
        </div>
      `;
    } else {
      mainContent = `
        <div class="file-upload-zone" id="files-upload-zone">
          <div class="file-upload-zone-icon">&#128196;</div>
          <h3>Add context files</h3>
          <p>Upload documents, paste text, or drag files here.<br>
          These provide additional context for your AI agent.</p>
          <input type="file" id="files-upload-input" multiple accept=".md,.txt,.markdown,.json,.yaml,.yml,.csv,.xml,.html,.py,.js,.ts,.toml,.cfg,.ini,.log">
          <div class="file-upload-actions">
            <button class="btn" id="files-browse-btn">Browse Files</button>
            <button class="btn" id="files-paste-btn">Paste Text</button>
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="files-layout">
        <div class="files-sidebar">
          <div class="files-sidebar-header">
            <h3>Files</h3>
            <button class="btn btn-small" id="files-add-btn" title="Add file">&#43; Add</button>
          </div>
          <div class="files-sidebar-list">
            ${sidebarItems}
          </div>
        </div>
        <div class="files-main">
          ${mainContent}
        </div>
      </div>
    `;

    bindFilesTabEvents(container);
  }

  function bindFilesTabEvents(container) {
    // Sidebar file selection
    container.querySelectorAll('.file-list-item[data-file-id]').forEach(el => {
      el.addEventListener('click', () => {
        state.activeFileId = el.dataset.fileId;
        render();
      });
    });

    // File content editing
    const contentEditor = document.getElementById('file-content-editor');
    if (contentEditor) {
      contentEditor.addEventListener('input', debounce(() => {
        const file = state.files.find(f => f.id === state.activeFileId);
        if (file) {
          file.content = contentEditor.value;
          renderTokenBudget();
          debouncedSave();
        }
      }, 300));
    }

    // Anchor depth change
    container.querySelectorAll('[data-file-depth]').forEach(el => {
      el.addEventListener('change', () => {
        const file = state.files.find(f => f.id === el.dataset.fileDepth);
        if (file) {
          file.anchorDepth = el.value;
          render();
        }
      });
    });

    // Project tag change
    container.querySelectorAll('[data-file-project]').forEach(el => {
      el.addEventListener('change', () => {
        const file = state.files.find(f => f.id === el.dataset.fileProject);
        if (file) {
          file.projectTag = el.value || '';
          render();
        }
      });
    });

    // Add button
    const addBtn = document.getElementById('files-add-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        state.activeFileId = null;
        render();
      });
    }

    // Upload zone
    const uploadZone = document.getElementById('files-upload-zone');
    const uploadInput = document.getElementById('files-upload-input');
    const browseBtn = document.getElementById('files-browse-btn');
    const pasteBtn = document.getElementById('files-paste-btn');

    if (uploadZone) {
      uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
      uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
      uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFileUploads(e.dataTransfer.files);
      });
    }

    if (uploadInput) {
      uploadInput.addEventListener('change', () => {
        handleFileUploads(uploadInput.files);
      });
    }

    if (browseBtn) {
      browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (uploadInput) uploadInput.click();
      });
    }

    if (pasteBtn) {
      pasteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        addPastedFile();
      });
    }
  }

  function handleFileUploads(fileList) {
    Array.from(fileList).forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const newFile = {
          id: generateFileId(),
          name: file.name,
          content: e.target.result,
          anchorDepth: 'full',
          projectTag: ''
        };
        state.files.push(newFile);
        state.activeFileId = newFile.id;
        render();
        showToast(`Added ${file.name}`, 'success');
      };
      reader.readAsText(file);
    });
  }

  function addPastedFile() {
    const name = prompt('File name:', 'untitled.md');
    if (!name) return;
    const newFile = {
      id: generateFileId(),
      name: name,
      content: '',
      anchorDepth: 'full',
      projectTag: ''
    };
    state.files.push(newFile);
    state.activeFileId = newFile.id;
    render();
  }

  // ---- Preview ----
  function renderPreview() {
    const container = document.getElementById('preview-content');
    if (!container) return;
    const md = state.activeFile === 'user' ? generateUserMarkdown() : generateAgentMarkdown();
    container.innerHTML = markdownToHtml(md);
    markdownCache[state.activeFile] = md;
  }

  // ---- Token Budget ----
  function renderTokenBudget() {
    const container = document.getElementById('token-budget');
    if (!container) return;

    fetch('/api/budget')
      .then(r => r.json())
      .then(data => {
        const breakdown = Array.isArray(data && data.breakdown) ? data.breakdown : [];
        const total = Number.isFinite(data && data.used) ? data.used : 0;
        const maxTokens = Number.isFinite(data && data.budget) && data.budget > 0 ? data.budget : 1;
        const pct = (n) => Math.max(0, Math.min(100, (n / maxTokens) * 100));
        const expanded = state.tokenBudgetExpanded;

        const seeds = breakdown.filter(b => b && b.type === 'seed');
        const semantics = breakdown.filter(b => b && b.type === 'semantic');
        const seedTokens = seeds.reduce((s, b) => s + b.tokens, 0);
        const semanticTokens = semantics.reduce((s, b) => s + b.tokens, 0);

        const detailRows = breakdown.map(b => {
          const icon = b.type === 'seed' ? '&#128203;' : '&#9875;';
          const depthLabel = b.type === 'semantic' && b.depth !== undefined
            ? `<span class="depth-badge">depth ${b.depth}</span>` : '';
          return `
            <div class="token-detail-row">
              <span class="token-detail-name">${icon} ${esc(b.file)} ${depthLabel}</span>
              <span class="token-detail-count">${formatTokens(b.tokens)} tokens</span>
            </div>
          `;
        }).join('');

        container.innerHTML = `
          <div class="token-budget-bar ${expanded ? 'expanded' : ''}" id="token-budget-bar">
            <div class="token-budget-header">
              <span class="token-budget-label">
                Context Budget
                <span class="token-budget-chevron">&#9660;</span>
              </span>
              <span class="token-budget-total">${formatTokens(total)} / ${formatTokens(maxTokens)} tokens</span>
            </div>
            <div class="token-budget-track">
              <div class="token-budget-segment user-seg" style="width:${pct(seedTokens)}%"></div>
              <div class="token-budget-segment files-seg" style="width:${pct(semanticTokens)}%"></div>
            </div>
            <div class="token-budget-legend">
              <span class="token-legend-item"><span class="token-legend-dot user-dot"></span>Seeds: ${formatTokens(seedTokens)}</span>
              <span class="token-legend-item"><span class="token-legend-dot files-dot"></span>Semantic: ${formatTokens(semanticTokens)}</span>
            </div>
            <div class="token-budget-detail">
              ${detailRows}
              <div class="token-detail-row" style="font-weight:600;margin-top:4px;padding-top:8px;border-top:1px solid var(--border);">
                <span class="token-detail-name">Total</span>
                <span class="token-detail-count">${formatTokens(total)} tokens</span>
              </div>
            </div>
          </div>
        `;

        document.getElementById('token-budget-bar').addEventListener('click', () => {
          state.tokenBudgetExpanded = !state.tokenBudgetExpanded;
          document.getElementById('token-budget-bar').classList.toggle('expanded');
        });
      })
      .catch(() => {
        container.innerHTML = '<div class="token-budget-bar"><div class="token-budget-header"><span>Context Budget</span><span>Error loading</span></div></div>';
      });
  }

  function renderPresetBar() {
    const isUser = state.activeFile === 'user';
    return `
      <div class="preset-bar">
        <div class="preset-bar-label">Use Case Preset</div>
        <div class="preset-group">
          ${Object.entries(PRESETS).map(([key, preset]) => `
            <button class="preset-btn ${state.preset === key ? 'active' : ''}" data-preset="${key}">${preset.label}</button>
          `).join('')}
        </div>
        <div class="preset-bar-hint">Presets suggest which sections to enable. You can always toggle any section on or off individually.</div>
      </div>
    `;
  }

  // ---- Section Toggle Rendering ----
  function renderSection(id, title, subtitle, colorClass, icon, body, emptyHint) {
    const enabled = state.enabledSections[id] !== false;
    const disabledClass = enabled ? '' : 'section-disabled';
    const collapsedClass = state.collapsedSections[id] ? 'collapsed' : '';
    const density = getSectionDensity(id);
    const materialityClass = 'materiality-' + density;
    return `
      <div class="section ${disabledClass} ${collapsedClass} ${materialityClass}" id="section-${id}">
        <div class="section-header">
          <div class="section-header-left" onclick="window.seedApp.toggleSection('section-${id}')">
            <div class="section-icon ${colorClass}">${icon}</div>
            <div>
              <div class="section-title">${title}</div>
              <div class="section-subtitle">${subtitle}</div>
            </div>
          </div>
          <div class="section-header-right">
            <label class="section-toggle" onclick="event.stopPropagation()">
              <input type="checkbox" ${enabled ? 'checked' : ''} data-section-toggle="${id}">
              <span class="section-toggle-track"></span>
            </label>
            <span class="section-chevron" onclick="window.seedApp.toggleSection('section-${id}')">&#9660;</span>
          </div>
        </div>
        <div class="section-body">
          ${body}
        </div>
      </div>
    `;
  }

  // ---- User Form ----
  function renderUserForm(container) {
    const u = state.user;
    container.innerHTML = `
      ${renderPresetBar()}

      ${renderSection('identity', 'Identity', 'Who you are', 'terracotta', '&#9733;', `
        <div class="form-row">
          <div class="form-group">
            <label>Name</label>
            <input type="text" data-bind="user.identity.name" value="${esc(u.identity.name)}" placeholder="Your name">
          </div>
          <div class="form-group">
            <label>Age</label>
            <input type="text" data-bind="user.identity.age" value="${esc(u.identity.age)}" placeholder="e.g. 34">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Location</label>
            <input type="text" data-bind="user.identity.location" value="${esc(u.identity.location)}" placeholder="City, country">
          </div>
          <div class="form-group">
            <label>Pronouns</label>
            <input type="text" data-bind="user.identity.pronouns" value="${esc(u.identity.pronouns)}" placeholder="e.g. he/him, she/her, they/them">
          </div>
        </div>
      `)}

      ${renderSection('about', 'About', 'A brief bio or description', 'sage', '&#9998;', `
        <div class="form-group">
          <textarea data-bind="user.about" rows="4" placeholder="Tell the agent about yourself. What matters to you? What should it know?">${esc(u.about)}</textarea>
        </div>
      `)}

      ${renderSection('cognitive', 'Cognitive Style', 'Neurodivergence and cognitive differences', 'sand', '&#10024;', `
        <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:10px;">Select any that apply. This helps the agent adapt its communication style.</p>
        <div class="toggle-group" id="cognitive-toggles">
          ${u.cognitiveOptions.map(k => {
            const active = u.cognitiveActive[k];
            const isCustom = !isDefaultCognitive(k);
            return `
              <div class="toggle-item ${active ? 'active' : ''}" data-cognitive="${k}">
                <span class="toggle-check">${active ? '&#10003;' : ''}</span>
                ${getCognitiveLabel(k)}
                ${isCustom ? `<button class="toggle-remove" data-remove-cognitive="${k}" title="Remove">&#10005;</button>` : ''}
              </div>
            `;
          }).join('')}
          <div class="toggle-item custom-toggle" id="add-cognitive-btn">
            <span style="font-size:0.9em;">&#43;</span> Add custom...
          </div>
        </div>
      `)}

      ${renderSection('values', 'Values', 'Ranked preferences that guide responses', 'terracotta', '&#9878;', `
        <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:10px;">What matters more? Left side is preferred over right side.</p>
        <div class="value-pairs" id="value-pairs">
          ${u.values.map((v, i) => `
            <div class="value-pair" data-index="${i}">
              <input type="text" value="${esc(v.higher)}" data-pair="higher" placeholder="More important">
              <span class="separator">&gt;</span>
              <input type="text" value="${esc(v.lower)}" data-pair="lower" placeholder="Less important">
              <button class="btn btn-icon btn-danger-ghost" data-remove-value="${i}" title="Remove">&#10005;</button>
            </div>
          `).join('')}
        </div>
        <button class="add-item-btn" id="add-value-btn">&#43; Add value pair</button>
      `)}

      ${renderSection('communication', 'Communication Preferences', 'How the agent should talk to you', 'sage', '&#128172;', `
        <div id="communication-switches">
          ${u.communicationOptions.map(k => {
            const isCustom = !isDefaultComm(k);
            return renderSwitchRowWithRemove('user.communicationActive.' + k, getCommLabel(k), getCommDesc(k), !!u.communicationActive[k], isCustom ? k : null, 'comm');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-comm-btn" style="margin-top:12px;">&#43; Add custom preference...</button>
      `)}

      ${renderSection('people', 'People', 'People the agent should know about', 'clay', '&#9824;', `
        <div class="repeatable-list" id="people-list" data-reorder-list="people">
          ${u.people.length ? u.people.map((p, i) => renderPersonItem(p, i)).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">&#128101;</div>
              <h3>No people added yet</h3>
              <p>Add people the agent should know about &mdash; family, friends, colleagues, or anyone relevant to your conversations.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-person-btn">&#43; Add person</button>
      `)}

      ${renderSection('projects', 'Projects', 'Active projects and their context', 'sand', '&#128193;', `
        <div class="repeatable-list" id="projects-list" data-reorder-list="projects">
          ${u.projects.length ? u.projects.map((p, i) => renderProjectItem(p, i)).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">&#128194;</div>
              <h3>No projects added yet</h3>
              <p>Add projects you're working on so the agent has context about your work.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-project-btn">&#43; Add project</button>
      `)}

      ${renderSection('user-custom', 'Custom Sections', 'Add your own sections', 'terracotta', '&#43;', `
        <div class="custom-sections" id="user-custom-sections" data-reorder-list="user-custom">
          ${u.customSections.length ? u.customSections.map((s, i) => renderCustomSectionItem(s, i, 'user')).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">&#9997;</div>
              <h3>No custom sections</h3>
              <p>Add anything else the agent should know &mdash; health context, work environment, preferences, routines, or any other relevant information.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-user-custom-btn">&#43; Add custom section</button>
      `)}
    `;

    bindFormEvents(container);
    bindUserSpecificEvents(container);
    bindPresetEvents(container);
    bindSectionToggleEvents(container);
    bindReorderEvents(container);
    applySectionFadeIn(container);
  }

  // ---- Agent Form ----
  function renderAgentForm(container) {
    const a = state.agent;
    container.innerHTML = `
      ${renderPresetBar()}

      ${renderSection('agent-name', 'Name', 'What the agent calls itself', 'sage', '&#9881;', `
        <div class="form-group">
          <label>Agent Name</label>
          <input type="text" data-bind="agent.name" value="${esc(a.name)}" placeholder="e.g. Claude, Aria, Helper">
        </div>
      `)}

      ${renderSection('traits', 'Character Traits', 'Personality sliders', 'terracotta', '&#9734;', `
        <div id="trait-sliders">
          ${a.traitOptions.map(key => renderSlider(key, getTraitLabel(key), a.traits[key] || 50, getTraitEndpoints(key), !isDefaultTrait(key))).join('')}
        </div>
        <button class="add-item-btn" id="add-trait-btn" style="margin-top:12px;">&#43; Add custom trait...</button>
      `)}

      ${renderSection('behaviors', 'Behaviors', 'What the agent should do', 'sage', '&#10003;', `
        <div class="toggle-group" id="behavior-toggles">
          ${a.behaviorOptions.map(k => {
            const active = a.behaviorsActive[k];
            const isCustom = !isDefaultBehavior(k);
            return `
              <div class="toggle-item ${active ? 'active' : ''}" data-behavior="${k}">
                <span class="toggle-check">${active ? '&#10003;' : ''}</span>
                ${getBehaviorLabel(k)}
                ${isCustom ? `<button class="toggle-remove" data-remove-behavior="${k}" title="Remove">&#10005;</button>` : ''}
              </div>
            `;
          }).join('')}
          <div class="toggle-item custom-toggle" id="add-behavior-btn">
            <span style="font-size:0.9em;">&#43;</span> Add custom...
          </div>
        </div>
      `)}

      ${renderSection('avoid', 'Avoid', 'Things the agent should not do', 'sand', '&#10007;', `
        <div class="tag-list" id="avoid-tags">
          ${a.avoid.length ? a.avoid.map((item, i) => `
            <span class="tag">${esc(item)}<button class="tag-remove" data-remove-avoid="${i}">&#10005;</button></span>
          `).join('') : ''}
        </div>
        ${a.avoid.length === 0 ? `
          <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:8px;">Add things the agent should avoid in its responses &mdash; tones, phrases, or behaviors you dislike.</p>
        ` : ''}
        <div class="tag-input-row">
          <input type="text" id="avoid-input" placeholder="Add something to avoid, e.g. 'patronizing tone'" onkeydown="if(event.key==='Enter'){window.seedApp.addAvoid();event.preventDefault();}">
          <button class="btn btn-small" onclick="window.seedApp.addAvoid()">Add</button>
        </div>
      `)}

      ${renderSection('when-low', 'When User Is Low', 'How to behave when the user seems down', 'clay', '&#9829;', `
        <div id="when-low-switches">
          ${a.whenLowOptions.map(k => {
            const isCustom = !isDefaultWhenLow(k);
            return renderSwitchRowWithRemove('agent.whenLowActive.' + k, getWhenLowLabel(k), getWhenLowDesc(k), !!a.whenLowActive[k], isCustom ? k : null, 'whenlow');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-whenlow-btn" style="margin-top:12px;">&#43; Add custom behavior...</button>
      `)}

      ${renderSection('tech-style', 'Technical Style', 'Code and technical preferences', 'terracotta', '&#128187;', `
        <div id="tech-style-switches">
          ${a.techStyleOptions.map(k => {
            const isCustom = !isDefaultTech(k);
            return renderSwitchRowWithRemove('agent.techStyleActive.' + k, getTechLabel(k), getTechDesc(k), !!a.techStyleActive[k], isCustom ? k : null, 'techstyle');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-techstyle-btn" style="margin-top:12px;">&#43; Add custom preference...</button>
      `)}

      ${renderSection('agent-custom', 'Custom Sections', 'Add your own sections', 'sage', '&#43;', `
        <div class="custom-sections" id="agent-custom-sections" data-reorder-list="agent-custom">
          ${a.customSections.length ? a.customSections.map((s, i) => renderCustomSectionItem(s, i, 'agent')).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">&#9997;</div>
              <h3>No custom sections</h3>
              <p>Add anything else you want the agent to know about itself &mdash; role context, special instructions, domain expertise, etc.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-agent-custom-btn">&#43; Add custom section</button>
      `)}
    `;

    bindFormEvents(container);
    bindAgentSpecificEvents(container);
    bindPresetEvents(container);
    bindSectionToggleEvents(container);
    bindReorderEvents(container);
    applySectionFadeIn(container);
  }

  // ---- Partial Renderers ----
  function renderSwitchRow(bind, label, desc, checked) {
    return `
      <div class="switch-row">
        <div>
          <div class="switch-label">${label}</div>
          ${desc ? `<div class="switch-label-desc">${desc}</div>` : ''}
        </div>
        <label class="switch">
          <input type="checkbox" data-bind="${bind}" ${checked ? 'checked' : ''}>
          <span class="switch-track"></span>
        </label>
      </div>
    `;
  }

  function renderSwitchRowWithRemove(bind, label, desc, checked, removeKey, removeType) {
    return `
      <div class="switch-row">
        <div>
          <div class="switch-label">${label}</div>
          ${desc ? `<div class="switch-label-desc">${desc}</div>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          <label class="switch">
            <input type="checkbox" data-bind="${bind}" ${checked ? 'checked' : ''}>
            <span class="switch-track"></span>
          </label>
          ${removeKey ? `<button class="switch-remove-btn" data-remove-switchrow="${removeKey}" data-remove-type="${removeType}" title="Remove">&#10005;</button>` : ''}
        </div>
      </div>
    `;
  }

  function renderSlider(key, label, value, endpoints, removable) {
    const desc = getTraitDescription(key, value);
    return `
      <div class="slider-group">
        <div class="slider-header">
          <span class="slider-label">${label}</span>
          <span style="display:flex;align-items:center;gap:4px;">
            <span class="slider-value" id="slider-val-${key}">${desc}</span>
            ${removable ? `<button class="slider-remove-btn" data-remove-trait="${key}" title="Remove">&#10005;</button>` : ''}
          </span>
        </div>
        <input type="range" min="0" max="100" value="${value}" data-trait="${key}">
        <div class="slider-labels">
          <span>${endpoints[0]}</span>
          <span>${endpoints[1]}</span>
        </div>
      </div>
    `;
  }

  function renderPersonItem(p, i) {
    return `
      <div class="repeatable-item reorder-item" draggable="true" data-reorder-group="people" data-reorder-index="${i}" data-person-index="${i}">
        <div class="repeatable-item-header">
          <div class="repeatable-item-title">
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">&#8942;&#8942;</span>
            <strong style="font-size:0.88rem;">${p.name || 'New person'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-person="${i}" title="Remove">&#10005;</button>
        </div>
        <div class="repeatable-item-fields">
          <div class="repeatable-item-row">
            <div class="form-group">
              <label>Name</label>
              <input type="text" data-person="${i}" data-field="name" value="${esc(p.name)}" placeholder="Name">
            </div>
            <div class="form-group">
              <label>Relationship</label>
              <input type="text" data-person="${i}" data-field="relationship" value="${esc(p.relationship)}" placeholder="e.g. partner, coworker, friend">
            </div>
          </div>
          <div class="form-group">
            <label>Notes</label>
            <textarea data-person="${i}" data-field="notes" rows="2" placeholder="Anything the agent should know about this person">${esc(p.notes)}</textarea>
          </div>
        </div>
      </div>
    `;
  }

  function renderProjectItem(p, i) {
    return `
      <div class="repeatable-item reorder-item" draggable="true" data-reorder-group="projects" data-reorder-index="${i}" data-project-index="${i}">
        <div class="repeatable-item-header">
          <div class="repeatable-item-title">
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">&#8942;&#8942;</span>
            <strong style="font-size:0.88rem;">${p.name || 'New project'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-project="${i}" title="Remove">&#10005;</button>
        </div>
        <div class="repeatable-item-fields">
          <div class="repeatable-item-row">
            <div class="form-group">
              <label>Name</label>
              <input type="text" data-project="${i}" data-field="name" value="${esc(p.name)}" placeholder="Project name">
            </div>
            <div class="form-group">
              <label>Status</label>
              <select data-project="${i}" data-field="status" class="status-select">
                <option value="active" ${p.status === 'active' ? 'selected' : ''}>Active</option>
                <option value="paused" ${p.status === 'paused' ? 'selected' : ''}>Paused</option>
                <option value="planning" ${p.status === 'planning' ? 'selected' : ''}>Planning</option>
                <option value="completed" ${p.status === 'completed' ? 'selected' : ''}>Completed</option>
                <option value="archived" ${p.status === 'archived' ? 'selected' : ''}>Archived</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Description</label>
            <textarea data-project="${i}" data-field="description" rows="2" placeholder="What this project is about">${esc(p.description)}</textarea>
          </div>
        </div>
      </div>
    `;
  }

  function renderCustomSectionItem(s, i, type) {
    const group = type === 'user' ? 'user-custom' : 'agent-custom';
    return `
      <div class="custom-section-item reorder-item" draggable="true" data-reorder-group="${group}" data-reorder-index="${i}" data-custom-index="${i}" data-custom-type="${type}">
        <div class="repeatable-item-header">
          <div class="repeatable-item-title">
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">&#8942;&#8942;</span>
            <strong style="font-size:0.88rem;">${s.title || 'New section'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-custom="${i}" data-custom-type="${type}" title="Remove">&#10005;</button>
        </div>
        <div class="form-group">
          <label>Section Title</label>
          <input type="text" data-custom="${i}" data-custom-type="${type}" data-field="title" value="${esc(s.title)}" placeholder="e.g. Health Notes, Work Context">
        </div>
        <div class="form-group">
          <label>Content (Markdown)</label>
          <textarea data-custom="${i}" data-custom-type="${type}" data-field="content" rows="4" placeholder="Free-form content for this section...">${esc(s.content)}</textarea>
        </div>
      </div>
    `;
  }

  // ---- Event Binding ----
  function bindFormEvents(container) {
    container.querySelectorAll('[data-bind]').forEach(el => {
      const handler = () => {
        const path = el.dataset.bind.split('.');
        let obj = state;
        for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]];
        const key = path[path.length - 1];
        obj[key] = el.type === 'checkbox' ? el.checked : el.value;
        renderPreview();
        debouncedSave();
      };
      if (el.type === 'checkbox') {
        el.addEventListener('change', handler);
      } else {
        el.addEventListener('input', handler);
      }
    });
  }

  function bindSectionToggleEvents(container) {
    container.querySelectorAll('[data-section-toggle]').forEach(el => {
      el.addEventListener('change', () => {
        const sectionId = el.dataset.sectionToggle;
        state.enabledSections[sectionId] = el.checked;
        const sectionEl = document.getElementById('section-' + sectionId);
        if (sectionEl) {
          if (el.checked) {
            sectionEl.classList.remove('section-disabled');
          } else {
            sectionEl.classList.add('section-disabled');
          }
        }
        // Update preset to custom if user manually toggles
        state.preset = 'custom';
        renderPreview();
        debouncedSave();
      });
    });
  }

  function bindPresetEvents(container) {
    container.querySelectorAll('[data-preset]').forEach(btn => {
      btn.addEventListener('click', () => {
        const presetKey = btn.dataset.preset;
        applyPreset(presetKey);
        render();
      });
    });
  }

  function applyPreset(presetKey) {
    state.preset = presetKey;
    const preset = PRESETS[presetKey];
    if (!preset) return;

    // For user sections
    const userSectionIds = ['identity', 'about', 'cognitive', 'values', 'communication', 'people', 'projects', 'user-custom'];
    userSectionIds.forEach(id => {
      state.enabledSections[id] = preset.userSections.includes(id);
    });

    // For agent sections
    const agentSectionIds = ['agent-name', 'traits', 'behaviors', 'avoid', 'when-low', 'tech-style', 'agent-custom'];
    agentSectionIds.forEach(id => {
      state.enabledSections[id] = preset.agentSections.includes(id);
    });
  }

  function bindUserSpecificEvents(container) {
    // Cognitive toggles
    container.querySelectorAll('[data-cognitive]').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.toggle-remove')) return;
        const key = el.dataset.cognitive;
        state.user.cognitiveActive[key] = !state.user.cognitiveActive[key];
        el.classList.toggle('active');
        el.querySelector('.toggle-check').innerHTML = state.user.cognitiveActive[key] ? '&#10003;' : '';
        renderPreview();
        debouncedSave();
      });
    });

    // Remove cognitive custom items
    container.querySelectorAll('[data-remove-cognitive]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = btn.dataset.removeCognitive;
        state.user.cognitiveOptions = state.user.cognitiveOptions.filter(k => k !== key);
        delete state.user.cognitiveActive[key];
        delete state.user.cognitiveLabels[key];
        render();
      });
    });

    // Add custom cognitive
    const addCogBtn = document.getElementById('add-cognitive-btn');
    if (addCogBtn) {
      addCogBtn.addEventListener('click', () => {
        showInlineAdd(addCogBtn, (label) => {
          const key = labelToKey(label);
          if (!state.user.cognitiveOptions.includes(key)) {
            state.user.cognitiveOptions.push(key);
            state.user.cognitiveLabels[key] = label;
            state.user.cognitiveActive[key] = true;
          }
          render();
        });
      });
    }

    // Value pairs
    container.querySelectorAll('.value-pair input').forEach(el => {
      el.addEventListener('input', () => {
        const idx = parseInt(el.closest('.value-pair').dataset.index, 10);
        const field = el.dataset.pair;
        state.user.values[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      });
    });

    container.querySelectorAll('[data-remove-value]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeValue, 10);
        state.user.values.splice(idx, 1);
        if (state.user.values.length === 0) state.user.values.push({ higher: '', lower: '' });
        render();
      });
    });

    const addValueBtn = document.getElementById('add-value-btn');
    if (addValueBtn) {
      addValueBtn.addEventListener('click', () => {
        state.user.values.push({ higher: '', lower: '' });
        render();
      });
    }

    // Add custom communication preference
    const addCommBtn = document.getElementById('add-comm-btn');
    if (addCommBtn) {
      addCommBtn.addEventListener('click', () => {
        showInlineAdd(addCommBtn, (label) => {
          const key = labelToKey(label);
          if (!state.user.communicationOptions.includes(key)) {
            state.user.communicationOptions.push(key);
            state.user.communicationLabels[key] = label;
            state.user.communicationDescs[key] = '';
            state.user.communicationActive[key] = true;
          }
          render();
        });
      });
    }

    // Remove custom communication options
    container.querySelectorAll('[data-remove-switchrow][data-remove-type="comm"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeSwitchrow;
        state.user.communicationOptions = state.user.communicationOptions.filter(k => k !== key);
        delete state.user.communicationActive[key];
        delete state.user.communicationLabels[key];
        delete state.user.communicationDescs[key];
        render();
      });
    });

    // People
    container.querySelectorAll('[data-person]').forEach(el => {
      const handler = () => {
        const idx = parseInt(el.dataset.person, 10);
        const field = el.dataset.field;
        state.user.people[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      };
      el.addEventListener('input', handler);
    });

    container.querySelectorAll('[data-remove-person]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removePerson, 10);
        state.user.people.splice(idx, 1);
        render();
      });
    });

    const addPersonBtn = document.getElementById('add-person-btn');
    if (addPersonBtn) {
      addPersonBtn.addEventListener('click', () => {
        state.user.people.push({ name: '', relationship: '', notes: '' });
        render();
      });
    }

    // Projects
    container.querySelectorAll('[data-project]').forEach(el => {
      const handler = () => {
        const idx = parseInt(el.dataset.project, 10);
        const field = el.dataset.field;
        state.user.projects[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      };
      el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', handler);
    });

    container.querySelectorAll('[data-remove-project]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeProject, 10);
        state.user.projects.splice(idx, 1);
        render();
      });
    });

    const addProjectBtn = document.getElementById('add-project-btn');
    if (addProjectBtn) {
      addProjectBtn.addEventListener('click', () => {
        state.user.projects.push({ name: '', status: 'active', description: '' });
        render();
      });
    }

    // Custom sections (user)
    bindCustomSectionEvents(container, 'user');
  }

  function bindAgentSpecificEvents(container) {
    // Behavior toggles
    container.querySelectorAll('[data-behavior]').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.toggle-remove')) return;
        const key = el.dataset.behavior;
        state.agent.behaviorsActive[key] = !state.agent.behaviorsActive[key];
        el.classList.toggle('active');
        el.querySelector('.toggle-check').innerHTML = state.agent.behaviorsActive[key] ? '&#10003;' : '';
        renderPreview();
        debouncedSave();
      });
    });

    // Remove behavior custom items
    container.querySelectorAll('[data-remove-behavior]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = btn.dataset.removeBehavior;
        state.agent.behaviorOptions = state.agent.behaviorOptions.filter(k => k !== key);
        delete state.agent.behaviorsActive[key];
        delete state.agent.behaviorLabels[key];
        render();
      });
    });

    // Add custom behavior
    const addBehaviorBtn = document.getElementById('add-behavior-btn');
    if (addBehaviorBtn) {
      addBehaviorBtn.addEventListener('click', () => {
        showInlineAdd(addBehaviorBtn, (label) => {
          const key = labelToKey(label);
          if (!state.agent.behaviorOptions.includes(key)) {
            state.agent.behaviorOptions.push(key);
            state.agent.behaviorLabels[key] = label;
            state.agent.behaviorsActive[key] = true;
          }
          render();
        });
      });
    }

    // Trait sliders
    container.querySelectorAll('[data-trait]').forEach(el => {
      el.addEventListener('input', () => {
        const key = el.dataset.trait;
        const val = parseInt(el.value, 10);
        state.agent.traits[key] = val;
        const valLabel = document.getElementById('slider-val-' + key);
        if (valLabel) valLabel.textContent = getTraitDescription(key, val);
        renderPreview();
        debouncedSave();
      });
    });

    // Remove custom trait sliders
    container.querySelectorAll('[data-remove-trait]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeTrait;
        state.agent.traitOptions = state.agent.traitOptions.filter(k => k !== key);
        delete state.agent.traits[key];
        delete state.agent.traitLabels[key];
        delete state.agent.traitEndpoints[key];
        render();
      });
    });

    // Add custom trait
    const addTraitBtn = document.getElementById('add-trait-btn');
    if (addTraitBtn) {
      addTraitBtn.addEventListener('click', () => {
        showInlineAdd(addTraitBtn, (label) => {
          const key = labelToKey(label);
          if (!state.agent.traitOptions.includes(key)) {
            state.agent.traitOptions.push(key);
            state.agent.traitLabels[key] = label;
            state.agent.traitEndpoints[key] = ['Low', 'High'];
            state.agent.traits[key] = 50;
          }
          render();
        });
      });
    }

    // Avoid tags
    container.querySelectorAll('[data-remove-avoid]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeAvoid, 10);
        state.agent.avoid.splice(idx, 1);
        render();
      });
    });

    // When low: remove custom
    container.querySelectorAll('[data-remove-switchrow][data-remove-type="whenlow"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeSwitchrow;
        state.agent.whenLowOptions = state.agent.whenLowOptions.filter(k => k !== key);
        delete state.agent.whenLowActive[key];
        delete state.agent.whenLowLabels[key];
        delete state.agent.whenLowDescs[key];
        render();
      });
    });

    // Add custom when-low option
    const addWhenLowBtn = document.getElementById('add-whenlow-btn');
    if (addWhenLowBtn) {
      addWhenLowBtn.addEventListener('click', () => {
        showInlineAdd(addWhenLowBtn, (label) => {
          const key = labelToKey(label);
          if (!state.agent.whenLowOptions.includes(key)) {
            state.agent.whenLowOptions.push(key);
            state.agent.whenLowLabels[key] = label;
            state.agent.whenLowDescs[key] = '';
            state.agent.whenLowActive[key] = true;
          }
          render();
        });
      });
    }

    // Tech style: remove custom
    container.querySelectorAll('[data-remove-switchrow][data-remove-type="techstyle"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeSwitchrow;
        state.agent.techStyleOptions = state.agent.techStyleOptions.filter(k => k !== key);
        delete state.agent.techStyleActive[key];
        delete state.agent.techStyleLabels[key];
        delete state.agent.techStyleDescs[key];
        render();
      });
    });

    // Add custom tech style option
    const addTechBtn = document.getElementById('add-techstyle-btn');
    if (addTechBtn) {
      addTechBtn.addEventListener('click', () => {
        showInlineAdd(addTechBtn, (label) => {
          const key = labelToKey(label);
          if (!state.agent.techStyleOptions.includes(key)) {
            state.agent.techStyleOptions.push(key);
            state.agent.techStyleLabels[key] = label;
            state.agent.techStyleDescs[key] = '';
            state.agent.techStyleActive[key] = true;
          }
          render();
        });
      });
    }

    // Custom sections (agent)
    bindCustomSectionEvents(container, 'agent');
  }

  function bindCustomSectionEvents(container, type) {
    const prefix = type === 'user' ? 'user' : 'agent';
    container.querySelectorAll(`[data-custom][data-custom-type="${type}"]`).forEach(el => {
      if (el.tagName === 'BUTTON') return;
      const handler = () => {
        const idx = parseInt(el.dataset.custom, 10);
        const field = el.dataset.field;
        state[prefix].customSections[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      };
      el.addEventListener('input', handler);
    });

    container.querySelectorAll(`[data-remove-custom][data-custom-type="${type}"]`).forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeCustom, 10);
        state[prefix].customSections.splice(idx, 1);
        render();
      });
    });

    const addBtn = document.getElementById(`add-${prefix}-custom-btn`);
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        state[prefix].customSections.push({ title: '', content: '' });
        render();
      });
    }
  }

  function getReorderTargetArray(group) {
    if (group === 'people') return state.user.people;
    if (group === 'projects') return state.user.projects;
    if (group === 'user-custom') return state.user.customSections;
    if (group === 'agent-custom') return state.agent.customSections;
    return null;
  }

  function moveArrayItem(arr, from, to) {
    if (!arr || from === to || from < 0 || to < 0) return;
    if (from >= arr.length || to > arr.length) return;
    const [item] = arr.splice(from, 1);
    if (item === undefined) return;
    arr.splice(to, 0, item);
  }

  function bindReorderEvents(container) {
    const dragState = { group: null, fromIndex: -1 };

    function clearDragClasses() {
      container.querySelectorAll('.reorder-item.dragging, .reorder-item.drag-over').forEach(el => {
        el.classList.remove('dragging', 'drag-over');
      });
    }

    container.querySelectorAll('.reorder-item[data-reorder-group]').forEach(item => {
      item.addEventListener('dragstart', (e) => {
        if (!e.target.closest('.drag-handle')) {
          e.preventDefault();
          return;
        }

        dragState.group = item.dataset.reorderGroup;
        dragState.fromIndex = parseInt(item.dataset.reorderIndex, 10);
        item.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', `${dragState.group}:${dragState.fromIndex}`);
      });

      item.addEventListener('dragover', (e) => {
        const targetGroup = item.dataset.reorderGroup;
        if (!dragState.group || dragState.group !== targetGroup) return;
        e.preventDefault();
        item.classList.add('drag-over');
        e.dataTransfer.dropEffect = 'move';
      });

      item.addEventListener('dragleave', () => {
        item.classList.remove('drag-over');
      });

      item.addEventListener('drop', (e) => {
        const targetGroup = item.dataset.reorderGroup;
        if (!dragState.group || dragState.group !== targetGroup) return;
        e.preventDefault();
        item.classList.remove('drag-over');

        const toIndexRaw = parseInt(item.dataset.reorderIndex, 10);
        const rect = item.getBoundingClientRect();
        const dropAfter = e.clientY > rect.top + (rect.height / 2);
        let toIndex = dropAfter ? toIndexRaw + 1 : toIndexRaw;
        if (dragState.fromIndex < toIndex) toIndex -= 1;

        const arr = getReorderTargetArray(targetGroup);
        if (!arr) return;
        moveArrayItem(arr, dragState.fromIndex, toIndex);
        dragState.group = null;
        dragState.fromIndex = -1;
        render();
      });

      item.addEventListener('dragend', () => {
        dragState.group = null;
        dragState.fromIndex = -1;
        clearDragClasses();
      });
    });

    container.querySelectorAll('[data-reorder-list]').forEach(list => {
      list.addEventListener('dragover', (e) => {
        const listGroup = list.dataset.reorderList;
        if (!dragState.group || dragState.group !== listGroup) return;
        if (e.target.closest('.reorder-item')) return;
        e.preventDefault();
      });

      list.addEventListener('drop', (e) => {
        const listGroup = list.dataset.reorderList;
        if (!dragState.group || dragState.group !== listGroup) return;
        if (e.target.closest('.reorder-item')) return;
        e.preventDefault();
        const arr = getReorderTargetArray(listGroup);
        if (!arr) return;
        moveArrayItem(arr, dragState.fromIndex, arr.length - 1);
        dragState.group = null;
        dragState.fromIndex = -1;
        render();
      });
    });
  }

  // ---- Inline Add (for toggle groups) ----
  function showInlineAdd(targetEl, onConfirm) {
    // Check if form already showing
    const existing = targetEl.parentNode.querySelector('.inline-add-form');
    if (existing) {
      existing.querySelector('input').focus();
      return;
    }

    const form = document.createElement('div');
    form.className = 'inline-add-form';
    form.innerHTML = `
      <input type="text" placeholder="Type a name..." autofocus>
      <button class="inline-add-confirm" title="Add">&#10003;</button>
      <button class="inline-add-cancel" title="Cancel">&#10005;</button>
    `;

    targetEl.parentNode.insertBefore(form, targetEl);

    const input = form.querySelector('input');
    input.focus();

    function confirm() {
      const val = input.value.trim();
      if (val) {
        onConfirm(val);
      } else {
        cancel();
      }
    }

    function cancel() {
      form.remove();
    }

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); confirm(); }
      if (e.key === 'Escape') { cancel(); }
    });

    form.querySelector('.inline-add-confirm').addEventListener('click', confirm);
    form.querySelector('.inline-add-cancel').addEventListener('click', cancel);
  }

  // ---- Import Modal ----
  function showImportModal() {
    const modalContainer = document.getElementById('modal-container');
    const fileType = state.activeFile;
    modalContainer.innerHTML = `
      <div class="modal-overlay" id="import-overlay">
        <div class="modal">
          <div class="modal-header">
            <h3>Import ${fileType}.md</h3>
            <button class="btn btn-icon btn-ghost" id="import-close-btn" title="Close">&#10005;</button>
          </div>
          <div class="modal-body">
            <div class="import-tabs">
              <button class="import-tab active" data-import-tab="paste">Paste Markdown</button>
              <button class="import-tab" data-import-tab="upload">Upload File</button>
            </div>
            <div id="import-tab-paste">
              <textarea id="import-paste-area" placeholder="Paste your existing ${fileType}.md content here..." rows="12"></textarea>
            </div>
            <div id="import-tab-upload" style="display:none;">
              <div class="file-drop-zone" id="file-drop-zone">
                <div class="file-drop-zone-icon">&#128196;</div>
                <p>Drop a .md file here, or click to browse</p>
                <input type="file" id="import-file-input" accept=".md,.txt,.markdown">
              </div>
            </div>
            <div class="import-preview" id="import-preview">
              <div class="import-preview-empty">Paste or upload markdown to preview what will change.</div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn" id="import-cancel-btn">Cancel</button>
            <button class="btn btn-primary" id="import-confirm-btn">Import</button>
          </div>
        </div>
      </div>
    `;

    let activeTab = 'paste';
    const pasteArea = document.getElementById('import-paste-area');
    const preview = document.getElementById('import-preview');

    function renderPreviewList(titles, emptyText) {
      if (!titles.length) {
        return `<p class="import-preview-empty-list">${emptyText}</p>`;
      }
      const shown = titles.slice(0, 5);
      const remaining = titles.length - shown.length;
      return `
        <ul class="import-preview-list">
          ${shown.map(title => `<li>${esc(title)}</li>`).join('')}
          ${remaining > 0 ? `<li>+${remaining} more</li>` : ''}
        </ul>
      `;
    }

    function updatePreview() {
      const md = pasteArea.value.trim();
      if (!md) {
        preview.innerHTML = '<div class="import-preview-empty">Paste or upload markdown to preview what will change.</div>';
        return;
      }

      const diff = buildImportDiff(md, fileType);
      preview.innerHTML = `
        <div class="import-preview-header">Import preview</div>
        <p class="import-preview-summary">
          This import will replace ${diff.replacedCount} section${diff.replacedCount === 1 ? '' : 's'}
          and add ${diff.newCustomCount} new custom section${diff.newCustomCount === 1 ? '' : 's'}.
        </p>
        <div class="import-preview-metrics">
          <div class="import-preview-metric">
            <span class="metric-value">${diff.replacedCount}</span>
            <span class="metric-label">Replaced</span>
          </div>
          <div class="import-preview-metric">
            <span class="metric-value">${diff.addedCount}</span>
            <span class="metric-label">Added</span>
          </div>
          <div class="import-preview-metric">
            <span class="metric-value">${diff.removedCount}</span>
            <span class="metric-label">Missing from import</span>
          </div>
        </div>
        <div class="import-preview-columns">
          <div class="import-preview-column">
            <h4>Added sections</h4>
            ${renderPreviewList(diff.addedTitles, 'No new sections.')}
          </div>
          <div class="import-preview-column">
            <h4>Missing from import</h4>
            ${renderPreviewList(diff.removedTitles, 'No current sections are missing.')}
          </div>
        </div>
      `;
    }

    // Tab switching
    modalContainer.querySelectorAll('.import-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        activeTab = tab.dataset.importTab;
        modalContainer.querySelectorAll('.import-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('import-tab-paste').style.display = activeTab === 'paste' ? '' : 'none';
        document.getElementById('import-tab-upload').style.display = activeTab === 'upload' ? '' : 'none';
      });
    });

    // File drop zone
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('import-file-input');

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) readImportFile(file);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) readImportFile(fileInput.files[0]);
    });

    function readImportFile(file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        pasteArea.value = e.target.result;
        // Switch to paste tab to show content
        modalContainer.querySelectorAll('.import-tab').forEach(t => t.classList.remove('active'));
        modalContainer.querySelector('[data-import-tab="paste"]').classList.add('active');
        document.getElementById('import-tab-paste').style.display = '';
        document.getElementById('import-tab-upload').style.display = 'none';
        updatePreview();
        showToast('File loaded. Review and click Import.', '');
      };
      reader.readAsText(file);
    }

    pasteArea.addEventListener('input', updatePreview);
    updatePreview();

    // Close
    const closeModal = () => { modalContainer.innerHTML = ''; };
    document.getElementById('import-close-btn').addEventListener('click', closeModal);
    document.getElementById('import-cancel-btn').addEventListener('click', closeModal);
    document.getElementById('import-overlay').addEventListener('click', (e) => {
      if (e.target.id === 'import-overlay') closeModal();
    });

    // Confirm import
    document.getElementById('import-confirm-btn').addEventListener('click', () => {
      const md = pasteArea.value.trim();
      if (!md) {
        showToast('Nothing to import. Paste or upload a markdown file first.', '');
        return;
      }
      if (state.activeFile === 'user') {
        parseUserMarkdown(md);
      } else {
        parseAgentMarkdown(md);
      }
      closeModal();
      render();
      showToast(`Imported ${fileType}.md successfully`, 'success');
    });
  }

  // ---- Markdown Editor View ----
  function renderMarkdownEditor(container) {
    const md = state.activeFile === 'user' ? generateUserMarkdown() : generateAgentMarkdown();

    container.innerHTML = `
      <div class="markdown-editor-container">
        <div class="editor-toolbar">
          ${state.markdownSubMode === 'rich' ? `
            <button class="toolbar-btn" title="Bold" data-format="bold"><strong>B</strong></button>
            <button class="toolbar-btn" title="Italic" data-format="italic"><em>I</em></button>
            <div class="divider"></div>
            <button class="toolbar-btn" title="Heading 1" data-format="h1">H1</button>
            <button class="toolbar-btn" title="Heading 2" data-format="h2">H2</button>
            <button class="toolbar-btn" title="Heading 3" data-format="h3">H3</button>
            <div class="divider"></div>
            <button class="toolbar-btn" title="Bullet list" data-format="ul">&bull;</button>
            <button class="toolbar-btn" title="Horizontal rule" data-format="hr">&mdash;</button>
          ` : `
            <button class="toolbar-btn" title="Bold" data-md-insert="bold"><strong>B</strong></button>
            <button class="toolbar-btn" title="Italic" data-md-insert="italic"><em>I</em></button>
            <div class="divider"></div>
            <button class="toolbar-btn" title="Heading 2" data-md-insert="h2">H2</button>
            <button class="toolbar-btn" title="Heading 3" data-md-insert="h3">H3</button>
            <div class="divider"></div>
            <button class="toolbar-btn" title="List item" data-md-insert="li">&bull;</button>
          `}
          <div class="raw-mode-toggle">
            <button class="raw-mode-btn ${state.markdownSubMode === 'rich' ? 'active' : ''}" data-submode="rich">Rich Text</button>
            <button class="raw-mode-btn ${state.markdownSubMode === 'plain' ? 'active' : ''}" data-submode="plain">Plain Text</button>
          </div>
        </div>
        ${state.markdownSubMode === 'plain' ? `
          <textarea class="raw-editor" id="raw-markdown-editor" spellcheck="false">${esc(md)}</textarea>
        ` : `
          <div class="rich-editor" id="rich-markdown-editor" contenteditable="true">${markdownToHtml(md)}</div>
        `}
      </div>
    `;

    // Sub-mode toggle
    container.querySelectorAll('[data-submode]').forEach(btn => {
      btn.addEventListener('click', () => {
        syncMarkdownToState();
        state.markdownSubMode = btn.dataset.submode;
        render();
      });
    });

    // Plain text editor events
    const rawEditor = document.getElementById('raw-markdown-editor');
    if (rawEditor) {
      rawEditor.addEventListener('input', debounce(() => {
        const md = rawEditor.value;
        if (state.activeFile === 'user') {
          parseUserMarkdown(md);
        } else {
          parseAgentMarkdown(md);
        }
        renderPreview();
        debouncedSave();
      }, 300));

      container.querySelectorAll('[data-md-insert]').forEach(btn => {
        btn.addEventListener('click', () => {
          const format = btn.dataset.mdInsert;
          insertMarkdownFormat(rawEditor, format);
        });
      });
    }

    // Rich text editor events
    const richEditor = document.getElementById('rich-markdown-editor');
    if (richEditor) {
      richEditor.addEventListener('input', debounce(() => {
        const md = htmlToMarkdown(richEditor.innerHTML);
        if (state.activeFile === 'user') {
          parseUserMarkdown(md);
        } else {
          parseAgentMarkdown(md);
        }
        renderPreview();
        debouncedSave();
      }, 300));

      container.querySelectorAll('[data-format]').forEach(btn => {
        btn.addEventListener('click', () => {
          const fmt = btn.dataset.format;
          applyRichFormat(fmt);
        });
      });
    }
  }

  function syncMarkdownToState() {
    const rawEditor = document.getElementById('raw-markdown-editor');
    const richEditor = document.getElementById('rich-markdown-editor');
    let md;
    if (rawEditor) {
      md = rawEditor.value;
    } else if (richEditor) {
      md = htmlToMarkdown(richEditor.innerHTML);
    } else {
      return;
    }
    if (state.activeFile === 'user') {
      parseUserMarkdown(md);
    } else {
      parseAgentMarkdown(md);
    }
  }

  function insertMarkdownFormat(textarea, format) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.substring(start, end);
    let insert = '';

    switch (format) {
      case 'bold': insert = `**${selected || 'bold text'}**`; break;
      case 'italic': insert = `*${selected || 'italic text'}*`; break;
      case 'h2': insert = `\n## ${selected || 'Heading'}\n`; break;
      case 'h3': insert = `\n### ${selected || 'Heading'}\n`; break;
      case 'li': insert = `\n- ${selected || 'List item'}`; break;
    }

    textarea.value = textarea.value.substring(0, start) + insert + textarea.value.substring(end);
    textarea.focus();
    const newPos = start + insert.length;
    textarea.setSelectionRange(newPos, newPos);
    textarea.dispatchEvent(new Event('input'));
  }

  function applyRichFormat(format) {
    switch (format) {
      case 'bold': document.execCommand('bold'); break;
      case 'italic': document.execCommand('italic'); break;
      case 'h1': document.execCommand('formatBlock', false, 'h1'); break;
      case 'h2': document.execCommand('formatBlock', false, 'h2'); break;
      case 'h3': document.execCommand('formatBlock', false, 'h3'); break;
      case 'ul': document.execCommand('insertUnorderedList'); break;
      case 'hr': document.execCommand('insertHorizontalRule'); break;
    }
  }

  // ---- Markdown <-> HTML conversion ----
  function markdownToHtml(md) {
    const lines = md.split('\n');
    const htmlLines = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      line = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

      const h3 = line.match(/^###\s+(.+)/);
      const h2 = line.match(/^##\s+(.+)/);
      const h1 = line.match(/^#\s+(.+)/);
      const hr = line.match(/^---$/);
      const bq = line.match(/^&gt;\s+(.+)/);
      const li = line.match(/^-\s+(.+)/);

      if (li) {
        if (!inList) { htmlLines.push('<ul>'); inList = true; }
        htmlLines.push(`<li>${inlineFmt(li[1])}</li>`);
        continue;
      } else if (inList) {
        htmlLines.push('</ul>');
        inList = false;
      }

      if (h3) { htmlLines.push(`<h3>${inlineFmt(h3[1])}</h3>`); }
      else if (h2) { htmlLines.push(`<h2>${inlineFmt(h2[1])}</h2>`); }
      else if (h1) { htmlLines.push(`<h1>${inlineFmt(h1[1])}</h1>`); }
      else if (hr) { htmlLines.push('<hr>'); }
      else if (bq) { htmlLines.push(`<blockquote>${inlineFmt(bq[1])}</blockquote>`); }
      else if (line.trim() === '') { htmlLines.push(''); }
      else { htmlLines.push(`<p>${inlineFmt(line)}</p>`); }
    }
    if (inList) htmlLines.push('</ul>');

    let html = htmlLines.join('\n');
    html = html.replace(/<\/ul>\n*<ul>/g, '');
    return html;
  }

  function inlineFmt(text) {
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    return text;
  }

  function htmlToMarkdown(html) {
    let md = html;
    md = md.replace(/<h1[^>]*>(.*?)<\/h1>/gi, '\n# $1\n');
    md = md.replace(/<h2[^>]*>(.*?)<\/h2>/gi, '\n## $1\n');
    md = md.replace(/<h3[^>]*>(.*?)<\/h3>/gi, '\n### $1\n');
    md = md.replace(/<hr\s*\/?>/gi, '\n---\n');
    md = md.replace(/<strong>(.*?)<\/strong>/gi, '**$1**');
    md = md.replace(/<b>(.*?)<\/b>/gi, '**$1**');
    md = md.replace(/<em>(.*?)<\/em>/gi, '*$1*');
    md = md.replace(/<i>(.*?)<\/i>/gi, '*$1*');
    md = md.replace(/<code>(.*?)<\/code>/gi, '`$1`');
    md = md.replace(/<blockquote[^>]*>(.*?)<\/blockquote>/gi, '> $1');
    md = md.replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1');
    md = md.replace(/<\/?ul[^>]*>/gi, '');
    md = md.replace(/<\/?ol[^>]*>/gi, '');
    md = md.replace(/<br\s*\/?>/gi, '\n');
    md = md.replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n');
    md = md.replace(/<div[^>]*>(.*?)<\/div>/gi, '$1\n');
    md = md.replace(/<[^>]+>/g, '');
    md = md.replace(/&amp;/g, '&');
    md = md.replace(/&lt;/g, '<');
    md = md.replace(/&gt;/g, '>');
    md = md.replace(/&nbsp;/g, ' ');
    md = md.replace(/&quot;/g, '"');
    md = md.replace(/\n{3,}/g, '\n\n');
    md = md.trim() + '\n';
    return md;
  }

  const debouncedSave = debounce(() => {
    setSaveState('saving');
    saveToLocalStorage();
  }, 500);

  // ---- localStorage ----
  function saveToLocalStorage() {
    try {
      localStorage.setItem('seedConfigurator', JSON.stringify(state));
      setSaveState('saved');
    } catch (e) {
      setSaveState('error');
      showToast('Failed to save locally: storage quota exceeded', 'error');
    }
  }

  function loadFromLocalStorage() {
    try {
      const saved = localStorage.getItem('seedConfigurator');
      if (saved) {
        const parsed = JSON.parse(saved);
        deepMerge(state, parsed);
        return true;
      }
    } catch (e) {
      // Silently fail
    }
    return false;
  }

  function deepMerge(target, source) {
    for (const key of Object.keys(source)) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key]) && target[key] && typeof target[key] === 'object') {
        deepMerge(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
  }

  function bindStorageSync() {
    window.addEventListener('storage', (e) => {
      if (e.key !== 'seedConfigurator' || !e.newValue) return;

      try {
        const parsed = JSON.parse(e.newValue);
        deepMerge(state, parsed);
        migrateState();
        resetConfigHistory();
        render();
        showToast('Synced changes from another tab', '');
      } catch (err) {
        console.warn('Failed to sync storage event:', err);
      }
    });
  }

  // ---- Migrate old state format ----
  // If someone loads with old format (cognitive as flat booleans, communication as flat booleans, etc.),
  // we migrate to the new arrays+active format.
  function migrateState() {
    const u = state.user;
    const a = state.agent;

    // Migrate old cognitive: { adhd: true, ... } -> cognitiveActive
    if (u.cognitive && typeof u.cognitive === 'object' && !u.cognitiveOptions) {
      // Old format
      u.cognitiveOptions = DEFAULT_COGNITIVE_OPTIONS.map(o => o.key);
      u.cognitiveLabels = {};
      u.cognitiveActive = {};
      Object.entries(u.cognitive).forEach(([k, v]) => {
        if (v) u.cognitiveActive[k] = true;
        if (!u.cognitiveOptions.includes(k)) u.cognitiveOptions.push(k);
      });
      delete u.cognitive;
    }

    // Migrate old communication
    if (u.communication && typeof u.communication === 'object' && !u.communicationOptions) {
      u.communicationOptions = DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key);
      u.communicationLabels = {};
      u.communicationDescs = {};
      u.communicationActive = {};
      Object.entries(u.communication).forEach(([k, v]) => {
        if (v) u.communicationActive[k] = true;
        if (!u.communicationOptions.includes(k)) u.communicationOptions.push(k);
      });
      delete u.communication;
    }

    // Migrate old agent behaviors
    if (a.behaviors && typeof a.behaviors === 'object' && !a.behaviorOptions) {
      a.behaviorOptions = DEFAULT_BEHAVIOR_OPTIONS.map(o => o.key);
      a.behaviorLabels = {};
      a.behaviorsActive = {};
      Object.entries(a.behaviors).forEach(([k, v]) => {
        if (v) a.behaviorsActive[k] = true;
        if (!a.behaviorOptions.includes(k)) a.behaviorOptions.push(k);
      });
      delete a.behaviors;
    }

    // Migrate old whenLow
    if (a.whenLow && typeof a.whenLow === 'object' && !a.whenLowOptions) {
      a.whenLowOptions = DEFAULT_WHEN_LOW_OPTIONS.map(o => o.key);
      a.whenLowLabels = {};
      a.whenLowDescs = {};
      a.whenLowActive = {};
      Object.entries(a.whenLow).forEach(([k, v]) => {
        if (v) a.whenLowActive[k] = true;
        if (!a.whenLowOptions.includes(k)) a.whenLowOptions.push(k);
      });
      delete a.whenLow;
    }

    // Migrate old technicalStyle
    if (a.technicalStyle && typeof a.technicalStyle === 'object' && !a.techStyleOptions) {
      a.techStyleOptions = DEFAULT_TECH_STYLE_OPTIONS.map(o => o.key);
      a.techStyleLabels = {};
      a.techStyleDescs = {};
      a.techStyleActive = {};
      Object.entries(a.technicalStyle).forEach(([k, v]) => {
        if (v) a.techStyleActive[k] = true;
        if (!a.techStyleOptions.includes(k)) a.techStyleOptions.push(k);
      });
      delete a.technicalStyle;
    }

    // Migrate old traits (flat object) -> new format with traitOptions
    if (a.traits && !a.traitOptions) {
      a.traitOptions = DEFAULT_TRAIT_OPTIONS.map(o => o.key);
      a.traitLabels = {};
      a.traitEndpoints = {};
      // Keep traits values as they are, just ensure custom ones are tracked
      Object.keys(a.traits).forEach(k => {
        if (!a.traitOptions.includes(k)) a.traitOptions.push(k);
      });
    }

    // Ensure enabledSections exists
    if (!state.enabledSections) {
      state.enabledSections = {};
    }
    if (!state.collapsedSections || typeof state.collapsedSections !== 'object') {
      state.collapsedSections = {};
    }
    const allSections = ['identity', 'about', 'cognitive', 'values', 'communication', 'people', 'projects', 'user-custom', 'agent-name', 'traits', 'behaviors', 'avoid', 'when-low', 'tech-style', 'agent-custom'];
    allSections.forEach(id => {
      if (state.enabledSections[id] === undefined) state.enabledSections[id] = true;
    });

    // Ensure preset exists
    if (!state.preset) state.preset = 'custom';

    // Ensure files array exists
    if (!Array.isArray(state.files)) state.files = [];
    // Ensure each file has anchorDepth
    state.files.forEach(f => {
      if (!f.anchorDepth) f.anchorDepth = 'full';
      if (!f.projectTag) f.projectTag = '';
      if (!f.id) f.id = generateFileId();
    });

    // Ensure new state properties
    if (!state.activePage) state.activePage = 'dashboard';
    if (!Array.isArray(state.notesCache)) state.notesCache = [];
    if (state.settingsCache === undefined) state.settingsCache = null;
    if (state.statusCache === undefined) state.statusCache = null;
    if (state.serverConnected === undefined) state.serverConnected = false;
    if (state.onboardingStep === undefined) state.onboardingStep = 1;
    if (!state.seedSync || typeof state.seedSync !== 'object') {
      state.seedSync = {
        deploymentKnown: false,
        deployedHash: '',
        deployedAt: '',
      };
    } else {
      if (state.seedSync.deploymentKnown === undefined) state.seedSync.deploymentKnown = false;
      if (typeof state.seedSync.deployedHash !== 'string') state.seedSync.deployedHash = '';
      if (typeof state.seedSync.deployedAt !== 'string') state.seedSync.deployedAt = '';
    }
  }

  // ---- Public API ----
  window.memorableApp = {
    toggleSection(id) {
      const el = document.getElementById(id);
      if (el && !el.classList.contains('section-disabled')) {
        el.classList.toggle('collapsed');
        const sectionId = id.startsWith('section-') ? id.slice('section-'.length) : id;
        state.collapsedSections[sectionId] = el.classList.contains('collapsed');
        debouncedSave();
      }
    },

    addAvoid() {
      const input = document.getElementById('avoid-input');
      if (input && input.value.trim()) {
        state.agent.avoid.push(input.value.trim());
        input.value = '';
        const container = document.getElementById('page-container');
        renderSeedsPage(container);
      }
    },

    showImportModal() {
      showImportModal();
    },

    retrySave() {
      setSaveState('saving');
      saveToLocalStorage();
    },

    onboardingSetField(path, value) {
      const parts = String(path || '').split('.');
      let ref = state;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!ref[parts[i]]) return;
        ref = ref[parts[i]];
      }
      const key = parts[parts.length - 1];
      ref[key] = value;
      render();
    },

    onboardingSetValue(index, field, value) {
      const i = parseInt(index, 10);
      if (!Array.isArray(state.user.values) || !state.user.values[i]) return;
      state.user.values[i][field] = value;
      render();
    },

    onboardingAddValue() {
      if (!Array.isArray(state.user.values)) state.user.values = [];
      state.user.values.push({ higher: '', lower: '' });
      render();
    },

    onboardingRemoveValue(index) {
      const i = parseInt(index, 10);
      if (!Array.isArray(state.user.values) || state.user.values.length <= 1) return;
      state.user.values.splice(i, 1);
      render();
    },

    onboardingSetTrait(key, value) {
      const n = parseInt(value, 10);
      if (!state.agent.traits || !Number.isFinite(n)) return;
      state.agent.traits[key] = Math.max(0, Math.min(100, n));
      render();
    },

    onboardingNext() {
      state.onboardingStep = clampOnboardingStep((state.onboardingStep || 1) + 1);
      render();
    },

    onboardingPrev() {
      state.onboardingStep = clampOnboardingStep((state.onboardingStep || 1) - 1);
      render();
    },

    onboardingSkip() {
      const step = clampOnboardingStep(state.onboardingStep || 1);
      if (step >= 5) {
        state.activePage = 'configure';
        syncNavHighlight();
      } else {
        state.onboardingStep = step + 1;
      }
      render();
    },

    async onboardingComplete() {
      const files = {
        'user.md': generateUserMarkdown(),
        'agent.md': generateAgentMarkdown(),
        'now.md': '# Current Context\n\n## Focus\n\n## Active Tasks\n\n## Blockers\n'
      };
      const result = await apiFetch('/api/seeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files })
      });

      if (result && result.ok) {
        state.onboardingStep = 1;
        state.seedSync.deploymentKnown = true;
        state.seedSync.deployedHash = _seedFingerprint(files['user.md'], files['agent.md']);
        state.seedSync.deployedAt = new Date().toISOString();
        if (state.statusCache) state.statusCache.seeds_present = true;
        showToast('Onboarding complete. Seed files created.', 'success');
      } else {
        showToast('Saved locally; seed deployment failed (server offline?)', '');
      }

      state.activePage = 'configure';
      syncNavHighlight();
      render();
    },

    async enableDaemon() {
      const existing = state.settingsCache || {};
      const existingDaemon = existing.daemon || {};
      const daemon = {
        ...existingDaemon,
        enabled: true,
        idle_threshold: Number(existingDaemon.idle_threshold || 300),
      };

      const result = await apiFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daemon }),
      });

      if (result && result.ok) {
        if (result.settings) {
          state.settingsCache = result.settings;
        } else {
          state.settingsCache = { ...existing, daemon };
        }
        await checkServerStatus();
        showToast('Daemon enabled. Start a session to generate your first note.', 'success');
        render();
      } else {
        showToast('Could not enable daemon from Dashboard', 'error');
      }
    },

    undo() {
      return undoConfigChange();
    },

    redo() {
      return redoConfigChange();
    },

    copyToClipboard(file) {
      const md = file === 'user' ? generateUserMarkdown() : generateAgentMarkdown();
      navigator.clipboard.writeText(md).then(() => {
        showToast(`${file}.md copied to clipboard`, 'success');
      }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = md;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast(`${file}.md copied to clipboard`, 'success');
      });
    },

    download(file) {
      const md = file === 'user' ? generateUserMarkdown() : generateAgentMarkdown();
      const blob = new Blob([md], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${file}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(`${file}.md downloaded`, 'success');
    },

    removeFile(fileId) {
      if (confirm('Remove this file?')) {
        state.files = state.files.filter(f => f.id !== fileId);
        if (state.activeFileId === fileId) {
          state.activeFileId = state.files.length > 0 ? state.files[0].id : null;
        }
        render();
        showToast('File removed', '');
      }
    },

    copyFileContent(fileId) {
      const file = state.files.find(f => f.id === fileId);
      if (!file) return;
      navigator.clipboard.writeText(file.content || '').then(() => {
        showToast(`${file.name} copied to clipboard`, 'success');
      }).catch(() => {
        showToast('Failed to copy', '');
      });
    },

    navigateTo(page) {
      state.activePage = page;
      syncNavHighlight();
      render();
    },

    setMemoriesSubTab(tab) {
      state.memoriesSubTab = tab;
      render();
    },

    resetAll() {
      if (confirm('Reset all data? This cannot be undone.')) {
        localStorage.removeItem('seedConfigurator');
        location.reload();
      }
    }
  };

  // Keep backward compat
  window.seedApp = window.memorableApp;

  // ---- Init ----
  async function init() {
    const hadLocalDraft = loadFromLocalStorage();
    migrateState();
    resetConfigHistory();
    bindStorageSync();
    bindSidebarNav();
    render();

    // Load data from server (non-blocking)
    checkServerStatus();
    loadNotes().then(() => {
      // Re-render if we're on a page that uses notes
      if (state.activePage === 'dashboard' || state.activePage === 'memories') {
        renderPage();
      }
    });
    loadSettings();
    loadDeployedSeeds(hadLocalDraft).then(() => {
      // Re-render pages that expose seed deployment status/content.
      if (state.activePage === 'configure' || state.activePage === 'dashboard') {
        render();
      }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      const mod = e.metaKey || e.ctrlKey;

      // Ctrl/Cmd+S: force save
      if (mod && e.key === 's') {
        e.preventDefault();
        setSaveState('saving');
        saveToLocalStorage();
        return;
      }

      // Configure page history shortcuts (outside text inputs)
      if (state.activePage === 'configure' && mod && !isEditableTarget(e.target)) {
        const key = e.key.toLowerCase();
        if (key === 'z' && !e.shiftKey) {
          e.preventDefault();
          if (!undoConfigChange()) showToast('Nothing to undo', '');
          return;
        }
        if (key === 'y' || (key === 'z' && e.shiftKey)) {
          e.preventDefault();
          if (!redoConfigChange()) showToast('Nothing to redo', '');
          return;
        }
      }

      // Escape: close modal if open
      if (e.key === 'Escape') {
        const modalContainer = document.getElementById('modal-container');
        if (modalContainer && modalContainer.innerHTML.trim()) {
          modalContainer.innerHTML = '';
        }
      }
    });

    // Periodic status check
    setInterval(checkServerStatus, 30000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
