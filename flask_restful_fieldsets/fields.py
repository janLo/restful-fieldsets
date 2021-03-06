from flask.ext.restful import fields


class OptionalNestedField(fields.Raw):
    """This can be used to nest Fieldsets into each other.

    It works like the Nested field but uses Fieldsets as nested
    structure instead of a simple dict. The user can select
    fields from the nested set by prefixing the fieldname with
    the name of the field in the parent set.

    The "plain_key" argument specify which attribute should be
    used if the user wont embedd the set.
    """
    _optional_nested = True

    def __init__(self, nested, plain_key, default=None, attribute=None, allow_none=False, plain_field=None):
        super().__init__(default, attribute)
        self._plain_key = plain_key
        self._plain_field = plain_field
        self._nested = nested if not isinstance(nested, type) else nested()
        self._allow_none = allow_none

    def key_field(self):
        if self._plain_key is None:
            return None
        return ObjectMemberField(self._plain_key, self.default, self.attribute, self._plain_field)

    def nested_fieldset(self):
        return self._nested

    def nested_kwargs(self):
        return {"attribute": self.attribute, "default": self.default, "allow_null": self._allow_none}


class ObjectMemberField(fields.Raw):
    """Get a member value from the value object as field value

    Use this if your attribute is an object but you only need one
    member from it. It extracts teh member and optionally chain
    another field format() method.
    """

    def __init__(self, member, default=None, attribute=None, member_field=None):
        """Initialize the ObjectMemberField

        :param member: The member in the object that should be used
        :param default: The default value
        :param attribute: The attribute to work on
        :param member_field: A flask restful field that should be used to format the member
        """
        super().__init__(default=default, attribute=attribute)
        self.member = member
        self.member_field = member_field

    @property
    def _embedded_instance(self):
        if isinstance(self.member_field, type):
            return self.member_field()
        return self.member_field

    def format(self, value):
        if hasattr(value, self.member):
            attr = getattr(value, self.member)
            if self.member_field is None:
                return attr
            else:
                return self._embedded_instance.format(attr)
        return None
