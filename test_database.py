import pytest
import os
import tempfile
from database import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


class TestDatabaseManager:
    """Тесты для класса DatabaseManager"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.db = DatabaseManager()
        self.db.connect()

    def teardown_method(self):
        """Очистка после каждого теста"""
        self.db.disconnect()

    def test_connection(self):
        """Тест подключения к БД"""
        assert self.db.connection is not None
        assert self.db.cursor is not None

    def test_create_tables(self):
        """Тест создания таблиц"""
        # Проверяем что таблицы созданы
        self.db.cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in self.db.cursor.fetchall()]

        expected_tables = ['users', 'coords', 'pereval_added', 'images']
        for table in expected_tables:
            assert table in tables, f"Таблица {table} не создана"

    def test_add_and_get_user(self):
        """Тест добавления и получения пользователя"""
        user_data = {
            'email': 'test_user@example.com',
            'fam': 'Тестов',
            'name': 'Тест',
            'otc': 'Тестович',
            'phone': '1234567890'
        }

        # Добавляем пользователя
        user_id = self.db._add_or_get_user(user_data)
        assert user_id is not None

        # Пробуем получить того же пользователя
        same_user_id = self.db._add_or_get_user(user_data)
        assert same_user_id == user_id  # Должен вернуть тот же ID

    def test_add_pereval(self):
        """Тест добавления перевала"""
        test_data = {
            'beauty_title': 'Тестовый перевал',
            'title': 'Тест горный',
            'other_titles': 'Тест',
            'connect': 'Соединяет',
            'add_time': '2023-12-07 12:00:00',
            'user': {
                'email': 'test_pereval@example.com',
                'fam': 'Перевалов',
                'name': 'Иван',
                'otc': 'Иванович',
                'phone': '9876543210'
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
                {
                    'data': 'test_image_data',
                    'title': 'Тестовое фото'
                }
            ]
        }

        pereval_id = self.db.add_pereval(test_data)
        assert pereval_id is not None

        # Проверяем что данные добавились
        self.db.cursor.execute("SELECT COUNT(*) FROM pereval_added WHERE id = %s", (pereval_id,))
        count = self.db.cursor.fetchone()[0]
        assert count == 1

        return pereval_id

    def test_get_pereval(self):
        """Тест получения перевала по ID"""
        # Сначала добавляем тестовый перевал
        pereval_id = self.test_add_pereval()

        # Получаем его
        pereval = self.db.get_pereval(pereval_id)
        assert pereval is not None
        assert pereval['id'] == pereval_id
        assert pereval['title'] == 'Тест горный'
        assert pereval['status'] == 'new'

    def test_update_pereval_new_status(self):
        """Тест обновления перевала со статусом new"""
        pereval_id = self.test_add_pereval()

        update_data = {
            'title': 'Обновленный перевал',
            'connect': 'Новое описание',
            'coords': {
                'latitude': '56.1234',
                'longitude': '38.5678',
                'height': '1500'
            },
            'images': []
        }

        result = self.db.update_pereval(pereval_id, update_data)
        assert result['state'] == 1
        assert 'Успешно обновлено' in result['message']

    def test_update_pereval_not_new_status(self):
        """Тест что нельзя обновить перевал со статусом не new"""
        pereval_id = self.test_add_pereval()

        # Меняем статус на accepted
        self.db.cursor.execute(
            "UPDATE pereval_added SET status = 'accepted' WHERE id = %s",
            (pereval_id,)
        )
        self.db.connection.commit()

        update_data = {'title': 'Попытка изменить'}
        result = self.db.update_pereval(pereval_id, update_data)

        assert result['state'] == 0
        assert 'Редактирование запрещено' in result['message']

    def test_get_user_perevals(self):
        """Тест получения перевалов пользователя"""
        # Добавляем два перевала для одного пользователя
        test_data1 = {
            'beauty_title': 'Перевал 1',
            'title': 'Первый перевал',
            'other_titles': '',
            'connect': '',
            'add_time': '2023-12-07 10:00:00',
            'user': {
                'email': 'same_user@example.com',
                'fam': 'Один',
                'name': 'Пользователь',
                'otc': 'Тест',
                'phone': '1111111111'
            },
            'coords': {'latitude': '55.0', 'longitude': '37.0', 'height': '1000'},
            'level': {'winter': '', 'summer': '', 'autumn': '', 'spring': ''},
            'images': []
        }

        test_data2 = {
            'beauty_title': 'Перевал 2',
            'title': 'Второй перевал',
            'other_titles': '',
            'connect': '',
            'add_time': '2023-12-07 11:00:00',
            'user': {
                'email': 'same_user@example.com',  # Тот же пользователь
                'fam': 'Один',
                'name': 'Пользователь',
                'otc': 'Тест',
                'phone': '1111111111'
            },
            'coords': {'latitude': '56.0', 'longitude': '38.0', 'height': '2000'},
            'level': {'winter': '', 'summer': '', 'autumn': '', 'spring': ''},
            'images': []
        }

        self.db.add_pereval(test_data1)
        self.db.add_pereval(test_data2)

        # Получаем перевалы пользователя
        perevals = self.db.get_user_perevals('same_user@example.com')
        assert len(perevals) >= 2

        # Проверяем что все перевалы принадлежат правильному пользователю
        for pereval in perevals:
            assert pereval['user']['email'] == 'same_user@example.com'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])