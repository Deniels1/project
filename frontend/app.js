const apiBase = window.location.origin;
const result = document.getElementById('result');
const resultType = document.getElementById('result-type');
const serverStatus = document.getElementById('server-status');
const userStatus = document.getElementById('user-status');

function getToken() {
  return localStorage.getItem('access_token');
}

function setToken(token) {
  localStorage.setItem('access_token', token);
  updateAuthState();
}

function removeToken() {
  localStorage.removeItem('access_token');
  updateAuthState();
}

function updateAuthState() {
  const token = getToken();
  userStatus.textContent = token ? 'авторизован' : 'не авторизован';
}

function showMessage(message, type = 'info') {
  resultType.textContent = type;
  result.textContent = message;
}

function showData(data, label = 'Результат') {
  resultType.textContent = label;
  result.textContent = JSON.stringify(data, null, 2);
}

async function request(url, options = {}) {
  const token = getToken();
  options.headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) {
    options.headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBase}${url}`, options);
  const contentType = response.headers.get('content-type') || '';
  let data = null;
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMessage = data?.detail || data || 'Ошибка запроса';
    throw new Error(errorMessage);
  }
  return data;
}

async function checkServer() {
  try {
    await request('/health');
    serverStatus.textContent = 'онлайн';
  } catch (err) {
    serverStatus.textContent = 'offline';
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const payload = {
    email: document.getElementById('register-email').value,
    password: document.getElementById('register-password').value,
    first_name: document.getElementById('register-first-name').value,
    last_name: document.getElementById('register-last-name').value,
  };
  try {
    const data = await request('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setToken(data.access_token);
    showMessage('Регистрация выполнена. Токен сохранён.', 'Регистрация');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const payload = {
    email: document.getElementById('login-email').value,
    password: document.getElementById('login-password').value,
  };
  try {
    const data = await request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setToken(data.access_token);
    showMessage('Вход выполнен. Токен сохранён.', 'Вход');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

async function loadProfile() {
  try {
    const data = await request('/api/v1/auth/me');
    showData(data, 'Профиль');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

async function loadUnits() {
  try {
    const data = await request('/api/v1/units');
    showData(data, 'Учебные блоки');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

async function loadChildren() {
  try {
    const data = await request('/api/v1/children');
    showData(data, 'Дети');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

async function createChild() {
  const payload = {
    name: document.getElementById('child-name').value,
    age: Number(document.getElementById('child-age').value),
    avatar_url: document.getElementById('child-avatar').value,
  };

  if (!payload.name || !payload.age) {
    showMessage('Введите имя и возраст ребёнка.', 'Ошибка');
    return;
  }

  try {
    const data = await request('/api/v1/children', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    showData(data, 'Ребёнок добавлен');
  } catch (err) {
    showMessage(err.message, 'Ошибка');
  }
}

function switchTab(event) {
  const tab = event.target.dataset.tab;
  if (!tab) return;
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === `${tab}-form`);
  });
}

function setupEvents() {
  document.getElementById('register-form').addEventListener('submit', handleRegister);
  document.getElementById('login-form').addEventListener('submit', handleLogin);
  document.getElementById('profile-button').addEventListener('click', loadProfile);
  document.getElementById('units-button').addEventListener('click', loadUnits);
  document.getElementById('children-button').addEventListener('click', loadChildren);
  document.getElementById('create-child-button').addEventListener('click', createChild);
  document.getElementById('logout-button').addEventListener('click', () => {
    removeToken();
    showMessage('Выход выполнен.', 'Выход');
  });
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', switchTab));
}

updateAuthState();
setupEvents();
checkServer();
