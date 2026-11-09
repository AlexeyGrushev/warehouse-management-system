import os

# Достаточно длинный ключ для HS256, чтобы тесты не сыпали предупреждениями
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests-only-0123456789"
# В тестах фоновую задачу истечения резервов не запускаем, её проверяют отдельные тесты
os.environ["RESERVATION_EXPIRY_INTERVAL_SECONDS"] = "0"
