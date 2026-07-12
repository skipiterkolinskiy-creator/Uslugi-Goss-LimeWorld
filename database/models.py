from dataclasses import dataclass


@dataclass(slots=True)
class CitizenData:
    passport: int
    login_code: str
    telegram_id: int
    username: str
    last_name: str
    first_name: str
    patronymic: str
    age: int
    birthdate: str
    gender: str
    first_citizenship: str
    second_citizenship: str
    nationality: str
    skin: str
    hair: str
    eyes: str
    appearance: str
    military: str
    photo_file_id: str
    status: str = "Жив"
    wanted: str = "Нет"
    fines: str = "0"
    licenses: str = ""
    job: str = ""
    notes: str = ""
    registered_at: str = ""

    @property
    def fio(self) -> str:
        return " ".join(x for x in [self.last_name, self.first_name, self.patronymic] if x).strip()


@dataclass(slots=True)
class SearchCitizen:
    passport: int
    telegram_id: str
    username: str
    fio: str
    age: str
    status: str
    wanted: str
    fines: str
    licenses: str
    job: str
    raw: dict[str, str]
