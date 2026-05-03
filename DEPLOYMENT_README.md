# Deployment README

## Развертывание и эксплуатация платформы

### Обзор развертывания
Children's Literacy Learning Platform развертывается как FastAPI приложение с PostgreSQL базой данных.

### Системные требования

#### Сервер
- Python 3.8+
- PostgreSQL 12+
- 2GB RAM минимум
- 10GB дискового пространства

#### Сетевое обеспечение
- Доступ к интернету для установки пакетов
- Порт 8000 для приложения (или настроенный порт)
- SSL сертификат для production

### Конфигурация среды

#### Переменные окружения
Создать файл `.env` в корне проекта:
```env
# База данных
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/child_learning

# JWT настройки
JWT_SECRET_KEY=your-super-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES=30
JWT_REFRESH_TOKEN_EXPIRES=7

# Настройки приложения
APP_NAME=Children's Literacy Learning Platform
APP_VERSION=1.0.0
DEBUG=False
```

#### Виртуальное окружение
```bash
# Создание виртуального окружения
python -m venv .venv

# Активация
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Установка зависимостей
pip install -r requirements.txt
```

### Установка и настройка базы данных

#### PostgreSQL
```sql
-- Создание базы данных
CREATE DATABASE child_learning;

-- Создание пользователя
CREATE USER learning_user WITH PASSWORD 'secure_password';

-- Предоставление прав
GRANT ALL PRIVILEGES ON DATABASE child_learning TO learning_user;
```

#### Миграции
Приложение использует SQLAlchemy с автоматическим созданием таблиц при старте:
```python
# Таблицы создаются автоматически в lifespan
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

### Запуск приложения

#### Development режим
```bash
# С reload для разработки
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Production режим
```bash
# С Gunicorn для production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker развертывание

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:password@db:5432/child_learning
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=child_learning
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Мониторинг и логирование

#### Логи приложения
- SQLAlchemy логирует все запросы (echo=True в development)
- FastAPI логирует HTTP запросы
- Аудит-логи сохраняются в базе данных

#### Метрики производительности
- `/health` endpoint для проверки здоровья
- `/api/v1/admin/stats` для статистики платформы
- WebSocket соединения для реал-тайм уведомлений

### Безопасность развертывания

#### HTTPS
```nginx
# Пример конфигурации Nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Firewall
- Открыть только необходимые порты (80, 443, 8000 для dev)
- Использовать fail2ban для защиты от brute-force

#### Секреты
- Никогда не коммитить `.env` файл
- Использовать сильные пароли для БД
- Регулярно менять JWT секреты

### Масштабирование

#### Горизонтальное масштабирование
- Использовать load balancer (Nginx, HAProxy)
- Несколько инстансов приложения за reverse proxy
- Redis для сессий и кэширования (если нужно)

#### Вертикальное масштабирование
- Увеличить RAM для большего количества одновременных пользователей
- SSD диски для лучшей производительности БД

### Резервное копирование

#### База данных
```bash
# Ежедневный бэкап PostgreSQL
pg_dump child_learning > backup_$(date +%Y%m%d).sql

# Восстановление
psql child_learning < backup_20231201.sql
```

#### Конфигурационные файлы
- Резервное копирование `.env` файлов
- Документация настроек

### Мониторинг и алерты

#### Инструменты
- Prometheus + Grafana для метрик
- ELK Stack для логов
- Sentry для ошибок

#### Ключевые метрики
- Количество активных пользователей
- Время отклика API
- Использование CPU/RAM
- Количество WebSocket соединений

### Часть для защиты проекта
**Тема:** Развертывание, эксплуатация и масштабирование платформы

**Что презентовать:**
1. Архитектура развертывания (Docker, PostgreSQL)
2. Конфигурация и переменные окружения
3. Процесс установки и запуска
4. Мониторинг и логирование
5. Стратегии масштабирования
6. Безопасность production среды

**Демонстрация:**
- Запуск приложения через Docker Compose
- Настройка базы данных
- Проверка health endpoints
- Просмотр логов и метрик
- Демонстрация WebSocket соединений

**Ключевые достижения:**
- Production-ready развертывание
- Масштабируемая архитектура
- Комплексная система мониторинга
- Высокий уровень безопасности</content>
<parameter name="filePath">c:\Users\Арнур\Downloads\task3\task3\DEPLOYMENT_README.md