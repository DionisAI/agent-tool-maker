class RouterError(Exception):
    """Safe-to-display error; never include upstream bodies or request headers."""
    def __init__(self, code: str, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.code, self.uncertain = code, uncertain

    def as_dict(self):
        return {"code": self.code, "message": str(self), "outcome_uncertain": self.uncertain}
