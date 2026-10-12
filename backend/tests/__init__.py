import os

# Достаточно длинный ключ для HS256, чтобы тесты не сыпали предупреждениями
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests-only-0123456789"
