/* Account wake-ups: no automatic mutation retries; request IDs survive ambiguity. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const providers = {codex: 'Codex', antigravity: 'Antigravity', claude: 'Claude Code'};
  let state = null, selected = new Set(), mode = 'now', busy = false, refreshing = false;
  let providerChoices = {}, settingsSignature = '', editingSchedule = null;
  let pendingRequest = null, pendingDelete = null, scheduleSignature = '', historySignature = '', defaultsSignature = '';

  try { pendingRequest = JSON.parse(sessionStorage.getItem('cyd-wakeup-pending') || 'null'); } catch (_) {}
  const node = (tag, className, value) => { const n = document.createElement(tag); if (className) n.className = className; if (value !== undefined) n.textContent = value; return n; };
  const localTime = value => value ? new Intl.DateTimeFormat(undefined, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}).format(new Date(value)) : 'No upcoming send';
  const providerIcon = provider => {
    const img = document.createElement('img'); img.alt = ''; img.setAttribute('aria-hidden', 'true');
    if (Object.hasOwn(providers, provider)) img.src = `/static/providers/${provider}.svg`;
    return img;
  };
  const label = id => state?.accounts.find(a => a.id === id)?.label || id;
  const notify = (message, error = false) => { $('notice').hidden = false; $('notice').className = 'notice' + (error ? ' error' : ''); $('notice').textContent = message; };
  async function request(payload) {
    const response = await fetch('/api/admin/wakeups', payload ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CYD-CSRF': '1'}, body: JSON.stringify(payload), credentials: 'same-origin'} : {credentials: 'same-origin', cache: 'no-store'});
    const body = await response.json();
    if (!response.ok || body.error) {
      const error = new Error(body.error || 'The request could not be completed.');
      error.status = response.status;
      throw error;
    }
    return body;
  }
  function actions() {
    $('promptCount').textContent = `${$('wakeupPrompt').value.length} / 500`;
    const count = selected.size;
    $('selectedCount').textContent = count ? `${count} selected` : 'None selected';
    $('sendSelection').textContent = count ? `${count} account${count === 1 ? '' : 's'} · one prompt each` : 'Choose accounts and models to continue.';
    document.querySelectorAll('[data-mutation]').forEach(button => button.disabled = busy);
    renderProviderSettings();
    const ready = settingsReady() && Boolean($('wakeupPrompt').value.trim());
    $('sendNow').disabled = busy || !count || !ready || !state?.enabled || Boolean(state?.clock_error);
    $('saveSchedule').disabled = busy || !count || !ready;
    $('sendNow').textContent = !count ? 'Choose accounts to continue' : !ready ? 'Choose models to continue' : state?.clock_error ? 'Sending on safety hold' : !state?.enabled ? 'Enable wake-ups to send' : `Review ${count} account${count === 1 ? '' : 's'}`;
    $('saveSchedule').textContent = !count ? 'Choose accounts to continue' : !ready ? 'Choose models to continue' : `${editingSchedule ? 'Save changes' : 'Create schedule'} · ${count} account${count === 1 ? '' : 's'}`;
    $('masterToggle').disabled = busy || !state;
    $('selectAll').textContent = state?.accounts.filter(a => a.enabled).every(a => selected.has(a.id)) && count ? 'Clear selection' : 'Select all';
    preview();
  }
  function selectedProviders() { return [...new Set([...selected].map(id => state.accounts.find(a => a.id === id)?.provider).filter(Boolean))].sort(); }
  function capability(provider) { return state?.accounts.find(a => a.provider === provider)?.capability || {}; }
  function settingsReady() { return selectedProviders().every(provider => { const choice = providerChoices[provider]; const option = capability(provider).models?.find(model => model.id === choice?.model); return option?.reasoning_levels?.includes(choice?.reasoning); }); }
  function chosenSettings() { return Object.fromEntries(selectedProviders().map(provider => [provider, {...providerChoices[provider]}])); }
  function renderProviderSettings() {
    if (!state) return;
    const activeProviders = selectedProviders(); $('modelSettings').hidden = !activeProviders.length;
    const signature = JSON.stringify(activeProviders.map(provider => [provider, capability(provider).models, capability(provider).execution_note, state.defaults?.[provider]]));
    if (signature === settingsSignature) return;
    settingsSignature = signature;
    const host = $('providerSettings'); host.replaceChildren();
    for (const provider of activeProviders) {
      const cap = capability(provider), models = cap.models || [];
      const row = node('section', 'provider-settings-row'), heading = node('h3', '', providers[provider]); heading.prepend(providerIcon(provider)); row.append(heading);
      const fields = node('div', 'provider-settings-fields');
      const modelLabel = node('label', 'field', 'Model'); const modelSelect = document.createElement('select'); modelSelect.setAttribute('aria-label', `${providers[provider]} model`);
      modelSelect.append(new Option('Choose a model', ''));
      for (const model of models) modelSelect.append(new Option(model.label || model.id, model.id));
      modelSelect.disabled = !models.length;
      const reasoningLabel = node('label', 'field', 'Reasoning'); const reasoningSelect = document.createElement('select'); reasoningSelect.setAttribute('aria-label', `${providers[provider]} reasoning`);
      const saved = providerChoices[provider] || {model: '', reasoning: ''};
      if (models.some(model => model.id === saved.model)) modelSelect.value = saved.model;
      const fillReasoning = () => {
        const prior = providerChoices[provider]?.reasoning || ''; reasoningSelect.replaceChildren(new Option('Choose reasoning', ''));
        const option = models.find(model => model.id === modelSelect.value);
        for (const level of option?.reasoning_levels || []) reasoningSelect.append(new Option(level === 'none' ? 'None' : level === 'default' ? 'Provider default' : level.charAt(0).toUpperCase() + level.slice(1), level));
        reasoningSelect.disabled = !option;
        if (option?.reasoning_levels?.includes(prior)) reasoningSelect.value = prior;
        providerChoices[provider] = {model: modelSelect.value, reasoning: reasoningSelect.value};
      };
      fillReasoning();
      const defaultChoice = state.defaults?.[provider];
      const defaultNote = node('p', 'default-context');
      const updateDefaultNote = () => {
        const choice = providerChoices[provider];
        const matches = defaultChoice && choice.model === defaultChoice.model && choice.reasoning === defaultChoice.reasoning;
        defaultNote.textContent = matches ? 'Using your saved default. Changes here apply only to this run.' : defaultChoice ? 'Override for this run. Your saved default stays unchanged.' : 'No saved default. Set one in Defaults to skip this step next time.';
      };
      updateDefaultNote();
      if (defaultChoice && !models.some(model => model.id === defaultChoice.model && model.reasoning_levels.includes(defaultChoice.reasoning))) {
        row.append(node('p', 'account-status', 'Your saved default is no longer available. Choose an available model and update Defaults.'));
      }
      modelSelect.addEventListener('change', () => { providerChoices[provider] = {model: modelSelect.value, reasoning: ''}; fillReasoning(); updateDefaultNote(); actions(); });
      reasoningSelect.addEventListener('change', () => { providerChoices[provider] = {model: modelSelect.value, reasoning: reasoningSelect.value}; updateDefaultNote(); actions(); });
      modelLabel.append(modelSelect); reasoningLabel.append(reasoningSelect); fields.append(modelLabel, reasoningLabel); row.append(fields, defaultNote);
      if (cap.execution_note) { const note = node('details', 'provider-note'); note.append(node('summary', '', 'Sending limits'), node('p', '', cap.execution_note)); row.append(note); }
      if (!models.length) row.append(node('p', 'account-status', cap.reason || 'The model list is not available yet. Refresh after the collector connects.'));
      host.append(row);
    }
  }
  function renderDefaults(force = false) {
    if (!state || (!force && $('defaultsList').contains(document.activeElement))) return;
    const signature = JSON.stringify([state.defaults, Object.keys(providers).map(provider => [provider, capability(provider).models])]);
    if (signature === defaultsSignature) return;
    defaultsSignature = signature;
    const host = $('defaultsList'); host.replaceChildren();
    for (const [provider, title] of Object.entries(providers)) {
      const models = capability(provider).models || [], saved = state.defaults?.[provider];
      const row = node('form', 'default-card'); row.dataset.provider = provider;
      const heading = node('h3', '', title); heading.prepend(providerIcon(provider)); row.append(heading);
      const fields = node('div', 'provider-settings-fields');
      const modelLabel = node('label', 'field', 'Default model'), model = document.createElement('select'); model.setAttribute('aria-label', `${title} default model`);
      model.append(new Option('Choose a model', ''));
      for (const item of models) model.append(new Option(item.label || item.id, item.id));
      if (saved && !models.some(item => item.id === saved.model)) model.append(new Option(saved.model + ' · unavailable', saved.model));
      model.value = saved?.model || ''; model.disabled = !models.length;
      const effortLabel = node('label', 'field', 'Default reasoning'), effort = document.createElement('select'); effort.setAttribute('aria-label', `${title} default reasoning`);
      const controls = node('div', 'default-actions'), save = node('button', 'button primary', 'Save default'); save.type = 'submit';
      const clear = node('button', 'text-button', 'Remove default'); clear.type = 'button'; clear.hidden = !saved;
      clear.addEventListener('click', async () => { const result = await mutate({action:'clear_default', provider}, `${title} default removed.`); if (result) { defaultsSignature = ''; renderDefaults(true); } });
      const fillEfforts = prior => {
        const option = models.find(item => item.id === model.value); effort.replaceChildren(new Option('Choose reasoning', ''));
        for (const level of option?.reasoning_levels || []) effort.append(new Option(level === 'fixed' ? 'Provider fixed' : level.charAt(0).toUpperCase()+level.slice(1), level));
        if (prior && !option?.reasoning_levels?.includes(prior)) effort.append(new Option(prior + ' · unavailable', prior));
        effort.value = prior || ''; effort.disabled = !option;
      };
      const update = () => { const valid = models.some(item => item.id === model.value && item.reasoning_levels.includes(effort.value)); save.disabled = busy || !valid; clear.disabled = busy; };
      fillEfforts(saved?.reasoning); update();
      model.addEventListener('change', () => { fillEfforts(''); update(); }); effort.addEventListener('change', update);
      modelLabel.append(model); effortLabel.append(effort); fields.append(modelLabel, effortLabel); row.append(fields);
      if (saved && !models.some(item => item.id === saved.model && item.reasoning_levels.includes(saved.reasoning))) row.append(node('p', 'account-status', 'Saved selection unavailable. Update it before your next send.'));
      if (!models.length) row.append(node('p', 'help', 'Connect an account from this provider to load its models.'));
      controls.append(save, clear); row.append(controls);
      row.addEventListener('submit', async event => { event.preventDefault(); if (busy || save.disabled) return; save.disabled = true; clear.disabled = true; const result = await mutate({action:'save_defaults', provider_settings:{[provider]:{model:model.value,reasoning:effort.value}}}, `${title} default saved.`); if (result) { defaultsSignature = ''; renderDefaults(true); } else update(); });
      host.append(row);
    }
  }
  function renderAccounts() {
    const host = $('accountList'); host.replaceChildren();
    const accounts = state.accounts.filter(a => a.enabled);
    selected = new Set([...selected].filter(id => accounts.some(a => a.id === id)));
    const query = $('accountSearch').value.trim().toLocaleLowerCase();
    if (!accounts.length) { host.append(node('p', 'empty', 'No accounts yet. Add an account in Accounts to get started.')); return; }
    let shown = 0;
    for (const provider of Object.keys(providers)) {
      const matches = accounts.filter(account => account.provider === provider && `${account.label} ${providers[provider]}`.toLocaleLowerCase().includes(query));
      if (!matches.length) continue;
      const group = node('section', 'account-group'), title = node('h4', 'account-group-title', `${providers[provider]} · ${matches.length}`);
      title.prepend(providerIcon(provider)); group.append(title);
      const options = node('div', 'account-group-options');
      for (const account of matches) {
        const row = node('label', 'account-option');
        const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(account.id); check.value = account.id;
        check.addEventListener('change', () => { check.checked ? selected.add(account.id) : selected.delete(account.id); actions(); });
        const avatar = node('span', 'account-avatar ' + account.provider); avatar.setAttribute('aria-hidden', 'true'); avatar.append(providerIcon(account.provider));
        const detail = node('span', 'account-info'); detail.append(node('span', 'account-label', account.label), node('span', 'account-detail', providers[account.provider]));
        if (!account.capability.available) detail.append(node('span', 'account-status', account.capability.reason || 'Sending is unavailable.'));
        row.append(check, avatar, detail); options.append(row); shown++;
      }
      group.append(options); host.append(group);
    }
    if (!shown) host.append(node('p', 'empty', 'No accounts match your search.'));
  }
  async function mutate(payload, success) {
    if (busy) return;
    busy = true; actions();
    try { const result = await request(payload); notify(success); await refresh(); return result; }
    catch (error) { notify(error.message || 'Connection interrupted. Check activity before trying again.', true); }
    finally { busy = false; actions(); }
  }
  function renderSchedules() {
    const signature = JSON.stringify([state.schedules, state.enabled, state.accounts.map(a => [a.id, a.label]), $('scheduleFilter').value]);
    if (signature === scheduleSignature) return;
    scheduleSignature = signature;
    const host = $('scheduleList'); host.replaceChildren(); $('scheduleCount').textContent = state.schedules.length;
    const filter = $('scheduleFilter').value;
    const schedules = state.schedules.filter(schedule => filter === 'all' || (filter === 'active' ? schedule.enabled : !schedule.enabled));
    if (!schedules.length) {
      const empty = node('div', 'empty-state');
      const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); icon.classList.add('empty-icon'); icon.setAttribute('viewBox', '0 0 48 48'); icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = '<rect x="7" y="11" width="34" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 21h34M16 6v10M32 6v10M17 30h14M24 25v10" fill="none" stroke="currentColor" stroke-width="2"/>';
      empty.append(icon, node('h3', '', state.schedules.length ? 'No schedules in this view' : 'Set your first wake-up'), node('p', '', state.schedules.length ? 'Choose another filter to see your saved schedules.' : 'Pick your accounts and a time. We’ll send one short prompt to each eligible account.'));
      const create = node('button', 'button primary', state.schedules.length ? 'Show all schedules' : '＋ Create a schedule'); create.type = 'button';
      create.addEventListener('click', () => { if (state.schedules.length) { $('scheduleFilter').value = 'all'; renderSchedules(); } else beginEditor('schedule'); });
      empty.append(create); host.append(empty); return;
    }
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    for (const schedule of schedules) {
      const row = node('article', 'schedule-item'); row.setAttribute('aria-label', schedule.label);
      const heading = node('header', 'schedule-card-heading'), title = node('div'); title.append(node('h3', '', schedule.label));
      const failed = Boolean(schedule.last_error || schedule.settings_error);
      const badge = node('span', 'status-badge ' + (failed ? 'failed' : !schedule.enabled ? '' : state.enabled ? 'enabled' : 'waiting'), failed ? 'Needs review' : !schedule.enabled ? schedule.kind === 'once' && !schedule.next_due ? 'Completed' : 'Paused' : state.enabled ? 'Active' : 'Ready');
      const date = schedule.kind === 'once' ? new Date(schedule.run_at) : new Date(`2000-01-01T${schedule.time}:00Z`);
      const time = new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit', timeZone: schedule.kind === 'once' ? schedule.timezone : 'UTC'}).format(date);
      title.append(node('div', 'schedule-time', time));
      title.append(node('div', 'schedule-timezone', schedule.kind === 'once' ? new Intl.DateTimeFormat(undefined, {month: 'long', day: 'numeric', year: 'numeric', timeZone: schedule.timezone}).format(date) + ' · ' + schedule.timezone.replaceAll('_', ' ') : schedule.timezone.replaceAll('_', ' ')));
      if (schedule.kind === 'weekly') {
        const weekdays = node('div', 'schedule-days'); weekdays.setAttribute('aria-label', schedule.weekdays.map(day => days[day]).join(', '));
        days.forEach((day, index) => weekdays.append(node('span', 'day-chip' + (schedule.weekdays.includes(index) ? ' selected' : ''), day)));
        title.append(weekdays);
      }
      heading.append(title, badge); row.append(heading);
      const content = node('div', 'schedule-content');
      const accounts = node('section'), accountList = node('div', 'schedule-accounts'); accounts.append(node('span', 'detail-label', `Accounts · ${schedule.profile_ids.length}`));
      for (const id of schedule.profile_ids) {
        const provider = state.accounts.find(a => a.id === id)?.provider || id.split('-')[0];
        const chip = node('div', 'account-chip'); chip.append(providerIcon(provider), node('span', '', label(id))); accountList.append(chip);
      }
      accounts.append(accountList); content.append(accounts);
      const models = node('section'), modelList = node('div', 'schedule-models'); models.append(node('span', 'detail-label', 'Models & reasoning'));
      for (const [provider, choice] of Object.entries(schedule.provider_settings || {})) {
        const model = node('div', 'schedule-model-row'), detail = node('div', 'model-detail');
        const displayName = capability(provider).models?.find(item => item.id === choice.model)?.label || choice.model;
        detail.append(node('strong', '', displayName), node('small', '', `${providers[provider] || provider} · ${choice.reasoning} reasoning`));
        model.append(providerIcon(provider), detail); modelList.append(model);
      }
      models.append(modelList); content.append(models);
      const message = node('section', 'message-detail'); message.append(node('span', 'detail-label', 'Message'), node('blockquote', 'schedule-message', schedule.prompt || 'say okay')); content.append(message);
      if (failed) content.append(node('p', 'schedule-error', schedule.settings_error || schedule.last_error));
      if (!schedule.provider_settings) content.append(node('p', 'schedule-error', 'Edit this schedule to choose models and reasoning.'));
      row.append(content);
      const when = node('div', 'schedule-when');
      when.append(node('strong', '', !schedule.enabled ? 'SCHEDULE STATUS' : state.enabled ? 'NEXT WAKE-UP' : 'WAKE-UPS ARE STOPPED'), node('span', '', !schedule.enabled ? schedule.kind === 'once' && !schedule.next_due ? 'This one-time schedule has finished.' : 'Paused · no prompts will be sent.' : `${state.enabled ? '' : 'Planned: '}${localTime(schedule.next_due)}`)); row.append(when);
      const controls = node('div', 'schedule-actions');
      const edit = node('button', 'button secondary', 'Edit schedule'); edit.type = 'button'; edit.dataset.mutation = '1'; edit.addEventListener('click', () => {
        editingSchedule = schedule.id; selected = new Set(schedule.profile_ids); providerChoices = structuredClone(schedule.provider_settings || {}); settingsSignature = '';
        $('wakeupPrompt').value = schedule.prompt || 'say okay'; $('accountSearch').value = '';
        $('scheduleLabel').value = schedule.label; $('scheduleKind').value = schedule.kind; $('scheduleTimezone').value = schedule.timezone;
        if (schedule.time) $('scheduleTime').value = schedule.time;
        if (schedule.kind === 'once' && schedule.run_at) {
          const parts = new Intl.DateTimeFormat('sv-SE', {timeZone: schedule.timezone, year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(schedule.run_at));
          $('scheduleDate').value = parts.replace(' ', 'T');
        }
        document.querySelectorAll('.weekdays input').forEach(input => input.checked = (schedule.weekdays || []).includes(Number(input.value)));
        $('scheduleKind').dispatchEvent(new Event('change')); setMode('schedule'); renderAccounts(); actions(); $('composeTitle').scrollIntoView({behavior: 'smooth', block: 'start'});
      }); controls.append(edit);
      if ((schedule.kind !== 'once' || schedule.next_due) && schedule.provider_settings && !schedule.settings_error) {
        const pause = node('button', 'button secondary', schedule.enabled ? 'Pause' : 'Resume'); pause.type = 'button'; pause.dataset.mutation = '1';
        pause.addEventListener('click', () => mutate({action: 'toggle_schedule', id: schedule.id, enabled: !schedule.enabled}, schedule.enabled ? 'Schedule paused.' : 'Schedule resumed.')); controls.append(pause);
      }
      const remove = node('button', 'text-button delete', 'Delete'); remove.type = 'button'; remove.dataset.mutation = '1';
      remove.addEventListener('click', () => { pendingDelete = schedule.id; $('deleteSummary').textContent = schedule.label; $('deleteDialog').returnValue = 'cancel'; $('deleteDialog').showModal(); });
      controls.append(remove); row.append(controls); host.append(row);
    }
  }
  function renderHistory() {
    const signature = JSON.stringify([state.jobs, state.attempts, state.notifications, state.accounts.map(a => [a.id, a.label]), Math.floor(Date.now() / 60000)]);
    if (signature === historySignature) return; historySignature = signature;
    const host = $('history'); host.replaceChildren();
    const events = [];
    for (const job of state.jobs) {
      const attempts = state.attempts.filter(attempt => attempt.job_id === job.id);
      const ids = job.profile_ids || [...new Set([...job.results.map(result => result.profile_id), ...attempts.map(attempt => attempt.profile_id)])];
      const reason = job.state === 'processing' ? 'Checking this account before sending.' : job.state === 'queued' ? 'Waiting for the collector.' : job.state === 'cancelled' ? 'Cancelled by a stop or schedule change.' : 'Request expired; no late send.';
      if (!ids.length) events.push({profile_id: '', state: job.state, reason, job_id: job.id, created_at: job.created_at, source: job.source});
      for (const id of ids) {
        const result = job.results.find(item => item.profile_id === id);
        const attempt = attempts.find(item => item.profile_id === id);
        const progress = attempt?.in_progress ? 'sending' : attempt?.state === 'reserved' ? 'unknown' : attempt?.state;
        events.push({profile_id: id, state: progress || (job.state === 'processing' ? 'checking' : job.state), reason: attempt?.reason || (progress === 'sending' ? 'Sending one prompt. It will not be retried.' : reason), attempt_id: attempt?.id, ...result, job_id: job.id, created_at: attempt?.created_at || job.created_at, source: job.source});
      }
    }
    // A process crash may leave a reservation without a completed job result.
    for (const attempt of state.attempts) {
      if (attempt.paused && !attempt.in_progress && !events.some(event => event.attempt_id === attempt.id)) events.unshift({profile_id: attempt.profile_id, state: attempt.state === 'failed' ? 'failed' : 'unknown', reason: attempt.reason || 'A previous attempt was interrupted. It will not be retried automatically.', attempt_id: attempt.id, created_at: attempt.created_at, source: 'manual'});
    }
    if (!events.length) { host.append(node('p', 'empty', 'No wake-ups sent yet. Scheduled and manual results will appear here.')); return; }
    const renderedPauses = new Set();
    for (const event of events.slice(0, 30)) {
      const row = node('article', 'history-item'); row.append(node('span', 'history-dot ' + event.state));
      const copy = node('div'); const title = event.profile_id ? label(event.profile_id) : event.source === 'manual' ? 'Manual send' : 'Scheduled send';
      copy.append(node('strong', '', `${title} · ${event.state === 'sent' ? 'Sent once' : event.state.charAt(0).toUpperCase() + event.state.slice(1)}`), node('p', '', event.reason), node('time', '', localTime(event.created_at)));
      if (event.model) copy.append(node('p', '', `${event.model} · ${event.reasoning || 'default'}`));
      for (const limit of (event.quota_limits || []).slice(0, 2)) {
        const title = {weekly: 'Weekly quota exhausted', five_hour: 'Five-hour quota exhausted'}[limit.window];
        if (!title) continue;
        const reset = limit.reset_at ? localTime(new Date(limit.reset_at * 1000).toISOString()) : limit.reset_text || 'not reported';
        copy.append(node('p', 'notification-problem', `${title} · reset: ${reset}`));
      }
      if (event.quota_status === 'checking') copy.append(node('p', '', 'Checking which usage limit was reached. No prompt is being resent.'));
      else if (event.failure_kind === 'usage_limit' && !event.quota_limits?.length) copy.append(node('p', '', 'Usage/rate limit rejected; weekly vs five-hour not confirmed by CLI.'));
      if (event.reset_at || event.reset_text) {
        const reset = event.reset_at ? localTime(new Date(event.reset_at * 1000).toISOString()) : event.reset_text;
        copy.append(node('p', 'activity-reset', `Next 5h reset · ${reset}${event.reset_estimated ? ' · Estimated' : event.reset_source === 'reported' || (event.state === 'skipped' && !event.reset_source) ? ' · CLI reported' : ''}`));
      }
      if (event.reset_status === 'checking') copy.append(node('p', '', 'Checking the next reset · prompt already completed.'));
      else if (event.state === 'sent' && !event.reset_at && !event.reset_text) copy.append(node('p', '', 'Next 5h reset · CLI did not report a usable time.'));
      const notification = state.notifications?.find(item => item.job_id === event.job_id && (item.kind === 'run_summary' || item.profile_id === event.profile_id));
      if (notification && ['delivery_failed', 'claimed'].includes(notification.delivery_state)) copy.append(node('p', 'notification-problem', notification.delivery_state === 'delivery_failed' ? 'Alert delivery failed. This result remains saved here.' : 'Alert delivery was attempted; automatic replay is disabled.'));
      const attempt = state.attempts.find(a => a.id === (event.attempt_id || event.blocked_by_attempt_id));
      if (attempt?.paused && !renderedPauses.has(attempt.account_ref)) {
        renderedPauses.add(attempt.account_ref);
        const resolve = node('button', 'resolve-button', new Date(attempt.next_eligible_at) > new Date() ? `Review available ${localTime(attempt.next_eligible_at)}` : attempt.state === 'failed' ? 'Acknowledge failure & resume' : 'Acknowledge uncertainty & resume');
        resolve.type = 'button'; resolve.disabled = new Date(attempt.next_eligible_at) > new Date();
        resolve.addEventListener('click', () => mutate({action: 'resume_account', account_ref: attempt.account_ref}, 'Account resumed. Its safety history is preserved.'));
        copy.append(resolve);
      }
      if (event.profile_id) { const icon = providerIcon(state.accounts.find(a => a.id === event.profile_id)?.provider); icon.classList.add('activity-provider'); row.prepend(icon); }
      row.append(copy); host.append(row);
    }
  }
  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      state = await request();
      $('connection').textContent = 'Connected'; $('masterState').textContent = state.enabled && state.clock_error ? 'Safety hold' : state.enabled ? 'Enabled' : 'Stopped'; $('masterState').className = 'state-pill' + (state.enabled ? ' enabled' : '');
      $('masterDescription').textContent = state.enabled && state.clock_error ? 'Sending paused for clock verification; saved preference unchanged.' : state.enabled ? 'Scheduled and immediate wake-ups are enabled.' : 'Schedules are saved. Sending is stopped.';
      $('masterToggle').textContent = state.enabled ? 'Stop all wake-ups' : 'Enable wake-ups'; $('masterToggle').className = 'button secondary' + (state.enabled ? ' danger' : '');
      // Preserve focused controls and selected accounts during background refreshes.
      if (!$('accountList').contains(document.activeElement)) renderAccounts();
      renderSchedules(); renderHistory(); renderDefaults(); actions();
      if (state.clock_error) notify(state.clock_error, true);
    } catch (error) { $('connection').textContent = 'Connection unavailable'; if (!state) notify(error.message, true); }
    finally { refreshing = false; }
  }
  function showView(view) {
    for (const name of ['schedules', 'composer', 'activity', 'defaults']) $(name + 'View').hidden = name !== view;
    for (const name of ['Schedules', 'Activity', 'Defaults']) { $('view' + name).classList.toggle('active', view === name.toLowerCase()); $('view' + name).setAttribute('aria-pressed', String(view === name.toLowerCase())); }
  }
  function setMode(value) {
    mode = value; showView('composer');
    for (const current of ['now', 'schedule']) $(current + 'Panel').hidden = current !== mode;
    $('composeTitle').textContent = mode === 'now' ? 'Send a wake-up now' : editingSchedule ? 'Edit schedule' : 'New schedule';
    $('editorDescription').textContent = mode === 'now' ? 'Send one prompt to your chosen accounts, even with an active window. Review before sending.' : 'Choose accounts, a message and a time.';
  }
  function beginEditor(value) {
    if (!state || busy) return;
    editingSchedule = null; selected = new Set(); providerChoices = structuredClone(state.defaults || {}); settingsSignature = '';
    $('accountSearch').value = ''; $('scheduleLabel').value = ''; $('wakeupPrompt').value = state.prompt || 'say OK';
    $('scheduleKind').value = 'weekly'; $('scheduleTime').value = '08:00';
    $('scheduleTimezone').value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    document.querySelectorAll('.weekdays input').forEach(input => input.checked = true);
    $('scheduleKind').dispatchEvent(new Event('change'));
    if (value === 'now' && pendingRequest) { selected = new Set(pendingRequest.profile_ids); providerChoices = structuredClone(pendingRequest.provider_settings || {}); $('wakeupPrompt').value = pendingRequest.prompt || 'say OK'; }
    setMode(value); renderAccounts(); actions(); $('composeTitle').scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  function preview() {
    const zone = $('scheduleTimezone').value;
    const count = selected.size;
    $('schedulePreview').textContent = `${count || 'No'} account${count === 1 ? '' : 's'} · ${$('scheduleKind').value === 'once' ? 'One-time wake-up' : $('scheduleTime').value || 'Choose a time'} · ${zone || 'Choose a timezone'}`;
  }
  $('nowTab').addEventListener('click', () => beginEditor('now')); $('scheduleTab').addEventListener('click', () => beginEditor('schedule'));
  $('viewDefaults').addEventListener('click', () => { showView('defaults'); renderDefaults(); });
  $('viewSchedules').addEventListener('click', () => showView('schedules')); $('viewActivity').addEventListener('click', () => showView('activity'));
  $('backSchedules').addEventListener('click', () => showView('schedules')); $('cancelEdit').addEventListener('click', () => showView('schedules'));
  $('accountSearch').addEventListener('input', renderAccounts); $('scheduleFilter').addEventListener('change', renderSchedules);
  $('deleteDialog').addEventListener('cancel', () => { $('deleteDialog').returnValue = 'cancel'; });
  $('deleteDialog').addEventListener('close', async () => { const id = pendingDelete; pendingDelete = null; if ($('deleteDialog').returnValue === 'delete' && id && !busy) await mutate({action: 'delete_schedule', id}, 'Schedule deleted.'); });
  $('selectAll').addEventListener('click', () => { const accounts = state.accounts.filter(a => a.enabled); selected = accounts.every(a => selected.has(a.id)) ? new Set() : new Set(accounts.map(a => a.id)); renderAccounts(); actions(); });
  $('masterToggle').addEventListener('click', () => mutate({action: 'enabled', enabled: !state.enabled}, state.enabled ? 'Wake-ups stopped. Queued requests were cancelled.' : 'Wake-ups enabled. Accounts are checked before every send.'));
  $('refresh').addEventListener('click', refresh);
  $('sendNow').addEventListener('click', () => {
    $('reviewSummary').textContent = `Send to ${selected.size} selected account${selected.size === 1 ? '' : 's'}, after a fresh usage check.`;
    $('reviewAccounts').replaceChildren(...[...selected].map(id => { const account = state.accounts.find(item => item.id === id); const choice = providerChoices[account.provider]; return node('span', '', `${label(id)} · ${choice.model} · ${choice.reasoning}`); }));
    $('reviewPrompt').textContent = $('wakeupPrompt').value;
    $('reviewDialog').returnValue = 'cancel';
    $('reviewDialog').showModal();
  });
  $('reviewDialog').addEventListener('cancel', () => { $('reviewDialog').returnValue = 'cancel'; });
  $('reviewDialog').addEventListener('close', async () => {
    if ($('reviewDialog').returnValue !== 'send' || busy) return;
    const ids = [...selected].sort(), settings = chosenSettings(), prompt = $('reviewPrompt').textContent;
    if (pendingRequest && (JSON.stringify(pendingRequest.profile_ids) !== JSON.stringify(ids) || JSON.stringify(pendingRequest.provider_settings) !== JSON.stringify(settings) || (pendingRequest.prompt ?? 'say OK') !== prompt)) { notify('An earlier send has an uncertain response. Refresh activity or retry that same account and model selection first.', true); return; }
    if (!pendingRequest) pendingRequest = {action: 'now', profile_ids: ids, provider_settings: settings, prompt, idempotency_key: crypto.randomUUID().replaceAll('-', '')};
    try { sessionStorage.setItem('cyd-wakeup-pending', JSON.stringify(pendingRequest)); } catch (_) {}
    busy = true; actions();
    try {
      await request(pendingRequest); pendingRequest = null; try { sessionStorage.removeItem('cyd-wakeup-pending'); } catch (_) {}
      notify('Request queued. The collector will check each account and send at most one prompt.'); showView('activity'); await refresh();
    } catch (error) {
      if (error.status >= 400 && error.status < 500) {
        // A definite rejection did not queue work. Let the operator repair
        // their selection instead of locking the page to a rejected request.
        pendingRequest = null; try { sessionStorage.removeItem('cyd-wakeup-pending'); } catch (_) {}
        notify(`${error.message} Review your selection before submitting again.`, true);
      } else notify(`${error.message} The same request ID will be reused if you try again.`, true);
    }
    finally { busy = false; actions(); }
  });
  $('scheduleKind').addEventListener('change', () => { const once = $('scheduleKind').value === 'once'; $('timeField').hidden = once; $('weekdayField').hidden = once; $('dateField').hidden = !once; $('scheduleTime').required = !once; $('scheduleDate').required = once; preview(); });
  $('schedulePanel').addEventListener('input', preview);
  $('schedulePanel').addEventListener('submit', async e => {
    e.preventDefault(); if (busy || !selected.size) return;
    const payload = {action: 'save_schedule', label: $('scheduleLabel').value || 'Account wake-up', profile_ids: [...selected], provider_settings: chosenSettings(), prompt: $('wakeupPrompt').value, kind: $('scheduleKind').value, timezone: $('scheduleTimezone').value, time: $('scheduleTime').value, weekdays: [...document.querySelectorAll('.weekdays input:checked')].map(input => Number(input.value)), local_datetime: $('scheduleDate').value};
    if (editingSchedule) payload.id = editingSchedule;
    const result = await mutate(payload, state.enabled ? 'Schedule created.' : 'Schedule saved. Enable wake-ups when you are ready to send.');
    if (result) { $('scheduleLabel').value = ''; editingSchedule = null; $('scheduleFilter').value = 'all'; renderSchedules(); showView('schedules'); actions(); }
  });
  $('wakeupPrompt').addEventListener('input', () => { $('promptCount').textContent = `${$('wakeupPrompt').value.length} / 500`; actions(); });
  if (pendingRequest?.prompt) $('wakeupPrompt').value = pendingRequest.prompt;
  $('scheduleTimezone').value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const soon = new Date(Date.now() + 3600000); soon.setMinutes(0, 0, 0); $('scheduleDate').value = new Date(soon.getTime() - soon.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  refresh(); setInterval(() => { if (!document.hidden && !$('reviewDialog').open && !$('deleteDialog').open) refresh(); }, 5000);
})();
