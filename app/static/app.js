const pages = ['playground', 'sources', 'processes', 'settings'];
function navigate() {
  const page = location.hash.slice(1);
  const selected = pages.includes(page) ? page : 'playground';
  document.querySelector('.layout').classList.toggle('show-processes', selected === 'processes');
  const workshop = document.getElementById('sunset-workshop');
  if (selected === 'processes' && !workshop.hasAttribute('src')) workshop.src = workshop.dataset.src;
  if (workshop.contentWindow && workshop.hasAttribute('src')) workshop.contentWindow.postMessage({type: 'workshop-visibility', visible: selected === 'processes'}, location.origin);
  pages.forEach(id => document.getElementById(id).hidden = id !== selected);
  document.querySelectorAll('[data-page]').forEach(button => button.classList.toggle('active', button.dataset.page === selected));
}
document.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => location.hash = button.dataset.page));
window.addEventListener('hashchange', () => { navigate(); if (location.hash === '#sources') loadSources(); if (location.hash === '#settings') loadSettings(); }); navigate();
const live = document.getElementById('live');
live.addEventListener('change', () => document.getElementById('mode-note').textContent = live.checked ? 'Local API · uses configured cloud providers' : 'Design preview · sample answers');
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => { document.getElementById('question').value = button.dataset.question; document.getElementById('question').focus(); }));
function node(tag, text, className) { const element = document.createElement(tag); element.textContent = text; if (className) element.className = className; return element; }
const answer = document.getElementById('answer');
function render(data, demo) {
  answer.replaceChildren(node('h2', demo ? 'A sample discovery' : 'Here’s what your notes say'), node('p', data.answer));
  const sources = Array.isArray(data.sources) ? data.sources : [];
  answer.append(node('p', `Sources: ${sources.join(', ') || 'none'}`, 'excerpt'));
  (data.cited_chunks || []).forEach(chunk => { const details = document.createElement('details'); details.append(node('summary', `${chunk.source} · chunk ${chunk.chunk_index + 1}`), node('p', chunk.content, 'excerpt')); answer.append(details); });
}
document.getElementById('ask-form').addEventListener('submit', async event => {
  event.preventDefault(); const question = document.getElementById('question').value.trim(); if (!question) return;
  const button = document.getElementById('ask-button'); button.disabled = true; answer.hidden = false; answer.replaceChildren(node('p', live.checked ? 'Looking through your notes…' : 'Opening a little thread…'));
  try {
    if (!live.checked) {
      render({answer: 'MemoryPalace keeps notes in PostgreSQL because pgvector lets semantic search and document metadata live together. Fewer moving parts, more room to learn.\n\nThis is a sample answer for the design preview, not a response from your stored notes.', sources:['Sample · project-notes.md'], cited_chunks:[{source:'Sample · project-notes.md', chunk_index:0, content:'Use PostgreSQL + pgvector for document chunks and semantic search in one database.'}]}, true);
    } else {
      const response = await fetch('/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question, top_k:5})});
      if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : 'The local API could not answer. Check that the database and provider credentials are ready.'); }
      const data = await response.json(); if (typeof data.answer !== 'string') throw new Error('The API returned an unexpected answer.'); render(data, false);
    }
  } catch (error) { answer.replaceChildren(node('h2','Let’s try again'),node('p',error.message)); }
  finally { button.disabled = false; }
});

// The supplied animation stays isolated so its SVG classes and timing cannot
// override the app. Its own ResizeObserver reports the responsive frame height.
window.addEventListener('message', event => {
  const frame = document.getElementById('sunset-workshop');
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  if (event.data?.type === 'workshop-height' && Number.isFinite(event.data.height)) {
    frame.style.height = `${Math.min(2400, Math.max(250, event.data.height))}px`;
  }
});

async function loadSources() {
  const list = document.getElementById('source-list');
  list.replaceChildren(node('p', 'Opening your bookshelf…', 'muted'));
  try {
    const response = await fetch('/api/sources');
    if (!response.ok) throw new Error('Could not load sources. Check that the local database is running.');
    const sources = await response.json();
    if (!Array.isArray(sources)) throw new Error('Unexpected source list.');
    list.replaceChildren();
    if (!sources.length) list.append(node('p', 'Your bookshelf is empty. Add your first note above.', 'empty-card'));
    sources.forEach(source => {
      const card = node('article', '', 'source-row');
      card.append(node('span', '▤', 'source-icon'), node('strong', source.source), node('span', `${source.chunk_count} chunks`, 'muted'));
      const remove = node('button', 'Delete', 'delete-source');
      remove.type = 'button'; remove.setAttribute('aria-label', `Delete ${source.source}`);
      remove.addEventListener('click', async () => {
        if (!window.confirm(`Delete “${source.source}” and all its stored chunks? This cannot be undone. Your original file will stay intact.`)) return;
        remove.disabled = true;
        try {
          const response = await fetch(`/api/sources?source=${encodeURIComponent(source.source)}`, {method: 'DELETE'});
          if (!response.ok) throw new Error('Could not delete this source. Refresh and try again.');
          document.getElementById('source-feedback').textContent = `Deleted ${source.source}.`;
          await loadSources();
        } catch (error) { document.getElementById('source-feedback').textContent = error.message; remove.disabled = false; }
      });
      card.append(remove); list.append(card);
    });
  } catch (error) { list.replaceChildren(node('p', error.message, 'muted')); }
}
document.getElementById('refresh-sources').addEventListener('click', loadSources);
document.getElementById('upload-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file = document.getElementById('source-file').files[0];
  const feedback = document.getElementById('source-feedback');
  if (!file) return;
  if (file.size > 64 * 1024) { feedback.textContent = 'Choose a file smaller than 64 KiB.'; return; }
  if (!/\.(txt|md|markdown)$/i.test(file.name)) { feedback.textContent = 'Choose a text or Markdown file.'; return; }
  const button = document.getElementById('upload-button'); button.disabled = true;
  feedback.textContent = 'Reading and embedding your note…';
  try {
    const response = await fetch(`/api/sources/upload?filename=${encodeURIComponent(file.name)}`, {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file});
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Upload failed. Check the API and provider credentials.');
    }
    const result = await response.json();
    feedback.textContent = `Added ${result.source} · ${result.chunks_created} chunks.`;
    document.getElementById('upload-form').reset(); await loadSources();
  } catch (error) { feedback.textContent = error.message; }
  finally { button.disabled = false; }
});
if (location.hash === '#sources') loadSources();

async function loadSettings() {
  const container = document.getElementById('settings-list');
  container.replaceChildren(node('p', 'Loading your setup…', 'muted'));
  try {
    const response = await fetch('/api/settings');
    if (!response.ok) throw new Error('Could not load configuration. Check that the local API is running.');
    const data = await response.json();
    const fields = [
      ['Embedding provider', data.embedding_provider],
      ['Embedding model', data.embedding_model],
      ['Vector dimensions', data.embedding_dimensions],
      ['Answer provider', data.answer_provider],
      ['Answer model', data.answer_model],
      ['Storage', data.storage],
      ['Chunk target / overlap', `${data.chunk_size} / ${data.chunk_overlap} tokens`],
      ['Upload limit', `${data.upload_limit_bytes / 1024} KiB · text / Markdown`]
    ];
    container.replaceChildren();
    fields.forEach(([label, value]) => { const row = document.createElement('div'); row.append(node('span', label), node('strong', String(value))); container.append(row); });
  } catch (error) { container.replaceChildren(node('p', error.message, 'muted')); }
}
if (location.hash === '#settings') loadSettings();

document.getElementById('text-form').addEventListener('submit', async event => {
  event.preventDefault();
  const title = document.getElementById('note-title').value.trim();
  const content = document.getElementById('note-content').value;
  const feedback = document.getElementById('source-feedback');
  if (!title || !content.trim()) { feedback.textContent = 'Add a title and some text first.'; return; }
  if (new TextEncoder().encode(content).length > 64 * 1024) { feedback.textContent = 'Keep your note under 64 KiB.'; return; }
  const button = document.getElementById('save-text-button'); button.disabled = true;
  feedback.textContent = 'Embedding your note…';
  try {
    const response = await fetch(`/api/sources/text?title=${encodeURIComponent(title)}`, {method:'POST', headers:{'Content-Type':'text/plain;charset=UTF-8'}, body:content});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save your note. Check the API and provider credentials.');
    feedback.textContent = `Saved ${data.source} · ${data.chunks_created} chunks.`;
    document.getElementById('text-form').reset(); await loadSources();
  } catch (error) { feedback.textContent = error.message; }
  finally { button.disabled = false; }
});
