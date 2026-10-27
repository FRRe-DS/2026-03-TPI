class DomainError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        problem_type: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail
        self.problem_type = problem_type or f"/errores/{code.lower().replace('_', '-')}"
        super().__init__(detail)


class DependencyUnavailableError(DomainError):
    def __init__(self, detail: str = "Una dependencia requerida no está disponible.") -> None:
        super().__init__(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            title="Dependencia no disponible",
            detail=detail,
        )


class DependencyTimeoutError(DomainError):
    def __init__(self, detail: str = "Una dependencia excedió el tiempo de espera.") -> None:
        super().__init__(
            status_code=504,
            code="DEPENDENCY_TIMEOUT",
            title="Tiempo de espera agotado",
            detail=detail,
        )
