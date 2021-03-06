from .fields import OptionalNestedField, ObjectMemberField
from .fieldset import Fieldset


def marshal_with_fieldset(fieldset_cls, *args, **kwargs):
    return fieldset_cls.do_marshal(*args, **kwargs)