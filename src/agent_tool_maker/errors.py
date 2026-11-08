# Machine-readable causes ATM defines. A hint relayed from another process is kept only if it is one of these.
HINTS = frozenset({"fake_ip_tunnel"})


class RouterError(Exception):
    """Safe-to-display error; never include upstream bodies or request headers.

    `hint` is an optional machine-readable cause (for example "fake_ip_tunnel"), additive to
    the unchanged code; it carries no hostname, address or provider text.
    """
    def __init__(self, code: str, message: str, *, uncertain: bool = False, hint: str | None = None):
        super().__init__(message)
        self.code, self.uncertain, self.hint = code, uncertain, hint

    def as_dict(self):
        result = {"code": self.code, "message": str(self), "outcome_uncertain": self.uncertain}
        if self.hint:
            result["hint"] = self.hint
        return result


def relayed_hint(value):
    """The hint of an error dict received over a local socket (broker, server runtime), or None."""
    return value if isinstance(value, str) and value in HINTS else None
