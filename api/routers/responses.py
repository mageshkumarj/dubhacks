from ..schemas.common import Envelope

ERROR_RESPONSES = {
    404: {"model": Envelope[None], "description": "Not found"},
    409: {"model": Envelope[None], "description": "Conflict"},
    422: {"model": Envelope[None], "description": "Validation error"},
    503: {"model": Envelope[None], "description": "Dataset unavailable"},
}
