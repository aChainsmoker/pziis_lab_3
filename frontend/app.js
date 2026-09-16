let selectedType = 'public-data';
const $ = id => document.getElementById(id);

async function api(url, options = {}) {
  options.headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  const response = await fetch(url, options);
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(data?.detail || 'Ошибка запроса');
  return data;
}

function showMessage(message, isError = false) {
  const element = $('message');
  element.textContent = message;
  element.classList.toggle('error', isError);
  element.hidden = !message;
}

function selectTab(type) {
  selectedType = type;
  $('tab-public').classList.toggle('active', type === 'public-data');
  $('tab-confidential').classList.toggle('active', type === 'confidential');
  $('panel-title').textContent = type === 'public-data' ? 'Неконфиденциальные данные' : 'Конфиденциальные данные';
  $('search').value = '';
  loadData();
}

function addRecord() { location.href = `/data-form.html?type=${selectedType}`; }

async function loadData() {
  try {
    showMessage('');
    const records = await api(`/api/${selectedType}?search=${encodeURIComponent($('search').value)}`);
    $('records').innerHTML = records.map(record => `
      <article class="record">
        <div class="record-content"><h3>${escapeHtml(record.title)}</h3><p>${escapeHtml(record.content)}</p></div>
        <div class="record-actions"><button type="button" onclick="editRecord(${record.id})">Редактировать</button><button type="button" class="danger" onclick="deleteRecord(${record.id})">Удалить</button></div>
      </article>
    `).join('') || '<p class="empty">Записей нет.</p>';
  } catch (error) { showMessage(error.message, true); }
}

function editRecord(id) { location.href = `/data-form.html?type=${selectedType}&id=${id}`; }

async function deleteRecord(id) {
  if (!confirm('Удалить эту запись?')) return;
  try { await api(`/api/${selectedType}/${id}`, {method: 'DELETE'}); await loadData(); }
  catch (error) { showMessage(error.message, true); }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[character]));
}

loadData();
