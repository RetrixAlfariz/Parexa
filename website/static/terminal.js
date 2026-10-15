/* Keyboard command surface; actions delegate to the existing application controls. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const dialog = byId('px-command-dialog');
  const search = byId('px-command-search');
  const list = byId('px-command-list');
  const trigger = byId('px-command-toggle');
  if (!dialog || !search || !list || !trigger) return;
  const click = selector => document.querySelector(selector)?.click();
  const openDrawer = (drawerId,toggleId,closeId) => {
    if (byId(drawerId)?.hidden) byId(toggleId)?.click();
    else byId(closeId)?.focus();
  };
  const commands = [
    { name:'New conversation', hint:'Alt N', run:() => click('.new-chat-btn') },
    { name:'Open Research OS', hint:'Projects / Vault / Lab', run:() => window.location.assign('/research') },
    { name:'Focus composer', hint:'/', run:() => byId('user-input')?.focus() },
    { name:'Choose model', hint:'Runtime', run:() => byId('ob-model-button')?.click() },
    { name:'Open sources', hint:'Research', run:() => click('[data-ob-action="sources"]') },
    { name:'Open notes', hint:'Browser local', run:() => click('[data-ob-action="notes"]') },
    { name:'Open activity', hint:'Execution', run:() => openDrawer('activity-drawer','panel-toggle-btn','activity-close') },
    { name:'Open settings', hint:'Preferences', run:() => openDrawer('settings-drawer','sidebar-settings-btn','settings-close') },
    { name:'Create folder', hint:'Chats', run:() => byId('chat-folder-new')?.click() },
    { name:'Standard reasoning', hint:'Single agent', run:() => byId('agent-default')?.click() },
    { name:'Genesis reasoning', hint:'Multi agent', run:() => byId('agent-genesis')?.click() },
    { name:'Toggle browsing', hint:'Web', run:() => byId('browse-toggle')?.click() },
    { name:'Toggle sidebar', hint:'Navigation', run:() => byId('sidebar-toggle-btn')?.click() },
  ];
  let visible = commands;
  let active = 0;
  let returnFocus = null;
  let restoreFocus = true;
  function markActive() {
    [...list.querySelectorAll('button')].forEach((button,index) => button.classList.toggle('is-active',index === active));
  }
  function run(command) {
    restoreFocus = false;
    dialog.close();
    byId('user-input')?.focus();
    command.run();
  }
  function render() {
    const query = search.value.trim().toLowerCase();
    visible = commands.filter(command => (command.name+' '+command.hint).toLowerCase().includes(query));
    active = 0;
    list.replaceChildren();
    if (!visible.length) {
      const empty = document.createElement('p');
      empty.className = 'px-command-empty';
      empty.textContent = 'No matching commands.';
      list.append(empty);
    }
    visible.forEach((command,index) => {
      const button = document.createElement('button');
      button.type = 'button';
      const label = document.createElement('span'); label.textContent = command.name;
      const hint = document.createElement('small'); hint.textContent = command.hint;
      button.append(label,hint);
      button.addEventListener('click',() => run(command));
      button.addEventListener('focus',() => { active = index; markActive(); });
      list.append(button);
    });
    markActive();
  }
  trigger.addEventListener('click',() => {
    if (dialog.open) { dialog.close(); return; }
    returnFocus = document.activeElement;
    restoreFocus = true;
    search.value = '';
    render();
    dialog.showModal();
    trigger.setAttribute('aria-expanded','true');
    search.focus();
  });
  byId('px-command-close')?.addEventListener('click',() => dialog.close());
  document.addEventListener('keydown',event => {
    if (dialog.open && event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
      dialog.close();
      return;
    }
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k') return;
    if (['modal-overlay','settings-drawer','activity-drawer'].some(id => byId(id) && !byId(id).hidden)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    trigger.click();
  },true);
  dialog.addEventListener('close',() => {
    trigger.setAttribute('aria-expanded','false');
    if (restoreFocus) {
      // The previous control may have become hidden while the command dialog was open.
      // Do not strand keyboard focus inside a closed modal.
      const visible = returnFocus?.isConnected &&
        returnFocus.getClientRects().length > 0 &&
        !returnFocus.closest('[hidden], [inert]');
      (visible ? returnFocus : byId('user-input'))?.focus();
    }
  });
  dialog.addEventListener('click',event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  search.addEventListener('input',render);
  dialog.addEventListener('keydown',event => {
    if (['ArrowDown','ArrowUp'].includes(event.key) && visible.length) {
      event.preventDefault();
      active = (active + (event.key === 'ArrowDown' ? 1 : -1) + visible.length) % visible.length;
      markActive();
      const button = list.querySelectorAll('button')[active];
      button?.scrollIntoView({block:'nearest'});
      button?.focus();
    } else if (event.key === 'Enter' && visible[active]) {
      event.preventDefault();
      run(visible[active]);
    }
  });
})();
