const params = new URLSearchParams(location.search);
const type = params.get('type') || 'public-data';
const id = params.get('id');
const $ = name => document.getElementById(name);

async function api(url, options = {}) {
  options.headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  const response = await fetch(url, options);
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(data?.detail || 'Ошибка запроса');
  return data;
}

function goBack() { location.href = '/'; }
function typeName() { return type === 'public-data' ? 'Неконфиденциальные данные' : 'Конфиденциальные данные'; }

async function init() {
  $('form-title').textContent = id ? 'Редактирование данных' : 'Добавление данных';
  $('form-type').textContent = `Тип: ${typeName()}`;
  if (!id) return;
  try {
    const record = await api(`/api/${type}/${id}`);
    $('title').value = record.title;
    $('content').value = record.content;
  } catch (error) { showError(error.message); }
}

async function saveRecord(event) {
  event.preventDefault();
  try {
    await api(`/api/${type}${id ? `/${id}` : ''}`, {method: id ? 'PUT' : 'POST', body: JSON.stringify({title: $('title').value, content: $('content').value})});
    goBack();
  } catch (error) { showError(error.message); }
}

function showError(message) { $('form-error').textContent = message; $('form-error').hidden = false; }
init();
