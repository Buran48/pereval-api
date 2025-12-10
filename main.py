from fastapi import FastAPI, HTTPException, Query
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
    add_time: Optional[str] = None
    user: User
    coords: Coords
    level: Level
    images: List[Image]


class PerevalUpdate(BaseModel):
    """Модель для обновления перевала (без данных пользователя)"""
    beauty_title: Optional[str] = None
    title: Optional[str] = None
    other_titles: Optional[str] = None
    connect: Optional[str] = None
    add_time: Optional[str] = None
    coords: Optional[Coords] = None
    level: Optional[Level] = None
    images: Optional[List[Image]] = None


class ResponseModel(BaseModel):
    status: int
    message: Optional[str] = None
    id: Optional[int] = None


class UpdateResponse(BaseModel):
    state: int  # 1 - успех, 0 - ошибка
    message: Optional[str] = None


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

        data_dict = pereval.dict()
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


@app.get("/submitData/{pereval_id}", response_model=Dict[str, Any])
async def get_pereval(pereval_id: int):
    """Получить перевал по ID"""
    db_manager = DatabaseManager()
    if not db_manager.connect():
        raise HTTPException(status_code=500, detail="Ошибка подключения к БД")

    pereval = db_manager.get_pereval(pereval_id)
    db_manager.disconnect()

    if not pereval:
        raise HTTPException(status_code=404, detail="Перевал не найден")

    return pereval


@app.patch("/submitData/{pereval_id}", response_model=UpdateResponse)
async def update_pereval(pereval_id: int, update_data: PerevalUpdate):
    """Обновить перевал (только если статус 'new')"""

    # Получаем dict с переданными полями (без unset)
    update_dict = update_data.dict(exclude_unset=True)

    # Проверяем что есть хоть одно поле для обновления
    if not update_dict:
        return UpdateResponse(state=0, message="Нет данных для обновления")

    # Проверяем что нет попытки изменить пользователя
    if 'user' in update_dict:
        return UpdateResponse(state=0, message="Нельзя изменять данные пользователя")

    db_manager = DatabaseManager()
    if not db_manager.connect():
        return UpdateResponse(state=0, message="Ошибка подключения к БД")

    result = db_manager.update_pereval(pereval_id, update_dict)
    db_manager.disconnect()

    return UpdateResponse(state=result['state'], message=result['message'])



@app.get("/submitData/", response_model=List[Dict[str, Any]])
async def get_user_perevals(user__email: str = Query(..., alias="user__email")):
    """Получить все перевалы пользователя по email"""
    db_manager = DatabaseManager()
    if not db_manager.connect():
        raise HTTPException(status_code=500, detail="Ошибка подключения к БД")

    perevals = db_manager.get_user_perevals(user__email)
    db_manager.disconnect()

    return perevals


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)


