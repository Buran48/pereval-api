from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from dotenv import load_dotenv
from database import DatabaseManager

load_dotenv()

app = FastAPI(title="Pereval API", description="API для мобильного приложения Перевалы")


class User(BaseModel):
    email: str
    fam: str
    name: str
    otc: str
    phone: str


class Coords(BaseModel):
    latitude: float
    longitude: float
    height: int


class Level(BaseModel):
    winter: str = ""
    summer: str = ""
    autumn: str = ""
    spring: str = ""


class Image(BaseModel):
    data: str
    title: str


class PerevalData(BaseModel):
    beauty_title: str
    title: str
    other_titles: str = ""
    connect: str = ""
    add_time: str
    user: User
    coords: Coords
    level: Level
    images: List[Image]


class ResponseModel(BaseModel):
    status: int
    message: Optional[str] = None
    id: Optional[int] = None


@app.post("/submitData", response_model=ResponseModel)
async def submit_data(pereval: PerevalData):
    try:
        # Проверка обязательных полей
        if not pereval.title or not pereval.user.email:
            return ResponseModel(
                status=400,
                message="Не хватает обязательных полей (title или email)",
                id=None
            )

        db_manager = DatabaseManager()
        if not db_manager.connect():
            return ResponseModel(
                status=500,
                message="Ошибка подключения к базе данных",
                id=None
            )

        data_dict = pereval.model_dump()
        record_id = db_manager.add_pereval(data_dict)
        db_manager.disconnect()

        if record_id:
            return ResponseModel(
                status=200,
                message=None,
                id=record_id
            )
        else:
            return ResponseModel(
                status=500,
                message="Ошибка при добавлении данных в БД",
                id=None
            )

    except Exception as e:
        return ResponseModel(
            status=500,
            message=f"Внутренняя ошибка сервера: {str(e)}",
            id=None
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)