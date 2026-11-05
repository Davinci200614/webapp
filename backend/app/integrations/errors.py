class IntegrationError(RuntimeError):
    """Provider failure with a safe, stable error code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
