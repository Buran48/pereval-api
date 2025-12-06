import os
import psycopg2
from psycopg2 import sql, errors
from typing import Optional, Dict, Any
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