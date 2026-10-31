class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def unavailable(service: str):
    raise ServiceError(503, "service_unavailable", f"{service} is not configured.")


def pending(operation: str):
    raise ServiceError(501, "not_implemented", f"{operation} is not implemented in the foundation.")
