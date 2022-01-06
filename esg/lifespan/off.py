from esg import Config


class LifespanOff:
    __slots__ = ["should_exit"]

    def __init__(self, config: Config) -> None:
        self.should_exit = False

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
