import pytest
pytest.skip("для ручного тестирования на локальном сервере", allow_module_level=True)

import requests
import json

url = "http://localhost:8001/submitData"
headers = {
    "accept": "application/json",
    "Content-Type": "application/json"
}

data = {
    "beauty_title": "перевал",
    "title": "тестперевал",
    "other_titles": "тест",
    "connect": "соединяет",
    "add_time": "2023-12-06 10:30:00",
    "user": {
        "email": "test@example.com",
        "fam": "тестфамилия",
        "name": "тестимя",
        "otc": "тестотчество",
        "phone": "123"
    },
    "coords": {
        "latitude": "55.7558",
        "longitude": "37.6176",
        "height": "200"
    },
    "level": {
        "winter": "1A",
        "summer": "1B",
        "autumn": "1A",
        "spring": ""
    },
    "images": [
        {
            "data": "тестфото",
            "title": "фото"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
