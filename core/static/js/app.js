(() => {
  'use strict';

  const root = document.documentElement;
  const language = (root.lang || 'en').slice(0, 2);
  const copy = language === 'ny' ? {
    theme: 'Maonekedwe', waiting: 'Chonde dikirani…', submitting: 'Pempho lanu likutumizidwa.',
    selected: 'zasankhidwa', ready: 'Takonzeka', connecting: 'Ikulumikizana', waitingReply: 'Yembekezani yankho',
    ended: 'Gawo latha', error: 'Vuto', connectionError: 'Takanika kulumikizana ndi USSD. Onani netiweki ndipo yesaninso.',
    dialAgain: 'Imbaninso', connected: 'Yalumikizidwa', tryAgain: 'Yesaninso', enterReply: 'Lowetsani yankho musanatumize.',
    noResponse: 'Palibe yankho.',
  } : {
    theme: 'Colour theme', waiting: 'Please wait…', submitting: 'Submitting your request.',
    selected: 'selected', ready: 'Ready', connecting: 'Connecting', waitingReply: 'Waiting for reply',
    ended: 'Session ended', error: 'Error', connectionError: 'Could not reach the USSD endpoint. Check the connection and try again.',
    dialAgain: 'Dial again', connected: 'Connected', tryAgain: 'Try again', enterReply: 'Enter a reply before sending.',
    noResponse: 'No response.',
  };
  const themeKey = 'pastns-theme';
  const applyTheme = (value) => {
    root.classList.remove('theme-light', 'theme-dark');
    if (value === 'light') root.classList.add('theme-light');
    if (value === 'dark') root.classList.add('theme-dark');
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-pressed', value !== 'system' ? 'true' : 'false');
      button.title = `${copy.theme}: ${value}. Click to change.`;
      const sr = button.querySelector('.visually-hidden');
      if (sr) sr.textContent = `${copy.theme}: ${value}. Click to change.`;
    });
  };
  let theme = localStorage.getItem(themeKey) || 'system';
  applyTheme(theme);
  document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      theme = theme === 'system' ? 'dark' : theme === 'dark' ? 'light' : 'system';
      localStorage.setItem(themeKey, theme);
      applyTheme(theme);
    });
  });

  document.querySelectorAll('[data-progress-form]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.classList.add('is-loading');
        button.disabled = true;
        const label = button.querySelector('.button-label');
        if (label) label.textContent = copy.waiting;
      }
      const live = document.querySelector('[data-live-region]');
      if (live) live.textContent = copy.submitting;
    });
  });
  const errorSummary = document.querySelector('[data-error-summary]');
  if (errorSummary) errorSummary.focus({ preventScroll: true });

  document.querySelectorAll('[data-bulk-form]').forEach((form) => {
    const boxes = Array.from(form.querySelectorAll('input[name="selected"]'));
    const selectAll = form.querySelector('[data-select-all]');
    const count = form.querySelector('[data-selected-count]');
    const buttons = Array.from(form.querySelectorAll('button[name="action"]'));
    const update = () => {
      const selected = boxes.filter((box) => box.checked).length;
      if (count) count.textContent = `${selected} ${copy.selected}`;
      if (selectAll) {
        selectAll.checked = boxes.length > 0 && selected === boxes.length;
        selectAll.indeterminate = selected > 0 && selected < boxes.length;
      }
      buttons.forEach((button) => { button.disabled = selected === 0; });
    };
    if (selectAll) selectAll.addEventListener('change', () => {
      boxes.forEach((box) => { box.checked = selectAll.checked; });
      update();
    });
    boxes.forEach((box) => box.addEventListener('change', update));
    form.addEventListener('submit', (event) => {
      const submitter = event.submitter;
      if (submitter && submitter.value !== 'export' && boxes.filter((box) => box.checked).length === 0) event.preventDefault();
    });
    update();
  });

  const menuToggle = document.querySelector('[data-menu-toggle]');
  const sidebar = document.querySelector('.officer-sidebar');
  if (menuToggle && sidebar) {
    menuToggle.addEventListener('click', () => {
      const opened = sidebar.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(opened));
    });
    document.addEventListener('click', (event) => {
      if (window.innerWidth <= 680 && sidebar.classList.contains('is-open') && !sidebar.contains(event.target) && !menuToggle.contains(event.target)) {
        sidebar.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  const gsmBasic = "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\u001bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
  const gsmExtended = '^{}\\\\[~]|€';
  const isGsm = (value) => Array.from(value).every((character) => gsmBasic.includes(character) || gsmExtended.includes(character));
  const gsmLength = (value) => Array.from(value).reduce((total, character) => total + (gsmExtended.includes(character) ? 2 : 1), 0);
  const renderSample = (value) => value.replaceAll('{code}', 'MW-MGC-2026-00042').replaceAll('{office}', 'Mangochi').replaceAll('{url}', 'pastns.gov.mw').replaceAll('{hours}', 'Mon–Fri 8–16');
  document.querySelectorAll('[data-sms-editor]').forEach((editor) => {
    const en = editor.querySelector('[data-template-en]');
    const ny = editor.querySelector('[data-template-ny]');
    const countEn = editor.querySelector('[data-count-en]');
    const countNy = editor.querySelector('[data-count-ny]');
    const previewEn = editor.querySelector('[data-preview-en]');
    const previewNy = editor.querySelector('[data-preview-ny]');
    const updateCounter = (field, label, preview, isChichewa) => {
      if (!field) return;
      const sample = renderSample(field.value);
      const unicode = !isGsm(sample);
      const max = unicode ? 70 : 160;
      const length = unicode ? Array.from(sample).length : gsmLength(sample);
      if (label) {
        label.textContent = `${length} / ${max} ${unicode ? 'characters (Unicode SMS)' : 'GSM characters'}`;
        label.classList.toggle('is-over', length > max);
      }
      if (preview) preview.textContent = sample;
    };
    const update = () => {
      updateCounter(en, countEn, previewEn, false);
      updateCounter(ny, countNy, previewNy, true);
    };
    [en, ny].forEach((field) => field && field.addEventListener('input', update));
    update();
  });

  const output = document.querySelector('[data-ussd-output]');
  if (output) {
    const startButton = document.querySelector('[data-ussd-start]');
    const sendButton = document.querySelector('[data-ussd-send]');
    const resetButton = document.querySelector('[data-ussd-reset]');
    const input = document.querySelector('[data-ussd-input]');
    const phone = document.querySelector('[data-ussd-phone]');
    const keypad = Array.from(document.querySelectorAll('[data-key]'));
    const sessionState = document.querySelector('[data-session-state]');
    let sessionId = '';
    let parts = [];
    let ended = true;
    const createSessionId = () => `pastns-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const setInteractive = (enabled) => {
      if (input) input.disabled = !enabled;
      if (sendButton) sendButton.disabled = !enabled;
      keypad.forEach((key) => { key.disabled = !enabled; });
    };
    const appendKey = (value) => {
      if (!input || input.disabled) return;
      const begin = input.selectionStart == null ? input.value.length : input.selectionStart;
      const end = input.selectionEnd == null ? input.value.length : input.selectionEnd;
      input.value = input.value.slice(0, begin) + value + input.value.slice(end);
      input.setSelectionRange(begin + value.length, begin + value.length);
      input.focus();
    };
    keypad.forEach((key) => key.addEventListener('click', () => appendKey(key.dataset.key)));
    const callEndpoint = async (text, initial = false) => {
      if (!sessionId || initial) sessionId = createSessionId();
      if (sessionState) sessionState.textContent = copy.connecting;
      if (startButton) startButton.disabled = true;
      try {
        const payload = new URLSearchParams({
          sessionId,
          serviceCode: '*384*123#',
          phoneNumber: phone ? phone.value.trim() : '+265991234567',
          text,
        });
        const response = await fetch('/api/ussd/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          credentials: 'same-origin',
          body: payload.toString(),
        });
        const result = await response.text();
        const prefix = result.slice(0, 3);
        output.textContent = result.replace(/^(CON|END)\s?/, '') || copy.noResponse;
        output.dataset.prefix = prefix;
        const isOpen = response.ok && prefix === 'CON';
        ended = !isOpen;
        setInteractive(isOpen);
        if (sessionState) sessionState.textContent = isOpen ? copy.waitingReply : prefix === 'END' ? copy.ended : copy.error;
        if (startButton) {
          startButton.disabled = false;
          startButton.textContent = prefix === 'END' || !response.ok ? copy.dialAgain : copy.connected;
        }
        if (input) {
          input.value = '';
          if (isOpen) input.focus();
        }
      } catch (error) {
        output.textContent = copy.connectionError;
        if (sessionState) sessionState.textContent = copy.error;
        if (startButton) { startButton.disabled = false; startButton.textContent = copy.tryAgain; }
        setInteractive(false);
      }
    };
    if (startButton) startButton.addEventListener('click', () => {
      parts = [];
      sessionId = createSessionId();
      ended = false;
      callEndpoint('', true);
    });
    if (sendButton) sendButton.addEventListener('click', () => {
      if (!input || ended) return;
      const reply = input.value.trim();
      if (!reply) {
        output.textContent += `\n\n${copy.enterReply}`;
        input.focus();
        return;
      }
      parts.push(reply);
      callEndpoint(parts.join('*'));
    });
    if (input) input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); sendButton && sendButton.click(); }
    });
    if (resetButton) resetButton.addEventListener('click', () => {
      parts = [];
      sessionId = '';
      ended = true;
      output.textContent = language === 'ny' ? 'Dinani Yambani kuti mulumikizane ndi *384*123#' : 'Press Start to connect to *384*123#';
      output.dataset.prefix = '';
      if (sessionState) sessionState.textContent = copy.ready;
      if (input) input.value = '';
      if (startButton) { startButton.disabled = false; startButton.textContent = 'Start'; }
      setInteractive(false);
    });
  }
})();
