"""Commercial fixtures used only by the synthetic generator."""

from decimal import Decimal
from typing import NamedTuple

from dealmind.models.enums import ActivityType, LossReason

STAGES = (
    ("new_lead", "Новая заявка"),
    ("contact_established", "Контакт установлен"),
    ("qualified", "Квалификация"),
    ("consultation", "Консультация"),
    ("offer_sent", "Предложение отправлено"),
    ("decision_pending", "Ожидание решения"),
    ("won", "Успешная продажа"),
    ("lost", "Сделка потеряна"),
)
PROGRAMS = (
    ("Python Developer", Decimal("89000"), Decimal("990")),
    ("Data Analyst", Decimal("79000"), Decimal("890")),
    ("AI Engineer", Decimal("129000"), Decimal("1490")),
    ("n8n & Business Automation", Decimal("59000"), Decimal("690")),
    ("Full Stack Developer", Decimal("119000"), Decimal("1390")),
    ("Digital Marketing", Decimal("69000"), Decimal("790")),
)


class ManagerProfile(NamedTuple):
    status_weights: tuple[int, int, int]  # open, won, lost
    communications: int
    cycle_days: int
    overdue_percent: int


PROFILES = (
    ManagerProfile((10, 22, 7), 5, 16, 8),
    ManagerProfile((12, 17, 9), 6, 28, 12),
    ManagerProfile((14, 13, 12), 4, 22, 15),
    ManagerProfile((16, 14, 12), 7, 18, 12),
    ManagerProfile((14, 12, 14), 4, 24, 23),
    ManagerProfile((16, 9, 18), 3, 34, 58),
    ManagerProfile((13, 7, 16), 2, 32, 44),
    ManagerProfile((5, 4, 6), 3, 20, 18),
)
MESSAGES = {
    ActivityType.CALL: ("Обсудили расписание занятий.", "Уточнили опыт и учебную цель клиента."),
    ActivityType.EMAIL: (
        "Клиент получил план курса и обсудил условия.",
        "Согласовали формат обратной связи.",
    ),
    ActivityType.MESSAGE: ("Обсудили нагрузку и практику.", "Клиент уточнил различия тарифов."),
    ActivityType.MEETING: (
        "Провели консультацию по программе.",
        "Разобрали учебный проект и требования.",
    ),
}
LOSS_WEIGHTS = (25, 20, 20, 10, 8, 7, 5, 5)
LOSS_NOTES = {
    LossReason.PRICE: "Стоимость предложения выше ожиданий.",
    LossReason.NO_BUDGET: "Бюджет на обучение пока отсутствует.",
    LossReason.NO_RESPONSE: "После последнего контакта дальнейшего ответа нет.",
    LossReason.NOT_INTERESTED: "Клиент утратил интерес к направлению.",
    LossReason.COMPETITOR: "Выбрана другая программа.",
    LossReason.TIMING: "Сроки набора не подошли.",
    LossReason.PRODUCT_MISMATCH: "Программа не соответствует учебной цели.",
    LossReason.OTHER: "Зафиксирована другая причина отказа.",
}
