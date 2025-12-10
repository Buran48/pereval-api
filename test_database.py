import os
import pytest
from database import DatabaseManager

# Всегда используем тестовую БД
os.environ["FSTR_DB_NAME"] = "pereval_test"


class TestDatabaseManager:
    """Тесты для класса DatabaseManager"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.db = DatabaseManager()
        self.db.connect()

    def teardown_method(self):
        """Очистка после каждого теста"""
        self.db.disconnect()

    # Тест подключения к базе
    def test_connection(self):
        assert self.db.connection is not None
        assert self.db.cursor is not None

    # Проверяем, что таблицы создаются
    def test_create_tables(self):
        self.db.cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = [t[0] for t in self.db.cursor.fetchall()]

        assert "users" in tables
        assert "coords" in tables
        assert "pereval_added" in tables
        assert "images" in tables

    # Тест добавления/получения пользователя
    def test_add_and_get_user(self):
        user_data = {
            'email': 'test@example.com',
            'fam': 'тестфамилия',
            'name': 'тестимя',
            'otc': 'тестотчество',
            'phone': '123'
        }

        user_id = self.db._add_or_get_user(user_data)
        assert user_id is not None

        self.db.cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        result = self.db.cursor.fetchone()

        assert result is not None
        assert result[0] == user_data["email"]

    # Тест добавления перевала
    def create_test_pereval(self):
        """Вспомогательная функция — создаёт тестовый перевал"""
        data = {
            'beauty_title': 'тест перевал',
            'title': 'тест горный',
            'other_titles': 'тест',
            'connect': 'соединяет',
            'add_time': '2023-12-07 12:00:00',
            'user': {
                'email': 'test@example.com',
                'fam': 'тестфамилия',
                'name': 'тестимя',
                'otc': 'тестотчество',
                'phone': '123'
            },
            'coords': {
                'latitude': '55.1234',
                'longitude': '37.5678',
                'height': '1000'
            },
            'level': {
                'winter': '1А',
                'summer': '1Б',
                'autumn': '1А',
                'spring': ''
            },
            'images': [
                {'data': 'test_image_data', 'title': 'тестфото'}
            ]
        }

        return self.db.add_pereval(data)

    def test_add_pereval(self):
        pereval_id = self.create_test_pereval()
        assert pereval_id is not None

    # Тест получения перевала
    def test_get_pereval(self):
        pereval_id = self.create_test_pereval()

        pereval = self.db.get_pereval(pereval_id)
        assert pereval is not None
        assert pereval["id"] == pereval_id

    # Тест обновления перевала со статусом "new"
    def test_update_pereval_new_status(self):
        pereval_id = self.create_test_pereval()

        update_data = {
            'title': 'новый перевал',
            'connect': 'новое описание',
            'coords': {
                'latitude': '56.1234',
                'longitude': '38.5678',
                'height': '1500'
            },
            'images': []
        }

        result = self.db.update_pereval(pereval_id, update_data)
        assert result['state'] == 1

        updated = self.db.get_pereval(pereval_id)
        assert updated["title"] == "новый перевал"
        assert updated["coords"]["height"] == 1500

    # Тест запрета обновления перевала не в статусе "new"
    def test_update_pereval_not_new_status(self):
        pereval_id = self.create_test_pereval()

        # Меняем статус вручную
        self.db.cursor.execute(
            "UPDATE pereval_added SET status='accepted' WHERE id=%s",
            (pereval_id,)
        )
        self.db.connection.commit()

        result = self.db.update_pereval(pereval_id, {'title': 'пробуем изменить'})

        assert result['state'] == 0
        assert "Редактирование запрещено" in result['message']

    # Тест списка перевалов пользователя
    def test_get_user_perevals(self):
        self.create_test_pereval()

        perevals = self.db.get_user_perevals("test@example.com")
        assert isinstance(perevals, list)
        assert len(perevals) >= 1

