import os
import psycopg2
from psycopg2 import sql, errors
from typing import Optional, Dict, Any, List
from datetime import datetime


class DatabaseManager:
    def __init__(self):
        self.db_host = os.getenv("FSTR_DB_HOST", "localhost")
        self.db_port = os.getenv("FSTR_DB_PORT", "5432")
        self.db_login = os.getenv("FSTR_DB_LOGIN", "postgres")
        self.db_pass = os.getenv("FSTR_DB_PASS", "")
        self.db_name = os.getenv("FSTR_DB_NAME", "pereval_db")

        self.connection = None
        self.cursor = None

    def connect(self):
        """подключается к базе данных, возвращает True если получилось"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_login,
                password=self.db_pass,
                database=self.db_name
            )
            self.cursor = self.connection.cursor()
            self._create_tables()
            return True
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            return False

    def _create_tables(self):
        """создает таблицы в базе если их нет"""
        create_tables_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100) NOT NULL UNIQUE,
            fam VARCHAR(100) NOT NULL,
            name VARCHAR(100) NOT NULL,
            otc VARCHAR(100),
            phone VARCHAR(20) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS coords (
            id SERIAL PRIMARY KEY,
            latitude DECIMAL(9,6) NOT NULL,
            longitude DECIMAL(9,6) NOT NULL,
            height INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pereval_added (
            id SERIAL PRIMARY KEY,
            beauty_title VARCHAR(255),
            title VARCHAR(255) NOT NULL,
            other_titles VARCHAR(255),
            connect TEXT,
            add_time TIMESTAMP NOT NULL,
            user_id INTEGER REFERENCES users(id),
            coord_id INTEGER REFERENCES coords(id),
            level_winter VARCHAR(10),
            level_summer VARCHAR(10),
            level_autumn VARCHAR(10),
            level_spring VARCHAR(10),
            status VARCHAR(20) DEFAULT 'new'
        );

        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            pereval_id INTEGER REFERENCES pereval_added(id),
            data TEXT NOT NULL,
            title VARCHAR(255)
        );

        -- таблицы из старой базы фстр
        CREATE TABLE IF NOT EXISTS pereval_areas (
            id SERIAL PRIMARY KEY,
            id_parent INTEGER NOT NULL,
            title TEXT
        );

        CREATE TABLE IF NOT EXISTS spr_activities_types (
            id SERIAL PRIMARY KEY,
            title TEXT
        );
        """

        self.cursor.execute(create_tables_sql)
        self.connection.commit()

    def disconnect(self):
        """отключается от базы данных"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def add_pereval(self, data: Dict[str, Any]) -> Optional[int]:
        """добавляет перевал в базу, возвращает номер записи или None если ошибка"""
        try:
            # 1. пользователь
            user_data = data['user']
            user_id = self._add_or_get_user(user_data)

            if not user_id:
                return None

            # 2. координаты
            coords_data = data['coords']
            self.cursor.execute(
                """
                INSERT INTO coords (latitude, longitude, height)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    float(coords_data['latitude']),
                    float(coords_data['longitude']),
                    int(coords_data['height'])
                )
            )
            coord_id = self.cursor.fetchone()[0]

            # 3. перевал
            pereval_sql = """
            INSERT INTO pereval_added (
                beauty_title, title, other_titles, connect, add_time,
                user_id, coord_id,
                level_winter, level_summer, level_autumn, level_spring, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new')
            RETURNING id
            """

            level_data = data['level']

            self.cursor.execute(pereval_sql, (
                data['beauty_title'],
                data['title'],
                data['other_titles'],
                data['connect'],
                data['add_time'],
                user_id,
                coord_id,
                level_data.get('winter', ''),
                level_data.get('summer', ''),
                level_data.get('autumn', ''),
                level_data.get('spring', '')
            ))

            pereval_id = self.cursor.fetchone()[0]

            # 4. фотографии
            for image in data['images']:
                self.cursor.execute(
                    "INSERT INTO images (pereval_id, data, title) VALUES (%s, %s, %s)",
                    (pereval_id, image['data'], image['title'])
                )

            self.connection.commit()
            return pereval_id

        except Exception as e:
            print(f"Ошибка добавления перевала: {e}")
            if self.connection:
                self.connection.rollback()
            return None

    def update_pereval(self, pereval_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        обновляет перевал если его статус 'new'
        возвращает {'state': 1/0, 'message': текст}
        """
        try:
            # 1. Проверяем статус перевала
            self.cursor.execute(
                "SELECT status FROM pereval_added WHERE id = %s",
                (pereval_id,)
            )
            result = self.cursor.fetchone()

            if not result:
                return {'state': 0, 'message': 'Перевал не найден'}

            if result[0] != 'new':
                return {'state': 0, 'message': f'Редактирование запрещено, статус: {result[0]}'}

            # 2. Обновляем координаты
            coords_data = data['coords']
            self.cursor.execute(
                """
                UPDATE coords c
                SET latitude = %s, longitude = %s, height = %s
                FROM pereval_added p
                WHERE p.id = %s AND p.coord_id = c.id
                """,
                (
                    float(coords_data['latitude']),
                    float(coords_data['longitude']),
                    int(coords_data['height']),
                    pereval_id
                )
            )

            # 3. Обновляем данные перевала (только переданные поля)
            update_fields = []
            update_values = []

            if 'beauty_title' in data:
                update_fields.append("beauty_title = %s")
                update_values.append(data['beauty_title'])
            if 'title' in data:
                update_fields.append("title = %s")
                update_values.append(data['title'])
            if 'other_titles' in data:
                update_fields.append("other_titles = %s")
                update_values.append(data['other_titles'])
            if 'connect' in data:
                update_fields.append("connect = %s")
                update_values.append(data['connect'])
            if 'add_time' in data:
                update_fields.append("add_time = %s")
                update_values.append(data['add_time'])

            # Уровни сложности
            if 'level' in data:
                level_data = data['level']
                if 'winter' in level_data:
                    update_fields.append("level_winter = %s")
                    update_values.append(level_data.get('winter', ''))
                if 'summer' in level_data:
                    update_fields.append("level_summer = %s")
                    update_values.append(level_data.get('summer', ''))
                if 'autumn' in level_data:
                    update_fields.append("level_autumn = %s")
                    update_values.append(level_data.get('autumn', ''))
                if 'spring' in level_data:
                    update_fields.append("level_spring = %s")
                    update_values.append(level_data.get('spring', ''))

            # Выполняем update только если есть что обновлять
            if update_fields:
                update_sql = f"UPDATE pereval_added SET {', '.join(update_fields)} WHERE id = %s"
                update_values.append(pereval_id)
                self.cursor.execute(update_sql, tuple(update_values))

            # 4. Удаляем старые изображения и добавляем новые
            self.cursor.execute("DELETE FROM images WHERE pereval_id = %s", (pereval_id,))

            for image in data['images']:
                self.cursor.execute(
                    "INSERT INTO images (pereval_id, data, title) VALUES (%s, %s, %s)",
                    (pereval_id, image['data'], image['title'])
                )

            self.connection.commit()
            return {'state': 1, 'message': 'Успешно обновлено'}

        except Exception as e:
            print(f"Ошибка обновления перевала: {e}")
            if self.connection:
                self.connection.rollback()
            return {'state': 0, 'message': f'Ошибка обновления: {str(e)}'}

    def get_user_perevals(self, email: str) -> List[Dict[str, Any]]:
        """получает все перевалы пользователя по email"""
        try:
            sql = """
            SELECT 
                p.id, p.beauty_title, p.title, p.other_titles, p.connect, p.add_time,
                p.level_winter, p.level_summer, p.level_autumn, p.level_spring,
                p.status,
                u.email, u.fam, u.name, u.otc, u.phone,
                c.latitude, c.longitude, c.height
            FROM pereval_added p
            JOIN users u ON p.user_id = u.id
            JOIN coords c ON p.coord_id = c.id
            WHERE u.email = %s
            ORDER BY p.add_time DESC
            """

            self.cursor.execute(sql, (email,))
            results = self.cursor.fetchall()

            perevals = []
            for row in results:
                # Получаем изображения для каждого перевала
                self.cursor.execute(
                    "SELECT data, title FROM images WHERE pereval_id = %s",
                    (row[0],)
                )
                images = self.cursor.fetchall()

                pereval_data = {
                    'id': row[0],
                    'beauty_title': row[1],
                    'title': row[2],
                    'other_titles': row[3],
                    'connect': row[4],
                    'add_time': row[5].isoformat() if row[5] else None,
                    'level': {
                        'winter': row[6],
                        'summer': row[7],
                        'autumn': row[8],
                        'spring': row[9]
                    },
                    'status': row[10],
                    'user': {
                        'email': row[11],
                        'fam': row[12],
                        'name': row[13],
                        'otc': row[14],
                        'phone': row[15]
                    },
                    'coords': {
                        'latitude': float(row[16]),
                        'longitude': float(row[17]),
                        'height': row[18]
                    },
                    'images': [
                        {'data': img[0], 'title': img[1]}
                        for img in images
                    ]
                }
                perevals.append(pereval_data)

            return perevals

        except Exception as e:
            print(f"Ошибка получения перевалов пользователя: {e}")
            return []

    def get_pereval(self, pereval_id: int) -> Optional[Dict[str, Any]]:
        """получает перевал по id"""
        try:
            sql = """
            SELECT 
                p.id, p.beauty_title, p.title, p.other_titles, p.connect, p.add_time,
                p.level_winter, p.level_summer, p.level_autumn, p.level_spring,
                p.status,
                u.email, u.fam, u.name, u.otc, u.phone,
                c.latitude, c.longitude, c.height,
                array_agg(json_build_object('data', i.data, 'title', i.title)) as images
            FROM pereval_added p
            JOIN users u ON p.user_id = u.id
            JOIN coords c ON p.coord_id = c.id
            LEFT JOIN images i ON p.id = i.pereval_id
            WHERE p.id = %s
            GROUP BY p.id, u.id, c.id
            """

            self.cursor.execute(sql, (pereval_id,))
            result = self.cursor.fetchone()

            if not result:
                return None

            # Преобразуем результат в словарь
            pereval_data = {
                'id': result[0],
                'beauty_title': result[1],
                'title': result[2],
                'other_titles': result[3],
                'connect': result[4],
                'add_time': result[5].isoformat() if result[5] else None,
                'level': {
                    'winter': result[6],
                    'summer': result[7],
                    'autumn': result[8],
                    'spring': result[9]
                },
                'status': result[10],
                'user': {
                    'email': result[11],
                    'fam': result[12],
                    'name': result[13],
                    'otc': result[14],
                    'phone': result[15]
                },
                'coords': {
                    'latitude': float(result[16]),
                    'longitude': float(result[17]),
                    'height': result[18]
                },
                'images': result[19] if result[19] and result[19][0] else []
            }

            return pereval_data

        except Exception as e:
            print(f"Ошибка получения перевала: {e}")
            return None

    def _add_or_get_user(self, user_data: Dict[str, str]) -> Optional[int]:
        """находит пользователя по email или создает нового"""
        try:
            # ищем пользователя
            self.cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (user_data['email'],)
            )
            result = self.cursor.fetchone()

            if result:
                return result[0]

            # создаем нового
            self.cursor.execute(
                """
                INSERT INTO users (email, fam, name, otc, phone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_data['email'],
                    user_data['fam'],
                    user_data['name'],
                    user_data['otc'],
                    user_data['phone']
                )
            )

            user_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return user_id

        except Exception as e:
            print(f"Ошибка работы с пользователем: {e}")
            return None