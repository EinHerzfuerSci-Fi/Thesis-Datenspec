from typing import Annotated, Any

from pydantic import Field, TypeAdapter

from ._base import FORBID_EXTRA
from .alert import AlertRecord
from .data import DataRecord
from .err import ErrRecord
from .info import InfoRecord
from .tele import TeleRecord

Record = Annotated[
    DataRecord | AlertRecord | TeleRecord | ErrRecord | InfoRecord,
    Field(discriminator="kind"),
]

RECORD_MODELS = (DataRecord, AlertRecord, TeleRecord, ErrRecord, InfoRecord)

record_adapter: TypeAdapter[Record] = TypeAdapter(Record)


def parse_record(line: str | bytes, *, forbid_extra: bool = False) -> Record:
    """Validate one JSON line. forbid_extra is for the spec's own tests, not for runtime."""
    return record_adapter.validate_json(line, context={FORBID_EXTRA: forbid_extra})


def validate_record(obj: Any, *, forbid_extra: bool = False) -> Record:
    return record_adapter.validate_python(obj, context={FORBID_EXTRA: forbid_extra})
