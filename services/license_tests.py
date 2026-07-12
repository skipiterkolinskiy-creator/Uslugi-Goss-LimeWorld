import json
import random
import sqlite3
from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class LicenseConfig:
    code: str
    title: str
    fee: int
    questions_count: int
    passing_score: int
    bank: str | None
    requires_license: str | None = None


LICENSES = {
    "AUTO": LicenseConfig("AUTO", "Автомобиль", 3200, 15, 13, "road"),
    "TRUCK": LicenseConfig("TRUCK", "Грузовик", 4200, 15, 13, "road"),
    "MOTO": LicenseConfig("MOTO", "Мотоцикл", 2800, 15, 13, "moto"),
    "WEAPON": LicenseConfig("WEAPON", "Оружие", 6500, 16, 14, "weapon"),
    "FISHING": LicenseConfig("FISHING", "Рыбалка", 1200, 0, 0, None),
    "HUNTING": LicenseConfig("HUNTING", "Охота", 2600, 0, 0, None, "WEAPON"),
}


ROAD_QUESTIONS = [
    ("Что необходимо сделать перед перестроением?", ["Включить поворотник и убедиться в безопасности", "Резко повернуть", "Посигналить"], 0),
    ("Когда нужно уступить пешеходу?", ["На пешеходном переходе", "Только ночью", "Никогда"], 0),
    ("Что означает красный сигнал светофора?", ["Остановиться", "Ускориться", "Ехать осторожно"], 0),
    ("Что делать при ДТП в RP?", ["Остановиться и вызвать службы", "Скрыться", "Удалить машину"], 0),
    ("Какой стиль езды безопасен в городе?", ["Соблюдать дистанцию", "Ехать вплотную", "Подрезать"], 0),
    ("Перед поворотом водитель обязан:", ["Занять правильную полосу", "Выключить фары", "Открыть дверь"], 0),
    ("Жёлтый сигнал светофора обычно означает:", ["Подготовиться к остановке", "Всегда ускориться", "Разворот запрещён навсегда"], 0),
    ("Можно ли выезжать на встречную полосу без причины?", ["Нет", "Да", "Только ради обгона в городе"], 0),
    ("Приоритет спецтранспорта с маячками:", ["Уступить дорогу", "Игнорировать", "Обогнать"], 0),
    ("Что важно при парковке?", ["Не мешать движению", "Закрыть перекрёсток", "Встать на переходе"], 0),
    ("Перед началом движения нужно:", ["Убедиться в безопасности", "Сразу газовать", "Выключить зеркала"], 0),
    ("Дистанция нужна, чтобы:", ["Успеть затормозить", "Красиво ехать", "Занять дорогу"], 0),
    ("Что делать при требовании полиции остановиться?", ["Остановиться безопасно", "Уехать", "Сменить номер"], 0),
    ("Разворот выполняют:", ["Там, где он безопасен и разрешён", "На любом мосту", "В тоннеле"], 0),
    ("Главное правило RP-водителя:", ["Не создавать опасность и соблюдать RP", "Побеждать всех", "Игнорировать знаки"], 0),
]

MOTO_QUESTIONS = [
    ("Что особенно важно для мотоциклиста?", ["Защитная экипировка", "Езда без света", "Игнорирование полос"], 0),
    ("Перед манёвром на мотоцикле нужно:", ["Проверить зеркала и слепую зону", "Закрыть глаза", "Резко наклониться"], 0),
    ("Безопасная скорость выбирается по:", ["Дорожным условиям", "Настроению", "Громкости двигателя"], 0),
    ("Мотоциклист на мокрой дороге должен:", ["Ехать плавно", "Резко тормозить", "Дрифтовать"], 0),
    ("Дистанция для мотоцикла:", ["Обязательна", "Не нужна", "Только ночью"], 0),
    ("Шлем в RP-документах считается:", ["Средством безопасности", "Украшением", "Причиной нарушать"], 0),
    ("При падении груза с транспорта впереди нужно:", ["Снизить скорость и объехать безопасно", "Ускориться", "Врезаться"], 0),
    ("Междурядье в плотном потоке:", ["Опасно и требует осторожности", "Всегда обязательно", "Даёт иммунитет"], 0),
    ("Поворотник на мотоцикле:", ["Нужно включать заранее", "Не нужен", "Включается после манёвра"], 0),
    ("Что делать при погоне полиции?", ["Соблюдать RP и требования сервера", "Нарушать все правила", "Выходить из игры"], 0),
    ("Торможение на мотоцикле лучше выполнять:", ["Плавно", "Только задним колесом", "Только стеной"], 0),
    ("Пассажир на мотоцикле должен:", ["Не мешать управлению", "Прыгать", "Закрывать обзор"], 0),
    ("Перед поездкой проверяют:", ["Тормоза и свет", "Цвет неба", "Радио"], 0),
    ("В тёмное время суток важно:", ["Быть заметным", "Ехать без фар", "Выключить звук"], 0),
    ("Основная цель экзамена:", ["Проверить безопасное RP-вождение", "Научить трюкам", "Обойти правила"], 0),
]

WEAPON_QUESTIONS = [
    ("Главный принцип обращения с оружием в RP?", ["Считать его опасным и соблюдать правила", "Размахивать в толпе", "Пугать игроков"], 0),
    ("Где хранится оружие по RP-нормам?", ["В безопасном месте", "На земле", "У случайного игрока"], 0),
    ("Можно ли угрожать без RP-причины?", ["Нет", "Да", "Всегда"], 0),
    ("Перед использованием оружия персонаж должен:", ["Иметь законное RP-основание", "Игнорировать ситуацию", "Спамить"], 0),
    ("Что запрещено на экзамене?", ["Обсуждать вред и обходы законов", "Говорить о безопасности", "Соблюдать нормы"], 0),
    ("При проверке документов нужно:", ["Сотрудничать по RP", "Сразу стрелять", "Выходить из игры"], 0),
    ("Оружейная лицензия даёт право:", ["Владеть по правилам сервера", "Нарушать RP", "Игнорировать полицию"], 0),
    ("Если оружие потеряно:", ["Сообщить компетентным службам по RP", "Скрыть", "Обвинить другого"], 0),
    ("Демонстрация оружия в общественном месте:", ["Недопустима без причины", "Обязательна", "Всегда смешна"], 0),
    ("Безопасное направление оружия:", ["В сторону, где нет людей", "На людей", "На администратора"], 0),
    ("Конфликт лучше решать:", ["Без эскалации", "Сразу оружием", "Нарушением правил"], 0),
    ("При задержании с оружием:", ["Следовать RP-процедуре", "Убегать OOC", "Удалять предметы"], 0),
    ("Лицензия может быть изъята за:", ["Нарушение RP-законов", "Вежливость", "Оплату пошлины"], 0),
    ("Охотничья лицензия требует:", ["Оружейную лицензию", "Медкарту только", "Ничего"], 0),
    ("Проверка безопасности нужна:", ["Всегда перед действиями", "Никогда", "Только для новичков"], 0),
    ("Задача правил оружия:", ["Сохранить честный и безопасный RP", "Дать преимущество", "Обойти модерацию"], 0),
]

BANKS = {"road": ROAD_QUESTIONS, "moto": MOTO_QUESTIONS, "weapon": WEAPON_QUESTIONS}


class LicenseTestsService:
    def config(self, code: str) -> LicenseConfig:
        return LICENSES[code]

    def can_apply_hunting(self, licenses: str) -> bool:
        return "WEAPON" in {part.strip().upper() for part in licenses.split(",")}

    def start_test(self, user_id: int, code: str) -> None:
        cfg = self.config(code)
        bank = BANKS[cfg.bank or ""]
        indices = list(range(len(bank)))
        random.shuffle(indices)
        selected = indices[: cfg.questions_count]
        with sqlite3.connect(settings.database_path) as conn:
            conn.execute(
                "REPLACE INTO license_tests(user_id, license_code, current_index, score, used_questions, answered_callbacks) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, code, 0, 0, json.dumps(selected), ""),
            )
            conn.commit()

    def get_current_question(self, user_id: int, code: str) -> tuple[int, int, str, list[str], str] | None:
        cfg = self.config(code)
        with sqlite3.connect(settings.database_path) as conn:
            row = conn.execute(
                "SELECT current_index, score, used_questions FROM license_tests WHERE user_id=? AND license_code=?",
                (user_id, code),
            ).fetchone()
        if row is None:
            return None
        index, score, raw = row
        selected = json.loads(raw)
        if index >= len(selected):
            return None
        q_index = selected[index]
        question, answers, _ = BANKS[cfg.bank or ""][q_index]
        question_id = f"{code}-{index}"
        return index, score, question, answers, question_id

    def answer(self, user_id: int, code: str, question_id: str, answer_index: int) -> tuple[bool, int, int, bool]:
        cfg = self.config(code)
        with sqlite3.connect(settings.database_path) as conn:
            row = conn.execute(
                "SELECT current_index, score, used_questions, answered_callbacks FROM license_tests WHERE user_id=? AND license_code=?",
                (user_id, code),
            ).fetchone()
            if row is None:
                return False, 0, cfg.questions_count, True
            index, score, raw, answered_raw = row
            answered = set(filter(None, answered_raw.split(",")))
            if question_id in answered:
                return False, score, cfg.questions_count, False
            selected = json.loads(raw)
            q_index = selected[index]
            correct = BANKS[cfg.bank or ""][q_index][2]
            if answer_index == correct:
                score += 1
            answered.add(question_id)
            index += 1
            finished = index >= cfg.questions_count
            conn.execute(
                "UPDATE license_tests SET current_index=?, score=?, answered_callbacks=? WHERE user_id=? AND license_code=?",
                (index, score, ",".join(sorted(answered)), user_id, code),
            )
            conn.commit()
        return True, score, cfg.questions_count, finished

    def clear(self, user_id: int, code: str) -> None:
        with sqlite3.connect(settings.database_path) as conn:
            conn.execute("DELETE FROM license_tests WHERE user_id=? AND license_code=?", (user_id, code))
            conn.commit()


license_tests_service = LicenseTestsService()
