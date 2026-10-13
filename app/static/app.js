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
window.addEventListener('hashchange', navigate); navigate();
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
      if (!response.ok) throw new Error(response.status === 409 ? 'Stored embeddings need re-embedding for the current model.' : 'The local API could not answer. Check that the database and provider credentials are ready.');
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
