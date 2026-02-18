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
    { key: 'dyslexia', label: 'Dyslexia' },
    { key: 'dyscalculia', label: 'Dyscalculia' },
    { key: 'dyspraxia', label: 'Dyspraxia' }
  ];

  const DEFAULT_COGNITIVE_STYLE_DIMS = [
    { key: 'thinking', label: 'Guidance Style', left: 'Give me structured outlines', right: 'Let ideas wander' },
    { key: 'abstraction', label: 'Starting Point', left: 'Start with specifics', right: 'Start with the big picture' },
    { key: 'focus', label: 'Zoom Level', left: 'Detail-first', right: 'Big picture first' },
    { key: 'processing', label: 'Threading', left: 'Explain step by step', right: 'I can juggle multiple threads' }
  ];

  const DEFAULT_COMMUNICATION_OPTIONS = [
    { key: 'beDirect', label: 'Be direct', desc: 'Don\'t soften or hedge unnecessarily' },
    { key: 'noSycophancy', label: 'No sycophancy', desc: 'Skip the "great question!" and "absolutely!"' },
    { key: 'skipPreamble', label: 'Skip preamble', desc: 'Get to the point, skip disclaimers' },
    { key: 'noEmojis', label: 'No emojis', desc: 'Keep responses text-only' }
  ];

  const DEFAULT_BEHAVIOR_OPTIONS = [
    { key: 'holdOwnViews', label: 'Hold your own views' },
    { key: 'challengeWhenWrong', label: 'Challenge me when I\'m wrong' },
    { key: 'admitUncertainty', label: 'Admit uncertainty clearly' },
    { key: 'askClarifyingQuestions', label: 'Ask clarifying questions when ambiguity blocks progress' },
    { key: 'calibrateTone', label: 'Calibrate emotional tone to context' }
  ];

  const DEFAULT_WHEN_LOW_OPTIONS = [
    { key: 'shorterReplies', label: 'Keep replies shorter', desc: 'Reduce output length' },
    { key: 'dontProbe', label: 'Don\'t probe — let me lead', desc: 'Avoid digging unless invited' },
    { key: 'silenceProcessing', label: 'Silence often means processing', desc: 'Don\'t assume disengagement' },
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
    { key: 'verbosity', label: 'Verbosity', endpoints: ['Terse', 'Detailed'] },
    { key: 'curiosity', label: 'Curiosity', endpoints: ['Focused', 'Highly curious'] },
    { key: 'independence', label: 'Independence', endpoints: ['Deferential', 'Independent'] }
  ];

  // ---- Presets ----
  const PRESETS = {
    technical: {
      label: 'Technical / Coding',
      userSections: ['identity', 'about', 'cognitive', 'cogStyle', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'agent-about', 'communication', 'behaviors', 'when-low', 'autonomy', 'rules', 'traits', 'avoid', 'tech-style', 'agent-custom']
    },
    research: {
      label: 'Research / Academic',
      userSections: ['identity', 'about', 'cognitive', 'cogStyle', 'values', 'interests', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'agent-about', 'communication', 'behaviors', 'when-low', 'autonomy', 'rules', 'traits', 'avoid', 'agent-custom']
    },
    personal: {
      label: 'Personal / Companion',
      userSections: ['identity', 'about', 'cognitive', 'cogStyle', 'values', 'interests', 'people', 'user-custom'],
      agentSections: ['agent-name', 'agent-about', 'communication', 'behaviors', 'when-low', 'autonomy', 'rules', 'traits', 'avoid', 'agent-custom']
    },
    custom: {
      label: 'Custom',
      userSections: ['identity', 'about', 'cognitive', 'cogStyle', 'values', 'interests', 'people', 'projects', 'user-custom'],
      agentSections: ['agent-name', 'agent-about', 'communication', 'behaviors', 'when-low', 'autonomy', 'rules', 'traits', 'avoid', 'tech-style', 'agent-custom']
    }
  };

  const USER_SECTION_IDS = [
    'identity', 'about', 'cognitive', 'cogStyle', 'values', 'interests', 'people', 'projects', 'user-custom'
  ];
  const AGENT_SECTION_IDS = [
    'agent-name', 'agent-about', 'communication', 'behaviors', 'when-low', 'autonomy', 'rules', 'traits', 'avoid', 'tech-style', 'agent-custom'
  ];
  const DEFAULT_COLLAPSED_SECTIONS = {};

  // ---- Icons (inline SVG, feather style) ----
  const _i = (d) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const ICON = {
    star:     _i('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'),
    edit:     _i('<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>'),
    sparkle:  _i('<path d="M12 2L9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z"/>'),
    settings: _i('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>'),
    scale:    _i('<path d="M16 3l5 5-5 5"/><path d="M21 8H9"/><path d="M8 21l-5-5 5-5"/><path d="M3 16h12"/>'),
    heart:    _i('<path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>'),
    users:    _i('<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>'),
    folder:   _i('<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>'),
    code:     _i('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>'),
    chat:     _i('<path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>'),
    sliders:  _i('<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>'),
    check:    _i('<polyline points="20 6 9 17 4 12"/>'),
    x:        _i('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'),
    plus:     _i('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'),
    ban:      _i('<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>'),
    circle:   _i('<circle cx="12" cy="12" r="10"/>'),
    penTool:  _i('<path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/>'),
    fileText: _i('<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>'),
    file:     _i('<path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/>'),
    search:   _i('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'),
    alert:    _i('<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
    moon:     _i('<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>'),
    sun:      _i('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'),
    book:     _i('<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>'),
    user:     _i('<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
    link:     _i('<path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>'),
    plug:     _i('<path d="M12 2v6"/><path d="M6 8h12"/><path d="M8 8v4a4 4 0 008 0V8"/><path d="M12 16v6"/>'),
    compass:  _i('<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>'),
    chevDown: _i('<polyline points="6 9 12 15 18 9"/>'),
    grip:     _i('<circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>'),
    upload:   _i('<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>'),
    clipboard:_i('<path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'),
  };

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
      case 'cogStyle': {
        const count = Object.keys(u.cognitiveStyle).filter(k => u.cognitiveStyle[k] && u.cognitiveStyle[k] !== 'balanced').length;
        return count === 0 ? 'sketch' : count <= 2 ? 'forming' : 'substantial';
      }
      case 'interests':
        return u.interests.length === 0 ? 'sketch' : u.interests.length <= 2 ? 'forming' : 'substantial';
      case 'communication': {
        const count = Object.values(a.communicationActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 3 ? 'forming' : 'substantial';
      }
      case 'people':
        return u.people.length === 0 ? 'sketch' : u.people.length <= 2 ? 'forming' : 'substantial';
      case 'projects':
        return u.projects.length === 0 ? 'sketch' : u.projects.length === 1 ? 'forming' : 'substantial';
      case 'user-custom':
        return u.customSections.length === 0 ? 'sketch' : u.customSections.length === 1 ? 'forming' : 'substantial';
      case 'agent-name': {
        const filled = ['name', 'model', 'role'].filter(k => a[k] && a[k].trim()).length;
        return filled === 0 ? 'sketch' : filled <= 1 ? 'forming' : 'substantial';
      }
      case 'agent-about':
        return !a.about || !a.about.trim() ? 'sketch' : a.about.trim().length < 100 ? 'forming' : 'substantial';
      case 'traits': {
        const changed = a.traitOptions.filter(k => (a.traits[k] ?? 50) !== 50).length;
        return changed === 0 ? 'sketch' : changed <= 2 ? 'forming' : 'substantial';
      }
      case 'behaviors': {
        const count = Object.values(a.behaviorsActive).filter(Boolean).length;
        return count === 0 ? 'sketch' : count <= 3 ? 'forming' : 'substantial';
      }
      case 'autonomy':
        return a.autonomyLevel === 50 ? 'sketch' : 'forming';
      case 'rules': {
        const count = Array.isArray(a.rules) ? a.rules.length : 0;
        return count === 0 ? 'sketch' : count <= 2 ? 'forming' : 'substantial';
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
    tokenBudgetExpanded: false,
    // Which sections are enabled (toggle on/off)
    enabledSections: {
      'identity': true, 'about': true, 'cognitive': true, 'cogStyle': true,
      'values': true, 'interests': true, 'people': true, 'projects': true, 'user-custom': true,
      'communication': true,
      'agent-name': true, 'traits': true, 'behaviors': true, 'avoid': true,
      'autonomy': true, 'rules': true,
      'when-low': true, 'tech-style': true, 'agent-custom': true
    },
    collapsedSections: { ...DEFAULT_COLLAPSED_SECTIONS },
    user: {
      identity: { name: '', age: '', location: '', pronouns: '', language: '', dialect: '', timezone: '' },
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
      cognitiveStyle: {},  // key -> 'left' | 'balanced' | 'right'
      cognitiveStyleDims: [],  // custom dims: [{key, label, left, right}]
      interests: [],       // [{name: '', context: ''}]
      people: [],
      projects: [],
      customSections: []
    },
    agent: {
      name: '',
      model: '',
      role: '',
      about: '',
      communicationOptions: DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key),
      communicationLabels: {},
      communicationDescs: {},
      communicationActive: {},
      traitOptions: DEFAULT_TRAIT_OPTIONS.map(o => o.key),
      traitLabels: {},
      traitEndpoints: {},
      traits: {
        warmth: 60, directness: 75, humor: 40, formality: 30, verbosity: 40, curiosity: 50, independence: 50
      },
      behaviorOptions: DEFAULT_BEHAVIOR_OPTIONS.map(o => o.key),
      behaviorLabels: {},
      behaviorsActive: {},
      autonomyLevel: 50,
      avoid: [],
      rules: [],
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
    memoriesSubTab: 'episodic', // memories sub-tab: episodic, working, semantic, deep
    notesCache: [],           // cached session notes from API
    settingsCache: null,      // cached settings from API
    statusCache: null,        // cached status from API
    metricsCache: null,       // cached local reliability metrics from API
    serverConnected: false,   // whether server is reachable
    seedSync: {
      deploymentKnown: false, // whether we have a deployed baseline to compare against
      deployedHash: "",       // hash-like fingerprint of deployed user+agent seeds
      deployedAt: "",         // local timestamp of most recent deploy action
    },
    semanticProcessing: {
      files: [],
    },
    deepSearch: {
      query: '',
      results: [],
      count: 0,
      ran: false,
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
    return state.agent.communicationLabels[key] || key;
  }

  function getCommDesc(key) {
    const def = DEFAULT_COMMUNICATION_OPTIONS.find(o => o.key === key);
    if (def) return def.desc;
    return state.agent.communicationDescs[key] || '';
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
    const isError = type === 'error';
    el.setAttribute('role', isError ? 'alert' : 'status');
    el.setAttribute('aria-live', isError ? 'assertive' : 'polite');
    el.setAttribute('aria-atomic', 'true');
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
      const isError = newState === 'error';
      el.setAttribute('role', isError ? 'alert' : 'status');
      el.setAttribute('aria-live', isError ? 'assertive' : 'polite');
      el.setAttribute('aria-atomic', 'true');

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

  function slugify(text) {
    return text.replace(/<[^>]*>/g, '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  }

  // Preview section heading → form section ID mapping
  const PREVIEW_TO_SECTION = {
    'about': 'about', 'neurodivergence': 'cognitive', 'neurotype': 'cognitive', 'cognitive-style': 'cogStyle',
    'values': 'values', 'interests': 'interests', 'people': 'people',
    'projects': 'projects', 'communication-preferences': 'communication', 'tone-format': 'communication',
    'tone-and-format': 'communication',
    'character-traits': 'traits', 'behaviors': 'behaviors', 'disposition': 'behaviors',
    'avoid': 'avoid', 'when-user-is-low': 'when-low', 'autonomy': 'autonomy', 'rules': 'rules',
    'conditional-rules': 'rules', 'technical-style': 'tech-style',
  };

  // ---- Markdown Generation ----
  function generateUserMarkdown() {
    const u = state.user;
    const sec = state.enabledSections;
    let md = '';

    // Identity
    if (sec['identity']) {
      const hasIdentity = u.identity.name || u.identity.age || u.identity.location || u.identity.pronouns || u.identity.language || u.identity.timezone;
      if (hasIdentity) {
        md += `# ${u.identity.name || 'User Profile'}\n\n`;
        const details = [];
        if (u.identity.age) details.push(`**Age:** ${u.identity.age}`);
        if (u.identity.location) details.push(`**Location:** ${u.identity.location}`);
        if (u.identity.pronouns) details.push(`**Pronouns:** ${u.identity.pronouns}`);
        if (u.identity.language) {
          let lang = u.identity.language;
          if (u.identity.dialect) lang += ` (${u.identity.dialect})`;
          details.push(`**Language:** ${lang}`);
        }
        if (u.identity.timezone) {
          const tz = u.identity.timezone === 'auto' ? Intl.DateTimeFormat().resolvedOptions().timeZone : u.identity.timezone;
          details.push(`**Timezone:** ${tz}`);
        }
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

    // Neurodivergence
    if (sec['cognitive']) {
      const activeCog = u.cognitiveOptions.filter(k => u.cognitiveActive[k]).map(k => getCognitiveLabel(k));
      if (activeCog.length) {
        md += `## Neurodivergence\n\n${activeCog.join(', ')}\n\n`;
      }
    }

    // Cognitive Style
    if (sec['cogStyle']) {
      const allDims = DEFAULT_COGNITIVE_STYLE_DIMS.concat(u.cognitiveStyleDims || []);
      const dims = allDims.filter(d => u.cognitiveStyle[d.key] && u.cognitiveStyle[d.key] !== 'balanced');
      if (dims.length) {
        md += '## Cognitive Style\n\n';
        dims.forEach(d => {
          const val = u.cognitiveStyle[d.key];
          const label = val === 'left' ? d.left : d.right;
          md += `- ${d.label}: ${label}\n`;
        });
        md += '\n';
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

    // Interests
    if (sec['interests'] && u.interests.length) {
      const filled = u.interests.filter(i => i.name.trim());
      if (filled.length) {
        md += '## Interests\n\n';
        filled.forEach(i => {
          md += `### ${i.name.trim()}\n`;
          if (i.context.trim()) md += `${i.context.trim()}\n`;
          md += '\n';
        });
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
      const details = [];
      if (a.model) details.push(`**Model:** ${a.model}`);
      if (a.role) details.push(`**Role:** ${a.role}`);
      if (details.length) md += details.join(' | ') + '\n\n';
    } else {
      md += '# Agent Profile\n\n';
    }

    if (sec['agent-about'] && a.about && a.about.trim()) {
      md += `## About\n\n${a.about.trim()}\n\n`;
    }

    // Tone & Format
    if (sec['communication']) {
      const commPrefs = a.communicationOptions
        .filter(k => isDefaultComm(k) ? !!a.communicationActive[k] : true)
        .map(k => getCommLabel(k));
      if (commPrefs.length) {
        md += '## Tone & Format\n\n';
        commPrefs.forEach(p => { md += `- ${p}\n`; });
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

    // When user is low
    if (sec['when-low']) {
      const lowPrefs = a.whenLowOptions
        .filter(k => isDefaultWhenLow(k) ? !!a.whenLowActive[k] : true)
        .map(k => getWhenLowLabel(k));
      if (lowPrefs.length) {
        md += '## When User Is Low\n\n';
        lowPrefs.forEach(p => { md += `- ${p}\n`; });
        md += '\n';
      }
    }

    // Autonomy
    if (sec['autonomy']) {
      const level = Number.isFinite(a.autonomyLevel) ? a.autonomyLevel : 50;
      md += '## Autonomy\n\n';
      md += `- **Autonomy:** ${getAutonomyDescription(level)} (${level}/100)\n\n`;
    }

    // Conditional rules
    if (sec['rules']) {
      const rules = (a.rules || []).filter((r) => (r.when || '').trim() || (r.then || '').trim());
      if (rules.length) {
        md += '## Conditional Rules\n\n';
        rules.forEach((r) => {
          md += `- When ${(r.when || '...').trim()} -> ${(r.then || '...').trim()}\n`;
        });
        md += '\n';
      }
    }

    // Character traits
    if (sec['traits']) {
      const traitEntries = a.traitOptions.filter(k => a.traits[k] !== undefined);
      if (traitEntries.length) {
        md += '## Character Traits\n\n';
        traitEntries.forEach(key => {
          const val = a.traits[key] ?? 50;
          const label = getTraitLabel(key);
          const desc = getTraitDescription(key, val);
          md += `- **${label}:** ${desc} (${val}/100)\n`;
        });
        md += '\n';
      }
    }

    // Avoid
    if (sec['avoid'] && a.avoid.length) {
      md += '## Avoid\n\n';
      a.avoid.forEach(item => { md += `- ${item}\n`; });
      md += '\n';
    }

    // Technical style
    if (sec['tech-style']) {
      const techPrefs = a.techStyleOptions
        .filter(k => isDefaultTech(k) ? !!a.techStyleActive[k] : true)
        .map(k => getTechLabel(k));
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
    u.identity = { name: '', age: '', location: '', pronouns: '', language: '', dialect: '', timezone: '' };
    u.about = '';
    u.cognitiveActive = {};
    u.cognitiveStyle = {};
    u.values = [];
    u.interests = [];
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
      const langMatch = intro.match(/\*\*Language:\*\*\s*([^|*\n]+)/);
      if (langMatch) {
        const langStr = langMatch[1].trim();
        const dialectMatch = langStr.match(/^(.+?)\s*\(([^)]+)\)$/);
        if (dialectMatch) {
          u.identity.language = dialectMatch[1].trim();
          u.identity.dialect = dialectMatch[2].trim();
        } else {
          u.identity.language = langStr;
        }
      }
      const tzMatch = intro.match(/\*\*Timezone:\*\*\s*([^|*\n]+)/);
      if (tzMatch) u.identity.timezone = tzMatch[1].trim();
    }

    if (getSection(sections, 'About')) {
      u.about = getSection(sections, 'About').trim();
      state.enabledSections['about'] = true;
    }

    // Parse Neurodivergence
    const neurotypeSrc = getSection(sections, 'Neurodivergence');
    if (neurotypeSrc) {
      state.enabledSections['cognitive'] = true;
      // Neurotype is comma-separated labels (not bullet list)
      const items = neurotypeSrc.split(',').map(s => s.trim()).filter(Boolean);
      // Only treat as neurotype if items look like toggle labels (no colon = not cognitive style dims)
      const isToggleList = items.every(i => !i.includes(':'));
      if (isToggleList) {
        items.forEach(item => {
          activateOptionByLabel({
            options: u.cognitiveOptions,
            active: u.cognitiveActive,
            labelFor: getCognitiveLabel,
            text: item,
            labels: u.cognitiveLabels,
          });
        });
      }
    }

    // Parse Cognitive Style (spectrum dimensions)
    const cogStyleSrc = getSection(sections, 'Cognitive Style');
    if (cogStyleSrc) {
      state.enabledSections['cogStyle'] = true;
      const lines = cogStyleSrc.split('\n').filter(l => l.trim().startsWith('-'));
      lines.forEach(line => {
        const match = line.match(/-\s*(.+?):\s*(.+)/);
        if (match) {
          const dimLabel = match[1].trim();
          const valLabel = match[2].trim();
          // Check built-in dims first
          const dim = DEFAULT_COGNITIVE_STYLE_DIMS.find(d => d.label.toLowerCase() === dimLabel.toLowerCase());
          if (dim) {
            if (valLabel.toLowerCase() === dim.left.toLowerCase()) u.cognitiveStyle[dim.key] = 'left';
            else if (valLabel.toLowerCase() === dim.right.toLowerCase()) u.cognitiveStyle[dim.key] = 'right';
          } else {
            // Custom dimension — reconstruct it
            const key = labelToKey(dimLabel);
            if (!u.cognitiveStyleDims.some(d => d.key === key)) {
              u.cognitiveStyleDims.push({ key, label: dimLabel, left: valLabel, right: '(unknown)' });
            }
            u.cognitiveStyle[key] = 'left'; // We only know the chosen side
          }
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

    // Interests
    if (getSection(sections, 'Interests')) {
      state.enabledSections['interests'] = true;
      parseTitledSubsections(getSection(sections, 'Interests')).forEach(({ title, body }) => {
        u.interests.push({ name: title, context: body });
      });
    }

    if (getSection(sections, 'People')) {
      state.enabledSections['people'] = true;
      parseTitledSubsections(getSection(sections, 'People')).forEach(({ title, body }) => {
        const firstLine = title;
        const relMatch = firstLine.match(/^(.+?)\s*\(([^)]+)\)/);
        const person = {
          name: relMatch ? relMatch[1].trim() : firstLine,
          relationship: relMatch ? relMatch[2].trim() : '',
          notes: body
        };
        if (person.name) u.people.push(person);
      });
    }

    if (getSection(sections, 'Projects')) {
      state.enabledSections['projects'] = true;
      parseTitledSubsections(getSection(sections, 'Projects')).forEach(({ title, body }) => {
        const firstLine = title;
        const statusMatch = firstLine.match(/^(.+?)\s*\[([^\]]+)\]/);
        const project = {
          name: statusMatch ? statusMatch[1].trim() : firstLine,
          status: statusMatch ? statusMatch[2].trim() : 'active',
          description: body
        };
        if (project.name) u.projects.push(project);
      });
    }

    const knownSections = ['about', 'neurodivergence', 'cognitive style', 'values', 'interests', 'people', 'projects'];
    Object.entries(sections).forEach(([title, content]) => {
      if (title.startsWith('_')) return;
      if (knownSections.includes(title.toLowerCase())) return;
      u.customSections.push({ title, content: content.trim() });
    });
  }

  function parseAgentMarkdown(md) {
    const a = state.agent;
    a.name = '';
    a.model = '';
    a.role = '';
    a.about = '';
    a.communicationActive = {};
    a.behaviorsActive = {};
    a.avoid = [];
    a.rules = [];
    a.autonomyLevel = 50;
    a.whenLowActive = {};
    a.techStyleActive = {};
    a.customSections = [];

    const sections = splitMarkdownSections(md);

    if (sections._title && sections._title !== 'Agent Profile') {
      a.name = sections._title;
    }

    if (sections._intro) {
      const intro = sections._intro;
      const modelMatch = intro.match(/\*\*Model:\*\*\s*([^|*\n]+)/);
      if (modelMatch) a.model = modelMatch[1].trim();
      const roleMatch = intro.match(/\*\*Role:\*\*\s*([^|*\n]+)/);
      if (roleMatch) a.role = roleMatch[1].trim();
    }

    if (getSection(sections, 'About')) {
      state.enabledSections['agent-about'] = true;
      a.about = getSection(sections, 'About').trim();
    }

    // Tone & Format
    const toneSrc = getSection(sections, 'Tone & Format');
    if (toneSrc) {
      state.enabledSections['communication'] = true;
      getBulletLines(toneSrc).forEach((text) => {
        activateOptionByLabel({
          options: a.communicationOptions,
          active: a.communicationActive,
          labelFor: getCommLabel,
          text,
          labels: a.communicationLabels,
          descs: a.communicationDescs,
          defaultDesc: '',
        });
      });
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

    const behaviorSrc = getSection(sections, 'Behaviors');
    if (behaviorSrc) {
      state.enabledSections['behaviors'] = true;
      getBulletLines(behaviorSrc).forEach((text) => {
        activateOptionByLabel({
          options: a.behaviorOptions,
          active: a.behaviorsActive,
          labelFor: getBehaviorLabel,
          text,
          labels: a.behaviorLabels,
        });
      });
    }

    if (getSection(sections, 'Autonomy')) {
      state.enabledSections['autonomy'] = true;
      for (const line of getBulletLines(getSection(sections, 'Autonomy'))) {
        const match = line.match(/\((\d+)\/100\)/);
        if (match) {
          const n = parseInt(match[1], 10);
          if (Number.isFinite(n)) {
            a.autonomyLevel = Math.max(0, Math.min(100, n));
            break;
          }
        }
      }
    }

    const rulesSrc = getSection(sections, 'Conditional Rules') || getSection(sections, 'Rules');
    if (rulesSrc) {
      state.enabledSections['rules'] = true;
      getBulletLines(rulesSrc).forEach((text) => {
        if (!text) return;
        const match = text.match(/^when\s+(.+?)\s*(?:->|→)\s*(.+)$/i);
        if (match) {
          a.rules.push({ when: match[1].trim(), then: match[2].trim() });
        } else {
          a.rules.push({ when: text, then: '' });
        }
      });
    }

    if (getSection(sections, 'Avoid')) {
      state.enabledSections['avoid'] = true;
      a.avoid = getBulletLines(getSection(sections, 'Avoid')).filter(Boolean);
    }

    if (getSection(sections, 'When User Is Low')) {
      state.enabledSections['when-low'] = true;
      getBulletLines(getSection(sections, 'When User Is Low')).forEach((text) => {
        activateOptionByLabel({
          options: a.whenLowOptions,
          active: a.whenLowActive,
          labelFor: getWhenLowLabel,
          text,
          labels: a.whenLowLabels,
          descs: a.whenLowDescs,
          defaultDesc: '',
        });
      });
    }

    if (getSection(sections, 'Technical Style')) {
      state.enabledSections['tech-style'] = true;
      getBulletLines(getSection(sections, 'Technical Style')).forEach((text) => {
        activateOptionByLabel({
          options: a.techStyleOptions,
          active: a.techStyleActive,
          labelFor: getTechLabel,
          text,
          labels: a.techStyleLabels,
          descs: a.techStyleDescs,
          defaultDesc: '',
        });
      });
    }

    const knownSections = [
      'about',
      'communication preferences',
      'tone & format',
      'tone and format',
      'character traits',
      'behaviors',
      'disposition',
      'autonomy',
      'conditional rules',
      'rules',
      'avoid',
      'when user is low',
      'technical style'
    ];
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

  function activateOptionByLabel({
    options,
    active,
    labelFor,
    text,
    labels,
    descs,
    defaultDesc = '',
  }) {
    const clean = String(text || '').trim();
    if (!clean) return null;
    const existing = options.find((k) => labelFor(k).toLowerCase() === clean.toLowerCase());
    if (existing) {
      active[existing] = true;
      return existing;
    }
    const key = labelToKey(clean);
    if (!options.includes(key)) {
      options.push(key);
      if (labels) labels[key] = clean;
      if (descs) descs[key] = defaultDesc;
    }
    active[key] = true;
    return key;
  }

  function getBulletLines(text) {
    return String(text || '')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('-'))
      .map((line) => line.replace(/^-\s*/, '').trim())
      .filter(Boolean);
  }

  function parseTitledSubsections(text) {
    return String(text || '')
      .split(/^###\s+/m)
      .filter(Boolean)
      .map((part) => {
        const lines = part.split('\n');
        return {
          title: (lines[0] || '').trim(),
          body: lines.slice(1).join('\n').trim(),
        };
      })
      .filter((item) => item.title);
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
      return ['About', 'Neurodivergence', 'Cognitive Style', 'Values', 'Interests', 'People', 'Projects'];
    }
    return [
      'About',
      'Tone & Format',
      'Character Traits',
      'Behaviors',
      'Autonomy',
      'Conditional Rules',
      'Rules',
      'Avoid',
      'When User Is Low',
      'Technical Style'
    ];
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
      verbosity: val < 30 ? 'Terse' : val < 50 ? 'Concise' : val < 70 ? 'Moderate' : 'Detailed',
      curiosity: val < 30 ? 'Focused' : val < 50 ? 'Occasionally exploratory' : val < 70 ? 'Curious' : 'Highly curious',
      independence: val < 30 ? 'Deferential' : val < 50 ? 'Collaborative' : val < 70 ? 'Self-directed' : 'Strongly independent'
    };
    if (descs[key]) return descs[key];
    // Generic for custom traits
    return val < 25 ? 'Very low' : val < 50 ? 'Low' : val < 75 ? 'Moderate' : 'High';
  }

  function getAutonomyDescription(val) {
    if (val < 25) return 'Cautious';
    if (val < 50) return 'Ask-first';
    if (val < 75) return 'Balanced';
    return 'Proactive';
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

  async function withPendingButton(button, pendingLabel, task) {
    if (!button) return task();
    const previousLabel = button.textContent;
    const previousDisabled = button.disabled;
    button.disabled = true;
    if (pendingLabel) button.textContent = pendingLabel;
    try {
      return await task();
    } finally {
      button.disabled = previousDisabled;
      button.textContent = previousLabel;
    }
  }

  async function runMutationAction(request, config = {}) {
    const {
      isSuccess = (result) => !!result,
      onSuccess = null,
      successMessage = '',
      failureMessage = 'Action failed',
      errorMessage = 'Action failed',
    } = config;
    try {
      const result = await request();
      if (!isSuccess(result)) {
        if (failureMessage) {
          showToast(
            typeof failureMessage === 'function' ? failureMessage(result) : failureMessage,
            'error'
          );
        }
        return { ok: false, result };
      }
      if (typeof onSuccess === 'function') {
        await onSuccess(result);
      }
      if (successMessage) {
        showToast(
          typeof successMessage === 'function' ? successMessage(result) : successMessage,
          'success'
        );
      }
      return { ok: true, result };
    } catch (err) {
      console.warn('Mutation action failed:', err);
      if (errorMessage) {
        showToast(
          typeof errorMessage === 'function' ? errorMessage(err) : errorMessage,
          'error'
        );
      }
      return { ok: false, error: err };
    }
  }

  async function readJsonSafely(resp) {
    try {
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  // ---- Server Status ----
  async function checkServerStatus() {
    try {
      const [statusResp, metricsResp] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/metrics'),
      ]);
      if (statusResp.ok) {
        state.serverConnected = true;
        state.statusCache = await statusResp.json();
      } else {
        state.serverConnected = false;
      }
      if (metricsResp.ok) {
        state.metricsCache = await metricsResp.json();
      } else if (!state.serverConnected) {
        state.metricsCache = null;
      }
    } catch (e) {
      state.serverConnected = false;
      state.metricsCache = null;
    }
    updateSidebarStatus();
    if (state.activePage === 'dashboard' || state.activePage === 'settings') {
      renderPage();
    }
  }

  function updateSidebarStatus() {
    const dots = document.querySelectorAll('.top-nav-status-dot');
    const texts = document.querySelectorAll('.top-nav-status-text');
    if (!dots.length || !texts.length) return;
    dots.forEach((dot) => {
      if (state.serverConnected) {
        dot.classList.add('online');
        dot.classList.remove('error');
      } else {
        dot.classList.remove('online');
        dot.classList.add('error');
      }
    });
    texts.forEach((text) => {
      text.textContent = state.serverConnected ? 'Connected' : 'Offline';
    });
    updateTopNavProcessing();
  }

  function updateTopNavProcessing() {
    const el = document.getElementById('top-nav-processing');
    if (!el) return;
    const files = (
      state.semanticProcessing
      && Array.isArray(state.semanticProcessing.files)
      ? state.semanticProcessing.files
      : []
    );
    const count = files.length;
    if (count <= 0) {
      el.hidden = true;
      el.textContent = '';
      return;
    }
    const noun = count === 1 ? 'document' : 'documents';
    el.textContent = `Processing ${count} ${noun}…`;
    el.hidden = false;
  }

  function setSemanticProcessing(filename, active) {
    const safe = String(filename || '').trim();
    if (!safe) return;
    const current = (
      state.semanticProcessing
      && Array.isArray(state.semanticProcessing.files)
      ? state.semanticProcessing.files
      : []
    );
    const next = current.filter((name) => name !== safe);
    if (active) next.push(safe);
    state.semanticProcessing = { files: next };
    updateTopNavProcessing();
  }

  // ---- Main Render (page router) ----
  function render() {
    recordConfigHistory();
    renderTokenBudget();
    renderPage();
    saveToLocalStorage();
    updateHistoryControls();
    updateTopNavProcessing();
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
    const settingsItem = document.getElementById('top-nav-open-settings') || document.getElementById('top-nav-settings');
    if (settingsItem) {
      settingsItem.classList.toggle('active', state.activePage === 'settings');
    }
  }

  function bindSidebarNav() {
    const utilityBtn = document.getElementById('top-nav-utilities');
    const utilityMenu = document.getElementById('top-nav-utility-menu');
    const settingsItem = document.getElementById('top-nav-open-settings') || document.getElementById('top-nav-settings');
    const setUtilityMenuOpen = (open) => {
      if (!utilityBtn || !utilityMenu) return;
      utilityMenu.hidden = !open;
      utilityBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      utilityBtn.classList.toggle('active', open);
    };

    // Logo = dashboard
    const homeLink = document.getElementById('top-nav-home');
    if (homeLink) {
      homeLink.addEventListener('click', (e) => {
        e.preventDefault();
        state.activePage = 'dashboard';
        syncNavHighlight();
        setUtilityMenuOpen(false);
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
        setUtilityMenuOpen(false);
        render();
      });
    });

    if (utilityBtn && utilityMenu) {
      utilityBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = utilityMenu.hidden;
        setUtilityMenuOpen(open);
      });

      utilityMenu.addEventListener('click', (e) => {
        e.stopPropagation();
      });

      document.addEventListener('click', () => setUtilityMenuOpen(false));
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') setUtilityMenuOpen(false);
      });
    }

    if (settingsItem) {
      settingsItem.addEventListener('click', () => {
        state.activePage = 'settings';
        syncNavHighlight();
        setUtilityMenuOpen(false);
        render();
      });
    }

    syncNavHighlight();
  }

  // ---- Dashboard Page ----
  function renderDashboard(container) {
    const status = state.statusCache;
    const metrics = state.metricsCache && typeof state.metricsCache === 'object'
      ? state.metricsCache
      : null;
    const totalNotes = status ? Number(status.total_notes || 0) : 0;
    const totalSessions = status ? Number(status.total_sessions || 0) : 0;
    const daemonRunning = status ? status.daemon_running : false;
    const seedsExist = status ? status.seeds_present : true;
    const daemonEnabled = status
      ? !!status.daemon_enabled
      : !!(((state.settingsCache || {}).daemon || {}).enabled);
    const daemonHealth = status && status.daemon_health ? status.daemon_health : null;
    const lastNoteDate = status ? status.last_note_date : '';
    const recentNotes = state.notesCache.slice(0, 5);
    const lastNote = recentNotes.length > 0 ? recentNotes[0] : null;

    // 7-day rhythm from metrics
    const last7 = metrics && Array.isArray(metrics.notes_generated_last_7_days)
      ? metrics.notes_generated_last_7_days : [];
    const maxCount7 = Math.max(1, ...last7.map(d => d.count || 0));
    const dayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

    const rhythmHtml = last7.map(d => {
      const count = d.count || 0;
      const height = count === 0 ? 4 : Math.max(8, Math.round((count / maxCount7) * 44));
      const dayOfWeek = new Date(d.date + 'T12:00:00').getDay();
      return `
        <div class="dash-rhythm-day">
          <div class="dash-rhythm-bar ${count === 0 ? 'empty' : ''}" style="height:${height}px;" title="${d.date}: ${count} note${count !== 1 ? 's' : ''}"></div>
          <span class="dash-rhythm-label">${dayLabels[dayOfWeek]}</span>
        </div>
      `;
    }).join('');

    // Single action-required module
    let actionRequiredHtml = '';
    let actionPrimaryId = '';
    if (!seedsExist) {
      actionRequiredHtml = `
        <section class="dash-action-required">
          <div class="dash-action-required-header">
            <span class="dash-action-required-icon">${ICON.alert}</span>
            <h2>Action required</h2>
          </div>
          <p>No seed files are deployed yet. Use Configure to create and publish user and agent seeds.</p>
          <div class="dash-action-required-actions">
            <button class="btn btn-primary" id="dash-action-open-configure">Open configure</button>
          </div>
        </section>
      `;
      actionPrimaryId = 'dash-action-open-configure';
    } else {
      const issues = daemonHealth && Array.isArray(daemonHealth.issues) ? daemonHealth.issues : [];
      let actionTitle = '';
      let actionText = '';
      let actionLabel = '';
      if (!daemonEnabled) {
        actionTitle = 'Action required';
        actionText = "Daemon is disabled. Session memories won't be generated until capture is enabled.";
        actionLabel = 'Enable daemon';
        actionPrimaryId = 'dash-action-enable-daemon';
      } else if (daemonHealth && daemonHealth.state !== 'healthy' && daemonHealth.state !== undefined) {
        actionTitle = 'Action required';
        if (issues.includes('daemon_not_running')) {
          actionText = 'Daemon capture is enabled but not currently running.';
        } else if (issues.includes('notes_lagging')) {
          actionText = 'Memory generation is lagging behind recent transcripts.';
        } else if (issues.includes('no_notes_generated')) {
          actionText = 'Transcripts exist, but no notes were generated yet.';
        } else {
          actionText = 'Memory capture needs attention.';
        }
        actionLabel = 'Open settings';
        actionPrimaryId = 'dash-action-open-settings';
      } else if (totalNotes === 0) {
        actionTitle = 'Get first memory';
        actionText = 'Seeds are set. Capture one session to start building your memory timeline.';
        actionLabel = 'Edit seeds';
        actionPrimaryId = 'dash-action-edit-seeds';
      }
      if (actionTitle && actionLabel && actionPrimaryId) {
        actionRequiredHtml = `
          <section class="dash-action-required">
            <div class="dash-action-required-header">
              <span class="dash-action-required-icon">${ICON.alert}</span>
              <h2>${esc(actionTitle)}</h2>
            </div>
            <p>${esc(actionText)}</p>
            <div class="dash-action-required-actions">
              <button class="btn btn-primary" id="${actionPrimaryId}">${esc(actionLabel)}</button>
            </div>
          </section>
        `;
      }
    }

    // Last session hero
    let sessionHtml = '';
    if (lastNote) {
      const when = lastNote.date
        ? new Date(lastNote.date).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
        : '';
      const tags = (lastNote.tags || []).map(t => `<span class="note-tag">${esc(t)}</span>`).join('');
      sessionHtml = `
        <section class="dash-session">
          <span class="dash-session-when">Last session \u00b7 ${esc(when)}</span>
          <p class="dash-session-summary">${esc(lastNote.summary || lastNote.content || 'No summary available')}</p>
          ${tags ? `<div class="dash-session-tags">${tags}</div>` : ''}
        </section>
      `;
    }

    // Daemon status
    const daemonStatusText = daemonRunning ? 'Active' : (daemonEnabled ? 'Stopped' : 'Off');
    const pulseClass = daemonRunning ? 'active' : (daemonEnabled ? 'inactive' : '');

    // Recent notes timeline (skip the first — it's the hero)
    let timelineHtml = '';
    if (recentNotes.length > 1) {
      const items = recentNotes.slice(1).map(note => {
        const salience = note.salience || 0;
        const dotColor = salience >= 1.5 ? 'var(--plum)' : salience >= 1.0 ? 'var(--sage)' : salience >= 0.5 ? 'var(--ochre-light)' : 'var(--border)';
        const date = note.date ? new Date(note.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
        const tags = (note.tags || []).slice(0, 3).map(t => `<span class="note-tag">${esc(t)}</span>`).join('');
        return `
          <button type="button" class="dash-timeline-item" data-nav-page="memories">
            <span class="dash-timeline-date">${date}</span>
            <span class="dash-timeline-dot" style="background:${dotColor}"></span>
            <div class="dash-timeline-body">
              <span class="dash-timeline-text">${esc(note.summary || note.title || 'Untitled')}</span>
              ${tags ? `<div class="dash-timeline-tags">${tags}</div>` : ''}
            </div>
          </button>
        `;
      }).join('');

      timelineHtml = `
        <section class="dash-recent">
          <div class="dash-recent-header">
            <h2>Recent</h2>
            <button class="btn btn-small" onclick="window.memorableApp.navigateTo('memories')">View all</button>
          </div>
          <div class="dash-timeline">${items}</div>
        </section>
      `;
    }

    container.innerHTML = `
      <div class="dashboard-page">
        <div class="dash-hero">
          <h1>Overview</h1>
          <span class="dash-hero-sub">${lastNoteDate ? `Last note ${formatRelativeTime(lastNoteDate)}` : (totalNotes > 0 ? totalNotes + ' notes captured' : 'No notes yet')}</span>
        </div>

        ${actionRequiredHtml}

        ${sessionHtml}

        <div class="dash-vitals">
          ${last7.length > 0 ? `
            <div class="dash-rhythm">
              <div class="dash-rhythm-title">This week</div>
              <div class="dash-rhythm-bars">${rhythmHtml}</div>
            </div>
          ` : ''}
          <div class="dash-stats">
            <div class="dash-stat">
              <span class="dash-stat-value">${totalNotes}</span>
              <span class="dash-stat-label">Notes</span>
            </div>
            <div class="dash-stat">
              <span class="dash-stat-value">${totalSessions}</span>
              <span class="dash-stat-label">Sessions</span>
            </div>
            <div class="dash-stat">
              <span class="dash-stat-value"><span class="dash-pulse ${pulseClass}"></span> ${esc(daemonStatusText)}</span>
              <span class="dash-stat-label">Daemon</span>
              ${lastNoteDate ? `<span class="dash-stat-sub">${formatRelativeTime(lastNoteDate)}</span>` : ''}
            </div>
          </div>
        </div>

        ${timelineHtml}

        <div class="dash-paths">
          <button class="dash-path-btn" onclick="window.memorableApp.navigateTo('configure')">
            ${ICON.file} Edit Seeds
          </button>
          <button class="dash-path-btn" onclick="window.memorableApp.navigateTo('memories')">
            ${ICON.search} Browse Notes
          </button>
          <button class="dash-path-btn" onclick="window.memorableApp.navigateTo('memories'); window.memorableApp.setMemoriesSubTab('semantic')">
            ${ICON.folder} Semantic Memory
          </button>
          <button class="dash-path-btn" onclick="window.memorableApp.navigateTo('settings')">
            ${ICON.settings} Settings
          </button>
        </div>
      </div>
    `;

    bindAll(container, '.dash-timeline-item[data-nav-page]', 'click', (_event, btn) => {
      const page = btn.dataset.navPage;
      if (page) window.memorableApp.navigateTo(page);
    });
    bindById('dash-action-enable-daemon', 'click', () => {
      window.memorableApp.enableDaemon();
    });
    bindById('dash-action-open-settings', 'click', () => {
      window.memorableApp.navigateTo('settings');
    });
    bindById('dash-action-open-configure', 'click', () => {
      window.memorableApp.navigateTo('configure');
    });
    bindById('dash-action-edit-seeds', 'click', () => {
      window.memorableApp.navigateTo('configure');
    });

    // Async: fetch recent notes if cache is empty
    if (state.notesCache.length === 0) {
      fetch('/api/notes?sort=date&limit=5')
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && Array.isArray(data.notes) && data.notes.length > 0) {
            state.notesCache = data.notes;
            if (state.activePage === 'dashboard') renderDashboard(container);
          }
        }).catch(() => {});
    }
  }


  // ==== PART 2: Notes Page, Settings Page, Seeds Page, Files Page ====

  // ---- Notes Page ----

  // Notes page state (persists across re-renders within the page)
  const notesState = {
    notes: [],
    tags: [],
    machines: [],
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
    const [tagsData, machinesData] = await Promise.all([
      apiFetch('/api/notes/tags?archived=' + archivedParam),
      apiFetch('/api/machines'),
    ]);
    notesState.tags = Array.isArray(tagsData && tagsData.tags) ? tagsData.tags : [];
    notesState.machines = Array.isArray(machinesData && machinesData.machines) ? machinesData.machines : [];
    if (
      notesState.machine
      && !notesState.machines.includes(notesState.machine)
    ) {
      // Clear stale machine selection so one chip is always active.
      notesState.machine = '';
    }
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
    const status = state.statusCache || null;
    const daemonEnabled = status && typeof status.daemon_enabled === 'boolean'
      ? status.daemon_enabled
      : !!(((state.settingsCache || {}).daemon || {}).enabled);

    // Machine tabs
    let machineTabsHtml = '';
    const machineOptions = Array.from(
      new Set(
        (Array.isArray(ns.machines) ? ns.machines : [])
          .map((m) => String(m || '').trim())
          .filter(Boolean)
      )
    );
    if (machineOptions.length > 0) {
      const allActive = ns.machine === '' ? ' active' : '';
      machineTabsHtml = `<div class="notes-device-tabs">
        <button type="button" class="notes-device-tab${allActive}" data-machine="">All</button>
        ${machineOptions.map(m => {
          const short = m.split('.')[0];
          const active = ns.machine === m ? ' active' : '';
          return `<button type="button" class="notes-device-tab${active}" data-machine="${esc(m)}">${esc(short)}</button>`;
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
        const pinAction = note.pinned ? 'unpin' : 'pin';
        const pinLabel = note.pinned ? 'Unpin' : 'Pin';
        const archiveAction = note.archived ? 'restore' : 'archive';
        const archiveLabel = note.archived ? 'Restore' : 'Archive';
        const tagsHtml = visibleTags.map(t => `<span class="note-tag">${esc(t)}</span>`).join('') +
          (note.pinned ? '<span class="note-review-chip pinned" title="Pinned notes receive extra retrieval weight.">Pinned</span>' : '') +
          (note.archived ? '<span class="note-review-chip archived" title="Archived notes are excluded by default.">Archived</span>' : '') +
          (overflowCount > 0 ? `<span class="note-tag">+${overflowCount}</span>` : '') +
          (shouldNotTry.length > 0 ? `<span class="note-antiforce-chip" title="Approaches marked as failed or unhelpful.">Avoid ${shouldNotTry.length}</span>` : '');

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
            <div class="notes-empty-icon">${ICON.alert}</div>
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
            <div class="notes-empty-icon">${ICON.fileText}</div>
            <h3>No notes match your filters</h3>
            <p>Try a different search term, tag, or clear active filters.</p>
          </div>
        `;
      } else if (!daemonEnabled) {
        notesHtml = `
          <div class="notes-empty">
            <div class="notes-empty-icon">${ICON.moon}</div>
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
            <div class="notes-empty-icon">${ICON.fileText}</div>
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
    const notesGuideHtml = '';

    const notesContentHtml = `
      <div class="notes-main">
        ${notesGuideHtml}
        ${machineTabsHtml}
        <div class="notes-search">
          <input type="text" class="notes-search-input" id="notes-search-input" placeholder="Search notes\u2026" value="${esc(ns.search)}">
        </div>
        <div class="notes-toolbar notes-toolbar-primary">
          <div class="notes-sort">
            <button class="notes-sort-btn ${ns.sort === 'date' ? 'active' : ''}" data-sort="date">Newest</button>
            <button class="notes-sort-btn ${ns.sort === 'date_asc' ? 'active' : ''}" data-sort="date_asc">Oldest</button>
            <button class="notes-sort-btn ${ns.sort === 'salience' ? 'active' : ''}" data-sort="salience" title="How relevant/important a note is. Higher salience notes are more likely to be loaded.">Salience</button>
          </div>
          <span class="notes-count">${ns.total} note${ns.total !== 1 ? 's' : ''}</span>
        </div>
        <div class="notes-toolbar notes-toolbar-secondary">
          <div class="notes-filters">
            <select class="notes-archive-filter" id="notes-archive-filter">
              <option value="exclude"${ns.archived === 'exclude' ? ' selected' : ''}>Active</option>
              <option value="only"${ns.archived === 'only' ? ' selected' : ''}>Archived</option>
              <option value="include"${ns.archived === 'include' ? ' selected' : ''}>All</option>
            </select>
            <select class="notes-tag-filter" id="notes-tag-filter">${tagOptions}</select>
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

    container.innerHTML = `
      <div class="notes-page">
        ${notesContentHtml}
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
      if (event.target.closest('a, button, .note-card-body')) return;
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
    if (!container.dataset.notesOutsideCloseBound) {
      container.addEventListener('click', (event) => {
        if (ns.expandedIdx === null) return;
        if (event.target.closest('.note-card')) return;
        ns.expandedIdx = null;
        const expanded = container.querySelector('.note-card.expanded');
        if (expanded) expanded.classList.remove('expanded');
      });
      container.dataset.notesOutsideCloseBound = 'true';
    }

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
        helper: 'Review captured sessions. Start with Newest, then pin or archive.',
      },
      working: {
        label: 'Working',
        helper: 'Your current rolling context — what\'s on your mind right now.',
      },
      semantic: {
        label: 'Semantic',
        helper: 'Long-lived knowledge documents with configurable zoom levels.',
      },
      deep: {
        label: 'Deep',
        helper: 'Large archives indexed for retrieval without startup context bloat.',
      },
    };
    const activeMemory = memoryKinds[subTab] || memoryKinds.episodic;

    // Sub-tab bar
    const subTabBar = `
      <div class="memories-sub-tabs">
        <button class="memories-sub-tab ${subTab === 'episodic' ? 'active' : ''}" data-subtab="episodic">Episodic</button>
        <button class="memories-sub-tab ${subTab === 'working' ? 'active' : ''}" data-subtab="working">Working</button>
        <button class="memories-sub-tab ${subTab === 'semantic' ? 'active' : ''}" data-subtab="semantic">Semantic</button>
        <button class="memories-sub-tab ${subTab === 'deep' ? 'active' : ''}" data-subtab="deep">Deep</button>
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
        <p>Session notes, current context, and reference documents</p>
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
      case 'deep':
        renderDeepMemory(contentEl);
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
      renderLoadErrorState(
        container,
        {
          title: 'Could not load working memory',
          message: 'Make sure the local server is running, then retry.',
          retryId: 'working-retry-btn',
          settingsId: 'working-open-settings-btn',
        },
        () => renderWorkingMemory(container)
      );
      return;
    }

    const nowContent = data.files['now.md'];
    if (!nowContent) {
      container.innerHTML = `
        <div class="notes-empty">
          <div class="notes-empty-icon">${ICON.clipboard}</div>
          <h3>No working memory yet</h3>
          <p>The now.md file will be created automatically by the <span title="Background process that watches sessions and auto-generates notes.">daemon</span> as sessions are processed.</p>
        </div>
      `;
      return;
    }

    const workingView = state.workingView || 'now';

    container.innerHTML = `
      <div class="working-toggle" style="display:flex;gap:0;margin-bottom:16px;border:1px solid var(--border-light, #e8e2d8);border-radius:8px;overflow:hidden;width:fit-content;">
        <button class="working-toggle-btn" data-view="now" style="padding:6px 16px;font-size:0.9em;border:none;cursor:pointer;background:${workingView === 'now' ? 'var(--accent, #6b5b3e)' : 'transparent'};color:${workingView === 'now' ? '#fff' : 'var(--text-secondary)'};">now.md</button>
        <button class="working-toggle-btn" data-view="observations" style="padding:6px 16px;font-size:0.9em;border:none;border-left:1px solid var(--border-light, #e8e2d8);cursor:pointer;background:${workingView === 'observations' ? 'var(--accent, #6b5b3e)' : 'transparent'};color:${workingView === 'observations' ? '#fff' : 'var(--text-secondary)'};">Observations</button>
      </div>
      <div id="working-view-content"></div>
    `;

    // Bind toggle
    container.querySelectorAll('.working-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.workingView = btn.dataset.view;
        renderWorkingMemory(container);
      });
    });

    const viewContent = container.querySelector('#working-view-content');

    if (workingView === 'now') {
      viewContent.innerHTML = `
        <div class="working-memory-card">
          <div class="working-memory-header">
            <span class="working-memory-label">now.md</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="working-memory-hint">Auto-generated from session notes</span>
              <button class="btn btn-small" id="regenerate-summary-btn" title="Regenerate from last 5 days of notes">${ICON.refresh} Regenerate</button>
            </div>
          </div>
          <div class="working-memory-content">${markdownToHtml(nowContent)}</div>
        </div>
      `;

      const regenBtn = viewContent.querySelector('#regenerate-summary-btn');
      if (regenBtn) {
        regenBtn.addEventListener('click', async () => {
          regenBtn.disabled = true;
          regenBtn.textContent = 'Regenerating...';
          try {
            const resp = await fetch('/api/regenerate-summary', { method: 'POST' });
            if (resp.ok) {
              renderWorkingMemory(container);
            } else {
              regenBtn.textContent = 'Failed — retry?';
              regenBtn.disabled = false;
            }
          } catch (e) {
            regenBtn.textContent = 'Failed — retry?';
            regenBtn.disabled = false;
          }
        });
      }
    } else {
      renderObservationsInline(viewContent);
    }
  }

  async function renderObservationsInline(container) {
    container.innerHTML = '<div style="padding:12px 0;color:var(--text-muted);font-size:0.9em;">Loading observations...</div>';

    const data = await apiFetch('/api/observations');
    if (!data || !data.observations || data.observations.length === 0) {
      container.innerHTML = `
        <div style="padding:16px 0;color:var(--text-muted);font-size:0.9em;">
          No observations yet. Facts are extracted every 15 messages during active sessions.
        </div>
      `;
      return;
    }

    const typeColors = {
      fact: '#5a8a5a',
      decision: '#7a6a3a',
      mood: '#8a5a5a',
      preference: '#5a6a8a',
      rejection: '#8a5a7a',
      open_thread: '#6a5a8a',
    };

    const typeIcons = {
      fact: '📌',
      decision: '⚖️',
      mood: '🌡️',
      preference: '⭐',
      rejection: '🚫',
      open_thread: '🧵',
    };

    // Group by day
    const byDay = {};
    for (const obs of data.observations) {
      const ts = obs.ts || '';
      const dayKey = ts ? new Date(ts).toLocaleDateString('en-AU', { weekday: 'long', month: 'short', day: 'numeric' }) : 'Unknown';
      if (!byDay[dayKey]) byDay[dayKey] = [];
      byDay[dayKey].push(obs);
    }

    const dayKeys = Object.keys(byDay);

    let html = `
      <div style="color:var(--text-muted);font-size:0.85em;padding-bottom:12px;">${data.count} observations across ${dayKeys.length} day(s)</div>
    `;

    dayKeys.forEach((day, idx) => {
      const observations = byDay[day];
      const isFirst = idx === 0;

      html += `
        <details class="obs-day-group" style="margin-bottom:8px;border:1px solid var(--border-light, #e8e2d8);border-radius:8px;overflow:hidden;" ${isFirst ? 'open' : ''}>
          <summary style="padding:10px 14px;cursor:pointer;font-weight:600;font-size:0.9em;color:var(--text-primary);background:var(--surface-elevated, #faf8f5);user-select:none;display:flex;justify-content:space-between;align-items:center;">
            <span>${esc(day)}</span>
            <span style="font-weight:400;font-size:0.85em;color:var(--text-muted);">${observations.length} observation${observations.length !== 1 ? 's' : ''}</span>
          </summary>
          <div style="padding:8px;">
      `;

      for (const obs of observations) {
        const type = obs.type || 'fact';
        const icon = typeIcons[type] || '📝';
        const color = typeColors[type] || '#666';
        const importance = obs.importance || 3;
        const dots = '●'.repeat(Math.min(importance, 5)) + '○'.repeat(Math.max(0, 5 - importance));

        html += `
          <div style="display:flex;gap:12px;padding:8px 10px;margin-bottom:4px;border-radius:6px;">
            <div style="font-size:1.1em;flex-shrink:0;">${icon}</div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:0.92em;line-height:1.5;color:var(--text-primary);">${esc(obs.content || '')}</div>
              <div style="display:flex;gap:12px;margin-top:4px;font-size:0.78em;color:var(--text-muted);">
                <span style="background:${color}22;color:${color};padding:1px 7px;border-radius:4px;font-weight:500;">${esc(type)}</span>
                <span title="Importance: ${importance}/5" style="letter-spacing:1px;font-size:0.85em;">${dots}</span>
              </div>
            </div>
          </div>
        `;
      }

      html += `</div></details>`;
    });

    container.innerHTML = html;
  }

  async function renderSemanticMemory(container) {
    container.innerHTML = '<div style="padding:20px;color:var(--text-muted);">Loading files...</div>';

    // Fetch files and seeds in parallel
    const [filesData, seedsData] = await Promise.all([
      apiFetch('/api/files'),
      apiFetch('/api/seeds'),
    ]);

    if (!filesData || !seedsData) {
      renderLoadErrorState(
        container,
        {
          title: 'Could not load semantic memory',
          message: 'Check that the local server is running, then retry.',
          retryId: 'semantic-retry-btn',
          settingsId: 'semantic-open-settings-btn',
          padded: true,
        },
        () => renderSemanticMemory(container)
      );
      return;
    }

    const files = Array.isArray(filesData && filesData.files) ? filesData.files : [];
    const seedFiles = (seedsData && typeof seedsData.files === 'object' && seedsData.files) ? seedsData.files : {};
    const seedNames = Object.keys(seedFiles).sort();
    const seedTooltips = {
      'knowledge.md': 'Long-term semantic knowledge distilled from recurring patterns in recent notes.',
      'now.md': 'Short-term working memory summary from recent sessions: themes, highlights, and open threads.',
    };

    // Identity files section (seeds)
    let seedsHtml = '';
    if (seedNames.length > 0) {
      seedsHtml = `
        <div class="semantic-section-header">Identity Files</div>
        <div class="semantic-seed-cards">
          ${seedNames.map(name => {
            const content = seedFiles[name] || '';
            const preview = content.trim()
              ? content.split('\n').slice(0, 6).join('\n')
              : '*No content yet. Use Regenerate to build this file.*';
            const tokens = Math.ceil(content.length / 4);
            const canRegenerate = name === 'knowledge.md' || name === 'now.md';
            const tooltip = seedTooltips[name] || '';
            return `
              <div class="semantic-seed-card">
                <div class="semantic-seed-header">
                  <div class="semantic-seed-title-row">
                    <span class="semantic-seed-name">${esc(name)}</span>
                    ${tooltip ? `
                      <span class="semantic-seed-help-wrap">
                        <button type="button" class="semantic-seed-help-btn" aria-label="What is ${esc(name)}?" tabindex="0">?</button>
                        <span class="semantic-seed-help-tooltip" role="tooltip">${esc(tooltip)}</span>
                      </span>
                    ` : ''}
                  </div>
                  <span class="semantic-seed-tokens">${tokens} tokens</span>
                </div>
                <div class="semantic-seed-preview">${markdownToHtml(preview)}</div>
                ${canRegenerate
                  ? `<button class="semantic-seed-configure-btn semantic-seed-regenerate-btn" data-seed-name="${esc(name)}">${ICON.refresh} Regenerate</button>`
                  : `<button class="semantic-seed-configure-btn" onclick="window.memorableApp.navigateTo('configure')">Configure</button>`
                }
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    // Upload zone
    const uploadHtml = `
      <div class="semantic-upload-zone" id="semantic-dropzone">
        <div class="semantic-upload-icon">${ICON.upload}</div>
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
            const isProcessed = !!f.processed;
            const levelCountRaw = Number.parseInt(f.levels, 10);
            const levelCount = Number.isFinite(levelCountRaw) ? Math.max(0, levelCountRaw) : 0;
            const hasLevels = isProcessed && levelCount > 0;
            const statusClass = hasLevels ? 'status-processed' : 'status-raw';
            const statusText = hasLevels ? `Processed (${levelCount} steps)` : 'Raw';

            const configuredDepthRaw = Number.parseInt(f.depth, 10);
            const configuredDepth = Number.isFinite(configuredDepthRaw)
              ? configuredDepthRaw
              : (hasLevels ? 1 : -1);
            const selectedDepth = hasLevels
              ? ((configuredDepth >= 1 && configuredDepth <= levelCount) ? configuredDepth : 1)
              : -1;

            const depthValues = hasLevels
              ? [...Array.from({ length: levelCount }, (_, idx) => idx + 1), -1]
              : [-1];
            const depthOptions = depthValues.map((d) => {
              let label = 'Raw file';
              if (d >= 1) {
                if (d === 1) label = 'Baseline (brief)';
                else if (d === levelCount) label = 'Full document';
                else label = `Detail step ${d}`;
              }
              return `<option value="${d}" ${selectedDepth === d ? 'selected' : ''}>${label}</option>`;
            }).join('');

            let depthInfo = '';
            const tokensByLevel = (f.tokens_by_level && typeof f.tokens_by_level === 'object')
              ? f.tokens_by_level
              : null;
            if (tokensByLevel) {
              const items = [];
              for (let level = 1; level <= levelCount; level += 1) {
                const key = String(level);
                const value = tokensByLevel[key];
                if (typeof value === 'number') items.push(`L${level}\u2248${value}`);
              }
              const rawTokens = Number.parseInt(f.tokens, 10);
              if (Number.isFinite(rawTokens) && rawTokens > 0) items.push(`raw\u2248${rawTokens}`);
              if (items.length) {
                depthInfo = `<div class="file-depth-info">Tokens: ${items.join(' &middot; ')}</div>`;
              }
            }

            return `
              <div class="file-card ${hasLevels ? 'file-card-processed' : ''}" data-filename="${esc(f.name)}">
                <div class="file-card-header">
                  <div class="file-card-info">
                    <span class="file-card-name">${esc(f.name)}</span>
                    <span class="file-status ${statusClass}">${statusText}</span>
                    <span class="file-card-meta">${f.tokens} tokens</span>
                  </div>
                  <div class="file-card-actions">
                    ${!hasLevels
                      ? `<button class="btn btn-primary btn-sm file-process-btn" data-filename="${esc(f.name)}" data-process-action="process">Process</button>`
                      : `<button class="btn btn-sm file-process-btn" data-filename="${esc(f.name)}" data-process-action="reprocess">Reprocess</button>`
                    }
                    <select class="file-depth-select" data-filename="${esc(f.name)}">${depthOptions}</select>
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
          <div class="notes-empty-icon">${ICON.book}</div>
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
          <p>Upload knowledge documents. Process them into hierarchical zoom levels, then choose which level to load during session start.</p>
        </div>
        ${uploadHtml}
        ${seedsHtml}
        ${filesHtml}
      </div>
    `;

    bindSemanticMemoryEvents(container);
  }

  async function renderDeepMemory(container) {
    container.innerHTML = '<div style="padding:20px;color:var(--text-muted);">Loading deep memory...</div>';

    const filesData = await apiFetch('/api/deep/files');
    if (!filesData) {
      renderLoadErrorState(
        container,
        {
          title: 'Could not load deep memory',
          message: 'Check that the local server is running, then retry.',
          retryId: 'deep-retry-btn',
          settingsId: 'deep-open-settings-btn',
          padded: true,
        },
        () => renderDeepMemory(container)
      );
      return;
    }

    const files = Array.isArray(filesData.files) ? filesData.files : [];
    const deepState = state.deepSearch || { query: '', results: [], count: 0, ran: false };
    const searchResults = Array.isArray(deepState.results) ? deepState.results : [];
    const searchCount = Number.isFinite(deepState.count) ? deepState.count : searchResults.length;

    const uploadHtml = `
      <div class="semantic-upload-zone" id="deep-dropzone">
        <div class="semantic-upload-icon">${ICON.upload}</div>
        <p>Drop a large document here, or click to upload</p>
        <p class="semantic-upload-hint">Indexed for retrieval, not auto-loaded at startup</p>
        <input type="file" id="deep-file-input" accept=".md,.txt,.text,.markdown,.rst,.org,.json,.csv,.log" multiple style="display:none">
        <div class="semantic-upload-progress" id="deep-upload-progress" hidden></div>
      </div>
    `;

    const searchHtml = `
      <div class="semantic-section-header">Search Deep Memory</div>
      <div class="notes-search">
        <input
          type="text"
          class="notes-search-input"
          id="deep-search-input"
          placeholder="Search threads, people, decisions..."
          value="${esc(deepState.query || '')}"
        >
      </div>
      <div class="notes-toolbar notes-toolbar-secondary">
        <button class="btn btn-primary btn-small" id="deep-search-btn">Search</button>
        <span class="notes-count">${searchCount} match${searchCount === 1 ? '' : 'es'}</span>
      </div>
      <div class="semantic-files-list">
        ${deepState.ran && searchResults.length === 0
          ? `
            <div class="notes-empty" style="padding:18px;">
              <div class="notes-empty-icon">${ICON.search}</div>
              <h3>No matches</h3>
              <p>Try shorter keywords or another anchor phrase.</p>
            </div>
          `
          : searchResults.map((item) => `
            <div class="file-card file-card-processed">
              <div class="file-card-header">
                <div class="file-card-info">
                  <span class="file-card-name">${esc(item.filename || '')}</span>
                  <span class="file-status status-processed">Chunk ${esc(String(item.chunk_index || ''))}</span>
                  <span class="file-card-meta">${esc(String(item.tokens || 0))} tokens</span>
                </div>
              </div>
              <div class="file-card-body expanded" style="display:block;padding-top:0;">
                <div class="file-preview-content file-preview-raw">${esc(item.snippet || '')}</div>
              </div>
            </div>
          `).join('')}
      </div>
    `;

    let filesHtml = '';
    if (files.length > 0) {
      filesHtml = `
        <div class="semantic-section-header">Deep Files</div>
        <div class="semantic-files-list">
          ${files.map((f) => `
            <div class="file-card ${f.processed ? 'file-card-processed' : ''}">
              <div class="file-card-header">
                <div class="file-card-info">
                  <span class="file-card-name">${esc(f.name)}</span>
                  <span class="file-status ${f.processed ? 'status-processed' : 'status-raw'}">${f.processed ? `Indexed (${f.chunks || 0} chunks)` : 'Raw'}</span>
                  <span class="file-card-meta">${esc(String(f.tokens || 0))} tokens</span>
                </div>
                <div class="file-card-actions">
                  <button class="btn ${f.processed ? 'btn-sm' : 'btn-primary btn-sm'} deep-process-btn" data-filename="${esc(f.name)}" data-process-action="${f.processed ? 'reprocess' : 'process'}">
                    ${f.processed ? 'Reprocess' : 'Process'}
                  </button>
                  <button class="btn btn-ghost btn-sm deep-delete-btn" data-filename="${esc(f.name)}">Delete</button>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      filesHtml = `
        <div class="semantic-section-header">Deep Files</div>
        <div class="notes-empty" style="padding:24px;">
          <div class="notes-empty-icon">${ICON.book}</div>
          <h3>No deep files yet</h3>
          <p>Upload conversation archives and large docs to build searchable long-term memory.</p>
          <div class="notes-empty-actions">
            <button class="btn btn-primary" id="deep-upload-first-btn">Upload First Document</button>
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="semantic-memory-page">
        <div class="semantic-placeholder">
          <p>Deep memory stores large documents for retrieval. These files are indexed and searched on demand.</p>
        </div>
        ${uploadHtml}
        ${searchHtml}
        ${filesHtml}
      </div>
    `;

    bindDeepMemoryEvents(container);
  }

  function bindSemanticMemoryEvents(container) {
    const dropzone = container.querySelector('#semantic-dropzone');
    const fileInput = container.querySelector('#semantic-file-input');

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

    bindById('semantic-upload-first-btn', 'click', () => {
      if (fileInput) fileInput.click();
    });

    bindAll(container, '.semantic-seed-regenerate-btn', 'click', async (e, btn) => {
      e.stopPropagation();
      const seedName = btn.dataset.seedName;
      const endpoint = seedName === 'knowledge.md' ? '/api/regenerate-knowledge' : '/api/regenerate-summary';
      const pendingLabel = seedName === 'knowledge.md' ? 'Regenerating knowledge...' : 'Regenerating now...';

      await withPendingButton(btn, pendingLabel, async () => {
        const outcome = await runMutationAction(
          () => apiFetch(endpoint, { method: 'POST' }),
          {
            isSuccess: (result) => !!result && result.ok === true,
            successMessage: () => `${seedName} regenerated`,
            failureMessage: (result) => `Could not regenerate ${seedName}: ${(result && result.error) || 'unknown'}`,
            errorMessage: (err) => `Could not regenerate ${seedName}: ${err.message}`,
          }
        );
        if (
          outcome.ok
          && state.activePage === 'memories'
          && state.memoriesSubTab === 'semantic'
          && container.isConnected
        ) {
          await renderSemanticMemory(container);
        }
      });
    });

    bindAll(container, '.file-process-btn', 'click', async (e, btn) => {
      e.stopPropagation();
      const filename = btn.dataset.filename;
      const action = btn.dataset.processAction === 'reprocess' ? 'reprocess' : 'process';
      setSemanticProcessing(filename, true);
      await withPendingButton(btn, action === 'reprocess' ? 'Reprocessing...' : 'Processing...', async () => {
        try {
          const outcome = await runMutationAction(
            () => apiFetch(`/api/files/${encodeURIComponent(filename)}/process`, { method: 'POST' }),
            {
              isSuccess: (result) => !!result && result.status === 'ok',
              successMessage: () => action === 'reprocess' ? `Reprocessed ${filename}` : `Processed ${filename}`,
              failureMessage: (result) => `${action === 'reprocess' ? 'Reprocessing' : 'Processing'} issue: ${(result && result.error) || 'unknown'}`,
              errorMessage: (err) => `${action === 'reprocess' ? 'Reprocessing' : 'Processing'} failed: ${err.message}`,
            }
          );
          if (
            outcome.ok
            && state.activePage === 'memories'
            && state.memoriesSubTab === 'semantic'
            && container.isConnected
          ) {
            await renderSemanticMemory(container);
          }
        } finally {
          setSemanticProcessing(filename, false);
        }
      });
    });

    bindAll(container, '.file-depth-select', 'change', async (e, select) => {
      e.stopPropagation();
      const filename = select.dataset.filename;
      const depth = parseInt(select.value, 10);
      const enabledToggle = container.querySelector(`.file-enabled-toggle[data-filename="${filename}"]`);
      const enabled = enabledToggle ? enabledToggle.checked : false;
      const outcome = await runMutationAction(
        () => apiFetch(`/api/files/${encodeURIComponent(filename)}/depth`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ depth, enabled }),
        }),
        {
          successMessage: 'Zoom level updated',
          failureMessage: 'Could not update depth',
        }
      );
      if (outcome.ok) {
        const card = select.closest('.file-card');
        if (card && card.classList.contains('expanded')) {
          await refreshSemanticFilePreview(card, { keepExisting: true, preserveScroll: true });
        }
      }
    });

    bindAll(container, '.file-enabled-toggle', 'change', async (e, toggle) => {
      e.stopPropagation();
      const filename = toggle.dataset.filename;
      const enabled = toggle.checked;
      const depthSelect = container.querySelector(`.file-depth-select[data-filename="${filename}"]`);
      const depth = depthSelect ? parseInt(depthSelect.value, 10) : -1;
      await runMutationAction(
        () => apiFetch(`/api/files/${encodeURIComponent(filename)}/depth`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ depth, enabled }),
        }),
        {
          successMessage: enabled ? 'Will load at session start' : 'Disabled',
          failureMessage: 'Could not update load setting',
        }
      );
    });

    bindAll(container, '.file-delete-btn', 'click', async (e, btn) => {
      e.stopPropagation();
      const filename = btn.dataset.filename;
      if (!confirm('Delete ' + filename + '?')) return;
      const outcome = await runMutationAction(
        () => apiFetch(`/api/files/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
        {
          successMessage: `Deleted ${filename}`,
          failureMessage: 'Delete failed',
        }
      );
      if (outcome.ok) await renderSemanticMemory(container);
    });

    bindAll(container, '.file-card', 'click', async (e, card) => {
      if (e.target.closest('.file-card-actions') || e.target.closest('.file-depth-info')) return;
      await toggleSemanticFilePreview(container, card);
    });
    if (!container.dataset.semanticOutsideCloseBound) {
      container.addEventListener('click', (event) => {
        const openCard = container.querySelector('.file-card.expanded');
        if (!openCard) return;
        if (event.target.closest('.file-card')) return;
        openCard.classList.remove('expanded');
      });
      container.dataset.semanticOutsideCloseBound = 'true';
    }
  }

  function bindDeepMemoryEvents(container) {
    const dropzone = container.querySelector('#deep-dropzone');
    const fileInput = container.querySelector('#deep-file-input');

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
        await handleDeepUpload(e.dataTransfer.files, container);
      });
      fileInput.addEventListener('change', async () => {
        await handleDeepUpload(fileInput.files, container);
        fileInput.value = '';
      });
    }

    bindById('deep-upload-first-btn', 'click', () => {
      if (fileInput) fileInput.click();
    });

    bindAll(container, '.deep-process-btn', 'click', async (e, btn) => {
      e.stopPropagation();
      const filename = btn.dataset.filename;
      const action = btn.dataset.processAction === 'reprocess' ? 'reprocess' : 'process';
      await withPendingButton(btn, action === 'reprocess' ? 'Reprocessing...' : 'Processing...', async () => {
        const outcome = await runMutationAction(
          () => apiFetch(`/api/deep/files/${encodeURIComponent(filename)}/process`, { method: 'POST' }),
          {
            isSuccess: (result) => !!result && result.status === 'ok',
            successMessage: () => action === 'reprocess' ? `Reprocessed ${filename}` : `Processed ${filename}`,
            failureMessage: (result) => `${action === 'reprocess' ? 'Reprocessing' : 'Processing'} issue: ${(result && result.error) || 'unknown'}`,
            errorMessage: (err) => `${action === 'reprocess' ? 'Reprocessing' : 'Processing'} failed: ${err.message}`,
          }
        );
        if (
          outcome.ok
          && state.activePage === 'memories'
          && state.memoriesSubTab === 'deep'
          && container.isConnected
        ) {
          await renderDeepMemory(container);
        }
      });
    });

    bindAll(container, '.deep-delete-btn', 'click', async (e, btn) => {
      e.stopPropagation();
      const filename = btn.dataset.filename;
      if (!confirm('Delete ' + filename + '?')) return;
      const outcome = await runMutationAction(
        () => apiFetch(`/api/deep/files/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
        {
          successMessage: `Deleted ${filename}`,
          failureMessage: 'Delete failed',
        }
      );
      if (
        outcome.ok
        && state.activePage === 'memories'
        && state.memoriesSubTab === 'deep'
        && container.isConnected
      ) {
        await renderDeepMemory(container);
      }
    });

    const runSearch = async () => {
      const input = container.querySelector('#deep-search-input');
      const query = input ? String(input.value || '').trim() : '';
      state.deepSearch = {
        ...(state.deepSearch || {}),
        query,
      };
      if (!query) {
        state.deepSearch = {
          query: '',
          results: [],
          count: 0,
          ran: false,
        };
        await renderDeepMemory(container);
        return;
      }
      const data = await apiFetch(`/api/deep/search?q=${encodeURIComponent(query)}&limit=30`);
      if (!data) {
        showToast('Search failed', 'error');
        return;
      }
      state.deepSearch = {
        query,
        results: Array.isArray(data.results) ? data.results : [],
        count: Number.isFinite(data.count) ? data.count : 0,
        ran: true,
      };
      await renderDeepMemory(container);
    };

    bindById('deep-search-btn', 'click', () => {
      runSearch();
    });
    bindById('deep-search-input', 'keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        runSearch();
      }
    });
  }

  function renderLoadErrorState(container, opts, onRetry) {
    const settingsClass = opts && opts.padded ? ' style="padding:24px;"' : '';
    const title = (opts && opts.title) || 'Could not load';
    const message = (opts && opts.message) || 'Retry and check settings.';
    const retryId = (opts && opts.retryId) || 'memories-retry-btn';
    const settingsId = (opts && opts.settingsId) || 'memories-open-settings-btn';

    container.innerHTML = `
      <div class="notes-empty"${settingsClass}>
        <div class="notes-empty-icon">${ICON.alert}</div>
        <h3>${esc(title)}</h3>
        <p>${esc(message)}</p>
        <div class="notes-empty-actions">
          <button class="btn btn-primary" id="${retryId}">Retry</button>
          <button class="btn" id="${settingsId}">Open Settings</button>
        </div>
      </div>
    `;

    bindRetrySettingsActions(container, retryId, settingsId, onRetry);
  }

  function bindRetrySettingsActions(container, retryId, settingsId, onRetry) {
    const retryBtn = container.querySelector(`#${retryId}`);
    if (retryBtn && typeof onRetry === 'function') {
      retryBtn.addEventListener('click', onRetry);
    }
    const settingsBtn = container.querySelector(`#${settingsId}`);
    if (settingsBtn) {
      settingsBtn.addEventListener('click', () => window.memorableApp.navigateTo('settings'));
    }
  }

  async function toggleSemanticFilePreview(container, card) {
    const filename = card.dataset.filename;
    const bodyId = 'file-body-' + filename.replace(/\./g, '-');
    const bodyEl = document.getElementById(bodyId);
    if (!bodyEl) return;

    const wasExpanded = card.classList.contains('expanded');
    container.querySelectorAll('.file-card.expanded').forEach((openCard) => {
      if (openCard !== card) openCard.classList.remove('expanded');
    });

    if (wasExpanded) {
      card.classList.remove('expanded');
      return;
    }

    card.classList.add('expanded');
    await refreshSemanticFilePreview(card);
  }

  async function refreshSemanticFilePreview(card, options = {}) {
    const { keepExisting = false, preserveScroll = false } = options;
    const filename = card.dataset.filename;
    const bodyId = 'file-body-' + filename.replace(/\./g, '-');
    const bodyEl = document.getElementById(bodyId);
    if (!bodyEl) return;

    const anchorTopBefore = preserveScroll ? card.getBoundingClientRect().top : 0;
    const scrollYBefore = preserveScroll ? window.scrollY : 0;

    if (!keepExisting || !bodyEl.innerHTML.trim()) {
      bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">Loading preview...</div>';
    }

    const depthSelect = card.querySelector('.file-depth-select');
    const selectedDepth = depthSelect ? Number.parseInt(depthSelect.value, 10) : -1;
    const depth = Number.isFinite(selectedDepth) ? selectedDepth : -1;
    const previewUrl = `/api/files/${encodeURIComponent(filename)}/preview?depth=${encodeURIComponent(String(depth))}`;

    const data = await apiFetch(previewUrl);
    if (data === null) {
      bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">Preview failed</div>';
      return;
    }
    if (!data.content) {
      bodyEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);">No content</div>';
      return;
    }

    const resolvedDepth = Number.parseInt(data.depth, 10);
    const isRaw = !Number.isFinite(resolvedDepth) || resolvedDepth < 1;
    const maxLevels = Number.parseInt(card.querySelector('.file-depth-select')?.options?.length || 0, 10) - 1;
    const depthLabel = isRaw
      ? 'raw'
      : (resolvedDepth === 1 ? 'baseline' : (maxLevels > 0 && resolvedDepth >= maxLevels ? 'full' : `detail step ${resolvedDepth}`));
    bodyEl.innerHTML = `
      <div class="file-preview-content ${isRaw ? 'file-preview-raw' : 'rendered-md'}">${isRaw ? esc(data.content) : markdownToHtml(data.content)}</div>
      <div class="file-preview-meta">${data.tokens} tokens (${depthLabel})</div>
    `;
    if (preserveScroll) {
      const anchorTopAfter = card.getBoundingClientRect().top;
      const delta = anchorTopAfter - anchorTopBefore;
      if (Math.abs(delta) > 1) {
        window.scrollTo(0, scrollYBefore + delta);
      }
    }
  }

  function uploadFileWithProgress(file, onProgress, endpoint = '/api/files/upload', options = {}) {
    const useRaw = !!(options && options.raw);
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
        const xhr = new XMLHttpRequest();
        xhr.open('POST', endpoint, true);
        if (useRaw) {
          xhr.setRequestHeader('Content-Type', 'application/octet-stream');
          xhr.setRequestHeader('X-Filename', file.name);
        } else {
          xhr.setRequestHeader('Content-Type', 'application/json');
        }

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
        if (useRaw) {
          xhr.send(reader.result);
          return;
        }
        const content = typeof reader.result === 'string'
          ? reader.result
          : String(reader.result || '');
        const payload = JSON.stringify({ filename: file.name, content });
        xhr.send(payload);
      };

      report(0, 'Reading');
      if (useRaw) {
        reader.readAsArrayBuffer(file);
      } else {
        reader.readAsText(file);
      }
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
        await uploadFileWithProgress(file, (percent, stage) => {
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

  async function handleDeepUpload(fileList, container) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;

    const dropzone = container.querySelector('#deep-dropzone');
    const input = container.querySelector('#deep-file-input');
    const progressRoot = container.querySelector('#deep-upload-progress');

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
        await uploadFileWithProgress(file, (percent, stage) => {
          updateFileProgress(index, percent, stage || 'Uploading');
        }, '/api/deep/files/upload', { raw: true });
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
    renderDeepMemory(container);
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

  function renderProviderCards(llm) {
    const providers = [
      { id: 'deepseek', name: 'DeepSeek', defaultModel: 'deepseek-chat', keyPlaceholder: 'sk-...' },
      { id: 'gemini', name: 'Gemini', defaultModel: 'gemini-2.5-flash', keyPlaceholder: 'AI...' },
      { id: 'claude', name: 'Claude (API)', defaultModel: 'claude-haiku-4-5-20251001', keyPlaceholder: 'sk-ant-...' },
    ];
    const activeProvider = llm.provider || 'deepseek';
    return providers.map(p => {
      const isActive = activeProvider === p.id;
      const hasKey = isActive && !!(llm.api_key);
      const statusText = hasKey ? 'Configured' : 'Not configured';
      const statusClass = hasKey ? 'configured' : 'not-configured';
      const expanded = state._expandedProvider === p.id;
      return `
        <div class="provider-card ${expanded ? 'expanded' : ''} ${isActive ? 'active' : ''}" data-provider="${p.id}">
          <div class="provider-card-header" data-toggle-provider="${p.id}">
            <div class="provider-card-name">${p.name}</div>
            <span class="provider-status provider-status-${statusClass}">${statusText}</span>
          </div>
          ${expanded ? `
          <div class="provider-card-body">
            <div class="settings-row">
              <div class="settings-row-info">
                <div class="settings-row-label">API Key</div>
                <div class="settings-row-desc">Stored locally, never sent anywhere</div>
              </div>
              <div class="settings-row-control">
                <input type="password" class="provider-apikey" data-provider="${p.id}" value="${esc(isActive ? (llm.api_key || '') : '')}" placeholder="${p.keyPlaceholder}">
              </div>
            </div>
            <div class="settings-row">
              <div class="settings-row-info">
                <div class="settings-row-label">Model</div>
              </div>
              <div class="settings-row-control">
                <input type="text" class="provider-model" data-provider="${p.id}" value="${esc(isActive ? (llm.model || p.defaultModel) : p.defaultModel)}" placeholder="${p.defaultModel}">
              </div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
              <button class="btn btn-primary btn-small provider-save-btn" data-provider="${p.id}">Save &amp; activate</button>
            </div>
          </div>
          ` : ''}
        </div>`;
    }).join('');
  }

  function renderSettingsPage(container) {
    const s = state.settingsCache || {};
    const llm = s.llm_provider || {};
    const routing = s.llm_routing || {};
    const claudeCli = s.claude_cli || {};
    const routeOptions = [
      { value: 'deepseek', label: 'DeepSeek (API)' },
      { value: 'claude_cli', label: 'Claude CLI (claude -p)' },
      { value: 'claude_api', label: 'Claude API' },
      { value: 'gemini', label: 'Gemini API' },
    ];
    const routeSelect = (selected) =>
      routeOptions
        .map((opt) => `<option value="${opt.value}" ${selected === opt.value ? 'selected' : ''}>${opt.label}</option>`)
        .join('');
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
              <div class="settings-section-icon ochre">${ICON.sun}</div>
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
              <div class="settings-section-icon terracotta">${ICON.settings}</div>
              <h3>Summarisation</h3>
            </div>
            <div class="settings-section-body">
              ${renderProviderCards(llm)}
              <div class="provider-routing-section">
                <div class="provider-routing-label">Per-task routing</div>
                <div class="settings-row">
                  <div class="settings-row-info">
                    <div class="settings-row-label">Session Notes</div>
                    <div class="settings-row-desc">Auto-generated summaries of each conversation</div>
                  </div>
                  <div class="settings-row-control">
                    <select id="settings-route-session-notes">${routeSelect(routing.session_notes || 'deepseek')}</select>
                  </div>
                </div>
                <div class="settings-row">
                  <div class="settings-row-info">
                    <div class="settings-row-label">Current Context (now.md)</div>
                    <div class="settings-row-desc">Rolling summary of what's happening right now</div>
                  </div>
                  <div class="settings-row-control">
                    <select id="settings-route-now-md">${routeSelect(routing.now_md || 'deepseek')}</select>
                  </div>
                </div>
                <div class="settings-row">
                  <div class="settings-row-info">
                    <div class="settings-row-label">Imported Documents</div>
                    <div class="settings-row-desc">Processing of uploaded files into zoom levels</div>
                  </div>
                  <div class="settings-row-control">
                    <select id="settings-route-document-levels">${routeSelect(routing.document_levels || 'deepseek')}</select>
                  </div>
                </div>
              </div>
              <div style="display:none">
                <input type="text" id="settings-claude-command" value="${esc(claudeCli.command || 'claude')}">
                <input type="text" id="settings-claude-prompt-flag" value="${esc(claudeCli.prompt_flag || '-p')}">
                <input type="text" id="settings-llm-endpoint" value="${esc(llm.endpoint || '')}">
              </div>
            </div>
          </div>

          <div class="settings-section">
            <div class="settings-section-header">
              <div class="settings-section-icon sage">${ICON.book}</div>
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
              <div class="settings-section-icon sand">${ICON.compass}</div>
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
              <div class="settings-section-icon ochre">${ICON.folder}</div>
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
              <div class="settings-section-icon sage">${ICON.plug}</div>
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
    bindSettingsPageEvents();
  }

  function getInputValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
  }

  function getCheckboxValue(id) {
    const el = document.getElementById(id);
    return !!(el && el.checked);
  }

  function buildSettingsPayload() {
    return {
      llm_routing: {
        session_notes: getInputValue('settings-route-session-notes'),
        now_md: getInputValue('settings-route-now-md'),
        document_levels: getInputValue('settings-route-document-levels'),
      },
      claude_cli: {
        command: getInputValue('settings-claude-command'),
        prompt_flag: getInputValue('settings-claude-prompt-flag'),
      },
      token_budget: parseInt(getInputValue('settings-token-budget'), 10),
      daemon: {
        enabled: getCheckboxValue('settings-daemon-enabled'),
        idle_threshold: parseInt(getInputValue('settings-idle-threshold'), 10),
      },
      server_port: parseInt(getInputValue('settings-port'), 10),
    };
  }

  async function handleSettingsSave() {
    const settings = buildSettingsPayload();
    await runMutationAction(
      () => apiFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      }),
      {
        onSuccess: (result) => {
          if (result.settings) {
            state.settingsCache = result.settings;
            return;
          }
          state.settingsCache = { ...state.settingsCache, ...settings };
        },
        successMessage: 'Settings saved',
        failureMessage: 'Failed to save settings (server offline?)',
      }
    );
  }

  async function handleSettingsExport() {
    try {
      const resp = await fetch('/api/export');
      if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
      const blob = await resp.blob();
      const cd = resp.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="([^"]+)"/i);
      const filename = match ? match[1] : 'memorable-export.zip';
      triggerDownload(blob, filename);
      showToast('Data exported as ZIP', 'success');
    } catch (err) {
      console.warn('Export failed:', err);
      const fallbackBlob = new Blob([JSON.stringify(state, null, 2)], {
        type: 'application/json',
      });
      triggerDownload(fallbackBlob, 'memorable-export.json');
      showToast('Exported local data (server offline)', '');
    }
  }

  async function handleSettingsImportChange(event) {
    const input = event.target;
    const file = input.files && input.files[0];
    input.value = '';
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
          'X-Filename': file.name,
        },
        body: file,
      });

      const data = await readJsonSafely(resp);
      if (!resp.ok) {
        const message = data && data.error && data.error.message
          ? data.error.message
          : `Import failed (${resp.status})`;
        throw new Error(message);
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
  }

  async function handleSettingsReset() {
    if (!confirm('Reset ALL data? This cannot be undone.')) return;

    const token = prompt('Type RESET to confirm permanent deletion.');
    if (token === null) return;
    if (token.trim() !== 'RESET') {
      showToast('Reset canceled (token mismatch)', '');
      return;
    }

    const outcome = await runMutationAction(
      () => apiFetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmation_token: token.trim() }),
      }),
      {
        isSuccess: (result) => !!result && result.ok === true,
        successMessage: 'All data reset',
        failureMessage: 'Reset failed',
      }
    );
    if (!outcome.ok) return;
    localStorage.removeItem('seedConfigurator');
    location.reload();
  }

  function bindSettingsThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;
    const current = localStorage.getItem('memorable-theme') || 'auto';
    const activeBtn = themeToggle.querySelector(`[data-theme="${current}"]`);
    if (activeBtn) activeBtn.classList.add('active');
    themeToggle.addEventListener('click', (e) => {
      const btn = e.target.closest('.theme-toggle-btn');
      if (!btn) return;
      themeToggle.querySelectorAll('.theme-toggle-btn').forEach((toggleBtn) => {
        toggleBtn.classList.remove('active');
      });
      btn.classList.add('active');
      localStorage.setItem('memorable-theme', btn.dataset.theme);
      applyTheme();
    });
  }

  function bindSettingsPageEvents() {
    bindSettingsThemeToggle();

    bindById('settings-retry-status-btn', 'click', async () => {
      await Promise.all([checkServerStatus(), loadSettings()]);
      showToast('Status refreshed', 'success');
    });

    bindById('settings-token-budget', 'input', (event) => {
      const value = parseInt(event.target.value, 10);
      const display = document.getElementById('token-budget-display');
      if (display) display.textContent = `${formatTokens(value)} tokens`;
    });

    bindById('settings-save-btn', 'click', handleSettingsSave);

    // Provider card toggle/save
    const pageContainer = document.getElementById('page-container');
    document.querySelectorAll('[data-toggle-provider]').forEach(el => {
      el.addEventListener('click', () => {
        const provider = el.dataset.toggleProvider;
        state._expandedProvider = state._expandedProvider === provider ? null : provider;
        renderSettingsPage(pageContainer);
      });
    });
    document.querySelectorAll('.provider-save-btn').forEach(el => {
      el.addEventListener('click', async () => {
        const provider = el.dataset.provider;
        const card = el.closest('.provider-card');
        const apiKey = card.querySelector('.provider-apikey').value;
        const model = card.querySelector('.provider-model').value;
        const llmPayload = { provider, api_key: apiKey, model };
        await runMutationAction(
          () => apiFetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ llm_provider: llmPayload }),
          }),
          {
            onSuccess: (result) => {
              if (result.settings) state.settingsCache = result.settings;
              state._expandedProvider = null;
            },
            successMessage: `${provider.charAt(0).toUpperCase() + provider.slice(1)} activated`,
            errorMessage: 'Failed to save provider',
          }
        );
        renderSettingsPage(pageContainer);
      });
    });
    bindById('settings-export-btn', 'click', handleSettingsExport);
    bindById('settings-import-btn', 'click', () => {
      const fileInput = document.getElementById('settings-import-input');
      if (fileInput) fileInput.click();
    });
    bindById('settings-import-input', 'change', handleSettingsImportChange);
    bindById('settings-reset-btn', 'click', handleSettingsReset);
  }

  // ---- Seeds Page ----
  function renderSeedsPage(container) {
    container.innerHTML = `
      <div class="seeds-page">
        <div class="seeds-header">
          <div class="seeds-header-row">
            <div class="seeds-sub-nav">
              <button class="seeds-tab ${state.activeFile === 'user' ? 'active' : ''}" data-seed-file="user">
                <span class="tab-icon">${ICON.user}</span>user.md
              </button>
              <button class="seeds-tab ${state.activeFile === 'agent' ? 'active' : ''}" data-seed-file="agent">
                <span class="tab-icon">${ICON.settings}</span>agent.md
              </button>
            </div>
            <span class="save-indicator save-state-idle"><span class="dot"></span> Auto-save on</span>
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
      <div class="seeds-actions">
        <span class="seed-sync-indicator ${seedStatus.className}" title="${esc(seedStatus.title)}">
          <span class="dot"></span>${esc(seedStatus.text)}
        </span>
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
          // Deploy settle animation — all sections settle
          document.querySelectorAll('.section').forEach(s => {
            s.classList.add('deploy-settle');
            s.addEventListener('animationend', () => s.classList.remove('deploy-settle'), { once: true });
          });
          showToast('Seeds are live', 'success');
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

  // ---- Preview ----
  function renderPreview() {
    const container = document.getElementById('preview-content');
    if (!container) return;
    const md = state.activeFile === 'user' ? generateUserMarkdown() : generateAgentMarkdown();
    const prevMd = markdownCache[state.activeFile] || '';
    container.innerHTML = markdownToHtml(md);
    markdownCache[state.activeFile] = md;

    // Connective preview: click heading anchors to jump to form section
    container.querySelectorAll('[data-preview-section]').forEach(el => {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => {
        const slug = el.dataset.previewSection;
        let sectionId = PREVIEW_TO_SECTION[slug];
        if (sectionId) {
          let sectionEl = document.getElementById('section-' + sectionId);
          // Fallback: try agent-prefixed version (e.g. 'about' -> 'agent-about')
          if (!sectionEl && state.activeFile === 'agent') {
            sectionEl = document.getElementById('section-agent-' + sectionId);
          }
          if (sectionEl) {
            sectionEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            sectionEl.classList.add('preview-highlight');
            setTimeout(() => sectionEl.classList.remove('preview-highlight'), 1200);
          }
        }
      });
    });

    // Change pulse: highlight lines that changed since last render
    if (prevMd && prevMd !== md) {
      const prevLines = prevMd.split('\n');
      const newLines = md.split('\n');
      const previewEls = container.querySelectorAll('h1, h2, h3, p, li, blockquote');
      let elIdx = 0;
      for (let i = 0; i < newLines.length && elIdx < previewEls.length; i++) {
        const line = newLines[i].trim();
        if (!line) continue;
        if (i >= prevLines.length || prevLines[i] !== newLines[i]) {
          previewEls[elIdx].classList.add('preview-pulse');
          const pEl = previewEls[elIdx];
          setTimeout(() => pEl.classList.remove('preview-pulse'), 1000);
        }
        elIdx++;
      }
    }
  }

  // Connective preview: scroll preview to matching section on form focus
  function scrollPreviewToSection(sectionId) {
    const container = document.getElementById('preview-content');
    if (!container) return;
    const reverseMap = {};
    Object.entries(PREVIEW_TO_SECTION).forEach(([slug, id]) => { reverseMap[id] = slug; });
    const slug = reverseMap[sectionId];
    if (!slug) return;
    const el = container.querySelector(`[data-preview-section="${slug}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('preview-pulse');
      setTimeout(() => el.classList.remove('preview-pulse'), 1000);
    }
  }

  // ---- Token Budget ----
  function renderTokenBudget() {
    const container = document.getElementById('token-budget');
    if (!container) return;
    if (state.activePage !== 'configure') {
      container.innerHTML = '';
      return;
    }

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
          const icon = b.type === 'seed' ? ICON.clipboard : ICON.link;
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
                <span class="token-budget-chevron">${ICON.chevDown}</span>
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
    return `
      <div class="preset-bar">
        <div class="preset-bar-label">Why do you use Claude?</div>
        <div class="preset-group">
          ${Object.entries(PRESETS).map(([key, preset]) => `
            <button class="preset-btn ${state.preset === key ? 'active' : ''}" data-preset="${key}">${preset.label}</button>
          `).join('')}
        </div>
        <div class="preset-bar-hint">Presets suggest which sections to enable. Advanced sections start collapsed so the core setup path stays focused.</div>
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
          <button type="button" class="section-header-left" data-section-expand="section-${id}" aria-expanded="${state.collapsedSections[id] ? 'false' : 'true'}" aria-controls="section-body-${id}">
            <div class="section-icon ${colorClass}">${icon}</div>
            <div>
              <div class="section-title">${title}</div>
              <div class="section-subtitle">${subtitle}</div>
            </div>
          </button>
          <div class="section-header-right">
            <label class="section-toggle">
              <input type="checkbox" ${enabled ? 'checked' : ''} data-section-toggle="${id}">
              <span class="section-toggle-track"></span>
            </label>
            <button type="button" class="section-chevron-btn" data-section-expand="section-${id}" aria-expanded="${state.collapsedSections[id] ? 'false' : 'true'}" aria-controls="section-body-${id}">
              <span class="section-chevron">${ICON.chevDown}</span>
            </button>
          </div>
        </div>
        <div class="section-body" id="section-body-${id}">
          ${body}
        </div>
      </div>
    `;
  }

  // ---- User Form ----
  function renderUserForm(container) {
    const u = state.user;
    const builtinLanguages = [
      'English', 'Spanish', 'French', 'German', 'Portuguese', 'Italian', 'Dutch', 'Japanese',
      'Korean', 'Mandarin', 'Arabic', 'Hindi', 'Russian', 'Polish', 'Swedish', 'Turkish'
    ];
    const isCustomLanguage = !!(u.identity.language && !builtinLanguages.includes(u.identity.language));
    container.innerHTML = `
      ${renderPresetBar()}

      ${renderSection('identity', 'Identity', 'Basic details for context', 'terracotta', ICON.star, `
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
        <div class="form-row-locale" id="locale-row">
          <div class="form-group">
            <label>${ICON.globe} Language</label>
            <select id="identity-language">
              <option value="">Not set</option>
              ${builtinLanguages.map((lang) => `
                <option value="${lang}" ${u.identity.language === lang ? 'selected' : ''}>${lang}</option>
              `).join('')}
              <option value="_other" ${isCustomLanguage ? 'selected' : ''}>Other...</option>
            </select>
          </div>
          <div class="form-group" id="dialect-group" style="${u.identity.language === 'English' ? '' : 'display:none'}">
            <label>Dialect</label>
            <select data-bind="user.identity.dialect" id="identity-dialect">
              <option value="">Not set</option>
              <option value="US" ${u.identity.dialect === 'US' ? 'selected' : ''}>US</option>
              <option value="UK" ${u.identity.dialect === 'UK' ? 'selected' : ''}>UK</option>
              <option value="Australian" ${u.identity.dialect === 'Australian' ? 'selected' : ''}>Australian</option>
              <option value="Canadian" ${u.identity.dialect === 'Canadian' ? 'selected' : ''}>Canadian</option>
              <option value="Irish" ${u.identity.dialect === 'Irish' ? 'selected' : ''}>Irish</option>
              <option value="South African" ${u.identity.dialect === 'South African' ? 'selected' : ''}>South African</option>
              <option value="Indian" ${u.identity.dialect === 'Indian' ? 'selected' : ''}>Indian</option>
              <option value="NZ" ${u.identity.dialect === 'NZ' ? 'selected' : ''}>New Zealand</option>
            </select>
          </div>
          <div class="form-group">
            <label>Timezone</label>
            <select data-bind="user.identity.timezone" id="identity-timezone">
              <option value="">Not set</option>
              <option value="auto" ${u.identity.timezone === 'auto' ? 'selected' : ''}>Auto-detect (${Intl.DateTimeFormat().resolvedOptions().timeZone})</option>
              <option value="Pacific/Auckland" ${u.identity.timezone === 'Pacific/Auckland' ? 'selected' : ''}>Pacific/Auckland (NZST)</option>
              <option value="Australia/Sydney" ${u.identity.timezone === 'Australia/Sydney' ? 'selected' : ''}>Australia/Sydney (AEST)</option>
              <option value="Asia/Tokyo" ${u.identity.timezone === 'Asia/Tokyo' ? 'selected' : ''}>Asia/Tokyo (JST)</option>
              <option value="Asia/Shanghai" ${u.identity.timezone === 'Asia/Shanghai' ? 'selected' : ''}>Asia/Shanghai (CST)</option>
              <option value="Asia/Kolkata" ${u.identity.timezone === 'Asia/Kolkata' ? 'selected' : ''}>Asia/Kolkata (IST)</option>
              <option value="Asia/Dubai" ${u.identity.timezone === 'Asia/Dubai' ? 'selected' : ''}>Asia/Dubai (GST)</option>
              <option value="Europe/Moscow" ${u.identity.timezone === 'Europe/Moscow' ? 'selected' : ''}>Europe/Moscow (MSK)</option>
              <option value="Europe/Istanbul" ${u.identity.timezone === 'Europe/Istanbul' ? 'selected' : ''}>Europe/Istanbul (TRT)</option>
              <option value="Europe/Berlin" ${u.identity.timezone === 'Europe/Berlin' ? 'selected' : ''}>Europe/Berlin (CET)</option>
              <option value="Europe/London" ${u.identity.timezone === 'Europe/London' ? 'selected' : ''}>Europe/London (GMT)</option>
              <option value="Europe/Dublin" ${u.identity.timezone === 'Europe/Dublin' ? 'selected' : ''}>Europe/Dublin (IST)</option>
              <option value="America/Sao_Paulo" ${u.identity.timezone === 'America/Sao_Paulo' ? 'selected' : ''}>America/Sao_Paulo (BRT)</option>
              <option value="America/New_York" ${u.identity.timezone === 'America/New_York' ? 'selected' : ''}>America/New_York (EST)</option>
              <option value="America/Chicago" ${u.identity.timezone === 'America/Chicago' ? 'selected' : ''}>America/Chicago (CST)</option>
              <option value="America/Denver" ${u.identity.timezone === 'America/Denver' ? 'selected' : ''}>America/Denver (MST)</option>
              <option value="America/Los_Angeles" ${u.identity.timezone === 'America/Los_Angeles' ? 'selected' : ''}>America/Los_Angeles (PST)</option>
              <option value="Pacific/Honolulu" ${u.identity.timezone === 'Pacific/Honolulu' ? 'selected' : ''}>Pacific/Honolulu (HST)</option>
            </select>
          </div>
        </div>
        <div class="form-group" id="identity-language-custom-group" style="${isCustomLanguage ? '' : 'display:none'}">
          <label>Custom language</label>
          <input type="text" id="identity-language-custom" value="${esc(isCustomLanguage ? u.identity.language : '')}" placeholder="Enter language">
        </div>
      `)}

      ${renderSection('about', 'About', 'Context that helps responses fit you', 'sage', ICON.edit, `
        <div class="form-group">
          <textarea data-bind="user.about" rows="4" placeholder="Tell the agent about yourself. What matters to you? What should it know?">${esc(u.about)}</textarea>
        </div>
      `)}

      ${renderSection('cognitive', 'Neurodivergence', 'Select any that apply', 'sand', ICON.sparkle, `
        <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:10px;">Select any that apply. This helps the agent adapt its communication style.</p>
        <div class="toggle-group" id="cognitive-toggles">
          ${u.cognitiveOptions.map(k => {
            const active = u.cognitiveActive[k];
            const isCustom = !isDefaultCognitive(k);
            return `
              <div class="toggle-item-wrap ${isCustom ? 'is-custom' : ''}">
                <button type="button" class="toggle-item ${active ? 'active' : ''}" data-cognitive="${k}" aria-pressed="${active ? 'true' : 'false'}">
                  <span class="toggle-check">${active ? ICON.check : ''}</span>
                  ${getCognitiveLabel(k)}
                  ${isCustom ? '<span class="custom-badge">Custom</span>' : ''}
                </button>
                ${isCustom ? `<button type="button" class="toggle-remove" data-remove-cognitive="${k}" title="Remove custom item">${ICON.x}</button>` : ''}
              </div>
            `;
          }).join('')}
          <button type="button" class="toggle-item custom-toggle" id="add-cognitive-btn">${ICON.plus} Add custom option</button>
        </div>
      `)}

      ${renderSection('cogStyle', 'Cognitive Style', 'How you prefer ideas to be explained', 'clay', ICON.settings, `
        <div class="spectrum-group" id="cogstyle-spectrums">
          ${DEFAULT_COGNITIVE_STYLE_DIMS.concat(u.cognitiveStyleDims || []).map(d => {
            const val = u.cognitiveStyle[d.key] || 'balanced';
            const isCustom = !DEFAULT_COGNITIVE_STYLE_DIMS.some(dd => dd.key === d.key);
            return `
              <div class="spectrum-row">
                <div class="spectrum-label">${d.label}</div>
                <div class="spectrum-pills" data-cogstyle="${d.key}">
                  <button class="spectrum-pill ${val === 'left' ? 'active' : ''}" data-val="left">${d.left}</button>
                  <button class="spectrum-pill ${val === 'balanced' ? 'active' : ''}" data-val="balanced">Balanced</button>
                  <button class="spectrum-pill ${val === 'right' ? 'active' : ''}" data-val="right">${d.right}</button>
                </div>
                ${isCustom ? `<button class="btn btn-icon btn-danger-ghost btn-small" data-remove-cogstyle="${d.key}" title="Remove">${ICON.x}</button>` : ''}
              </div>
            `;
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-cogstyle-btn" style="margin-top:12px;">${ICON.plus} Add custom dimension</button>
      `)}

      ${renderSection('values', 'Values', 'Ranked preferences that guide responses', 'terracotta', ICON.scale, `
        <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:10px;">What matters more? Left side is preferred over right side.</p>
        <div class="value-pairs" id="value-pairs">
          ${u.values.map((v, i) => `
            <div class="value-pair" data-index="${i}">
              <input type="text" value="${esc(v.higher)}" data-pair="higher" placeholder="More important">
              <span class="separator">&gt;</span>
              <input type="text" value="${esc(v.lower)}" data-pair="lower" placeholder="Less important">
              <button class="btn btn-icon btn-danger-ghost" data-remove-value="${i}" title="Remove">${ICON.x}</button>
            </div>
          `).join('')}
        </div>
        <button class="add-item-btn" id="add-value-btn">${ICON.plus} Add value pair</button>
      `)}

      ${renderSection('interests', 'Interests', 'Things you care about', 'sage', ICON.star, `
        <div class="repeatable-list" id="interests-list" data-reorder-list="interests">
          ${u.interests.length ? u.interests.map((item, i) => renderInterestItem(item, i)).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">${ICON.star}</div>
              <h3>No interests added yet</h3>
              <p>Add things you care about so the agent knows when to go deeper or when to skim.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-interest-btn">${ICON.plus} Add interest</button>
      `)}

      ${renderSection('people', 'People', 'People the agent should know about', 'clay', ICON.users, `
        <div class="repeatable-list" id="people-list" data-reorder-list="people">
          ${u.people.length ? u.people.map((p, i) => renderPersonItem(p, i)).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">${ICON.users}</div>
              <h3>No people added yet</h3>
              <p>Add people the agent should know about &mdash; family, friends, colleagues, or anyone relevant to your conversations.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-person-btn">${ICON.plus} Add person</button>
      `)}

      ${renderSection('projects', 'Projects', 'Active projects and their context', 'sand', ICON.folder, `
        <div class="repeatable-list" id="projects-list" data-reorder-list="projects">
          ${u.projects.length ? u.projects.map((p, i) => renderProjectItem(p, i)).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">${ICON.folder}</div>
              <h3>No projects added yet</h3>
              <p>Add projects you're working on so the agent has context about your work.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-project-btn">${ICON.plus} Add project</button>
      `)}

      ${renderSection('user-custom', 'Custom Sections', 'Add your own sections', 'terracotta', ICON.plus, `
        <div class="custom-sections" id="user-custom-sections" data-reorder-list="user-custom">
          ${u.customSections.length ? u.customSections.map((s, i) => renderCustomSectionItem(s, i, 'user')).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">${ICON.penTool}</div>
              <h3>No custom sections</h3>
              <p>Add anything else the agent should know &mdash; health context, work environment, preferences, routines, or any other relevant information.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-user-custom-btn">${ICON.plus} Add custom section</button>
      `)}
    `;

    bindFormEvents(container);
    bindUserSpecificEvents(container);
    bindPresetEvents(container);
    bindSectionToggleEvents(container);
    bindSectionExpandEvents(container);
    bindReorderEvents(container);
    applySectionFadeIn(container);
  }

  // ---- Agent Form ----
  function renderAgentForm(container) {
    const a = state.agent;
    const autonomyLevel = Number.isFinite(a.autonomyLevel) ? Math.max(0, Math.min(100, a.autonomyLevel)) : 50;
    container.innerHTML = `
      ${renderPresetBar()}

      ${renderSection('agent-name', 'Identity', 'Basic details for context', 'sage', ICON.settings, `
        <div class="form-row">
          <div class="form-group">
            <label>Name</label>
            <input type="text" data-bind="agent.name" value="${esc(a.name)}" placeholder="e.g. Claude, Aria, Helper">
          </div>
          <div class="form-group">
            <label>Model</label>
            <input type="text" data-bind="agent.model" value="${esc(a.model)}" placeholder="e.g. Claude Opus 4.6">
          </div>
        </div>
        <div class="form-group">
          <label>Role</label>
          <select id="agent-role-select">
            <option value="" ${!a.role ? 'selected' : ''}>Choose a role...</option>
            <option value="Coding partner" ${a.role === 'Coding partner' ? 'selected' : ''}>Coding partner</option>
            <option value="Companion" ${a.role === 'Companion' ? 'selected' : ''}>Companion</option>
            <option value="Creative collaborator" ${a.role === 'Creative collaborator' ? 'selected' : ''}>Creative collaborator</option>
            <option value="Research assistant" ${a.role === 'Research assistant' ? 'selected' : ''}>Research assistant</option>
            <option value="Writing partner" ${a.role === 'Writing partner' ? 'selected' : ''}>Writing partner</option>
            <option value="custom" ${(state._agentRoleCustom || (a.role && !['Coding partner','Companion','Creative collaborator','Research assistant','Writing partner'].includes(a.role))) ? 'selected' : ''}>Other...</option>
          </select>
          ${(state._agentRoleCustom || (a.role && !['','Coding partner','Companion','Creative collaborator','Research assistant','Writing partner'].includes(a.role))) ? `
            <input type="text" data-bind="agent.role" value="${esc(a.role)}" placeholder="Describe the role..." style="margin-top:8px;" id="agent-role-custom">
          ` : ''}
        </div>
      `)}

      ${renderSection('agent-about', 'About', 'What this agent is for and how it should show up', 'sage', ICON.edit, `
        <div class="form-group">
          <textarea data-bind="agent.about" rows="4" placeholder="Describe who this agent is, its role, personality, or purpose.">${esc(a.about)}</textarea>
        </div>
      `)}

      ${renderSection('communication', 'Tone & Format', 'Surface-level style for responses', 'sage', ICON.chat, `
        <div id="communication-switches">
          ${a.communicationOptions.map(k => {
            const isCustom = !isDefaultComm(k);
            return renderPreferenceRow('agent.communicationActive.' + k, getCommLabel(k), getCommDesc(k), !!a.communicationActive[k], isCustom ? k : null, 'comm');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-comm-btn" style="margin-top:12px;">${ICON.plus} Add custom preference</button>
      `)}

      ${renderSection('behaviors', 'Behaviors', 'Rules your agent follows', 'sage', ICON.check, `
        <div class="toggle-group" id="behavior-toggles">
          ${a.behaviorOptions.map(k => {
            const active = a.behaviorsActive[k];
            const isCustom = !isDefaultBehavior(k);
            return `
              <div class="toggle-item-wrap ${isCustom ? 'is-custom' : ''}">
                <button type="button" class="toggle-item ${active ? 'active' : ''}" data-behavior="${k}" aria-pressed="${active ? 'true' : 'false'}">
                  <span class="toggle-check">${active ? ICON.check : ''}</span>
                  ${getBehaviorLabel(k)}
                  ${isCustom ? '<span class="custom-badge">Custom</span>' : ''}
                </button>
                ${isCustom ? `<button type="button" class="toggle-remove" data-remove-behavior="${k}" title="Remove custom item">${ICON.x}</button>` : ''}
              </div>
            `;
          }).join('')}
          <button type="button" class="toggle-item custom-toggle" id="add-behavior-btn">${ICON.plus} Add custom behavior</button>
        </div>
      `)}

      ${renderSection('when-low', 'When User Is Low', 'How to respond when the user seems down', 'clay', ICON.heart, `
        <div id="when-low-switches">
          ${a.whenLowOptions.map(k => {
            const isCustom = !isDefaultWhenLow(k);
            return renderPreferenceRow('agent.whenLowActive.' + k, getWhenLowLabel(k), getWhenLowDesc(k), !!a.whenLowActive[k], isCustom ? k : null, 'whenlow');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-whenlow-btn" style="margin-top:12px;">${ICON.plus} Add custom preference</button>
      `)}

      ${renderSection('autonomy', 'Autonomy', 'How proactive the agent should be without explicit prompts', 'clay', ICON.compass, `
        <div class="slider-group">
          <div class="slider-header">
            <span class="slider-label">Proactivity</span>
            <span class="slider-value" id="autonomy-level-label">${getAutonomyDescription(autonomyLevel)} (${autonomyLevel}/100)</span>
          </div>
          <input type="range" min="0" max="100" value="${autonomyLevel}" id="autonomy-slider">
          <div class="slider-labels">
            <span>Ask before acting</span>
            <span>Act proactively</span>
          </div>
        </div>
      `)}

      ${renderSection('rules', 'Conditional Rules', 'If/then instructions for specific situations', 'sand', ICON.link, `
        <div class="value-pairs" id="rules-list">
          ${a.rules.length ? a.rules.map((rule, i) => `
            <div class="value-pair" data-rule-index="${i}">
              <input type="text" data-rule="${i}" data-field="when" value="${esc(rule.when || '')}" placeholder="When...">
              <span class="separator">&rarr;</span>
              <input type="text" data-rule="${i}" data-field="then" value="${esc(rule.then || '')}" placeholder="Then...">
              <button class="btn btn-icon btn-danger-ghost" data-remove-rule="${i}" title="Remove">${ICON.x}</button>
            </div>
          `).join('') : `
            <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:8px;">Add rules like &ldquo;When I share code &rarr; review first, rewrite only if asked.&rdquo;</p>
          `}
        </div>
        <button class="add-item-btn" id="add-rule-btn">${ICON.plus} Add rule</button>
      `)}

      ${renderSection('traits', 'Character Traits', 'How your agent\'s personality feels', 'terracotta', ICON.sliders, `
        <div id="trait-sliders">
          ${a.traitOptions.map(key => renderSlider(key, getTraitLabel(key), a.traits[key] ?? 50, getTraitEndpoints(key), !isDefaultTrait(key), key)).join('')}
        </div>
        <button class="add-item-btn" id="add-trait-btn" style="margin-top:12px;">${ICON.plus} Add custom trait</button>
      `)}

      ${renderSection('avoid', 'Avoid', 'Things the agent should not do', 'sand', ICON.ban, `
        <div class="tag-list" id="avoid-tags">
          ${a.avoid.length ? a.avoid.map((item, i) => `
            <span class="tag">${esc(item)}<button class="tag-remove" data-remove-avoid="${i}">${ICON.x}</button></span>
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

      ${renderSection('tech-style', 'Technical Style', 'How technical responses should be shaped', 'terracotta', ICON.code, `
        <div id="tech-style-switches">
          ${a.techStyleOptions.map(k => {
            const isCustom = !isDefaultTech(k);
            return renderPreferenceRow('agent.techStyleActive.' + k, getTechLabel(k), getTechDesc(k), !!a.techStyleActive[k], isCustom ? k : null, 'techstyle');
          }).join('')}
        </div>
        <button class="add-item-btn" id="add-techstyle-btn" style="margin-top:12px;">${ICON.plus} Add custom preference</button>
      `)}

      ${renderSection('agent-custom', 'Custom Sections', 'Add your own sections', 'sage', ICON.plus, `
        <div class="custom-sections" id="agent-custom-sections" data-reorder-list="agent-custom">
          ${a.customSections.length ? a.customSections.map((s, i) => renderCustomSectionItem(s, i, 'agent')).join('') : `
            <div class="empty-state">
              <div class="empty-state-icon">${ICON.penTool}</div>
              <h3>No custom sections</h3>
              <p>Add anything else you want the agent to know about itself &mdash; role context, special instructions, domain expertise, etc.</p>
            </div>
          `}
        </div>
        <button class="add-item-btn" id="add-agent-custom-btn">${ICON.plus} Add custom section</button>
      `)}
    `;

    bindFormEvents(container);
    bindAgentSpecificEvents(container);
    bindPresetEvents(container);
    bindSectionToggleEvents(container);
    bindSectionExpandEvents(container);
    bindReorderEvents(container);
    applySectionFadeIn(container);
  }

  // ---- Partial Renderers ----
  function renderPreferenceRow(bind, label, desc, checked, removeKey, removeType) {
    const isCustom = !!removeKey;
    const customDesc = desc || '';
    return `
      <div class="switch-row ${isCustom ? 'switch-row-custom' : ''}">
        <div class="switch-copy">
          <div class="switch-label-row">
            <div class="switch-label">${label}</div>
            ${isCustom ? '<span class="custom-badge">Custom</span>' : ''}
          </div>
          ${!isCustom && desc ? `<div class="switch-label-desc">${desc}</div>` : ''}
        </div>
        <div class="switch-controls">
          ${!isCustom ? `
            <label class="switch">
              <input type="checkbox" data-bind="${bind}" ${checked ? 'checked' : ''}>
              <span class="switch-track"></span>
            </label>
          ` : ''}
          ${isCustom ? `<button type="button" class="switch-remove-btn" data-remove-switchrow="${removeKey}" data-remove-type="${removeType}" title="Remove custom item">${ICON.x}</button>` : ''}
        </div>
      </div>
    `;
  }

  function renderSlider(key, label, value, endpoints, removable, traitKey) {
    const desc = getTraitDescription(key, value);
    return `
      <div class="slider-group ${removable ? 'slider-group-custom' : ''}">
        <div class="slider-header">
          <span class="slider-label-row">
            <span class="slider-label">${label}</span>
            ${removable ? '<span class="custom-badge">Custom</span>' : ''}
          </span>
          <span class="slider-controls">
            <span class="slider-value" id="slider-val-${key}">${desc}</span>
            ${removable ? `<button class="slider-remove-btn" data-remove-trait="${key}" title="Remove">${ICON.x}</button>` : ''}
          </span>
        </div>
        <input type="range" min="0" max="100" value="${value}" data-trait="${key}">
        <div class="slider-labels">
          <span>${esc(endpoints[0])}</span>
          <span>${esc(endpoints[1])}</span>
        </div>
        ${removable ? `
          <div class="custom-trait-endpoints">
            <input type="text" value="${esc(endpoints[0])}" data-trait-endpoint="${traitKey}" data-trait-endpoint-side="0" placeholder="Left endpoint">
            <input type="text" value="${esc(endpoints[1])}" data-trait-endpoint="${traitKey}" data-trait-endpoint-side="1" placeholder="Right endpoint">
          </div>
        ` : ''}
      </div>
    `;
  }

  function renderInterestItem(item, i) {
    return `
      <div class="repeatable-item reorder-item" draggable="true" data-reorder-group="interests" data-reorder-index="${i}" data-interest-index="${i}">
        <div class="repeatable-item-header">
          <div class="repeatable-item-title">
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">${ICON.grip}</span>
            <strong style="font-size:0.88rem;">${item.name || 'New interest'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-interest="${i}" title="Remove">${ICON.x}</button>
        </div>
        <div class="repeatable-item-fields">
          <div class="form-group">
            <label>Interest</label>
            <input type="text" data-interest="${i}" data-field="name" value="${esc(item.name)}" placeholder="e.g. Woodworking, AI/ML, Cooking">
          </div>
          <div class="form-group">
            <label>Context</label>
            <textarea data-interest="${i}" data-field="context" rows="2" placeholder="Level, focus areas, what Claude should know...">${esc(item.context)}</textarea>
          </div>
        </div>
      </div>
    `;
  }

  function renderPersonItem(p, i) {
    return `
      <div class="repeatable-item reorder-item" draggable="true" data-reorder-group="people" data-reorder-index="${i}" data-person-index="${i}">
        <div class="repeatable-item-header">
          <div class="repeatable-item-title">
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">${ICON.grip}</span>
            <strong style="font-size:0.88rem;">${p.name || 'New person'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-person="${i}" title="Remove">${ICON.x}</button>
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
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">${ICON.grip}</span>
            <strong style="font-size:0.88rem;">${p.name || 'New project'}</strong>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-project="${i}" title="Remove">${ICON.x}</button>
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
            <span class="drag-handle" title="Drag to reorder" aria-label="Drag to reorder">${ICON.grip}</span>
            <strong style="font-size:0.88rem;">${s.title || 'New section'}</strong>
            <span class="custom-badge">Custom</span>
          </div>
          <button class="btn btn-icon btn-danger-ghost btn-small" data-remove-custom="${i}" data-custom-type="${type}" title="Remove">${ICON.x}</button>
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
      if (el.type === 'checkbox' || el.tagName === 'SELECT') {
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

  function bindSectionExpandEvents(container) {
    bindAll(container, '[data-section-expand]', 'click', (_event, btn) => {
      const sectionRef = btn.dataset.sectionExpand;
      if (sectionRef) window.memorableApp.toggleSection(sectionRef);
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
    USER_SECTION_IDS.forEach(id => {
      state.enabledSections[id] = preset.userSections.includes(id);
    });

    // For agent sections
    AGENT_SECTION_IDS.forEach(id => {
      state.enabledSections[id] = preset.agentSections.includes(id);
    });
  }

  function bindUserSpecificEvents(container) {
    // Language → dialect conditional display + "Other..." handling
    const langSelect = document.getElementById('identity-language');
    if (langSelect) {
      langSelect.addEventListener('change', () => {
        const customGroup = document.getElementById('identity-language-custom-group');
        const customInput = document.getElementById('identity-language-custom');
        if (langSelect.value === '_other') {
          state.user.identity.language = '';
          if (customGroup) customGroup.style.display = '';
          if (customInput) {
            customInput.value = '';
            customInput.focus();
          }
          renderPreview();
          debouncedSave();
          return;
        }
        if (customGroup) customGroup.style.display = 'none';
        state.user.identity.language = langSelect.value;
        const dialectGroup = document.getElementById('dialect-group');
        if (dialectGroup) {
          dialectGroup.style.display = langSelect.value === 'English' ? '' : 'none';
        }
        if (langSelect.value !== 'English') {
          state.user.identity.dialect = '';
        }
        renderPreview();
        debouncedSave();
      });
    }
    const customLangInput = document.getElementById('identity-language-custom');
    if (customLangInput) {
      customLangInput.addEventListener('input', () => {
        state.user.identity.language = customLangInput.value.trim();
        renderPreview();
        debouncedSave();
      });
    }

    // Cognitive toggles
    container.querySelectorAll('[data-cognitive]').forEach(el => {
      el.addEventListener('click', () => {
        const key = el.dataset.cognitive;
        state.user.cognitiveActive[key] = !state.user.cognitiveActive[key];
        el.classList.toggle('active');
        el.setAttribute('aria-pressed', state.user.cognitiveActive[key] ? 'true' : 'false');
        el.querySelector('.toggle-check').innerHTML = state.user.cognitiveActive[key] ? ICON.check : '';
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

    // Cognitive Style spectrum pills
    container.querySelectorAll('.spectrum-pills').forEach(group => {
      group.querySelectorAll('.spectrum-pill').forEach(pill => {
        pill.addEventListener('click', () => {
          const dimKey = group.dataset.cogstyle;
          const val = pill.dataset.val;
          state.user.cognitiveStyle[dimKey] = val;
          group.querySelectorAll('.spectrum-pill').forEach(p => p.classList.remove('active'));
          pill.classList.add('active');
          renderPreview();
          debouncedSave();
        });
      });
    });

    // Remove custom cognitive style dim
    container.querySelectorAll('[data-remove-cogstyle]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeCogstyle;
        state.user.cognitiveStyleDims = (state.user.cognitiveStyleDims || []).filter(d => d.key !== key);
        delete state.user.cognitiveStyle[key];
        render();
      });
    });

    // Add custom cognitive style dim
    const addCogStyleBtn = document.getElementById('add-cogstyle-btn');
    if (addCogStyleBtn) {
      addCogStyleBtn.addEventListener('click', () => {
        showTripleAdd(addCogStyleBtn, (label, left, right) => {
          const key = labelToKey(label);
          if (!state.user.cognitiveStyleDims) state.user.cognitiveStyleDims = [];
          if (!state.user.cognitiveStyleDims.some(d => d.key === key) && !DEFAULT_COGNITIVE_STYLE_DIMS.some(d => d.key === key)) {
            state.user.cognitiveStyleDims.push({ key, label, left, right });
            state.user.cognitiveStyle[key] = 'balanced';
          }
          render();
        });
      });
    }

    // Interests
    container.querySelectorAll('[data-interest]').forEach(el => {
      const handler = () => {
        const idx = parseInt(el.dataset.interest, 10);
        const field = el.dataset.field;
        state.user.interests[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      };
      el.addEventListener('input', handler);
    });

    container.querySelectorAll('[data-remove-interest]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeInterest, 10);
        state.user.interests.splice(idx, 1);
        render();
      });
    });

    const addInterestBtn = document.getElementById('add-interest-btn');
    if (addInterestBtn) {
      addInterestBtn.addEventListener('click', () => {
        state.user.interests.push({ name: '', context: '' });
        render();
      });
    }

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
    // Role select — handle "Other" showing free text field
    const roleSelect = document.getElementById('agent-role-select');
    if (roleSelect) {
      roleSelect.addEventListener('change', () => {
        const val = roleSelect.value;
        if (val === 'custom') {
          state._agentRoleCustom = true;
          state.agent.role = '';
          render();
          setTimeout(() => {
            const customInput = document.getElementById('agent-role-custom');
            if (customInput) customInput.focus();
          }, 50);
        } else {
          state._agentRoleCustom = false;
          state.agent.role = val;
          render();
        }
      });
    }

    // Communication preferences
    const addCommBtn = document.getElementById('add-comm-btn');
    if (addCommBtn) {
      addCommBtn.addEventListener('click', () => {
        showInlineAdd(addCommBtn, (label) => {
          const key = labelToKey(label);
          if (!state.agent.communicationOptions.includes(key)) {
            state.agent.communicationOptions.push(key);
            state.agent.communicationLabels[key] = label;
            state.agent.communicationDescs[key] = '';
            state.agent.communicationActive[key] = true;
          }
          render();
        });
      });
    }

    container.querySelectorAll('[data-remove-switchrow][data-remove-type="comm"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.removeSwitchrow;
        state.agent.communicationOptions = state.agent.communicationOptions.filter(k => k !== key);
        delete state.agent.communicationActive[key];
        delete state.agent.communicationLabels[key];
        delete state.agent.communicationDescs[key];
        render();
      });
    });
    container.querySelectorAll('[data-custom-desc-type="comm"]').forEach((el) => {
      el.addEventListener('input', () => {
        const key = el.dataset.customDescKey;
        state.agent.communicationDescs[key] = el.value;
        debouncedSave();
      });
    });

    // Behavior toggles
    container.querySelectorAll('[data-behavior]').forEach(el => {
      el.addEventListener('click', () => {
        const key = el.dataset.behavior;
        state.agent.behaviorsActive[key] = !state.agent.behaviorsActive[key];
        el.classList.toggle('active');
        el.setAttribute('aria-pressed', state.agent.behaviorsActive[key] ? 'true' : 'false');
        el.querySelector('.toggle-check').innerHTML = state.agent.behaviorsActive[key] ? ICON.check : '';
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

    // Autonomy slider
    const autonomySlider = document.getElementById('autonomy-slider');
    if (autonomySlider) {
      autonomySlider.addEventListener('input', () => {
        const raw = parseInt(autonomySlider.value, 10);
        const val = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 50;
        state.agent.autonomyLevel = val;
        const label = document.getElementById('autonomy-level-label');
        if (label) label.textContent = `${getAutonomyDescription(val)} (${val}/100)`;
        renderPreview();
        debouncedSave();
      });
    }

    // Conditional rules
    container.querySelectorAll('[data-rule]').forEach(el => {
      el.addEventListener('input', () => {
        const idx = parseInt(el.dataset.rule, 10);
        const field = el.dataset.field;
        if (!state.agent.rules[idx]) state.agent.rules[idx] = { when: '', then: '' };
        state.agent.rules[idx][field] = el.value;
        renderPreview();
        debouncedSave();
      });
    });

    container.querySelectorAll('[data-remove-rule]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.removeRule, 10);
        state.agent.rules.splice(idx, 1);
        render();
      });
    });

    const addRuleBtn = document.getElementById('add-rule-btn');
    if (addRuleBtn) {
      addRuleBtn.addEventListener('click', () => {
        state.agent.rules.push({ when: '', then: '' });
        render();
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
    container.querySelectorAll('[data-trait-endpoint]').forEach((el) => {
      el.addEventListener('input', () => {
        const key = el.dataset.traitEndpoint;
        const side = parseInt(el.dataset.traitEndpointSide, 10);
        if (!state.agent.traitEndpoints[key]) state.agent.traitEndpoints[key] = ['Low', 'High'];
        state.agent.traitEndpoints[key][side] = el.value.trim() || (side === 0 ? 'Low' : 'High');
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
    container.querySelectorAll('[data-custom-desc-type="whenlow"]').forEach((el) => {
      el.addEventListener('input', () => {
        const key = el.dataset.customDescKey;
        state.agent.whenLowDescs[key] = el.value;
        debouncedSave();
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
    container.querySelectorAll('[data-custom-desc-type="techstyle"]').forEach((el) => {
      el.addEventListener('input', () => {
        const key = el.dataset.customDescKey;
        state.agent.techStyleDescs[key] = el.value;
        debouncedSave();
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
    if (group === 'interests') return state.user.interests;
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
      <button class="inline-add-confirm" title="Add">${ICON.check}</button>
      <button class="inline-add-cancel" title="Cancel">${ICON.x}</button>
      <div class="inline-add-error" role="alert" aria-live="polite"></div>
    `;

    targetEl.parentNode.insertBefore(form, targetEl);

    const input = form.querySelector('input');
    const error = form.querySelector('.inline-add-error');
    input.focus();

    function setError(message) {
      if (!error) return;
      error.textContent = message || '';
      form.classList.toggle('invalid', !!message);
    }

    function confirm() {
      const val = input.value.trim();
      if (val) {
        setError('');
        onConfirm(val);
      } else {
        setError('Enter a name before adding.');
        input.focus();
      }
    }

    function cancel() {
      form.remove();
    }

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); confirm(); }
      if (e.key === 'Escape') { cancel(); }
    });
    input.addEventListener('input', () => setError(''));

    form.querySelector('.inline-add-confirm').addEventListener('click', confirm);
    form.querySelector('.inline-add-cancel').addEventListener('click', cancel);
  }

  function showTripleAdd(targetEl, onConfirm) {
    const existing = targetEl.parentNode.querySelector('.inline-add-form');
    if (existing) {
      existing.querySelector('input').focus();
      return;
    }

    const form = document.createElement('div');
    form.className = 'inline-add-form triple-add-form';
    form.innerHTML = `
      <input type="text" placeholder="Dimension name..." autofocus>
      <input type="text" placeholder="Left endpoint...">
      <input type="text" placeholder="Right endpoint...">
      <button class="inline-add-confirm" title="Add">${ICON.check}</button>
      <button class="inline-add-cancel" title="Cancel">${ICON.x}</button>
      <div class="inline-add-error" role="alert" aria-live="polite"></div>
    `;

    targetEl.parentNode.insertBefore(form, targetEl);

    const inputs = form.querySelectorAll('input');
    const error = form.querySelector('.inline-add-error');
    inputs[0].focus();

    function setError(message) {
      if (!error) return;
      error.textContent = message || '';
      form.classList.toggle('invalid', !!message);
    }

    function confirm() {
      const label = inputs[0].value.trim();
      const left = inputs[1].value.trim();
      const right = inputs[2].value.trim();
      if (label && left && right) {
        setError('');
        onConfirm(label, left, right);
      } else {
        setError('Fill all three fields before adding.');
      }
    }

    function cancel() {
      form.remove();
    }

    inputs.forEach((input, i) => {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (i < inputs.length - 1) {
            inputs[i + 1].focus();
          } else {
            confirm();
          }
        }
        if (e.key === 'Escape') { cancel(); }
      });
      input.addEventListener('input', () => setError(''));
    });

    form.querySelector('.inline-add-confirm').addEventListener('click', confirm);
    form.querySelector('.inline-add-cancel').addEventListener('click', cancel);
  }

  // ---- Import Modal ----
  function showImportModal(triggerEl) {
    const modalContainer = document.getElementById('modal-container');
    const returnFocusEl = triggerEl || document.activeElement;
    const fileType = state.activeFile;
    modalContainer.innerHTML = `
      <div class="modal-overlay" id="import-overlay">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="import-modal-title">
          <div class="modal-header">
            <h3 id="import-modal-title">Import ${fileType}.md</h3>
            <button type="button" class="btn btn-icon btn-ghost" id="import-close-btn" title="Close" aria-label="Close import modal">${ICON.x}</button>
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
              <button type="button" class="file-drop-zone" id="file-drop-zone">
                <span class="file-drop-zone-icon">${ICON.upload}</span>
                <span class="file-drop-zone-text">Drop a .md file here, or click to browse</span>
              </button>
              <input type="file" id="import-file-input" accept=".md,.txt,.markdown">
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
    const modalEl = modalContainer.querySelector('.modal');

    function getFocusableModalElements() {
      return Array.from(modalEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
        .filter((el) => !el.disabled && el.offsetParent !== null);
    }

    function onModalKeydown(event) {
      if (event.key !== 'Tab') return;
      const focusable = getFocusableModalElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
        return;
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

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
    const closeModal = () => {
      modalContainer.removeEventListener('keydown', onModalKeydown);
      modalContainer.innerHTML = '';
      if (returnFocusEl && typeof returnFocusEl.focus === 'function') returnFocusEl.focus();
    };
    document.getElementById('import-close-btn').addEventListener('click', closeModal);
    document.getElementById('import-cancel-btn').addEventListener('click', closeModal);
    document.getElementById('import-overlay').addEventListener('click', (e) => {
      if (e.target.id === 'import-overlay') closeModal();
    });
    modalContainer.addEventListener('keydown', onModalKeydown);
    pasteArea.focus();

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

      if (h3) { htmlLines.push(`<h3 data-preview-section="${slugify(h3[1])}">${inlineFmt(h3[1])}<span class="preview-anchor" title="Jump to form section">${ICON.link}</span></h3>`); }
      else if (h2) { htmlLines.push(`<h2 data-preview-section="${slugify(h2[1])}">${inlineFmt(h2[1])}<span class="preview-anchor" title="Jump to form section">${ICON.link}</span></h2>`); }
      else if (h1) { htmlLines.push(`<h1 data-preview-section="${slugify(h1[1])}">${inlineFmt(h1[1])}</h1>`); }
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
    const dedupe = (items) => {
      const out = [];
      const seen = new Set();
      (items || []).forEach((item) => {
        if (!item || seen.has(item)) return;
        seen.add(item);
        out.push(item);
      });
      return out;
    };
    const withDefaults = (defaults, items) => {
      const custom = (items || []).filter(k => !defaults.includes(k));
      return dedupe(defaults.concat(custom));
    };

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

    // Migrate old communication (flat booleans)
    if (u.communication && typeof u.communication === 'object' && !u.communicationOptions) {
      if (!a.communicationOptions) a.communicationOptions = DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key);
      if (!a.communicationLabels) a.communicationLabels = {};
      if (!a.communicationDescs) a.communicationDescs = {};
      if (!a.communicationActive) a.communicationActive = {};
      Object.entries(u.communication).forEach(([k, v]) => {
        if (v) a.communicationActive[k] = true;
        if (!a.communicationOptions.includes(k)) a.communicationOptions.push(k);
      });
      delete u.communication;
    }

    // Migrate communication from user to agent (new format)
    if (u.communicationOptions && !a.communicationOptions) {
      a.communicationOptions = u.communicationOptions;
      a.communicationLabels = u.communicationLabels || {};
      a.communicationDescs = u.communicationDescs || {};
      a.communicationActive = u.communicationActive || {};
      delete u.communicationOptions;
      delete u.communicationLabels;
      delete u.communicationDescs;
      delete u.communicationActive;
    }

    // Ensure new user fields exist
    if (!u.cognitiveStyle) u.cognitiveStyle = {};
    if (!Array.isArray(u.cognitiveStyleDims)) u.cognitiveStyleDims = [];
    if (!Array.isArray(u.interests)) u.interests = [];

    // Ensure agent about exists
    if (typeof a.about !== 'string') a.about = '';

    // Ensure agent communication exists
    if (!a.communicationOptions) a.communicationOptions = DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key);
    if (!a.communicationLabels) a.communicationLabels = {};
    if (!a.communicationDescs) a.communicationDescs = {};
    if (!a.communicationActive) a.communicationActive = {};
    if (!Array.isArray(a.behaviorOptions)) a.behaviorOptions = [];
    if (!a.behaviorLabels) a.behaviorLabels = {};
    if (!a.behaviorsActive) a.behaviorsActive = {};
    if (!Array.isArray(a.whenLowOptions)) a.whenLowOptions = [];
    if (!a.whenLowLabels) a.whenLowLabels = {};
    if (!a.whenLowDescs) a.whenLowDescs = {};
    if (!a.whenLowActive) a.whenLowActive = {};
    if (!Array.isArray(a.traitOptions)) a.traitOptions = [];
    if (!a.traitLabels) a.traitLabels = {};
    if (!a.traitEndpoints) a.traitEndpoints = {};
    if (!a.traits || typeof a.traits !== 'object') a.traits = {};
    if (!Array.isArray(a.rules)) a.rules = [];

    // Legacy communication keys moved into disposition / when-low.
    const commToBehavior = {
      challengeMe: 'challengeWhenWrong',
      admitUncertainty: 'admitUncertainty',
      matchEnergy: 'calibrateTone'
    };
    const commToWhenLow = {
      shortWhenLow: 'shorterReplies'
    };
    Object.entries(commToBehavior).forEach(([oldKey, newKey]) => {
      if (a.communicationActive[oldKey]) a.behaviorsActive[newKey] = true;
      a.communicationOptions = a.communicationOptions.filter(k => k !== oldKey);
      delete a.communicationActive[oldKey];
      delete a.communicationLabels[oldKey];
      delete a.communicationDescs[oldKey];
      if (!a.behaviorOptions.includes(newKey)) a.behaviorOptions.push(newKey);
    });
    Object.entries(commToWhenLow).forEach(([oldKey, newKey]) => {
      if (a.communicationActive[oldKey]) a.whenLowActive[newKey] = true;
      a.communicationOptions = a.communicationOptions.filter(k => k !== oldKey);
      delete a.communicationActive[oldKey];
      delete a.communicationLabels[oldKey];
      delete a.communicationDescs[oldKey];
      if (!a.whenLowOptions.includes(newKey)) a.whenLowOptions.push(newKey);
    });

    // Migrate old agent behaviors
    if (a.behaviors && typeof a.behaviors === 'object' && (!Array.isArray(a.behaviorOptions) || a.behaviorOptions.length === 0)) {
      a.behaviorOptions = DEFAULT_BEHAVIOR_OPTIONS.map(o => o.key);
      a.behaviorLabels = {};
      a.behaviorsActive = {};
      Object.entries(a.behaviors).forEach(([k, v]) => {
        if (v) a.behaviorsActive[k] = true;
        if (!a.behaviorOptions.includes(k)) a.behaviorOptions.push(k);
      });
      delete a.behaviors;
    }

    // Rename old behavior keys to new behavior keys.
    const behaviorRenames = {
      uncertainWhenAppropriate: 'admitUncertainty',
      adaptToMood: 'calibrateTone',
      matchEnergy: 'calibrateTone',
      challengeMe: 'challengeWhenWrong'
    };
    Object.entries(behaviorRenames).forEach(([oldKey, newKey]) => {
      if (a.behaviorsActive[oldKey]) a.behaviorsActive[newKey] = true;
      a.behaviorOptions = a.behaviorOptions.map(k => (k === oldKey ? newKey : k));
      delete a.behaviorsActive[oldKey];
      delete a.behaviorLabels[oldKey];
    });

    // Drop old vague defaults that don't produce reliable behavior steering.
    const retiredBehaviorKeys = new Set([
      'rememberContext',
      'useSharedVocabulary',
      'showWorkingProcess',
      'provideSources'
    ]);
    a.behaviorOptions = a.behaviorOptions.filter(k => !retiredBehaviorKeys.has(k));
    retiredBehaviorKeys.forEach((key) => {
      delete a.behaviorsActive[key];
      delete a.behaviorLabels[key];
    });

    // Migrate old whenLow
    if (a.whenLow && typeof a.whenLow === 'object' && (!Array.isArray(a.whenLowOptions) || a.whenLowOptions.length === 0)) {
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
    if (a.traits && (!Array.isArray(a.traitOptions) || a.traitOptions.length === 0)) {
      a.traitOptions = DEFAULT_TRAIT_OPTIONS.map(o => o.key);
      a.traitLabels = {};
      a.traitEndpoints = {};
      // Keep traits values as they are, just ensure custom ones are tracked
      Object.keys(a.traits).forEach(k => {
        if (!a.traitOptions.includes(k)) a.traitOptions.push(k);
      });
    }

    const commDefaultKeys = DEFAULT_COMMUNICATION_OPTIONS.map(o => o.key);
    const behaviorDefaultKeys = DEFAULT_BEHAVIOR_OPTIONS.map(o => o.key);
    const whenLowDefaultKeys = DEFAULT_WHEN_LOW_OPTIONS.map(o => o.key);
    const traitDefaultKeys = DEFAULT_TRAIT_OPTIONS.map(o => o.key);
    a.communicationOptions = withDefaults(commDefaultKeys, a.communicationOptions);
    a.behaviorOptions = withDefaults(behaviorDefaultKeys, a.behaviorOptions);
    a.whenLowOptions = withDefaults(whenLowDefaultKeys, a.whenLowOptions);
    a.traitOptions = withDefaults(traitDefaultKeys, a.traitOptions);
    traitDefaultKeys.forEach((key) => {
      if (a.traits[key] === undefined) a.traits[key] = 50;
    });
    a.rules = a.rules.map((rule) => ({
      when: String((rule && rule.when) || ''),
      then: String((rule && rule.then) || '')
    }));
    const autonomyRaw = parseInt(a.autonomyLevel, 10);
    a.autonomyLevel = Number.isFinite(autonomyRaw) ? Math.max(0, Math.min(100, autonomyRaw)) : 50;

    // Ensure enabledSections exists
    if (!state.enabledSections) {
      state.enabledSections = {};
    }
    // Keep section collapse state stable; default-collapse advanced sections on first run.
    if (!state.collapsedSections || typeof state.collapsedSections !== 'object') {
      state.collapsedSections = {};
    }
    const allSections = USER_SECTION_IDS.concat(AGENT_SECTION_IDS);
    allSections.forEach(id => {
      if (state.enabledSections[id] === undefined) state.enabledSections[id] = true;
      if (state.collapsedSections[id] === undefined) state.collapsedSections[id] = !!DEFAULT_COLLAPSED_SECTIONS[id];
    });
    // Ensure preset exists
    if (!state.preset) state.preset = 'custom';

    // Ensure new state properties
    if (!state.activePage) state.activePage = 'dashboard';
    if (!Array.isArray(state.notesCache)) state.notesCache = [];
    if (state.settingsCache === undefined) state.settingsCache = null;
    if (state.statusCache === undefined) state.statusCache = null;
    if (state.serverConnected === undefined) state.serverConnected = false;
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
        const collapsed = el.classList.contains('collapsed');
        state.collapsedSections[sectionId] = collapsed;
        el.querySelectorAll('[data-section-expand]').forEach((btn) => {
          btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        });
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
      showImportModal(document.activeElement);
    },

    retrySave() {
      setSaveState('saving');
      saveToLocalStorage();
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

    navigateTo(page) {
      state.activePage = page;
      syncNavHighlight();
      render();
    },

    setMemoriesSubTab(tab) {
      state.memoriesSubTab = tab;
      render();
    },

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
        const closeBtn = document.getElementById('import-close-btn');
        if (closeBtn) {
          closeBtn.click();
          return;
        }
      }
    });

    // Active editing accent + connective preview on field focus
    document.addEventListener('focusin', (e) => {
      const section = e.target.closest('.section');
      if (section && (e.target.matches('input, textarea, select'))) {
        document.querySelectorAll('.section.section-editing').forEach(s => s.classList.remove('section-editing'));
        section.classList.add('section-editing');
        // Connective preview: scroll preview to matching section
        const sectionId = section.id.replace('section-', '');
        scrollPreviewToSection(sectionId);
      }
    });
    document.addEventListener('focusout', (e) => {
      const section = e.target.closest('.section');
      if (section) {
        setTimeout(() => {
          if (!section.contains(document.activeElement)) {
            section.classList.remove('section-editing');
          }
        }, 50);
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
