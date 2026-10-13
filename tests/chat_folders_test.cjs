const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../website/static/script.js'), 'utf8');
const helpers = source.slice(source.indexOf('const chatFolderStorageKey'), source.indexOf('const renderConversationList'));
function load(stored) {
  const context = {
    localStorage: { getItem: () => stored, setItem: () => {} },
    openConfirmModal: async () => true,
    renderConversationList: () => {}, conversations: [], conversationId: '',
    document: { getElementById: () => null },
  };
  vm.runInNewContext(helpers + '\nglobalThis.result = { state: chatFolders, orderedChatFolders, chatFolderPath, removeChatFolder };', context);
  return context.result;
}

// Existing flat folders and assignments survive the additive parentId migration.
let result = load(JSON.stringify({ folders: [{ id: 'root', name: 'Research', collapsed: true }], assignments: { chat: 'root' } }));
assert.equal(result.state.folders[0].parentId, null);
assert.equal(result.state.folders[0].collapsed, true);
assert.equal(result.state.assignments.chat, 'root');

// Out-of-order nested records produce a complete parent-first tree and full paths.
result = load(JSON.stringify({ folders: [
  { id: 'leaf', name: 'Sources', parentId: 'child' },
  { id: 'root', name: 'Research' },
  { id: 'child', name: 'Topic', parentId: 'root' },
], assignments: { chat: 'leaf' } }));
assert.equal(result.orderedChatFolders().map(folder => folder.id).join(','), 'root,child,leaf');
assert.equal(result.chatFolderPath(result.state.folders[0]), 'Research / Topic / Sources');
assert.equal(result.state.assignments.chat, 'leaf');

// Orphaned, self-parenting, and cyclic folders remain visible, without infinite traversal.
result = load(JSON.stringify({ folders: [
  { id: 'a', name: 'A', parentId: 'b' }, { id: 'b', name: 'B', parentId: 'a' },
  { id: 'self', name: 'Self', parentId: 'self' }, { id: 'orphan', name: 'Orphan', parentId: 'missing' },
], assignments: { missingChat: 'missing' } }));
assert.equal(result.orderedChatFolders().length, 4);
assert.equal(result.state.folders.find(folder => folder.id === 'self').parentId, null);
assert.equal(result.state.folders.find(folder => folder.id === 'orphan').parentId, null);
assert.equal(result.state.assignments.missingChat, undefined);

assert.equal(load('{bad json').state.folders.length, 0);
(async () => {
  result = load(JSON.stringify({ folders: [
    { id: 'root', name: 'Research' }, { id: 'middle', name: 'Topic', parentId: 'root' },
    { id: 'leaf', name: 'Drafts', parentId: 'middle' },
  ], assignments: { directChat: 'middle', nestedChat: 'leaf' } }));
  await result.removeChatFolder(result.state.folders.find(folder => folder.id === 'middle'));
  assert.equal(result.state.folders.length, 2);
  assert.equal(result.state.folders.find(folder => folder.id === 'leaf').parentId, 'root');
  assert.equal(result.state.assignments.directChat, undefined);
  assert.equal(result.state.assignments.nestedChat, 'leaf');
  assert.equal(result.chatFolderPath(result.state.folders.find(folder => folder.id === 'leaf')), 'Research / Drafts');
  console.log('Chat folder migration, nesting, cycle recovery, corrupt storage, and safe parent removal passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
