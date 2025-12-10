import os
import psycopg2
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
load_dotenv()



class DatabaseManager:
    def __init__(self):
        # параметры подключения читаем из .env
        self.db_host = os.getenv("FSTR_DB_HOST", "localhost")
        self.db_port = os.getenv("FSTR_DB_PORT", "5432")
        self.db_login = os.getenv("FSTR_DB_LOGIN", "postgres")
        self.db_pass = os.getenv("FSTR_DB_PASS", "")
        self.db_name = os.getenv("FSTR_DB_NAME", "pereval_db")

        self.connection = None
        self.cursor = None

    # подключение к БД
    def connect(self):
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

    # отключение от БД
    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    # создание таблиц, если их нет
    def _create_tables(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    fam TEXT,
                    name TEXT,
                    otc TEXT,
                    phone TEXT
                );

                CREATE TABLE IF NOT EXISTS coords (
                    id SERIAL PRIMARY KEY,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    height INTEGER
                );

                CREATE TABLE IF NOT EXISTS pereval_added (
                    id SERIAL PRIMARY KEY,
                    beauty_title TEXT,
                    title TEXT,
                    other_titles TEXT,
                    connect TEXT,
                    add_time TIMESTAMP,
                    user_id INTEGER REFERENCES users(id),
                    coord_id INTEGER REFERENCES coords(id),
                    level_winter TEXT,
                    level_summer TEXT,
                    level_autumn TEXT,
                    level_spring TEXT,
                    status TEXT DEFAULT 'new'
                );

                CREATE TABLE IF NOT EXISTS images (
                    id SERIAL PRIMARY KEY,
                    pereval_id INTEGER REFERENCES pereval_added(id) ON DELETE CASCADE,
                    data TEXT,
                    title TEXT
                );
            """)
            self.connection.commit()
        except Exception as e:
            print(f"Ошибка создания таблиц: {e}")
            self.connection.rollback()

    # получение или создание пользователя
    def _add_or_get_user(self, data: Dict[str, str]) -> Optional[int]:
        try:
            self.cursor.execute("SELECT id FROM users WHERE email=%s", (data["email"],))
            row = self.cursor.fetchone()

            if row:
                return row[0]

            self.cursor.execute(
                """
                INSERT INTO users (email, fam, name, otc, phone)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
                """,
                (data["email"], data["fam"], data["name"], data["otc"], data["phone"])
            )
            user_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return user_id

        except Exception as e:
            print(f"Ошибка работы с пользователем: {e}")
            self.connection.rollback()
            return None

    # добавление перевала
    def add_pereval(self, data: Dict[str, Any]) -> Optional[int]:
        try:
            user_id = self._add_or_get_user(data["user"])
            if not user_id:
                return None

            self.cursor.execute(
                "INSERT INTO coords (latitude, longitude, height) VALUES (%s, %s, %s) RETURNING id",
                (
                    float(data["coords"]["latitude"]),
                    float(data["coords"]["longitude"]),
                    int(data["coords"]["height"])
                )
            )
            coord_id = self.cursor.fetchone()[0]

            self.cursor.execute(
                """
                INSERT INTO pereval_added (
                    beauty_title, title, other_titles, connect, add_time,
                    user_id, coord_id,
                    level_winter, level_summer, level_autumn, level_spring
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["beauty_title"],
                    data["title"],
                    data["other_titles"],
                    data["connect"],
                    data["add_time"],
                    user_id,
                    coord_id,
                    data["level"]["winter"],
                    data["level"]["summer"],
                    data["level"]["autumn"],
                    data["level"]["spring"]
                )
            )
            pereval_id = self.cursor.fetchone()[0]

            for img in data["images"]:
                self.cursor.execute(
                    "INSERT INTO images (pereval_id, data, title) VALUES (%s, %s, %s)",
                    (pereval_id, img["data"], img["title"])
                )

            self.connection.commit()
            return pereval_id

        except Exception as e:
            print(f"Ошибка добавления перевала: {e}")
            self.connection.rollback()
            return None

    # получение одного перевала
    def get_pereval(self, pereval_id: int) -> Optional[Dict[str, Any]]:
        try:
            self.cursor.execute(
                """
                SELECT
                    p.id, p.beauty_title, p.title, p.other_titles, p.connect,
                    p.add_time,
                    p.level_winter, p.level_summer, p.level_autumn, p.level_spring,
                    p.status,
                    u.email, u.fam, u.name, u.otc, u.phone,
                    c.latitude, c.longitude, c.height
                FROM pereval_added p
                JOIN users u ON p.user_id = u.id
                JOIN coords c ON p.coord_id = c.id
                WHERE p.id = %s
                """,
                (pereval_id,)
            )
            row = self.cursor.fetchone()

            if not row:
                return None

            self.cursor.execute(
                "SELECT data, title FROM images WHERE pereval_id=%s",
                (pereval_id,)
            )
            images = [{"data": r[0], "title": r[1]} for r in self.cursor.fetchall()]

            return {
                "id": row[0],
                "beauty_title": row[1],
                "title": row[2],
                "other_titles": row[3],
                "connect": row[4],
                "add_time": row[5].isoformat() if row[5] else None,
                "level": {
                    "winter": row[6],
                    "summer": row[7],
                    "autumn": row[8],
                    "spring": row[9]
                },
                "status": row[10],
                "user": {
                    "email": row[11],
                    "fam": row[12],
                    "name": row[13],
                    "otc": row[14],
                    "phone": row[15]
                },
                "coords": {
                    "latitude": row[16],
                    "longitude": row[17],
                    "height": row[18]
                },
                "images": images
            }

        except Exception as e:
            print(f"Ошибка получения перевала: {e}")
            return None

    # обновление перевала
    def update_pereval(self, pereval_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.cursor.execute("SELECT status FROM pereval_added WHERE id=%s", (pereval_id,))
            row = self.cursor.fetchone()

            if not row:
                return {"state": 0, "message": "Перевал не найден"}

            if row[0] != "new":
                return {"state": 0, "message": f"Редактирование запрещено, статус: {row[0]}"}

            if "coords" in data:
                c = data["coords"]
                self.cursor.execute(
                    """
                    UPDATE coords
                    SET latitude=%s, longitude=%s, height=%s
                    WHERE id = (SELECT coord_id FROM pereval_added WHERE id=%s)
                    """,
                    (
                        float(c["latitude"]),
                        float(c["longitude"]),
                        int(c["height"]),
                        pereval_id
                    )
                )

            allowed = ["beauty_title", "title", "other_titles", "connect"]
            for key in allowed:
                if key in data:
                    self.cursor.execute(
                        f"UPDATE pereval_added SET {key}=%s WHERE id=%s",
                        (data[key], pereval_id)
                    )

            self.connection.commit()
            return {"state": 1, "message": "Успешно обновлено"}

        except Exception as e:
            print(f"Ошибка обновления: {e}")
            self.connection.rollback()
            return {"state": 0, "message": str(e)}

    # список всех перевалов пользователя
    def get_user_perevals(self, email: str) -> List[Dict[str, Any]]:
        try:
            self.cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            row = self.cursor.fetchone()

            if not row:
                return []

            self.cursor.execute(
                "SELECT id FROM pereval_added WHERE user_id=%s",
                (row[0],)
            )
            ids = [r[0] for r in self.cursor.fetchall()]

            return [self.get_pereval(pid) for pid in ids]

        except Exception as e:
            print(f"Ошибка получения списка перевалов: {e}")
            return []

