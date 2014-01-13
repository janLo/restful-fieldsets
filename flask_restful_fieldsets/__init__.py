from .fields import OptionalNestedField, ObjectMemberField
from .fieldset import Fieldset


def marshall_with_fieldset(fieldset_cls, *args, **kwargs):
    return fieldset_cls.do_marshall(*args, **kwargs)