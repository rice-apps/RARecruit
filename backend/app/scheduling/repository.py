from app.scheduling.models import (
    JsonRepository,
    Config,
    User,
    Availability,
    Recusal,
)

repo = JsonRepository()

def load_inputs() -> tuple[
    Config,
    list[User],
    list[Availability],
    list[Recusal]
]:
    return (
        repo.load_config(),
        repo.load_users(),
        repo.load_availability(),
        repo.load_recusals(),
    )